
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx, os, asyncio
from dotenv import load_dotenv
from telegram import send_alert

load_dotenv()
app = FastAPI()
templates = Jinja2Templates(directory="templates")

REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 5))
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 1.0))
TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"

# Static memo/network mapping
token_info = {
    "XRPUSDT": "Memo", "XLMUSDT": "Memo", "STEEMUSDT": "Memo", "HIVEUSDT": "Memo",
    "EOSUSDT": "Tag", "ATOMUSDT": "Memo", "OISTUSDT": "Memo", "AUSDT": "Memo",
    "BTCUSDT": "Native", "ETHUSDT": "ERC20", "BNBUSDT": "BEP20", "TRXUSDT": "TRC20",
    "AVAXUSDT": "AVAX", "APTUSDT": "APTOS", "DOGEUSDT": "Native", "LTCUSDT": "Native",
    "SOLUSDT": "SOL", "MATICUSDT": "ERC20", "OPUSDT": "ERC20", "ARBUSDT": "ERC20"
}

top_pairs = list(token_info.keys())

def format_symbol(exchange, pair):
    if exchange == "Bybit":
        return pair
    elif exchange == "Bitget":
        return pair.lower() + "_SPBL"
    elif exchange == "MEXC":
        return pair
    elif exchange == "HTX":
        return pair.lower()
    return pair

async def fetch_prices(pair):
    urls = {
        "Bybit": f"https://api.bybit.com/v2/public/tickers?symbol={format_symbol('Bybit', pair)}",
        "Bitget": f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={format_symbol('Bitget', pair)}",
        "MEXC": f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={format_symbol('MEXC', pair)}",
        "HTX": f"https://api.huobi.pro/market/detail/merged?symbol={format_symbol('HTX', pair)}"
    }
    prices = {}
    async with httpx.AsyncClient() as client:
        for name, url in urls.items():
            try:
                r = await client.get(url, timeout=5)
                data = r.json()
                if name == "Bybit":
                    prices[name] = float(data["result"][0]["last_price"])
                elif name == "Bitget":
                    prices[name] = float(data["data"]["close"])
                elif name == "MEXC":
                    prices[name] = float(data["askPrice"])
                elif name == "HTX":
                    prices[name] = float(data["tick"]["close"])
            except Exception as e:
                print(f"Error fetching {pair} from {name}: {e}")
                prices[name] = None
    return prices

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/data")
async def dashboard_data():
    table = []
    for pair in top_pairs:
        prices = await fetch_prices(pair)
        valid = {k: v for k, v in prices.items() if v}
        if valid:
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
    return {"table": table}
