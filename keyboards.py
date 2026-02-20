from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import config
import pair_cache

# ═══════════════════════════════════════════════
#  keyboards.py  –  Crypto Futures Bot UI
# ═══════════════════════════════════════════════


# ── MAIN MENU ───────────────────────────────────
def get_main_menu_keyboard():
    keyboard = [
        # ── Xem thông tin ──────────────────────────
        [
            InlineKeyboardButton("📡 Trạng thái",      callback_data="menu_status"),
            InlineKeyboardButton("💼 Vị thế mở",       callback_data="menu_positions"),
        ],
        # ── Cấu hình theo dõi ──────────────────────
        [
            InlineKeyboardButton("🪙 Cặp giao dịch",   callback_data="menu_pairs"),
            InlineKeyboardButton("🕐 Khung thời gian", callback_data="menu_timeframe"),
        ],
        # ── Thiết lập ──────────────────────────────
        [
            InlineKeyboardButton("🎛 Cài đặt",         callback_data="menu_settings"),
            InlineKeyboardButton("🔐 API Keys",         callback_data="menu_api_keys"),
        ],
        # ── Làm mới ────────────────────────────────
        [
            InlineKeyboardButton("🔄 Làm mới",         callback_data="menu_refresh"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── SETTINGS ────────────────────────────────────
def get_settings_keyboard(auto_trade_enabled):
    auto_icon  = "🟢" if auto_trade_enabled else "🔴"
    auto_label = "BẬT" if auto_trade_enabled else "TẮT"
    keyboard = [
        [
            InlineKeyboardButton("⚡ Đòn bẩy",          callback_data="set_leverage"),
            InlineKeyboardButton("💵 Ký quỹ (USDT)",    callback_data="set_margin"),
        ],
        [
            InlineKeyboardButton("🔁 Chế độ Margin",    callback_data="set_margin_mode"),
        ],
        [
            InlineKeyboardButton("🎯 Take Profit (%)",  callback_data="set_tp"),
            InlineKeyboardButton("🛡️ Stop Loss (%)",    callback_data="set_sl"),
        ],
        [
            InlineKeyboardButton(f"{auto_icon} Auto‑Trade: {auto_label}", callback_data="toggle_auto_trade"),
        ],
        [
            InlineKeyboardButton("◀️ Quay lại Menu",    callback_data="menu_main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


# ── EXCHANGE LIST ────────────────────────────────
# Brand-colour circles for each exchange
_EX_ICONS = {
    "Binance": "🟡",
    "BingX":   "🔵",
    "Bybit":   "🟠",
    "MEXC":    "🟣",
    "OKX":     "⬜",
}

def get_exchange_list_keyboard(exchanges, current_apis=[]):
    keyboard = []

    # Setup buttons – 2 per row
    row = []
    for ex in exchanges:
        has_api = any(item['exchange_name'] == ex for item in current_apis)
        icon    = _EX_ICONS.get(ex, "🔘")
        tick    = " ✅" if has_api else ""
        row.append(InlineKeyboardButton(f"{icon} {ex}{tick}", callback_data=f"setup_api_{ex}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Toggle on/off per exchange
    if current_apis:
        keyboard.append([InlineKeyboardButton("─── Bật / Tắt sàn ───", callback_data="ignore")])
        for api in current_apis:
            status = "🟢" if api['is_enabled'] else "🔴"
            icon   = _EX_ICONS.get(api['exchange_name'], "🔘")
            keyboard.append([InlineKeyboardButton(
                f"{icon} {api['exchange_name']}  {status}",
                callback_data=f"toggle_api_{api['exchange_name']}"
            )])

    keyboard.append([InlineKeyboardButton("◀️ Quay lại Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)


# ── TIMEFRAME PICKER ────────────────────────────
def get_timeframe_keyboard(current_timeframes=[]):
    keyboard = []
    row = []
    for tf in config.SUPPORTED_TIMEFRAMES:
        label = (f"✅ {tf}") if tf in current_timeframes else tf
        row.append(InlineKeyboardButton(label, callback_data=f"tf_toggle_{tf}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("🗑️ Xóa tất cả",  callback_data="tf_clear_all"),
        InlineKeyboardButton("◀️ Quay lại",     callback_data="menu_main"),
    ])
    return InlineKeyboardMarkup(keyboard)


# ── PAIRS — ALPHABET NAV ────────────────────────
def get_pairs_alphabet_keyboard(current_symbols=[]):
    keyboard = []
    letters = pair_cache.get_available_letters()

    # Alphabet grid — 5 per row
    row = []
    for letter in letters:
        count = len(pair_cache.get_symbols_by_letter(letter))
        row.append(InlineKeyboardButton(f"{letter} · {count}", callback_data=f"pairs_letter_{letter}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # Currently selected (removable)
    if current_symbols:
        keyboard.append([InlineKeyboardButton(
            f"─── Đang theo dõi  ({len(current_symbols)} cặp) ───", callback_data="ignore"
        )])
        row = []
        for sym in current_symbols[:16]:
            short = sym.split("/")[0]
            row.append(InlineKeyboardButton(f"✖ {short}", callback_data=f"pairs_remove_{sym}"))
            if len(row) == 4:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        if len(current_symbols) > 16:
            keyboard.append([InlineKeyboardButton(
                f"… và {len(current_symbols) - 16} cặp khác", callback_data="ignore"
            )])

    keyboard.append([
        InlineKeyboardButton("✍️ Nhập thủ công",  callback_data="pairs_add"),
        InlineKeyboardButton("🗑️ Xóa tất cả",     callback_data="pairs_clear_all"),
    ])
    keyboard.append([InlineKeyboardButton("◀️ Quay lại Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)


# ── PAIRS — BY LETTER ────────────────────────────
def get_pairs_by_letter_keyboard(letter, current_symbols=[]):
    keyboard = []
    symbols_for_letter = pair_cache.get_symbols_by_letter(letter)

    row = []
    for short_name in symbols_for_letter:
        full_symbol = pair_cache.get_full_symbol(short_name)
        label = (f"✅ {short_name}") if full_symbol in current_symbols else short_name
        row.append(InlineKeyboardButton(label, callback_data=f"pairs_toggle_{full_symbol}"))
        if len(row) == 4:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("◀️ Chọn chữ cái khác", callback_data="menu_pairs")])
    return InlineKeyboardMarkup(keyboard)


# ── CANCEL / BACK ────────────────────────────────
def get_cancel_keyboard():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✖️ Hủy bỏ", callback_data="menu_main")
    ]])
