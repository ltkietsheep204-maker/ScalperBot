import logging
import ccxt.async_support as ccxt

logger = logging.getLogger(__name__)

# Comprehensive list of all Binance USDT-M Futures symbols (as of 2025)
# This is the fallback when API is unavailable (e.g. geo-blocked)
HARDCODED_BINANCE_FUTURES = [
    "1000BONK","1000FLOKI","1000LUNC","1000PEPE","1000RATS","1000SATS","1000SHIB","1000XEC",
    "1INCH","AAVE","ACE","ACH","ADA","AEVO","AGLD","AI","AKRO","ALGO","ALICE","ALPHA",
    "ALT","AMB","ANKR","ANT","APE","API3","APT","AR","ARB","ARKM","ASTR","ATA",
    "ATOM","AUCTION","AVAX","AXL","AXS",
    "BADGER","BAKE","BAL","BANANA","BAND","BAT","BB","BCH","BEAMX","BEL","BICO",
    "BIGTIME","BLUR","BLZ","BNB","BNT","BNX","BOME","BOND","BONK","BTC","BTCDOM",
    "C98","CAKE","CELO","CELR","CFX","CHR","CHZ","CKB","COMBO","COMP","CORE",
    "COTI","CRV","CTK","CTSI","CYBER","CVX",
    "DAR","DASH","DEFI","DENT","DGB","DODO","DOGE","DOT","DRIFT","DUSK","DYDX",
    "EDU","EGLD","ENA","ENJ","ENS","EOS","ETC","ETH","ETHFI","ETHW",
    "FET","FIL","FLOKI","FLOW","FLR","FORTH","FRONT","FTM","FXS",
    "GAL","GALA","GAS","GLMR","GLM","GMT","GMX","GNS","GRT","GTC",
    "HBAR","HFT","HIFI","HIGH","HOOK","HOT","ICP","ICX","ID","ILV","IMX",
    "INJ","IOST","IOTA","IOTX",
    "JASMY","JOE","JTO","JUP","KAVA","KEY","KLAY","KNC","KSM",
    "LDO","LEVER","LINA","LINK","LIT","LOOKS","LPT","LQTY","LRC","LSK","LTC","LUNA2","LUNC",
    "MAGIC","MANA","MANTA","MASK","MATIC","MAV","MBL","MEME","METIS","MINA","MKR",
    "MOVR","MTL","MULTI","MYRO",
    "NEAR","NEO","NFP","NKN","NMR","NOT","NTRN","NULS",
    "OCEAN","OGN","OMG","OMNI","ONE","ONG","ONT","OP","ORBS","ORDI","OXT",
    "PAXG","PENDLE","PEOPLE","PEPE","PERP","PHB","PIXEL","POLYX","PORTAL","POWR","PYTH",
    "QI","QNT","QTUM",
    "RARE","RARI","RDNT","REEF","REN","REZ","RIF","RLC","RNDR","RONIN","ROSE","RSR","RUNE",
    "SAGA","SAND","SEI","SFP","SKL","SLP","SNT","SNX","SOL","SPELL","SSV","STEEM","STG",
    "STMX","STORJ","STRAX","STRK","STX","SUI","SUN","SUPER","SUSHI","SWELL","SXP",
    "TAO","THETA","TIA","TLM","TOKEN","TON","TRB","TRU","TRX","TURBO","TWT",
    "UMA","UNI","USDC","USTC",
    "VET","VIDT","VOXEL",
    "W","WAXP","WIF","WLD","WOO",
    "XAI","XEM","XLM","XMR","XRP","XTZ","XVG","XVS",
    "YFI","YGG",
    "ZEC","ZEN","ZETA","ZIL","ZK","ZRO","ZRX",
]

# In-memory cache
_cached_symbols = []
_symbol_map = {}

async def load_binance_futures_symbols():
    """Try to fetch live data from Binance, fallback to hardcoded list."""
    global _cached_symbols, _symbol_map
    
    # Try live fetch first
    try:
        exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        try:
            await exchange.load_markets()
            symbols = []
            symbol_map = {}
            for symbol, market in exchange.markets.items():  # type: ignore[union-attr]
                if (market.get('future') or market.get('swap') or market.get('linear')) \
                   and market.get('quote') == 'USDT' and market.get('active', True):
                    short_name = symbol.split("/")[0]
                    if short_name not in symbol_map:
                        symbol_map[short_name] = symbol
                        symbols.append(short_name)
            
            symbols.sort()
            _cached_symbols = symbols
            _symbol_map = symbol_map
            logger.info(f"Live loaded {len(symbols)} Binance futures symbols.")
            return
        finally:
            await exchange.close()
    except Exception as e:
        logger.warning(f"Cannot fetch live Binance data ({e}), using hardcoded list.")
    
    # Fallback: use hardcoded list
    _cached_symbols = sorted(HARDCODED_BINANCE_FUTURES)
    _symbol_map = {s: f"{s}/USDT:USDT" for s in _cached_symbols}
    logger.info(f"Using hardcoded list: {len(_cached_symbols)} Binance futures symbols.")

def get_all_short_names():
    """Return cached list of short names like ['1INCH', 'AAVE', 'ADA', ...]"""
    return _cached_symbols

def get_full_symbol(short_name):
    """Convert short name back to full CCXT symbol, e.g. 'BTC' -> 'BTC/USDT:USDT'"""
    return _symbol_map.get(short_name, f"{short_name}/USDT:USDT")

def get_available_letters():
    """Return sorted list of unique first letters from cached symbols."""
    letters = sorted(set(s[0].upper() for s in _cached_symbols if _cached_symbols))
    return letters

def get_symbols_by_letter(letter):
    """Return all short symbol names starting with the given letter."""
    return [s for s in _cached_symbols if s[0].upper() == letter.upper()]
