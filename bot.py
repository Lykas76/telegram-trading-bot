import os
import asyncio
import logging
import requests
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf

from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackContext, ContextTypes, MessageHandler, filters, CallbackQueryHandler

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
TWELVE_DATA_KEY = os.getenv("TWELVE_DATA_KEY")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

logging.basicConfig(level=logging.INFO)
app_flask = Flask(__name__)
bot = Bot(token=TOKEN)

DB_FILE = "signals.db"
if not os.path.exists(DB_FILE):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair TEXT,
            timeframe TEXT,
            signal_type TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

# Utils
async def fetch_twelve_data(pair, timeframe):
    symbol = pair.replace("/", "")
    interval = timeframe.lower()
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}&outputsize=50"
    response = requests.get(url)
    data = response.json()
    return pd.DataFrame(data['values']) if 'values' in data else None

def fetch_alpha_vantage_data(pair, interval):
    symbol = pair.replace("/", "")
    function = "TIME_SERIES_INTRADAY"
    url = f"https://www.alphavantage.co/query?function={function}&symbol={symbol}&interval={interval}&apikey={ALPHA_VANTAGE_KEY}&outputsize=compact"
    r = requests.get(url)
    data = r.json()
    key = f"Time Series ({interval})"
    if key in data:
        df = pd.DataFrame.from_dict(data[key], orient='index')
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        df = df.astype(float)
        return df.iloc[::-1]
    return None

def calculate_rsi(df, period=14):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_macd(df):
    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    return macd

def save_signal(pair, timeframe, signal_type):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO signals (pair, timeframe, signal_type) VALUES (?, ?, ?)", (pair, timeframe, signal_type))
    conn.commit()
    conn.close()

async def smart_signal(pair, timeframe):
    interval_map = {"M1": "1min", "M5": "5min", "M15": "15min"}
    df = fetch_alpha_vantage_data(pair, interval_map[timeframe])
    if df is None or 'volume' not in df:
        return "⚠️ Ошибка анализа: 'volume'"

    df['rsi'] = calculate_rsi(df)
    df['macd'] = calculate_macd(df)
    rsi = df['rsi'].iloc[-1]
    macd = df['macd'].iloc[-1]

    if rsi < 30 and macd > 0:
        signal = "🟢 BUY (вверх)"
    elif rsi > 70 and macd < 0:
        signal = "🔴 SELL (вниз)"
    else:
        signal = "⚠️ Нет сигнала"

    save_signal(pair, timeframe, signal)
    return f"🤖 Умный сигнал {pair} {timeframe}\n{signal}\n📊 RSI: {round(rsi, 2)}, MACD: {round(macd, 4)}\n⏳ Время: 1–3 мин"

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    buttons = [[InlineKeyboardButton(tf, callback_data=tf)] for tf in TIMEFRAMES]
    await update.message.reply_text("Выберите таймфрейм:", reply_markup=InlineKeyboardMarkup(buttons))

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    timeframe = query.data
    pair = "EUR/USD"
    msg = await smart_signal(pair, timeframe)
    await query.edit_message_text(text=msg)

# Flask Webhook
@app_flask.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    asyncio.run(application.process_update(update))
    return "ok"

async def run_bot():
    global application
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))

    await application.initialize()
    await application.start()
    await application.bot.set_webhook(url=WEBHOOK_URL + "/webhook")
    await application.updater.start_polling()

if __name__ == "__main__":
    asyncio.run(run_bot())
    app_flask.run(host="0.0.0.0", port=8080)

