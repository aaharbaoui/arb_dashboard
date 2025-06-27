import os
import uvicorn
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from utils.cache import load_common_tokens, load_cached_tokens
from utils.exchange_client import fetch_live_prices, fetch_top_spreads
from notifier import send_spread_alert
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

ENABLED_EXCHANGES = {
    "Binance": True,
    "Bybit": True,
    "OKX": True,
    "MEXC": True,
    "HTX": True,
    "Bitget": True
}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "exchanges": list(ENABLED_EXCHANGES.keys()),
        "enabled": ENABLED_EXCHANGES
    })

@app.post("/api/top5")
async def top5_api():
    symbols = load_cached_tokens()
    raw_spreads = await fetch_top_spreads(symbols)  # ✅ This is now a coroutine
    top_tokens = calculate_top_spreads(raw_spreads)  # ✅ Filters and sorts the top 20

    # ✅ Send alerts only if spread is 1.5% or more
    for token_obj in top_tokens:
        if "spread" in token_obj and token_obj["spread"] >= 1.5:
            await send_spread_alert(token_obj)

    return {"data": top_tokens[:5]}

@app.post("/api/allprices")
async def all_prices_api(req: Request):
    body = await req.json()
    enabled_exchanges = [ex for ex, state in body.items() if state]
    
    tokens = load_common_tokens()[:20]  # ✅ Ensure tokens like "BTC/USDT"
    prices = await fetch_live_prices(tokens, enabled_exchanges)  # ✅ Proper args
    return JSONResponse(prices)

@app.get("/test-alert")
async def test_alert():
    await send_spread_alert({
        "token": "TEST/USDT",
        "spread": 5.23,
        "buy_ex": "Binance",
        "sell_ex": "HTX",
        "buy": 1.005,
        "sell": 1.057,
        "withdrawal": "✅",
        "star": True
    })
    return {"ok": True, "message": "Alert sent."}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)