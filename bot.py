import os
import sqlite3
import asyncio
import pandas as pd
import mplfinance as mpf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = os.getenv("API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")  # Пример: https://your-app.up.railway.app

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]
active_chats = set()

app_flask = Flask(__name__)


def init_db():
    conn = sqlite3.connect("signals.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            pair TEXT,
            timeframe TEXT,
            rsi REAL,
            macd REAL,
            signal TEXT
        )
    ''')
    conn.commit()
    conn.close()


def get_trade_duration(strength: str) -> str:
    if strength == "СИЛЬНЫЙ":
        return "3–5 минут"
    elif strength == "СРЕДНИЙ":
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
    df = pd.read_json(url, params=params)['values']
    df = pd.DataFrame(df)
    df = df.iloc[::-1]  # переворачиваем, чтобы были по времени
    df.columns = df.columns.str.lower()
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    return df


def calculate_rsi_macd(df: pd.DataFrame):
    rsi = RSIIndicator(close=df["close"], window=14).rsi().iloc[-1]
    macd = MACD(close=df["close"]).macd().iloc[-1]
    return rsi, macd


def determine_signal_strength(rsi, macd):
    if rsi < 25 and macd > 0:
        return "СИЛЬНЫЙ", "🟢 BUY"
    elif rsi > 70 and macd < 0:
        return "СИЛЬНЫЙ", "🔴 SELL"
    elif 30 <= rsi <= 70:
        return "СРЕДНИЙ", "🟡 Внимание"
    else:
        return "СЛАБЫЙ", "⚪️ Нейтрально"


def draw_candlestick_chart(df: pd.DataFrame, filename="chart.png", pair="", tf=""):
    title = f"{pair} {tf} • {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC"
    mpf.plot(
        df.tail(50),
        type='candle',
        mav=(9, 21),
        volume=False,
        title=title,
        style="yahoo",
        savefig=filename
    )


async def send_smart_signal(app, chat_id, pair, timeframe):
    tf_map = {"M1": "1min", "M5": "5min", "M15": "15min"}
    interval = tf_map.get(timeframe, "1min")

    try:
        symbol = pair.replace("/", "")
        df = fetch_price_series(symbol, interval)
        rsi, macd = calculate_rsi_macd(df)
        strength, signal_icon = determine_signal_strength(rsi, macd)
        duration = get_trade_duration(strength)

        draw_candlestick_chart(df, filename="chart.png", pair=pair, tf=timeframe)

        with open("chart.png", "rb") as photo:
            await app.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=f"📊 Умный сигнал {pair} {timeframe}\n{signal_icon} {strength}\n📈 RSI: {rsi:.2f}, MACD: {macd:.4f}\n⏳ Время: {duration}"
            )
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
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text("👋 Привет! Выбери валютную пару:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
    active_chats.add(update.effective_chat.id)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in PAIRS:
        context.user_data["pair"] = text
        keyboard = [[tf] for tf in TIMEFRAMES]
        await update.message.reply_text(f"Выбрана пара: {text}\nТеперь выбери таймфрейм:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return
    elif text in TIMEFRAMES:
        context.user_data["tf"] = text
        keyboard = [["📊 Умный сигнал (RSI+MACD)"]]
        await update.message.reply_text(f"Выбран таймфрейм: {text}", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))
        return
    elif text in ["📊", "📊 Умный сигнал (RSI+MACD)"]:
        pair = context.user_data.get("pair")
        tf = context.user_data.get("tf")
        if pair and tf:
            await send_smart_signal(context.application, update.effective_chat.id, pair, tf)
        else:
            await update.message.reply_text("Сначала выбери валюту и таймфрейм.")
        return
    await update.message.reply_text("Выбери действие с клавиатуры.")


@app_flask.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), telegram_app().bot)
    telegram_app().update_queue.put_nowait(update)
    return "ok"


def telegram_app():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT, handle_message))
    return application


if __name__ == "__main__":
    init_db()
    app = telegram_app()
    asyncio.run(auto_update_signals(app))
    app.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        webhook_url=WEBHOOK_URL + "/webhook"
    )
