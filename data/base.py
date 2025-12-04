"""Abstract data client definitions."""
from abc import ABC, abstractmethod

import pandas as pd


class DataClient(ABC):
    @abstractmethod
    def get_historical_bars(self, symbol: str, days: int) -> pd.DataFrame:
        """Return OHLCV data for the symbol."""

    @abstractmethod
    def get_latest_price(self, symbol: str) -> float:
        """Return the latest trade price."""
