import dash_bootstrap_components as dbc
from dash import dcc, html
from dashboard.shared.components import (
    product_dropdown_col, toggle_col, trader_dropdown_col,
    trade_controls_collapse, timestamp_slider_row, CONTAINER_STYLE,
)
from loaders.log_loader import log_names

def get_layout():
    header_row = dbc.Row([
        dbc.Col(html.H4("Simulation Viewer", className="fw-bold mb-0",
                        style={"fontFamily": "monospace"}), width="auto"),
        dbc.Col(                                          # ← unique to strategy
            dbc.Select(
                id="selector-dropdown",
                options=[{"label": n, "value": n} for n in log_names],
                value=log_names[0] if log_names else None,
                className="bg-dark text-light border-light",
                style={"fontFamily": "monospace", "minWidth": "180px"},
            ),
            width="auto", className="ms-auto d-flex align-items-center",
        ),
        product_dropdown_col(),
        trader_dropdown_col()
    ], align="center", className="mb-3 mt-3")

    toggle_row = dbc.Row([
        toggle_col(
            extra_options=[
                {"label": " My Trades",  "value": "show_own_trades"},
                {"label": " My Quotes", "value": "show_own_makes"},
                {"label": " IMC Fair Price", "value": "show_imc_price"}
            ],
            default_values=["show_quotes", "show_trades", "show_own_trades", "show_own_makes", "show_imc_price"],
        )
    ], align="center", class_name="mb-3")

    order_book_graph = dbc.Col(
        dcc.Loading(
            type="circle", color="#5BC0DE",
            children=dcc.Graph(id="order-book-plot",
                config={"responsive": True, "displayModeBar": True},
                style={"height": "60vh"},
                clear_on_unhover=True
            )
        ), width=9
    )

    log_panel = dbc.Col([
        dbc.Row([
            dbc.Col(
                dbc.Input(
                    id="log-search",
                    placeholder="Search all logs e.g. ERROR, BUY...",
                    size="sm",
                    debounce=True,
                    style={
                        "backgroundColor": "#222", "color": "#ccc",
                        "border": "1px solid #444", "fontFamily": "monospace",
                        "fontSize": "11px",
                    },
                ),
            ),
        ], className="mb-2"),

        # Search results list — shown when searching
        html.Div(
            id="log-search-results",
            style={
                "fontFamily": "monospace", "fontSize": "11px",
                "overflowY": "auto", "maxHeight": "20vh",
                "borderBottom": "1px solid #333", "marginBottom": "8px",
                "display": "none",  # hidden when no search
            }
        ),

        html.P("Hover to inspect", id="log-timestamp",
            className="text-muted small mb-2",
            style={"fontFamily": "monospace"}),

        html.Div(
            id="log-content",
            style={
                "fontFamily": "monospace", "fontSize": "12px",
                "overflowY": "auto", "height": "55vh",
                "borderLeft": "1px solid #333", "paddingLeft": "16px",
            }
        ),

        # Hidden store for clicked search result timestamp
        dcc.Store(id="log-selected-timestamp"),

    ], width=3)



    position_pnl_graph = dbc.Col(
        dcc.Loading(
            type="circle", color="#5BC0DE",
            children=dcc.Graph(id="position-pnl-plot",
                config={"responsive": True, "displayModeBar": True},
                style={"height": "50vh"},
            )
        ), width=12
    )
    def metrics_card(label: str, value_id: str) -> dbc.Col:
        return dbc.Col(
            dbc.Card(dbc.CardBody([
                html.P(label, className="text-muted small mb-1",
                    style={"fontFamily": "monospace", "fontSize": "11px"}),
                html.H6(id=value_id, className="text-info mb-0",
                        style={"fontFamily": "monospace"}),
            ]), color="dark", outline=True, className="h-100"),
            width=2,
        )


    making_row = dbc.Row([
        dbc.Col(
            html.P("Market Making", className="text-muted small mb-0 mt-2",
                style={"fontFamily": "monospace", "fontSize": "11px",
                        "borderLeft": "2px solid #00D4FF", "paddingLeft": "8px"}),
            width=12, className="mb-1"
        ),
        metrics_card("Avg Fill Probability", "metric-fill-prob"),
        metrics_card("Avg Spread Captured",  "metric-avg-spread"),
        metrics_card("Avg Make Size",        "metric-avg-make-size"),
        metrics_card("Avg Fill Size",        "metric-avg-fill-size"),
        metrics_card("Avg Quote Distance",   "metric-quote-distance"),
        metrics_card("Quote Rate",           "metric-quote-rate"),
    ], className="mt-3 g-2")

    taking_row = dbc.Row([
        dbc.Col(
            html.P("Taking / Overall", className="text-muted small mb-0 mt-2",
                style={"fontFamily": "monospace", "fontSize": "11px",
                        "borderLeft": "2px solid #FF6EB4", "paddingLeft": "8px"}),
            width=12, className="mb-1"
        ),
        metrics_card("Total PnL",      "metric-total-pnl"),
        metrics_card("Avg Fill Quality","metric-fill-quality"),
        metrics_card("Num Takes",      "metric-num-takes"),
        metrics_card("Avg Take Size",   "avg-take-size"),
        metrics_card("Sharpe",         "metric-sharpe"),
        metrics_card("Max Drawdown",   "metric-max-drawdown"),
    ], className="mt-2 g-2")
    
    return dbc.Container([
        header_row,
        toggle_row,
        trade_controls_collapse(),
        dbc.Row([
            order_book_graph, log_panel,
        ], className="mb-2"),
        timestamp_slider_row(),
        dbc.Row([position_pnl_graph,], className="mt-4"),
        making_row, taking_row
    ], fluid=True, style=CONTAINER_STYLE)