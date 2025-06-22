from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx, os, asyncio
from dotenv import load_dotenv
from typing import Dict

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

EXCHANGES = ["bybit", "bitget", "mexc", "htx"]
token_info = {
    "HIVE/USDT": "Hive Network",
    "XLM/USDT": "Stellar Network",
    "XRP/USDT": "Ripple",
    "EOS/USDT": "EOS",
    "ATOM/USDT": "Cosmos",
    "STEEM/USDT": "Steem",
    "XEM/USDT": "NEM",
    "A/USDT": "Aptos",
    "OIST/USDT": "Optimism"
}
top_pairs = list(token_info.keys())

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
REFRESH_INTERVAL = float(os.getenv("REFRESH_INTERVAL", 5))
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 1.0))
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"

headers = {"Accept": "application/json"}

async def fetch_price_from(exchange: str, pair: str):
    try:
        base, quote = pair.split('/')
        if exchange == "bybit":
            url = f"https://api.bybit.com/v5/market/tickers?category=spot"
            async with httpx.AsyncClient() as client:
                r = await client.get(url)
                for item in r.json()["result"]["list"]:
                    if item["symbol"] == base + quote:
                        return float(item["askPrice"])
        elif exchange == "bitget":
            url = f"https://api.bitget.com/api/spot/v1/market/tickers"
            async with httpx.AsyncClient() as client:
                r = await client.get(url)
                for item in r.json()["data"]:
                    if item["symbol"] == base + quote:
                        return float(item["askPr"])
        elif exchange == "mexc":
            url = f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={base}{quote}"
            async with httpx.AsyncClient() as client:
                r = await client.get(url)
                return float(r.json().get("askPrice"))
        elif exchange == "htx":
            url = f"https://api.htx.com/market/detail/merged?symbol={base.lower()}{quote.lower()}"
            async with httpx.AsyncClient() as client:
                r = await client.get(url)
                return float(r.json()["tick"]["ask"][0])
    except Exception as e:
        return None

async def fetch_prices(pair: str) -> Dict[str, float]:
    tasks = [fetch_price_from(ex, pair) for ex in EXCHANGES]
    prices = await asyncio.gather(*tasks)
    return dict(zip(EXCHANGES, prices))

async def send_alert(pair, low_ex, low_price, high_ex, high_price, spread):
    try:
        message = f"📊 *Arbitrage Opportunity!*\n\n🔁 {pair}\n\nBuy on *{low_ex.upper()}* at *{low_price}*\nSell on *{high_ex.upper()}* at *{high_price}*\n\n💰 *Spread:* {spread:.2f}%"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        await httpx.AsyncClient().post(url, data=payload)
    except Exception as e:
        pass

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data")
async def dashboard_data():
    table = []
    for pair in top_pairs:
        prices = await fetch_prices(pair)
        valid = {k: v for k, v in prices.items() if v}
        if valid and len(valid) >= 2:
            low_ex = min(valid, key=valid.get)
            high_ex = max(valid, key=valid.get)
            spread_pct = ((valid[high_ex] - valid[low_ex]) / valid[low_ex]) * 100 if valid[low_ex] > 0 else 0
            if TELEGRAM_ENABLED and spread_pct >= SPREAD_THRESHOLD:
                await send_alert(pair, low_ex, valid[low_ex], high_ex, valid[high_ex], spread_pct)
            table.append({
                "pair": pair,
                "network": token_info.get(pair, "-"),
                "prices": prices,
                "buy": low_ex,
                "sell": high_ex,
                "spread": round(spread_pct, 2)
            })
    table.sort(key=lambda x: x["spread"], reverse=True)
    return {"table": table[:10]}  # Only show top 10