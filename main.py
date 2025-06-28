import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from utils.cache import load_common_tokens, load_cached_tokens, refresh_and_cache_tokens
from utils.exchange_client import fetch_live_prices, fetch_top_spreads, calculate_top_spreads
from notifier import send_spread_alert
from dotenv import load_dotenv
import asyncio

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

def get_symbols():
    symbols = load_cached_tokens()
    if not symbols:
        symbols = refresh_and_cache_tokens()
    return symbols or []

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "exchanges": list(ENABLED_EXCHANGES.keys()),
        "enabled": ENABLED_EXCHANGES
    })

@app.post("/api/top5")
async def top5_api():
    symbols = get_symbols()
    if not symbols:
        return JSONResponse({"data": [], "error": "No tokens found in cache."}, status_code=200)
    try:
        raw_prices = await fetch_top_spreads(symbols)
        top_tokens = calculate_top_spreads(raw_prices)
        for token_obj in top_tokens:
            if "spread" in token_obj and token_obj["spread"] >= 1.5:
                await send_spread_alert(token_obj)
        return {"data": top_tokens[:5]}
    except Exception as e:
        return JSONResponse({"data": [], "error": str(e)}, status_code=500)

@app.post("/api/allprices")
async def all_prices_api(req: Request):
    body = await req.json()
    enabled_exchanges = [ex for ex, state in body.items() if state]
    tokens = load_common_tokens() or []
    tokens = tokens[:20]
    if not tokens:
        return JSONResponse([], status_code=200)
    try:
        flat_prices = await fetch_live_prices(tokens, enabled_exchanges)
        # Group prices by token
        from collections import defaultdict
        token_map = defaultdict(dict)
        for p in flat_prices:
            token = p.get("token")
            exchange = p.get("exchange")
            if not token or not exchange:
                continue
            token_map[token][exchange] = {"buy": p.get("buy"), "sell": p.get("sell")}
        # Structure for frontend
        table = [
            {
                "token": token,
                "prices": exchanges
            }
            for token, exchanges in token_map.items()
        ]
        return JSONResponse(table)
    except Exception as e:
        return JSONResponse([], status_code=500)

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