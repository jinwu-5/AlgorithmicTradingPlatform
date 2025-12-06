"""Entry point for the Algorithmic Trading Platform."""
from config.settings import (
    BACKTEST_DB_PATH,
    COINBASE_API_KEY,
    COINBASE_API_SECRET,
    COINBASE_GRANULARITY,
    HISTORICAL_LOOKBACK_DAYS,
    INITIAL_CAPITAL,
    LIVE_LOOKBACK_DAYS,
    MODE,
    SYMBOLS,
    TRADING_DB_PATH,
    MA_PERIOD,
)
from data.coinbase_client import CoinbaseDataClient
from backtest.engine import Backtester
from database.manager import DatabaseManager
from execution.coinbase import CoinbaseExecutionEngine
from execution.simulated import SimulatedExecutionEngine
from live.engine import LiveTradingEngine
from models.types import TradingMode
from strategies.rsi_bollinger import RSIBollingerMeanReversionStrategy
from strategies.trend_following import TrendFollowingStrategy
from utils.logger import setup_logging


def build_data_client():
    if not (COINBASE_API_KEY and COINBASE_API_SECRET):
        raise RuntimeError("Coinbase credentials are required for data access")

    print("✓ Using Coinbase Advanced Trade market data")
    return CoinbaseDataClient(
        granularity_seconds=COINBASE_GRANULARITY,
        api_key=COINBASE_API_KEY,
        api_secret=COINBASE_API_SECRET,
    )


def build_live_execution_engine(db_manager: DatabaseManager) -> CoinbaseExecutionEngine:
    if not (COINBASE_API_KEY and COINBASE_API_SECRET):
        raise RuntimeError("Coinbase credentials are required for LIVE mode")

    return CoinbaseExecutionEngine(
        api_key=COINBASE_API_KEY,
        api_secret=COINBASE_API_SECRET,
        db_manager=db_manager,
    )


def build_strategies():
    """Instantiate one strategy per configured symbol."""
    # Toggle between the strategy implementations here.
    return [RSIBollingerMeanReversionStrategy(symbol=symbol) for symbol in SYMBOLS]
    # return [TrendFollowingStrategy(symbol=symbol, ma_period=MA_PERIOD) for symbol in SYMBOLS]


def main():
    setup_logging()

    print("\n" + "=" * 60)
    print(f"COINBASE RSI MEAN REVERSION BOT - {MODE.value.upper()} MODE")
    print("=" * 60 + "\n")
    print(f"Active symbols: {', '.join(SYMBOLS)}")

    strategies = build_strategies()
    if not strategies:
        print("ERROR: No strategies configured")
        return

    try:
        data_client = build_data_client()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    if MODE == TradingMode.BACKTEST:
        backtester = Backtester(strategies, data_client, INITIAL_CAPITAL, db_path=BACKTEST_DB_PATH)
        backtester.run(lookback_days=HISTORICAL_LOOKBACK_DAYS)
        return

    db_path = TRADING_DB_PATH or f"{MODE.value}_trading.db"
    db_manager = DatabaseManager(db_path)

    if MODE == TradingMode.PAPER:
        execution_engine = SimulatedExecutionEngine(db_manager)
    else:
        try:
            execution_engine = build_live_execution_engine(db_manager)
        except RuntimeError as exc:
            print(f"ERROR: {exc}")
            return

    live_engine = LiveTradingEngine(
        strategies=strategies,
        data_client=data_client,
        execution_engine=execution_engine,
        mode=MODE,
        initial_capital=INITIAL_CAPITAL,
        db_manager=db_manager,
    )

    live_engine.run_iteration(lookback_days=LIVE_LOOKBACK_DAYS)

if __name__ == "__main__":
    main()
