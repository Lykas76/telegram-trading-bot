import os
import logging
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
import requests

# Загрузка переменных окружения
load_dotenv()

# 🔐 Ключи из окружения
TOKEN = os.getenv("TOKEN")
TWELVE_DATA_KEY = os.getenv("API_KEY")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📦 Инициализация БД
def init_db():
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT,
            timeframe TEXT,
            signal_type TEXT,
            signal TEXT,
            timestamp TEXT
        )
    """)
    conn.commit()
    conn.close()

# 📡 Получение сигнала от Twelve Data
def get_basic_signal(pair: str, interval: str):
    try:
        url = f"https://api.twelvedata.com/time_series?symbol={pair}&interval={interval}&apikey={TWELVE_DATA_KEY}"
        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            raise ValueError(f"Ошибка анализа: {data.get('message', 'данные не получены')}")

        last_close = float(data["values"][0]["close"])
        prev_close = float(data["values"][1]["close"])
        signal = "BUY" if last_close > prev_close else "SELL"
        return signal
    except Exception as e:
        return f"Ошибка анализа: {str(e)}"

# 📊 Получение сигнала от Alpha Vantage
def get_smart_signal(pair: str, interval: str):
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={pair}&interval={interval}&apikey={ALPHA_VANTAGE_KEY}&datatype=json"
        response = requests.get(url)
        data = response.json()

        # Находим ключ "Time Series (1min)" или другой
        time_series_key = next((k for k in data if "Time Series" in k), None)
        if not time_series_key:
            raise ValueError(f"Ошибка анализа: {data.get('Note') or data.get('Error Message') or 'нет данных'}")

        time_series = data[time_series_key]
        values = list(time_series.values())
        last_close = float(values[0]['4. close'])
        prev_close = float(values[1]['4. close'])
        signal = "BUY" if last_close > prev_close else "SELL"
        return signal
    except Exception as e:
        return f"Ошибка анализа: {str(e)}"

# 🚀 Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📡 Сигнал", callback_data="basic")],
        [InlineKeyboardButton("📊 Умный сигнал (RSI+MACD)", callback_data="smart")]
    ]
    await update.message.reply_text("Выбери тип сигнала:", reply_markup=InlineKeyboardMarkup(keyboard))

# 🎯 Обработка сигналов по кнопкам
async def handle_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = "EUR/USD"
    interval = "1min"

    if query.data == "basic":
        signal = get_basic_signal(pair, interval)
        text = f"📡 Сигнал {pair} M1\n🟢 {signal}\n⏳ Время: 1–3 мин"
        signal_type = "basic"
    else:
        signal = get_smart_signal(pair, interval)
        text = f"📊 Умный сигнал (RSI+MACD)\n{signal}\n⏳ Время: 1–3 мин"
        signal_type = "smart"

    # 💾 Сохраняем сигнал в БД
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    c.execute("""
        INSERT INTO signals (pair, timeframe, signal_type, signal, timestamp)
        VALUES (?, ?, ?, ?, ?)
    """, (pair, interval, signal_type, signal, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

    await query.edit_message_text(text)

# 🚦 Запуск бота
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_signal))
    app.run_polling()
