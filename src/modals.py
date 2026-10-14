from dash import html, dcc, dash_table
import dash_bootstrap_components as dbc
import pandas as pd
from src.database.data_connection import get_prods, get_trans, get_users
from src.components import get_table
from src.version import APP_VERSION

USER_COLS = ["rank", "team"]
DOCUMENTATION_URL = "https://thomashelboepoulsen.dk/mosen/docs"

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

user_body.append(
    dbc.Checklist(
        id={"type": "user_input", "index": "inp_is_guest_user"},
        options=[{"label": " Guest", "value": 1}],
        value=[],
        inline=True,
    )
)
user_body.append(html.Hr())
user_body.append(
    dbc.InputGroup(
        [
            dbc.InputGroupText("Early payment (DKK)"),
            dbc.Input(
                placeholder="0.00",
                id={"type": "user_input", "index": "inp_paid_user"},
                type="number",
                min=0,
                value=0,
            ),
        ]
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


PROD_COLS = ["price", "category", "initial_stock"]

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
            placeholder=col.replace("_", " ").title(),
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
                                "Updating stock recalculates waste using the selected allocation strategy."
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
                [
                    dbc.Button(
                        "Documentation",
                        id="open_documentation",
                        color="secondary",
                        className="me-auto",
                    ),
                    dbc.Button("Confirm", id="confirm_password"),
                ]
            ),
        ],
        size="md",
        id="password_modal",
    )
    return mdl


def documentation_modal():
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("Documentation")),
            dbc.ModalBody(
                [
                    html.Img(
                        src="assets/documentation-qr.png",
                        alt="QR code for the Mosen documentation",
                        className="documentation-qr",
                    ),
                    html.P("Scan with your phone for the setup and admin guide.", className="mb-2"),
                    html.Div(DOCUMENTATION_URL, className="documentation-address"),
                    html.P(
                        f"App version: {APP_VERSION}",
                        id="documentation_app_version",
                        className="mt-3 mb-0 text-muted",
                    ),
                ],
                className="text-center",
            ),
        ],
        id="documentation_modal",
        is_open=False,
        centered=True,
        size="md",
    )


def export_payments_modal():
    mdl = dbc.Modal(
        [
            dbc.ModalHeader("Export Payments"),
            dbc.ModalBody(
                [
                    html.P(
                        "Export payments after the final stock update. Exporting recalculates and saves waste using the selected allocation strategy."
                    ),
                    html.Hr(),
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


def remove_transaction_modal():
    return dbc.Modal(
        [
            dbc.ModalHeader("Remove transaction?"),
            dbc.ModalBody(id="remove_transaction_summary"),
            dbc.ModalFooter(
                html.Div(
                    [
                        dbc.Button(
                            "Remove transaction",
                            id="confirm_remove_transaction",
                            color="danger",
                        ),
                        dbc.Button(
                            "Cancel",
                            id="cancel_remove_transaction",
                            className="ms-2",
                        ),
                    ],
                    className="d-flex justify-content-end w-100",
                )
            ),
        ],
        id="remove_transaction_modal",
        is_open=False,
    )


def bad_rows_mdl():
    tables = ["users", "prods", "transactions"]
    table_defs = [
        html.P(
            "Upload aborted. The following bad rows were detected in your upload. You can edit them manually, and reupload"
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
                html.Div(
                    [
                        dbc.Button("Edit", id="edit_modal_edit"),
                        dbc.Button(
                            "Delete",
                            id="edit_modal_delete",
                            color="danger",
                            outline=True,
                        ),
                    ],
                    className="d-flex justify-content-between w-100",
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
