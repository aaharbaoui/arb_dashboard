import os
import json
import time
import httpx

CACHE_FILE = os.path.join(os.path.dirname(__file__), "cache.json")
EXCHANGES = ["Binance", "Bybit", "HTX"]

ENDPOINTS = {
    "Binance": "https://api.binance.com/api/v3/exchangeInfo",
    "Bybit": "https://api.bybit.com/v5/market/instruments-info?category=spot",
    "HTX": "https://api.huobi.pro/v1/common/symbols"
}

def load_common_tokens():
    try:
        with open("common_tokens.json", "r") as f:
            return json.load(f)
    except Exception:
        return []

def load_cached_tokens():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            data = json.load(f)
            if time.time() - data.get("timestamp", 0) < 86400:
                return data.get("tokens", []) or []
    return []

def save_tokens_to_cache(tokens):
    with open(CACHE_FILE, "w") as f:
        json.dump({
            "timestamp": time.time(),
            "tokens": tokens
        }, f)

def format_token(symbol):
    # Ensure format is ALWAYS XXX/USDT
    s = symbol.upper().replace("_", "").replace("-", "")
    if not s.endswith("USDT"):
        return None
    return s.replace("USDT", "") + "/USDT"

def fetch_binance_tokens():
    try:
        r = httpx.get(ENDPOINTS["Binance"], timeout=5)
        symbols = r.json()["symbols"]
        return set(filter(None, (format_token(s["symbol"]) for s in symbols if s["quoteAsset"] == "USDT" and s["status"] == "TRADING")))
    except Exception as e:
        print(f"[⚠️ Binance error] {e}")
        return set()

def fetch_bybit_tokens():
    try:
        r = httpx.get(ENDPOINTS["Bybit"], timeout=5)
        data = r.json().get("result", {}).get("list", [])
        return set(filter(None, (format_token(s["symbol"]) for s in data if s.get("quoteCoin") == "USDT")))
    except Exception as e:
        print(f"[⚠️ Bybit error] {e}")
        return set()

def fetch_htx_tokens():
    try:
        r = httpx.get(ENDPOINTS["HTX"], timeout=5)
        data = r.json().get("data", [])
        return set(filter(None, (format_token(s["symbol"]) for s in data if s.get("quote-currency") == "usdt")))
    except Exception as e:
        print(f"[⚠️ HTX error] {e}")
        return set()

def refresh_and_cache_tokens():
    token_sets = [
        fetch_binance_tokens(),
        fetch_bybit_tokens(),
        fetch_htx_tokens()
    ]
    for name, s in zip(EXCHANGES, token_sets):
        print(f"[DEBUG] {name} tokens: {len(s)}")
    token_sets = [s for s in token_sets if s]
    if not token_sets:
        print("[DEBUG] No token sets available for intersection.")
        return []
    # Try union instead of intersection if intersection is empty
    tokens = list(set.intersection(*token_sets))
    if len(tokens) == 0:
        tokens = list(set.union(*token_sets))
        print("[DEBUG] Intersection empty, using union instead.")
    print(f"[DEBUG] Final tokens: {len(tokens)}")
    save_tokens_to_cache(tokens)
    return tokens