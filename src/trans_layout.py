from dash import dcc, html, callback, Input, Output, State, no_update, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime
from src.components import get_barcode, get_table
from src.data_connection import (
    get_prods,
    get_trans,
    get_users,
    get_current_trans,
    update_current_trans,
    upload_values,
    reset_current_trans,
    get_show_bill,
    get_waste,
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
                ),
                close_button=False,
            ),
            dbc.ModalBody(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                html.Div(
                                    [html.H1("Products: ")], id="show_current_prods"
                                ),
                                width=4,
                            ),
                            dbc.Col(
                                html.Div(
                                    [
                                        dbc.Row(
                                            dbc.Col(
                                                children=dcc.Graph(
                                                    id="trans_graph",
                                                    config={"displayModeBar": False},
                                                    # style={"maxHeight": "350px"},
                                                ),
                                                id="prod_barchart",
                                            ),
                                        ),
                                    ],
                                    className="show_box",
                                ),
                                width=7,
                            ),
                        ]
                    ),
                    dbc.Row(
                        dbc.Input(
                            placeholder="Barcode",
                            id="prod_barcode",
                            autoFocus=True,
                        ),
                        align="end",
                    ),
                ],
            ),
        ],
        is_open=False,
        id="new_trans_modal",
        fullscreen=True,
        keyboard=False,
    )
    return modal


@callback(
    Output("trans_graph", "figure"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
)
def get_transactions(trigger, barcode):
    transactions = get_trans()
    users = get_users()
    prods = get_prods()
    barcode = get_barcode(barcode)
    user_barcodes = list(map(str, users["barcode"]))
    if not (trigger is not None and str(barcode) in user_barcodes):
        return no_update, no_update
    user_trans = transactions[transactions["barcode_user"] == str(barcode)]
    trans_data = [
        {
            p: sum(
                [
                    (
                        1
                        if p
                        == prods[prods["barcode"] == str(row["barcode_prod"])][
                            "name"
                        ].values[0]
                        else 0
                    )
                    for i, row in user_trans.iterrows()
                ]
            )
            for p in list(prods["name"])
        }
    ]
    return px.bar(trans_data)


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
    barcode_open = get_barcode(barcode_open)
    barcode_close = get_barcode(barcode_close)
    user_barcodes = list(users["barcode"])
    trigger = ctx.triggered_id
    if trigger == "new_trans_inp":
        if len(user_barcodes) < 1:
            return no_update, "", no_update, True
        if str(int(barcode_open)) in user_barcodes:
            reset_current_trans()
            return True, no_update, "", False
        return no_update, "", no_update, False
    elif trigger == "prod_barcode" and int(barcode_close) == int(barcode_open):
        for _, row in current.iterrows():
            new_row = pd.DataFrame(
                [
                    {
                        "barcode_user": barcode_open,
                        "barcode_prod": row["barcode_prod"],
                        "price": str(
                            prods[prods["barcode"] == str(row["barcode_prod"])][
                                "price"
                            ].values[0]
                        ),
                        "timestamp": str(datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                    }
                ]
            )
            transactions = pd.concat([transactions, new_row], ignore_index=True)
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
    barcode = get_barcode(barcode)
    user_barcode = get_barcode(user_barcode)
    if barcode == user_barcode:
        return (
            [html.H1("Products: ")],
            "",
        )
    elif int(barcode) == 0:
        if len(current) == 0:
            return no_update, ""
        last_barcode = current.iloc[len(current) - 1]["barcode_prod"]
        indecies = current[current["barcode_prod"] == str(last_barcode)].index
        current.drop(indecies, inplace=True)
    elif len(barcode) < 3:
        if len(current) == 0:
            return no_update, ""
        last_barcode = current.iloc[len(current) - 1]["barcode_prod"]
        current_amount = len(current[current["barcode_prod"] == str(last_barcode)])
        addition = int(barcode) if current_amount > 1 else int(barcode) - 1
        for _ in range(addition):
            last = current.iloc[len(current) - 1]
            data = [
                {col: last.values[i] for i, col in enumerate(list(current.columns))}
            ]
            current = pd.concat([current, pd.DataFrame(data)], ignore_index=True)
    elif str(int(barcode)) not in list(prods["barcode"]):
        return no_update, ""
    else:
        try:
            product = prods[prods["barcode"] == str(barcode)]
        except:
            return no_update, "", no_update
        name = str(product["name"].values[0])
        new_transaction = pd.DataFrame([{"barcode_prod": barcode, "name": name}])
        current = pd.concat([current, new_transaction], ignore_index=True)
    display_text = [html.H1("Products: ")]
    for current_barcode in current["barcode_prod"].unique():
        prod_name = str(
            current[current["barcode_prod"] == current_barcode]["name"].values[0]
        )
        current_amount = int(len(current[current["barcode_prod"] == current_barcode]))
        display_text.append(html.H2(f"{current_amount}x: {prod_name}"))

    update_current_trans(current)

    return display_text, ""


@callback(
    Output("new_trans_user", "children"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
)
def show_balance(trigger, user_id):
    if trigger is not None:
        if not get_show_bill():
            users = get_users()
            try:
                user = str(users[users["barcode"] == str(user_id)]["name"].values[0])
            except:
                return no_update
            return str(user)
        else:
            trans = get_trans()
            users = get_users()
            prods = get_prods()
            price_dict = {str(p["barcode"]): p["price"] for _, p in prods.iterrows()}
            trans["price"] = trans["barcode_prod"].apply(
                lambda x: price_dict[str(x)] if str(x) in list(price_dict.keys()) else 0
            )

            user_waste = 0 if len(users) == 0 else get_waste() / len(users)
            user_id = get_barcode(user_id)
            try:
                user = str(users[users["barcode"] == str(user_id)]["name"].values[0])
            except:
                return no_update
            user_balance = sum(
                map(int, trans[trans["barcode_user"] == str(user_id)]["price"])
            )
            return f"{user} - Current bill is approximately: {max(0, round(user_balance + user_waste))}"
    return no_update
