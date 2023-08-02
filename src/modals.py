from dash import html, dcc
import dash_bootstrap_components as dbc
import pandas as pd

USER_COLS = [
    "barcode", #mandatory
    "name", #mandatory
    "rank",
    "team"
]

user_body = []
for col in USER_COLS:
    user_body.append(dbc.Input(placeholder=col, id={"type": "input", "index": f"inp_{col}"}))
    user_body.append(html.Hr())
    
def new_user_modal():
    mdl = dbc.Modal([
            dbc.ModalHeader("Create new user"),
            dbc.ModalBody(
                user_body[:-1]
            ),
            dbc.ModalFooter([
                dbc.Row([
                    dbc.Col(dbc.Button("Confirm", id="confirm_user", disabled=True)),
                    dbc.Col(dbc.Button("Cancel", id="cancel_user"))
                ]
                )
            ])
        ],
        id="new_user_modal",
        is_open=False
    )
    
    return mdl