# 🏠 Avito Apartment Parser Pro

Telegram bot for real-time monitoring of new apartment listings on Avito with enterprise-grade WAF bypass, customizable filters, and instant notifications.

## 📋 Features

- **Enterprise Anti-Bot Bypass** - Uses Playwright in stealth mode to solve JS-challenges and extract clearance cookies (`ft` token).
- **High-Speed Parsing** - Employs `curl_cffi` to spoof Chrome TLS fingerprints for fast, undetected HTTP requests.
- **Advanced Data Extraction** - Parses heavily protected real estate data directly from encrypted `mime/invalid` JSON scripts in the DOM.
- **Data Persistence** - Automatically saves listing history to `avito_data.csv` using `pandas` to survive restarts and prevent duplicate alerts.
- **Real-time monitoring** - Checks Avito every 5 minutes for new 2-bedroom apartments in Kazan (35,000-45,000 ₽/month).
- **Telegram integration** - Instant async notifications with apartment details and direct links.

## 🛠️ Tech Stack

- **Python 3.10+**
- **Libraries:**
  - `playwright` - Headless browser automation for WAF bypass.
  - `curl_cffi` - TLS-impersonated HTTP requests.
  - `pandas` - Fast CSV database management and filtering.
  - `beautifulsoup4` - DOM parsing and script extraction.
  - `python-telegram-bot` - Async Telegram API integration.

## 🚀 Quick Start

1. Clone the repository:
```bash
git clone [https://github.com/Elchin-bit/avito_parser_2_rooms.git](https://github.com/Elchin-bit/avito_parser_2_rooms.git)
cd avito-apartment-parser 
```

2. Install dependencies and the Chromium browser for Playwright:

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Configure your credentials:

Create a config.py file in the root directory.

Add your Telegram credentials (get them from @BotFather and @userinfobot):

```Python 
TELEGRAM_BOT_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"
```

4. Run the parser:

```Python 
python parser.py
```

📊 How It Works
The parser follows a self-healing workflow:

Authenticates: Playwright opens a hidden browser, visits a random listing, and "steals" the ft clearance cookie from Avito's WAF.

Fetches: curl_cffi makes fast requests to the search page using the stolen cookie and Chrome 120 headers.

Extracts: Decodes the hidden script[type="mime/invalid"] JSON state where Avito now hides apartment data.

Filters & Saves: Compares new results against the avito_data.csv history using Pandas.

Notifies: Sends formatted alerts for unique listings to Telegram.

Why Playwright + curl_cffi?
Standard HTML/JSON-LD parsing no longer works due to Avito's strict Web Application Firewall (Qrator/Cloudflare). 
The bot uses a hybrid approach: Playwright behaves like a real human to get the access pass, while curl_cffi does the heavy lifting rapidly without consuming too much RAM.

🔧 Configuration
Edit search parameters directly in parser.py:

```Python 
MIN_PRICE = 35000       # Minimum price (₽/month)
MAX_PRICE = 45000       # Maximum price (₽/month)
CHECK_INTERVAL = 300    # Check frequency (seconds)
CSV_FILENAME = "avito_data.csv"
```

📱 Example Output
🏠 Новая 2-комнатная!

💰 45,000 ₽/мес
📝 2-к. квартира, 55 м², 8/9 эт.

🔗 [suspicious link removed]


⚠️ WAF & Anti-Bot Protection
The parser automatically handles HTTP blocks (301, 302, 403, 429) by flushing cookies and launching Playwright to acquire a fresh token.

Note: Avito tracks IP reputation. If you plan to run this script 24/7 on a cloud server (Data Center IP), it will eventually receive a hard 302 redirect to a Captcha page. 
For autonomous server deployment, routing the requests through rotating mobile SOCKS5 proxies is highly recommended.


👨‍💻 Author
Elchin Aliev Junior IT Specialist | AI Enthusiast

Built with AI assistance. 

📄 License
MIT License - Free to use for personal and educational purposes.

Made for automating apartment hunting in Kazan 🏙️

