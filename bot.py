import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

TOKEN = os.getenv("TOKEN")
print(f"TOKEN: {repr(TOKEN)}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["M1", "M5", "M15"]]
    await update.message.reply_text("Выбери таймфрейм:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in ["M1", "M5", "M15"]:
        context.user_data["tf"] = text
        await update.message.reply_text("Нажми 📡 Сигнал", reply_markup=ReplyKeyboardMarkup([["📡 Сигнал"]], resize_keyboard=True))
    elif text == "📡 Сигнал":
        tf = context.user_data.get("tf", "M5")
        await update.message.reply_text(f"🔔 Сигнал EUR/USD {tf}\n🟢 BUY (вверх)\n⏳ Время: 1–3 мин")
    else:
        await update.message.reply_text("Пожалуйста, выбери таймфрейм.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
