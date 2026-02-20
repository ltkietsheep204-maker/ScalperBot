import ccxt.async_support as ccxt
from .base_exchange import BaseExchange

class BybitExchange(BaseExchange):
    def __init__(self, api_key, api_secret, passphrase=None):
        super().__init__(api_key, api_secret, passphrase)
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future', # USDT perp
            }
        })

    async def initialize(self):
        await self.exchange.load_markets()

    async def get_futures_symbols(self):
        symbols = []
        for symbol, market in self.exchange.markets.items():  # type: ignore[union-attr]
            if market.get('linear') and market.get('quote') == 'USDT':
                 symbols.append(symbol)
        return symbols

    async def get_klines(self, symbol, interval, limit=200):
        # ccxt normalizes interval for bybit
        ohlcv = await self.exchange.fetch_ohlcv(symbol, interval, limit=limit)
        return ohlcv

    async def set_leverage(self, symbol, leverage):
        try:
             await self.exchange.set_leverage(leverage, symbol)
             return True
        except Exception as e:
             if 'leverage not modified' in str(e).lower():
                 return True
             print(f"Bybit set_leverage error: {e}")
             return False

    async def set_margin_mode(self, symbol, mode):
        try:
             await self.exchange.set_margin_mode(mode.lower(), symbol)
             return True
        except Exception as e:
             if 'margin mode not modified' in str(e).lower():
                 return True
             print(f"Bybit set_margin_mode error: {e}")
             return False

    async def open_position(self, symbol, side, quantity, leverage, margin_mode):
        await self.set_margin_mode(symbol, margin_mode)
        await self.set_leverage(symbol, leverage)
        
        # side: 'LONG' -> buy, 'SHORT' -> sell
        order_side = 'buy' if side == 'LONG' else 'sell'
        
        params = {}
        # Bybit also has position_idx for hedge mode (0: One-Way, 1: Buy side, 2: Sell side)
        # Assuming one-way mode for Bybit by default, or CCXT handles it
        
        return await self.exchange.create_market_order(symbol, order_side, quantity, params=params)

    async def close_position(self, symbol, side):
        positions = await self.exchange.fetch_positions([symbol])
        for p in positions:
            if p['symbol'] == symbol and float(p['contracts']) > 0:
                amount = p['contracts']
                close_side = 'sell' if p['side'] == 'long' else 'buy'
                
                return await self.exchange.create_market_order(symbol, close_side, amount, params={'reduceOnly': True})
        return None

    async def get_balance(self):
        balance = await self.exchange.fetch_balance()
        return balance['total'].get('USDT', 0.0)

    async def close_connection(self):
        await self.exchange.close()
