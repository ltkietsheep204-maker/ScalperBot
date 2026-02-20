import ccxt.async_support as ccxt
from .base_exchange import BaseExchange

class OkxExchange(BaseExchange):
    def __init__(self, api_key, api_secret, passphrase=None):
        super().__init__(api_key, api_secret, passphrase)
        self.exchange = ccxt.okx({
            'apiKey': api_key,
            'secret': api_secret,
            'password': passphrase, # OKX uses password for passphrase
            'enableRateLimit': True,
            'options': {
                'defaultType': 'swap', 
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
             print(f"OKX set_leverage error: {e}")
             return False

    async def set_margin_mode(self, symbol, mode):
        # OKX margin mode is set per order actually, or through account config
        return True

    async def open_position(self, symbol, side, quantity, leverage, margin_mode):
        await self.set_leverage(symbol, leverage)
        
        order_side = 'buy' if side == 'LONG' else 'sell'
        
        params = {
             'tdMode': 'isolated' if margin_mode.lower() == 'isolated' else 'cross'
        }
        
        return await self.exchange.create_market_order(symbol, order_side, quantity, params=params)

    async def close_position(self, symbol, side):
        positions = await self.exchange.fetch_positions([symbol])
        for p in positions:
            if p['symbol'] == symbol and float(p['contracts']) > 0:
                amount = p['contracts']
                close_side = 'sell' if p['side'] == 'long' else 'buy'
                
                params = {
                     'tdMode': p.get('marginMode', 'isolated'),
                     'reduceOnly': True
                }
                
                return await self.exchange.create_market_order(symbol, close_side, amount, params=params)
        return None

    async def get_balance(self):
        balance = await self.exchange.fetch_balance()
        return balance['total'].get('USDT', 0.0)

    async def close_connection(self):
        await self.exchange.close()
