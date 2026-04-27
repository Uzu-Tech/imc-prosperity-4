# dashboard/historical/orderbook.py
from typing import Optional
import plotly.graph_objects as go
from dashboard.prices import process_prices
from analysis.prices import calc_fair_price
from dashboard.trades import process_trades
from loaders.csv_loader import get_prices_df, get_trades_df
from dashboard.shared.orderbook import (
    plot_quotes, plot_fair_prices, plot_trades, filter_timestamp,
)
import polars as pl

def build_figure(
    round_num: int, day: int, product: str,
    show_quotes: bool, show_trades: bool,
    timestamp_range: tuple,
    qty_range: Optional[tuple], qty_exact: Optional[int],
    mark_type
) -> go.Figure:
    prices_df = get_prices_df(round_num, day, product)
    fig = go.Figure()

    if show_quotes:
        vol_matrix, raw_vol_matrix = process_prices(prices_df)
        plot_quotes(fig, prices_df, vol_matrix, raw_vol_matrix)

    prices_df = calc_fair_price(prices_df)
    plot_fair_prices(fig, prices_df)

    if show_trades:
        trades_df = get_trades_df(round_num, day, product)    
        trades_df = process_trades(prices_df, trades_df)
        
        if mark_type != 'ALL':
            trades_df = trades_df.filter((pl.col("buyer") == mark_type) | (pl.col("seller") == mark_type))
        
        plot_trades(fig, trades_df, qty_range, qty_exact, mark_type)

    filter_timestamp(fig, prices_df, timestamp_range)

    fig.update_layout(
        title        =f"{product} — Round {round_num} Day {day}",
        yaxis        =dict(title="Price"),
        xaxis        =dict(title="Timestamp"),
        hovermode    ="closest",
        hoverdistance=5,
        uirevision   =f"{round_num}-{day}-{product}",
    )
    return fig