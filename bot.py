import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import aiohttp

TOKEN = os.getenv("TELEGRAM_TOKEN")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

bot = Bot(token=TOKEN)

async def start(update, context):
    await update.message.reply_text(
        "Привет! Я бот для торговли. Используй /обновить чтобы получить сигнал."
    )

async def send_signal(context: ContextTypes.DEFAULT_TYPE):
    chat_id = YOUR_TELEGRAM_CHAT_ID  # Вставь сюда свой chat_id
    # Пример сигнала
    text = "🔔 Сигнал EUR/USD M1\n🟢 BUY (вверх)\n⏳ Время: 1–3 мин"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 BUY", callback_data='buy')],
        [InlineKeyboardButton("🔴 SELL", callback_data='sell')]
    ])
    await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)

async def refresh(update, context):
    await send_signal(context)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", refresh))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
