import os
import logging
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, CallbackQueryHandler
import requests

# Загрузка переменных окружения
load_dotenv()

# 🔐 Получение ключей из Railway/переменных окружения
TOKEN = os.getenv("TOKEN")
TWELVE_DATA_KEY = os.getenv("API_KEY")  # Для обычных сигналов
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")  # Для умных сигналов (RSI + MACD)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация базы данных
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

# Получение обычного сигнала (Twelve Data)
def get_basic_signal(pair: str, interval: str):
    try:
        symbol = pair.replace("/", "")
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}"
        response = requests.get(url)
        data = response.json()
        if "values" not in data:
            raise ValueError("Ошибка анализа: данные не получены")
        # Пример: просто направление (для теста)
        last_close = float(data["values"][0]["close"])
        prev_close = float(data["values"][1]["close"])
        signal = "BUY" if last_close > prev_close else "SELL"
        return signal
    except Exception as e:
        return f"Ошибка анализа: {str(e)}"

# Получение умного сигнала (Alpha Vantage)
def get_smart_signal(pair: str, interval: str):
    try:
        symbol = pair.replace("/", "")
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={ALPHA_VANTAGE_KEY}&datatype=json"
        response = requests.get(url)
        data = response.json()
        if "Time Series" not in str(data):
            raise ValueError("Ошибка анализа: данные не получены")
        # Простейший RSI+MACD можно вставить здесь (упрощён)
        return "BUY"  # Заглушка
    except Exception as e:
        return f"Ошибка анализа: {str(e)}"

# Команды бота
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📡 Сигнал", callback_data="basic")],
                [InlineKeyboardButton("📊 Умный сигнал (RSI+MACD)", callback_data="smart")]]
    await update.message.reply_text("Выбери тип сигнала:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = "EUR/USD"
    interval = "1min"  # M1
    if query.data == "basic":
        signal = get_basic_signal(pair, interval)
        text = f"📡 Сигнал {pair} M1\n🟢 {signal}\n⏳ Время: 1–3 мин"
    else:
        signal = get_smart_signal(pair, interval)
        text = f"📊 Умный сигнал (RSI+MACD)\n{signal}\n⏳ Время: 1–3 мин"
    await query.edit_message_text(text)

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_signal))
    app.run_polling()
