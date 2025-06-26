import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

def slab_style(spread):
    if spread >= 7.5:
        return "💣🚀💥", "*BOOM! Jackpot Incoming!*"
    elif spread >= 5:
        return "🔥🤑", "*🔥 Hot Arbitrage Opportunity!*"
    elif spread >= 3:
        return "⚡️🤩", "*Nice Spread – Let’s Go!*"
    elif spread >= 1.5:
        return "🟢🔍", "*Tiny Crack in the Wall!*"
    else:
        return "🧊", "*Barely worth your coffee ☕️*"

async def send_spread_alert(token_obj):
    token = token_obj["token"]
    spread = token_obj["spread"]
    buy_ex = token_obj["buy_ex"]
    sell_ex = token_obj["sell_ex"]
    buy_price = token_obj["buy"]
    sell_price = token_obj["sell"]
    access = token_obj["withdrawal"]
    star = token_obj["star"]

    emoji, title = slab_style(spread)
    star_icon = "⭐️" if star else ""
    access_note = "✅ All Clear" if access == "✅" else "⚠️ Check deposit/withdrawal status!"

    msg = (
        f"{emoji} {title}\n\n"
        f"Token: *{token}* {star_icon}\n"
        f"Buy from: *{buy_ex}* at *${buy_price:.6f}*\n"
        f"Sell to: *{sell_ex}* at *${sell_price:.6f}*\n"
        f"Spread: *{spread:.2f}%*\n"
        f"Access: {access}\n"
        f"{access_note}\n"
    )

    try:
        async with httpx.AsyncClient() as client:
            await client.post(SEND_URL, json={
                "chat_id": CHAT_ID,
                "text": msg,
                "parse_mode": "Markdown"
            })
    except Exception as e:
        print(f"[❌ TELEGRAM ERROR] {e}")
