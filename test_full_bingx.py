"""
╔══════════════════════════════════════════════════════╗
║  TEST FULL BINGX  —  ScalperBot Function Test       ║
║  Test toàn bộ chức năng bot trên sàn BingX           ║
╚══════════════════════════════════════════════════════╝

Chạy:
    python test_full_bingx.py                # Full test (mở + đóng lệnh thật)
    python test_full_bingx.py --dry-run      # Chỉ test kết nối + tín hiệu, KHÔNG mở lệnh

Biến môi trường cần thiết:
    BINGX_API_KEY       API Key từ BingX
    BINGX_API_SECRET    API Secret từ BingX

Hoặc bạn có thể nhập trực tiếp khi chạy script.
"""

import asyncio
import os
import sys
import time
import traceback
import pandas as pd

# ── Thêm project root vào path ──────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exchanges.bingx_exchange import BingxExchange
from strategy import calculate_signal
import database
import config

# ══════════════════════════════════════════════════════
#  CẤU HÌNH TEST
# ══════════════════════════════════════════════════════

TEST_SYMBOL = "BTC/USDT:USDT"       # Cặp giao dịch test
TEST_TIMEFRAME = "5m"                 # Khung thời gian
TEST_LEVERAGE = 5                     # Đòn bẩy
TEST_MARGIN_USDT = 5.0                # Ký quỹ (USDT) — rất nhỏ để an toàn
TEST_MARGIN_MODE = "isolated"         # Chế độ margin
TEST_USER_ID = 999999999              # User ID giả cho test database
KLINE_LIMIT = 300                     # Số nến cần lấy

# ══════════════════════════════════════════════════════
#  HELPERS
# ══════════════════════════════════════════════════════

class Colors:
    """ANSI color codes cho terminal output"""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

C = Colors

PASS = f"{C.GREEN}✅ PASS{C.RESET}"
FAIL = f"{C.RED}❌ FAIL{C.RESET}"
SKIP = f"{C.YELLOW}⏭  SKIP{C.RESET}"
DIVIDER = f"{C.DIM}{'━' * 60}{C.RESET}"

results = []  # (name, status, detail)

def header(step: int, title: str):
    print(f"\n{DIVIDER}")
    print(f"{C.BOLD}{C.CYAN}  BƯỚC {step}/10  │  {title}{C.RESET}")
    print(DIVIDER)

def record(name: str, passed: bool, detail: str = ""):
    status = "PASS" if passed else "FAIL"
    results.append((name, status, detail))
    icon = PASS if passed else FAIL
    print(f"  {icon}  {name}")
    if detail:
        print(f"       {C.DIM}{detail}{C.RESET}")

def record_skip(name: str, reason: str = ""):
    results.append((name, "SKIP", reason))
    print(f"  {SKIP}  {name}")
    if reason:
        print(f"       {C.DIM}{reason}{C.RESET}")

def summary():
    print(f"\n{'═' * 60}")
    print(f"{C.BOLD}{C.MAGENTA}  📊  TỔNG KẾT TEST{C.RESET}")
    print(f"{'═' * 60}")
    
    total = len(results)
    passed = sum(1 for _, s, _ in results if s == "PASS")
    failed = sum(1 for _, s, _ in results if s == "FAIL")
    skipped = sum(1 for _, s, _ in results if s == "SKIP")
    
    for name, status, detail in results:
        if status == "PASS":
            icon = f"{C.GREEN}✅{C.RESET}"
        elif status == "FAIL":
            icon = f"{C.RED}❌{C.RESET}"
        else:
            icon = f"{C.YELLOW}⏭ {C.RESET}"
        line = f"  {icon}  {name}"
        if detail and status != "PASS":
            line += f"  {C.DIM}({detail}){C.RESET}"
        print(line)
    
    print(f"\n  {C.BOLD}Tổng: {total}  │  "
          f"{C.GREEN}Pass: {passed}{C.RESET}  │  "
          f"{C.RED}Fail: {failed}{C.RESET}  │  "
          f"{C.YELLOW}Skip: {skipped}{C.RESET}")
    
    if failed == 0:
        print(f"\n  {C.GREEN}{C.BOLD}🎉  Tất cả test đều PASS!{C.RESET}")
    else:
        print(f"\n  {C.RED}{C.BOLD}⚠️  Có {failed} test FAIL — kiểm tra lại!{C.RESET}")
    
    print(f"{'═' * 60}\n")

# ══════════════════════════════════════════════════════
#  MAIN TEST FLOW
# ══════════════════════════════════════════════════════

async def run_tests(dry_run: bool = False):
    print(f"\n{'═' * 60}")
    print(f"{C.BOLD}{C.MAGENTA}  🤖  SCALP BOT  —  FULL TEST BINGX{C.RESET}")
    print(f"{'═' * 60}")
    print(f"  Symbol:     {C.CYAN}{TEST_SYMBOL}{C.RESET}")
    print(f"  Timeframe:  {C.CYAN}{TEST_TIMEFRAME}{C.RESET}")
    print(f"  Leverage:   {C.CYAN}{TEST_LEVERAGE}x{C.RESET}")
    print(f"  Margin:     {C.CYAN}{TEST_MARGIN_USDT} USDT{C.RESET}")
    print(f"  Mode:       {C.CYAN}{TEST_MARGIN_MODE.upper()}{C.RESET}")
    if dry_run:
        print(f"  {C.YELLOW}{C.BOLD}⚠  DRY-RUN MODE — Không mở lệnh thật{C.RESET}")
    else:
        print(f"  {C.RED}{C.BOLD}⚠  LIVE MODE — Sẽ mở + đóng lệnh thật!{C.RESET}")
    print(f"{'═' * 60}")

    # ── Lấy API credentials ──────────────────────────────────────
    api_key = os.getenv("BINGX_API_KEY", "").strip()
    api_secret = os.getenv("BINGX_API_SECRET", "").strip()
    
    if not api_key:
        api_key = input(f"\n{C.CYAN}Nhập BINGX_API_KEY: {C.RESET}").strip()
    if not api_secret:
        api_secret = input(f"{C.CYAN}Nhập BINGX_API_SECRET: {C.RESET}").strip()
    
    if not api_key or not api_secret:
        print(f"\n{C.RED}❌ Thiếu API Key hoặc API Secret. Dừng test.{C.RESET}")
        return

    exchange = None
    signal = "LONG"  # default signal nếu strategy trả về HOLD

    try:
        # ─────────────────────────────────────────────────────────
        # BƯỚC 1: Kết nối BingX
        # ─────────────────────────────────────────────────────────
        header(1, "KẾT NỐI BINGX")
        try:
            exchange = BingxExchange(api_key, api_secret)
            print(f"  ⏳ Đang kết nối và load markets...")
            t0 = time.time()
            await exchange.initialize()
            elapsed = time.time() - t0
            
            market_count = len(exchange.exchange.markets) if exchange.exchange.markets else 0
            record("Kết nối BingX", True, f"{market_count} markets loaded ({elapsed:.1f}s)")
        except Exception as e:
            record("Kết nối BingX", False, str(e))
            print(f"\n{C.RED}Không thể kết nối BingX, dừng test.{C.RESET}")
            summary()
            return

        # ─────────────────────────────────────────────────────────
        # BƯỚC 2: Lấy Balance
        # ─────────────────────────────────────────────────────────
        header(2, "LẤY SỐ DƯ TÀI KHOẢN")
        try:
            balance = await exchange.get_balance()
            record("Lấy balance", True, f"Số dư: {balance:.4f} USDT")
            
            if not dry_run and balance < TEST_MARGIN_USDT:
                print(f"  {C.YELLOW}⚠  Số dư ({balance:.2f} USDT) < margin test ({TEST_MARGIN_USDT} USDT)")
                print(f"     Bước mở lệnh có thể thất bại.{C.RESET}")
        except Exception as e:
            record("Lấy balance", False, str(e))

        # ─────────────────────────────────────────────────────────
        # BƯỚC 3: Lấy danh sách Futures symbols
        # ─────────────────────────────────────────────────────────
        header(3, "LẤY DANH SÁCH FUTURES")
        try:
            symbols = await exchange.get_futures_symbols()
            has_btc = TEST_SYMBOL in symbols
            record("Lấy futures symbols", True, f"{len(symbols)} symbols, {TEST_SYMBOL}: {'✓' if has_btc else '✗'}")
            
            if not has_btc:
                print(f"  {C.YELLOW}⚠  {TEST_SYMBOL} không tìm thấy trong danh sách!")
                print(f"     5 symbols mẫu: {symbols[:5]}{C.RESET}")
        except Exception as e:
            record("Lấy futures symbols", False, str(e))

        # ─────────────────────────────────────────────────────────
        # BƯỚC 4: Lấy Klines (OHLCV)
        # ─────────────────────────────────────────────────────────
        header(4, "LẤY DỮ LIỆU KLINES")
        df = None
        try:
            print(f"  ⏳ Đang lấy {KLINE_LIMIT} nến {TEST_TIMEFRAME} cho {TEST_SYMBOL}...")
            t0 = time.time()
            klines = await exchange.get_klines(TEST_SYMBOL, TEST_TIMEFRAME, limit=KLINE_LIMIT)
            elapsed = time.time() - t0
            
            if klines and len(klines) > 0:
                df = pd.DataFrame(klines, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                last_close = float(df['close'].iloc[-1])
                record("Lấy klines", True, f"{len(klines)} nến, close = {last_close:.2f} USDT ({elapsed:.1f}s)")
            else:
                record("Lấy klines", False, "Không có dữ liệu trả về")
        except Exception as e:
            record("Lấy klines", False, str(e))

        # ─────────────────────────────────────────────────────────
        # BƯỚC 5: Tính tín hiệu (Strategy)
        # ─────────────────────────────────────────────────────────
        header(5, "TÍNH TÍN HIỆU STRATEGY")
        try:
            if df is not None and len(df) >= config.ATR_PERIOD:
                signal_result = calculate_signal(df.copy())
                
                if signal_result == "LONG":
                    signal_icon = f"{C.GREEN}🟢 LONG  ↑{C.RESET}"
                elif signal_result == "SHORT":
                    signal_icon = f"{C.RED}🔴 SHORT ↓{C.RESET}"
                else:
                    signal_icon = f"{C.YELLOW}⚪ HOLD  ─{C.RESET}"
                
                record("Tính tín hiệu", True, f"Kết quả: {signal_result}")
                print(f"\n  {C.BOLD}  ╔═══════════════════════════════╗")
                print(f"  ║  📊  TÍN HIỆU:  {signal_icon}{C.BOLD}       ║")
                print(f"  ╚═══════════════════════════════╝{C.RESET}\n")
                
                if signal_result != "HOLD":
                    signal = signal_result
                else:
                    print(f"  {C.YELLOW}ℹ  Tín hiệu HOLD — sẽ dùng LONG mặc định cho test mở lệnh{C.RESET}")
                    signal = "LONG"
            else:
                data_len = len(df) if df is not None else 0
                record("Tính tín hiệu", False, f"Không đủ dữ liệu ({data_len}/{config.ATR_PERIOD} nến)")
        except Exception as e:
            record("Tính tín hiệu", False, str(e))
            traceback.print_exc()

        # ─────────────────────────────────────────────────────────
        # BƯỚC 6: Set Leverage & Margin Mode
        # ─────────────────────────────────────────────────────────
        header(6, "SET LEVERAGE & MARGIN MODE")
        if dry_run:
            record_skip("Set leverage", "Dry-run mode")
            record_skip("Set margin mode", "Dry-run mode")
        else:
            try:
                lev_ok = await exchange.set_leverage(TEST_SYMBOL, TEST_LEVERAGE)
                record("Set leverage", lev_ok, f"{TEST_LEVERAGE}x")
            except Exception as e:
                record("Set leverage", False, str(e))
            
            try:
                mode_ok = await exchange.set_margin_mode(TEST_SYMBOL, TEST_MARGIN_MODE)
                record("Set margin mode", mode_ok, TEST_MARGIN_MODE.upper())
            except Exception as e:
                record("Set margin mode", False, str(e))

        # ─────────────────────────────────────────────────────────
        # BƯỚC 7: Mở lệnh (Entry)
        # ─────────────────────────────────────────────────────────
        header(7, f"MỞ LỆNH — {signal}")
        order = None
        if dry_run:
            record_skip("Mở lệnh", "Dry-run mode — không mở lệnh thật")
        else:
            try:
                # Tính quantity từ margin
                if df is not None:
                    current_price = float(df['close'].iloc[-1])
                else:
                    # Fallback: lấy giá từ kline 1m
                    klines_1m = await exchange.get_klines(TEST_SYMBOL, "1m", limit=1)
                    current_price = float(klines_1m[0][4])
                
                quantity = (TEST_MARGIN_USDT * TEST_LEVERAGE) / current_price
                
                print(f"  📌 Giá hiện tại:  {current_price:.2f} USDT")
                print(f"  📌 Quantity:       {quantity:.6f}")
                print(f"  📌 Hướng:          {signal}")
                print(f"  ⏳ Đang mở lệnh...")
                
                order = await exchange.open_position(
                    TEST_SYMBOL, signal, quantity, TEST_LEVERAGE, TEST_MARGIN_MODE
                )
                
                if order:
                    order_id = order.get('id', 'N/A')
                    avg_price = order.get('average', order.get('price', 'N/A'))
                    status = order.get('status', 'N/A')
                    record("Mở lệnh", True, f"ID: {order_id}, Price: {avg_price}, Status: {status}")
                    
                    print(f"\n  {C.GREEN}{C.BOLD}  ╔═══════════════════════════════════╗")
                    print(f"  ║  🎯  LỆNH ĐÃ MỞ THÀNH CÔNG!     ║")
                    print(f"  ║  Order ID:  {str(order_id)[:20]:<20s}   ║")
                    print(f"  ╚═══════════════════════════════════╝{C.RESET}\n")
                else:
                    record("Mở lệnh", False, "Order trả về None")
            except Exception as e:
                record("Mở lệnh", False, str(e))
                traceback.print_exc()

        # ─────────────────────────────────────────────────────────
        # BƯỚC 8: Đóng lệnh (Exit)
        # ─────────────────────────────────────────────────────────
        header(8, "ĐÓNG LỆNH — EXIT")
        if dry_run:
            record_skip("Đóng lệnh", "Dry-run mode — không có lệnh để đóng")
        elif order:
            try:
                print(f"  ⏳ Đợi 2 giây trước khi đóng lệnh...")
                await asyncio.sleep(2)
                
                print(f"  ⏳ Đang đóng vị thế {signal} trên {TEST_SYMBOL}...")
                close_order = await exchange.close_position(TEST_SYMBOL, signal)
                
                if close_order:
                    close_id = close_order.get('id', 'N/A')
                    close_price = close_order.get('average', close_order.get('price', 'N/A'))
                    record("Đóng lệnh", True, f"ID: {close_id}, Price: {close_price}")
                    
                    print(f"\n  {C.GREEN}{C.BOLD}  ╔═══════════════════════════════════╗")
                    print(f"  ║  ✅  LỆNH ĐÃ ĐÓNG THÀNH CÔNG!    ║")
                    print(f"  ╚═══════════════════════════════════╝{C.RESET}\n")
                else:
                    record("Đóng lệnh", False, "close_position trả về None (có thể đã tự đóng)")
            except Exception as e:
                record("Đóng lệnh", False, str(e))
                traceback.print_exc()
        else:
            record_skip("Đóng lệnh", "Không có lệnh đã mở để đóng")

        # ─────────────────────────────────────────────────────────
        # BƯỚC 9: Database Operations
        # ─────────────────────────────────────────────────────────
        header(9, "DATABASE OPERATIONS")
        try:
            # Use a temporary test database to avoid polluting the real one
            original_db = config.DB_PATH
            config.DB_PATH = os.path.join(config.BASE_DIR, 'test_database.sqlite')
            
            await database.init_db()
            record("Init database", True)
            
            await database.create_user(TEST_USER_ID)
            record("Create user", True, f"User ID: {TEST_USER_ID}")
            
            # Test trading config
            await database.update_trading_config(
                TEST_USER_ID,
                leverage=TEST_LEVERAGE,
                margin_qty=TEST_MARGIN_USDT,
                margin_mode=TEST_MARGIN_MODE,
                tp_percent=1.5,
                sl_percent=1.0,
                auto_trade_enabled=True
            )
            cfg = await database.get_trading_config(TEST_USER_ID)
            if cfg:
                record("Trading config CRUD", True,
                       f"Leverage={cfg['leverage']}, Margin={cfg['margin_qty']}, "
                       f"TP={cfg['tp_percent']}%, SL={cfg['sl_percent']}%")
            else:
                record("Trading config CRUD", False, "get_trading_config trả về None")
            
            # Test open positions
            await database.add_open_position(
                TEST_USER_ID, "BingX", TEST_SYMBOL, signal,
                50000.0, 0.001, 50500.0, 49500.0, "TEST_ORDER_123"
            )
            positions = await database.get_open_positions(TEST_USER_ID)
            if positions and len(positions) > 0:
                record("Open positions CRUD", True, f"{len(positions)} position(s)")
            else:
                record("Open positions CRUD", False, "Không tìm thấy position")
            
            # Cleanup test database
            config.DB_PATH = original_db
            test_db_path = os.path.join(config.BASE_DIR, 'test_database.sqlite')
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
                print(f"  {C.DIM}🗑  Đã xóa test database{C.RESET}")
                
        except Exception as e:
            record("Database operations", False, str(e))
            traceback.print_exc()
            # Restore original DB path
            config.DB_PATH = os.path.join(config.BASE_DIR, 'bot_database.sqlite')

        # ─────────────────────────────────────────────────────────
        # BƯỚC 10: Cleanup — Đóng kết nối
        # ─────────────────────────────────────────────────────────
        header(10, "CLEANUP — ĐÓNG KẾT NỐI")
        try:
            if exchange:
                await exchange.close_connection()
                record("Đóng kết nối BingX", True)
        except Exception as e:
            record("Đóng kết nối BingX", False, str(e))

    except Exception as e:
        print(f"\n{C.RED}{C.BOLD}💥 LỖI KHÔNG MONG ĐỢI: {e}{C.RESET}")
        traceback.print_exc()
        if exchange:
            try:
                await exchange.close_connection()
            except Exception:
                pass

    # ── In tổng kết ──────────────────────────────────────────────
    summary()


# ══════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    
    print(f"""
{C.BOLD}{C.MAGENTA}
  ╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║   🤖  SCALP BOT — BingX Full Test Suite              ║
  ║                                                      ║
  ║   Test toàn bộ chức năng bot trên sàn BingX          ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝
{C.RESET}""")
    
    if not dry_run:
        print(f"{C.RED}{C.BOLD}")
        print(f"  ⚠️  CẢNH BÁO: Script này sẽ MỞ LỆNH THẬT trên BingX!")
        print(f"  ⚠️  Ký quỹ mặc định: {TEST_MARGIN_USDT} USDT, Leverage: {TEST_LEVERAGE}x")
        print(f"  ⚠️  Lệnh sẽ được ĐÓNG NGAY SAU KHI MỞ.")
        print(f"{C.RESET}")
        
        confirm = input(f"\n{C.YELLOW}  Bạn có muốn tiếp tục? (y/N): {C.RESET}").strip().lower()
        if confirm not in ('y', 'yes'):
            print(f"\n{C.YELLOW}  ⏹  Đã hủy. Dùng --dry-run để test an toàn.{C.RESET}\n")
            sys.exit(0)
    
    asyncio.run(run_tests(dry_run=dry_run))
