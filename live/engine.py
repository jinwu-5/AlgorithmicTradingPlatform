"""Live trading orchestration."""
from datetime import datetime
import logging
from typing import Optional

from data.base import DataClient
from database.manager import DatabaseManager
from execution.base import ExecutionEngine
from models.types import TradingMode
from strategies.base import Strategy

logger = logging.getLogger(__name__)


class LiveTradingEngine:
    def __init__(
        self,
        strategy: Strategy,
        data_client: DataClient,
        execution_engine: ExecutionEngine,
        mode: TradingMode = TradingMode.PAPER,
        initial_capital: float = 10000,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.strategy = strategy
        self.data_client = data_client
        self.execution_engine = execution_engine
        self.mode = mode
        self.db_manager = db_manager or DatabaseManager(f"{mode.value}_trading.db")
        self.portfolio = self.db_manager.load_portfolio(initial_capital)

        logger.info("Live Trading Engine initialized in %s mode", mode.value.upper())
        logger.info("Portfolio: Cash=$%0.2f, Equity=$%0.2f", self.portfolio.cash, self.portfolio.equity)

    def run_iteration(self, lookback_days: int = 300) -> None:
        logger.info("%s", "=" * 60)
        logger.info("Running %s iteration at %s", self.mode.value.upper(), datetime.now())
        logger.info("%s", "=" * 60)

        try:
            history_df = self.data_client.get_historical_bars(self.strategy.symbol, days=lookback_days)
            if history_df.empty:
                logger.error("No historical data available")
                return

            current_price = self.data_client.get_latest_price(self.strategy.symbol)
            if current_price == 0:
                logger.error("Could not fetch current price")
                return

            for pos in self.portfolio.positions.values():
                pos.current_price = current_price

            logger.info("Current Price: $%0.2f", current_price)
            logger.info("Cash: $%0.2f", self.portfolio.cash)

            position = self.portfolio.get_position(self.strategy.symbol)
            if position.quantity > 0:
                logger.info("Position: %s shares @ $%0.2f", position.quantity, position.avg_price)
                logger.info(
                    "Unrealized P&L: $%0.2f (%0.2f%%)",
                    position.unrealized_pnl,
                    position.unrealized_pnl_pct,
                )

            orders = self.strategy.on_bar(history_df, self.portfolio)
            for order in orders:
                self.portfolio = self.execution_engine.execute_order(order, current_price, self.portfolio)

            positions_value = sum(pos.market_value for pos in self.portfolio.positions.values())
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
