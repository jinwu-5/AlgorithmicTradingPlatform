"""Centralized configuration and environment loading."""
import os

from dotenv import load_dotenv

from models.types import TradingMode

load_dotenv()

SYMBOL = os.getenv("SYMBOL", "QQQ")
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "10000"))
MA_PERIOD = int(os.getenv("MA_PERIOD", "200"))

_mode_env = (os.getenv("MODE") or TradingMode.BACKTEST.value).lower()
try:
    MODE = TradingMode(_mode_env)
except ValueError:
    MODE = TradingMode.BACKTEST

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_API_SECRET = os.getenv("ALPACA_API_SECRET")

HISTORICAL_LOOKBACK_DAYS = int(os.getenv("HISTORICAL_LOOKBACK_DAYS", "400"))
LIVE_LOOKBACK_DAYS = int(os.getenv("LIVE_LOOKBACK_DAYS", "300"))
LIVE_SCHEDULE_TIME = os.getenv("LIVE_SCHEDULE_TIME", "16:30")
DATA_TIMEFRAME = os.getenv("DATA_TIMEFRAME", "1Day")

TRADING_DB_PATH = os.getenv("TRADING_DB_PATH", "trading_bot.db")
BACKTEST_DB_PATH = os.getenv("BACKTEST_DB_PATH", "backtest.db")
