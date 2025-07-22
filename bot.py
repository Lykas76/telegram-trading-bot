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
def get_smart_signal(pair: str, timeframe: str) -> str:
    tf_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min"
    }
    symbol = pair
    interval = tf_map[timeframe]

    url_rsi = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval={interval}&apikey={API_KEY}"
    url_macd = f"https://api.twelvedata.com/macd?symbol={symbol}&interval={interval}&apikey={API_KEY}"

    try:
        rsi_data = requests.get(url_rsi).json()
        macd_data = requests.get(url_macd).json()

        rsi = float(rsi_data["values"][0]["rsi"])
        macd = float(macd_data["values"][0]["macd"])

        # Правила сигнала
        if rsi < 30 and macd > 0:
            signal = "🟢 BUY (вверх)"
        elif rsi > 70 and macd < 0:
            signal = "🔴 SELL (вниз)"
        else:
            signal = "⚪️ Нейтрально"

        # 💾 Сохраняем сигнал в БД
        conn = sqlite3.connect("signals.db")
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO smart_signals (pair, timeframe, signal, rsi, macd) VALUES (?, ?, ?, ?, ?)",
            (pair, timeframe, signal, rsi, macd)
        )
        conn.commit()
        conn.close()

        return f"🤖 Умный сигнал {pair} {timeframe}\n{signal}\n📊 RSI: {rsi:.2f}, MACD: {macd:.4f}\n⏳ Время: 1–3 мин"
    except Exception as e:
        return f"🤖 Умный сигнал {pair} {timeframe}\n⚠️ Ошибка анализа: {e}\n📊 RSI: 0.0, MACD: 0.0000\n⏳ Время: 1–3 мин"


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
            await update.message.reply_text(f"🔔 Сигнал {pair} {tf}\n{signal}\n⏳ Время: 1–3 мин")
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
