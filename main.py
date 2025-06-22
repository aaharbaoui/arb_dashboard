import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import httpx

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="templates")

EXCHANGES = ["bitget", "mexc", "htx"]
PAIRS = ["HIVE/USDT", "XRP/USDT", "ATOM/USDT", "XLM/USDT", "EOS/USDT",
         "STEEM/USDT", "A/USDT", "OIST/USDT", "XEM/USDT", "TLM/USDT"]

async def fetch_price(exchange, pair):
    base_url = {
        "bitget": f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={pair.replace('/', '')}_SPBL",
        "mexc": f"https://api.mexc.com/api/v3/ticker/price?symbol={pair.replace('/', '')}",
        "htx": f"https://api.huobi.pro/market/detail/merged?symbol={pair.replace('/', '').lower()}"
    }
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(base_url[exchange])
            data = r.json()
            if exchange == "bitget":
                return float(data["data"]["last"])
            elif exchange == "mexc":
                return float(data["price"])
            elif exchange == "htx":
                return float(data["tick"]["close"])
    except:
        return None

async def fetch_all_prices(pair):
    prices = {}
    tasks = [fetch_price(ex, pair) for ex in EXCHANGES]
    results = await asyncio.gather(*tasks)
    for i, ex in enumerate(EXCHANGES):
        prices[ex] = results[i]
    return prices

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data")
async def data():
    table = []
    for pair in PAIRS:
        prices = await fetch_all_prices(pair)
        valid = {k: v for k, v in prices.items() if v}
        if len(valid) < 2:
            continue
        low_ex = min(valid, key=valid.get)
        high_ex = max(valid, key=valid.get)
        spread = round(((valid[high_ex] - valid[low_ex]) / valid[low_ex]) * 100, 2)
        table.append({
            "pair": pair,
            "prices": prices,
            "buy": low_ex,
            "sell": high_ex,
            "spread": spread
        })
    table.sort(key=lambda x: x["spread"], reverse=True)
    return {"table": table[:19]}