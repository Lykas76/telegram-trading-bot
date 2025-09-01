import os
import requests
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 🔑 Токены
TOKEN = os.getenv("TOKEN")  # Твой Telegram Bot API
ALPHA_TOKEN = os.getenv("ALPHA_TOKEN")  # API Alpha Vantage

# 📊 Валютные пары и таймфреймы
PAIRS = {
    "EUR/USD": ("EUR", "USD"),
    "GBP/USD": ("GBP", "USD"),
    "AUD/JPY": ("AUD", "JPY"),
    "EUR/CAD": ("EUR", "CAD"),
}
TIMEFRAMES = {"M1": "1min", "M5": "5min", "M15": "15min"}


# 📡 Получение сигнала с Alpha Vantage
def get_signal(pair: str, tf: str):
    base, quote = PAIRS[pair]
    interval = TIMEFRAMES[tf]

    url = (
        f"https://www.alphavantage.co/query?"
        f"function=FX_INTRADAY&from_symbol={base}&to_symbol={quote}"
        f"&interval={interval}&apikey={ALPHA_TOKEN}&outputsize=compact"
    )

    try:
        r = requests.get(url)
        data = r.json()

        key = f"Time Series FX ({interval})"
        if key not in data:
            return "❌ Ошибка: нет данных", "NONE", 2, 0

        candles = list(data[key].items())
        if len(candles) < 2:
            return "❌ Недостаточно данных", "NONE", 2, 0

        # последние две свечи
        last_time, last_candle = candles[0]
        prev_time, prev_candle = candles[1]

        last_close = float(last_candle["4. close"])
        prev_close = float(prev_candle["4. close"])

        diff = abs(last_close - prev_close)  # сила сигнала
        pct_strength = min(100, round((diff / prev_close) * 100000))  # % силы (0–100)

        # направление
        if last_close > prev_close:
            signal = "🟢 BUY (вверх)"
            direction = "BUY"
        elif last_close < prev_close:
            signal = "🔴 SELL (вниз)"
            direction = "SELL"
        else:
            signal = "⚪ НЕТ СИГНАЛА"
            direction = "FLAT"

        # время сделки по силе движения
        if diff < 0.0005:
            duration = 1
        elif diff < 0.0010:
            duration = 2
        elif diff < 0.0015:
            duration = 3
        elif diff < 0.0020:
            duration = 4
        else:
            duration = 5

        return signal, direction, duration, pct_strength

    except Exception as e:
        return f"❌ Ошибка: {e}", "NONE", 2, 0


# ▶️ Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text(
        "Выбери валютную пару:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )


# 💬 Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # выбор валютной пары
    if text in PAIRS:
        context.user_data["pair"] = text
        keyboard = [[tf for tf in TIMEFRAMES]]
        await update.message.reply_text(
            "Выбери таймфрейм:",
            reply_markup=ReplyKeyboardMarkup(keyboard + [["🔄 Валюта"]], resize_keyboard=True),
        )

    # выбор таймфрейма
    elif text in TIMEFRAMES:
        context.user_data["tf"] = text
        await update.message.reply_text(
            "Нажми 📡 Сигнал",
            reply_markup=ReplyKeyboardMarkup([["📡 Сигнал", "🔄 Валюта"]], resize_keyboard=True),
        )

    # генерация сигнала
    elif text == "📡 Сигнал":
        pair = context.user_data.get("pair", "EUR/USD")
        tf = context.user_data.get("tf", "M5")

        signal_text, direction, duration, strength = get_signal(pair, tf)

        now = datetime.now()
        now_str = now.strftime("%H:%M:%S")
        end_time = (now + timedelta(minutes=duration)).strftime("%H:%M:%S")

        await update.message.reply_text(
            f"🔔 Сигнал {pair} {tf}\n"
            f"{signal_text}\n"
            f"⏳ Зайти на: {duration} мин\n"
            f"📊 Сила сигнала: {strength}%\n"
            f"🕒 Время сигнала: {now_str}\n"
            f"⏹ Закрыть сделку до: {end_time}"
        )

        await update.message.reply_text(
            "Готов к новому сигналу:",
            reply_markup=ReplyKeyboardMarkup([["📡 Сигнал", "🔄 Валюта"]], resize_keyboard=True),
        )

    # смена валюты
    elif text == "🔄 Валюта":
        keyboard = [[pair] for pair in PAIRS]
        await update.message.reply_text(
            "Выбери валютную пару:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )

    else:
        await update.message.reply_text("Пожалуйста, выбери валютную пару или таймфрейм.")


# ▶️ Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()
