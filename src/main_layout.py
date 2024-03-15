import keyboard as k
import time
from dash import dcc, html, callback, Input, Output, State, ctx, no_update
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
import os
from src.tables.prod_table import get_waste, get_waste_table
from src.tables.trans_table import (
    get_revenue,
    get_income,
    get_total_income,
    get_current_return,
)
from src.modals import (
    new_user_modal,
    new_prod_modal,
    update_stock_modal,
    password_modal,
    export_payments_modal,
    export_barcodes_mdl,
    bad_rows_mdl,
    edit_modal,
    reset_modal,
)
from src.trans_layout import trans_modal
from src.main_page_callbacks import create_overview
from src.components import get_upload, get_table
from src.data_connection import (
    get_prods,
    get_trans,
    get_users,
    get_password,
    get_show_bill,
)
from src.tables.user_table import init
from app import app

users_init = init()


def user_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    dbc.Button("Create new user", id="new_user_btn"),
                                    html.Hr(),
                                    dbc.Button(
                                        "Download users",
                                        id={
                                            "index": "users",
                                            "type": "download_trigger_btn",
                                        },
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Edit users",
                                        id="edit_users",
                                    ),
                                    dcc.Download(
                                        id={
                                            "index": "users",
                                            "type": "download_trigger",
                                        }
                                    ),
                                ],
                            ),
                            width=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [
                                    get_table(
                                        "user_table",
                                        get_users().to_dict(orient="records"),
                                        300,
                                    )
                                ],
                            ),
                            width=9,
                        ),
                    ],
                    align="center",
                    style={"height": "100%"},
                ),
                className="show_box",
            ),
            new_user_modal(),
            dcc.Store(id="edit_modal_row"),
            dcc.Store(id={"index": "users", "type": "bad_rows"}),
        ],
    )
    return layout


def product_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    dbc.Button("Create new product", id="new_prod_btn"),
                                    html.Hr(),
                                    dbc.Button("Update stock", id="open_update_stock"),
                                    html.Hr(),
                                    dbc.Button(
                                        "Download Products",
                                        id={
                                            "index": "prods",
                                            "type": "download_trigger_btn",
                                        },
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Edit products",
                                        id="edit_prods",
                                    ),
                                    dcc.Download(
                                        id={
                                            "index": "prods",
                                            "type": "download_trigger",
                                        }
                                    ),
                                ]
                            ),
                            width=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [
                                    get_table(
                                        "prod_table",
                                        get_prods().to_dict(orient="records"),
                                        200,
                                    ),
                                    html.Hr(),
                                    get_table(
                                        "waste_table",
                                        get_waste_table(),
                                        200,
                                    ),
                                ]
                            ),
                            width=9,
                        ),
                    ],
                    align="center",
                ),
                className="show_box",
            ),
            new_prod_modal(),
            update_stock_modal(),
            dcc.Store(id={"index": "prods", "type": "bad_rows"}),
        ]
    )
    return layout


def transaction_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    html.P(
                                        f"Initially Projected Revenue: {get_total_income()}"
                                    ),
                                    html.Hr(),
                                    html.P(f"Current Revenue: {get_revenue()}"),
                                    html.Hr(),
                                    html.P(f"Current Waste: {get_waste()}"),
                                    html.Hr(),
                                    html.P(f"Current Return: {get_current_return()}"),
                                    html.Hr(),
                                    dbc.Button(
                                        "Export payments", id="export_payments_btn"
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Download Raw Transactions",
                                        id={
                                            "index": "transactions",
                                            "type": "download_trigger_btn",
                                        },
                                    ),
                                    dcc.Download(
                                        id={
                                            "index": "transactions",
                                            "type": "download_trigger",
                                        }
                                    ),
                                ]
                            ),
                            width=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [
                                    get_table(
                                        "trans_table",
                                        get_trans().to_dict(orient="records"),
                                        200,
                                    ),
                                    html.Hr(),
                                    get_table("income_table", get_income(), 200),
                                ]
                            ),
                            width=9,
                        ),
                    ]
                ),
                className="show_box",
            ),
            dcc.Store(id="placeholder_for_empty_output"),
            export_payments_modal(),
            dcc.Download(id="payments_download"),
            dcc.Store(id={"index": "transactions", "type": "bad_rows"}),
        ],
    )
    return layout


def settings_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        html.Br(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Upload user database: "), width=4),
                                    dbc.Col(get_upload("users")),
                                    dbc.Col(
                                        html.P(
                                            id={
                                                "index": "users",
                                                "type": "show_upload_file",
                                            }
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.P("Upload product database: "), width=4
                                    ),
                                    dbc.Col(get_upload("prods")),
                                    dbc.Col(
                                        html.P(
                                            id={
                                                "index": "prods",
                                                "type": "show_upload_file",
                                            }
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.P(
                                            "Upload transaction database \n(not recommended): "
                                        ),
                                        width=4,
                                    ),
                                    dbc.Col(get_upload("transactions")),
                                    dbc.Col(
                                        html.P(
                                            id={
                                                "index": "transactions",
                                                "type": "show_upload_file",
                                            }
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Display current bill: "), width=4),
                                    dbc.Col(
                                        dbc.Switch(
                                            id="display_bill_switch",
                                            value=get_show_bill(),
                                        )
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Password: "), width=4),
                                    dbc.Col(
                                        dbc.Input(
                                            value=get_password(),
                                            id="settings_password",
                                            type="text",
                                            minLength=1,
                                        ),
                                        width=4,
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "Confirm Password",
                                            id="confirm_new_password",
                                        ),
                                        width=4,
                                        align="center",
                                    ),
                                ],
                                align="center",
                            ),
                            width=12,
                        ),
                        dbc.Col(html.Hr()),
                        dbc.Col(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                "Export Barcodes",
                                                id="export_barcodes_btn",
                                            ),
                                            width=4,
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Reset app",
                                                id="reset_app",
                                                color="danger",
                                            ),
                                            width=4,
                                        ),
                                        dbc.Col(
                                            dbc.Button("Close app", id="close_app_btn"),
                                            width=4,
                                        ),
                                    ],
                                    align="center",
                                ),
                            ],
                            width=12,
                        ),
                    ],
                    align="center",
                ),
                className="show_box",
            ),
            dbc.Alert(
                "You removed the password, I set it to OLProgram, as this is the default. Please remember this!!!",
                color="danger",
                id="bad_password_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            dbc.Alert(
                "There was an error in the data that you uploaded, please check the input and try again",
                color="danger",
                id="bad_data_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            dbc.Alert(
                "You have succesfully updated the password!",
                color="success",
                id="new_password_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            export_barcodes_mdl(),
            bad_rows_mdl(),
            reset_modal(),
        ]
    )
    return layout


def settings_mode_func():
    return dbc.Modal(
        [
            dbc.ModalHeader(html.H1("Settings")),
            dbc.ModalBody(
                dcc.Tabs(
                    id="setting_tabs",
                    children=[
                        dcc.Tab(
                            label="Users",
                            value="users",
                            children=user_settings_layout(),
                            id="user_settings",
                        ),
                        dcc.Tab(
                            label="Products",
                            value="products",
                            children=product_settings_layout(),
                            id="product_settings",
                        ),
                        dcc.Tab(
                            label="Economy",
                            value="economy",
                            children=transaction_settings_layout(),
                            id="economy_settings",
                        ),
                        dcc.Tab(
                            label="Settings",
                            value="settings",
                            children=settings_settings_layout(),
                            id="settings_settings",
                        ),
                    ],
                ),
            ),
        ],
        id="settings_modal",
        fullscreen=True,
        is_open=False,
    )


def layout_func():
    layout = dbc.Container(
        [
            html.Div(
                [
                    dbc.Col(
                        [
                            dbc.Row(html.Br()),
                            dbc.Row(
                                [
                                    dbc.Col(html.H1(app.title), width=11),
                                    dbc.Col(
                                        dbc.Button(
                                            html.I(className="bi bi-sliders"),
                                            id="open_settings",
                                        ),
                                        width=1,
                                    ),
                                ],
                            ),
                            dbc.Row(
                                dbc.Input(id="new_trans_inp", autoFocus=True),
                            ),
                        ],
                        width=12,
                    ),
                    html.Div(
                        [
                            dbc.Col(
                                children=dcc.Graph(
                                    figure=create_overview(
                                        graph_col := "team", average=False
                                    ),
                                    id="overview_graph",
                                    config={"displayModeBar": False},
                                ),
                            ),
                            html.Br(),
                            dbc.Col(
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.RadioItems(
                                                options=[
                                                    {"label": "Teams", "value": "team"},
                                                    {"label": "Ranks", "value": "rank"},
                                                    {
                                                        "label": "Products",
                                                        "value": "products",
                                                    },
                                                ],
                                                value=graph_col,
                                                id="graph_selection",
                                                inline=True,
                                            ),
                                            width=3,
                                        ),
                                        dbc.Col(
                                            dbc.Switch(
                                                id="graph_average",
                                                value=False,
                                                label="Average",
                                            ),
                                        ),
                                    ]
                                )
                            ),
                        ],
                        className="show_box",
                    ),
                ]
            ),
            settings_mode_func(),
            trans_modal(),
            password_modal(),
            edit_modal(),
            dcc.Store(id="update_settings"),
            dbc.Alert(
                "There are no users, ya dumb dumb!",
                color="danger",
                id="bad_barcode_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            dcc.Store(id="retain_focus_main", data=None),
            dcc.Store(id="retain_focus_prod", data=None),
        ]
    )

    return layout


@callback(
    Output("password_modal", "is_open"),
    Input("open_settings", "n_clicks"),
    Input("confirm_password", "n_clicks"),
    Input("password_input", "n_submit"),
    State("password_input", "value"),
)
def open_password(trigger_open, trigger_close, trigger_enter, password):
    trigger = ctx.triggered_id
    if trigger is not None and trigger == "open_settings":
        return True
    elif trigger is not None and (
        trigger == "confirm_password" or trigger == "password_input"
    ):
        if password == get_password():
            return False
    return no_update


@callback(
    Output("settings_modal", "is_open"),
    Output("password_input", "value"),
    Input("confirm_password", "n_clicks"),
    Input("password_input", "n_submit"),
    State("password_input", "value"),
)
def open_settings(trigger, trigger_enter, password):
    if (trigger is not None and trigger > 0) or (
        trigger_enter is not None and trigger_enter > 0
    ):
        if password == get_password():
            return True, ""
    return False, no_update


@callback(
    Output("user_settings", "children"),
    Output("product_settings", "children"),
    Output("economy_settings", "children"),
    Input("setting_tabs", "value"),
    Input("confirm_prod", "n_clicks"),
    Input("confirm_user", "n_clicks"),
    Input("delete_data_btn", "n_clicks"),
)
def update_settings_layout(trigger, prods_trigger, user_trigger, reset_trigger):
    time.sleep(1)
    return (
        user_settings_layout(),
        product_settings_layout(),
        transaction_settings_layout(),
    )


@callback(
    Output("close_app_btn", "disabled"),
    Input("close_app_btn", "n_clicks"),
)
def close_appI(trigger):
    if trigger is not None:
        k.unhook_all()
        k.send("alt+f4")
    return no_update
