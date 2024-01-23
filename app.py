import dash
import dash_bootstrap_components as dbc

# Create the Dash app
app = dash.Dash(
    title="The swamp machine 4.0",
    external_stylesheets=[dbc.themes.COSMO, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

# Clientside callbacks ---------

app.clientside_callback(
    """
    function() {
        console.log("Client side callback triggered");
        document.getElementById("prod_barcode").focus();
        return;
    }
    """,
    dash.Output("retain_focus_main", "data", allow_duplicate=True),
    dash.Input("prod_barcode", "n_blur"),
    prevent_initial_call=True,
)

app.clientside_callback(
    """
    function() {
        console.log("Client side callback triggered");
        document.getElementById("new_trans_inp").focus();
        return;
    }
    """,
    dash.Output("retain_focus_main", "data", allow_duplicate=True),
    dash.Input("new_trans_inp", "n_blur"),
    prevent_initial_call=True,
)
