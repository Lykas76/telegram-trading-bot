import os
import requests
import asyncio
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
API_KEY = "TMNLROVN3BTDZUFS"  # Alpha Vantage API

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

def get_signal(pair: str, timeframe: str) -> str:
    symbol_map = {
        "EUR/USD": ("EUR", "USD"),
        "GBP/USD": ("GBP", "USD"),
        "AUD/JPY": ("AUD", "JPY"),
        "EUR/CAD": ("EUR", "CAD")
    }

    tf_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min"
    }

    from_symbol, to_symbol = symbol_map[pair]
    interval = tf_map[timeframe]

    url = (
        f"https://www.alphavantage.co/query"
        f"?function=FX_INTRADAY&from_symbol={from_symbol}&to_symbol={to_symbol}"
        f"&interval={interval}&apikey={API_KEY}&outputsize=compact"
    )

    try:
        response = requests.get(url)
        data = response.json()
        ts_key = f"Time Series FX ({interval})"
        ts = data[ts_key]
        latest_time = sorted(ts.keys())[-1]
        candle = ts[latest_time]
        open_price = float(candle["1. open"])
        close_price = float(candle["4. close"])

        if close_price > open_price:
            return "🟢 BUY (вверх)"
        elif close_price < open_price:
            return "🔴 SELL (вниз)"
        else:
            return "⚪️ Нейтрально"
    except Exception as e:
        return f"⚠️ Ошибка получения данных: {e}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text(
        "👋 Привет! Выбери валютную пару:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

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
        keyboard = [["📡 Сигнал", "🔄 Валюта"]]
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
            await update.message.reply_text(
                f"🔔 Сигнал {pair} {tf}\n{signal}\n⏳ Время: 1–3 мин"
            )
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

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ Бот запущен")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

