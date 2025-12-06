"""Backtesting utilities."""
from typing import Dict, List
import logging

import numpy as np
import pandas as pd

from data.base import DataClient
from database.manager import DatabaseManager
from execution.simulated import SimulatedExecutionEngine
from models.types import PortfolioState
from strategies.base import Strategy

logger = logging.getLogger(__name__)


class Backtester:
    def __init__(self, strategy: Strategy, data_client: DataClient, initial_capital: float = 10000, db_path: str = "backtest.db"):
        self.strategy = strategy
        self.data_client = data_client
        self.initial_capital = initial_capital
        self.db_manager = DatabaseManager(db_path)

    def run(self, lookback_days: int = 730) -> Dict:
        logger.info("Starting backtest for %s", self.strategy.symbol)

        history_df = self.data_client.get_historical_bars(self.strategy.symbol, days=lookback_days)
        min_bars = getattr(self.strategy, "min_history_bars", getattr(self.strategy, "ma_period", 0))
        if history_df.empty or len(history_df) < min_bars:
            logger.error("Insufficient historical data for backtest")
            return {}

        portfolio = PortfolioState(self.initial_capital, {}, self.initial_capital)
        execution_engine = SimulatedExecutionEngine(self.db_manager, slippage_pct=0.001)
        equity_curve = []
        trade_count = 0

        start_index = min_bars if min_bars > 0 else 0
        for i in range(start_index, len(history_df)):
            window = history_df.iloc[: i + 1]
            current_price = window["close"].iloc[-1]

            for pos in portfolio.positions.values():
                pos.current_price = current_price

            orders = self.strategy.on_bar(window, portfolio)

            # Count how many trades we’re placing at this bar
            trade_count += len(orders)

            for order in orders:
                trade_time = window.index[-1]
                recent_prices = window[["close"]].tail(5)
                print(
                    f"\n[Backtest] {trade_time} -> {order.side.value.upper()} {order.quantity} {order.symbol} @ ${current_price:0.2f}")
                print("Recent closes before trade:\n", recent_prices)
                print("Strategy window snapshot (last 5 bars):\n", window.tail(5))
                portfolio = execution_engine.execute_order(order, current_price, portfolio)

            positions_value = sum(pos.market_value for pos in portfolio.positions.values())
            portfolio.equity = portfolio.cash + positions_value

            equity_curve.append(
                {
                    "timestamp": window.index[-1],
                    "equity": portfolio.equity,
                    "cash": portfolio.cash,
                    "positions_value": positions_value,
                }
            )

        metrics = self._calculate_metrics(equity_curve, trade_count)
        logger.info("=" * 60)
        logger.info("BACKTEST RESULTS")
        logger.info("=" * 60)
        for key, value in metrics.items():
            logger.info("%s: %s", key, value)
        logger.info("=" * 60)
        return metrics

    def _calculate_metrics(self, equity_curve: List[Dict], total_trades: int) -> Dict:
        if not equity_curve:
            return {}

        df = pd.DataFrame(equity_curve)
        df["returns"] = df["equity"].pct_change()

        final_equity = df["equity"].iloc[-1]
        total_return = ((final_equity - self.initial_capital) / self.initial_capital) * 100

        df["cummax"] = df["equity"].cummax()
        df["drawdown"] = (df["equity"] - df["cummax"]) / df["cummax"] * 100
        max_drawdown = df["drawdown"].min()

        sharpe = 0
        if df["returns"].std() > 0:
            sharpe = (df["returns"].mean() / df["returns"].std()) * np.sqrt(252)

        return {
            "Initial Capital": f"${self.initial_capital:,.2f}",
            "Final Equity": f"${final_equity:,.2f}",
            "Total Return": f"{total_return:.2f}%",
            "Max Drawdown": f"{max_drawdown:.2f}%",
            "Sharpe Ratio": f"{sharpe:.2f}",
            "Total Trades": total_trades,
            "Completed Trades": total_trades // 2,
        }

