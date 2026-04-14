import dash
import dash_bootstrap_components as dbc
from dashboard.simulation.layout import get_layout
from dashboard.simulation.callbacks import register_callbacks

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.SLATE])
app.layout = get_layout()
register_callbacks(app)

if __name__ == "__main__":
    app.run(debug=True)