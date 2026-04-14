import dash_bootstrap_components as dbc
from dash import dcc, html

def product_dropdown_col() -> dbc.Col:
    return dbc.Col(
        dbc.Select(
            id="product-dropdown",
            options=[], value=None,
            className="bg-dark text-light border-light",
            style={"fontFamily": "monospace", "minWidth": "140px"},
        ),
        width="auto", className="ms-2 d-flex align-items-center",
    )

def toggle_col(
    extra_options: list = [],
    default_values: list = ["show_quotes", "show_trades"],
) -> dbc.Col:
    base_options = [
        {"label": "Bot Quotes",     "value": "show_quotes"},
        {"label": "Bot Trades", "value": "show_trades"},
    ]
    return dbc.Col(
        dbc.Checklist(
            id="display-options",
            options=base_options + extra_options, # type: ignore
            value=default_values,
            inline=True, switch=True,
            className="text-light",
            style={"fontFamily": "monospace"},
        ),
        width="auto", className="d-flex align-items-center",
    )


def trade_controls_collapse() -> dbc.Collapse:
    return dbc.Collapse(
        dbc.Row([
            dbc.Col([
                html.P("Trade Quantity Range", className="text-muted small mb-1",
                       style={"fontFamily": "monospace"}),
                dcc.RangeSlider(
                    id="qty-slider", min=0, max=100, step=1,
                    value=[0, 100], marks=None, tooltip=None,
                ),
            ], width=5),
            dbc.Col([
                html.P("Exact Trade Quantity", className="text-muted small mb-1",
                       style={"fontFamily": "monospace"}),
                dbc.Input(
                    id="qty-exact", type="number", placeholder="e.g. 15", size="sm",
                    style={"backgroundColor": "#222", "color": "#ccc",
                           "border": "1px solid #444"},
                ),
            ], width=3),
        ], justify="center", align="end",
           className="mb-4", style={"columnGap": "80px"}),
        id="trades-controls",
        is_open=False,
    )

def timestamp_slider_row() -> dbc.Row:
    return dbc.Row(
        dbc.Col(
            dcc.RangeSlider(
                id="timestamp-slider", step=100,
                allowCross=False, tooltip=None, marks=None,
                className="px-2",
            ),
            width=12, className="mb-2",
        )
    )

CONTAINER_STYLE = {"minHeight": "100vh", "padding": "32px 48px"}