import os
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Временно вставляем токен напрямую
TOKEN = "8163815904:AAES02wCoEM6334FpPxuKbiuWsy7-ii9a-E"
bot = Bot(token=TOKEN)

# Команда /start
async def start(update, context):
    await update.message.reply_text("Привет! Я бот для торговли. Используй /signal или /id.")

# Команда /id — присылает твой chat_id
async def get_chat_id(update, context):
    chat_id = update.effective_chat.id
    await update.message.reply_text(f"Ваш chat_id: `{chat_id}`", parse_mode='Markdown')

# Команда /signal — отправка сигнала с кнопками
async def refresh(update, context):
    text = "🔔 Сигнал EUR/USD M1\n🟢 BUY (вверх)\n⏳ Время: 1–3 мин"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 BUY", callback_data='buy')],
        [InlineKeyboardButton("🔴 SELL", callback_data='sell')]
    ])
    await update.message.reply_text(text=text, reply_markup=keyboard)

# Обработка кнопок BUY / SELL
async def handle_button(update, context):
    query = update.callback_query
    await query.answer()
    action = query.data
    if action == "buy":
        await query.edit_message_text("✅ Сделка BUY зафиксирована!")
    elif action == "sell":
        await query.edit_message_text("✅ Сделка SELL зафиксирована!")

# 🚀 Запуск бота
def main():
    print("✅ Бот запускается...")
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("signal", refresh))
    app.add_handler(CommandHandler("id", get_chat_id))          # 👈 важно
    app.add_handler(CallbackQueryHandler(handle_button))
    app.run_polling()

if __name__ == "__main__":
    main()


