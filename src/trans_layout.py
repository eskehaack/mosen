from dash import dcc, html, callback, Input, Output, State, dash_table, no_update, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime
from src.tables.prod_table import get_waste
from src.data_connectors import (
    get_prods,
    get_trans,
    get_users,
    get_current_trans,
    update_current_trans,
    upload_values,
    reset_current_trans,
)


def trans_modal():
    modal = dbc.Modal(
        [
            dbc.ModalHeader(
                dbc.Col(
                    dbc.Row(
                        [
                            dbc.Col(html.H1(id="new_trans_user")),
                        ]
                    ),
                    width=12,
                )
            ),
            dbc.ModalBody(
                dbc.Col(
                    [
                        dbc.Row(
                            [
                                dbc.Col(
                                    html.Div(
                                        [html.H1("Products: ")], id="show_current_prods"
                                    )
                                ),
                                dbc.Col(
                                    children=dcc.Graph(id="trans_graph"),
                                    id="prod_barchart",
                                ),
                            ]
                        ),
                        dbc.Row(
                            [
                                dash_table.DataTable(id="show_prods"),
                                dbc.Input(
                                    placeholder="Product barcode",
                                    id="prod_barcode",
                                    autoFocus=True,
                                ),
                            ]
                        ),
                    ]
                )
            ),
        ],
        is_open=False,
        id="new_trans_modal",
        fullscreen=True,
    )
    return modal


@callback(
    Output("trans_graph", "figure"),
    Output("show_prods", "data"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
)
def get_transactions(trigger, barcode):
    transactions = get_trans()
    users = get_users()
    prods = get_prods()

    user_barcodes = list(users["barcode"])
    if not (trigger is not None and int(barcode) in user_barcodes):
        return no_update
    user_trans = transactions[transactions["barcode_user"] == int(barcode)]
    trans_data = [
        {
            p: sum(
                [1 if p == row["product"] else 0 for i, row in user_trans.iterrows()]
            )
            for p in list(prods["name"])
        }
    ]
    return px.bar(trans_data), trans_data


@callback(
    Output("new_trans_modal", "is_open"),
    Output("new_trans_inp", "value"),
    Output("prod_barcode", "value", allow_duplicate=True),
    Output("bad_barcode_alert", "is_open"),
    Input("new_trans_inp", "n_submit"),
    Input("prod_barcode", "n_submit"),
    State("new_trans_inp", "value"),
    State("prod_barcode", "value"),
    prevent_initial_call=True,
)
def open_trans_modal(trigger_open, trigger_close, barcode_open, barcode_close):
    users = get_users()
    prods = get_prods()
    transactions = get_trans()
    current = get_current_trans()
    user_barcodes = list(users["barcode"])
    trigger = ctx.triggered_id
    if trigger == "new_trans_inp":
        if len(user_barcodes) < 1:
            return no_update, "", no_update, True
        if int(barcode_open) in user_barcodes:
            reset_current_trans()
            return True, no_update, "", False
        return no_update, "", no_update, False
    elif trigger == "prod_barcode" and int(barcode_close) == int(barcode_open):
        for _, row in current.iterrows():
            new_row = pd.DataFrame(
                [
                    {
                        "barcode_user": barcode_open,
                        "user": str(
                            users[users["barcode"] == int(barcode_open)]["name"].values[
                                0
                            ]
                        ),
                        "barcode_prod": row["barcode_prod"],
                        "product": row["name"],
                        "price": str(
                            prods[prods["barcode"] == int(row["barcode_prod"])][
                                "price"
                            ][0]
                        ),
                        "timestamp": str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                    }
                ]
            )
            transactions = pd.concat([transactions, new_row])
        upload_values(transactions, "transactions")
        return False, "", no_update, False
    return no_update, no_update, no_update, False


@callback(
    Output("show_current_prods", "children"),
    Output("prod_barcode", "value"),
    Input("prod_barcode", "n_submit"),
    State("prod_barcode", "value"),
    State("new_trans_inp", "value"),
    prevent_initial_call=True,
)
def new_trans(trigger, barcode, user_barcode):
    prods = get_prods()
    current = get_current_trans()
    if barcode == user_barcode:
        return (
            [html.H1("Products: ")],
            "",
        )
    elif int(barcode) not in list(prods["barcode"]):
        return no_update, ""
    elif len(barcode) == 2:
        for _ in range(int(barcode)):
            current(pd.concat([current, current[-1]]))
    else:
        try:
            product = prods[prods["barcode"] == int(barcode)]
        except:
            return no_update, "", no_update
        name = str(product["name"][0])
        new_transaction = pd.DataFrame([{"barcode_prod": barcode, "name": name}])
        current = pd.concat([current, new_transaction], ignore_index=True)
    display_text = [html.H1("Products: ")]
    for current_barcode in current["barcode_prod"].unique():
        prod_name = str(current[current["barcode_prod"] == current_barcode]["name"][0])
        current_amount = int(len(current[current["barcode_prod"] == current_barcode]))
        display_text.append(html.H2(f"{current_amount}x: {prod_name}"))

    update_current_trans(current)

    return display_text, ""


@callback(
    Output("new_trans_user", "children"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
    State("display_bill_switch", "value"),
)
def show_balance(trigger, user_id, display_bill_switch):
    if trigger is not None and display_bill_switch:
        trans = get_trans()
        users = get_prods()
        user_waste = get_waste() / len(users)
        try:
            user = str(users[users["barcode"] == int(user_id)]["name"][0])
        except:
            return no_update
        user_balance = sum(trans[trans["barcode_user"] == int(user_id)]["price"])
        return f"{user} - Current bill is: {user_balance} DKK and: {user_waste} DKK in waste."
    return no_update
