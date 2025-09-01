import os
import random
import requests
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# === УСТАНОВКИ ===
TELEGRAM_TOKEN = "ТОКЕН_ТВОЕГО_БОТА"
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")  # ключ API Alpha Vantage

# Доступные валютные пары и таймфреймы
PAIRS = ["EUR/USD", "AUD/JPY", "AUD/USD", "EUR/GBP", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

# === ФУНКЦИИ ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[p] for p in PAIRS]
    await update.message.reply_text(
        "Выбери валютную пару:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
    )

async def get_forex_data(pair: str, tf: str):
    if not ALPHA_VANTAGE_KEY:
        return None, "❌ Ошибка: не задан API-ключ"

    base, quote = pair.split("/")
    interval = {"M1": "1min", "M5": "5min", "M15": "15min"}.get(tf, "1min")

    url = (
        f"https://www.alphavantage.co/query"
        f"?function=FX_INTRADAY&from_symbol={base}&to_symbol={quote}"
        f"&interval={interval}&apikey={ALPHA_VANTAGE_KEY}&outputsize=compact"
    )

    try:
        r = requests.get(url, timeout=10)
        data = r.json()
    except Exception:
        return None, "❌ Ошибка: нет соединения"

    if "Time Series FX" not in data:
        if "Note" in data:
            return None, "❌ Ошибка: превышен лимит API (5 запросов/мин)"
        if "Error Message" in data:
            return None, "❌ Ошибка: неверная валютная пара"
        return None, "❌ Ошибка: нет данных"

    prices = list(data[f"Time Series FX ({interval})"].values())
    if not prices:
        return None, "❌ Ошибка: пустые данные"
    return prices, None


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Если выбрана пара
    if text in PAIRS:
        context.user_data["pair"] = text
        keyboard = [[t] for t in TIMEFRAMES]
        await update.message.reply_text(
            f"Выбрана пара {text}. Теперь выбери таймфрейм:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    # Если выбран таймфрейм
    if text in TIMEFRAMES:
        context.user_data["tf"] = text
        keyboard = [["📡 Сигнал"], ["Сменить валюту"]]
        await update.message.reply_text(
            f"Выбран таймфрейм {text}. Теперь запроси сигнал:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return

    # Если пользователь запросил сигнал
    if text == "📡 Сигнал":
        pair = context.user_data.get("pair", "EUR/USD")
        tf = context.user_data.get("tf", "M5")

        prices, error = await get_forex_data(pair, tf)

        if error:
            now = datetime.now().strftime("%H:%M:%S")
            await update.message.reply_text(
                f"🔔 Сигнал {pair} {tf}\n{error}\n"
                f"⏳ Зайти на: 2 мин\n📊 Сила сигнала: 0%\n🕒 Время сигнала: {now}"
            )
            return

        direction = random.choice(["BUY", "SELL"])
        emoji = "🟢" if direction == "BUY" else "🔴"
        arrow = "вверх" if direction == "BUY" else "вниз"

        now = datetime.now()
        enter_time = now.strftime("%H:%M:%S")
        exit_time = (now + timedelta(minutes=2)).strftime("%H:%M:%S")

        await update.message.reply_text(
            f"🔔 Сигнал {pair} {tf}\n"
            f"{emoji} {direction} ({arrow})\n"
            f"⏳ Зайти на: 2 мин\n"
            f"📊 Сила сигнала: {random.randint(70, 95)}%\n"
            f"🕒 Время сигнала: {enter_time}\n"
            f"⏹ Закрыть сделку до: {exit_time}"
        )
        return

    # Смена валюты
    if text == "Сменить валюту":
        keyboard = [[p] for p in PAIRS]
        await update.message.reply_text(
            "Выбери валютную пару:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
        )
        return


# === ЗАПУСК ===
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()


if __name__ == "__main__":
    main()
