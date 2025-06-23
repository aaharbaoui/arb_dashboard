import os
import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv
import httpx
from contextlib import asynccontextmanager
from telegram import send_telegram_alert

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# Load .env if available
load_dotenv()

# Set your BOT and CHAT ID here
TOKEN = os.getenv("BOT_TOKEN", "8109808707:AAFE7IDqTgotM5QM4UNeGgGR-BJ6ATWLfMU")
CHAT_ID = os.getenv("CHAT_ID", "6422403122")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 3))
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 0.01))

# Templates and tokens setup
templates = Jinja2Templates(directory="templates")

EXCHANGES = {
    "bitget": "https://api.bitget.com/api/spot/v1/market/tickers",
    "mexc": "https://api.mexc.com/api/v3/ticker/bookTicker",
    "htx": "https://api.huobi.pro/market/tickers"
}

TOKENS = [
    "XRP/USDT", "XLM/USDT", "HIVE/USDT", "OIST/USDT", "A/USDT",
    "EOS/USDT", "STEEM/USDT", "ATOM/USDT", "XEM/USDT", "AID/USDT"
]

NETWORK_INFO = {
    "XRP/USDT": "XRP (Tag)", "XLM/USDT": "XLM (Memo)", "HIVE/USDT": "HIVE (Memo)",
    "OIST/USDT": "Aptos", "A/USDT": "Aptos", "EOS/USDT": "EOS (Memo)",
    "STEEM/USDT": "STEEM (Memo)", "ATOM/USDT": "Cosmos", "XEM/USDT": "XEM",
    "AID/USDT": "Aptos"
}

latest_data = []

app = FastAPI()


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/data")
async def get_data():
    return JSONResponse(latest_data)


async def fetch_prices():
    global latest_data
    logger.info("Started fetch_prices() loop")
    while True:
        results = {ex: {} for ex in EXCHANGES}
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                responses = await asyncio.gather(
                    *[client.get(url) for url in EXCHANGES.values()],
                    return_exceptions=True
                )

                for (name, _), resp in zip(EXCHANGES.items(), responses):
                    if isinstance(resp, Exception):
                        logger.error(f"{name} fetch failed: {resp}")
                        continue
                    try:
                        data = resp.json()
                        if name == "bitget":
                            for item in data.get("data", []):
                                s = item.get("symbol", "").upper()
                                if s.endswith("USDT"):
                                    results[name][s] = {
                                        "buy": float(item["buyOne"]),
                                        "sell": float(item["sellOne"])
                                    }
                        elif name == "mexc":
                            for item in data:
                                s = item.get("symbol", "").upper()
                                if s.endswith("USDT"):
                                    results[name][s] = {
                                        "buy": float(item["bidPrice"]),
                                        "sell": float(item["askPrice"])
                                    }
                        elif name == "htx":
                            for item in data.get("data", []):
                                s = item.get("symbol", "").upper().replace("USDT", "/USDT")
                                results[name][s] = {
                                    "buy": float(item["bid"]),
                                    "sell": float(item["ask"])
                                }
                    except Exception as e:
                        logger.error(f"Error parsing {name} response: {e}")

            rows = []
            for token in TOKENS:
                pair = token.replace("/", "")
                prices = {
                    ex: results[ex].get(pair if ex != "htx" else token, {})
                    for ex in EXCHANGES
                }

                if not all("buy" in p and "sell" in p for p in prices.values()):
                    continue

                buys = [(ex, p["buy"]) for ex, p in prices.items()]
                sells = [(ex, p["sell"]) for ex, p in prices.items()]
                best_buy = min(buys, key=lambda x: x[1])
                best_sell = max(sells, key=lambda x: x[1])
                spread = (best_sell[1] - best_buy[1]) / best_buy[1] * 100

                row = {
                    "token": token,
                    "spread": round(spread, 2),
                    "buy_on": best_buy[0],
                    "sell_on": best_sell[0],
                    "network": NETWORK_INFO.get(token, "-"),
                    "bitget": prices["bitget"],
                    "mexc": prices["mexc"],
                    "htx": prices["htx"]
                }

                rows.append(row)

                if spread >= SPREAD_THRESHOLD:
                    msg = (
                        f"📊 {token} Spread: {round(spread, 2)}%\n"
                        f"Buy on {best_buy[0]} @ {best_buy[1]}\n"
                        f"Sell on {best_sell[0]} @ {best_sell[1]}"
                    )
                    logger.info(f"Alert: {msg}")
                    send_telegram_alert(TOKEN, CHAT_ID, msg)

            latest_data = sorted(rows, key=lambda x: x["spread"], reverse=True)[:19]
            logger.info(f"Updated arbitrage list with {len(latest_data)} entries")
        except Exception as e:
            logger.exception(f"Main fetch loop error: {e}")
        await asyncio.sleep(REFRESH_INTERVAL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App lifespan starting")
    task = asyncio.create_task(fetch_prices())
    yield
    task.cancel()
    logger.info("App lifespan ended")


app = FastAPI(lifespan=lifespan)
