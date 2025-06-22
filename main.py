import os
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from dotenv import load_dotenv
from typing import List, Dict

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

EXCHANGES = ["bitget", "mexc", "htx"]
TOKENS = ["XRP", "HIVE", "STEEM", "XLM", "EOS", "ATOM", "XEM", "A", "OIST", "TON"]
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", "0.3"))
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "1"))

# Memo/tag requirements
NETWORK_TAGS = {
    "XRP": "MEMO",
    "XLM": "MEMO",
    "ATOM": "MEMO",
    "EOS": "MEMO",
    "STEEM": "MEMO",
    "XEM": "MESSAGE",
    "A": "APTOS",
    "OIST": "AVAX",
}

# Telegram settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# In-memory to avoid repeat alerts
last_alerts = {}

async def fetch_price(session, url, exchange, token):
    try:
        r = await session.get(url, timeout=5)
        data = r.json()
        if exchange == "bitget":
            return {
                "buy": float(data["data"]["buyOne"]),
                "sell": float(data["data"]["sellOne"])
            }
        elif exchange == "mexc":
            return {
                "buy": float(data["data"]["bid"]),
                "sell": float(data["data"]["ask"])
            }
        elif exchange == "htx":
            return {
                "buy": float(data["tick"]["bid"][0]),
                "sell": float(data["tick"]["ask"][0])
            }
    except Exception as e:
        return {"buy": None, "sell": None}

async def get_all_prices():
    urls = []
    for token in TOKENS:
        for exchange in EXCHANGES:
            if exchange == "bitget":
                urls.append((f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={token}USDT", exchange, token))
            elif exchange == "mexc":
                urls.append((f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={token}USDT", exchange, token))
            elif exchange == "htx":
                urls.append((f"https://api.huobi.pro/market/depth?symbol={token.lower()}usdt&type=step0", exchange, token))

    results = {token: {} for token in TOKENS}
    async with httpx.AsyncClient() as session:
        tasks = [fetch_price(session, url, exchange, token) for url, exchange, token in urls]
        price_data = await asyncio.gather(*tasks)

    for i, (url, exchange, token) in enumerate(urls):
        results[token][exchange] = price_data[i]
    return results

def calculate_spread(prices):
    opportunities = []
    for token, ex_data in prices.items():
        valid_prices = [(ex, p["buy"], p["sell"]) for ex, p in ex_data.items() if p["buy"] and p["sell"]]
        if len(valid_prices) < 2:
            continue
        lowest = min(valid_prices, key=lambda x: x[1])
        highest = max(valid_prices, key=lambda x: x[2])
        spread = ((highest[2] - lowest[1]) / lowest[1]) * 100
        if spread > 0:
            opportunities.append({
                "token": token,
                "prices": ex_data,
                "spread": round(spread, 2),
                "buy_on": lowest[0],
                "sell_on": highest[0],
                "network": NETWORK_TAGS.get(token, "")
            })
    return sorted(opportunities, key=lambda x: x["spread"], reverse=True)[:19]

async def send_telegram(msg):
    if not TELEGRAM_ENABLED or not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, data=payload)
    except:
        pass

async def monitor_and_alert():
    while True:
        prices = await get_all_prices()
        opportunities = calculate_spread(prices)
        for opp in opportunities:
            key = opp["token"]
            if opp["spread"] >= SPREAD_THRESHOLD:
                if key not in last_alerts or abs(opp["spread"] - last_alerts[key]) >= 0.1:
                    message = (
                        f"🚨 Arbitrage Alert ({opp['spread']}%)\n"
                        f"{opp['token']} | Buy on {opp['buy_on']} | Sell on {opp['sell_on']}\n"
                        f"Network: {opp['network']}"
                    )
                    await send_telegram(message)
                    last_alerts[key] = opp["spread"]
        await asyncio.sleep(REFRESH_INTERVAL)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data")
async def get_data():
    prices = await get_all_prices()
    opportunities = calculate_spread(prices)
    return JSONResponse(opportunities)

@app.on_event("startup")
async def start_monitor():
    asyncio.create_task(monitor_and_alert())