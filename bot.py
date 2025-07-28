import os
import logging
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
import requests
import pandas as pd
import mplfinance as mpf

from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
TWELVE_DATA_KEY = os.getenv("API_KEY")

# Включаем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Валютные пары и таймфреймы
PAIRS = ["EUR/USD", "GBP/USD", "EUR/JPY"]
TIMEFRAMES = ["1min", "5min", "15min"]

# Глобальные переменные (можно заменить на контекст пользователя)
user_selection = {}

# 📊 Получение сигнала от Twelve Data
def get_signal(pair, interval):
    try:
        symbol = pair.replace("/", "")
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}"
        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            raise ValueError("Нет данных")

        last = float(data["values"][0]["close"])
        prev = float(data["values"][1]["close"])
        signal = "BUY" if last > prev else "SELL"
        return signal
    except Exception as e:
        logger.error(f"Ошибка сигнала: {e}")
        return f"Ошибка анализа: {e}"

# 📈 Генерация графика
def generate_chart(pair, interval):
    try:
        symbol = pair.replace("/", "")
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}&outputsize=30"
        response = requests.get(url)
        data = response.json()

        if "values" not in data:
            raise ValueError("Нет данных 'values'")

        df = pd.DataFrame(data["values"])
        df["datetime"] = pd.to_datetime(df["datetime"])
        df.set_index("datetime", inplace=True)
        df = df.astype(float)
        df = df.sort_index()

        filename = f"{symbol}_{interval}.png"
        mpf.plot(df, type="candle", style="charles", volume=False, savefig=filename)
        return filename
    except Exception as e:
        logger.error(f"Chart error: {e}")
        return None

# 🟢 Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in PAIRS]
    await update.message.reply_text("Выбери валютную пару:", reply_markup=InlineKeyboardMarkup(keyboard))

# 🕐 Выбор таймфрейма
async def choose_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pair = query.data.split("_")[1]
    user_selection[query.from_user.id] = {"pair": pair}

    keyboard = [[InlineKeyboardButton(tf, callback_data=f"time_{tf}")] for tf in TIMEFRAMES]
    await query.edit_message_text(f"Выбрана пара: {pair}\nВыбери таймфрейм:", reply_markup=InlineKeyboardMarkup(keyboard))

# 📡 Кнопки сигналов
async def choose_signal_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    tf = query.data.split("_")[1]
    user_selection[query.from_user.id]["timeframe"] = tf

    keyboard = [
        [InlineKeyboardButton("📡 Сигнал", callback_data="signal_basic")],
        [InlineKeyboardButton("📊 Умный сигнал (RSI+MACD)", callback_data="signal_smart")]
    ]
    await query.edit_message_text(f"Таймфрейм: {tf}\nВыбери тип сигнала:", reply_markup=InlineKeyboardMarkup(keyboard))

# 📤 Отправка сигнала + график
async def handle_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = query.from_user.id
    pair = user_selection[uid]["pair"]
    interval = user_selection[uid]["timeframe"]

    signal = get_signal(pair, interval)
    chart_path = generate_chart(pair, interval)

    text = f"📡 Сигнал {pair} {interval.upper()}\n🟢 {signal}\n⏳ Время: 1–3 мин"

    if chart_path:
        with open(chart_path, "rb") as img:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=img, caption=text)
    else:
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text)

# 📌 Роутинг коллбеков
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("pair_"):
        await choose_timeframe(update, context)
    elif data.startswith("time_"):
        await choose_signal_type(update, context)
    elif data.startswith("signal_"):
        await handle_signal(update, context)

# ▶️ Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
