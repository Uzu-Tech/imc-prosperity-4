# dashboard/shared/callbacks.py
from dash import Input, Output
import plotly.graph_objects as go

FIGURE_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    height=None,
    font={"family": "monospace", "color": "#C8C8C8"},
    margin=dict(l=20, r=20, t=40, b=20),
)

def register_shared_callbacks(app, get_timestamps_fn, get_max_qty_fn):
    @app.callback(
        Output("timestamp-slider", "min"),
        Output("timestamp-slider", "max"),
        Output("timestamp-slider", "value"),
        Input("product-dropdown", "value"),
        Input("selector-dropdown", "value"),  # day-dropdown or log-dropdown
    )
    def reset_slider(product, selector):
        if not product or not selector:
            return 0, 1, [0, 1]
        timestamps = get_timestamps_fn(selector, product)
        return timestamps[0], timestamps[-1], [timestamps[0], timestamps[-1]]

    @app.callback(
        Output("trades-controls", "is_open"),
        Input("display-options", "value"),
    )
    def toggle_trade_controls(display_options):
        return "show_trades" in (display_options or [])

    @app.callback(
        Output("qty-slider", "max"),
        Output("qty-slider", "value"),
        Input("selector-dropdown", "value"),
        Input("product-dropdown",  "value"),
    )
    def reset_qty_slider(selector, product):
        if not product or not selector:
            return 100, [0, 100]
        max_qty = int(get_max_qty_fn(selector, product))
        return max_qty, [0, max_qty]