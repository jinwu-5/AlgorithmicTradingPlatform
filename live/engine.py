"""Live trading orchestration."""
from datetime import datetime
import logging
from typing import List, Optional

from data.base import DataClient
from database.manager import DatabaseManager
from execution.base import ExecutionEngine
from models.types import TradingMode
from strategies.base import Strategy

logger = logging.getLogger(__name__)


class LiveTradingEngine:
    def __init__(
        self,
        strategies: List[Strategy],
        data_client: DataClient,
        execution_engine: ExecutionEngine,
        mode: TradingMode = TradingMode.PAPER,
        initial_capital: float = 10000,
        db_manager: Optional[DatabaseManager] = None,
    ):
        if not strategies:
            raise ValueError("At least one strategy is required for live trading")

        self.strategies = strategies
        self.data_client = data_client
        self.execution_engine = execution_engine
        self.mode = mode
        self.db_manager = db_manager or DatabaseManager(f"{mode.value}_trading.db")
        self.portfolio = self.db_manager.load_portfolio(initial_capital)

        logger.info(
            "Live Trading Engine initialized in %s mode for symbols: %s",
            mode.value.upper(),
            ", ".join(strategy.symbol for strategy in strategies),
        )
        logger.info("Portfolio: Cash=$%0.2f, Equity=$%0.2f", self.portfolio.cash, self.portfolio.equity)

    def run_iteration(self, lookback_days: int = 300) -> None:
        logger.info("%s", "=" * 60)
        logger.info("Running %s iteration at %s", self.mode.value.upper(), datetime.now())
        logger.info("%s", "=" * 60)

        try:
            latest_prices = {}
            for strategy in self.strategies:
                history_df = self.data_client.get_historical_bars(strategy.symbol, days=lookback_days)
                if history_df.empty:
                    logger.error("No historical data available for %s", strategy.symbol)
                    continue

                current_price = self.data_client.get_latest_price(strategy.symbol)
                if current_price == 0:
                    logger.error("Could not fetch current price for %s", strategy.symbol)
                    continue

                latest_prices[strategy.symbol] = current_price
                if strategy.symbol in self.portfolio.positions:
                    self.portfolio.positions[strategy.symbol].current_price = current_price

                logger.info("Current Price %s: $%0.2f", strategy.symbol, current_price)
                logger.info("Cash: $%0.2f", self.portfolio.cash)

                position = self.portfolio.get_position(strategy.symbol)
                if position.quantity > 0:
                    logger.info("Position %s: %s @ $%0.2f", strategy.symbol, position.quantity, position.avg_price)
                    logger.info(
                        "Unrealized P&L %s: $%0.2f (%0.2f%%)",
                        strategy.symbol,
                        position.unrealized_pnl,
                        position.unrealized_pnl_pct,
                    )

                orders = strategy.on_bar(history_df, self.portfolio)
                for order in orders:
                    self.portfolio = self.execution_engine.execute_order(order, current_price, self.portfolio)

            positions_value = 0.0
            for symbol, pos in self.portfolio.positions.items():
                if symbol in latest_prices:
                    pos.current_price = latest_prices[symbol]
                positions_value += pos.market_value

            self.portfolio.equity = self.portfolio.cash + positions_value

            self.db_manager.save_portfolio(self.portfolio)
            self.db_manager.log_equity(self.portfolio.equity, self.portfolio.cash, positions_value)

            logger.info("Portfolio Equity: $%0.2f", self.portfolio.equity)
            logger.info("%s\n", "=" * 60)
        except Exception as exc:  # pragma: no cover - runtime safety
            logger.error("Error in trading iteration: %s", exc, exc_info=True)

    def start_scheduler(self, run_time: str = "16:30") -> None:
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler = BlockingScheduler()
        hour, minute = map(int, run_time.split(":"))

        scheduler.add_job(
            self.run_iteration,
            "cron",
            hour=hour,
            minute=minute,
            day_of_week="mon-fri",
        )

        logger.info("Scheduler started. Will run daily at %s (Mon-Fri)", run_time)
        logger.info("Press Ctrl+C to stop")

        try:
            scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            logger.info("Scheduler stopped")
