"""Entry point for the Algorithmic Trading Platform."""
from config.settings import (
    ALPACA_API_KEY,
    ALPACA_API_SECRET,
    BACKTEST_DB_PATH,
    DATA_TIMEFRAME,
    HISTORICAL_LOOKBACK_DAYS,
    INITIAL_CAPITAL,
    LIVE_LOOKBACK_DAYS,
    MA_PERIOD,
    MODE,
    SYMBOL,
    TRADING_DB_PATH,
)
from data.alpaca_client import AlpacaDataClient
from data.yfinance_client import YFinanceDataClient
from backtest.engine import Backtester
from database.manager import DatabaseManager
from execution.alpaca import AlpacaExecutionEngine
from execution.simulated import SimulatedExecutionEngine
from live.engine import LiveTradingEngine
from models.types import TradingMode
from strategies.trend_following import TrendFollowingStrategy
from utils.logger import setup_logging


def build_data_client():
    if ALPACA_API_KEY and ALPACA_API_SECRET:
        print("✓ Using Alpaca for data")
        return AlpacaDataClient(ALPACA_API_KEY, ALPACA_API_SECRET, paper=True, timeframe=DATA_TIMEFRAME)

    print("⚠ Alpaca credentials not found, using yfinance")
    print("  (Install: pip install yfinance)")
    return YFinanceDataClient()


def main():
    setup_logging()

    print("\n" + "=" * 60)
    print(f"QQQ TREND-FOLLOWING BOT - {MODE.value.upper()} MODE")
    print("=" * 60 + "\n")

    strategy = TrendFollowingStrategy(SYMBOL, ma_period=MA_PERIOD)
    data_client = build_data_client()

    if MODE == TradingMode.BACKTEST:
        backtester = Backtester(strategy, data_client, INITIAL_CAPITAL, db_path=BACKTEST_DB_PATH)
        backtester.run(lookback_days=HISTORICAL_LOOKBACK_DAYS)
        return

    db_path = TRADING_DB_PATH or f"{MODE.value}_trading.db"
    db_manager = DatabaseManager(db_path)

    if MODE == TradingMode.PAPER:
        execution_engine = SimulatedExecutionEngine(db_manager)
    else:
        if not (ALPACA_API_KEY and ALPACA_API_SECRET):
            print("ERROR: Alpaca credentials required for LIVE mode")
            return
        execution_engine = AlpacaExecutionEngine(ALPACA_API_KEY, ALPACA_API_SECRET, paper=False, db_manager=db_manager)

    live_engine = LiveTradingEngine(
        strategy=strategy,
        data_client=data_client,
        execution_engine=execution_engine,
        mode=MODE,
        initial_capital=INITIAL_CAPITAL,
        db_manager=db_manager,
    )

    live_engine.run_iteration(lookback_days=LIVE_LOOKBACK_DAYS)

    # To enable scheduling instead of a single run:
    # live_engine.start_scheduler(run_time=LIVE_SCHEDULE_TIME)


if __name__ == "__main__":
    main()
