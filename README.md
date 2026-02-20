# Telegram Crypto Futures Bot

Tool giao dịch Crypto Futures tự động qua Telegram dựa trên chiến lược Future Trend Channel.

## Setup
1. Đảm bảo Python 3.9+ đã được cài đặt.
2. Cài đặt các thư viện:
   ```bash
   pip install -r requirements.txt
   ```
3. Chạy bot:
   ```bash
   python bot.py
   ```

## Thay đổi Bot Token
Nếu bạn muốn đổi bot token, thay đổi hằng số `TELEGRAM_BOT_TOKEN` trong file `config.py`.

## Cấu trúc thư mục
- `bot.py`: Quản lý giao diện Telegram và các handlers.
- `database.py`: Lưu trữ người dùng, API keys, và vị thế trong SQLite.
- `scanner.py`: Background task quét giá và phát tín hiệu.
- `trade_manager.py`: Thực hiện lệnh trade qua API của các sàn.
- `strategy.py`: Logic của chiến lược Future Trend Channel.
- `exchanges/`: Các adapter kết nối với Binance, BingX, Bybit, MEXC, và OKX.
