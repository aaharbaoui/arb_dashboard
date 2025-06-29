import httpx
import asyncio

async def fetch_binance(symbol):
    try:
        symbol_formatted = symbol.replace("/", "")
        url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        print(f"[DEBUG][Binance] {url} => {resp.status_code} {resp.text[:120]}")
        data = resp.json()
        return {
            "exchange": "Binance",
            "token": symbol,
            "buy": float(data.get("bidPrice", 0)),
            "sell": float(data.get("askPrice", 0)),
        }
    except Exception as e:
        print(f"[ERROR][Binance] {symbol} {e}")
        return {"exchange": "Binance", "token": symbol, "error": str(e)}

async def fetch_okx(symbol):
    try:
        symbol_formatted = symbol.replace("/", "-").upper()
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        print(f"[DEBUG][OKX] {url} => {resp.status_code} {resp.text[:120]}")
        data_list = resp.json().get("data", [])
        if not data_list or not isinstance(data_list, list):
            raise ValueError("No data returned from OKX")
        data = data_list[0]
        return {
            "exchange": "OKX",
            "token": symbol,
            "buy": float(data.get("bidPx", 0)),
            "sell": float(data.get("askPx", 0)),
        }
    except Exception as e:
        print(f"[ERROR][OKX] {symbol} {e}")
        return {"exchange": "OKX", "token": symbol, "error": str(e)}

async def fetch_bybit(symbol):
    try:
        symbol_formatted = symbol.replace("/", "").upper()
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        print(f"[DEBUG][Bybit] {url} => {resp.status_code} {resp.text[:120]}")
        result_list = resp.json().get("result", {}).get("list", [])
        result = result_list[0] if result_list else {}
        return {
            "exchange": "Bybit",
            "token": symbol,
            "buy": float(result.get("bid1Price", 0)),
            "sell": float(result.get("ask1Price", 0)),
        }
    except Exception as e:
        print(f"[ERROR][Bybit] {symbol} {e}")
        return {"exchange": "Bybit", "token": symbol, "error": str(e)}

async def fetch_mexc(symbol):
    try:
        symbol_formatted = symbol.replace("/", "_").upper()
        url = f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        print(f"[DEBUG][MEXC] {url} => {resp.status_code} {resp.text[:120]}")
        data = resp.json()
        return {
            "exchange": "MEXC",
            "token": symbol,
            "buy": float(data.get("bidPrice", 0)),
            "sell": float(data.get("askPrice", 0)),
        }
    except Exception as e:
        print(f"[ERROR][MEXC] {symbol} {e}")
        return {"exchange": "MEXC", "token": symbol, "error": str(e)}

async def fetch_htx(symbol):
    try:
        symbol_formatted = symbol.replace("/", "").lower()
        url = f"https://api.huobi.pro/market/detail/merged?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        print(f"[DEBUG][HTX] {url} => {resp.status_code} {resp.text[:120]}")
        tick = resp.json().get("tick", {})
        return {
            "exchange": "HTX",
            "token": symbol,
            "buy": float(tick.get("bid", [0])[0] if "bid" in tick else 0),
            "sell": float(tick.get("ask", [0])[0] if "ask" in tick else 0),
        }
    except Exception as e:
        print(f"[ERROR][HTX] {symbol} {e}")
        return {"exchange": "HTX", "token": symbol, "error": str(e)}

async def fetch_bitget(symbol):
    try:
        symbol_formatted = symbol.replace("/", "").upper()
        url = f"https://api.bitget.com/api/v2/spot/market/ticker?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        print(f"[DEBUG][Bitget] {url} => {resp.status_code} {resp.text[:120]}")
        data = resp.json().get("data", None)
        if not data or not isinstance(data, dict):
            raise ValueError("No data returned from Bitget")
        return {
            "exchange": "Bitget",
            "token": symbol,
            "buy": float(data.get("buyOne", 0)),
            "sell": float(data.get("sellOne", 0)),
        }
    except Exception as e:
        print(f"[ERROR][Bitget] {symbol} {e}")
        return {"exchange": "Bitget", "token": symbol, "error": str(e)}

# List of exchange fetchers
EXCHANGE_FUNCTIONS = [
    fetch_binance,
    fetch_okx,
    fetch_bybit,
    fetch_mexc,
    fetch_htx,
    fetch_bitget
]

async def fetch_live_prices(symbols, enabled_exchanges=None):
    results = []
    for symbol in symbols:
        tasks = []
        for func in EXCHANGE_FUNCTIONS:
            ex_name = func.__name__.replace("fetch_", "").capitalize()
            if enabled_exchanges is None or ex_name in enabled_exchanges:
                tasks.append(func(symbol))
        responses = await asyncio.gather(*tasks)
        for r in responses:
            results.append(r)
    return results

async def fetch_top_spreads(symbols):
    # For each token, get all exchange prices (buy/sell)
    all_prices = await fetch_live_prices(symbols)
    return all_prices

def calculate_top_spreads(all_prices):
    """
    all_prices: list of {exchange, token, buy, sell}
    Returns: list of top spread opportunities, sorted by spread descending
    """
    from collections import defaultdict
    token_prices = defaultdict(list)
    for p in all_prices:
        if "token" not in p or "buy" not in p or "sell" not in p:
            continue
        token = p["token"]
        token_prices[token].append(p)
    results = []
    for token, prices in token_prices.items():
        max_sell = max((p for p in prices if p.get("sell", 0)), key=lambda x: x.get("sell", 0), default=None)
        min_buy = min((p for p in prices if p.get("buy", 0)), key=lambda x: x.get("buy", 0), default=None)
        if not max_sell or not min_buy:
            continue
        if max_sell["exchange"] == min_buy["exchange"]:
            continue
        spread = ((max_sell["sell"] - min_buy["buy"]) / min_buy["buy"]) * 100 if min_buy["buy"] else 0
        if spread > 0:
            results.append({
                "token": token,
                "spread": round(spread, 2),
                "buy_ex": min_buy["exchange"],
                "sell_ex": max_sell["exchange"],
                "buy": min_buy["buy"],
                "sell": max_sell["sell"],
                "star": spread >= 1.5,
                "withdrawal": None    # <-- Add this line
            })
    results.sort(key=lambda x: x["spread"], reverse=True)
    return results