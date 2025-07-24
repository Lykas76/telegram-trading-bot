import os
import logging
import requests
import sqlite3
import pandas as pd
import mplfinance as mpf
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Загрузка переменных среды
load_dotenv()
TOKEN = os.getenv("TOKEN")
ALPHA_VANTAGE_KEY = os.getenv("ALPHA_VANTAGE_KEY")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

def fetch_price_series_alpha_vantage(symbol: str, interval: str, outputsize=50):
    interval_map = {
        "M1": "1min",
        "M5": "5min",
        "M15": "15min"
    }
    selected_interval = interval_map.get(interval, "1min")
    url = "https://www.alphavantage.co/query"
    params = {
        "function": "TIME_SERIES_INTRADAY",
        "symbol": symbol,
        "interval": selected_interval,
        "apikey": ALPHA_VANTAGE_KEY,
        "outputsize": "compact"
    }
    response = requests.get(url, params=params)
    data = response.json()
    key = f"Time Series ({selected_interval})"
    if key not in data:
        raise Exception(f"Ошибка API Alpha Vantage: {data.get('Note') or data.get('Error Message') or 'нет данных'}")
    df = pd.DataFrame.from_dict(data[key], orient="index")
    df = df.rename(columns={
        "1. open": "open",
        "2. high": "high",
        "3. low": "low",
        "4. close": "close",
        "5. volume": "volume"
    })
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    df = df.astype(float)
    return df

def calculate_rsi_macd(df):
    delta = df['close'].diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    avg_gain = gain.rolling(window=14).mean()
    avg_loss = loss.rolling(window=14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    exp1 = df['close'].ewm(span=12, adjust=False).mean()
    exp2 = df['close'].ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2

    return rsi.iloc[-1], macd.iloc[-1]

def determine_signal_strength(rsi, macd):
    if rsi < 30 and macd > 0:
        return "🟢 BUY (вверх)", "📈"
    elif rsi > 70 and macd < 0:
        return "🔴 SELL (вниз)", "📉"
    else:
        return "⚪️ Нет сигнала", "➖"

def get_trade_duration(strength):
    if "BUY" in strength or "SELL" in strength:
        return "1–3 мин"
    return "Подождите"

def draw_candlestick_chart(df, filename="chart.png", pair="PAIR", tf="M1"):
    mpf.plot(
        df.tail(30),
        type='candle',
        style='charles',
        title=f"{pair} {tf}",
        ylabel='Цена',
        savefig=dict(fname=filename, dpi=100)
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text("👋 Привет! Выбери валютную пару:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))

async def handle_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = update.message.text
    context.user_data['pair'] = pair
    keyboard = [[tf] for tf in TIMEFRAMES]
    await update.message.reply_text("⏱ Выбери таймфрейм:",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True))

async def handle_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    timeframe = update.message.text
    context.user_data['timeframe'] = timeframe
    keyboard = [["📊 Умный сигнал (RSI+MACD)"]]
    await update.message.reply_text("✅ Нажми кнопку, чтобы получить сигнал:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def handle_smart_signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pair = context.user_data.get("pair", "EUR/USD")
    timeframe = context.user_data.get("timeframe", "M1")
    symbol = pair.replace("/", "")
    try:
        df = fetch_price_series_alpha_vantage(symbol, timeframe)
        rsi, macd = calculate_rsi_macd(df)
        strength, icon = determine_signal_strength(rsi, macd)
        duration = get_trade_duration(strength)

        draw_candlestick_chart(df, filename="chart.png", pair=pair, tf=timeframe)

        with open("chart.png", "rb") as photo:
            await update.message.reply_photo(
                photo=InputFile(photo),
                caption=f"🤖 Умный сигнал {pair} {timeframe}\n{icon} {strength}\n📊 RSI: {rsi:.2f}, MACD: {macd:.4f}\n⏳ Время: {duration}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка анализа: {e}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_pair))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^(M1|M5|M15)$"), handle_timeframe))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^📊 Умный сигнал.*"), handle_smart_signal))

    print("Бот запущен")
    app.run_polling()

if __name__ == '__main__':
    main()
