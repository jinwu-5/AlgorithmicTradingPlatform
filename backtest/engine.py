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
    def __init__(self, strategies: List[Strategy], data_client: DataClient, initial_capital: float = 10000, db_path: str = "backtest.db"):
        if not strategies:
            raise ValueError("At least one strategy is required for backtesting")

        self.strategies = strategies
        self.data_client = data_client
        self.initial_capital = initial_capital
        self.db_manager = DatabaseManager(db_path)

    def run(self, lookback_days: int = 730) -> Dict:
        logger.info("Starting backtest for %s", ", ".join(strategy.symbol for strategy in self.strategies))

        history_map: Dict[str, pd.DataFrame] = {}
        active_strategies: Dict[str, Strategy] = {}
        for strategy in self.strategies:
            history_df = self.data_client.get_historical_bars(strategy.symbol, days=lookback_days)
            min_bars = getattr(strategy, "min_history_bars", getattr(strategy, "ma_period", 0))
            if history_df.empty or len(history_df) < min_bars:
                logger.error("Insufficient historical data for %s", strategy.symbol)
                continue

            history_map[strategy.symbol] = history_df
            active_strategies[strategy.symbol] = strategy

        if not active_strategies:
            logger.error("No strategies have enough historical data to run a backtest")
            return {}

        portfolio = PortfolioState(self.initial_capital, {}, self.initial_capital)
        execution_engine = SimulatedExecutionEngine(self.db_manager, slippage_pct=0.001)
        equity_curve = []
        trade_count = 0
        latest_prices: Dict[str, float] = {}

        # Build a combined event stream sorted by timestamp so trades for different
        # symbols share the same portfolio state progression.
        events = []
        for symbol, df in history_map.items():
            for timestamp in df.index:
                events.append((timestamp, symbol))
        events.sort()

        for timestamp, symbol in events:
            strategy = active_strategies[symbol]
            history_df = history_map[symbol]
            window = history_df.loc[:timestamp]

            min_bars = getattr(strategy, "min_history_bars", getattr(strategy, "ma_period", 0))
            if len(window) < min_bars:
                continue

            current_price = window["close"].iloc[-1]
            latest_prices[symbol] = current_price
            if symbol in portfolio.positions:
                portfolio.positions[symbol].current_price = current_price

            orders = strategy.on_bar(window, portfolio)
            trade_count += len(orders)

            for order in orders:
                portfolio = execution_engine.execute_order(order, current_price, portfolio)

            positions_value = 0.0
            for held_symbol, pos in portfolio.positions.items():
                if held_symbol in latest_prices:
                    pos.current_price = latest_prices[held_symbol]
                positions_value += pos.market_value
            portfolio.equity = portfolio.cash + positions_value

            equity_curve.append(
                {
                    "timestamp": timestamp,
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
