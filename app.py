import dash
import dash_bootstrap_components as dbc

# Create the Dash app
app = dash.Dash(
    title="The swamp machine 4.0", 
    external_stylesheets=[dbc.themes.COSMO], 
    suppress_callback_exceptions=True, 
)