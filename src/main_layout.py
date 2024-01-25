from dash import dcc, html, callback, Input, Output, State, ctx, no_update
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
from dash import dash_table
import os
from src.tables.prod_table import get_waste
from src.tables.trans_table import get_revenue, get_income
from src.modals import (
    new_user_modal,
    new_prod_modal,
    update_stock_modal,
    password_modal,
    export_payments_modal,
    export_barcodes_mdl,
    bad_rows_mdl,
    edit_modal,
)
from src.trans_layout import trans_modal
from src.main_page_callbacks import create_overview
from src.components import get_upload
from src.connection import get_password, get_show_bill
from src.data_connectors import get_prods, get_trans, get_users
from src.tables.user_table import init
from app import app

users_init = init()


def user_settings_layout():
    layout = dbc.Container(
        [
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
                                dash_table.DataTable(
                                    id="user_table",
                                    data=get_users().to_dict(orient="records"),
                                    row_deletable=False,
                                )
                            ],
                        ),
                        width=9,
                    ),
                ],
                align="center",
                style={"height": "100%"},
            ),
            new_user_modal(),
            edit_modal(),
            dcc.Store(id="edit_modal_row"),
            dcc.Store(id={"index": "users", "type": "bad_rows"}),
        ],
    )
    return layout


def product_settings_layout():
    layout = dbc.Container(
        [
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
                                dash_table.DataTable(
                                    id="prod_table",
                                    data=get_prods().to_dict(orient="records"),
                                )
                            ]
                        ),
                        width=9,
                    ),
                ],
                align="center",
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
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.P(f"Total revenue: {get_revenue()}"),
                                html.Hr(),
                                html.P(f"Total waste generated: {get_waste()}"),
                                html.Hr(),
                                dbc.Button("Export payments", id="export_payments_btn"),
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
                                dash_table.DataTable(
                                    id="trans_table",
                                    data=get_trans().to_dict(
                                        orient="records"
                                    ),  # [['barcode_user', 'user', 'product', 'price', 'timestamp']].to_dict(orient="records"),
                                    style_table={
                                        "height": "300px",
                                        "overflowY": "auto",
                                    },
                                ),
                                html.Hr(),
                                dash_table.DataTable(
                                    id="income_table",
                                    data=get_income(),
                                    style_table={
                                        "height": "300px",
                                        "overflowY": "auto",
                                    },
                                ),
                            ]
                        ),
                        width=9,
                    ),
                ]
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
            dbc.Row(
                [
                    html.Br(),
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(html.H3("Upload user database: ")),
                                html.Br(),
                                dbc.Col(get_upload("users")),
                                html.Br(),
                                dbc.Col(
                                    html.P(
                                        id={
                                            "index": "users",
                                            "type": "show_upload_file",
                                        }
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
                                dbc.Col(html.H3("Upload product database: ")),
                                html.Br(),
                                dbc.Col(get_upload("prods")),
                                html.Br(),
                                dbc.Col(
                                    html.P(
                                        id={
                                            "index": "prods",
                                            "type": "show_upload_file",
                                        }
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
                                dbc.Col(
                                    html.H3(
                                        "Upload transaction database \n(not recommended): "
                                    )
                                ),
                                html.Br(),
                                dbc.Col(get_upload("transactions")),
                                html.Br(),
                                dbc.Col(
                                    html.P(
                                        id={
                                            "index": "transactions",
                                            "type": "show_upload_file",
                                        }
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
                                dbc.Col(html.H3("Password: ")),
                                html.Br(),
                                dbc.Col(
                                    dbc.Input(
                                        value=get_password(),
                                        id="settings_password",
                                        type="text",
                                        minLength=1,
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
                                dbc.Col(html.H3("Display current bill: ")),
                                html.Br(),
                                dbc.Col(
                                    dbc.Switch(
                                        id="display_bill_switch", value=get_show_bill()
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
                                dbc.Col(
                                    dbc.Button(
                                        "Export Barcodes", id="export_barcodes_btn"
                                    ),
                                    width=8,
                                ),
                                html.Br(),
                                dbc.Col(
                                    dbc.Button(
                                        "Confirm Settings", id="confirm_settings"
                                    )
                                ),
                            ]
                        ),
                        width=12,
                    ),
                ]
            ),
            dbc.Alert(
                "You removed the password, if set it to OLProgram, as this is the default. Please remember this!!!",
                color="danger",
                id="bad_password_alert",
                is_open=False,
            ),
            dbc.Alert(
                "There was an error in the data that you uploaded, please check the input and try again",
                color="danger",
                id="bad_data_alert",
                is_open=False,
            ),
            export_barcodes_mdl(),
            bad_rows_mdl(),
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
                                    figure=create_overview("team"),
                                    id="overview_graph",
                                    config={"displayModeBar": False},
                                ),
                            )
                        ]
                    ),
                ]
            ),
            settings_mode_func(),
            trans_modal(),
            password_modal(),
            dcc.Store(id="update_settings"),
            dbc.Alert(
                "There are no users, ya dumb dumb!",
                color="danger",
                id="bad_barcode_alert",
                is_open=False,
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
    State("password_input", "value"),
)
def open_settings(trigger_open, trigger_close, password):
    trigger = ctx.triggered_id
    if trigger is not None and trigger == "open_settings":
        return True
    elif trigger is not None and trigger == "confirm_password":
        if password == get_password():
            return False
    return no_update


@callback(
    Output("settings_modal", "is_open"),
    Output("password_input", "value"),
    Input("confirm_password", "n_clicks"),
    State("password_input", "value"),
)
def open_settings(trigger, password):
    if trigger is not None and trigger > 0:
        if password == get_password():
            return True, ""
    return False, no_update


@callback(
    Output("user_settings", "children"),
    Output("product_settings", "children"),
    Output("economy_settings", "children"),
    Input("setting_tabs", "value"),
)
def update_trans_table(trigger):
    return (
        user_settings_layout(),
        product_settings_layout(),
        transaction_settings_layout(),
    )
