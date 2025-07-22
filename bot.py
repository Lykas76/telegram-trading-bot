import os
import requests
import sqlite3
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = "8aefd7f6d24d4e99ba317872ce59e00c"

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

# 💾 Создание базы данных
conn = sqlite3.connect("signals.db")
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS smart_signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT,
        timeframe TEXT,
        signal TEXT,
        rsi REAL,
        macd REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
conn.commit()
conn.close()


# 📡 Обычный сигнал (по цене)
def get_signal(pair: str, timeframe: str) -> str:
    symbol_map = {
        "EUR/USD": "EUR/USD",
        "GBP/USD": "GBP/USD",
        "AUD/JPY": "AUD/JPY",
        "EUR/CAD": "EUR/CAD"
    }

    tf_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min"
    }

    symbol = symbol_map[pair]
    interval = tf_map[timeframe]

    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={API_KEY}&outputsize=2"

    try:
        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            raise Exception(data.get("message", "Неизвестная ошибка"))

        latest = data["values"][0]
        open_price = float(latest["open"])
        close_price = float(latest["close"])

        if close_price > open_price:
            return "🟢 BUY (вверх)"
        elif close_price < open_price:
            return "🔴 SELL (вниз)"
        else:
            return "⚪️ Нейтрально"
    except Exception as e:
        return f"⚠️ Ошибка получения данных: {e}"


# 📊 Умный сигнал на основе RSI и MACD
def get_s
