"""Coinbase Advanced Trade data client."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlencode

import pandas as pd
import requests

from config.settings import COINBASE_API_HOST
from data.base import DataClient
from utils.coinbase_auth import build_coinbase_jwt

logger = logging.getLogger(__name__)


class CoinbaseDataClient(DataClient):
    """Fetch historical and latest prices from Coinbase Advanced Trade."""

    GRANULARITY_MAP = {
        60: "ONE_MINUTE",
        300: "FIVE_MINUTE",
        900: "FIFTEEN_MINUTE",
        3600: "ONE_HOUR",
        14400: "FOUR_HOUR",
        21600: "SIX_HOUR",
        86400: "ONE_DAY",
    }

    # Public endpoints that don't require authentication
    PUBLIC_ENDPOINTS = {
        "/products",  # Product list and details
        "/candles",   # Market candles (in path)
        "/ticker",    # Product ticker (in path)
    }

    def __init__(
        self,
        granularity_seconds: int = 86400,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
    ):
        if granularity_seconds not in self.GRANULARITY_MAP:
            granularity_seconds = 86400

        self.api_host = f"https://{COINBASE_API_HOST}"
        self.api_prefix = "/api/v3/brokerage"
        self.granularity = granularity_seconds
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        self.base_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "AlgorithmicTradingPlatform/1.0",
        }

    def get_historical_bars(self, symbol: str, days: int = 300) -> pd.DataFrame:
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(days=days)

        start_time = self._align_timestamp(start_time)
        end_time = self._align_timestamp(end_time)

        frames: List[pd.DataFrame] = []
        chunk_start = start_time
        max_span = timedelta(seconds=self.granularity * 300)

        while chunk_start < end_time:
            chunk_end = min(chunk_start + max_span, end_time)
            chunk_start = self._align_timestamp(chunk_start)
            chunk_end = self._align_timestamp(chunk_end)

            if chunk_end <= chunk_start:
                chunk_end = chunk_start + timedelta(seconds=self.granularity)

            # Convert to UNIX timestamps (integers) instead of ISO strings
            params = {
                "start": str(int(chunk_start.timestamp())),
                "end": str(int(chunk_end.timestamp())),
                "granularity": self.GRANULARITY_MAP[self.granularity],
            }

            try:
                # Use public market endpoint (no auth required)
                candles = self._request("GET", f"/market/products/{symbol}/candles", params=params)
            except Exception as exc:  # pragma: no cover - network
                logger.error("Error fetching Coinbase candles: %s", exc)
                break

            if isinstance(candles, dict):
                candles = candles.get("candles", [])
            if not candles:
                break

            normalized_rows = [self._normalize_candle(c) for c in candles]
            chunk_df = pd.DataFrame([row for row in normalized_rows if row])
            if chunk_df.empty:
                break

            chunk_df = chunk_df.dropna()
            frames.append(chunk_df)
            chunk_start = chunk_end

        if not frames:
            return pd.DataFrame()

        df = pd.concat(frames, ignore_index=True)
        # Timestamp is already datetime objects from _normalize_candle
        if df["timestamp"].dtype == 'object':
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.drop_duplicates(subset="timestamp")
        df = df.sort_values("timestamp")
        df = df.set_index("timestamp")
        return df

    def get_latest_price(self, symbol: str) -> float:
        try:
            # Use public market endpoint (no auth required)
            data = self._request("GET", f"/market/products/{symbol}/ticker")
            price = data.get("price") or data.get("best_bid") or data.get("best_ask")
            return float(price) if price else 0.0
        except Exception as exc:  # pragma: no cover - network
            logger.error("Error fetching Coinbase ticker: %s", exc)
            return 0.0

    def _normalize_candle(self, candle: Any) -> Dict[str, Any]:
        """Normalize candle data from Coinbase API response."""
        if isinstance(candle, dict):
            timestamp = candle.get("start") or candle.get("time") or candle.get("timestamp")

            # Convert UNIX timestamp to datetime if it's an integer or string integer
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            elif isinstance(timestamp, str) and timestamp.isdigit():
                timestamp = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
            elif isinstance(timestamp, str):
                # Already an ISO string, parse it
                timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))

            return {
                "timestamp": timestamp,
                "open": float(candle.get("open", 0)),
                "high": float(candle.get("high", 0)),
                "low": float(candle.get("low", 0)),
                "close": float(candle.get("close", 0)),
                "volume": float(candle.get("volume", 0)),
            }

        if isinstance(candle, list) and len(candle) >= 6:
            return {
                "timestamp": datetime.fromtimestamp(candle[0], tz=timezone.utc),
                "open": float(candle[3]),
                "high": float(candle[2]),
                "low": float(candle[1]),
                "close": float(candle[4]),
                "volume": float(candle[5]),
            }

        return {}

    def _is_public_endpoint(self, path: str) -> bool:
        """Check if endpoint is public and doesn't need authentication."""
        for public_path in self.PUBLIC_ENDPOINTS:
            if public_path in path:
                return True
        return False

    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.api_host}{self.api_prefix}{path}"

        # Prepare the base request
        request = requests.Request(
            method,
            url,
            params=params,
            json=body,
            headers=self.base_headers.copy(),
        )
        prepared = request.prepare()

        # Only add authentication for non-public endpoints
        is_public = self._is_public_endpoint(path)

        if not is_public and self.api_key and self.api_secret:
            # Build the canonical URI for JWT (unencoded)
            parsed_host = urlsplit(self.api_host)
            request_path = f"{self.api_prefix}{path}"

            if params:
                query_string = urlencode(params, safe=':')
                canonical_uri = f"{method} {parsed_host.netloc}{request_path}?{query_string}"
            else:
                canonical_uri = f"{method} {parsed_host.netloc}{request_path}"

            # Generate JWT and add to headers
            jwt_token = build_coinbase_jwt(
                key_name=self.api_key,
                key_secret=self.api_secret,
                uri=canonical_uri
            )
            prepared.headers["Authorization"] = f"Bearer {jwt_token}"

        response = self.session.send(prepared, timeout=10)

        if response.status_code >= 400:
            logger.error(
                "Coinbase API error %s: %s | endpoint: %s | public: %s",
                response.status_code,
                response.text,
                path,
                is_public,
            )

        response.raise_for_status()
        return response.json()

    def _align_timestamp(self, dt: datetime, round_up: bool = False) -> datetime:
        """Align timestamps to the closest interval supported by Coinbase candles."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        total_seconds = int((dt - epoch).total_seconds())
        remainder = total_seconds % self.granularity

        if remainder == 0:
            aligned_seconds = total_seconds
        elif round_up:
            aligned_seconds = total_seconds + (self.granularity - remainder)
        else:
            aligned_seconds = total_seconds - remainder

        return epoch + timedelta(seconds=aligned_seconds)
