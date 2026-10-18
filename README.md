# Algorithmic Trading Platform

A crypto trading bot I run against Coinbase Advanced Trade. It backtests a
strategy over historical candles, paper trades it against live prices, or
places real orders, depending on which mode you start it in. Results go to
SQLite and it writes a diagnostic chart per symbol after a backtest.

Built for my own use on BTC-USD and ETH-USD.

## Stack

Python with pandas and numpy for the strategy logic, Coinbase Advanced Trade
over REST with JWT auth (PyJWT and cryptography), APScheduler for the live
loop, SQLite for state, and matplotlib with mplfinance for the charts.

## Getting it running

You need Python 3.10+ and a Coinbase Advanced Trade API key.

```bash
pip install -r requirements.txt
```

Put your credentials in a `.env` file next to `main.py`:

```
COINBASE_API_KEY=organizations/{org_id}/apiKeys/{key_id}
COINBASE_API_SECRET="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n"
MODE=backtest
```

Then:

```bash
python main.py
```

If the key or the private key format gives you trouble, `python
debug_coinbase_auth.py` walks through loading the key and signing a request and
tells you which step failed.

## Modes

`MODE` decides what the run does. Market data comes from Coinbase in all three.

| Mode | What happens |
|---|---|
| `backtest` | Replays `HISTORICAL_LOOKBACK_DAYS` of candles, fills at the bar close with 0.1% slippage, prints return, max drawdown, Sharpe and trade counts, and writes `plots/<symbol>_diagnostics.png` |
| `paper` | Runs against live candles through the simulated execution engine, so no order reaches the exchange |
| `live` | Same loop, with orders placed on Coinbase |

## Configuration

Everything is environment variables, read in `config/settings.py`.

| Variable | Default | Notes |
|---|---|---|
| `SYMBOLS` | `BTC-USD` | Comma separated; only BTC-USD and ETH-USD are allowed |
| `INITIAL_CAPITAL` | `10000` | Starting cash for backtests and paper runs |
| `COINBASE_GRANULARITY` | `3600` | Candle size in seconds, from 60 to 86400 |
| `HISTORICAL_LOOKBACK_DAYS` | `730` | How far back a backtest reads |
| `LIVE_LOOKBACK_DAYS` | `120` | Candle history each live iteration pulls for its indicators |
| `MA_PERIOD` | `200` | Moving average length for the trend strategy |
| `BACKTEST_DB_PATH` | `backtest.db` | |
| `TRADING_DB_PATH` | `trading_bot.db` | Paper and live runs |

## Strategies

Both live in `strategies/` and implement the same interface, so a run can hold
one per symbol.

- **RSI + Bollinger mean reversion** (default). Buys when price sits at the
  lower band with RSI oversold, exits when price returns to the middle band or
  RSI recovers past its exit level.
- **Moving average trend following.** Buys when price is above the moving
  average and sells when it falls back below, sizing each entry off a fixed
  fraction of equity.

Swap between them in `build_strategies()` in `main.py`.

## What it stores

`database/manager.py` keeps four tables: `portfolio` for cash and equity,
`positions` for what is currently held, `trades` for every fill with its P&L,
and `equity_curve` for the per-step equity used in the metrics and charts.

## Tests

```bash
python -m unittest discover tests
```

Currently covers the Coinbase JWT signing path.

## What's next

- Choose the strategy from an environment variable instead of editing `main.py`
- Wire `LiveTradingEngine.start_scheduler()` into `main.py` so live mode runs on
  a schedule rather than a single iteration
- Model exchange fees in the backtester, which today only applies slippage
- Portfolio-level risk limits: max exposure per symbol and a daily loss cutoff
- Test coverage for the strategies and the backtest engine, not just auth
- More symbols once the allowlist in `config/settings.py` can be configured
