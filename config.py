import os

# ══════════════════════════════════════════════════════
#  config.py  —  Cấu hình Bot
#  Đặt token và các thông số tại đây trước khi chạy.
# ══════════════════════════════════════════════════════

# Telegram Bot Token — lấy từ @BotFather
# Có thể đặt thẳng ở đây HOẶC dùng biến môi trường TELEGRAM_BOT_TOKEN
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")

# Project root directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bot_database.sqlite')

# Supported Exchanges
SUPPORTED_EXCHANGES = ["Binance", "BingX", "Bybit", "MEXC", "OKX"]

# Supported Timeframes
SUPPORTED_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w"]

# Timeframe to minutes mapping (for logic)
TIMEFRAME_MINUTES = {
    "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
    "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480, "12h": 720,
    "1d": 1440, "3d": 4320, "1w": 10080
}

# Future Trend Channel Default Strategy Parameters
TREND_LENGTH = 100
CHANNEL_WIDTH = 3.0
ATR_PERIOD = 200
SMA_PERIOD = 20

# Scanner interval (seconds)
SCANNER_INTERVAL = 30

# Popular trading pairs for quick selection
POPULAR_PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "BNB/USDT:USDT",
    "XRP/USDT:USDT",
    "DOGE/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "DOT/USDT:USDT",
    "LINK/USDT:USDT",
    "MATIC/USDT:USDT",
    "UNI/USDT:USDT",
    "LTC/USDT:USDT",
    "ATOM/USDT:USDT",
    "FIL/USDT:USDT",
    "ARB/USDT:USDT",
    "OP/USDT:USDT",
    "APT/USDT:USDT",
    "SUI/USDT:USDT",
    "PEPE/USDT:USDT",
]
