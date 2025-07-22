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

# --- RSI + MACD умный сигнал ---
def get_smart_signal(pair: str, timeframe: str) -> dict:
    tf_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min"
    }
    interval = tf_map.get(timeframe, "5min")
    symbol = pair

    try:
        # RSI
        rsi_url = f"https://api.twelvedata.com/rsi?symbol={symbol}&interval={interval}&apikey={API_KEY}&outputsize=1"
        rsi = float(requests.get(rsi_url).json()["values"][0]["rsi"])

        # MACD
        macd_url = f"https://api.twelvedata.com/macd?symbol={symbol}&interval={interval}&apikey={API_KEY}&outputsize=1"
        macd_data = requests.get(macd_url).json()["values"][0]
        macd = float(macd_data["macd"])
        signal = float(macd_data["signal"])

        # Интерпретация
        if rsi < 30 and macd > signal:
            action = "🟢 BUY (вверх)"
        elif rsi > 70 and macd < signal:
            action = "🔴 SELL (вниз)"
        else:
            action = "⚪️ Нет сигнала"

        return {
            "action": action,
            "rsi": rsi,
            "macd": macd,
            "macd_signal": signal
        }

    except Exception as e:
        return {"action": f"⚠️ Ошибка анализа: {e}", "rsi": 0, "macd": 0, "macd_signal": 0}

# --- Сохранение в базу ---
def save_signal_to_db(pair, tf, rsi, macd, macd_signal, action):
    conn = sqlite3.connect("signals.db")
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pair TEXT,
        timeframe TEXT,
        rsi REAL,
        macd REAL,
        signal REAL,
        action TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    c.execute("INSERT INTO signals (pair, timeframe, rsi, macd, signal, action) VALUES (?, ?, ?, ?, ?, ?)",
              (pair, tf, rsi, macd, macd_signal, action))
    conn.commit()
    conn.close()

# --- Команда /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text(
        "👋 Привет! Выбери валютную пару:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# --- Обработка сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    print(f"👤 chat_id пользователя: {update.effective_chat.id}")  # ← Вывод chat_id

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
        keyboard = [["📡 Сигнал", "📊 Умный сигнал (RSI+MACD)"], ["🔄 Валюта"]]
        await update.message.reply_text(
            f"Выбран таймфрейм: {text}",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    if text == "📊 Умный сигнал (RSI+MACD)":
        pair = context.user_data.get("pair")
        tf = context.user_data.get("tf")
        if pair and tf:
            result = get_smart_signal(pair, tf)
            save_signal_to_db(pair, tf, result["rsi"], result["macd"], result["macd_signal"], result["action"])
            await update.message.reply_text(
                f"🤖 Умный сигнал {pair} {tf}\n{result['action']}\n📊 RSI: {result['rsi']:.1f}, MACD: {result['macd']:.4f}\n⏳ Время: 1–3 мин"
            )
        else:
            await update.message.reply_text("Сначала выбери валюту и таймфрейм.")
        return

    if text == "📡 Сигнал":
        await update.message.reply_text("⚠️ Эта функция пока не подключена.")
        return

    if text == "🔄 Валюта":
        context.user_data.clear()
        keyboard = [[pair] for pair in PAIRS]
        await update.message.reply_text(
            "Выбери валютную пару заново:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        return

    await update.message.reply_text("Выбери действие с клавиатуры.")

# --- Запуск бота ---
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("✅ Бот запущен")
    app.run_polling()

if __name__ == "__main__":
    main()

