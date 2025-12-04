"""SQLite persistence for portfolio, trades, and equity curve."""
import sqlite3
from datetime import datetime
import logging

from models.types import PortfolioState, Position

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path: str = "trading_bot.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS portfolio (
                id INTEGER PRIMARY KEY,
                cash REAL,
                equity REAL,
                timestamp TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS positions (
                symbol TEXT PRIMARY KEY,
                quantity REAL,
                avg_price REAL,
                last_updated TEXT
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                quantity REAL,
                price REAL,
                timestamp TEXT,
                pnl REAL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS equity_curve (
                timestamp TEXT PRIMARY KEY,
                equity REAL,
                cash REAL,
                positions_value REAL
            )
            """
        )

        conn.commit()
        conn.close()

    def save_portfolio(self, portfolio: PortfolioState) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO portfolio (id, cash, equity, timestamp)
            VALUES (1, ?, ?, ?)
            """,
            (portfolio.cash, portfolio.equity, datetime.now().isoformat()),
        )

        cursor.execute("DELETE FROM positions")
        for symbol, pos in portfolio.positions.items():
            if pos.quantity > 0:
                cursor.execute(
                    """
                    INSERT INTO positions (symbol, quantity, avg_price, last_updated)
                    VALUES (?, ?, ?, ?)
                    """,
                    (symbol, pos.quantity, pos.avg_price, datetime.now().isoformat()),
                )

        conn.commit()
        conn.close()

    def load_portfolio(self, initial_cash: float = 10000) -> PortfolioState:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT cash, equity FROM portfolio WHERE id = 1")
        row = cursor.fetchone()

        if row:
            cash, equity = row
        else:
            cash = initial_cash
            equity = initial_cash

        cursor.execute("SELECT symbol, quantity, avg_price FROM positions")
        positions = {}
        for symbol, quantity, avg_price in cursor.fetchall():
            positions[symbol] = Position(symbol, quantity, avg_price, 0)

        conn.close()
        return PortfolioState(cash, positions, equity)

    def log_trade(self, symbol: str, side: str, quantity: float, price: float, pnl: float = 0) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO trades (symbol, side, quantity, price, timestamp, pnl)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (symbol, side, quantity, price, datetime.now().isoformat(), pnl),
        )

        conn.commit()
        conn.close()

    def log_equity(self, equity: float, cash: float, positions_value: float) -> None:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO equity_curve (timestamp, equity, cash, positions_value)
            VALUES (?, ?, ?, ?)
            """,
            (datetime.now().isoformat(), equity, cash, positions_value),
        )

        conn.commit()
        conn.close()
