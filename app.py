import dash
import dash_bootstrap_components as dbc

from src.container import Container
from src.database.data_connection import Database
from src.analytics.TopUserChartData import TopUserChartData


# Initialize database container
Container.set(Database, Database())
Container.set(TopUserChartData, TopUserChartData())

# Create the Dash app
app = dash.Dash(
    title="Mosemaskinen",
    # external_stylesheets=[dbc.themes.LITERA, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

# Clientside callbacks ---------

dash.clientside_callback(
    """
    function(documentationOpen, passwordOpen) {
        if (!documentationOpen && passwordOpen) {
            // Wait for the closing fade and the modal's own focus restoration.
            window.setTimeout(function() {
                const input = document.getElementById("password_input");
                if (input && input.closest(".modal.show") &&
                    !document.getElementById("documentation_modal")) {
                    input.focus();
                }
            }, 350);
        }
        return window.dash_clientside.no_update;
    }
    """,
    dash.Output("retain_focus_password", "data"),
    dash.Input("documentation_modal", "is_open"),
    dash.State("password_modal", "is_open"),
    prevent_initial_call=True,
)

dash.clientside_callback(
    """
    function(trig, newT, settings, password) {
        if (newT && !settings && !password) {
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
