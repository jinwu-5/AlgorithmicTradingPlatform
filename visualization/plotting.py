"""Diagnostic plotting helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import matplotlib

# Use a non-interactive backend for CLI environments
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mplfinance.original_flavor import candlestick_ohlc
import pandas as pd

from models.types import OrderSide
from strategies.base import IndicatorPanel


def plot_strategy_diagnostics(
    symbol: str,
    history_df: pd.DataFrame,
    order_log: Sequence[Dict],
    indicator_panels: Sequence[IndicatorPanel],
    output_dir: str | os.PathLike[str] = "plots",
) -> Path:
    """Render price + indicator charts with trade markers for a strategy."""
    if history_df.empty:
        raise ValueError("Cannot plot diagnostics without historical data")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"{symbol}_diagnostics.png"

    price_df = history_df.copy()
    price_df = price_df[["open", "high", "low", "close", "volume"]].dropna()
    price_df["mdates"] = mdates.date2num(price_df.index.to_pydatetime())

    overlay_panels = [panel for panel in indicator_panels if panel.overlay_on_price]
    separate_panels = [panel for panel in indicator_panels if not panel.overlay_on_price]

    total_rows = 1 + len(separate_panels)
    height_ratios = [3] + [1] * len(separate_panels)

    fig = plt.figure(figsize=(14, 6 + 2 * len(separate_panels)))
    grid = fig.add_gridspec(nrows=total_rows, ncols=1, height_ratios=height_ratios, hspace=0.05)

    ax_price = fig.add_subplot(grid[0, 0])
    _plot_candles(ax_price, price_df)
    _plot_trades(ax_price, order_log)
    _shade_positions(ax_price, price_df.index, order_log)

    for panel in overlay_panels:
        for column in panel.data.columns:
            aligned = panel.data[column].reindex(price_df.index).dropna()
            ax_price.plot(aligned.index, aligned.values, label=f"{panel.title} - {column}")
    ax_price.legend(loc="upper left")
    ax_price.set_title(f"{symbol} Price with Signals")

    for idx, panel in enumerate(separate_panels):
        ax = fig.add_subplot(grid[idx + 1, 0], sharex=ax_price)
        for column in panel.data.columns:
            aligned = panel.data[column].reindex(price_df.index).dropna()
            ax.plot(aligned.index, aligned.values, label=column)
        if panel.horizontal_lines:
            for label, value in panel.horizontal_lines.items():
                ax.axhline(value, linestyle="--", linewidth=1, alpha=0.6, label=label)
        ax.set_title(panel.title)
        ax.legend(loc="upper left")
        ax.grid(True, linestyle=":", alpha=0.3)

    ax_price.set_ylabel("Price")
    ax_price.grid(True, linestyle=":", alpha=0.3)
    ax_price.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.setp(ax_price.get_xticklabels(), rotation=0, ha="center")

    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_path, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return output_path


def _plot_candles(ax, price_df: pd.DataFrame) -> None:
    ohlc = price_df[["mdates", "open", "high", "low", "close"]].values
    candlestick_ohlc(ax, ohlc, width=0.6, colorup="tab:green", colordown="tab:red", alpha=0.8)


def _plot_trades(ax, order_log: Sequence[Dict]) -> None:
    if not order_log:
        return

    plotted_labels = set()
    for order in order_log:
        timestamp = order["timestamp"]
        price = order["price"]
        side = order["side"]
        mdate = mdates.date2num(pd.Timestamp(timestamp))
        if side == OrderSide.BUY:
            marker = "^"
            color = "green"
            label = "Buy"
        else:
            marker = "v"
            color = "red"
            label = "Sell"

        if label in plotted_labels:
            label = None
        else:
            plotted_labels.add(label)

        ax.scatter(
            mdate,
            price,
            marker=marker,
            color=color,
            edgecolor="black",
            linewidths=0.5,
            s=70,
            label=label,
            zorder=5,
        )


def _shade_positions(ax, index: Iterable[pd.Timestamp], order_log: Sequence[Dict]) -> None:
    if not order_log:
        return

    position_series = _build_position_series(index, order_log)
    if position_series.empty:
        return

    spans = _build_position_spans(position_series)
    for start, end in spans:
        ax.axvspan(
            mdates.date2num(start),
            mdates.date2num(end),
            color="green",
            alpha=0.08,
        )


def _build_position_series(index: Iterable[pd.Timestamp], order_log: Sequence[Dict]) -> pd.Series:
    timestamps = pd.Index(index)
    if timestamps.empty:
        return pd.Series(dtype=float)

    sorted_orders = sorted(order_log, key=lambda entry: entry["timestamp"])
    position_values = []
    active_position = 0.0
    order_pointer = 0

    for ts in timestamps:
        while order_pointer < len(sorted_orders) and sorted_orders[order_pointer]["timestamp"] <= ts:
            order = sorted_orders[order_pointer]
            side = order["side"]
            qty = float(order["quantity"])
            if side == OrderSide.BUY:
                active_position += qty
            else:
                active_position -= qty
            order_pointer += 1
        position_values.append(active_position)

    return pd.Series(position_values, index=timestamps)


def _build_position_spans(position_series: pd.Series) -> List[tuple[pd.Timestamp, pd.Timestamp]]:
    spans: List[tuple[pd.Timestamp, pd.Timestamp]] = []
    in_position = False
    span_start: pd.Timestamp | None = None

    for timestamp, value in position_series.items():
        currently_in_position = value > 0
        if currently_in_position and not in_position:
            span_start = timestamp
            in_position = True
        elif not currently_in_position and in_position:
            spans.append((span_start, timestamp))
            in_position = False
            span_start = None

    if in_position and span_start is not None:
        spans.append((span_start, position_series.index[-1]))

    return spans
