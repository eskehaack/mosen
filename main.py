import dash
from dash import dcc, html
from src.settings_layout import layout_func
import dash_bootstrap_components as dbc

# Create the Dash app
app = dash.Dash("Moskemaskinen", external_stylesheets=[dbc.themes.COSMO])
# Define the layout of the app
app.layout = layout_func

# Run the app
if __name__ == '__main__':
    print("Running....")
    app.run(debug=True)