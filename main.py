import os, json, time, html, re
from datetime import datetime, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

BASE = "https://data-api.binance.vision"
DOCS = "docs"
STATE_FILE = "state.json"
PAPER_FILE = "paper_trades.json"
USER_AGENT = "NIRA-Crypto-Signal-Board/1.0"

# Exclude stablecoins and leveraged tokens from dynamic Top 10 selection.
EXCLUDED_BASES = {
    "USDT","USDC","FDUSD","TUSD","BUSD","DAI","USDE","USDD","PYUSD",
    "EUR","TRY","BRL","GBP","BIDR","UST","USTC","LUNA","UP","DOWN","BULL","BEAR"
}
POSITIVE = {
    "approval","approved","adoption","launch","launched","partnership","integrate",
    "integration","inflow","surge","record","upgrade","mainnet","listing","listed",
    "growth","bullish","breakthrough","fund","funding","support","etf inflow"
}
NEGATIVE = {
    "hack","hacked","exploit","lawsuit","ban","banned","investigation","outflow",
    "crash","plunge","fraud","breach","stolen","delist","delisted","bearish",
    "liquidation","fine","charges","vulnerability","attack","bankruptcy"
}
COIN_ALIASES = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "ether", "eth"],
    "BNB": ["bnb", "binance coin"],
    "SOL": ["solana", "sol"],
    "XRP": ["xrp", "ripple"],
    "DOGE": ["dogecoin", "doge"],
    "ADA": ["cardano", "ada"],
    "TRX": ["tron", "trx"],
    "LINK": ["chainlink", "link"],
    "AVAX": ["avalanche", "avax"],
    "LTC": ["litecoin", "ltc"],
    "TON": ["toncoin", "ton"],
    "SUI": ["sui"],
    "DOT": ["polkadot", "dot"],
    "BCH": ["bitcoin cash", "bch"],
    "NEAR": ["near protocol", "near"],
    "APT": ["aptos", "apt"],
    "UNI": ["uniswap", "uni"],
    "AAVE": ["aave"],
    "ATOM": ["cosmos", "atom"]
}
def fetch_json(url, timeout=15):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))

def fetch_text(url, timeout=15):
    req = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def ema(values, period):
    if not values:
        return []
    k = 2 / (period + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(value * k + result[-1] * (1 - k))
    return result

def rsi(values, period=14):
    if len(values) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def load_json(path, fallback):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_top_coins():
    # Public market endpoint; no exchange API key is required.
    tickers = fetch_json(BASE + "/api/v3/ticker/24hr")
    selected = []
    for t in tickers:
        symbol = t.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        base_asset = symbol[:-4]
        if base_asset in EXCLUDED_BASES or any(base_asset.endswith(x) for x in ("UP","DOWN","BULL","BEAR")):
            continue
        price = safe_float(t.get("lastPrice"))
        volume = safe_float(t.get("quoteVolume"))
        if price <= 0 or volume <= 0:
            continue
        selected.append({
            "symbol": symbol,
            "coin": base_asset,
            "price": price,
            "change24h": safe_float(t.get("priceChangePercent")),
            "volume24h": volume
        })
    selected.sort(key=lambda x: x["volume24h"], reverse=True)
    return selected[:10]
    

def analyze_technical(symbol):
    query = urlencode({"symbol": symbol, "interval": "15m", "limit": 100})
    candles = fetch_json(BASE + "/api/v3/klines?" + query)
    # Ignore the currently forming candle.
    candles = candles[:-1]
    closes = [safe_float(c[4]) for c in candles]
    volumes = [safe_float(c[5]) for c in candles]
    if len(closes) < 35:
        raise ValueError("Not enough candle history")
    e9, e21 = ema(closes, 9), ema(closes, 21)
    ema_bull = e9[-1] > e21[-1]
    macd_line = [a-b for a,b in zip(ema(closes,12), ema(closes,26))]
    signal_line = ema(macd_line, 9)
    macd_bull = macd_line[-1] > signal_line[-1]
    r = rsi(closes)
    avg_vol = sum(volumes[-21:-1]) / max(1, len(volumes[-21:-1]))
    vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1
    score = 50
    score += 15 if ema_bull else -15
    score += 12 if macd_bull else -12
    if r >= 55 and r < 72: score += 12
    elif r <= 45 and r > 28: score -= 12
    elif r >= 72: score -= 5
    elif r <= 28: score += 5
    if vol_ratio >= 1.5:
        score += 5 if closes[-1] >= closes[-2] else -5
    score = max(0, min(100, round(score)))
    return {
        "rsi": round(r, 1), "ema9": e9[-1], "ema21": e21[-1],
        "macdBull": macd_bull, "emaBull": ema_bull,
        "volumeRatio": round(vol_ratio, 2), "score": score
    }
    

def get_news():
    feeds = [
        ("Cointelegraph", "https://cointelegraph.com/rss"),
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/")
    ]
    items, seen = [], set()
    for source, url in feeds:
        try:
            root = ET.fromstring(fetch_text(url, timeout=12))
            for item in root.findall(".//item")[:40]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                desc = re.sub("<[^>]+>", " ", item.findtext("description") or "")
                text = re.sub(r"\s+", " ", html.unescape(title + " " + desc)).strip()
                if title and title.lower() not in seen:
                    seen.add(title.lower())
                    items.append({"title": title, "link": link, "published": pub, "source": source, "text": text})
        except Exception as e:
            print("News feed unavailable:", source, str(e)[:160])
    return items[:60]

def sentiment_score(text):
    lower = text.lower()
    pos = sum(1 for word in POSITIVE if word in lower)
    neg = sum(1 for word in NEGATIVE if word in lower)
    if pos + neg == 0:
        return 0
    return max(-100, min(100, round(100 * (pos-neg) / (pos+neg))))
    
def coin_news_score(coin, news):
    aliases = COIN_ALIASES.get(coin, [coin.lower()])
    matches = []
    for item in news:
        haystack = item["text"].lower()
        if any(re.search(r"\b" + re.escape(alias.lower()) + r"\b", haystack) for alias in aliases):
            matches.append(item)
    # Most recent feed items are weighted equally in this first version.
    scores = [sentiment_score(n["text"]) for n in matches[:10]]
    score = round(sum(scores) / len(scores)) if scores else 0
    return score, matches[:5]

def get_fear_greed():
    try:
        data = fetch_json("https://api.alternative.me/fng/?limit=1")
        item = data["data"][0]
        return {"value": int(item["value"]), "label": item["value_classification"], "source": "Alternative.me"}
    except Exception as e:
        print("Fear & Greed unavailable:", str(e)[:160])
        return {"value": None, "label": "Unavailable", "source": "Alternative.me"}
        
def build_signals():
    coins = get_top_coins()
    news = get_news()
    fng = get_fear_greed()
    overall_news = sentiment_score(" ".join(n["text"] for n in news[:30]))
    if fng["value"] is None:
        sentiment_component = 0
    else:
        sentiment_component = round((fng["value"] - 50) * 2)
    # Shared sentiment combines Fear & Greed and broad news tone.
    market_sentiment = round(0.65 * sentiment_component + 0.35 * overall_news)
    results = []
    for coin in coins:
        try:
            tech = analyze_technical(coin["symbol"])
            news_score, matches = coin_news_score(coin["coin"], news)
            news_component = news_score
            combined = round(50 + (tech["score"] - 50) * 0.50 + news_component * 0.15 + market_sentiment * 0.10)
            combined = max(0, min(100, combined))
            # Avoid trading solely on headlines when technicals disagree.
            if combined >= 65 and tech["score"] >= 55:
                signal = "BUY"
            elif combined <= 35 and tech["score"] <= 45:
                signal = "SELL"
            else:
                signal = "WAIT"
            results.append({
                **coin, "technical": tech, "newsScore": news_score,
                "newsCount": len(matches), "news": matches,
                "marketSentiment": market_sentiment,
                "combinedScore": combined, "signal": signal,
                "reason": f"Technical {tech['score']}/100; News {news_score:+}; Market sentiment {market_sentiment:+}."
            })
            
        except Exception as e:
            results.append({
                **coin, "technical": None, "newsScore": 0, "newsCount": 0, "news": [],
                "marketSentiment": market_sentiment, "combinedScore": 50, "signal": "WAIT",
                "reason": "ডেটা পাওয়া যায়নি; নতুন ট্রেড সিগন্যাল তৈরি করা হয়নি।"
            })
            print("Technical analysis failed:", coin["symbol"], str(e)[:160])
    return results, news, fng, market_sentiment, overall_news

def telegram_send(text):
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram secrets not configured; skipping notification.")
        return False
    from urllib.request import Request, urlopen
    import urllib.parse
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode({"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}).encode()
    req = Request(url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=15) as response:
            result = json.loads(response.read().decode())
            return bool(result.get("ok"))
    except Exception as e:
        print("Telegram send failed:", str(e)[:200])
        return False

def update_paper_trades(results):
    paper = load_json(PAPER_FILE, {"open": [], "closed": []})
    now = datetime.now(timezone.utc).isoformat()
    by_symbol = {x["symbol"]: x for x in results}
    remaining = []
    for trade in paper.get("open", []):
        coin = by_symbol.get(trade["symbol"])
        if not coin:
            remaining.append(trade); continue
        price = coin["price"]
        exit_reason = None
        if trade["side"] == "BUY":
            if price <= trade["stopLoss"]: exit_reason = "STOP_LOSS"
            elif price >= trade["takeProfit"]: exit_reason = "TAKE_PROFIT"
        else:
            if price >= trade["stopLoss"]: exit_reason = "STOP_LOSS"
            elif price <= trade["takeProfit"]: exit_reason = "TAKE_PROFIT"
        if exit_reason:
            trade.update({"exitPrice": price, "exitTime": now, "status": exit_reason,
                          "pnlPercent": round(((price-trade["entry"])/trade["entry"]*100) *
                                             (1 if trade["side"] == "BUY" else -1), 3)})
            paper.setdefault("closed", []).append(trade)
            
        else:
            remaining.append(trade)
    paper["open"] = remaining
    open_symbols = {t["symbol"] for t in remaining}
    for coin in results:
        if coin["signal"] not in ("BUY", "SELL") or coin["symbol"] in open_symbols:
            continue
        price = coin["price"]
        side = coin["signal"]
        if side == "BUY":
            sl, tp = price * 0.985, price * 1.03
        else:
            sl, tp = price * 1.015, price * 0.97
        trade = {"symbol": coin["symbol"], "side": side, "entry": price,
                 "stopLoss": round(sl, 10), "takeProfit": round(tp, 10),
                 "entryTime": now, "status": "OPEN", "mode": "PAPER ONLY"}
        paper["open"].append(trade)
        open_symbols.add(coin["symbol"])
    paper["closed"] = paper.get("closed", [])[-500:]
    save_json(PAPER_FILE, paper)
    return paper

def write_dashboard(results, news, fng, market_sentiment, overall_news, paper):
    os.makedirs(DOCS, exist_ok=True)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "generatedAt": generated, "interval": "15m candles",
        "marketSentiment": market_sentiment, "overallNewsScore": overall_news,
        "fearGreed": fng, "coins": results,
        "news": news[:20], "paper": paper,
        "disclaimer": "Educational signal scanner only. Not financial advice. No live orders are placed."
    }
    save_json(os.path.join(DOCS, "data.json"), payload)
    rows = []
    for c in results:
        t = c["technical"] or {}
        color = {"BUY":"#16a34a", "SELL":"#dc2626", "WAIT":"#64748b"}.get(c["signal"], "#64748b")
        rows.append(
            "<tr><td><b>" + html.escape(c["coin"]) + "</b><small>" + html.escape(c["symbol"]) + "</small></td>"
            "<td>$" + format(c["price"], ",.8f").rstrip("0").rstrip(".") + "</td>"
            "<td>" + format(c["change24h"], "+.2f") + "%</td>"
            "<td><span class='pill' style='background:" + color + "'>" + c["signal"] + "</span></td>"
            "<td><b>" + str(c["combinedScore"]) + "</b>/100</td>"
            "<td>" + (str(t.get("rsi", "—")) if t else "—") + "</td>"
            "<td>" + str(c["newsScore"]) + "</td></tr>"
)
        
    news_cards = []
    for item in news[:12]:
        news_cards.append("<article><small>" + html.escape(item["source"]) + " · " + html.escape(item["published"]) +
                          "</small><a target='_blank' rel='noopener' href='" + html.escape(item["link"], quote=True) +
                          "'>" + html.escape(item["title"]) + "</a></article>")
    paper_open = paper.get("open", [])
    paper_closed = paper.get("closed", [])
    html_doc = """<!doctype html><html lang="bn"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300"><title>NIRA Crypto Signal Board</title>
<style>
:root{color-scheme:dark;--bg:#0b1220;--card:#121d30;--line:#26364e;--muted:#9aacc5;--text:#edf4ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px system-ui,Arial}
main{max-width:1100px;margin:auto;padding:16px}header{display:flex;justify-content:space-between;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:23px;margin:8px 0}h2{font-size:18px;margin:4px 0 12px}.muted,small{color:var(--muted)}
.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;min-width:0}
.big{font-size:25px;font-weight:750;margin-top:5px}.tablewrap{overflow:auto}
table{border-collapse:collapse;width:100%;min-width:650px}th,td{text-align:left;padding:11px 9px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12px}td small{display:block}.pill{color:white;border-radius:8px;padding:5px 8px;font-weight:750;font-size:12px}
article{padding:11px 0;border-bottom:1px solid var(--line)}article a{display:block;color:#9ec5ff;text-decoration:none;margin-top:4px}article a:hover{text-decoration:underline}
.notice{border:1px solid #8b6d27;background:#302817;padding:12px;border-radius:12px;margin:14px 0;color:#ffedbd}
    
@media(max-width:650px){main{padding:11px}.grid{grid-template-columns:1fr 1fr}.big{font-size:21px}h1{font-size:20px}}
</style></head><body><main>
<header><div><h1>🧠 NIRA Crypto Signal Board</h1><div class="muted">Top 10 USDT pairs · 15m Technical + News + Sentiment</div></div>
<div class="muted">Updated: """ + html.escape(generated) + """</div></header>
<div class="grid">
<div class="card"><div class="muted">Fear & Greed</div><div class="big">""" + (str(fng["value"]) if fng["value"] is not None else "N/A") + """</div><div>""" + html.escape(fng["label"]) + """</div><small>Source: Alternative.me</small></div>
<div class="card"><div class="muted">Market Sentiment</div><div class="big">""" + ("+" if market_sentiment > 0 else "") + str(market_sentiment) + """</div><div>Composite score · -100 to +100</div></div>
<div class="card"><div class="muted">Paper trades</div><div class="big">""" + str(len(paper_open)) + """ open</div><div>""" + str(len(paper_closed)) + """ closed</div></div>
</div>
<div class="notice">⚠️ Signal scores are experimental, not verified win probabilities. This dashboard never places real orders. Paper-trade SL/TP checks use periodic snapshots and can miss intraperiod price touches.</div>
<section class="card"><h2>Top 10 USDT pairs by 24h quote volume</h2><div class="tablewrap"><table><thead><tr><th>Coin</th><th>Price (USDT)</th><th>24h</th><th>Signal</th><th>Score</th><th>RSI</th><th>News</th></tr></thead><tbody>""" + "".join(rows) + """</tbody></table></div><small>Technical: RSI(14), EMA(9/21), MACD and relative volume. Score is a rule-based heuristic.</small></section>
<div class="grid" style="grid-template-columns:repeat(auto-fit,minmax(280px,1fr))">
<section class="card"><h2>Latest crypto news</h2>""" + ("".join(news_cards) if news_cards else "<p class='muted'>News feeds unavailable in latest run.</p>") + """</section>
<section class="card"><h2>Open paper trades</h2>""" + ("".join("<article><b>"+html.escape(t["symbol"])+" · "+t["side"]+"</b><br><small>Entry: "+str(t["entry"])+" | SL: "+str(t["stopLoss"])+" | TP: "+str(t["takeProfit"])+"</small></article>" for t in paper_open) if paper_open else "<p class='muted'>No open paper trades.</p>") + """<h2 style="margin-top:18px">Recent closed paper trades</h2>""" + ("".join("<article><b>"+html.escape(t["symbol"])+" · "+html.escape(t["status"])+"</b><br><small>P/L: "+str(t.get("pnlPercent","—"))+"%</small></article>" for t in paper_closed[-8:][::-1]) if paper_closed else "<p class='muted'>No closed trades yet.</p>") + """</section></div>
    
<footer class="muted" style="padding:18px 0;font-size:12px">Sources: Binance public market data · Alternative.me Fear & Greed · Crypto news RSS. """ + html.escape("Generated " + generated) + """<br>For research and education only. No guarantee of accuracy or profit.</footer>
</main></body></html>"""
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(html_doc)

def main():
    results, news, fng, market_sentiment, overall_news = build_signals()
    paper = update_paper_trades(results)
    write_dashboard(results, news, fng, market_sentiment, overall_news, paper)
    previous = load_json(STATE_FILE, {"signals": {}})
    old_signals = previous.get("signals", {})
    new_signals = {c["symbol"]: c["signal"] for c in results}
    alerts = []
    for coin in results:
        old = old_signals.get(coin["symbol"], "WAIT")
        if coin["signal"] in ("BUY", "SELL") and coin["signal"] != old:
            tech = coin["technical"] or {}
            alerts.append(
                f"🧠 NIRA {coin['signal']} ALERT\n{coin['symbol']} | Price: {coin['price']:.8g} USDT\n"
                f"Combined score: {coin['combinedScore']}/100\nTechnical: {tech.get('score','N/A')} | "
                f"RSI: {tech.get('rsi','N/A')} | News score: {coin['newsScore']:+}\n"
                f"24h change: {coin['change24h']:+.2f}%\nReason: {coin['reason']}\n"
                "Paper signal only — no real trade placed."
            )
    for message in alerts:
        telegram_send(message)
    save_json(STATE_FILE, {"updatedAt": datetime.now(timezone.utc).isoformat(), "signals": new_signals})
    print(f"Completed: {len(results)} coins; news items={len(news)}; alerts={len(alerts)}; Fear & Greed={fng}")
    for c in results:
        print(c["symbol"], c["signal"], c["combinedScore"], "RSI", (c["technical"] or {}).get("rsi"))

if __name__ == "__main__":
    main()
    
