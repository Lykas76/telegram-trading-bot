import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler,
    ContextTypes, CallbackQueryHandler
)

# Получаем токен из переменных окружения
TOKEN = os.getenv("TELEGRAM_TOKEN")

# 👋 Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для торговли. Используй /signal чтобы получить сигнал.\n"
        "Напиши /id чтобы узнать свой chat_id."
    )

# 🆔 Команда /id — присылает chat_id
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Ваш chat_id: {chat_id}")

# 🔘 Обработка нажатий на кнопки BUY / SELL
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = "Покупка (BUY)" if query.data == "buy" else "Продажа (SELL)"
    await query.edit_message_text(f"✅ Вы выбрали: {action}")

# 🔁 Команда /signal — отправляет сигнал с кнопками
async def send_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🔔 Сигнал EUR/USD M1\n🟢 BUY (вверх)\n⏳ Время: 1–3 мин"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 BUY", callback_data='buy')],
        [InlineKeyboardButton("🔴 SELL", callback_data='sell')]
    ])
    await update.message.reply_text(text, reply_markup=keyboard)

# 🚀 Основная функция запуска бота
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("id", get_chat_id))
    app.add_handler(CommandHandler("signal", send_signal))

    # Обработка кнопок
    app.add_handler(CallbackQueryHandler(handle_button))

    # Запуск бота
    app.run_polling()

if __name__ == "__main__":
    main()



