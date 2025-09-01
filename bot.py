import os
import random
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.getenv("TOKEN")

# Список доступных валютных пар
PAIRS = ["EUR/USD", "GBP/USD", "AUD/JPY", "EUR/CAD"]
TIMEFRAMES = ["M1", "M5", "M15"]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сбросим сохранённые данные
    context.user_data.clear()
    # Показываем выбор пары
    keyboard = [[pair] for pair in PAIRS]
    await update.message.reply_text("Выбери валютную пару:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text in PAIRS:
        context.user_data["pair"] = text
        # Показываем таймфреймы
        keyboard = [[tf for tf in TIMEFRAMES]]
        await update.message.reply_text("Выбери таймфрейм:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    elif text in TIMEFRAMES:
        context.user_data["tf"] = text
        await update.message.reply_text("Нажми 📡 Сигнал", reply_markup=ReplyKeyboardMarkup([["📡 Сигнал"]], resize_keyboard=True))

    elif text == "📡 Сигнал":
        pair = context.user_data.get("pair", "EUR/USD")
        tf = context.user_data.get("tf", "M5")
        direction = random.choice(["BUY", "SELL"])
        emoji = "🟢" if direction == "BUY" else "🔴"
        arrow = "вверх" if direction == "BUY" else "вниз"

        await update.message.reply_text(
            f"🔔 Сигнал {pair} {tf}\n{emoji} {direction} ({arrow})\n⏳ Время: 1–3 мин"
        )

        # После сигнала снова предлагаем выбрать валюту
        keyboard = [[pair] for pair in PAIRS]
        await update.message.reply_text("Выбери валютную пару:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

    else:
        await update.message.reply_text("Пожалуйста, выбери валютную пару или таймфрейм.")


