from dash import Input, Output, State, ALL, html, ctx
import plotly.graph_objects as go
from dashboard.shared.callbacks import register_shared_callbacks, FIGURE_LAYOUT
from dashboard.simulation.orderbook import build_figure, build_pnl_position_figure
from loaders.log_loader import (
    get_timestamps, get_products,
    get_max_qty, get_logs_df, 
    get_prices_df, get_trades_df, get_own_makes_df, get_own_takes_df, 
)
from dashboard.log_formatter import format_log
from dashboard.simulation.metrics import calc_metrics
from dashboard.prices import calc_fair_price
import json

def _get_timestamps(selector: str, product: str) -> list:
    return get_timestamps(selector, product)

def _get_max_qty(selector: str, product: str) -> int:
    return get_max_qty(selector, product)

def register_callbacks(app):
    register_shared_callbacks(app, _get_timestamps, _get_max_qty)

    # Strategy-specific: product list depends on log file
    @app.callback(
        Output("product-dropdown", "options"),
        Output("product-dropdown", "value"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown", "value"),
    )
    def update_products(log_name, current_product):
        prods = get_products(log_name)
        options = [{"label": p, "value": p} for p in prods]
        value = current_product if current_product in prods else (prods[0] if prods else None)
        return options, value

    # Strategy-specific figure builder
    @app.callback(
        Output("order-book-plot", "figure"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown", "value"),
        Input("display-options", "value"),
        Input("timestamp-slider", "value"),
        Input("qty-slider", "value"),
        Input("qty-exact", "value"),
    )
    def update_order_book_plot(log_name, product, display_options, timestamp_range, qty_range, qty_exact):
        if not product or not log_name or not timestamp_range:
            return go.Figure()
        display_options = display_options or []
        fig = build_figure(
            log_name, product,
            show_quotes    ="show_quotes"    in display_options,
            show_trades    ="show_trades"    in display_options,
            show_own_trades="show_own_trades" in display_options,
            show_own_makes ="show_own_makes"  in display_options,
            timestamp_range=timestamp_range,
            qty_range      =tuple(qty_range) if qty_range else None,
            qty_exact      =qty_exact,
        )
        fig.update_layout(**FIGURE_LAYOUT) # type: ignore
        return fig
    
    @app.callback(
        Output("position-pnl-plot", "figure"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown", "value"),
        Input("timestamp-slider", "value"),
    )
    def update_position_pnl_plot(log_name, product, timestamp_range):
        fig = build_pnl_position_figure(
            log_name, product, timestamp_range
        )
        fig.update_layout(**FIGURE_LAYOUT) # type: ignore
        return fig

    @app.callback(
        Output("metric-fill-prob",      "children"),
        Output("metric-avg-spread",     "children"),
        Output("metric-avg-make-size",  "children"),
        Output("metric-avg-fill-size",      "children"),
        Output("metric-quote-distance", "children"),
        Output("metric-quote-rate",      "children"),
        Output("metric-total-pnl",      "children"),
        Output("metric-fill-quality",   "children"),
        Output("metric-num-takes",      "children"),
        Output("metric-sharpe",         "children"),
        Output("metric-max-drawdown",   "children"),
        # Color outputs
        Output("metric-total-pnl",      "style"),
        Output("metric-fill-quality",   "style"),
        Output("metric-sharpe",         "style"),
        Input("selector-dropdown",      "value"),
        Input("product-dropdown",       "value"),
        Input("timestamp-slider",       "value")
    )
    def update_metrics(log_name, product, timestamp_range):
        base = {"fontFamily": "monospace"}
        neutral = {**base, "color": "#ccc"}

        if not log_name or not product or not timestamp_range:
            empty = "—"
            return [empty] * 12 + [neutral] * 4

        prices_df = get_prices_df(log_name, product)
        trades_df = get_trades_df(log_name, product)
        prices_df = calc_fair_price(prices_df)

        takes = get_own_takes_df(log_name, product)
        makes = get_own_makes_df(log_name, product)

        m = calc_metrics(takes, makes, prices_df, trades_df, tuple(timestamp_range))

        def color_style(val_str: str, good_positive: bool = True) -> dict:
            try:
                val = float(val_str.replace("+", ""))
                if val == 0:
                    return neutral
                good = val > 0 if good_positive else val < 0
                return {**base, "color": "#00C97A" if good else "#FF4B4B"}
            except (ValueError, AttributeError):
                return neutral

        return (
            m["fill_prob"],
            m["avg_spread"],
            m["avg_make_size"],
            m["avg_fill_size"],
            m["quote_distance"],
            m["quote_rate"],
            m["total_pnl"],
            m["fill_quality"],
            m["num_takes"],
            m["sharpe"],
            m["max_drawdown"],
            color_style(m["total_pnl"]),
            color_style(m["fill_quality"]),
            color_style(m["sharpe"]),
        )
    
    @app.callback(
        Output("log-search-results", "children"),
        Output("log-search-results", "style"),
        Input("log-search",        "value"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown",  "value"),
    )
    def search_logs(search_term, log_name, product):
        hidden = {
            "fontFamily": "monospace", "fontSize": "11px",
            "overflowY": "auto", "maxHeight": "20vh",
            "borderBottom": "1px solid #333", "marginBottom": "8px",
            "display": "none",
        }
        visible = {**hidden, "display": "block"}

        if not search_term or not log_name or not product:
            return [], hidden

        logs = get_logs_df(log_name, product)
        if logs.is_empty():
            return [html.P("No logs", className="text-muted small")], visible

        # Search across all log_dict entries
        matches = []
        for row in logs.iter_rows(named=True):
            log_dict = row.get("log_dict", {})
            log_str  = json.dumps(log_dict).lower()
            if search_term.lower() in log_str:
                matches.append(row["timestamp"])

        if not matches:
            return [
                html.P(f"No matches for '{search_term}'",
                    className="text-muted small")
            ], visible

        # Build clickable result list
        results = [
            html.Div(
                f"t = {t}",
                id={"type": "log-result", "index": t},
                style={
                    "cursor": "pointer", "padding": "2px 6px",
                    "borderRadius": "3px", "color": "#5BC0DE",
                    "marginBottom": "2px",
                },
                className="log-result-item",
            )
            for t in matches
        ]

        summary = html.P(
            f"{len(matches)} matches",
            className="text-muted small mb-1",
            style={"fontFamily": "monospace"},
        )

        return [summary] + results, visible


    @app.callback(
        Output("log-selected-timestamp", "data"),
        Input({"type": "log-result", "index": ALL}, "n_clicks"),
        State({"type": "log-result", "index": ALL}, "id"),
        prevent_initial_call=True,
    )
    def select_log_timestamp(n_clicks, ids):
        from dash import ctx
        if not any(n_clicks):
            return None
        triggered = ctx.triggered_id
        if triggered:
            return triggered["index"]
        return None


    @app.callback(
        Output("log-timestamp", "children"),
        Output("log-content",   "children"),
        Input("order-book-plot",        "hoverData"),
        Input("log-selected-timestamp", "data"),
        Input("selector-dropdown",      "value"),
        Input("product-dropdown",       "value"),
        Input("log-search",             "value"),
    )
    def show_log(hover_data, selected_timestamp, log_name, product, search_term):
        if not log_name or not product:
            return "Hover to inspect", []

        # Selected from search results takes priority over hover
        from dash import ctx
        if ctx.triggered_id == "log-selected-timestamp" and selected_timestamp:
            timestamp = selected_timestamp
        elif hover_data:
            timestamp = hover_data["points"][0]["x"]
        else:
            return "Hover to inspect", []

        logs = get_logs_df(log_name, product)
        if logs.is_empty():
            return f"t = {timestamp}", html.P("No logs", className="text-muted small")

        formatted = format_log(logs, timestamp, product)

        # Highlight search term in the log content if active
        if search_term and search_term.lower() in formatted.lower():
            lines   = formatted.split("\n")
            content = []
            for line in lines:
                if search_term.lower() in line.lower():
                    idx    = line.lower().index(search_term.lower())
                    before = line[:idx]
                    match  = line[idx:idx + len(search_term)]
                    after  = line[idx + len(search_term):]
                    content.append(html.Div([
                        html.Span(before, style={"color": "#ccc"}),
                        html.Span(match,  style={"backgroundColor": "#FFD166",
                                                "color": "#111"}),
                        html.Span(after,  style={"color": "#ccc"}),
                    ], style={"fontFamily": "monospace", "fontSize": "12px",
                            "whiteSpace": "pre-wrap"}))
                else:
                    content.append(html.Div(
                        line,
                        style={"color": "#ccc", "fontFamily": "monospace",
                            "fontSize": "12px", "whiteSpace": "pre-wrap"},
                    ))
            return f"t = {timestamp}", content

        return (
            f"t = {timestamp}",
            html.Pre(formatted, style={
                "color": "#ccc", "fontFamily": "monospace",
                "fontSize": "12px", "whiteSpace": "pre-wrap", "margin": 0,
            })
        )