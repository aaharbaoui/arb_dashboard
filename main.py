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

# Load environment variables
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN must be set in the environment")
CHAT_ID = os.getenv("CHAT_ID", "6422403122")
REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", 3))
SPREAD_THRESHOLD = float(os.getenv("SPREAD_THRESHOLD", 0.01))

templates = Jinja2Templates(directory="templates")

EXCHANGES = {
    "bitget": "https://api.bitget.com/api/spot/v1/market/tickers",
    "mexc": "https://api.mexc.com/api/v3/ticker/bookTicker",
    "htx": "https://api.huobi.pro/market/tickers"
}

TOKENS = [
   "XRP/USDT", "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "DOGE/USDT", "ADA/USDT", "AVAX/USDT", "TRX/USDT", "LINK/USDT",
    "MATIC/USDT", "LTC/USDT", "DOT/USDT", "SHIB/USDT", "XLM/USDT", "BCH/USDT", "ATOM/USDT", "XMR/USDT", "APT/USDT", "LDO/USDT",
    "ARB/USDT", "OP/USDT", "NEAR/USDT", "TON/USDT", "ICP/USDT", "SAND/USDT", "AAVE/USDT", "GRT/USDT", "RUNE/USDT", "FTM/USDT",
    "EOS/USDT", "MKR/USDT", "SNX/USDT", "INJ/USDT", "CRV/USDT", "COMP/USDT", "GMT/USDT", "ENJ/USDT", "STORJ/USDT", "HBAR/USDT",
    "DYDX/USDT", "HIVE/USDT", "STEEM/USDT", "KAVA/USDT", "COTI/USDT", "XEM/USDT", "ZEC/USDT", "NEO/USDT", "ZIL/USDT", "FLOW/USDT",
    "UMA/USDT", "IOTA/USDT", "1INCH/USDT", "BAT/USDT", "QNT/USDT", "WOO/USDT", "GALA/USDT", "CHZ/USDT", "DODO/USDT", "AKRO/USDT",
    "VET/USDT", "FLUX/USDT", "CELO/USDT", "LRC/USDT", "OCEAN/USDT", "API3/USDT", "BAND/USDT", "CTXC/USDT", "DUSK/USDT", "ARPA/USDT",
    "BEL/USDT", "SKL/USDT", "YFI/USDT", "ALPHA/USDT", "TLM/USDT", "VRA/USDT", "BICO/USDT", "JASMY/USDT", "NKN/USDT", "RSR/USDT",
    "STMX/USDT", "XVS/USDT", "REN/USDT", "KSM/USDT", "BAL/USDT", "BLZ/USDT", "PERP/USDT", "C98/USDT", "LINA/USDT", "ORN/USDT",
    "DENT/USDT", "MBL/USDT", "REEF/USDT", "SLP/USDT", "WIN/USDT", "POLYX/USDT", "ID/USDT", "MULTI/USDT", "AID/USDT", "A/USDT"
]

NETWORK_INFO = {
    "XRP/USDT": "XRP (Tag)", "XLM/USDT": "XLM (Memo)", "HIVE/USDT": "HIVE (Memo)",
    "OIST/USDT": "Aptos", "A/USDT": "Aptos", "EOS/USDT": "EOS (Memo)",
    "STEEM/USDT": "STEEM (Memo)", "ATOM/USDT": "Cosmos", "XEM/USDT": "XEM",
    "AID/USDT": "Aptos",
    "BTC/USDT": "BTC",
    "ETH/USDT": "Ethereum",
    "BNB/USDT": "BSC",
    "SOL/USDT": "Solana",
    "DOGE/USDT": "DOGE",
    "ADA/USDT": "Cardano",
    "AVAX/USDT": "Avalanche",
    "TRX/USDT": "TRON (Tag)",
    "MATIC/USDT": "Polygon",
    "NEO/USDT": "NEO",
}

latest_data = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("App lifespan starting")
    task = asyncio.create_task(fetch_prices())
    yield
    task.cancel()
    logger.info("App lifespan ended")

app = FastAPI(lifespan=lifespan)

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
                                bid = item.get("bidPrice")
                                ask = item.get("askPrice")
                                if s.endswith("USDT") and bid is not None and ask is not None:
                                    results[name][s] = {
                                        "buy": float(bid),
                                        "sell": float(ask)
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
                    logger.debug(f"Missing price data for: {token} -> {prices}")
                    continue

                buys = [(ex, p["buy"]) for ex, p in prices.items()]
                sells = [(ex, p["sell"]) for ex, p in prices.items()]
                best_buy = min(buys, key=lambda x: x[1])
                best_sell = max(sells, key=lambda x: x[1])
                if best_buy[0] == best_sell[0]:
                    continue
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

            latest_data = sorted(rows, key=lambda x: x["spread"], reverse=True)[:10]
            logger.info(f"Updated arbitrage list with {len(latest_data)} entries")
        except Exception as e:
            logger.exception(f"Main fetch loop error: {e}")
        await asyncio.sleep(REFRESH_INTERVAL)
