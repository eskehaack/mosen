import dash
import dash_bootstrap_components as dbc

# Create the Dash app
app = dash.Dash(
    title="Mosemaskinen 4.0",
    external_stylesheets=[dbc.themes.LITERA, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

# Clientside callbacks ---------

dash.clientside_callback(
    """
    function(trig, newT, settings, password) {
        if (newT && !settings && !password) {
            console.log("Prod focus");
            document.getElementById("prod_barcode").focus();
        }
        return;
    }
    """,
    dash.Output("retain_focus_prod", "data"),
    dash.Input("prod_barcode", "n_blur"),
    dash.State("new_trans_modal", "is_open"),
    dash.State("settings_modal", "is_open"),
    dash.State("password_modal", "is_open"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(trig, newT, settings, password) {
        if (!newT && !settings && !password) {
            console.log("Main focus");
            document.getElementById("new_trans_inp").focus();
            return;
        }
    }
    """,
    dash.Output("retain_focus_main", "data"),
    dash.Input("new_trans_inp", "n_blur"),
    dash.State("new_trans_modal", "is_open"),
    dash.State("settings_modal", "is_open"),
    dash.State("password_modal", "is_open"),
    prevent_initial_call=True,
)
