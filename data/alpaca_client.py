"""Alpaca implementation of the data client."""
from datetime import datetime, timedelta
import logging
from typing import Optional

import pandas as pd

from data.base import DataClient

logger = logging.getLogger(__name__)


class AlpacaDataClient(DataClient):
    def __init__(self, api_key: str, api_secret: str, paper: bool = True, timeframe: str = "1Day"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://paper-api.alpaca.markets" if paper else "https://api.alpaca.markets"
        self.data_url = "https://data.alpaca.markets"
        self.timeframe = timeframe

        import requests

        self.session = requests.Session()
        self.session.headers.update(
            {
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": api_secret,
            }
        )

    def get_historical_bars(self, symbol: str, days: int = 300) -> pd.DataFrame:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        url = f"{self.data_url}/v2/stocks/{symbol}/bars"
        params = {
            "start": start_date.strftime("%Y-%m-%d"),
            "end": end_date.strftime("%Y-%m-%d"),
            "timeframe": self.timeframe,
            "limit": 10000,
        }

        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            if "bars" not in data or not data["bars"]:
                logger.warning("No bars returned for %s", symbol)
                return pd.DataFrame()

            df = pd.DataFrame(data["bars"])
            df["timestamp"] = pd.to_datetime(df["t"])
            df = df.rename(columns={"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume"})
            df = df[["timestamp", "open", "high", "low", "close", "volume"]]
            return df.set_index("timestamp").sort_index()
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error fetching historical data: %s", exc)
            return pd.DataFrame()

    def get_latest_price(self, symbol: str) -> float:
        url = f"{self.data_url}/v2/stocks/{symbol}/trades/latest"

        try:
            response = self.session.get(url)
            response.raise_for_status()
            data = response.json()
            return data["trade"]["p"]
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error fetching latest price: %s", exc)
            return 0.0
