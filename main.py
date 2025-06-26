from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from utils.exchange_client import fetch_from, ENABLED, API_INFO, get_binance_asset_status
from utils.cache import TimedCache
import asyncio
import httpx
from notifier import send_spread_alert

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

EXCHANGES = list(ENABLED.keys())
token_cache = TimedCache(ttl_seconds=600)  # Cache token list for 10 minutes

# 🔁 Background task: runs every 60 seconds
async def run_top5_alerts_background():
    while True:
        try:
            enabled = [ex for ex, on in ENABLED.items() if on]
            result = await compute_spreads(enabled)
            top5 = result[:5]
            for token in top5:
                send_spread_alert(token)
        except Exception as e:
            print(f"[❌ Alert Loop Error] {e}")
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    await get_binance_asset_status()  # Fetch once at startup
    asyncio.create_task(run_top5_alerts_background())  # Start background alerts

# Get token list from all active exchanges
async def fetch_token_list_from_exchange(exchange: str):
    if not ENABLED.get(exchange):
        return []

    info = API_INFO[exchange]
    url = info["url"]

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url)
            res.raise_for_status()
            data = res.json()

            items = data
            if "result_key" in info:
                a, b = info["result_key"]
                items = data.get(a, {}).get(b, [])
            elif "data" in data:
                items = data["data"]

            if isinstance(items, dict):
                items = [items]

            tokens = set()
            for item in items:
                symbol = item.get(info.get("inst_key", "symbol"))
                if symbol:
                    symbol = symbol.replace("-", "/").replace("_", "/").upper()
                    if "/" in symbol and symbol.endswith("USDT"):
                        tokens.add(symbol)

            return list(tokens)

    except Exception as e:
        print(f"[❌ {exchange} token list error] {e}")
        return []

async def get_all_tokens():
    cached = token_cache.get("tokens")
    if cached:
        return cached

    tasks = [fetch_token_list_from_exchange(ex) for ex in EXCHANGES if ENABLED[ex]]
    results = await asyncio.gather(*tasks)
    token_set = set()
    for tokens in results:
        token_set.update(tokens)

    sorted_tokens = sorted(token_set)
    token_cache.set("tokens", sorted_tokens)
    return sorted_tokens

# Compute spread per token from enabled exchanges
async def compute_spreads(enabled_exchanges):
    all_tokens = await get_all_tokens()
    out = []

    for token in all_tokens:
        print(f"🔍 Checking token: {token}")
        data = await asyncio.gather(*[fetch_from(ex, token) for ex in enabled_exchanges])
        valid = [d for d in data if d]

        print(f"✅ Valid results for {token}: {valid}")

        if len(valid) >= 2:
            buy = min(valid, key=lambda x: x["buy"])
            sell = max(valid, key=lambda x: x["sell"])
            spread = round((sell["sell"] - buy["buy"]) / buy["buy"] * 100, 2)
            star = buy.get("star", False) or sell.get("star", False)

            access = "✅"
            if buy["access"] == "❌" or sell["access"] == "❌":
                access = "❌"

            out.append({
                "token": token,
                "spread": spread,
                "buy_ex": buy["exchange"],
                "sell_ex": sell["exchange"],
                "buy": buy["buy"],
                "sell": sell["sell"],
                "network": buy.get("network", "Auto"),
                "withdrawal": access,
                "fees": "0.1%",
                "star": star
            })

    return sorted(out, key=lambda x: (-x["star"], -x["spread"]))

# Routes
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    tokens = await get_all_tokens()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "exchanges": EXCHANGES,
        "enabled": ENABLED,
        "tokens": tokens
    })

@app.post("/api/top5", response_class=JSONResponse)
async def top5(request: Request):
    enabled = [ex for ex, on in ENABLED.items() if on]
    result = await compute_spreads(enabled)
    top5 = result[:5]
    for token in top5:
        send_spread_alert(token)
    return top5

@app.post("/api/allprices", response_class=JSONResponse)
async def all_prices(request: Request):
    body = await request.json()
    enabled = [ex for ex, on in body.items() if on]
    return await compute_spreads(enabled)
