from abc import ABC, abstractmethod
from typing import Any, Optional

class BaseExchange(ABC):
    def __init__(self, api_key: str, api_secret: str, passphrase: Optional[str] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection"""
        ...

    @abstractmethod
    async def get_futures_symbols(self) -> list:
        """Return list of available futures symbols (e.g. ['BTC/USDT:USDT', ...])"""
        ...

    @abstractmethod
    async def get_klines(self, symbol: str, interval: str, limit: int = 200) -> list:
        """
        Return list of OHLCV data. 
        Format: [[timestamp, open, high, low, close, volume], ...]
        """
        ...

    @abstractmethod
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Set leverage for a symbol"""
        ...

    @abstractmethod
    async def set_margin_mode(self, symbol: str, mode: str) -> bool:
        """Set margin mode: 'cross' or 'isolated'"""
        ...

    @abstractmethod
    async def open_position(self, symbol: str, side: str, quantity: float, leverage: int, margin_mode: str) -> Any:
        """
        Open a new position.
        Side: 'LONG' or 'SHORT'
        Return dict with order ID and details.
        """
        ...

    @abstractmethod
    async def close_position(self, symbol: str, side: str) -> Any:
        """
        Close existing position.
        Side: 'LONG' or 'SHORT'
        """
        ...

    @abstractmethod
    async def get_balance(self) -> float:
        """Return USDT balance"""
        ...
        
    @abstractmethod
    async def close_connection(self) -> None:
        """Close connections to exchange"""
        ...
