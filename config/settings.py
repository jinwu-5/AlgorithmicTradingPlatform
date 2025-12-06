"""Centralized configuration and environment loading."""
import os

from dotenv import load_dotenv

from models.types import TradingMode

load_dotenv()

ALLOWED_SYMBOLS = ["BTC-USD", "ETH-USD"]

_symbol = (os.getenv("SYMBOL") or "BTC-USD").upper()
if _symbol not in ALLOWED_SYMBOLS:
    _symbol = "BTC-USD"

_symbols_env = os.getenv("SYMBOLS")
if _symbols_env:
    _requested = [token.strip().upper() for token in _symbols_env.split(",") if token.strip()]
else:
    _requested = [_symbol]

SYMBOLS = [sym for sym in _requested if sym in ALLOWED_SYMBOLS]
if not SYMBOLS:
    SYMBOLS = [_symbol]

SYMBOL = SYMBOLS[0]
INITIAL_CAPITAL = float(os.getenv("INITIAL_CAPITAL", "10000"))
MA_PERIOD = int(os.getenv("MA_PERIOD", "200"))

_mode_env = (os.getenv("MODE") or TradingMode.BACKTEST.value).lower()
try:
    MODE = TradingMode(_mode_env)
except ValueError:
    MODE = TradingMode.BACKTEST

COINBASE_API_KEY = os.getenv("COINBASE_API_KEY")
_secret = os.getenv("COINBASE_API_SECRET", "")
COINBASE_API_SECRET = _secret.replace("\\n", "\n")
COINBASE_API_HOST = os.getenv("COINBASE_API_HOST", "api.coinbase.com")

_granularity = int(os.getenv("COINBASE_GRANULARITY", "3600"))
_allowed_granularities = {60, 300, 900, 3600, 14400, 21600, 86400}
if _granularity not in _allowed_granularities:
    _granularity = 3600
COINBASE_GRANULARITY = _granularity

HISTORICAL_LOOKBACK_DAYS = int(os.getenv("HISTORICAL_LOOKBACK_DAYS", "730"))
LIVE_LOOKBACK_DAYS = int(os.getenv("LIVE_LOOKBACK_DAYS", "120"))

TRADING_DB_PATH = os.getenv("TRADING_DB_PATH", "trading_bot.db")
BACKTEST_DB_PATH = os.getenv("BACKTEST_DB_PATH", "backtest.db")
