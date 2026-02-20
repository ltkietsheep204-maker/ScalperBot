import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import pandas as pd
import numpy as np
import ccxt
import time
from datetime import datetime, timedelta

# Thêm thư mục hiện tại vào sys.path để import strategy
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import strategy
import config

def fetch_historical_data(exchange, symbol, timeframe, days=90):
    since = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
    all_ohlcv = []
    print(f"Đang tải dữ liệu {days} ngày trước...")
    while True:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
        if len(ohlcv) == 0:
            break
        
        # Ngăn trùng lặp nến do timestamp
        if all_ohlcv and ohlcv[0][0] == all_ohlcv[-1][0]:
            ohlcv = ohlcv[1:]
            
        all_ohlcv.extend(ohlcv)
        if len(ohlcv) < 999:
            break
        since = ohlcv[-1][0] + 1
        time.sleep(0.1)
    return all_ohlcv

def run_backtest(symbol='BTC/USDT', timeframe='15m', days=90):
    print(f"Bắt đầu tải dữ liệu {symbol} khung {timeframe} từ Binance...")
    exchange = ccxt.binance()
    
    # Fetch data
    ohlcv = fetch_historical_data(exchange, symbol, timeframe, days)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    # Tính toán tín hiệu dựa trên strategy.py
    print("Đang tính toán tín hiệu...")
    
    if len(df) < config.ATR_PERIOD:
        print("Không đủ dữ liệu")
        return
        
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['hl2'] = (df['high'] + df['low']) / 2
    
    atr_series = strategy.calculate_atr(df, config.ATR_PERIOD)
    atr = atr_series.rolling(window=config.TREND_LENGTH).max()
    
    sma = strategy.calculate_sma(df['close'], config.TREND_LENGTH)
    upper = sma + atr
    lower = sma - atr
    
    df['signal_up'] = (df['close'] > upper) & (df['close'].shift(1) <= upper.shift(1))
    df['signal_dn'] = (df['close'] < lower) & (df['close'].shift(1) >= lower.shift(1))
    
    trend = pd.Series(index=df.index, dtype=object)
    trend.loc[df['signal_up']] = True
    trend.loc[df['signal_dn']] = False
    trend = trend.ffill().infer_objects(copy=False)
    
    # Origin prices (y1 of channel line)
    trend_changed_up = (trend == True) & (trend.shift(1) == False)
    trend_changed_dn = (trend == False) & (trend.shift(1) == True)
    
    df['origin_price_up'] = np.where(trend_changed_up, df['hl2'], np.nan)
    df['origin_price_up'] = df['origin_price_up'].ffill()
    
    df['origin_price_dn'] = np.where(trend_changed_dn, df['hl2'], np.nan)
    df['origin_price_dn'] = df['origin_price_dn'].ffill()
    
    sma_20 = strategy.calculate_sma(df['hl2'], config.SMA_PERIOD)
    
    # Diamond visibility (from color_lines in indicator)
    # Green diamond visible when: origin_hl2 < sma(hl2, 20) = channel slopes UP
    # Orange diamond visible when: origin_hl2 > sma(hl2, 20) = channel slopes DOWN
    diamond_green = (trend == True) & (df['origin_price_up'] < sma_20)
    diamond_orange = (trend == False) & (df['origin_price_dn'] > sma_20)
    
    # Edge detection: enter on FIRST bar diamond becomes visible
    long_signal = diamond_green & ~diamond_green.shift(1, fill_value=False)
    short_signal = diamond_orange & ~diamond_orange.shift(1, fill_value=False)
    
    df['LONG'] = long_signal
    df['SHORT'] = short_signal
    
    # Backtest logic
    position = 0 # 1 for Long, -1 for Short
    entry_price = 0.0
    trades = []
    
    initial_capital = 10000.0
    capital = initial_capital
    order_size = 1000.0 # Trade $1000 mỗi lệnh theo yêu cầu
    fee_rate = 0.0004 # 0.04% taker fee Binance Futures
    
    for i in range(len(df)):
        current_price = df['close'].iloc[i]
        
        # Nếu có vị thế và có tín hiệu ngược lại, đóng vị thế
        if position == 1 and df['SHORT'].iloc[i]:
            # Đóng Long
            pnl = (current_price - entry_price) / entry_price * order_size
            fee = (entry_price + current_price) * (order_size / entry_price) * fee_rate
            net_pnl = pnl - fee
            capital += net_pnl
            trades.append({'type': 'LONG', 'entry': entry_price, 'exit': current_price, 'pnl': net_pnl, 'win': net_pnl > 0})
            position = 0
            
        elif position == -1 and df['LONG'].iloc[i]:
            # Đóng Short
            pnl = (entry_price - current_price) / entry_price * order_size
            fee = (entry_price + current_price) * (order_size / entry_price) * fee_rate
            net_pnl = pnl - fee
            capital += net_pnl
            trades.append({'type': 'SHORT', 'entry': entry_price, 'exit': current_price, 'pnl': net_pnl, 'win': net_pnl > 0})
            position = 0
            
        # Mở vị thế mới nếu chưa có
        if position == 0:
            if df['LONG'].iloc[i]:
                position = 1
                entry_price = current_price
            elif df['SHORT'].iloc[i]:
                position = -1
                entry_price = current_price
                
    wins = [t for t in trades if t['win']]
    losses = [t for t in trades if not t['win']]
    
    win_rate = len(wins) / len(trades) * 100 if trades else 0
    total_pnl = sum(t['pnl'] for t in trades)
    
    print("-" * 50)
    print(f"KẾT QUẢ BACKTEST: {symbol} | Khung: {timeframe} | {len(df)} nến ({days} ngày)")
    print(f"Volume mỗi lệnh: ${order_size:.2f}")
    print(f"Tổng số lệnh: {len(trades)}")
    print(f"Lệnh thắng: {len(wins)}")
    print(f"Lệnh thua: {len(losses)}")
    print(f"Tỉ lệ thắng (Win Rate): {win_rate:.2f}%")
    print(f"Tổng PNL Net (sau phí): ${total_pnl:.2f}")
    print(f"Vốn cuối cùng: ${capital:.2f} (Vốn ban đầu: ${initial_capital:.2f})")
    print("-" * 50)

if __name__ == "__main__":
    run_backtest(symbol='BTC/USDT', timeframe='15m', days=90)
    run_backtest(symbol='ETH/USDT', timeframe='15m', days=90)
