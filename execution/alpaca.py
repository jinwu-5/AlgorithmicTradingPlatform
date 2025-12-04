"""Live execution engine backed by Alpaca."""
import logging
from typing import Optional

from database.manager import DatabaseManager
from execution.base import ExecutionEngine
from models.types import Order, PortfolioState

logger = logging.getLogger(__name__)


class AlpacaExecutionEngine(ExecutionEngine):
    def __init__(self, api_key: str, api_secret: str, paper: bool = True, db_manager: Optional[DatabaseManager] = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.db_manager = db_manager

        import requests

        self.session = requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            }
        )

    def execute_order(self, order: Order, current_price: float, portfolio: PortfolioState) -> PortfolioState:
        url = f"{self.base_url}/v2/orders"
        payload = {
            "symbol": order.symbol,
            "qty": order.quantity,
            "side": order.side.value,
            "type": order.order_type.value,
            "time_in_force": "day",
        }

        try:
            response = self.session.post(url, json=payload)
            response.raise_for_status()
            order_data = response.json()

            logger.info("Order submitted to Alpaca: %s", order_data.get("id"))

            if self.db_manager:
                self.db_manager.log_trade(order.symbol, order.side.value.upper(), order.quantity, current_price, 0)
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error executing order via Alpaca: %s", exc)

        return portfolio
