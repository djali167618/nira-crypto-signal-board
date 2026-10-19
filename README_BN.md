# NIRA 24/7 Crypto Signal Board — বাংলা সেটআপ

এই প্রজেক্ট Binance-এর পাবলিক USDT মার্কেট ডেটা, RSI/EMA/MACD/ভলিউম, RSS crypto news এবং Alternative.me Fear & Greed Index ব্যবহার করে পরীক্ষামূলক BUY/SELL/WAIT সিগন্যাল তৈরি করে। এটি **কোনো real trade করে না**।

## কী কী থাকবে
- প্রতি ৫ মিনিটে নির্ধারিত GitHub Actions scan (সময়মতো প্রতিবার চলার নিশ্চয়তা নেই)
- Binance-এর 24h quote volume অনুযায়ী Top 10 USDT pair
- 15m candle technical analysis
- Coin news keyword sentiment এবং overall market sentiment
- Telegram alert (BUY/SELL সিগন্যাল WAIT থেকে বদলালে)
- GitHub Pages dashboard
- সহজ Paper Trade লগ: 1.5% stop-loss ও 3% take-profit (পর্যবেক্ষণ করা দামের snapshot দিয়ে)

## ফোন থেকে সেটআপ

### ১. GitHub repository তৈরি
1. Chrome-এ https://github.com খুলে লগইন/অ্যাকাউন্ট তৈরি করো।
2. `+` → **New repository** চাপো।
3. নাম দাও `nira-crypto-signal-board`।
4. **Public** বেছে নাও (Public repo-তে standard GitHub-hosted Actions usage free থাকে)।
5. **Add a README file** টিক না দিলেও হবে; Create repository চাপো।

### ২. ZIP ফাইল আপলোড
1. এই ZIP ফাইলটি ফোনে Extract করো।
2. Repository-তে **Add file → Upload files** বেছে নাও।
3. ZIP-এর ভেতরের ফাইলগুলো আপলোড করবে, ZIP-ফাইল নিজে নয়। `.github/workflows/scan.yml`-সহ hidden `.github` folder-ও আপলোড হয়েছে কি না যাচাই করো।
4. **Commit changes** চাপো।
5. সহজ উপায়: GitHub-এ ফোল্ডারসহ আপলোড কঠিন হলে প্রতিটি ফাইল GitHub-এর **Add file → Create new file** দিয়ে তৈরি করো এবং ZIP-এর ফাইল থেকে কোড কপি করো। Workflow path ঠিক ` .github/workflows/scan.yml` হতে হবে (শুরুর/শেষের space নয়)।

### ৩. Telegram bot তৈরি
1. Telegram-এ `@BotFather` খুঁজে `/newbot` পাঠাও।
2. নির্দেশনা অনুসারে বটের নাম ও username দাও।
3. BotFather যে **token** দেবে, সেটা গোপন রাখবে। কোডে বা পাবলিক ফাইলে লিখবে না।
4. তোমার নতুন বটের chat খুলে **Start** চাপো।
5. Chat ID পাওয়ার সহজ পদ্ধতি: ব্রাউজারে `https://api.telegram.org/botYOUR_TOKEN/getUpdates` খোলো (YOUR_TOKEN-এর জায়গায় নিজের token বসাও)। JSON-এ `"chat":{"id":123456789...}` অংশের সংখ্যা হলো chat ID। কাজ শেষ হলে এই URL অন্য কাউকে পাঠাবে না। `getUpdates` ফাঁকা হলে বটকে আবার `/start` পাঠিয়ে URL রিফ্রেশ করো।

### ৪. GitHub Secrets যোগ
Repository → **Settings → Secrets and variables → Actions → New repository secret**।
দুটি secret বানাও:
- `TELEGRAM_BOT_TOKEN` = BotFather token
- `TELEGRAM_CHAT_ID` = নিজের chat ID

**Token কখনো কোডে commit কোরো না।**

### ৫. GitHub Actions চালু
1. Repository → **Actions**।
2. “NIRA 24-7 Crypto Scanner” workflow-তে ক্লিক করো।
3. প্রথমবার প্রয়োজন হলে **I understand my workflows, go ahead and enable them** চাপো।
4. **Run workflow** → Run workflow চাপো।
5. রান সবুজ হলে `docs/index.html`, `docs/data.json`, `state.json` ও `paper_trades.json` তৈরি/আপডেট হবে।
6. কোনো error হলে Actions → সর্বশেষ run → লাল step খুলে error দেখো।

### ৬. Dashboard প্রকাশ
Repository → **Settings → Pages**:
- Source: **Deploy from a branch**
- Branch: `main`
- Folder: `/docs`
- Save

GitHub Pages URL সাধারণত `https://YOUR-USERNAME.github.io/nira-crypto-signal-board/` হবে। প্রকাশ হতে কয়েক মিনিট লাগতে পারে। Pages-এ দেখানো প্রকৃত URL-টাই ব্যবহার করবে।

## গুরুত্বপূর্ণ বাস্তব সীমাবদ্ধতা
- GitHub Actions cron প্রতি ৫ মিনিটে নির্ধারণ করা যায়, কিন্তু execution দেরি হতে পারে বা সাময়িকভাবে skip হতে পারে। এটিকে নিশ্চিত ২৪/৭ SLA ভাববে না।
- Public repository-তে কোড সবাই দেখতে পারে; তাই Telegram token শুধু GitHub Secrets-এ রাখবে।
- নিউজের sentiment এখন keyword-based; এটি পূর্ণাঙ্গ AI বা নির্ভরযোগ্য সত্যতা যাচাই নয়। প্রতিটি খবরের মূল লিংক দেখে সিদ্ধান্ত নেবে।
- News RSS/Exchange API সাময়িকভাবে ব্যর্থ হতে পারে। কোনো কয়েনের candle ডেটা না এলে সেই কয়েন WAIT দেখাবে।
- “Top 10” মানে Binance-এ quote volume অনুযায়ী নির্বাচিত USDT pair; এটি সব এক্সচেঞ্জের global top 10 নয়।
- Paper trade snapshot-ভিত্তিক। ৫ মিনিটের ব্যবধানে price SL/TP ছুঁয়ে ফিরে এলে তা ধরা নাও পড়তে পারে।
- সিগন্যাল লাভের নিশ্চয়তা দেয় না। প্রথমে কয়েক সপ্তাহ paper trade ফলাফল দেখো। এই সংস্করণে কোনো live order placement নেই।
- Alternative.me Fear & Greed ডেটা প্রদর্শনের সময় উৎসের attribution রাখা হয়েছে।
