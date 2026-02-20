import aiosqlite
import logging
import config

logger = logging.getLogger(__name__)

async def init_db():
    """Initialize the SQLite database with required tables."""
    try:
        async with aiosqlite.connect(config.DB_PATH) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS exchange_apis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    exchange_name TEXT,
                    api_key TEXT,
                    api_secret TEXT,
                    passphrase TEXT,
                    is_enabled BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, exchange_name)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS trading_config (
                    user_id INTEGER PRIMARY KEY,
                    leverage INTEGER DEFAULT 10,
                    margin_qty REAL DEFAULT 10.0,
                    margin_mode TEXT DEFAULT 'isolated',
                    auto_trade_enabled BOOLEAN DEFAULT 0,
                    tp_percent REAL DEFAULT 1.0,
                    sl_percent REAL DEFAULT 1.0,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

            # User's selected timeframes (separate from pairs)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_timeframes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    timeframe TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, timeframe)
                )
            ''')

            # User's selected symbols (separate from timeframes)
            await db.execute('''
                CREATE TABLE IF NOT EXISTS user_symbols (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    symbol TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, symbol)
                )
            ''')

            # watched_pairs is now auto-generated from user_timeframes x user_symbols
            await db.execute('''
                CREATE TABLE IF NOT EXISTS watched_pairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    symbol TEXT,
                    timeframe TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    UNIQUE(user_id, symbol, timeframe)
                )
            ''')

            await db.execute('''
                CREATE TABLE IF NOT EXISTS open_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    exchange_name TEXT,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    quantity REAL,
                    tp_price REAL,
                    sl_price REAL,
                    order_id TEXT,
                    opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            ''')

            await db.commit()
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

async def create_user(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        await db.execute('INSERT OR IGNORE INTO trading_config (user_id) VALUES (?)', (user_id,))
        await db.commit()

# --- Exchange APIs ---

async def save_exchange_api(user_id, exchange_name, api_key, api_secret, passphrase=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('''
            INSERT INTO exchange_apis (user_id, exchange_name, api_key, api_secret, passphrase)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, exchange_name) DO UPDATE SET
                api_key=excluded.api_key,
                api_secret=excluded.api_secret,
                passphrase=excluded.passphrase
        ''', (user_id, exchange_name, api_key, api_secret, passphrase))
        await db.commit()

async def get_exchange_apis(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM exchange_apis WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchall()

async def toggle_exchange_api(user_id, exchange_name, is_enabled):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('''
            UPDATE exchange_apis SET is_enabled = ? 
            WHERE user_id = ? AND exchange_name = ?
        ''', (is_enabled, user_id, exchange_name))
        await db.commit()

# --- Trading Config ---

async def get_trading_config(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM trading_config WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchone()

async def update_trading_config(user_id, **kwargs):
    if not kwargs: return
    set_clause = ", ".join([f"{k} = ?" for k in kwargs.keys()])
    values = tuple(kwargs.values()) + (user_id,)
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute(f'UPDATE trading_config SET {set_clause} WHERE user_id = ?', values)
        await db.commit()

# --- User Timeframes ---

async def get_user_timeframes(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute('SELECT timeframe FROM user_timeframes WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def toggle_user_timeframe(user_id, timeframe):
    """Add if not exists, remove if exists. Returns new list."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute('SELECT id FROM user_timeframes WHERE user_id = ? AND timeframe = ?', (user_id, timeframe)) as cursor:
            exists = await cursor.fetchone()
        if exists:
            await db.execute('DELETE FROM user_timeframes WHERE user_id = ? AND timeframe = ?', (user_id, timeframe))
        else:
            await db.execute('INSERT INTO user_timeframes (user_id, timeframe) VALUES (?, ?)', (user_id, timeframe))
        await db.commit()
    # Rebuild watched pairs
    await rebuild_watched_pairs(user_id)

async def clear_user_timeframes(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('DELETE FROM user_timeframes WHERE user_id = ?', (user_id,))
        await db.commit()
    await rebuild_watched_pairs(user_id)

# --- User Symbols ---

async def get_user_symbols(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        async with db.execute('SELECT symbol FROM user_symbols WHERE user_id = ?', (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

async def add_user_symbol(user_id, symbol):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO user_symbols (user_id, symbol) VALUES (?, ?)', (user_id, symbol))
        await db.commit()
    await rebuild_watched_pairs(user_id)

async def remove_user_symbol(user_id, symbol):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('DELETE FROM user_symbols WHERE user_id = ? AND symbol = ?', (user_id, symbol))
        await db.commit()
    await rebuild_watched_pairs(user_id)

async def clear_user_symbols(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('DELETE FROM user_symbols WHERE user_id = ?', (user_id,))
        await db.commit()
    await rebuild_watched_pairs(user_id)

# --- Watched Pairs (auto-generated from timeframes x symbols) ---

async def rebuild_watched_pairs(user_id):
    """Rebuild watched_pairs as cartesian product of user_timeframes x user_symbols."""
    timeframes = await get_user_timeframes(user_id)
    symbols = await get_user_symbols(user_id)
    
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('DELETE FROM watched_pairs WHERE user_id = ?', (user_id,))
        for sym in symbols:
            for tf in timeframes:
                await db.execute('INSERT OR IGNORE INTO watched_pairs (user_id, symbol, timeframe) VALUES (?, ?, ?)', (user_id, sym, tf))
        await db.commit()

async def get_watched_pairs(user_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM watched_pairs WHERE user_id = ?', (user_id,)) as cursor:
            return await cursor.fetchall()

async def get_all_watched_pairs():
    """Used by scanner to get all pairs watched by all users"""
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute('SELECT * FROM watched_pairs') as cursor:
            return await cursor.fetchall()

# --- Open Positions ---

async def add_open_position(user_id, exchange_name, symbol, side, entry_price, quantity, tp_price, sl_price, order_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('''
            INSERT INTO open_positions (user_id, exchange_name, symbol, side, entry_price, quantity, tp_price, sl_price, order_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, exchange_name, symbol, side, entry_price, quantity, tp_price, sl_price, order_id))
        await db.commit()

async def get_open_positions(user_id=None):
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if user_id:
            async with db.execute('SELECT * FROM open_positions WHERE user_id = ?', (user_id,)) as cursor:
                return await cursor.fetchall()
        else:
            async with db.execute('SELECT * FROM open_positions') as cursor:
                return await cursor.fetchall()

async def remove_open_position(pos_id):
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.execute('DELETE FROM open_positions WHERE id = ?', (pos_id,))
        await db.commit()
