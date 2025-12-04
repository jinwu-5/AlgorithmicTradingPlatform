"""Execution engine abstraction."""
from abc import ABC, abstractmethod

from models.types import Order, PortfolioState


class ExecutionEngine(ABC):
    @abstractmethod
    def execute_order(self, order: Order, current_price: float, portfolio: PortfolioState) -> PortfolioState:
        """Execute the provided order and return the updated portfolio state."""
