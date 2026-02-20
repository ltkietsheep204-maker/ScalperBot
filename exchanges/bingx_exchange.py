import ccxt.async_support as ccxt
from .base_exchange import BaseExchange

class BingxExchange(BaseExchange):
    def __init__(self, api_key, api_secret, passphrase=None):
        super().__init__(api_key, api_secret, passphrase)
        self.exchange = ccxt.bingx({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap', # BingX standard/perpetual futures
            }
        })

    async def initialize(self):
        await self.exchange.load_markets()

    async def get_futures_symbols(self):
        symbols = []
        for symbol, market in self.exchange.markets.items():  # type: ignore[union-attr]
            if market.get('swap') and market.get('quote') == 'USDT':
                 symbols.append(symbol)
        return symbols

    async def get_klines(self, symbol, interval, limit=200):
        ohlcv = await self.exchange.fetch_ohlcv(symbol, interval, limit=limit)
        return ohlcv

    async def set_leverage(self, symbol, leverage):
        try:
             await self.exchange.set_leverage(leverage, symbol)
             return True
        except Exception as e:
             print(f"BingX set_leverage error: {e}")
             return False

    async def set_margin_mode(self, symbol, mode):
        try:
             await self.exchange.set_margin_mode(mode.upper(), symbol)
             return True
        except Exception as e:
             print(f"BingX set_margin_mode error: {e}")
             return False

    async def open_position(self, symbol, side, quantity, leverage, margin_mode):
        await self.set_margin_mode(symbol, margin_mode)
        await self.set_leverage(symbol, leverage)
        
        # side: 'LONG' -> buy, 'SHORT' -> sell
        order_side = 'buy' if side == 'LONG' else 'sell'
        
        params = {}
        # BUG FIX 5: BingX POSITION SIDE HEDGE MODE
        params['positionSide'] = 'LONG' if side == 'LONG' else 'SHORT'
        
        return await self.exchange.create_market_order(symbol, order_side, quantity, params=params)

    async def close_position(self, symbol, side):
        positions = await self.exchange.fetch_positions([symbol])
        for p in positions:
            if p['symbol'] == symbol and float(p['contracts']) > 0:
                amount = p['contracts']
                close_side = 'sell' if p['side'] == 'long' else 'buy'
                
                params = {'positionSide': p['side'].upper()}
                return await self.exchange.create_market_order(symbol, close_side, amount, params=params)
        return None

    async def get_balance(self):
        balance = await self.exchange.fetch_balance()
        return balance['total'].get('USDT', 0.0)

    async def close_connection(self):
        await self.exchange.close()
