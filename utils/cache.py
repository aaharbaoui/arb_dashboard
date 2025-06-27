import os
import json
import time
import httpx

# ✅ Loads common token list from JSON
def load_common_tokens():
    with open("common_tokens.json", "r") as f:
        return json.load(f)

# ✅ Path to the cached token file
CACHE_FILE = "utils/cache.json"
EXCHANGES = ["Binance", "OKX", "Bybit", "HTX"]

# ✅ API endpoints for top tokens on each exchange
ENDPOINTS = {
    "Binance": "https://api.binance.com/api/v3/exchangeInfo",
    "OKX": "https://www.okx.com/api/v5/public/instruments?instType=SPOT",
    "Bybit": "https://api.bybit.com/v5/market/instruments-info?category=spot",
    "HTX": "https://api.huobi.pro/v1/common/symbols"
}

# ✅ Load tokens from cache if not expired (1 day = 86400 seconds)
def load_cached_tokens():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if time.time() - data["timestamp"] < 86400:
                return data["tokens"]
    return None

# ✅ Save tokens to cache with timestamp
def save_tokens_to_cache(tokens):
    with open(CACHE_FILE, "w") as f:
        json.dump({
            "timestamp": time.time(),
            "tokens": tokens
        }, f)

# ✅ Format tokens to a clean /USDT symbol
def format_token(symbol):
    return symbol.upper().replace("_", "").replace("-", "").replace("USDT", "") + "/USDT"

# ✅ Fetch tokens from Binance
def fetch_binance_tokens():
    try:
        r = httpx.get(ENDPOINTS["Binance"], timeout=5)
        symbols = r.json()["symbols"]
        return set(format_token(s["symbol"]) for s in symbols if s["quoteAsset"] == "USDT" and s["status"] == "TRADING")
    except Exception as e:
        print(f"[⚠️ Binance error] {e}")
        return set()

# ✅ Fetch tokens from OKX
def fetch_okx_tokens():
    try:
        r = httpx.get(ENDPOINTS["OKX"], timeout=5)
        instruments = r.json()["data"]
        return set(format_token(s["instId"]) for s in instruments if s["quoteCcy"] == "USDT")
    except Exception as e:
        print(f"[⚠️ OKX error] {e}")
        return set()

# ✅ Fetch tokens from Bybit
def fetch_bybit_tokens():
    try:
        r = httpx.get(ENDPOINTS["Bybit"], timeout=5)
        data = r.json()["result"]["list"]
        return set(format_token(s["symbol"]) for s in data if s["quoteCoin"] == "USDT")
    except Exception as e:
        print(f"[⚠️ Bybit error] {e}")
        return set()

# ✅ Fetch tokens from HTX
def fetch_htx_tokens():
    try:
        r = httpx.get(ENDPOINTS["HTX"], timeout=5)
        data = r.json()["data"]
        return set(format_token(s["symbol"]) for s in data if s["quote-currency"] == "usdt")
    except Exception as e:
        print(f"[⚠️ HTX error] {e}")
        return set()

# ✅ Get intersection of all tokens (only those common across all exchanges)
def get_top_common_tokens(limit=300):
    cached = load_cached_tokens()
    if cached:
        return cached

    print("[🔄 CACHE REFRESH] Fetching top tokens from all exchanges...")

    sets = [
        fetch_binance_tokens(),
        fetch_okx_tokens(),
        fetch_bybit_tokens(),
        fetch_htx_tokens()
    ]

    common = set.intersection(*sets)
    top = sorted(list(common))[:limit]

    save_tokens_to_cache(top)
    print(f"[✅ CACHE READY] {len(top)} common tokens cached.")
    return top