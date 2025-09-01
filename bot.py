import os
import random
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🔑 Токен из переменной окружения (или можно сразу прописать строкой)
TOKEN = os.getenv("TOKEN")

# Доступные валютные пары и таймфреймы
PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]


# 📌 Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text(
        "Выбери валютную пару:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )


# 📌 Основная обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # ✅ Выбор валютной пары
    if text in PAIRS:
        context.user_data["pair"] = text
        keyboard = [[tf for tf in TIMEFRAMES]]
        await update.message.reply_text(
            "Выбери таймфрейм:",
            reply_markup=ReplyKeyboardMarkup(keyboard + [["🔄 Валюта"]], resize_keyboard=True)
        )

    # ✅ Выбор таймфрейма
    elif text in TIMEFRAMES:
        context.user_data["tf"] = text
        await update.message.reply_text(
            "Нажми 📡 Сигнал",
            reply_markup=ReplyKeyboardMarkup([["📡 Сигнал", "🔄 Валюта"]], resize_keyboard=True)
        )

    # ✅ Генерация сигнала
    elif text == "📡 Сигнал":
        pair = context.user_data.get("pair", "EUR/USD")
        tf = context.user_data.get("tf", "M5")
        direction = random.choice(["BUY", "SELL"])
        emoji = "🟢" if direction == "BUY" else "🔴"
        arrow = "вверх" if direction == "BUY" else "вниз"

        # Время сделки
        duration = random.randint(1, 5)  # 1–5 минут
        now = datetime.now()
        now_str = now.strftime("%H:%M:%S")
        end_time = (now + timedelta(minutes=duration)).strftime("%H:%M:%S")

        # Сообщение сигнала
        await update.message.reply_text(
            f"🔔 Сигнал {pair} {tf}\n"
            f"{emoji} {direction} ({arrow})\n"
            f"⏳ Зайти на: {duration} мин\n"
            f"🕒 Время сигнала: {now_str}\n"
            f"⏹ Закрыть сделку до: {end_time}"
        )

        # Кнопки после сигнала
        await update.message.reply_text(
            "Готов к новому сигналу:",
            reply_markup=ReplyKeyboardMarkup([["📡 Сигнал", "🔄 Валюта"]], resize_keyboard=True)
        )

    # ✅ Смена валютной пары
    elif text == "🔄 Валюта":
        keyboard = [[pair] for pair in PAIRS]
        await update.message.reply_text(
            "Выбери валютную пару:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )

    # ✅ Защита от лишних сообщений
    else:
        await update.message.reply_text("Пожалуйста, выбери валютную пару или таймфрейм.")


# 📌 Точка входа
if __name__ == "__main__":
    if not TOKEN:
        print("❌ Ошибка: токен не найден! Установи переменную окружения TOKEN.")
        exit(1)

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Бот запущен...")
    app.run_polling()
