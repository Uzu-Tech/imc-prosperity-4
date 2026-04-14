# dashboard/historical/callbacks.py
from dash import Input, Output
import plotly.graph_objects as go
from dashboard.shared.callbacks import register_shared_callbacks, FIGURE_LAYOUT
from dashboard.historical.orderbook import build_figure
from loaders.csv_loader import (
    get_timestamps, get_products,
    get_max_qty, parse_day_value,
)

def _get_timestamps(selector: str, product: str) -> list:
    round_num, day = parse_day_value(selector)
    return get_timestamps(round_num, day, product)

def _get_max_qty(selector: str, product: str) -> int:
    round_num, day = parse_day_value(selector)
    return get_max_qty(round_num, day, product)

def register_callbacks(app):
    register_shared_callbacks(app, _get_timestamps, _get_max_qty)

    # Update Product Dropdown
    @app.callback(
        Output("product-dropdown", "options"),
        Output("product-dropdown", "value"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown", "value"),
    )
    def update_products(round_day, current_product):
        round_num, day = parse_day_value(round_day)
        prods = get_products(round_num, day)
        options = [{"label": p, "value": p} for p in prods]
        value = current_product if current_product in prods else (prods[0] if prods else None)
        return options, value

    # Update Graph
    @app.callback(
        Output("order-book-plot", "figure"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown", "value"),
        Input("display-options", "value"),
        Input("timestamp-slider", "value"),
        Input("qty-slider", "value"),
        Input("qty-exact", "value"),
    )
    def update_plot(round_day, product, display_options, timestamp_range, qty_range, qty_exact):
        if not product or not round_day or not timestamp_range:
            return go.Figure()
        display_options = display_options or []
        round_num, day = parse_day_value(round_day)
        fig = build_figure(
            round_num, day, product,
            show_trades    ="show_trades" in display_options,
            show_quotes    ="show_quotes" in display_options,
            timestamp_range=timestamp_range,
            qty_range      =tuple(qty_range) if qty_range else None,
            qty_exact      =qty_exact,
        )
        fig.update_layout(**FIGURE_LAYOUT) # type: ignore
        return fig