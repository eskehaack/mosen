from dash import dcc, html, callback, Input, Output, State, ctx, no_update
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
)
from src.trans_layout import trans_modal
from src.main_page_callbacks import create_overview
from src.components import get_upload
from src.connection import get_password, get_paths, get_show_bill
from src.data_connectors import get_trans, get_users, get_prods
from app import app

PASSWORD = get_password()
SHOW_BILL = get_show_bill()


def user_settings_layout(user_path):
    for file in [user_path]:
        if not os.path.isfile(file):
            return dbc.Container([html.H1("Error 404, file path not found")])
    layout = dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                dbc.Button("Create new user", id="new_user_btn"),
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
                                    row_deletable=True,
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
        ],
    )
    return layout


def product_settings_layout(prods_path, users_path):
    for file in [prods_path]:
        if not os.path.isfile(file):
            return dbc.Container([html.H1("Error 404, file path not found")])
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
            dcc.Store(
                id="waste_value",
                data=get_waste() / len(get_users()),
            ),
        ]
    )
    return layout


def transaction_settings_layout(trans_path, users_path, prods_path):
    for file in [trans_path, users_path, prods_path]:
        if not os.path.isfile(file):
            return dbc.Container([html.H1("Error 404, file path not found")])
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
                                dbc.Button("Export payments", id="export_payments"),
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
        ],
    )
    return layout


def settings_settings_layout(password, trans_path, users_path, prods_path, show_bill):
    layout = dbc.Container(
        [
            dbc.Row(
                [
                    html.Br(),
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(html.H3("User Table Location: ")),
                                html.Br(),
                                dbc.Col(get_upload("user_file", users_path)),
                            ]
                        ),
                        width=12,
                    ),
                    html.Hr(),
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(html.H3("Transaction Table Location: ")),
                                html.Br(),
                                dbc.Col(get_upload("trans_file", trans_path)),
                            ]
                        ),
                        width=12,
                    ),
                    html.Hr(),
                    dbc.Col(
                        dbc.Row(
                            [
                                dbc.Col(html.H3("Product Table Location: ")),
                                html.Br(),
                                dbc.Col(get_upload("prods_file", prods_path)),
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
                                        placeholder=password,
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
                                        id="display_bill_switch", value=show_bill
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
                                dbc.Col(width=8),
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
            )
        ]
    )
    return layout


def settings_mode_func():
    prods_path, trans_path, users_path = get_paths()
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
                            children=user_settings_layout(users_path),
                            id="user_settings",
                        ),
                        dcc.Tab(
                            label="Products",
                            value="products",
                            children=product_settings_layout(prods_path, users_path),
                            id="product_settings",
                        ),
                        dcc.Tab(
                            label="Economy",
                            value="economy",
                            children=transaction_settings_layout(
                                trans_path, users_path, prods_path
                            ),
                            id="economy_settings",
                        ),
                        dcc.Tab(
                            label="Settings",
                            value="settings",
                            children=settings_settings_layout(
                                PASSWORD, trans_path, users_path, prods_path, SHOW_BILL
                            ),
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
        if password == PASSWORD:
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
        if password == PASSWORD:
            return True, ""
    return False, no_update


@callback(
    Output("user_settings", "children"),
    Output("product_settings", "children"),
    Output("economy_settings", "children"),
    Input("setting_tabs", "value"),
)
def update_trans_table(trigger):
    prods_path, trans_path, users_path = get_paths()
    return (
        user_settings_layout(users_path),
        product_settings_layout(prods_path, users_path),
        transaction_settings_layout(trans_path, users_path, prods_path),
    )
