"""YFinance fallback implementation."""
import logging

import pandas as pd

from data.base import DataClient

logger = logging.getLogger(__name__)


class YFinanceDataClient(DataClient):
    def get_historical_bars(self, symbol: str, days: int = 300) -> pd.DataFrame:
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            df = ticker.history(period=f"{days}d")
            df = df.rename(
                columns={
                    "Open": "open",
                    "High": "high",
                    "Low": "low",
                    "Close": "close",
                    "Volume": "volume",
                }
            )
            df.index.name = "timestamp"
            return df[["open", "high", "low", "close", "volume"]]
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error fetching data from yfinance: %s", exc)
            return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> float:
        try:
            import yfinance as yf

            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            return data["Close"].iloc[-1] if not data.empty else 0.0
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error fetching latest price from yfinance: %s", exc)
            return 0.0
