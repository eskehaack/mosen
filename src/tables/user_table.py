import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL, no_update
from src.data_connection import upload_values, get_users, get_trans


def init():
    pass


@callback(
    Output("new_user_modal", "is_open", allow_duplicate=True),
    Output({"type": "user_input", "index": "inp_barcode_user"}, "value"),
    Input("new_user_btn", "n_clicks"),
    Input("confirm_user", "n_clicks"),
    Input("cancel_user", "n_clicks"),
    State("user_table", "data"),
    prevent_initial_call=True,
)
def open_user_modal(new_user, confirm, cancel, data):
    try:
        barcode = int(max(pd.DataFrame(data)["barcode"])) + 1
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
    Input({"type": "user_input", "index": f"inp_barcode_user"}, "invalid"),
)
def enable_confirm(inps, invalid_barcode):
    if None not in inps and not invalid_barcode:
        return False
    return True


@callback(
    Output("user_table", "data"),
    Output("edit_input", "value", allow_duplicate=True),
    Input("confirm_user", "n_clicks"),
    State({"type": "user_input", "index": ALL}, "value"),
    State({"type": "user_input", "index": ALL}, "id"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def add_row(n_clicks, vals, ids, edit_barcode):
    data = get_users()
    if n_clicks is None:
        return no_update, no_update
    if n_clicks > 0:
        if str(edit_barcode) in list(data["barcode"]):
            row = data[data["barcode"] == str(edit_barcode)]
            indecies = row.index
            data.drop(indecies, inplace=True)

        new = pd.DataFrame([{c: vals[i] for i, c in enumerate(data.columns)}])
        data = pd.concat([data, new])

    upload_values(data, "users")

    if edit_barcode is not None and int(edit_barcode) > 999:
        trans = get_trans()
        trans.loc[trans["barcode_user"] == str(edit_barcode), "barcode_user"] = int(
            vals[0]
        )
        upload_values(trans, "transactions")

    return data.to_dict(orient="records"), None


@callback(
    Output({"type": "user_input", "index": f"inp_barcode_user"}, "invalid"),
    Input({"type": "user_input", "index": f"inp_barcode_user"}, "value"),
    State("edit_input", "value"),
    prevent_initial_callback=True,
)
def validate_barcode_user(value, edit_barcode):
    bars = [row["barcode"] for row in get_users().to_dict(orient="records")]
    bars.extend([row["barcode_user"] for row in get_trans().to_dict(orient="records")])
    if (
        (str(value) in set(bars) and str(value) != str(edit_barcode))
        or value is None
        or type(value) != int
        or len(str(value)) != 4
    ):
        return True
    return False
