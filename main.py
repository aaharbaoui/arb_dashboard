# main.py
import os, asyncio, httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()
templates = Jinja2Templates(directory="templates")

EXCHANGES = ["bitget", "mexc", "htx"]
PAIRS = ["HIVE/USDT", "STEEM/USDT", "A/USDT", "EOS/USDT", "XEM/USDT", "XLM/USDT", "XRP/USDT", "ATOM/USDT", "OIST/USDT"]
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 0.3))
CHAT_ID = os.getenv("CHAT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

token_info = {
    "HIVE/USDT": "Memo",
    "STEEM/USDT": "Memo",
    "A/USDT": "Tag",
    "EOS/USDT": "Memo",
    "XEM/USDT": "Tag",
    "XLM/USDT": "Memo",
    "XRP/USDT": "Tag",
    "ATOM/USDT": "Memo",
    "OIST/USDT": "Memo"
}

async def fetch_prices(pair):
    base, quote = pair.split("/")
    async with httpx.AsyncClient(timeout=3) as client:
        tasks = []
        urls = {
            "bitget": f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={base.lower()}{quote.lower()}",
            "mexc": f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={base}{quote}",
            "htx": f"https://api.huobi.pro/market/detail/merged?symbol={base.lower()}{quote.lower()}"
        }
        for ex in EXCHANGES:
            tasks.append(client.get(urls[ex]))
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        result = {}
        for idx, ex in enumerate(EXCHANGES):
            try:
                r = responses[idx]
                if isinstance(r, Exception): continue
                data = r.json()
                if ex == "bitget":
                    d = data.get("data", {})
                    result[ex] = {"buy": float(d.get("buyOne", 0)), "sell": float(d.get("sellOne", 0))}
                elif ex == "mexc":
                    result[ex] = {"buy": float(data["bidPrice"]), "sell": float(data["askPrice"])}
                elif ex == "htx":
                    tick = data.get("tick", {})
                    result[ex] = {"buy": float(tick.get("bid", [0])[0]), "sell": float(tick.get("ask", [0])[0])}
            except:
                continue
        return result

async def send_alert(pair, buy_ex, buy_price, sell_ex, sell_price, spread):
    if not TELEGRAM_ENABLED: return
    text = f"📈 *Arbitrage Opportunity!*\n\n*{pair}*\nBuy on *{buy_ex.upper()}* at `{buy_price}`\nSell on *{sell_ex.upper()}* at `{sell_price}`\nSpread: *{round(spread,2)}%*"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, data=payload)
    except:
        pass

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data")
async def dashboard_data():
    table = []
    for pair in PAIRS:
        prices = await fetch_prices(pair)
        valid = [(ex, p["buy"], p["sell"]) for ex, p in prices.items() if p["buy"] > 0 and p["sell"] > 0]
        if len(valid) < 2: continue
        low = min(valid, key=lambda x: x[1])
        high = max(valid, key=lambda x: x[2])
        spread = ((high[2] - low[1]) / low[1]) * 100 if low[1] else 0
        if spread >= SPREAD_THRESHOLD:
            await send_alert(pair, low[0], low[1], high[0], high[2], spread)
        table.append({
            "pair": pair,
            "network": token_info.get(pair, "-"),
            "prices": prices,
            "buy": low[0],
            "sell": high[0],
            "spread": round(spread, 2)
        })
    table.sort(key=lambda x: x["spread"], reverse=True)
    return {"table": table[:19]}