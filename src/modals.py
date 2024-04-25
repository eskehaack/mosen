from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from src.data_connection import get_prods, get_trans, get_users
from src.components import get_table

USER_COLS = ["rank", "team"]

user_body = [
    dbc.Input(
        placeholder="Barcode",
        id={"type": "user_input", "index": f"inp_barcode_user"},
        type="number",
        min=1000,
        max=99999999999,
        invalid=True,
    ),
    html.Hr(),
    dbc.Input(placeholder="Name", id={"type": "user_input", "index": f"inp_name_user"}),
    html.Hr(),
]
for col in USER_COLS:
    user_body.append(
        dbc.Input(
            placeholder=col.replace("_", " ").title(),
            id={"type": "user_input", "index": f"inp_{col}_user"},
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


PROD_COLS = ["price", "category", "current_stock", "initial_stock"]

prod_body = [
    dbc.Input(
        placeholder="Barcode",
        id={"type": "prod_input", "index": f"inp_barcode_prod"},
        type="number",
        min=100,
        max=999,
        invalid=True,
    ),
    html.Hr(),
    dbc.Input(placeholder="Name", id={"type": "prod_input", "index": f"inp_name_prod"}),
    html.Hr(),
]
for col in PROD_COLS:
    prod_body.append(
        dbc.Input(
            placeholder=col.replace("_", " ").title()
            + ("(typically same as Initial Stock)" if col == "current_stock" else ""),
            id={"type": "prod_input", "index": f"inp_{col}_prod"},
            type="text" if col == "category" else "number",
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
                dbc.Input(
                    placeholder="Password",
                    type="password",
                    id="password_input",
                    autofocus=True,
                )
            ),
            dbc.ModalFooter(
                dbc.Row([dbc.Col(dbc.Button("Confirm", id="confirm_password"))])
            ),
        ],
        size="md",
        id="password_modal",
    )
    return mdl


def export_payments_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Export Payments"),
            dbc.ModalBody(
                [
                    dbc.Col(
                        [
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Add income: "), width=8),
                                    dbc.Col(
                                        dbc.Input(
                                            id="added_amount_inp",
                                            value=0,
                                            min=0,
                                            type="number",
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            html.Hr(),
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Round"), width=2),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            ["Up", "Down", "Nearest"],
                                            value="Up",
                                            clearable=False,
                                            multi=False,
                                            id="up_down_dd",
                                        ),
                                        width=3,
                                    ),
                                    dbc.Col(html.P("to nearest: "), width=3),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            [0, 1, 2, 5, 10],
                                            value=0,
                                            clearable=False,
                                            multi=False,
                                            id="round_dd",
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                        ]
                    ),
                ]
            ),
            dbc.ModalFooter(
                dbc.Row([dbc.Col(dbc.Button("Confirm", id="confirm_payments"))])
            ),
        ],
        size="md",
        id="payments_modal",
    )
    return mdl


def export_barcodes_mdl():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Export Barcodes"),
            dbc.ModalBody(
                [
                    html.P("Number of guest barcodes:"),
                    dbc.Input(id="guest_barcodes_inp", type="number", value=10),
                ]
            ),
            dbc.ModalFooter(dbc.Button("Confirm", id="confirm_export_barcodes")),
            dcc.Store(id="pdf_download"),
        ],
        size="md",
        id="export_barcodes_modal",
    )
    return mdl


def bad_rows_mdl():
    tables = ["users", "prods", "transactions"]
    table_defs = [
        html.P(
            "The following bad rows were detected in your upload. You can edit them manually, and reupload the file, if the below data is not what you wanted."
        )
    ]
    for table in tables:
        table_defs.extend(
            [
                html.Hr(),
                html.P(table.title()),
                html.Br(),
                dash_table.DataTable(
                    id={"index": table, "type": "bad_rows_table"},
                    style_cell={"color": "black"},
                ),
            ]
        )
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Bad Rows"),
            dbc.ModalBody(table_defs),
        ],
        id="bad_rows_modal",
        size="lg",
    )
    return mdl


def edit_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Edit or delete data?"),
            dbc.ModalBody(
                [
                    html.P("Input barcode for user/product:", id="edit_text"),
                    dbc.Input(id="edit_input", placeholder="Barcode"),
                ]
            ),
            dbc.ModalFooter(
                dbc.Row(
                    [
                        # dbc.Col(width=6),
                        dbc.Col(dbc.Button("Delete", id="edit_modal_delete")),
                        dbc.Col(dbc.Button("Edit", id="edit_modal_edit")),
                    ]
                )
            ),
        ],
        id="edit_data_modal",
        size="lg",
        is_open=False,
    )
    return mdl


def reset_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Reset Database and Delete All Data?"),
            dbc.ModalBody(
                [
                    html.P("Are you sure you want to delete all data?"),
                    html.Br(),
                    html.P("This is irreversible!!"),
                    html.Br(),
                    html.P("The app will close down once it has been reset."),
                ]
            ),
            dbc.ModalFooter(
                dbc.Row(
                    [
                        dbc.Col(
                            dbc.Button("Delete", id="delete_data_btn", color="danger")
                        ),
                        dbc.Col(dbc.Button("Cancel", id="cancel_delete_data_btn")),
                    ]
                )
            ),
        ],
        id="reset_data_modal",
        size="md",
        is_open=False,
    )
    return mdl


def study_users_modal():
    available_users = list(get_users()["barcode"])
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Take a closer look at what users bought."),
            dbc.ModalBody(
                [
                    dbc.Row(
                        dcc.Dropdown(
                            id="study_users_dd",
                            options=available_users,
                            multi=True,
                            style={"color": "black"},
                        ),
                    ),
                    html.Hr(),
                    dbc.Row(
                        dcc.Graph(id="study_user_table"),
                        className="show_box",
                    ),
                ]
            ),
        ],
        id="study_users_modal",
        size="lg",
        is_open=False,
    )
    return mdl
