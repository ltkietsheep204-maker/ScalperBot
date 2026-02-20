from .base_exchange import BaseExchange
from .binance_exchange import BinanceExchange
from .bingx_exchange import BingxExchange
from .bybit_exchange import BybitExchange
from .mexc_exchange import MexcExchange
from .okx_exchange import OkxExchange

def get_exchange_instance(exchange_name, api_key, api_secret, passphrase=None):
    exchanges = {
        "Binance": BinanceExchange,
        "BingX": BingxExchange,
        "Bybit": BybitExchange,
        "MEXC": MexcExchange,
        "OKX": OkxExchange
    }
    
    cls = exchanges.get(exchange_name)
    if cls:
         return cls(api_key, api_secret, passphrase)
    return None
