# Real-Time Crypto Arbitrage Dashboard

A FastAPI-powered dashboard for tracking real-time cryptocurrency arbitrage opportunities across multiple exchanges.

## 🚀 Features

- Live price table for popular tokens across major exchanges
- Top 5 tokens with the highest arbitrage spread
- Exchange toggles and filters
- Profit simulation calculator
- Telegram alert integration for high-spread opportunities

## 🏗️ Project Structure

```
.
├── main.py                # FastAPI entrypoint
├── requirements.txt       # Python dependencies
├── static/                # Static files (CSS, JS, images)
├── templates/             # Jinja2 HTML templates
├── utils/
│   ├── cache.py
│   ├── exchange_client.py
│   └── __init__.py
├── notifier.py            # Telegram alert logic
├── common_tokens.json     # Cached token list
└── ...
```


## 👨‍💻 Developed by Amine
aaharbaoui@gmail.com
---

