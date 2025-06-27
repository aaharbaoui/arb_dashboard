import httpx
import os

headers_okx = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

async def fetch_okx(symbol):
    try:
        symbol_formatted = symbol.replace("/", "-").upper()
        url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers_okx)
        if resp.status_code != 200:
            return {"exchange": "OKX", "symbol": symbol, "error": f"Status code {resp.status_code}"}
        data = resp.json().get("data", [{}])[0]
        return {
            "exchange": "OKX",
            "symbol": symbol,
            "buy": float(data.get("bidPx", 0)),
            "sell": float(data.get("askPx", 0)),
        }
    except Exception as e:
        return {"exchange": "OKX", "symbol": symbol, "error": str(e)}

async def fetch_bitget(symbol):
    try:
        symbol_formatted = symbol.replace("/", "").upper()
        url = f"https://api.bitget.com/api/v2/spot/market/ticker?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        data = resp.json().get("data", {})
        return {
            "exchange": "Bitget",
            "symbol": symbol,
            "buy": float(data.get("buyOne", 0)),
            "sell": float(data.get("sellOne", 0)),
        }
    except Exception as e:
        return {"exchange": "Bitget", "symbol": symbol, "error": str(e)}

async def fetch_bybit(symbol):
    try:
        symbol_formatted = symbol.replace("/", "").upper()
        url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        result = resp.json().get("result", {}).get("list", [{}])[0]
        return {
            "exchange": "Bybit",
            "symbol": symbol,
            "buy": float(result.get("bid1Price", 0)),
            "sell": float(result.get("ask1Price", 0)),
        }
    except Exception as e:
        return {"exchange": "Bybit", "symbol": symbol, "error": str(e)}

async def fetch_mexc(symbol):
    try:
        symbol_formatted = symbol.replace("/", "_").upper()
        url = f"https://api.mexc.com/api/v3/ticker/bookTicker?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        data = resp.json()
        return {
            "exchange": "MEXC",
            "symbol": symbol,
            "buy": float(data.get("bidPrice", 0)),
            "sell": float(data.get("askPrice", 0)),
        }
    except Exception as e:
        return {"exchange": "MEXC", "symbol": symbol, "error": str(e)}

async def fetch_htx(symbol):
    try:
        symbol_formatted = symbol.replace("/", "").lower()
        url = f"https://api.huobi.pro/market/detail/merged?symbol={symbol_formatted}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url)
        tick = resp.json().get("tick", {})
        return {
            "exchange": "HTX",
            "symbol": symbol,
            "buy": float(tick.get("bid", [0])[0]),
            "sell": float(tick.get("ask", [0])[0]),
        }
    except Exception as e:
        return {"exchange": "HTX", "symbol": symbol, "error": str(e)}