import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r'c:\Users\Administrator\Desktop\SCALPVER')

import pandas as pd
import numpy as np
import ccxt
from datetime import datetime, timedelta
import time
import strategy
import config

pd.set_option('future.no_silent_downcasting', True)

exchange = ccxt.binance()

# Fetch 60 days of 30m data (to cover from Jan 1)
since = int(datetime(2026, 1, 1).timestamp() * 1000)
all_ohlcv = []
print("Loading BTC/USDT 30m from Jan 1...")
s = since
while True:
    ohlcv = exchange.fetch_ohlcv("BTC/USDT", "30m", since=s, limit=1000)
    if len(ohlcv) == 0:
        break
    all_ohlcv.extend(ohlcv)
    if len(ohlcv) < 999:
        break
    s = ohlcv[-1][0] + 1
    time.sleep(0.1)

df = pd.DataFrame(all_ohlcv, columns=['timestamp','open','high','low','close','volume'])
df['high'] = df['high'].astype(float)
df['low'] = df['low'].astype(float)
df['close'] = df['close'].astype(float)
df['hl2'] = (df['high'] + df['low']) / 2

# Need more historical data for SMA(100) warmup
since_warmup = int(datetime(2025, 10, 1).timestamp() * 1000)
warmup_ohlcv = []
s = since_warmup
while True:
    ohlcv = exchange.fetch_ohlcv("BTC/USDT", "30m", since=s, limit=1000)
    if len(ohlcv) == 0:
        break
    warmup_ohlcv.extend(ohlcv)
    if len(ohlcv) < 999:
        break
    s = ohlcv[-1][0] + 1
    time.sleep(0.1)

df_full = pd.DataFrame(warmup_ohlcv, columns=['timestamp','open','high','low','close','volume'])
df_full['high'] = df_full['high'].astype(float)
df_full['low'] = df_full['low'].astype(float)
df_full['close'] = df_full['close'].astype(float)
df_full['hl2'] = (df_full['high'] + df_full['low']) / 2

# Calculate trend
atr_s = strategy.calculate_atr(df_full, config.ATR_PERIOD)
atr = atr_s.rolling(window=config.TREND_LENGTH).max()
sma = strategy.calculate_sma(df_full['close'], config.TREND_LENGTH)
upper = sma + atr
lower = sma - atr

df_full['signal_up'] = (df_full['close'] > upper) & (df_full['close'].shift(1) <= upper.shift(1))
df_full['signal_dn'] = (df_full['close'] < lower) & (df_full['close'].shift(1) >= lower.shift(1))

trend = pd.Series(index=df_full.index, dtype=object)
trend.loc[df_full['signal_up']] = True
trend.loc[df_full['signal_dn']] = False
trend = trend.ffill().infer_objects(copy=False)

up = (trend == True) & (trend.shift(1) == False)
dn = (trend == False) & (trend.shift(1) == True)

# Filter only from Jan 1 2026
jan1_ts = int(datetime(2026, 1, 1).timestamp() * 1000)
mask = df_full['timestamp'] >= jan1_ts

print(f"\n=== TU 1/1/2026 DEN NAY ===")
print(f"Tong so nen 30m: {mask.sum()}")
print(f"Hinh thoi XANH (trend up): {up[mask].sum()}")
print(f"Hinh thoi CAM (trend dn): {dn[mask].sum()}")
print(f"TONG SO HINH THOI: {up[mask].sum() + dn[mask].sum()}")

# List each diamond with date
print(f"\nChi tiet tung hinh thoi:")
for idx in df_full[mask & (up | dn)].index:
    ts = pd.to_datetime(df_full.loc[idx, 'timestamp'], unit='ms')
    direction = "XANH (Long)" if up[idx] else "CAM (Short)"
    price = df_full.loc[idx, 'close']
    print(f"  {ts} | {direction} | Close: {price:.2f}")
