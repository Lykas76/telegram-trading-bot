import os
import sqlite3
import logging
import requests
import pandas as pd
import mplfinance as mpf
from datetime import datetime
from dotenv import load_dotenv
from ta.momentum import RSIIndicator
from ta.trend import MACD
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Загрузка .env
load_dotenv()

TOKEN = os.getenv("TOKEN")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")
TWELVE_DATA_KEY = os.getenv("API_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PAIRS = ["EUR/USD", "GBP/USD", "EUR/CAD"]
TIMEFRAMES = {"M1": "1min", "M5": "5min", "M15": "15min"}

user_selection = {}

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await update.message.reply_text("🌐 Выбери валютную пару:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat.id

    if data.startswith("pair_"):
        pair = data.split("_")[1]
        user_selection[chat_id] = {"pair": pair}
        tf_keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")] for tf in TIMEFRAMES]
        await query.edit_message_text(f"🔄 Выбрано: {pair}\n🕒 Таймфрейм?", reply_markup=InlineKeyboardMarkup(tf_keyboard))

    elif data.startswith("tf_"):
        tf = data.split("_")[1]
        user_selection[chat_id]["timeframe"] = tf
        signal_keyboard = [
            [InlineKeyboardButton("📡 Сигнал", callback_data="signal_basic")],
            [InlineKeyboardButton("📊 Умный сигнал (RSI+MACD)", callback_data="signal_smart")]
        ]
        await query.edit_message_text(f"🕒 Выбран: {tf}\nВыбери тип сигнала:", reply_markup=InlineKeyboardMarkup(signal_keyboard))

    elif data.startswith("signal_"):
        signal_type = data.split("_")[1]
        pair = user_selection[chat_id]["pair"]
        tf_name = user_selection[chat_id]["timeframe"]
        interval = TIMEFRAMES[tf_name]

        image_path = await generate_chart(pair, interval)

        if signal_type == "basic":
            signal = get_basic_signal(pair, interval)
            title = f"📡 Сигнал {pair} {tf_name}"
        else:
            signal = get_smart_signal(pair, interval)
            title = f"📊 Умный сигнал {pair} {tf_name}"

        save_signal(pair, tf_name, signal_type, signal)

        caption = f"{title}\n🔹 {signal}\n⏳ Время: 1–3 мин"

        with open(image_path, 'rb') as img:
            await query.message.reply_photo(photo=img, caption=caption)

# Обычный сигнал (TwelveData)
def get_basic_signal(pair: str, interval: str):
    try:
        symbol = pair.replace("/", "")
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}"
        response = requests.get(url)
        data = response.json()
        values = data.get("values", [])
        if len(values) < 2:
            raise ValueError("Данные не получены")
        last_close = float(values[0]["close"])
        prev_close = float(values[1]["close"])
        return "BUY" if last_close > prev_close else "SELL"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# RSI+MACD из Alpha Vantage
def get_smart_signal(pair: str, interval: str):
    try:
        symbol = pair.replace("/", "") + "=X"
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={interval}&apikey={ALPHA_VANTAGE_KEY}"
        response = requests.get(url)
        data = response.json()
        key = next((k for k in data if "Time Series" in k), None)
        if not key:
            raise ValueError("Данные не найдены")

        df = pd.DataFrame.from_dict(data[key], orient='index').astype(float).sort_index()
        df.columns = ["open", "high", "low", "close", "volume"]
        df["RSI"] = RSIIndicator(df["close"]).rsi()
        macd = MACD(df["close"])
        df["MACD"] = macd.macd_diff()

        rsi = df["RSI"].iloc[-1]
        macd_val = df["MACD"].iloc[-1]

        if rsi < 30 and macd_val > 0:
            return "BUY"
        elif rsi > 70 and macd_val < 0:
            return "SELL"
        else:
            return "WAIT"
    except Exception as e:
        return f"Ошибка: {str(e)}"

# Сохранение в DB
def save_signal(pair, tf, s_type, signal):
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    c.execute("INSERT INTO signals (pair, timeframe, signal_type, signal, timestamp) VALUES (?, ?, ?, ?, ?)",
              (pair, tf, s_type, signal, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

# Создаёт свечной график
def generate_chart(pair, interval):
    try:
        symbol = pair.replace("/", "")
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}&outputsize=30"
        response = requests.get(url)
        data = response.json()
        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        df = df.astype(float).sort_index()
        filename = f"chart_{pair.replace('/', '')}_{interval}.png"
        mpf.plot(df, type='candle', style='charles', savefig=filename)
        return filename
    except Exception as e:
        logger.error(f"Chart error: {e}")
        return ""

if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
