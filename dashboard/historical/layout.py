import dash_bootstrap_components as dbc
from dash import dcc, html
from dashboard.shared.components import (
    product_dropdown_col, toggle_col, trader_dropdown_col,
    trade_controls_collapse, timestamp_slider_row, CONTAINER_STYLE,
)
from loaders.csv_loader import get_day_dropdown_options, get_default_day_value

def get_layout():
    header_row = dbc.Row([
        dbc.Col(html.H4("Historical Data Viewer", className="fw-bold mb-0",
                        style={"fontFamily": "monospace"}), width="auto"),
        dbc.Col(                                          # ← unique to historical
            dbc.Select(
                id="selector-dropdown",
                options=get_day_dropdown_options(), # type: ignore
                value=get_default_day_value(),
                className="bg-dark text-light border-light",
                style={"fontFamily": "monospace", "minWidth": "180px"},
            ),
            width="auto", className="ms-auto d-flex align-items-center",
        ),
        product_dropdown_col(),
        trader_dropdown_col(),
        toggle_col(),
    ], align="center", className="mb-3 mt-3")

    return dbc.Container([
        header_row,
        trade_controls_collapse(),
        dbc.Row(dbc.Col(dcc.Loading(type="circle", color="#5BC0DE",
            children=dcc.Graph(id="order-book-plot",
                config={"responsive": True, "displayModeBar": True},
                style={"height": "65vh"})), width=12), className="mb-2"),
        timestamp_slider_row(),
    ], fluid=True, style=CONTAINER_STYLE)