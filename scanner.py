import asyncio
import logging
from telegram.ext import Application
import pandas as pd

import config
import database
from strategy import calculate_signal
from exchanges import get_exchange_instance
from trade_manager import process_signal

logger = logging.getLogger(__name__)

# Cache to store last known signals to prevent duplicate alerts
# Format: {(user_id, symbol, timeframe): 'LONG'}
last_signals = {}

async def scan_pair(user_id, symbol, timeframe, is_auto_trade, tg_application: Application, user_exchanges=None):
    anonymous_binance = None
    try:
         anonymous_binance = get_exchange_instance("Binance", "", "")
         if not anonymous_binance:
             return
         
         limit = max(config.ATR_PERIOD + config.TREND_LENGTH, 300)
         
         klines = await anonymous_binance.get_klines(symbol, timeframe, limit=limit)
         
         if not klines or len(klines) < config.ATR_PERIOD:
             return
             
         df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])  # type: ignore[arg-type]
         
         signal = calculate_signal(df)
         
         cache_key = (user_id, symbol, timeframe)
         last_signal = last_signals.get(cache_key)
         
         if signal != 'HOLD' and signal != last_signal:
             # NEW SIGNAL!
             last_signals[cache_key] = signal
             
             DIVIDER = "━" * 28
             if signal == "LONG":
                 signal_icon = "🟢"
                 signal_label = "LONG  ↑"
             else:
                 signal_icon = "🔴"
                 signal_label = "SHORT  ↓"
                 
             message = (
                 f"{signal_icon} *TÍN HIỆU MỚI* {signal_icon}\n"
                 f"{DIVIDER}\n"
                 f"💱  Cặp:    `{symbol.split('/')[0]}`\n"
                 f"⏱  Khung:   `{timeframe}`\n"
                 f"📊  Lệnh:   *{signal_label}*\n"
                 f"{DIVIDER}\n"
             )
                        
             if is_auto_trade:
                 message += "⚙️ _Bot đang tự động mở lệnh..._"
                 await tg_application.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
                 # Trigger auto trade
                 await process_signal(user_id, symbol, signal, user_exchanges)
             else:
                 message += "📌 _Auto‑trade TẮT · Hãy tự vào lệnh!_"
                 await tg_application.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
                 
    except Exception as e:
         logger.error(f"Error scanning {symbol} on {timeframe} for {user_id}: {e}")
    finally:
         if anonymous_binance:
             try:
                 await anonymous_binance.close_connection()
             except Exception:
                 pass

async def scanner_task(tg_application: Application):
    """Background task that runs periodically to fetch data and look for signals"""
    
    while True:
        try:
             # Get all watched pairs
             pairs = await database.get_all_watched_pairs()
             
             if pairs:
                  # Group by user_id to optimize exchange instance creation
                  user_pairs = {}
                  for row in pairs:
                       uid = row['user_id']
                       if uid not in user_pairs:
                            user_pairs[uid] = []
                       user_pairs[uid].append(row)
                       
                  for user_id, user_watched_list in user_pairs.items():
                       # check if auto trade is enabled
                       trading_config = await database.get_trading_config(user_id)
                       if not trading_config: continue
                       
                       is_auto_trade = trading_config['auto_trade_enabled']
                       
                       # get their exchanges only once if auto trade is on
                       user_exchanges = []
                       if is_auto_trade:
                            apis = await database.get_exchange_apis(user_id)
                            for api in apis:
                                 if api['is_enabled']:
                                       ex = get_exchange_instance(api['exchange_name'], api['api_key'], api['api_secret'], api['passphrase'])
                                       if ex: user_exchanges.append((str(api['exchange_name']), ex))
                       
                       try:
                            for w_pair in user_watched_list:
                                 symbol = w_pair['symbol']
                                 timeframe = w_pair['timeframe']
                                 
                                 await scan_pair(user_id, symbol, timeframe, is_auto_trade, tg_application, user_exchanges)
                                 await asyncio.sleep(0.5) # rate limiting
                       finally:
                            for _, ex in user_exchanges:
                                try:
                                    await ex.close_connection()
                                except Exception:
                                    pass
                            
        except Exception as e:
             logger.error(f"Scanner task global error: {e}")
             
        await asyncio.sleep(config.SCANNER_INTERVAL)
