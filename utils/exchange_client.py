import httpx
import asyncio

EXCHANGES = ["Binance", "Bybit", "MEXC", "HTX", "OKX", "Bitget"]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

# --- Exchange price functions ---

async def get_binance(symbol):
    try:
        s = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={s}"
        async with httpx.AsyncClient(verify=False, headers=HEADERS, timeout=5) as client:
            r = await client.get(url)
        r.raise_for_status()
        return float(r.json()["price"])
    except Exception as e:
        print(f"[⚠️ Binance error] {symbol}: {e}")
        return None

async def get_bybit(symbol):
    try:
        s = symbol.replace("/", "")
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={s}"
        async with httpx.AsyncClient(verify=False, headers=HEADERS, timeout=5) as client:
            r = await client.get(url)
        data = r.json().get("result", {}).get("list")
        if not data or not isinstance(data, list):
            raise ValueError("Missing or invalid 'list'")
        return float(data[0]["lastPrice"])
    except Exception as e:
        print(f"[⚠️ Bybit error] {symbol}: {e}")
        return None

async def get_mexc(symbol):
    try:
        s = symbol.lower().replace("/", "_")
        url = f"https://api.mexc.com/api/v3/ticker/price?symbol={s}"
        async with httpx.AsyncClient(verify=False, headers=HEADERS, timeout=5) as client:
            r = await client.get(url)
        data = r.json()
        if "price" not in data:
            raise ValueError("Missing 'price'")
        return float(data["price"])
    except Exception as e:
        print(f"[⚠️ MEXC error] {symbol}: {e}")
        return None

async def get_htx(symbol):
    try:
        s = symbol.lower().replace("/", "")
        url = f"https://api.huobi.pro/market/detail/merged?symbol={s}"
        async with httpx.AsyncClient(verify=False, headers=HEADERS, timeout=5) as client:
            r = await client.get(url)
        tick = r.json().get("tick")
        if not tick or "close" not in tick:
            raise ValueError("Missing 'tick.close'")
        return float(tick["close"])
    except Exception as e:
        print(f"[⚠️ HTX error] {symbol}: {e}")
        return None

async def get_okx(symbol):
    try:
        s = symbol.replace("/", "-")
        url = f"https://www.okx.com/api/v5/market/ticker?instId={s}"
        okx_headers = {
            **HEADERS,
            "Referer": "https://www.okx.com/",
        }
        async with httpx.AsyncClient(verify=False, headers=okx_headers, timeout=5) as client:
            r = await client.get(url)
        data = r.json().get("data")
        if not data or not isinstance(data, list) or "last" not in data[0]:
            raise ValueError("Missing 'data[0].last'")
        return float(data[0]["last"])
    except Exception as e:
        print(f"[⚠️ OKX error] {symbol}: {e}")
        return None

async def get_bitget(symbol):
    try:
        s = symbol.lower().replace("/", "")
        url = f"https://api.bitget.com/api/spot/v1/market/ticker?symbol={s}"
        async with httpx.AsyncClient(verify=False, headers=HEADERS, timeout=5) as client:
            r = await client.get(url)
        data = r.json().get("data")
        if not data or "close" not in data:
            raise ValueError("Missing 'data.close'")
        return float(data["close"])
    except Exception as e:
        print(f"[⚠️ Bitget error] {symbol}: {e}")
        return None

# --- Main fetch function ---

EXCHANGE_FUNCS = {
    "Binance": get_binance,
    "Bybit": get_bybit,
    "MEXC": get_mexc,
    "HTX": get_htx,
    "OKX": get_okx,
    "Bitget": get_bitget,
}

async def fetch_live_prices(tokens):
    results = {}
    for token in tokens:
        results[token] = {}
        for ex in EXCHANGES:
            func = EXCHANGE_FUNCS[ex]
            price = await func(token)
            if price:
                results[token][ex] = price
    return results

def fetch_top_spreads(prices):
    top = []
    for token, data in prices.items():
        if len(data) < 2:
            continue
        min_ex = min(data, key=data.get)
        max_ex = max(data, key=data.get)
        buy = data[min_ex]
        sell = data[max_ex]
        spread = ((sell - buy) / buy) * 100
        if spread > 0:
            top.append({
                "token": token,
                "buy_on": min_ex,
                "sell_on": max_ex,
                "buy_price": round(buy, 4),
                "sell_price": round(sell, 4),
                "spread": round(spread, 2)
            })
    return sorted(top, key=lambda x: x["spread"], reverse=True)