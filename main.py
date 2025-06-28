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
from collections import defaultdict

# Utility: Group prices per token and per exchange, filling missing with None
def group_prices_by_token(flat_prices, exchanges):
    token_map = defaultdict(dict)
    for p in flat_prices:
        token = p.get("token")
        exchange = p.get("exchange")
        if not token or not exchange:
            continue
        token_map[token][exchange] = {"buy": p.get("buy"), "sell": p.get("sell")}
    table = []
    for token, ex_prices in token_map.items():
        row = {"token": token, "prices": {}}
        for ex in exchanges:
            row["prices"][ex] = ex_prices.get(ex, {"buy": None, "sell": None})
        table.append(row)
    return table

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Default exchanges (can be toggled in UI)
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
                try:
                    await send_spread_alert(token_obj)
                except Exception as alert_err:
                    print(f"[ERROR][Alert] Failed to send: {alert_err}")
        return {"data": top_tokens[:5]}
    except Exception as e:
        print(f"[ERROR][/api/top5] {e}")
        return JSONResponse({"data": [], "error": str(e)}, status_code=500)

@app.post("/api/allprices")
async def all_prices_api(req: Request):
    try:
        body = await req.json()
        enabled_exchanges = [ex for ex, state in body.items() if state]
        tokens = load_common_tokens() or []
        tokens = tokens[:20]  # limit for speed
        if not tokens:
            return JSONResponse([], status_code=200)
        flat_prices = await fetch_live_prices(tokens, enabled_exchanges)
        table = group_prices_by_token(flat_prices, enabled_exchanges)
        return JSONResponse(table)
    except Exception as e:
        print(f"[ERROR][/api/allprices] {e}")
        return JSONResponse([], status_code=500)

@app.get("/test-alert")
async def test_alert():
    try:
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
    except Exception as e:
        print(f"[ERROR][test-alert] {e}")
        return {"ok": False, "message": "Failed to send alert."}

@app.get("/admin/refresh-cache")
async def admin_refresh_cache():
    try:
        tokens = refresh_and_cache_tokens()
        print(f"[ADMIN] Refreshed token cache: {len(tokens)} tokens. Sample: {tokens[:5]}")
        return {"count": len(tokens), "tokens": tokens[:5]}
    except Exception as e:
        print(f"[ERROR][refresh-cache] {e}")
        return {"count": 0, "tokens": [], "error": str(e)}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)