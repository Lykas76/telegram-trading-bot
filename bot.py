import os
import asyncio
import sqlite3
import pandas as pd
import requests
import mplfinance as mpf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, request

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]
active_chats = set()

app_flask = Flask(__name__)

# --- Инициализация базы ---
def init_db():
    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT,
        timeframe TEXT,
        signal TEXT,
        strength TEXT,
        rsi REAL,
        macd REAL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    conn.commit()
    conn.close()

init_db()

def fetch_price_series(symbol: str, interval: str, outputsize=50):
    url = "https://api.twelvedata.com/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "apikey": API_KEY,
        "outputsize": outputsize,
        "format": "JSON"
    }
    response = requests.get(url, params=params)
    data = response.json()
    df = pd.DataFrame(data["values"])
    df = df[::-1]
    df.columns = df.columns.str.lower()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df

def calculate_rsi_macd(df: pd.DataFrame):
    rsi = RSIIndicator(close=df["close"], window=14).rsi().iloc[-1]
    macd = MACD(close=df["close"]).macd().iloc[-1]
    return rsi, macd

def determine_signal_strength(rsi, macd):
    if rsi < 25 and macd > 0:
        return "СИЛЬНЫЙ", "🟢 BUY (вверх)"
    elif rsi > 75 and macd < 0:
        return "СИЛЬНЫЙ", "🔴 SELL (вниз)"
    elif rsi < 45 and macd > 0:
        return "СРЕДНИЙ", "🟢 BUY (вверх)"
    elif rsi > 55 and macd < 0:
        return "СРЕДНИЙ", "🔴 SELL (вниз)"
    else:
        return "СЛАБЫЙ", "⚪️ Нейтрально"

def draw_candlestick_chart(df: pd.DataFrame, filename="chart.png", pair="", tf=""):
    title = f"{pair} {tf} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    mpf.plot(
        df.tail(50),
        type='candle',
        mav=(9, 21),
        volume=("volume" in df.columns),
        title=title,
        style="yahoo",
        savefig=filename
    )

async def send_smart_signal(app, chat_id, pair, timeframe):
    tf_map = {"M1": "1min", "M5": "5min", "M15": "15min"}
    interval = tf_map.get(timeframe, "1min")
    try:
        df = fetch_price_series(pair.replace("/", ""), interval)
        rsi, macd = calculate_rsi_macd(df)
        strength, signal = determine_signal_strength(rsi, macd)
        draw_candlestick_chart(df, "chart.png", pair, timeframe)
        duration = "1–3 мин" if strength == "СЛАБЫЙ" else "3–5 мин"
        text = (
            f"🤖 Умный сигнал {pair} {timeframe}\n"
            f"{signal}\n"
            f"📊 RSI: {round(rsi, 2)}, MACD: {round(macd, 4)}\n"
            f"📈 Сила сигнала: {strength}\n"
            f"⏳ Время: {duration}"
        )
        await app.bot.send_photo(chat_id=chat_id, photo=open("chart.png", "rb"), caption=text)
        conn = sqlite3.connect("signals.db")
        conn.execute(
            "INSERT INTO signals (pair, timeframe, signal, strength, rsi, macd) VALUES (?, ?, ?, ?, ?, ?)",
            (pair, timeframe, signal, strength, rsi, macd)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        await app.bot.send_message(chat_id=chat_id, text=f"⚠️ Ошибка анализа: {e}")

async def auto_update_signals(app):
    while True:
        if not active_chats:
            await asyncio.sleep(60)
            continue
        for chat_id in active_chats:
            await send_smart_signal(app, chat_id, "EUR/USD", "M1")
            await asyncio.sleep(1)
        await asyncio.sleep(300)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text("👋 Привет! Выбери валютную пару:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    active_chats.add(update.effective_chat.id)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in PAIRS:
        context.user_data["pair"] = text
        keyboard = [[tf] for tf in TIMEFRAMES]
        await update.message.reply_text(f"Выбрана пара: {text}\nТеперь выбери таймфрейм:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    elif text in TIMEFRAMES:
        context.user_data["tf"] = text
        keyboard = [["📡 Сигнал", "🔄 Валюта", "📊 Умный сигнал (RSI+MACD)"]]
        await update.message.reply_text(f"Выбран таймфрейм: {text}", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    elif text in ["📊", "📊 Умный сигнал (RSI+MACD)"]:
        pair = context.user_data.get("pair")
        tf = context.user_data.get("tf")
        if pair and tf:
            await send_smart_signal(context.application, update.effective_chat.id, pair, tf)
        else:
            await update.message.reply_text("Сначала выбери валюту и таймфрейм.")
    elif text == "🔄 Валюта":
        context.user_data.pop("pair", None)
        context.user_data.pop("tf", None)
        keyboard = [[pair] for pair in PAIRS]
        await update.message.reply_text("Выбери валютную пару заново:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    else:
        await update.message.reply_text("Выбери действие с клавиатуры.")

async def on_startup(app):
    try:
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook удалён")
    except Exception as e:
        print(f"⚠️ Ошибка удаления webhook: {e}")
    asyncio.create_task(auto_update_signals(app))

def telegram_app():
    application = Application.builder().token(TOKEN).post_init(on_startup).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    return application

@app_flask.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app().bot)
    telegram_app().update_queue.put_nowait(update)
    return "ok"

if __name__ == "__main__":
    telegram_app().run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        webhook_url=WEBHOOK_URL + "/webhook"
    )
