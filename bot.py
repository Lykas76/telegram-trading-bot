import os
import asyncio
import requests
import sqlite3
import pandas as pd
import mplfinance as mpf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv
from datetime import datetime
from flask import Flask, request

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # например: https://your-app.up.railway.app/webhook

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]
active_chats = set()

app_flask = Flask(__name__)

# --- Инициализация базы ---
def init_db():
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
            signal_strength TEXT,
            duration TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_trade_duration(strength: str) -> str:
    if strength == "СИЛЬНЫЙ":
        return "3–5 минут"
    elif strength == "УМЕРЕННЫЙ":
        return "1–3 минуты"
    else:
        return "1 минута"

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
    if "values" not in data:
        raise Exception(data.get("message", "Ошибка получения данных"))
    df = pd.DataFrame(data["values"])
    df["datetime"] = pd.to_datetime(df["datetime"])
    df = df.sort_values("datetime")
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
    elif 30 < rsi < 40 and macd > 0:
        return "УМЕРЕННЫЙ", "🟢 BUY (вверх)"
    elif 60 < rsi < 70 and macd < 0:
        return "УМЕРЕННЫЙ", "🔴 SELL (вниз)"
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
        savefig=filename
    )

async def send_smart_signal(app, chat_id, pair, timeframe):
    tf_map = {"M1": "1min", "M5": "5min", "M15": "15min"}
    interval = tf_map.get(timeframe, "1min")
    try:
        df = fetch_price_series(pair, interval)
        rsi, macd = calculate_rsi_macd(df)
        strength, signal = determine_signal_strength(rsi, macd)
        duration = get_trade_duration(strength)

        conn = sqlite3.connect("signals.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO smart_signals (pair, timeframe, signal, rsi, macd, signal_strength, duration) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (pair, timeframe, signal, rsi, macd, strength, duration)
        )
        conn.commit()
        conn.close()

        draw_candlestick_chart(df, pair=pair, tf=timeframe)

        message = (
            f"📡 Умный сигнал {pair} {timeframe}\n"
            f"{signal} — {strength}\n"
            f"📊 RSI: {rsi:.2f} | MACD: {macd:.4f}\n"
            f"⏳ Время: {duration}"
        )
        button = InlineKeyboardMarkup.from_button(
            InlineKeyboardButton("BUY" if "BUY" in signal else "SELL", callback_data="none")
        )

        await app.bot.send_photo(chat_id=chat_id, photo=open("chart.png", "rb"), caption=message, reply_markup=button)
    except Exception as e:
        await app.bot.send_message(chat_id=chat_id, text=f"⚠️ Ошибка анализа: {e}")

async def auto_update_signals(application):
    while True:
        if not active_chats:
            await asyncio.sleep(60)
            continue
        for chat_id in active_chats:
            await send_smart_signal(application, chat_id, "EUR/USD", "M1")
            await asyncio.sleep(1)
        await asyncio.sleep(300)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    active_chats.add(update.effective_chat.id)
    await update.message.reply_text("Выбери валютную пару:\n" + "\n".join(PAIRS))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in PAIRS:
        context.user_data["pair"] = text
        await update.message.reply_text(f"Выбрана пара: {text}\nТеперь выбери таймфрейм:\n" + "\n".join(TIMEFRAMES))
    elif text in TIMEFRAMES:
        context.user_data["tf"] = text
        await update.message.reply_text(f"Выбран таймфрейм: {text}\nНажми 📊 для сигнала.")
    elif text in ["📊", "📊 Умный сигнал (RSI+MACD)"]:
        pair = context.user_data.get("pair")
        tf = context.user_data.get("tf")
        if pair and tf:
            await send_smart_signal(context.application, update.effective_chat.id, pair, tf)
        else:
            await update.message.reply_text("Сначала выбери валюту и таймфрейм.")
    else:
        await update.message.reply_text("Выбери валютную пару или таймфрейм.")

def telegram_app():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    asyncio.create_task(auto_update_signals(application))
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
