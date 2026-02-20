import logging
import asyncio
import random
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler,
)

import config
import database
import keyboards
import pair_cache
from scanner import scanner_task

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── Conversation states ──────────────────────────────────────────
WAIT_API_KEY, WAIT_API_SECRET, WAIT_API_PASSPHRASE = 1, 2, 3
WAIT_LEVERAGE, WAIT_MARGIN, WAIT_TP, WAIT_SL = 4, 5, 6, 7
WAIT_PAIR_ADD = 9

# ── UI helpers ───────────────────────────────────────────────────

HEADER = (
    "╔══════════════════════════╗\n"
    "║  🤖  SCALP BOT  ⚡       ║\n"
    "╚══════════════════════════╝"
)

DIVIDER = "━" * 28

def _status_line(label: str, value: str, icon: str = "▸") -> str:
    return f"{icon}  {label}: `{value}`"

async def _loading(query, text: str = "⏳ Đang tải dữ liệu..."):
    """Show a brief loading indicator, then caller overwrites it."""
    try:
        await query.edit_message_text(text, parse_mode="Markdown")
    except Exception:
        pass

# ── /start ───────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    await database.create_user(user_id)
    kb = keyboards.get_main_menu_keyboard()
    msg = (
        f"{HEADER}\n\n"
        "Chào mừng đến với *SCALP BOT* 🚀\n"
        "Bot giao dịch Futures tự động đa sàn.\n\n"
        f"{DIVIDER}\n"
        "Chọn chức năng bên dưới 👇"
    )
    if update.message:
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")
    return ConversationHandler.END

# ── Menu handler (callbacks) ─────────────────────────────────────

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query:
        return ConversationHandler.END
    await query.answer()
    data = query.data
    if data is None:
        return ConversationHandler.END
    user_id = update.effective_user.id  # type: ignore[union-attr]

    try:

        # ── Home / Refresh ───────────────────────────────────────
        if data in ("menu_main", "menu_refresh"):
            kb = keyboards.get_main_menu_keyboard()
            # Small random suffix prevents "Message is not modified" error
            suffix = random.randint(100, 999)
            msg = (
                f"{HEADER}\n\n"
                "🏠 *Menu chính*\n\n"
                f"{DIVIDER}\n"
                f"Chọn chức năng bên dưới 👇  `#{suffix}`"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        # ── Status ───────────────────────────────────────────────
        elif data == "menu_status":
            await _loading(query)
            pairs    = list(await database.get_watched_pairs(user_id))
            symbols  = await database.get_user_symbols(user_id)
            tfs      = await database.get_user_timeframes(user_id)
            cfg      = await database.get_trading_config(user_id)

            sym_txt  = ", ".join(f"`{s.split('/')[0]}`" for s in symbols) if symbols else "_Chưa chọn_"
            tf_txt   = ", ".join(f"`{t}`" for t in tfs) if tfs else "_Chưa chọn_"
            count    = len(pairs)
            auto_on  = cfg and cfg['auto_trade_enabled']
            auto_txt = "🟢 BẬT" if auto_on else "🔴 TẮT"

            if count > 0:
                pair_lines = "\n".join(
                    f"  `{p['symbol'].split('/')[0]}` / `{p['timeframe']}`" for p in pairs[:20]
                )
                if count > 20:
                    pair_lines += f"\n  _... và {count - 20} cặp khác_"
            else:
                pair_lines = "  _Không có_"

            msg = (
                f"📊 *TRẠNG THÁI BOT*\n"
                f"{DIVIDER}\n"
                f"💱  Cặp đang chọn:  {sym_txt}\n"
                f"⏱  Khung TG:        {tf_txt}\n"
                f"📌  Tổng theo dõi:  `{count}` cặp×khung\n"
                f"🤖  Auto‑trade:     {auto_txt}\n"
                f"{DIVIDER}\n"
                f"*Danh sách theo dõi:*\n{pair_lines}"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")

        # ── Timeframe picker ─────────────────────────────────────
        elif data in ("menu_timeframe", "tf_clear_all") or data.startswith("tf_toggle_"):
            if data.startswith("tf_toggle_"):
                tf = data.replace("tf_toggle_", "")
                if tf in config.SUPPORTED_TIMEFRAMES:
                    await database.toggle_user_timeframe(user_id, tf)
            elif data == "tf_clear_all":
                await database.clear_user_timeframes(user_id)

            current_tfs = await database.get_user_timeframes(user_id)
            kb = keyboards.get_timeframe_keyboard(current_tfs)
            tf_txt = "  ".join(f"`{t}`" for t in current_tfs) if current_tfs else "_Chưa chọn_"
            msg = (
                f"⏱ *KHUNG THỜI GIAN*\n"
                f"{DIVIDER}\n"
                f"Đang chọn: {tf_txt}\n"
                f"{DIVIDER}\n"
                "Nhấn để bật / tắt từng khung 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        # ── Pairs picker (alphabet nav) ───────────────────────────
        elif data == "menu_pairs":
            await _loading(query)
            symbols = await database.get_user_symbols(user_id)
            kb = keyboards.get_pairs_alphabet_keyboard(symbols)
            total = len(pair_cache.get_all_short_names())
            sym_txt = "  ".join(f"`{s.split('/')[0]}`" for s in symbols) if symbols else "_Chưa chọn_"
            msg = (
                f"💱 *CẶP GIAO DỊCH*\n"
                f"{DIVIDER}\n"
                f"📦  Thư viện:    `{total}` cặp (Binance)\n"
                f"👁  Theo dõi:    {sym_txt}\n"
                f"{DIVIDER}\n"
                "Chọn chữ cái đầu để tìm cặp 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data.startswith("pairs_letter_"):
            letter = data.replace("pairs_letter_", "")
            symbols = await database.get_user_symbols(user_id)
            kb = keyboards.get_pairs_by_letter_keyboard(letter, symbols)
            count = len(pair_cache.get_symbols_by_letter(letter))
            msg = (
                f"💱 *CẶP NHÓM  «{letter}»*\n"
                f"{DIVIDER}\n"
                f"Có `{count}` cặp · Nhấn để bật / tắt 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data.startswith("pairs_toggle_"):
            sym = data.replace("pairs_toggle_", "")
            current_symbols = await database.get_user_symbols(user_id)
            if sym in current_symbols:
                await database.remove_user_symbol(user_id, sym)
                action = f"🔴 Đã bỏ `{sym.split('/')[0]}`"
            else:
                await database.add_user_symbol(user_id, sym)
                action = f"🟢 Đã thêm `{sym.split('/')[0]}`"
            letter = sym.split("/")[0][0].upper()
            symbols = await database.get_user_symbols(user_id)
            kb = keyboards.get_pairs_by_letter_keyboard(letter, symbols)
            count = len(pair_cache.get_symbols_by_letter(letter))
            msg = (
                f"💱 *CẶP NHÓM  «{letter}»*\n"
                f"{DIVIDER}\n"
                f"{action}\n"
                f"Có `{count}` cặp · Nhấn để bật / tắt 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data == "pairs_add":
            msg = (
                f"✍️ *NHẬP CẶP THỦ CÔNG*\n"
                f"{DIVIDER}\n"
                "Nhập tên cặp, mỗi cặp 1 dòng hoặc cách bằng dấu phẩy:\n\n"
                "`BTC, ETH, SOL`\n"
                "`BTC/USDT:USDT`\n\n"
                "_Bot tự chuyển sang định dạng futures._"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")
            return WAIT_PAIR_ADD

        elif data.startswith("pairs_remove_"):
            sym = data.replace("pairs_remove_", "")
            await database.remove_user_symbol(user_id, sym)
            symbols = await database.get_user_symbols(user_id)
            kb = keyboards.get_pairs_alphabet_keyboard(symbols)
            sym_txt = "  ".join(f"`{s.split('/')[0]}`" for s in symbols) if symbols else "_Chưa chọn_"
            msg = (
                f"💱 *CẶP GIAO DỊCH*\n"
                f"{DIVIDER}\n"
                f"🗑 Đã xóa `{sym.split('/')[0]}`\n\n"
                f"👁  Theo dõi: {sym_txt}\n"
                f"{DIVIDER}\n"
                "Chọn chữ cái để tìm cặp 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data == "pairs_clear_all":
            await database.clear_user_symbols(user_id)
            kb = keyboards.get_pairs_alphabet_keyboard([])
            msg = (
                f"💱 *CẶP GIAO DỊCH*\n"
                f"{DIVIDER}\n"
                "🗑 Đã xóa tất cả cặp theo dõi.\n"
                f"{DIVIDER}\n"
                "Chọn chữ cái để tìm cặp 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        # ── API Keys ─────────────────────────────────────────────
        elif data == "menu_api_keys":
            apis = await database.get_exchange_apis(user_id)
            kb = keyboards.get_exchange_list_keyboard(config.SUPPORTED_EXCHANGES, apis)
            configured = [a['exchange_name'] for a in apis if a['is_enabled']] if apis else []
            cfg_txt = "  ".join(f"`{e}`" for e in configured) if configured else "_Chưa cấu hình_"
            msg = (
                f"🔑 *API KEYS*\n"
                f"{DIVIDER}\n"
                f"✅  Sàn đang bật: {cfg_txt}\n"
                f"{DIVIDER}\n"
                "Chọn sàn để cấu hình · Nhấn tên sàn để bật/tắt 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data.startswith("setup_api_"):
            ex_name = data.replace("setup_api_", "")
            context.user_data['setup_exchange'] = ex_name  # type: ignore[index]
            msg = (
                f"🔑 *CẤU HÌNH API — {ex_name}*\n"
                f"{DIVIDER}\n"
                "Bước 1/2  ·  Gửi *API Key* của bạn:\n\n"
                "_Lưu ý: chỉ cần quyền Trading, không cần Withdraw._"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")
            return WAIT_API_KEY

        elif data.startswith("toggle_api_"):
            ex_name = data.replace("toggle_api_", "")
            apis = await database.get_exchange_apis(user_id)
            for api in apis:
                if api['exchange_name'] == ex_name:
                    await database.toggle_exchange_api(user_id, ex_name, not api['is_enabled'])
                    break
            updated_apis = await database.get_exchange_apis(user_id)
            kb = keyboards.get_exchange_list_keyboard(config.SUPPORTED_EXCHANGES, updated_apis)
            configured = [a['exchange_name'] for a in updated_apis if a['is_enabled']]
            cfg_txt = "  ".join(f"`{e}`" for e in configured) if configured else "_Chưa cấu hình_"
            msg = (
                f"🔑 *API KEYS*\n"
                f"{DIVIDER}\n"
                f"✅  Sàn đang bật: {cfg_txt}\n"
                f"{DIVIDER}\n"
                "Chọn sàn để cấu hình · Nhấn tên sàn để bật/tắt 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        # ── Settings ─────────────────────────────────────────────
        elif data == "menu_settings":
            cfg = await database.get_trading_config(user_id)
            if not cfg:
                return ConversationHandler.END
            kb = keyboards.get_settings_keyboard(cfg['auto_trade_enabled'])
            mode_icon = "🔀" if cfg['margin_mode'] == 'cross' else "🔒"
            auto_txt = "🟢 BẬT" if cfg['auto_trade_enabled'] else "🔴 TẮT"
            msg = (
                f"⚙️ *CÀI ĐẶT TRADING*\n"
                f"{DIVIDER}\n"
                f"⚡  Đòn bẩy:    `{cfg['leverage']}x`\n"
                f"💵  Ký quỹ:     `{cfg['margin_qty']} USDT`\n"
                f"{mode_icon}  Margin:      `{cfg['margin_mode'].upper()}`\n"
                f"🎯  Take Profit: `{cfg['tp_percent']}%`\n"
                f"🛡  Stop Loss:  `{cfg['sl_percent']}%`\n"
                f"🤖  Auto‑Trade: {auto_txt}\n"
                f"{DIVIDER}\n"
                "Nhấn nút bên dưới để chỉnh sửa 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data == "toggle_auto_trade":
            cfg = await database.get_trading_config(user_id)
            if not cfg:
                return ConversationHandler.END
            new_val = not cfg['auto_trade_enabled']
            await database.update_trading_config(user_id, auto_trade_enabled=new_val)
            kb = keyboards.get_settings_keyboard(new_val)
            state = "🟢 *BẬT*" if new_val else "🔴 *TẮT*"
            msg = (
                f"⚙️ *CÀI ĐẶT TRADING*\n"
                f"{DIVIDER}\n"
                f"🤖  Auto‑Trade: {state}\n"
                f"{DIVIDER}\n"
                "Nhấn nút bên dưới để chỉnh sửa 👇"
            )
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

        elif data == "set_leverage":
            msg = (
                f"⚡ *ĐÒN BẨY (LEVERAGE)*\n"
                f"{DIVIDER}\n"
                "Nhập số đòn bẩy muốn dùng:\n"
                "_VD: `10`, `20`, `50`_"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")
            return WAIT_LEVERAGE

        elif data == "set_margin":
            msg = (
                f"💵 *KÝ QUỸ MỖI LỆNH (USDT)*\n"
                f"{DIVIDER}\n"
                "Nhập số USDT muốn dùng cho mỗi lệnh:\n"
                "_VD: `10`, `50`, `100`_"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")
            return WAIT_MARGIN

        elif data == "set_margin_mode":
            cfg = await database.get_trading_config(user_id)
            if not cfg:
                return ConversationHandler.END
            new_mode = 'cross' if cfg['margin_mode'] == 'isolated' else 'isolated'
            await database.update_trading_config(user_id, margin_mode=new_mode)
            mode_icon = "🔀" if new_mode == 'cross' else "🔒"
            msg = (
                f"⚙️ *CÀI ĐẶT TRADING*\n"
                f"{DIVIDER}\n"
                f"✅  Đã chuyển sang chế độ:\n"
                f"   {mode_icon}  `{new_mode.upper()}`"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_main_menu_keyboard(), parse_mode="Markdown")

        elif data == "set_tp":
            msg = (
                f"🎯 *TAKE PROFIT (%)*\n"
                f"{DIVIDER}\n"
                "Nhập % lợi nhuận để chốt lời:\n"
                "_VD: `1.5`, `2`, `3`_"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")
            return WAIT_TP

        elif data == "set_sl":
            msg = (
                f"🛡 *STOP LOSS (%)*\n"
                f"{DIVIDER}\n"
                "Nhập % thua lỗ tối đa cho mỗi lệnh:\n"
                "_VD: `1`, `1.5`, `2`_"
            )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")
            return WAIT_SL

        # ── Positions ────────────────────────────────────────────
        elif data == "menu_positions":
            await _loading(query)
            positions = list(await database.get_open_positions(user_id))
            if positions:
                lines: list[str] = []
                for p in positions:
                    side_icon = "🟢" if p['side'] == 'LONG' else "🔴"
                    lines.append(
                        f"{side_icon} *{p['symbol'].split('/')[0]}* ({p['side']}) · _{p['exchange_name']}_\n"
                        f"   🏷 Entry: `{p['entry_price']:.4f}`\n"
                        f"   🎯 TP: `{p['tp_price']:.4f}`  🛡 SL: `{p['sl_price']:.4f}`"
                    )
                msg = (
                    f"📈 *VỊ THẾ ĐANG MỞ  ({len(positions)})*\n"
                    f"{DIVIDER}\n"
                    + "\n\n".join(lines)
                )
            else:
                msg = (
                    f"📈 *VỊ THẾ ĐANG MỞ*\n"
                    f"{DIVIDER}\n"
                    "📭  Hiện không có vị thế nào đang mở."
                )
            await query.edit_message_text(msg, reply_markup=keyboards.get_cancel_keyboard(), parse_mode="Markdown")

        elif data == "ignore":
            pass

    except Exception as e:
        if "Message is not modified" not in str(e):
            logger.error(f"Menu error: {e}")

    return ConversationHandler.END

# ── Text input handlers ───────────────────────────────────────────

async def _num_input(update, context, field, label, icon, retry_state):
    user_id = update.effective_user.id
    try:
        val = float(update.message.text)
        await database.update_trading_config(user_id, **{field: val})
        msg = (
            f"✅ *Đã cập nhật*\n"
            f"{DIVIDER}\n"
            f"{icon}  {label}: `{val}`"
        )
        await update.message.reply_text(msg, reply_markup=keyboards.get_main_menu_keyboard(), parse_mode="Markdown")
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text(
            f"❌ Giá trị không hợp lệ. Vui lòng nhập số:",
            reply_markup=keyboards.get_cancel_keyboard()
        )
        return retry_state

async def ask_leverage(u, c): return await _num_input(u, c, 'leverage',   "Đòn bẩy",    "⚡", WAIT_LEVERAGE)
async def ask_margin(u, c):   return await _num_input(u, c, 'margin_qty', "Ký quỹ",     "💵", WAIT_MARGIN)
async def ask_tp(u, c):       return await _num_input(u, c, 'tp_percent', "Take Profit", "🎯", WAIT_TP)
async def ask_sl(u, c):       return await _num_input(u, c, 'sl_percent', "Stop Loss",   "🛡", WAIT_SL)

async def ask_pair_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id  # type: ignore[union-attr]
    if not update.message or not update.message.text:
        return WAIT_PAIR_ADD
    raw = update.message.text.strip()
    parts = [s.strip().upper() for s in raw.replace(",", " ").split() if s.strip()]
    added = []
    for sym in parts:
        if "/" not in sym:
            sym = (sym[:-4] + "/USDT:USDT") if sym.endswith("USDT") else (sym + "/USDT:USDT")
        await database.add_user_symbol(user_id, sym)
        added.append(sym)

    if added:
        added_txt = "\n".join(f"  ✅ `{s.split('/')[0]}`" for s in added)
        msg = (
            f"💱 *ĐÃ THÊM CẶP*\n"
            f"{DIVIDER}\n"
            f"{added_txt}"
        )
        await update.message.reply_text(msg, reply_markup=keyboards.get_main_menu_keyboard(), parse_mode="Markdown")
    else:
        await update.message.reply_text(
            "❌ Không nhận dạng được cặp nào. Thử lại:",
            reply_markup=keyboards.get_cancel_keyboard()
        )
        return WAIT_PAIR_ADD
    return ConversationHandler.END

async def ask_api_key(update, context):
    context.user_data['temp_api_key'] = update.message.text.strip()
    msg = (
        f"🔑 *CẤU HÌNH API*\n"
        f"{DIVIDER}\n"
        "Bước 2/2  ·  Gửi *API Secret* của bạn:"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
    return WAIT_API_SECRET

async def ask_api_secret(update, context):
    context.user_data['temp_api_secret'] = update.message.text.strip()
    ex = context.user_data.get('setup_exchange')
    if ex == 'OKX':
        msg = (
            f"🔑 *CẤU HÌNH API — OKX*\n"
            f"{DIVIDER}\n"
            "Bước 3/3  ·  Gửi *Passphrase* của bạn:"
        )
        await update.message.reply_text(msg, parse_mode="Markdown")
        return WAIT_API_PASSPHRASE
    user_id = update.effective_user.id
    await database.save_exchange_api(
        user_id, ex,
        context.user_data['temp_api_key'],
        context.user_data['temp_api_secret']
    )
    msg = (
        f"✅ *Đã lưu API — {ex}*\n"
        f"{DIVIDER}\n"
        "_API Key đã được lưu an toàn._"
    )
    await update.message.reply_text(msg, reply_markup=keyboards.get_main_menu_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

async def ask_api_passphrase(update, context):
    ex = context.user_data.get('setup_exchange')
    user_id = update.effective_user.id
    await database.save_exchange_api(
        user_id, ex,
        context.user_data['temp_api_key'],
        context.user_data['temp_api_secret'],
        update.message.text.strip()
    )
    msg = (
        f"✅ *Đã lưu API — {ex}*\n"
        f"{DIVIDER}\n"
        "_API Key + Passphrase đã được lưu an toàn._"
    )
    await update.message.reply_text(msg, reply_markup=keyboards.get_main_menu_keyboard(), parse_mode="Markdown")
    return ConversationHandler.END

# ── Application setup ─────────────────────────────────────────────

async def post_init(application: Application) -> None:
    await database.init_db()
    logger.info("Loading Binance futures symbols...")
    await pair_cache.load_binance_futures_symbols()
    asyncio.create_task(scanner_task(application))
    logger.info("Bot started — Scanner running.")

def main() -> None:
    application = (
        Application.builder()
        .token(config.TELEGRAM_BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(menu_handler),
        ],
        states={
            WAIT_LEVERAGE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_leverage)],
            WAIT_MARGIN:         [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_margin)],
            WAIT_TP:             [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_tp)],
            WAIT_SL:             [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_sl)],
            WAIT_PAIR_ADD:       [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_pair_add)],
            WAIT_API_KEY:        [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_api_key)],
            WAIT_API_SECRET:     [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_api_secret)],
            WAIT_API_PASSPHRASE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_api_passphrase)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(menu_handler),
        ],
        allow_reentry=True,
        per_message=False,
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
