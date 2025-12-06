"""RSI + Bollinger Bands mean reversion strategy."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List
import logging

import pandas as pd

from models.types import Order, OrderSide, OrderType, PortfolioState
from strategies.base import Strategy

logger = logging.getLogger(__name__)


@dataclass
class StrategyThresholds:
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    rsi_period: int = 14
    oversold_rsi: float = 30
    exit_rsi: float = 55
    allocation_pct: float = 0.5


class RSIBollingerMeanReversionStrategy(Strategy):
    def __init__(self, symbol: str, thresholds: StrategyThresholds | None = None):
        super().__init__(symbol)
        self.thresholds = thresholds or StrategyThresholds()
        self.min_history_bars = max(self.thresholds.bollinger_period, self.thresholds.rsi_period) + 5
        logger.info(
            "Initialized RSI+Bollinger strategy for %s (BB=%s/%s, RSI=%s)",
            symbol,
            self.thresholds.bollinger_period,
            self.thresholds.bollinger_std,
            self.thresholds.rsi_period,
        )

    def on_bar(self, history_df: pd.DataFrame, portfolio: PortfolioState) -> List[Order]:
        if len(history_df) < self.min_history_bars:
            logger.warning("Need %s bars, have %s", self.min_history_bars, len(history_df))
            return []

        df = history_df[["close"]].copy()
        df["middle"] = df["close"].rolling(self.thresholds.bollinger_period).mean()
        df["std"] = df["close"].rolling(self.thresholds.bollinger_period).std()
        df["upper"] = df["middle"] + self.thresholds.bollinger_std * df["std"]
        df["lower"] = df["middle"] - self.thresholds.bollinger_std * df["std"]
        df["rsi"] = self._compute_rsi(df["close"], self.thresholds.rsi_period)

        latest = df.iloc[-1]
        if any(pd.isna(val) for val in latest[["middle", "upper", "lower", "rsi"]]):
            logger.warning("Indicators not ready yet for %s", self.symbol)
            return []

        current_price = latest["close"]
        position = portfolio.get_position(self.symbol)
        orders: List[Order] = []

        if position.quantity == 0:
            if current_price <= latest["lower"] and latest["rsi"] <= self.thresholds.oversold_rsi:
                quantity = self._position_size(portfolio, current_price)
                if quantity > 0:
                    orders.append(Order(self.symbol, OrderSide.BUY, quantity, OrderType.MARKET))
                    logger.info(
                        "BUY SIGNAL: %s price=$%0.2f lower=$%0.2f rsi=%0.1f qty=%s",
                        self.symbol,
                        current_price,
                        latest["lower"],
                        latest["rsi"],
                        quantity,
                    )
        else:
            if current_price >= latest["middle"] or latest["rsi"] >= self.thresholds.exit_rsi:
                orders.append(Order(self.symbol, OrderSide.SELL, position.quantity, OrderType.MARKET))
                logger.info(
                    "EXIT SIGNAL: %s price=$%0.2f middle=$%0.2f rsi=%0.1f qty=%s",
                    self.symbol,
                    current_price,
                    latest["middle"],
                    latest["rsi"],
                    position.quantity,
                )

        return orders

    def _position_size(self, portfolio: PortfolioState, price: float) -> float:
        allocation = portfolio.cash * self.thresholds.allocation_pct
        if allocation <= 0:
            return 0.0
        quantity = allocation / price
        return round(quantity, 6)

    def _compute_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        delta = prices.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()

        # Avoid division by zero
        rs = avg_gain / avg_loss.replace(0, pd.NA)

        rsi = 100 - (100 / (1 + rs))

        # Use bfill() instead of deprecated fillna(method="bfill")
        return rsi.bfill()

