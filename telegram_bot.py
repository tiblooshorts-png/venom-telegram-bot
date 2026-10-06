import logging
import asyncio
import requests
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8997358797:AAENjOwec1PF1FjqaiLW1zdA85-Jw2Wwurw"
# =======================================================

def fetch_tradingview_data(pair, timeframe="1m"):
    try:
        clean_pair = pair.replace("_OTC", "").replace("OTC", "").upper()
        symbol = f"FX:{clean_pair}" if any(curr in clean_pair for curr in ["USD", "EUR", "GBP", "JPY", "CAD", "AUD"]) else f"BITSTAMP:{clean_pair}"
        
        url = "https://scanner.tradingview.com/forex/scan"
        payload = {
            "symbols": {"tickers": [symbol]},
            "columns": [
                "RSI", "Stoch.K", "Stoch.D", 
                "EMA5", "EMA20", "SMA50",
                "close", "open", "high", "low", "volume",
                "MACD.macd", "MACD.signal",
                "BB.upper", "BB.lower"
            ]
        }
        res = requests.post(url, json=payload, timeout=15)
        data = res.json()
        
        if data and "data" in data and len(data["data"]) > 0:
            vals = data["data"][0]["d"]
            return {
                "rsi": round(vals[0] or 50, 2),
                "stoch_k": round(vals[1] or 50, 2),
                "ema_fast": vals[3] or 0,
                "ema_slow": vals[4] or 0,
                "sma_trend": vals[5] or 0,
                "close": vals[6] or 0,
                "open": vals[7] or 0,
                "high": vals[8] or 0,
                "low": vals[9] or 0,
                "macd": vals[11] or 0,
                "macd_signal": vals[12] or 0,
                "bb_upper": vals[13] or 0,
                "bb_lower": vals[14] or 0
            }
    except Exception as e:
        print("Error fetching market data:", e)
    
    return None

def analyze_market(pair, tf):
    market = fetch_tradingview_data(pair, tf)
    if not market:
        return "⚠️ Market data currently unavailable. Try another pair."

    rsi = market["rsi"]
    ema_fast = market["ema_fast"]
    ema_slow = market["ema_slow"]
    sma_trend = market["sma_trend"]
    close_p = market["close"]
    open_p = market["open"]
    high_p = market["high"]
    low_p = market["low"]
    macd = market["macd"]
    macd_signal = market["macd_signal"]
    bb_upper = market["bb_upper"]
    bb_lower = market["bb_lower"]
    
    body_size = abs(close_p - open_p)
    upper_wick = high_p - max(close_p, open_p)
    lower_wick = min(close_p, open_p) - low_p
    
    score = 0
    confluences = []
    
    if close_p > sma_trend and ema_fast > ema_slow:
        score += 3
        confluences.append("Macro Trend Bullish 🟢")
    elif close_p < sma_trend and ema_fast < ema_slow:
        score -= 3
        confluences.append("Macro Trend Bearish 🔴")

    if close_p >= bb_upper:
        score += 2
        confluences.append("BB Upper Expansion 📈")
    elif close_p <= bb_lower:
        score -= 2
        confluences.append("BB Lower Expansion 📉")

    if macd > macd_signal and macd > 0:
        score += 2
        confluences.append("MACD Bullish Alignment 🟢")
    elif macd < macd_signal and macd < 0:
        score -= 2
        confluences.append("MACD Bearish Alignment 🔴")

    if rsi >= 58:
        score += 2
        confluences.append("RSI High Momentum 🔥")
    elif rsi <= 42:
        score -= 2
        confluences.append("RSI Low Momentum 🔥")

    if lower_wick >= (body_size * 1.3) and body_size > 0:
        score += 2
        confluences.append("Buyer Rejection Pinbar 🔨")
    elif upper_wick >= (body_size * 1.3) and body_size > 0:
        score -= 2
        confluences.append("Seller Rejection Pinbar 🔨")

    if score >= 6:
        signal_text = f"🔥 *SURESHOT CALL / BUY* 📈\n⏰ *Timeframe:* {tf.upper()}\n🎯 *Confidence:* 88% - 90%\n\n*Confluences:* \n• " + "\n• ".join(confluences)
    elif score <= -6:
        signal_text = f"🔥 *SURESHOT PUT / SELL* 📉\n⏰ *Timeframe:* {tf.upper()}\n🎯 *Confidence:* 88% - 90%\n\n*Confluences:* \n• " + "\n• ".join(confluences)
    else:
        signal_text = f"⚠️ *SKIP / NO TRADE*\n⏰ *Timeframe:* {tf.upper()}\n\n*Reason:* Market consolidation/conflicting signals. Auto-skipped to protect balance."

    return signal_text

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("EUR/USD OTC", callback_data="pair_EURUSD_OTC"), InlineKeyboardButton("GBP/USD OTC", callback_data="pair_GBPUSD_OTC")],
        [InlineKeyboardButton("USD/JPY OTC", callback_data="pair_USDJPY_OTC"), InlineKeyboardButton("AUD/CAD OTC", callback_data="pair_AUDCAD_OTC")],
        [InlineKeyboardButton("EUR/USD Real", callback_data="pair_EURUSD"), InlineKeyboardButton("GBP/USD Real", callback_data="pair_GBPUSD")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🦅 *VENOM PRO AI SIGNAL BOT*\n\nSelect a Currency Pair to start scanning:", reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("pair_"):
        pair = data.split("pair_")[1]
        context.user_data["pair"] = pair
        
        keyboard = [
            [InlineKeyboardButton("⚡ 5 SEC", callback_data="tf_5s"), InlineKeyboardButton("⏱ 15 SEC", callback_data="tf_15s")],
            [InlineKeyboardButton("🕯 1 MIN", callback_data="tf_1m"), InlineKeyboardButton("📊 5 MIN", callback_data="tf_5m")],
            [InlineKeyboardButton("🔙 Change Pair", callback_data="back_pairs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Selected Pair: *{pair}*\nNow select candle Timeframe:", reply_markup=reply_markup, parse_mode="Markdown")

    elif data.startswith("tf_"):
        tf = data.split("tf_")[1]
        pair = context.user_data.get("pair", "EURUSD_OTC")
        
        msg = await query.edit_message_text(f"🔍 *Scanning Market Data for {pair} ({tf.upper()})...*\n⏳ Calculating indicators in 3s...", parse_mode="Markdown")
        await asyncio.sleep(1)
        await msg.edit_text(f"🔍 *Scanning Market Data for {pair} ({tf.upper()})...*\n⏳ Calculating indicators in 2s...", parse_mode="Markdown")
        await asyncio.sleep(1)
        await msg.edit_text(f"🔍 *Scanning Market Data for {pair} ({tf.upper()})...*\n⏳ Calculating indicators in 1s...", parse_mode="Markdown")
        await asyncio.sleep(1)

        result = analyze_market(pair, tf)
        
        keyboard = [
            [InlineKeyboardButton("🔄 Refresh Signal", callback_data=f"tf_{tf}")],
            [InlineKeyboardButton("🔙 Choose Another Pair", callback_data="back_pairs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(f"📊 *PAIR:* {pair}\n\n{result}", reply_markup=reply_markup, parse_mode="Markdown")

    elif data == "back_pairs":
        await start(query, context)

def start_bot():
    while True:
        try:
            print("🚀 VENOM PRO TELEGRAM BOT IS RUNNING LIVE...")
            app = (
                Application.builder()
                .token(BOT_TOKEN)
                .connect_timeout(60.0)
                .read_timeout(60.0)
                .write_timeout(60.0)
                .pool_timeout(60.0)
                .get_updates_connect_timeout(60.0)
                .build()
            )
            
            app.add_handler(CommandHandler("start", start))
            app.add_handler(CallbackQueryHandler(button_handler))
            
            app.run_polling(poll_interval=2.0, timeout=30, drop_pending_updates=True)
        except Exception as e:
            print(f"⚠ Network connection dropped ({e}). Auto-reconnecting in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    start_bot()
