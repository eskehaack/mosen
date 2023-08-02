import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL

def get_users():
    return pd.read_csv("data/users.csv")

@callback(
    Output('new_user_modal', 'is_open'),
    Output({"type": "input", "index": "inp_barcode"}, "value"),
    Input('new_user_btn', 'n_clicks'),
    Input('confirm_user', 'n_clicks'),
    Input('cancel_user', 'n_clicks'),
    State("user_table", "data"),
    prevent_initial_call=True
)
def open_user_modal(new_user, confirm, cancel, data):
    barcode = max(pd.DataFrame(data)['barcode']) + 1
    trigger = ctx.triggered_id
    if trigger == "new_user_btn":
        return True, barcode
    elif trigger == "confirm_user":
        return False, barcode
    else:
        return False, barcode

@callback(
    Output("confirm_user", "disabled"),
    Input({"type": "input", "index": ALL}, "value"),
)
def enable_confirm(inps):
    if None not in inps:
        return False
    return True

@callback(
    Output('user_table', 'data'),
    Input('confirm_user', 'n_clicks'),
    State('user_table', 'data'),
    State({"type": "input", "index": ALL}, "value"),
    prevent_initial_call=True
)
def add_row(n_clicks, data, vals):
    columns = data[0]
    if n_clicks > 0:
        data.append({c: vals[i] for i, c in enumerate(columns)})
    pd.DataFrame(data).to_csv("data/users.csv",index=False)
    return data