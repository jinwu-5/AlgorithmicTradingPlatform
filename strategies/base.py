"""Strategy abstraction."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from models.types import Order, PortfolioState


@dataclass
class IndicatorPanel:
    """Metadata describing how to plot a derived indicator series."""

    title: str
    data: pd.DataFrame
    overlay_on_price: bool = False
    horizontal_lines: Optional[Dict[str, float]] = None


class Strategy(ABC):
    def __init__(self, symbol: str):
        self.symbol = symbol

    @abstractmethod
    def on_bar(self, history_df: pd.DataFrame, portfolio: PortfolioState) -> List[Order]:
        """Return a list of desired orders for the latest bar."""

    def build_indicator_panels(self, history_df: pd.DataFrame) -> List[IndicatorPanel]:
        """Return indicator data to visualize alongside the price series."""
        return []
