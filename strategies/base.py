"""Strategy abstraction."""
from abc import ABC, abstractmethod
from typing import List

import pandas as pd

from models.types import Order, PortfolioState


class Strategy(ABC):
    def __init__(self, symbol: str):
        self.symbol = symbol

    @abstractmethod
    def on_bar(self, history_df: pd.DataFrame, portfolio: PortfolioState) -> List[Order]:
        """Return a list of desired orders for the latest bar."""
