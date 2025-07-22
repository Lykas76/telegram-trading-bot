import os
import requests
import sqlite3
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = "dc4ce2bd0a5e4865abcd294f28d55796"

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

# Создание базы данных (один раз при старте)
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
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

def get_trade_duration(timeframe: str) -> str:
    if timeframe == "M1":
        return "1–3 мин"
    elif timeframe == "M5":
        return "3–5 мин"
    elif timeframe == "M15":
        return "15–30 мин"
    else:
        return "1–3 мин"

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

# Получение ценовой серии для расчёта индикаторов
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
    df = df.sort_values("datetime")  # сортируем по времени возрастания
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    return df

# Расчет RSI и MACD на данных DataFrame
def calculate_rsi_macd(df: pd.DataFrame):
    rsi_indicator = RSIIndicator(close=df["close"], window=14)
    df["rsi"] = rsi_indicator.rsi()
    macd_indicator = MACD(close=df["close"])
    df["macd"] = macd_indicator.macd()
    last_rsi = df["rsi"].iloc[-1]
    last_macd = df["macd"].iloc[-1]
    return last_rsi, last_macd

def get_smart_signal(pair: str, timeframe: str) -> str:
    tf_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min"
    }
    symbol = pair
    interval = tf_map.get(timeframe, "1min")
    try:
        df = fetch_price_series(symbol, interval)
        rsi, macd = calculate_rsi_macd(df)
        if rsi < 30 and macd > 0:
            signal = "🟢 BUY (вверх)"
        elif rsi > 70 and macd < 0:
            signal = "🔴 SELL (вниз)"
        else:
            signal = "⚪️ Нейтрально"
        duration = get_trade_duration(timeframe)
        # Сохраняем сигнал в базу
        conn = sqlite3.connect("signals.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO smart_signals (pair, timeframe, signal, rsi, macd) VALUES (?, ?, ?, ?, ?)",
            (pair, timeframe, signal, rsi, macd)
        )
        conn.commit()
        conn.close()
        return f"🤖 Умный сигнал {pair} {timeframe}\n{signal}\n📊 RSI: {rsi:.2f}, MACD: {macd:.4f}\n⏳ Время: {duration}"
    except Exception as e:
        duration = get_trade_duration(timeframe)
        return f"🤖 Умный сигнал {pair} {timeframe}\n⚠️ Ошибка анализа: {e}\n📊 RSI: 0.0, MACD: 0.0000\n⏳ Время: {duration}"

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text(
        "👋 Привет! Выбери валютную пару:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# Обработка всех сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text in PAIRS:
        context.user_data["pair"] = text
        keyboard = [[tf] for tf in TIMEFRAMES]
        await update.message.reply_text(
            f"Выбрана пара: {text}\nТеперь выбери таймфрейм:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    if text in TIMEFRAMES:
        context.user_data["tf"] = text
        keyboard = [["📡 Сигнал", "🔄 Валюта", "📊 Умный сигнал (RSI+MACD)"]]
        await update.message.reply_text(
            f"Выбран таймфрейм: {text}",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    if text == "📡 Сигнал":
        pair = context.user_data.get("pair")
        tf = context.user_data.get("tf")
        if pair and tf:
            signal = get_signal(pair, tf)
            duration = get_trade_duration(tf)
            await update.message.reply_text(f"🔔 Сигнал {pair} {tf}\n{signal}\n⏳ Время: {duration}")
        else:
            await update.message.reply_text("Сначала выбери валюту и таймфрейм.")
        return
    if text == "📊 Умный сигнал (RSI+MACD)":
        pair = context.user_data.get("pair")
        tf = context.user_data.get("tf")
        if pair and tf:
            signal = get_smart_signal(pair, tf)
            await update.message.reply_text(signal)
        else:
            await update.message.reply_text("Сначала выбери валюту и таймфрейм.")
        return
    if text == "🔄 Валюта":
        context.user_data.pop("pair", None)
        context.user_data.pop("tf", None)
        keyboard = [[pair] for pair in PAIRS]
        await update.message.reply_text(
            "Выбери валютную пару заново:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return
    await update.message.reply_text("Выбери действие с клавиатуры.")

# Запуск бота
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()

