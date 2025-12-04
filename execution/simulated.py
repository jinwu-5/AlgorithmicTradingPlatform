"""Simulated execution engine for backtests and paper trading."""
import logging

from database.manager import DatabaseManager
from execution.base import ExecutionEngine
from models.types import Order, OrderSide, PortfolioState, Position

logger = logging.getLogger(__name__)


class SimulatedExecutionEngine(ExecutionEngine):
    def __init__(self, db_manager: DatabaseManager, slippage_pct: float = 0.001):
        self.db_manager = db_manager
        self.slippage_pct = slippage_pct

    def execute_order(self, order: Order, current_price: float, portfolio: PortfolioState) -> PortfolioState:
        execution_price = current_price * (1 + self.slippage_pct if order.side == OrderSide.BUY else 1 - self.slippage_pct)
        position = portfolio.get_position(order.symbol)

        if order.side == OrderSide.BUY:
            cost = execution_price * order.quantity
            if cost > portfolio.cash:
                logger.warning("Insufficient cash: need $%0.2f, have $%0.2f", cost, portfolio.cash)
                return portfolio

            new_quantity = position.quantity + order.quantity
            new_avg_price = 0.0
            if new_quantity > 0:
                new_avg_price = ((position.avg_price * position.quantity) + (execution_price * order.quantity)) / new_quantity

            portfolio.positions[order.symbol] = Position(order.symbol, new_quantity, new_avg_price, current_price)
            portfolio.cash -= cost

            self.db_manager.log_trade(order.symbol, "BUY", order.quantity, execution_price, 0)
            logger.info("EXECUTED BUY: %s %s @ $%0.2f (Cost: $%0.2f)", order.quantity, order.symbol, execution_price, cost)

        elif order.side == OrderSide.SELL:
            if order.quantity > position.quantity:
                logger.warning(
                    "Insufficient position: trying to sell %s, have %s", order.quantity, position.quantity
                )
                return portfolio

            proceeds = execution_price * order.quantity
            pnl = (execution_price - position.avg_price) * order.quantity

            new_quantity = position.quantity - order.quantity
            if new_quantity > 0:
                portfolio.positions[order.symbol] = Position(order.symbol, new_quantity, position.avg_price, current_price)
            else:
                portfolio.positions.pop(order.symbol, None)

            portfolio.cash += proceeds

            self.db_manager.log_trade(order.symbol, "SELL", order.quantity, execution_price, pnl)
            logger.info(
                "EXECUTED SELL: %s %s @ $%0.2f (Proceeds: $%0.2f, PnL: $%0.2f)",
                order.quantity,
                order.symbol,
                execution_price,
                proceeds,
                pnl,
            )

        portfolio.equity = portfolio.cash + sum(pos.market_value for pos in portfolio.positions.values())
        return portfolio
