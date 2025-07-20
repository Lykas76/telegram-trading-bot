import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    CallbackQueryHandler, ContextTypes
)

# Получаем токен из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN") or "8163815904:AAES02wCoEM6334FpPxuKbiuWsy7-ii9a-E"

# 👋 Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для торговли. Используй /signal чтобы получить сигнал.\n"
        "Напиши /id чтобы узнать свой chat_id."
    )

# 🆔 Команда /id
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Ваш chat_id: `{chat_id}`", parse_mode='MarkdownV2')

# 📡 Команда /signal — отправка сигнала с кнопками BUY/SELL
async def send_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔔 Сигнал EUR/USD M1\n🟢 BUY (вверх)\n⏳ Время: 1–3 мин"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 BUY", callback_data='buy')],
        [InlineKeyboardButton("🔴 SELL", callback_data='sell')]
    ])
    await update.message.reply_text(text=text, reply_markup=keyboard)

# 🟢🔴 Обработка нажатий кнопок
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "buy":
        await query.edit_message_text("✅ Сделка BUY зафиксирована!")
    elif query.data == "sell":
        await query.edit_message_text("✅ Сделка SELL зафиксирована!")

# 🚀 Запуск бота
def main():
    print("✅ Бот запускается...")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_chat_id))
    app.add_handler(CommandHandler("signal", send_signal))
    app.add_handler(CallbackQueryHandler(handle_button))

    app.run_polling()

if __name__ == "__main__":
    main()



