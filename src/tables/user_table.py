import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL
from src.data_connectors import upload_values, get_users


def init():
    pass


@callback(
    Output("new_user_modal", "is_open"),
    Output({"type": "user_input", "index": "inp_barcode_user"}, "value"),
    Input("new_user_btn", "n_clicks"),
    Input("confirm_user", "n_clicks"),
    Input("cancel_user", "n_clicks"),
    State("user_table", "data"),
    prevent_initial_call=True,
)
def open_user_modal(new_user, confirm, cancel, data):
    try:
        barcode = max(pd.DataFrame(data)["barcode"]) + 1
    except KeyError:
        barcode = 1001
    trigger = ctx.triggered_id
    if trigger == "new_user_btn":
        return True, barcode
    elif trigger == "confirm_user":
        return False, barcode
    else:
        return False, barcode


@callback(
    Output("confirm_user", "disabled"),
    Input({"type": "user_input", "index": ALL}, "value"),
    State({"type": "user_input", "index": ALL}, "id"),
)
def enable_confirm(inps, ids):
    if None not in inps:
        return False
    return True


@callback(
    Output("user_table", "data"),
    Input("confirm_user", "n_clicks"),
    State("user_table", "data"),
    State({"type": "user_input", "index": ALL}, "value"),
    State({"type": "user_input", "index": ALL}, "id"),
    prevent_initial_call=True,
)
def add_row(n_clicks, data, vals, ids):
    try:
        columns = data[0]
    except:
        columns = [inp["index"].split("_")[1] for inp in ids]
    if n_clicks > 0:
        data.append({c: vals[i] for i, c in enumerate(columns)})
    upload_values(data, "users")
    return data


@callback(
    Output({"type": "user_input", "index": f"inp_barcode_user"}, "invalid"),
    Input({"type": "user_input", "index": f"inp_barcode_user"}, "value"),
    State("user_table", "data"),
    prevent_initial_callback=True,
)
def validate_barcode_user(value, data):
    bars = [row["barcode"] for row in data]
    if value in bars or value is None or type(value) != int or len(str(value)) != 4:
        return True
    return False
