from dash import dcc, html, callback, Input, Output, State, dash_table, no_update, ctx
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.express as px
from datetime import datetime

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
                                        [html.H1("Products: ")],
                                        id="show_current_prods"
                                    )
                                ),
                                dbc.Col(
                                    children=dcc.Graph(id="trans_graph"),
                                    id="prod_barchart"
                                )
                            ]
                        ),
                        dbc.Row(
                            [
                                dash_table.DataTable(
                                    id="show_prods"
                                ),
                                dbc.Input(placeholder="Product barcode",id="prod_barcode")
                            ]
                        ),
                        dcc.Store(id="current_trans")
                    ]
                )
            )
        ], 
        is_open=False,
        id="new_trans_modal",
        fullscreen=True
    )
    return modal

@callback(
    Output("trans_graph", "figure"),
    Output("show_prods", "data"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value")
)
def get_transactions(trigger, barcode):
    transactions = pd.read_csv("data/transactions.csv")
    users = pd.read_csv("data/users.csv")
    prods = pd.read_csv("data/prods.csv")
    
    user_barcodes = list(users['barcode'])
    if not (trigger is not None and int(barcode) in user_barcodes):
        return no_update
    user_trans = transactions[transactions['barcode_user'] == int(barcode)]
    trans_data = [{p: sum([1 if p==row["product"] else 0 for i, row in user_trans.iterrows()]) for p in list(prods['name'])}]
    
    
    return px.bar(trans_data), trans_data
    
@callback(
    Output("new_trans_modal", "is_open"),
    Output("new_trans_inp", "value"),
    Output("prod_barcode", "value", allow_duplicate=True),
    Input("new_trans_inp", "n_submit"),
    Input("prod_barcode", "n_submit"),
    State("new_trans_inp", "value"),
    State("prod_barcode", "value"),
    State("current_trans", "data"),
    prevent_initial_call=True
)
def open_trans_modal(trigger_open, trigger_close, barcode_open, barcode_close, current_trans):
    users = pd.read_csv("data/users.csv")
    user_barcodes = list(users['barcode'])
    trigger = ctx.triggered_id
    if trigger == "new_trans_inp":
        if int(barcode_open) in user_barcodes:
            return True, no_update, ""
        return no_update, "", no_update
    elif trigger == "prod_barcode" and int(barcode_close) == int(barcode_open):
        if current_trans is not None:
            current_trans = "\n" + "\n".join([",".join(t) for t in current_trans])
            with open("data/transactions.csv", 'a') as fd:
                fd.write(current_trans)
        return False, "", no_update
    return no_update, no_update, no_update

@callback(
    Output("show_current_prods", "children"),
    Output("prod_barcode", "value"),
    Output("current_trans", "data"),
    Input("prod_barcode", "n_submit"),
    State("prod_barcode", "value"),
    State("current_trans", "data"),
    State("new_trans_inp", "value"),
    State("show_current_prods", "children"),
    prevent_initial_call=True
)
def new_trans(trigger, barcode, current, user_barcode, display_text):
    prods = pd.read_csv("data/prods.csv")
    transactions = pd.read_csv("data/transactions.csv")
    users = pd.read_csv("data/users.csv")
    if barcode == user_barcode:
        return [html.H1("Products: ")], "", no_update
    if int(barcode) not in list(prods['barcode']):
        return no_update, "", no_update
    try:
        product = prods[prods['barcode'] == int(barcode)]
        user = users[users['barcode'] == int(user_barcode)]
    except:
        return no_update,"",no_update
    prod_name = product['name'][0]

    transaction_str = [
        user_barcode,
        user['name'][0],
        barcode,
        prod_name,
        str(product['price'][0]),
        str(datetime.now().strftime("%d/%m/%Y %H:%M:%S"))
    ]
    if not current:
        current = list()
    current.append(transaction_str)
    previously_bought = False
    for i, p in enumerate(display_text):
        prod_str = p['props']['children']
        if prod_str != "Products: " and prod_str.split(" x: ")[1] == prod_name:
            nr = int(prod_str.split(" x: ")[0]) + 1
            idx = i
            previously_bought = True
            break
        
    if previously_bought:
        display_text[idx] = html.H2(f"{nr} x: {prod_name}")
    else:
        display_text.append(html.H2(f"1 x: {prod_name}"))

    prods['sold'] = [len(transactions[transactions['barcode_prod'] == p['barcode']]) for _, p in prods.iterrows()]
    prods.to_csv("data/prods.csv", index=False)
        
    return display_text, "", current

@callback(
    Output("new_trans_user", "children"),
    Input("new_trans_inp", "n_submit"),
    State("new_trans_inp", "value"),
    State("waste_value", "data")
)
def show_balance(trigger, user_id, user_waste):
    if trigger is not None:
        trans = pd.read_csv("data/transactions.csv")
        users = pd.read_csv("data/users.csv")
        
        user = str(users[users["barcode"] == int(user_id)]['name'][0])
        user_balance = sum(trans[trans['barcode_user'] == int(user_id)]['price'])
        return f"{user} - Current bill is: {user_balance + user_waste} DKK"
    return no_update
    