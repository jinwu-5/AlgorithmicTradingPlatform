"""Live execution engine backed by Coinbase Advanced Trade."""
from __future__ import annotations

import logging
from typing import Optional
from uuid import uuid4
from urllib.parse import urlsplit

import requests

from database.manager import DatabaseManager
from execution.base import ExecutionEngine
from models.types import Order, OrderType, PortfolioState
from utils.coinbase_auth import build_coinbase_jwt

logger = logging.getLogger(__name__)


class CoinbaseExecutionEngine(ExecutionEngine):
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        db_manager: Optional[DatabaseManager] = None,
    ):
        self.base_url = "https://api.coinbase.com/api/v3/brokerage"

        self.db_manager = db_manager
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "AlgorithmicTradingPlatform/1.0",
            }
        )

    def execute_order(self, order: Order, current_price: float, portfolio: PortfolioState) -> PortfolioState:
        if order.order_type != OrderType.MARKET:
            logger.warning("Advanced Trade engine currently supports market orders only")
            return portfolio

        payload = {
            "client_order_id": str(uuid4()),
            "product_id": order.symbol,
            "side": order.side.value.upper(),
            "order_configuration": {
                "market_market_ioc": {
                    "base_size": str(order.quantity),
                }
            },
        }

        try:
            response = self._send("POST", "/orders", payload)
            order_id = response.get("success_response", {}).get("order_id") or response.get("order_id")
            logger.info("Order submitted to Coinbase Advanced Trade: %s", order_id)

            if self.db_manager:
                self.db_manager.log_trade(order.symbol, order.side.value.upper(), order.quantity, current_price, 0)
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error executing Coinbase order: %s", exc)

        return portfolio

    def _send(self, method: str, path: str, body: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        request = requests.Request(method, url, json=body, headers=self.session.headers)
        prepared = request.prepare()
        parsed = urlsplit(prepared.url)
        canonical_path = parsed.path
        if parsed.query:
            canonical_path += f"?{parsed.query}"

        prepared.headers["Authorization"] = f"Bearer {build_coinbase_jwt(method, canonical_path, parsed.netloc)}"

        response = self.session.send(prepared, timeout=10)
        response.raise_for_status()
        return response.json()
