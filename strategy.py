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
    
    # 4. draw_channel origin prices
    # if trend and not trend[1]: origin_price_up = hl2
    # if not trend and trend[1]: origin_price_dn = hl2
    trend_changed_up = (trend == True) & (trend.shift(1) == False)
    trend_changed_dn = (trend == False) & (trend.shift(1) == True)
    
    df['origin_price_up'] = np.where(trend_changed_up, df['hl2'], np.nan)
    df['origin_price_up'] = df['origin_price_up'].ffill()
    
    df['origin_price_dn'] = np.where(trend_changed_dn, df['hl2'], np.nan)
    df['origin_price_dn'] = df['origin_price_dn'].ffill()
    
    # 5. sma_20 = ta.sma(hl2, 20)
    sma_20 = calculate_sma(df['hl2'], config.SMA_PERIOD)
    
    # 6. Check for solid color WITH gray zone filter
    # Matching logic from "logic strategy.md":
    #   var float true_y1 = na
    #   if ta.change(trend) or na(true_y1)
    #       true_y1 := hl2          // y1 = điểm neo khi trend thay đổi
    #   float true_y2 = ta.sma(hl2, 20)  // y2 = SMA(20) của hl2
    #   bool is_gray = trend ? (true_y1 >= true_y2) : (true_y1 <= true_y2)
    
    # true_y1: hl2 tại thời điểm trend thay đổi
    trend_changed = trend != trend.shift(1)
    df['true_y1'] = np.where(trend_changed, df['hl2'], np.nan)
    df['true_y1'] = df['true_y1'].ffill()
    
    # true_y2: ta.sma(hl2, 20)
    true_y2 = sma_20
    
    # is_gray: Vùng xám (kênh nét đứt, KHÔNG được giao dịch)
    is_gray = np.where(trend == True, df['true_y1'] >= true_y2, df['true_y1'] <= true_y2)
    is_gray = pd.Series(is_gray, index=df.index).astype(bool)
    
    # is_colored: ngược lại vùng xám = vùng có MÀU (xanh hoặc cam)
    is_colored = ~is_gray
    
    # ĐẾM SỐ NẾN LIÊN TỤC CÓ MÀU (không phải xám)
    # Để xác nhận vùng màu đã ổn định, tránh vào lệnh ở đầu dải xám
    colored_streak = pd.Series(0, index=df.index, dtype=int)
    for i in range(1, len(df)):
        if is_colored.iloc[i]:
            colored_streak.iloc[i] = colored_streak.iloc[i-1] + 1
        else:
            colored_streak.iloc[i] = 0
    
    # Chỉ cho phép giao dịch khi vùng màu đã xác nhận ít nhất 3 nến liên tiếp
    # Điều này ngăn bot vào lệnh ở đầu dải xám (khi nó mới chớp màu 1-2 nến)
    MIN_COLORED_BARS = 3
    is_confirmed_color = colored_streak >= MIN_COLORED_BARS
    
    # Final signals
    is_green = (trend == True) & (df['origin_price_up'] < sma_20) & is_confirmed_color
    is_orange = (trend == False) & (df['origin_price_dn'] > sma_20) & is_confirmed_color
    
    current_is_green = bool(is_green.iloc[-1]) if len(is_green) > 0 else False
    current_is_orange = bool(is_orange.iloc[-1]) if len(is_orange) > 0 else False
    
    if current_is_green:
        return 'LONG'
    elif current_is_orange:
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
