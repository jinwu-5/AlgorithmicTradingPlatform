"""Simple moving-average trend following strategy."""
from typing import List
import logging

import pandas as pd

from models.types import Order, OrderSide, OrderType, PortfolioState
from strategies.base import Strategy

logger = logging.getLogger(__name__)


class TrendFollowingStrategy(Strategy):
    def __init__(self, symbol: str, ma_period: int = 200, risk_per_trade_pct: float = 0.02):
        super().__init__(symbol)
        self.ma_period = ma_period
        self.risk_per_trade_pct = risk_per_trade_pct
        logger.info("Initialized TrendFollowingStrategy for %s with MA=%s", symbol, ma_period)

    def on_bar(self, history_df: pd.DataFrame, portfolio: PortfolioState) -> List[Order]:
        if len(history_df) < self.ma_period:
            logger.warning("Not enough data: %s bars, need %s", len(history_df), self.ma_period)
            return []

        history_df = history_df.copy()
        history_df["ma200"] = history_df["close"].rolling(self.ma_period).mean()

        current_price = history_df["close"].iloc[-1]
        ma200 = history_df["ma200"].iloc[-1]

        if pd.isna(ma200):
            logger.warning("MA%d is NaN", self.ma_period)
            return []

        position = portfolio.get_position(self.symbol)
        orders: List[Order] = []

        if current_price > ma200 and position.quantity == 0:
            size = self._calculate_position_size(portfolio, current_price)
            if size > 0:
                orders.append(Order(self.symbol, OrderSide.BUY, size, OrderType.MARKET))
                logger.info(
                    "BUY SIGNAL: %s @ $%0.2f (MA%d: $%0.2f) - Qty: %s",
                    self.symbol,
                    current_price,
                    self.ma_period,
                    ma200,
                    size,
                )
        elif current_price < ma200 and position.quantity > 0:
            orders.append(Order(self.symbol, OrderSide.SELL, position.quantity, OrderType.MARKET))
            logger.info(
                "SELL SIGNAL: %s @ $%0.2f (MA%d: $%0.2f) - Qty: %s",
                self.symbol,
                current_price,
                self.ma_period,
                ma200,
                position.quantity,
            )

        return orders

    def _calculate_position_size(self, portfolio: PortfolioState, price: float) -> float:
        max_position_value = portfolio.cash * 0.95
        shares = int(max_position_value / price)
        return shares
