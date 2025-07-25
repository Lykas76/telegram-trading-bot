import os
import sqlite3
import asyncio
import logging
import requests
import matplotlib.pyplot as plt
import mplfinance as mpf
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")  # Twelve Data
ALPHA_KEY = os.getenv("ALPHA_VANTAGE_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

PAIR = "EUR/USD"
DB_FILE = "signals.db"
TIMEFRAMES = ["M1", "M5", "M15"]

logging.basicConfig(level=logging.INFO)

# --- Database Setup ---
def create_db():
    conn = sqlite3.connect(DB_FILE)
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

create_db()

# --- Signal Logic ---
def get_price_data(pair, interval):
    symbol = pair.replace("/", "")
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval.lower()}&apikey={API_KEY}&outputsize=30"
    response = requests.get(url).json()
    candles = response.get("values", [])
    if not candles:
        return []
    return list(reversed(candles))

def get_alpha_data(pair, interval):
    symbol = pair.replace("/", "")
    func = "TIME_SERIES_INTRADAY"
    url = f"https://www.alphavantage.co/query?function={func}&symbol={symbol}&interval={interval.lower()}&apikey={ALPHA_KEY}&outputsize=compact"
    response = requests.get(url).json()
    data = response.get(f"Time Series ({interval})", {})
    candles = []
    for time, values in sorted(data.items())[-30:]:
        candles.append({
            "datetime": time,
            "open": values["1. open"],
            "high": values["2. high"],
            "low": values["3. low"],
            "close": values["4. close"],
            "volume": values.get("5. volume", "0")
        })
    return candles

def calculate_rsi(prices):
    if len(prices) < 14:
        return 0.0
    gains = [max(0, prices[i] - prices[i-1]) for i in range(1, len(prices))]
    losses = [max(0, prices[i-1] - prices[i]) for i in range(1, len(prices))]
    avg_gain = sum(gains) / 14
    avg_loss = sum(losses) / 14
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)

def calculate_macd(prices):
    def ema(values, period):
        k = 2 / (period + 1)
        ema_values = [sum(values[:period]) / period]
        for price in values[period:]:
            ema_values.append(price * k + ema_values[-1] * (1 - k))
        return ema_values

    if len(prices) < 26:
        return 0.0
    ema12 = ema(prices, 12)
    ema26 = ema(prices, 26)
    macd = [a - b for a, b in zip(ema12[-len(ema26):], ema26)]
    return round(macd[-1], 4) if macd else 0.0

def generate_signal(rsi, macd):
    if rsi < 30 and macd > 0:
        return "BUY"
    elif rsi > 70 and macd < 0:
        return "SELL"
    return "HOLD"

def save_smart_signal(pair, timeframe, signal, rsi, macd):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO smart_signals (pair, timeframe, signal, rsi, macd)
        VALUES (?, ?, ?, ?, ?)
    """, (pair, timeframe, signal, rsi, macd))
    conn.commit()
    conn.close()

# --- Telegram Bot ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["M1", "M5", "M15"]]
    await update.message.reply_text("👋 Привет! Выбери таймфрейм:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def choose_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['timeframe'] = update.message.text
    keyboard = [["📡 Сигнал"], ["📊 Умный сигнал"]]
    await update.message.reply_text(f"Выбран таймфрейм {update.message.text}. Выбери действие:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def send_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tf = context.user_data.get("timeframe", "M1")
    candles = get_price_data(PAIR, tf)
    if not candles:
        await update.message.reply_text("⚠️ Ошибка получения данных!")
        return
    signal = "BUY" if float(candles[-1]['close']) > float(candles[-2]['close']) else "SELL"
    text = f"🔔 Сигнал {PAIR} {tf}\n{'🟢' if signal=='BUY' else '🔴'} {signal} (по цене)\n⏳ Время: 1–3 мин"
    await update.message.reply_text(text)

async def send_smart_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tf = context.user_data.get("timeframe", "M1")
    interval_map = {"M1": "1min", "M5": "5min", "M15": "15min"}
    candles = get_alpha_data(PAIR, interval_map[tf])
    if not candles:
        await update.message.reply_text("⚠️ Ошибка анализа данных!")
        return

    closes = [float(c["close"]) for c in candles]
    rsi = calculate_rsi(closes)
    macd = calculate_macd(closes)
    signal = generate_signal(rsi, macd)
    save_smart_signal(PAIR, tf, signal, rsi, macd)

    text = f"🤖 Умный сигнал {PAIR} {tf}\n{'🟢' if signal=='BUY' else '🔴' if signal=='SELL' else '⚪️'} {signal}\n📊 RSI: {rsi}, MACD: {macd}\n⏳ Время: 1–3 мин"
    await update.message.reply_text(text)

async def run_bot():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^(M1|M5|M15)$"), choose_timeframe))
    app.add_handler(MessageHandler(filters.Regex("^📡 Сигнал$"), send_signal))
    app.add_handler(MessageHandler(filters.Regex("^📊 Умный сигнал$"), send_smart_signal))

    await app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        webhook_url=WEBHOOK_URL + "/webhook"
    )

if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(run_bot())
    except RuntimeError as e:
        if str(e).startswith("Этот цикл событий уже запущен") or str(e).startswith("Cannot close a running event loop"):
            loop = asyncio.get_event_loop()
            loop.create_task(run_bot())
            loop.run_forever()
        else:
            raise

