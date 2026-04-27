# dashboard/shared/orderbook.py
from typing import Optional
import numpy as np
import plotly.graph_objects as go
import polars as pl
from dashboard.prices import get_min_max_price

def filter_timestamp(fig, prices_df, timestamp_range):
    start, end = timestamp_range
    price_min, price_max = get_min_max_price(
        prices_df.filter(pl.col("timestamp").is_between(start, end))
    )
    
    # Update the X-axis range globally
    fig.update_xaxes(range=[start, end])
    fig.update_yaxes(range=[price_min - 1, price_max + 1])

def filter_position_timestamp(fig, timestamp_range):
    start, end = timestamp_range
    fig.update_xaxes(range=[start, end], row=1, col=1)

def plot_fair_prices(fig, prices_df):
    fig.add_trace(go.Scatter(
        x=prices_df["timestamp"].to_list(),
        y=prices_df["fair_price"].to_list(),
        name="Fair Price",
        mode="lines",
        line=dict(color="#FFD166", width=1, dash="dot"),
        hovertemplate="Fair Price: %{y}<br>Time: %{x}<extra></extra>",
    ))

def plot_trades(fig, trades_df, qty_range: Optional[tuple], qty_exact: Optional[int], mark_type: str):
    if trades_df.is_empty():
        return

    if qty_exact is not None:
        trades_df = trades_df.filter(pl.col("quantity") == qty_exact)
    elif qty_range is not None:
        trades_df = trades_df.filter(pl.col("quantity").is_between(qty_range[0], qty_range[1]))

    if trades_df.is_empty():
        return

    max_qty = trades_df["quantity"].max() or 1
    buys    = trades_df.filter(pl.col("direction") == "buy")
    sells   = trades_df.filter(pl.col("direction") == "sell")

    if len(buys) > 0:
        fig.add_trace(go.Scatter(
            x=buys["timestamp"].to_list(),
            y=buys["price"].to_list(),
            mode="markers", name="Bot Buy",
            marker=dict(
                symbol="triangle-up", color="#00FA9A", size=10,
                opacity=(buys["quantity"] / max_qty * 0.7 + 0.3).to_list(),
                line=dict(color="white", width=0.5),
            ),
            hovertemplate=(
                "BUY<br>"
                "Price: %{y}<br>"
                "Qty: %{customdata[0]}<br>"
                "Buyer: %{customdata[1]}<br>"
                "Seller: %{customdata[2]}<br>"
                "Time: %{x}<extra></extra>"
            ),
            customdata=list(zip(
                buys["quantity"].to_list(),
                buys["buyer"].to_list(),
                buys["seller"].to_list(),
            )),
            text=buys["quantity"].to_list(),
        ))

    if len(sells) > 0:
        fig.add_trace(go.Scatter(
            x=sells["timestamp"].to_list(),
            y=sells["price"].to_list(),
            mode="markers", name="Bot Sell",
            marker=dict(
                symbol="triangle-down", color="#FF4B4B", size=10,
                opacity=(sells["quantity"] / max_qty * 0.7 + 0.3).to_list(),
                line=dict(color="white", width=0.5),
            ),
            hovertemplate=(
                "SELL<br>"
                "Price: %{y}<br>"
                "Qty: %{customdata[0]}<br>"
                "Buyer: %{customdata[1]}<br>"
                "Seller: %{customdata[2]}<br>"
                "Time: %{x}<extra></extra>"
            ),
            customdata=list(zip(
                sells["quantity"].to_list(),
                sells["buyer"].to_list(),
                sells["seller"].to_list(),
            )),
        ))

def plot_quotes(fig, prices_df, vol_matrix, raw_vol_matrix):
    timestamps  = prices_df["timestamp"].to_list()
    price_min, price_max = get_min_max_price(prices_df)
    price_range = np.arange(price_min, price_max + 1)

    fig.add_trace(go.Heatmap(
        x=timestamps, y=price_range, z=vol_matrix,
        customdata=raw_vol_matrix,
        hovertemplate="Volume: %{customdata:.0f}<br>Price: %{y}<br>Time: %{x}<extra></extra>",
        hoverongaps=False,
        colorscale=[
            [0.0, "#FF4B4B"],
            [0.5, "rgba(0,0,0,0)"],
            [1.0, "#00C97A"],
        ],
        zmid=0, zsmooth=False, showscale=False,
        name="Order book depth",
    ))

    fig.add_trace(go.Scatter(
        x=timestamps, y=prices_df["bid_price_1"],
        name="Best bid", mode="lines",
        line=dict(color="#00FA9A", width=0.75, shape="hv"),
        hoverinfo="skip",
    ))

    fig.add_trace(go.Scatter(
        x=timestamps, y=prices_df["ask_price_1"],
        name="Best ask", mode="lines",
        line=dict(color="#FF6B6B", width=0.75, shape="hv"),
        hoverinfo="skip",
    ))

    # Dummy traces for legend
    for color, label in [("#00C97A", "Bid depth"), ("#FF4B4B", "Ask depth")]:
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode="markers",
            marker=dict(symbol="square", color=color, size=10),
            name=label,
            showlegend=True,
        ))