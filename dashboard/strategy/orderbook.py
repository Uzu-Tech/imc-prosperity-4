from typing import Optional
import plotly.graph_objects as go
import polars as pl
from dashboard.prices import process_prices, calc_fair_price
from dashboard.trades import process_trades
from loaders.log_loader import (
    get_prices_df, get_trades_df, get_logs_df,
    get_own_makes_df, get_own_takes_df,
)
from dashboard.shared.orderbook import (
    plot_quotes, plot_fair_prices, plot_trades, filter_timestamp, filter_pnl_timestamp, filter_position_timestamp
)
from plotly.subplots import make_subplots

OWN_BUY_COLOR  = "#00D4FF"
OWN_SELL_COLOR = "#FF6EB4"

def plot_own_takes(fig, own_takes, qty_range, qty_exact):
    if own_takes.is_empty():
        return

    if qty_exact is not None:
        own_takes = own_takes.filter(pl.col("quantity") == qty_exact)
    elif qty_range is not None:
        own_takes = own_takes.filter(pl.col("quantity").is_between(qty_range[0], qty_range[1]))

    if own_takes.is_empty():
        return

    max_qty = own_takes["quantity"].max() or 1
    buys    = own_takes.filter(pl.col("order_type") == "buy")
    sells   = own_takes.filter(pl.col("order_type") == "sell")

    if len(buys) > 0:
        fig.add_trace(go.Scatter(
            x=buys["timestamp"].to_list(),
            y=buys["price"].to_list(),
            mode="markers", name="My Buy",
            marker=dict(
                symbol="triangle-up", color=OWN_BUY_COLOR, size=14,
                opacity=(buys["quantity"] / max_qty * 0.7 + 0.3).to_list(),
                line=dict(color="white", width=1.5),
            ),
            hovertemplate="MY BUY<br>Price: %{y}<br>Qty: %{text}<br>Time: %{x}<extra></extra>",
            text=buys["quantity"].to_list(),
        ))

    if len(sells) > 0:
        fig.add_trace(go.Scatter(
            x=sells["timestamp"].to_list(),
            y=sells["price"].to_list(),
            mode="markers", name="My Sell",
            marker=dict(
                symbol="triangle-down", color=OWN_SELL_COLOR, size=14,
                opacity=(sells["quantity"] / max_qty * 0.7 + 0.3).to_list(),
                line=dict(color="white", width=1.5),
            ),
            hovertemplate="MY SELL<br>Price: %{y}<br>Qty: %{text}<br>Time: %{x}<extra></extra>",
            text=sells["quantity"].to_list(),
        ))

def plot_own_makes(fig, own_makes):
    if own_makes.is_empty():
        return
    
    max_qty = own_makes["quantity"].max() or 1
    bids = own_makes.filter(pl.col("order_type") == "bid")
    asks = own_makes.filter(pl.col("order_type") == "ask")

    if len(bids) > 0:
        fig.add_trace(go.Scatter(
            x=bids["timestamp"].to_list(),
            y=bids["price"].to_list(),
            mode="lines",           # ← line instead of markers
            name="My Bid Quote",
            line=dict(
                color=OWN_BUY_COLOR,
                width=1,
                shape="hv",         # ← step interpolation matches order book style
            ),
            opacity=1,
            hovertemplate="MY BID<br>Price: %{y}<br>Qty: %{text}<br>Time: %{x}<extra></extra>",
            text=bids["quantity"].to_list(),
        ))

    if len(asks) > 0:
        fig.add_trace(go.Scatter(
            x=asks["timestamp"].to_list(),
            y=asks["price"].to_list(),
            mode="lines",
            name="My Ask Quote",
            line=dict(
                color=OWN_SELL_COLOR,
                width=1,
                shape="hv",
            ),
            opacity=1,
            hovertemplate="MY ASK<br>Price: %{y}<br>Qty: %{text}<br>Time: %{x}<extra></extra>",
            text=asks["quantity"].to_list(),
        ))

def build_figure(
    log_name: str, product: str,
    show_quotes: bool, show_trades: bool,
    show_own_trades: bool, show_own_makes: bool,
    timestamp_range: tuple,
    qty_range: Optional[tuple], qty_exact: Optional[int],
) -> go.Figure:
    prices_df = get_prices_df(log_name, product)
    fig = go.Figure()

    if show_quotes:
        vol_matrix, raw_vol_matrix = process_prices(prices_df)
        plot_quotes(fig, prices_df, vol_matrix, raw_vol_matrix)

    prices_df = calc_fair_price(prices_df)
    plot_fair_prices(fig, prices_df)

    if show_own_makes:
        own_makes = get_own_makes_df(log_name, product)
        plot_own_makes(fig, own_makes)

    if show_own_trades:
        own_takes = get_own_takes_df(log_name, product)
        plot_own_takes(fig, own_takes, qty_range, qty_exact)

    if show_trades:
        trades_df = get_trades_df(log_name, product)
        trades_df = process_trades(prices_df, trades_df)
        plot_trades(fig, trades_df, qty_range, qty_exact)

    filter_timestamp(fig, prices_df, timestamp_range)

    fig.update_layout(
        title        =f"{product} — {log_name}",
        yaxis        =dict(title="Price"),
        xaxis        =dict(title="Timestamp"),
        hovermode    ="closest",
        hoverdistance=5,
        uirevision   =f"{log_name}-{product}",
    )
    return fig


def plot_position(fig, logs, product):
    position_limits = {
        "EMERALDS": 80,
        "TOMATOES": 80,
    }
    limit = position_limits.get(product, 20)
    warning_zone = limit * 0.8  # ← shade when within 20% of limit

    timestamps = logs["timestamp"].to_list()

    # ── Warning zone shading ───────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=timestamps + timestamps[::-1],
        y=[limit] * len(timestamps) + [warning_zone] * len(timestamps),
        fill="toself",
        fillcolor="rgba(255, 75, 75, 0.08)",
        line=dict(width=0),
        hoverinfo="skip",
        showlegend=False,
        name="Upper warning",
    ), row=1, col=1)

    # Lower warning zone (negative side)
    fig.add_trace(go.Scatter(
        x=timestamps + timestamps[::-1],
        y=[-warning_zone] * len(timestamps) + [-limit] * len(timestamps),
        fill="toself",
        fillcolor="rgba(255, 75, 75, 0.08)",
        line=dict(width=0),
        hoverinfo="skip",
        showlegend=False,
        name="Lower warning",
    ), row=1, col=1)

    # ── Position line ──────────────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=logs["timestamp"],
        y=logs["position"],
        mode="lines",
        name="Position",
        fill='tozeroy',  # Fills the area between the line and 0
        line=dict(color='#F6E71D', width=1.5, shape="hv"),
        fillcolor='rgba(246, 231, 29, 0.2)', # Transparent version of your yellow
        hovertemplate="Position: %{y}<br>Time: %{x}<extra></extra>"
    ), row=1, col=1)

    # ── Limit lines ────────────────────────────────────────────────
    for lim, label in [(limit, " Long limit"), (-limit, " Short limit")]:
        fig.add_hline(
            y=lim,
            line=dict(color="#FF4B4B", width=1, dash="dash"),
            annotation_text=label,
            annotation_position="right",
            annotation_font=dict(color="#FF4B4B", size=11, family="monospace"),
            row=1, col=1,
        )

    # ── Warning threshold lines ────────────────────────────────────
    for lim, label in [(warning_zone, " Warning Zone"), (-warning_zone, " Warning Zone")]:
        fig.add_hline(
            y=lim,
            line=dict(color="#FFB432", width=0.5, dash="dot"),
            annotation_text=label,
            annotation_position="right",
            annotation_font=dict(color="#FFB432", size=11, family="monospace"),
            row=1, col=1,
        )

    fig.update_yaxes(
        range=[-limit - 5, limit + 5],
        row=1, col=1,
    )

def plot_pnl(fig, prices_df):
    pnl_df = prices_df.filter(
        pl.col("pnl_per_step") != 0  # only plot non-zero timesteps
    )
    
    timestamps = pnl_df["timestamp"].to_list()
    pnl        = pnl_df["pnl_per_step"].to_list()

    for t, v in zip(timestamps, pnl):
        fig.add_shape(
            type="line",
            x0=t, x1=t, y0=0, y1=v,
            line=dict(
                color="#00C97A" if v >= 0 else "#FF4B4B",
                width=1.5,
            ),
            row=1, col=2
        )

    # Dots at the tip
    fig.add_trace(go.Scatter(
        x=timestamps,
        y=pnl,
        mode="markers",
        name="PnL",
        marker=dict(
            color=["#00C97A" if v >= 0 else "#FF4B4B" for v in pnl],
            size=4,
            line=dict(width=0),
        ),
        hovertemplate="PnL: %{y:.2f}<br>Time: %{x}<extra></extra>",
    ), row=1, col=2)

    fig.update_yaxes(
        zeroline=True, zerolinecolor="#555", zerolinewidth=1,
        gridcolor="#2a2a2a", title="PnL",
        row=1, col=2,
    )


def build_pnl_position_figure(log_name: str, product: str, timestamp_range: tuple):
    logs, prices_df = get_logs_df(log_name, product), get_prices_df(log_name, product)
    
    fig = make_subplots(
        rows=1, cols=2, 
        subplot_titles=("Market Position", "Pnl Per Timestep"),
        horizontal_spacing=0.1 
    )

    fig.update_yaxes(title_text="Position Size", row=1, col=1)
    fig.update_yaxes(title_text="Profit & Loss", row=1, col=2)
    fig.update_xaxes(title_text="Timestamp")

    plot_position(fig, logs, product)
    plot_pnl(fig, prices_df)
    filter_position_timestamp(fig, logs, timestamp_range)
    filter_pnl_timestamp(fig, prices_df, timestamp_range)

    fig.update_layout(
        hovermode    ="x unified",
        hoverlabel=dict(
            bgcolor="#222222",      # Match your background color
            font_size=13,           # Clean, readable size
            font_family="monospace", # Great for alignment of numbers
            font_color="white",     # High contrast text
            bordercolor="#444444"   # Subtle border
        ),
        hoverdistance=5,
        uirevision   =f"{log_name}-{product}",
        showlegend=True
    )
    return fig