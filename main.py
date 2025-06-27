from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from utils.exchange_client import fetch_from, ENABLED, API_INFO
from utils.cache import TimedCache
from notifier import send_spread_alert
import asyncio, httpx, os, hmac, hashlib, base64, time

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

EXCHANGES = list(ENABLED.keys())
token_cache = TimedCache(ttl_seconds=600)

# 🛠 BINANCE asset status using API key
async def get_binance_asset_status():
    api_key = os.getenv("BINANCE_API_KEY")
    api_secret = os.getenv("BINANCE_API_SECRET")
    if not api_key or not api_secret:
        print("[⚠️ BINANCE KEYS MISSING]")
        return

    try:
        timestamp = int(time.time() * 1000)
        query = f'timestamp={timestamp}'
        signature = hmac.new(api_secret.encode(), query.encode(), hashlib.sha256).hexdigest()

        headers = {"X-MBX-APIKEY": api_key}
        url = f'https://api.binance.com/sapi/v1/capital/config/getall?{query}&signature={signature}'

        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            return r.json()
    except Exception as e:
        print(f"[❌ BINANCE ASSET STATUS ERROR] {e}")

# 🚨 Telegram test alert route
@app.get("/test-alert")
async def test_alert():
    send_spread_alert({"token": "TEST", "spread": 1.23, "buy_ex": "MEXC", "sell_ex": "HTX", "buy": 0.95, "sell": 1.07})
    return {"status": "✅ Test alert sent"}

# Background spread check every 60s
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
    await get_binance_asset_status()
    asyncio.create_task(run_top5_alerts_background())

# Token list with OKX fix
async def fetch_token_list_from_exchange(exchange: str):
    if not ENABLED.get(exchange): return []

    info = API_INFO[exchange]
    url = info["url"]

    try:
        headers = {}
        if exchange == "okx":
            headers["User-Agent"] = "Mozilla/5.0"

        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(url, headers=headers)
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
        print(f"[❌ {exchange.upper()} token list error] {e}")
        return []

# Token cache
async def get_all_tokens():
    cached = token_cache.get("tokens")
    if cached: return cached

    tasks = [fetch_token_list_from_exchange(ex) for ex in EXCHANGES if ENABLED[ex]]
    results = await asyncio.gather(*tasks)
    token_set = set()
    for tokens in results:
        token_set.update(tokens)

    sorted_tokens = sorted(token_set)
    token_cache.set("tokens", sorted_tokens)
    return sorted_tokens

# Spread calculation
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
            access = "✅" if buy["access"] != "❌" and sell["access"] != "❌" else "❌"

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
