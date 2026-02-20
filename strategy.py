import pandas as pd
import numpy as np
import config

pd.set_option('future.no_silent_downcasting', True)

def calculate_sma(series, length):
    return series.rolling(window=length).mean()

def calculate_atr(df, period):
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = np.max(ranges, axis=1)
    
    # Calculate RMA (Running Moving Average) as equivalent to TradingView's ta.rma
    rma = true_range.ewm(alpha=1/period, adjust=False).mean()
    return rma
    
def calculate_signal(df):
    """
    Calculate Future Trend Channel signal based on the Pine Script strategy.
    
    df columns: [timestamp, open, high, low, close, volume]
    Returns: 'LONG', 'SHORT', or 'HOLD'
    """
    if len(df) < config.ATR_PERIOD:
         return 'HOLD'
         
    # Ensure pandas DataFrame with correct types
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['close'] = df['close'].astype(float)
    df['hl2'] = (df['high'] + df['low']) / 2
    
    # 1. atr = ta.highest(ta.atr(200), 100)
    atr_series = calculate_atr(df, config.ATR_PERIOD)
    atr = atr_series.rolling(window=config.TREND_LENGTH).max()
    
    # 2. sma = ta.sma(close, length)
    sma = calculate_sma(df['close'], config.TREND_LENGTH)
    upper = sma + atr
    lower = sma - atr
    
    # 3. Trend calculation
    # trend() =>  signal_up = ta.crossover(close, upper) ; signal_dn = ta.crossunder(close, lower)
    df['signal_up'] = (df['close'] > upper) & (df['close'].shift(1) <= upper.shift(1))
    df['signal_dn'] = (df['close'] < lower) & (df['close'].shift(1) >= lower.shift(1))
    
    # Forward fill trend
    trend = pd.Series(index=df.index, dtype=object)
    trend.loc[df['signal_up']] = True
    trend.loc[df['signal_dn']] = False
    trend = trend.ffill().infer_objects(copy=False)
    
    # 4. Origin prices (hl2 at trend change = y1 of the channel line)
    trend_changed_up = (trend == True) & (trend.shift(1) == False)
    trend_changed_dn = (trend == False) & (trend.shift(1) == True)
    
    df['origin_price_up'] = np.where(trend_changed_up, df['hl2'], np.nan)
    df['origin_price_up'] = df['origin_price_up'].ffill()
    
    df['origin_price_dn'] = np.where(trend_changed_dn, df['hl2'], np.nan)
    df['origin_price_dn'] = df['origin_price_dn'].ffill()
    
    # 5. sma_20 = ta.sma(hl2, 20) = y2 of the channel line (updated every bar)
    sma_20 = calculate_sma(df['hl2'], config.SMA_PERIOD)
    
    # 6. DIAMOND VISIBILITY (from color_lines() in indicator)
    # color_lines sets diamond to 100% transparent when channel is GRAY
    # Diamond VISIBLE = channel has COLOR:
    #   Green diamond: y1 <= y2 → origin_hl2 <= sma(hl2, 20) → channel slopes UP
    #   Orange diamond: y1 >= y2 → origin_hl2 >= sma(hl2, 20) → channel slopes DOWN
    
    diamond_green_visible = (trend == True) & (df['origin_price_up'] < sma_20)
    diamond_orange_visible = (trend == False) & (df['origin_price_dn'] > sma_20)
    
    # Check current bar
    if len(df) < 2:
        return 'HOLD'
    
    current_green = bool(diamond_green_visible.iloc[-1]) if not pd.isna(diamond_green_visible.iloc[-1]) else False
    current_orange = bool(diamond_orange_visible.iloc[-1]) if not pd.isna(diamond_orange_visible.iloc[-1]) else False
    
    if current_green:
        return 'LONG'
    elif current_orange:
        return 'SHORT'
    else:
        return 'HOLD'

# For testing
if __name__ == "__main__":
    print("Testing Strategy Calculation logic...")
    # create dummy data
    data = {'timestamp': range(300), 'open': np.random.rand(300)*10+100,
            'high': np.random.rand(300)*10+105, 'low': np.random.rand(300)*10+95,
            'close': np.random.rand(300)*10+100, 'volume': np.random.rand(300)*1000}
    df = pd.DataFrame(data)
    signal = calculate_signal(df)
    print(f"Test Signal: {signal}")
