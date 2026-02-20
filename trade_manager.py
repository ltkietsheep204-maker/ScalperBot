import logging
import database

logger = logging.getLogger(__name__)

async def process_signal(user_id, symbol, signal, user_exchanges):
    """
    Process a new signal (LONG/SHORT) for a user.
    Executes trades on all enabled exchanges and sets up TP/SL tracking in DB.
    """
    if not user_exchanges:
        return
        
    trading_config = await database.get_trading_config(user_id)
    if not trading_config:
        return
        
    leverage = trading_config['leverage']
    margin_qty = trading_config['margin_qty']
    margin_mode = trading_config['margin_mode']
    tp_percent = trading_config['tp_percent']
    sl_percent = trading_config['sl_percent']
    
    for ex_name, exchange in user_exchanges:
        try:
             # Calculate position size based on current price
             # For simplicity we fetch current ticker or just use the margin_qty as order size depending on exchange
             # Usually in CCXT, quantity is in base currency (e.g., BTC for BTC/USDT)
             # So we need to convert USDT margin_qty -> base_ccy qty using current price
             
             # Fetch a quick kline to get latest close price
             klines = await exchange.get_klines(symbol, "1m", limit=1)
             if not klines: continue
             current_price = float(klines[0][4])
             
             # Example quantity calculation: (margin_qty * leverage) / current_price
             # BingX might behave differently, but CCXT handles standardization mostly
             quantity = (margin_qty * leverage) / current_price
             
             # IMPORTANT format adjustment based on exchange min quantities might be required here
             # For demo purposes, we will assume quantity is ok
             
             order = await exchange.open_position(symbol, signal, quantity, leverage, margin_mode)
             if order:
                  # Estimate entry price (or use actual if order returned it)
                  entry_price = float(order.get('average', order.get('price', current_price)))
                  order_id = order.get('id', 'unknown')
                  
                  # Calculate TP / SL Prices
                  if signal == 'LONG':
                       tp_price = entry_price * (1 + (tp_percent / 100))
                       sl_price = entry_price * (1 - (sl_percent / 100))
                  else:
                       tp_price = entry_price * (1 - (tp_percent / 100))
                       sl_price = entry_price * (1 + (sl_percent / 100))
                       
                  await database.add_open_position(user_id, ex_name, symbol, signal, entry_price, quantity, tp_price, sl_price, order_id)
                  logger.info(f"User {user_id} Auto-traded {symbol} {signal} on {ex_name}")
                  
             await exchange.close_connection()
                  
        except Exception as e:
             logger.error(f"Error executing auto-trade on {ex_name} for user {user_id}: {e}")
