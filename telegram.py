
import os, httpx

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

last_alerts = {}

async def send_alert(pair, buy_ex, buy_price, sell_ex, sell_price, spread_pct):
    global last_alerts
    key = f"{pair}_{buy_ex}_{sell_ex}"
    message = f"🔔 *Arbitrage Alert* 🔔\nPair: `{pair}`\nBuy on: *{buy_ex}* @ `{buy_price}`\nSell on: *{sell_ex}* @ `{sell_price}`\nSpread: *{round(spread_pct, 2)}%`"
    if last_alerts.get(key) != message:
        last_alerts[key] = message
        async with httpx.AsyncClient() as client:
            await client.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={
                    "chat_id": CHAT_ID or (await get_chat_id(BOT_TOKEN)),
                    "text": message, "parse_mode": "Markdown"
                })

async def get_chat_id(token):
    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://api.telegram.org/bot{token}/getUpdates")
        data = r.json()
        if data["ok"] and data["result"]:
            return data["result"][-1]["message"]["chat"]["id"]
    return ""
