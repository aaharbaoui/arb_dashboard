from telegram import Update
from telegram.ext import ApplicationBuilder, ChatMemberHandler, ContextTypes

BOT_TOKEN = "8109808707:AAFE7IDqTgotM5QM4UNeGgGR-BJ6ATWLfMU"
WELCOME_MESSAGE = """
🎸🎤 *WELCOME TO THE ARBITRAGE PIT, LEGEND!* 🎤🎸

You're now part of the *elite crypto radar crew* 🚨💸
Tracking real-time arbitrage across Binance, OKX, Bybit, HTX, MEXC, Bitget.

✨ Live spreads  
🚫 Deposit/Withdraw flags  
⭐ Star tokens  
📬 Instant alerts when money's on the table

👉 Dashboard: [Insert link here]
🤝 Reach out to [@Ameen_DxB](https://t.me/Ameen_DxB)

*Let’s ride the spreads like thunder ⚡️🚀*
"""

async def welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.chat_member.new_chat_members:
        await context.bot.send_message(
            chat_id=update.chat_member.chat.id,
            text=WELCOME_MESSAGE,
            parse_mode="Markdown"
        )

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(ChatMemberHandler(welcome, ChatMemberHandler.CHAT_MEMBER))
    app.run_polling()
