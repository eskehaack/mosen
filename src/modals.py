from dash import html, dcc
import dash_bootstrap_components as dbc
import pandas as pd
from src.data_connectors import get_prods, get_trans, get_users

USER_COLS = ["rank", "team"]

user_body = [
    dbc.Input(
        placeholder="Barcode",
        id={"type": "user_input", "index": f"inp_barcode_user"},
        type="number",
    ),
    html.Hr(),
    dbc.Input(placeholder="Name", id={"type": "user_input", "index": f"inp_name_user"}),
    html.Hr(),
]
for col in USER_COLS:
    user_body.append(
        dbc.Input(
            placeholder=col, id={"type": "user_input", "index": f"inp_{col}_user"}
        )
    )
    user_body.append(html.Hr())


def new_user_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Create new user"),
            dbc.ModalBody(user_body[:-1]),
            dbc.ModalFooter(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button("Confirm", id="confirm_user", disabled=True)
                            ),
                            dbc.Col(dbc.Button("Cancel", id="cancel_user")),
                        ]
                    )
                ]
            ),
        ],
        id="new_user_modal",
        is_open=False,
    )

    return mdl


PROD_COLS = ["price", "category", "current stock", "initial stock"]

prod_body = [
    dbc.Input(
        placeholder="Barcode",
        id={"type": "prod_input", "index": f"inp_barcode_prod"},
        type="number",
    ),
    html.Hr(),
    dbc.Input(placeholder="Name", id={"type": "prod_input", "index": f"inp_name_prod"}),
    html.Hr(),
]
for col in PROD_COLS:
    prod_body.append(
        dbc.Input(
            placeholder=col, id={"type": "prod_input", "index": f"inp_{col}_prod"}
        )
    )
    prod_body.append(html.Hr())


def new_prod_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Create new product"),
            dbc.ModalBody(prod_body[:-1]),
            dbc.ModalFooter(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                dbc.Button("Confirm", id="confirm_prod", disabled=True)
                            ),
                            dbc.Col(dbc.Button("Cancel", id="cancel_prod")),
                        ]
                    )
                ]
            ),
        ],
        id="new_prod_modal",
        is_open=False,
    )

    return mdl


def update_stock_modal():
    prods = get_prods()
    prods = prods.to_dict(orient="records")
    new_stock_inps = [
        dbc.Row(
            [
                dbc.Col(dcc.Input(placeholder=p["name"], disabled=True)),
                html.Br(),
                dbc.Col(dcc.Input(placeholder=p["initial_stock"], disabled=True)),
                html.Br(),
                dbc.Col(
                    dcc.Input(
                        value=p["current_stock"],
                        id={"type": "new_stock_inp", "index": f'{p["name"]}'},
                        type="number",
                        max=p["initial_stock"],
                    )
                ),
            ]
        )
        for p in prods
    ]
    new_stock_titles = [
        dbc.Row(
            [
                dbc.Col(html.P("Product")),
                html.Br(),
                dbc.Col(html.P("Total stock")),
                html.Br(),
                dbc.Col(html.P("Current stock")),
            ]
        )
    ]

    new_stock_inps = new_stock_titles + new_stock_inps

    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Update product stock"),
            dbc.ModalBody(new_stock_inps),
            dbc.ModalFooter(
                dbc.Row(
                    [
                        dbc.Col(
                            html.P(
                                "Updating stock will apply possible waste to all users."
                            )
                        ),
                        dbc.Col(dbc.Button("Confirm", id="confirm_new_stock")),
                    ]
                )
            ),
        ],
        size="lg",
        id="new_stock_modal",
    )
    return mdl


def password_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Input Password"),
            dbc.ModalBody(
                dbc.Input(placeholder="Password", type="password", id="password_input")
            ),
            dbc.ModalFooter(
                dbc.Row([dbc.Col(dbc.Button("Confirm", id="confirm_password"))])
            ),
        ],
        size="md",
        id="password_modal",
    )
    return mdl
