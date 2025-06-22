import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import httpx
from telegram import send_telegram_alert

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 0.3))
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 1))
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"

EXCHANGES = ["bitget", "mexc", "htx"]

TOKENS = [
    {"symbol": "XRP/USDT", "network": "Tag"},
    {"symbol": "XLM/USDT", "network": "Memo"},
    {"symbol": "ATOM/USDT", "network": "Memo"},
    {"symbol": "EOS/USDT", "network": "Memo"},
    {"symbol": "STEEM/USDT", "network": "Memo"},
    {"symbol": "HIVE/USDT", "network": "Memo"},
    {"symbol": "OIST/USDT", "network": "AVAX"},
    {"symbol": "A/USDT", "network": "APTOS"},
]

async def fetch_price(client, exchange, symbol):
    url = f"https://arb-price-api.onrender.com/{exchange}/{symbol}"
    try:
        response = await client.get(url, timeout=5)
        data = response.json()
        return float(data["data"]["buy"]), float(data["data"]["sell"])
    except Exception as e:
        print(f"{exchange.upper()} {symbol} ERROR: {e}")
        return None, None

async def fetch_prices():
    results = []
    async with httpx.AsyncClient() as client:
        for token in TOKENS:
            symbol = token["symbol"].replace("/", "_")
            prices = {}

            for exchange in EXCHANGES:
                buy, sell = await fetch_price(client, exchange, symbol)
                if buy and sell:
                    prices[exchange] = {"buy": buy, "sell": sell}

            if len(prices) < 2:
                continue

            all_buys = [v["buy"] for v in prices.values()]
            all_sells = [v["sell"] for v in prices.values()]
            lowest_buy = min(all_buys)
            highest_sell = max(all_sells)
            spread = (highest_sell - lowest_buy) / lowest_buy * 100

            if spread >= SPREAD_THRESHOLD:
                buy_on = next(ex for ex in prices if prices[ex]["buy"] == lowest_buy)
                sell_on = next(ex for ex in prices if prices[ex]["sell"] == highest_sell)

                results.append({
                    "symbol": token["symbol"],
                    "network": token["network"],
                    "spread": round(spread, 2),
                    "buy_on": buy_on,
                    "sell_on": sell_on,
                    "bitget": prices.get("bitget"),
                    "mexc": prices.get("mexc"),
                    "htx": prices.get("htx"),
                })

                if TELEGRAM_ENABLED:
                    msg = f"🚨 {token['symbol']} Spread: {spread:.2f}%\nBuy on {buy_on} @ {lowest_buy}\nSell on {sell_on} @ {highest_sell}"
                    send_telegram_alert(BOT_TOKEN, CHAT_ID, msg)

    results.sort(key=lambda x: x["spread"], reverse=True)
    return results[:19]

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data")
async def get_data():
    return JSONResponse(content=await fetch_prices())