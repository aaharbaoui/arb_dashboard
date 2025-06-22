import os
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from jinja2 import Environment, FileSystemLoader

load_dotenv()

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

env = Environment(loader=FileSystemLoader("templates"))
template = env.get_template("index.html")

TELEGRAM_ENABLED = os.getenv("TELEGRAM_ENABLED", "false").lower() == "true"
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 0.3))
REFRESH_INTERVAL = float(os.getenv("REFRESH_INTERVAL", 1))

EXCHANGES = ["bitget", "mexc", "htx"]
SYMBOLS = [
    "XRP_USDT", "XLM_USDT", "ATOM_USDT", "EOS_USDT",
    "HIVE_USDT", "STEEM_USDT", "XEM_USDT", "OIST_USDT",
    "A_USDT", "ZIL_USDT", "TRX_USDT", "AR_USDT",
    "STRAX_USDT", "LSK_USDT", "ONG_USDT", "LUNC_USDT",
    "WAVES_USDT", "BTS_USDT", "CVC_USDT"
]

price_cache = {}

async def fetch_price(session, url, exchange, symbol):
    try:
        resp = await session.get(url, timeout=5)
        data = resp.json()
        if exchange == "bitget":
            return float(data["data"]["buyOne"]), float(data["data"]["sellOne"])
        elif exchange == "mexc":
            return float(data["data"]["bid"]), float(data["data"]["ask"])
        elif exchange == "htx":
            return float(data["tick"]["bid"][0]), float(data["tick"]["ask"][0])
    except:
        return None, None

def get_symbol_for_exchange(symbol, exchange):
    token = symbol.replace("_USDT", "")
    if exchange == "bitget":
        return f"{token}USDT"
    if exchange == "mexc":
        return f"{token}_USDT"
    if exchange == "htx":
        return f"{token.lower()}usdt"
    return symbol

async def get_prices():
    global price_cache
    tasks = []
    async with httpx.AsyncClient() as client:
        for symbol in SYMBOLS:
            for exchange in EXCHANGES:
                mapped = get_symbol_for_exchange(symbol, exchange)
                if exchange == "bitget":
                    url = f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={mapped}"
                elif exchange == "mexc":
                    url = f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={mapped}"
                elif exchange == "htx":
                    url = f"https://api.huobi.pro/market/detail/merged?symbol={mapped}"
                tasks.append(fetch_price(client, url, exchange, symbol))
        results = await asyncio.gather(*tasks)

    prices = {}
    i = 0
    for symbol in SYMBOLS:
        prices[symbol] = {}
        for exchange in EXCHANGES:
            buy, sell = results[i]
            prices[symbol][exchange] = {"buy": buy, "sell": sell}
            i += 1
    price_cache = prices

def calculate_spread(prices):
    spread_list = []
    for symbol, ex_data in prices.items():
        buy_prices = [(ex, data["buy"]) for ex, data in ex_data.items() if data["buy"]]
        sell_prices = [(ex, data["sell"]) for ex, data in ex_data.items() if data["sell"]]
        if not buy_prices or not sell_prices:
            continue
        best_buy_ex, best_buy = min(buy_prices, key=lambda x: x[1])
        best_sell_ex, best_sell = max(sell_prices, key=lambda x: x[1])
        spread = ((best_sell - best_buy) / best_buy) * 100 if best_buy > 0 else 0
        spread_list.append({
            "symbol": symbol.replace("_USDT", "/USDT"),
            "spread": round(spread, 3),
            "buy_exchange": best_buy_ex,
            "sell_exchange": best_sell_ex,
            "buy_price": best_buy,
            "sell_price": best_sell,
            "network": "Tag/Memo"
        })
    return sorted(spread_list, key=lambda x: x["spread"], reverse=True)[:19]

async def send_telegram_alert(symbol, spread, buy_ex, sell_ex):
    if not TELEGRAM_ENABLED or not BOT_TOKEN or not CHAT_ID:
        return
    text = f"🔔 Arbitrage Alert\nSymbol: {symbol}\nSpread: {spread:.2f}%\nBuy on: {buy_ex}\nSell on: {sell_ex}"
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text}
    try:
        async with httpx.AsyncClient() as client:
            await client.post(url, data=payload)
    except:
        pass

@app.on_event("startup")
async def start_loop():
    async def loop():
        last_alerts = set()
        while True:
            await get_prices()
            spread_data = calculate_spread(price_cache)
            for arb in spread_data:
                key = f"{arb['symbol']}:{arb['buy_exchange']}:{arb['sell_exchange']}"
                if arb["spread"] >= SPREAD_THRESHOLD and key not in last_alerts:
                    await send_telegram_alert(arb["symbol"], arb["spread"], arb["buy_exchange"], arb["sell_exchange"])
                    last_alerts.add(key)
                elif arb["spread"] < SPREAD_THRESHOLD and key in last_alerts:
                    last_alerts.remove(key)
            await asyncio.sleep(REFRESH_INTERVAL)
    asyncio.create_task(loop())

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    spread_data = calculate_spread(price_cache)
    return template.render(spreads=spread_data, refresh=REFRESH_INTERVAL)

@app.get("/data", response_class=JSONResponse)
async def get_data():
    spread_data = calculate_spread(price_cache)
    return spread_data