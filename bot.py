import os
import logging
import sqlite3
import requests
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Загрузка переменных окружения
load_dotenv()
TOKEN = os.getenv("TOKEN")
TWELVE_DATA_KEY = os.getenv("API_KEY")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация базы данных
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

# Получение обычного сигнала
def get_basic_signal(pair: str, interval: str):
    try:
        symbol = pair.replace("/", "")
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&apikey={TWELVE_DATA_KEY}"
        response = requests.get(url)
        data = response.json()
        if "values" not in data:
            raise ValueError("Ошибка анализа: данные не получены")
        last_close = float(data["values"][0]["close"])
        prev_close = float(data["values"][1]["close"])
        return "BUY" if last_close > prev_close else "SELL"
    except Exception as e:
        return f"Ошибка анализа: {str(e)}"

# Получение умного сигнала (заглушка)
def get_smart_signal(pair: str, interval: str):
    try:
        symbol = pair.replace("/", "")
        av_interval = "1min" if interval == "M1" else "5min" if interval == "M5" else "15min"
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval={av_interval}&apikey={ALPHA_VANTAGE_KEY}"
        response = requests.get(url)
        data = response.json()
        if not any(k.startswith("Time Series") for k in data):
            raise ValueError("Ошибка анализа: данные не получены")
        return "BUY"  # Заглушка. Здесь можно добавить RSI + MACD
    except Exception as e:
        return f"Ошибка анализа: {str(e)}"

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(pair, callback_data=f"pair_{pair}")] for pair in ["EUR/USD", "GBP/USD", "EUR/CAD", "AUD/JPY"]]
    await update.message.reply_text("Выберите валютную пару:", reply_markup=InlineKeyboardMarkup(keyboard))

# Обработка выбора пары или таймфрейма или запроса сигнала
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    if data.startswith("pair_"):
        pair = data.split("_")[1]
        context.user_data["pair"] = pair
        keyboard = [[InlineKeyboardButton(tf, callback_data=f"tf_{tf}")] for tf in ["M1", "M5", "M15"]]
        await query.edit_message_text(f"Вы выбрали пару: {pair}\nТеперь выберите таймфрейм:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("tf_"):
        timeframe = data.split("_")[1]
        context.user_data["timeframe"] = timeframe
        keyboard = [
            [InlineKeyboardButton("📡 Сигнал", callback_data="basic")],
            [InlineKeyboardButton("📊 Умный сигнал (RSI+MACD)", callback_data="smart")]
        ]
        await query.edit_message_text(f"Пара: {context.user_data['pair']}\nТаймфрейм: {timeframe}\nВыберите тип сигнала:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data in ["basic", "smart"]:
        pair = context.user_data.get("pair", "EUR/USD")
        tf = context.user_data.get("timeframe", "M1")
        interval = "1min" if tf == "M1" else "5min" if tf == "M5" else "15min"

        if data == "basic":
            signal = get_basic_signal(pair, interval)
            signal_type = "Обычный"
            text = f"📡 Сигнал {pair} {tf}\n🟢 {signal}\n⏳ Время: 1–3 мин"
        else:
            signal = get_smart_signal(pair, tf)
            signal_type = "Умный (RSI+MACD)"
            text = f"📊 Умный сигнал (RSI+MACD)\n{pair} {tf}\n📈 {signal}\n⏳ Время: 1–3 мин"

        # Сохраняем в базу
        conn = sqlite3.connect("signals.db")
        c = conn.cursor()
        c.execute("INSERT INTO signals (pair, timeframe, signal_type, signal, timestamp) VALUES (?, ?, ?, ?, ?)",
                  (pair, tf, signal_type, signal, datetime.now().isoformat()))
        conn.commit()
        conn.close()

        await query.edit_message_text(text)

# Запуск приложения
if __name__ == "__main__":
    init_db()
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()
