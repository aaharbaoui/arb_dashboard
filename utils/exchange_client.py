import os
import httpx
from dotenv import load_dotenv

load_dotenv()

EXCHANGES = ["Binance", "MEXC", "Bybit", "Bitget", "HTX", "OKX"]

ENABLED = {
    ex: os.getenv(f"{ex.upper()}_ENABLED", "False").strip().lower() == "true"
    for ex in EXCHANGES
}

API_INFO = {
    "Binance": {
        "url": "https://api.binance.com/api/v3/ticker/bookTicker",
        "hdr": "X-MBX-APIKEY",
        "ask": "askPrice",
        "bid": "bidPrice"
    },
    "MEXC": {
        "url": "https://api.mexc.com/api/v3/ticker/bookTicker",
        "hdr": "X-MEXC-APIKEY",
        "ask": "askPrice",
        "bid": "bidPrice"
    },
    "Bybit": {
        "url": "https://api.bybit.com/v5/market/tickers?category=spot",
        "hdr": "X-BYBIT-API-KEY",
        "ask": "askPrice",
        "bid": "bidPrice",
        "result_key": ("result", "list")
    },
    "Bitget": {
        "url": "https://api.bitget.com/api/spot/v1/market/tickers",
        "hdr": "ACCESS-KEY",
        "ask": "askPr",
        "bid": "bidPr"
    },
    "HTX": {
        "url": "https://api.huobi.pro/market/tickers",
        "hdr": "AccessKeyId",
        "ask": "ask",
        "bid": "bid"
    },
    "OKX": {
        "url": "https://www.okx.com/api/v5/market/tickers?instType=SPOT",
        "hdr": "OK-ACCESS-KEY",
        "ask": "askPx",
        "bid": "bidPx",
        "inst_key": "instId"
    },
}

BINANCE_ASSET_STATUS = {}

async def get_binance_asset_status():
    global BINANCE_ASSET_STATUS
    url = "https://api.binance.com/sapi/v1/capital/config/getall"
    headers = {"X-MBX-APIKEY": os.getenv("BINANCE_API_KEY")}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.get(url, headers=headers)
            res.raise_for_status()
            data = res.json()
            for item in data:
                asset = item.get("coin")
                BINANCE_ASSET_STATUS[asset] = {
                    "deposit": item.get("depositAllEnable", True),
                    "withdraw": item.get("withdrawAllEnable", True)
                }
    except Exception as e:
        print(f"[❌ BINANCE ASSET STATUS ERROR] {e}")

def is_star_token(token_info):
    liquidity_ok = token_info.get("volume", 0) > 1_000_000
    withdrawal_ok = token_info.get("withdrawal_enabled", True)
    deposit_ok = token_info.get("deposit_enabled", True)
    low_fee = token_info.get("withdrawal_fee", 0) < 1
    good_network = token_info.get("network", "").upper() in ["TRC20", "XRP", "XLM", "BEP20", "MATIC"]
    return liquidity_ok and withdrawal_ok and deposit_ok and low_fee and good_network

async def fetch_from(exchange: str, pair: str):
    if not ENABLED.get(exchange, False):
        print(f"[⚠️ {exchange}] Skipped - Disabled in .env")
        return None

    info = API_INFO.get(exchange)
    headers = {info["hdr"]: os.getenv(f"{exchange.upper()}_API_KEY")}
    sym = pair.replace("/", "") if exchange != "OKX" else pair.replace("/", "-")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(info["url"], headers=headers)
            res.raise_for_status()
            d = res.json()

            items = d
            if "result_key" in info:
                a, b = info["result_key"]
                items = d.get(a, {}).get(b, [])
            elif "data" in d:
                items = d["data"]

            if isinstance(items, dict):
                items = [items]

            for it in items:
                key = it.get(info.get("inst_key", "symbol"))
                if not key:
                    continue
                if key.replace("-", "").lower() == sym.lower():
                    ask = it.get(info["ask"])
                    bid = it.get(info["bid"])
                    if ask is not None and bid is not None:
                        asset = pair.split("/")[0].upper()
                        token_info = {
                            "volume": float(it.get("quoteVolume") or it.get("vol") or 0),
                            "withdrawal_enabled": True,
                            "deposit_enabled": True,
                            "withdrawal_fee": float(it.get("withdrawFee") or 0),
                            "network": it.get("network", "")
                        }

                        if exchange == "Binance" and BINANCE_ASSET_STATUS.get(asset):
                            token_info["withdrawal_enabled"] = BINANCE_ASSET_STATUS[asset]["withdraw"]
                            token_info["deposit_enabled"] = BINANCE_ASSET_STATUS[asset]["deposit"]

                        result = {
                            "exchange": exchange,
                            "buy": float(ask),
                            "sell": float(bid),
                            "star": is_star_token(token_info),
                            "access": "✅" if token_info["deposit_enabled"] and token_info["withdrawal_enabled"] else "❌"
                        }
                        if os.getenv("DEBUG", "false").lower() == "true":
                            print(f"[✅ {exchange}] {pair}: {result}")
                        return result

        print(f"[❌ {exchange}] {pair}: Not found or missing ask/bid")
        return None

    except Exception as e:
        print(f"[❌ {exchange}] {pair}: {e}")
        return None
