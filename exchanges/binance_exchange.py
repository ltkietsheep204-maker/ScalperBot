import ccxt.async_support as ccxt
from .base_exchange import BaseExchange

class BinanceExchange(BaseExchange):
    def __init__(self, api_key, api_secret, passphrase=None):
        super().__init__(api_key, api_secret, passphrase)
        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',
            }
        })

    async def initialize(self):
        await self.exchange.load_markets()

    async def get_futures_symbols(self):
        symbols = []
        for symbol, market in self.exchange.markets.items():  # type: ignore[union-attr]
             if market['future'] or market['swap'] or market['linear']:
                  # Filter for USDT-M futures only
                  if market['quote'] == 'USDT':
                      symbols.append(symbol)
        return symbols

    async def get_klines(self, symbol, interval, limit=200):
        # binance uses generic ccxt timeframe 1m, 3m, 5m etc
        ohlcv = await self.exchange.fetch_ohlcv(symbol, interval, limit=limit)
        return ohlcv

    async def set_leverage(self, symbol, leverage):
        try:
             await self.exchange.set_leverage(leverage, symbol)
             return True
        except Exception as e:
             print(f"Binance set_leverage error: {e}")
             return False

    async def set_margin_mode(self, symbol, mode):
        try:
            # ccxt standardizes this for some exchanges, but binance has set_margin_mode
            await self.exchange.fapiPrivatePostMarginType({
                 'symbol': self.exchange.market_id(symbol),
                 'marginType': 'ISOLATED' if mode.lower() == 'isolated' else 'CROSSED'
            })
            return True
        except Exception as e:
            if 'No need to change margin type' in str(e):
                return True
            print(f"Binance set_margin_mode error: {e}")
            return False

    async def open_position(self, symbol, side, quantity, leverage, margin_mode):
        await self.set_margin_mode(symbol, margin_mode)
        await self.set_leverage(symbol, leverage)
        
        # side: 'LONG' -> buy, 'SHORT' -> sell
        # binance mode: One-way by default, or hedge
        order_side = 'buy' if side == 'LONG' else 'sell'
        
        return await self.exchange.create_market_order(symbol, order_side, quantity)

    async def close_position(self, symbol, side):
        # We need to find the open position size
        positions = await self.exchange.fetch_positions([symbol])
        for p in positions:
            if p['symbol'] == symbol and float(p['contracts']) > 0:
                amount = p['contracts']
                # To close a position in one-way mode, we do the opposite side
                close_side = 'sell' if p['side'] == 'long' else 'buy'
                return await self.exchange.create_market_order(symbol, close_side, amount, params={'reduceOnly': True})
        return None

    async def get_balance(self):
        balance = await self.exchange.fetch_balance()
        return balance['total'].get('USDT', 0.0)

    async def close_connection(self):
        await self.exchange.close()
