import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL, MATCH, no_update
from src.data_connection import (
    get_users,
    get_prods,
    get_trans,
    upload_values,
    update_values,
)
from src.tables.trans_table import get_currently_sold


def calculate_waste():
    prods = get_prods()
    waste = sum(
        [
            (
                (int(p["initial_stock"]) - int(p["current_stock"]))
                - get_currently_sold(p)
            )
            * float(p["price"])
            for _, p in prods.iterrows()
        ]
    )
    return int(waste)


def get_waste_table():
    prods = get_prods()
    waste = [
        {
            "Barcode": int(p["barcode"]),
            "Product": p["name"],
            "Waste": (
                n_waste := int(p["initial_stock"])
                - int(p["current_stock"])
                - get_currently_sold(p)
            ),
            "Amount": n_waste * float(p["price"]),
        }
        for _, p in prods.iterrows()
    ]
    return waste


@callback(
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output({"type": "prod_input", "index": "inp_barcode_prod"}, "value"),
    Input("new_prod_btn", "n_clicks"),
    Input("confirm_prod", "n_clicks"),
    Input("cancel_prod", "n_clicks"),
    State("prod_table", "data"),
    prevent_initial_call=True,
)
def open_prod_modal(new_prod, confirm, cancel, data):
    try:
        barcode = max(pd.DataFrame(data)["barcode"]) + 1
    except:
        barcode = 101
    trigger = ctx.triggered_id
    if trigger == "new_prod_btn":
        return True, barcode
    elif trigger == "confirm_prod":
        return False, barcode
    else:
        return False, barcode


@callback(
    Output("confirm_prod", "disabled"),
    Input({"type": "prod_input", "index": ALL}, "value"),
    Input({"type": "prod_input", "index": f"inp_barcode_prod"}, "invalid"),
)
def enable_confirm(inps, invalid_barcode):
    if None not in inps and not invalid_barcode:
        return False
    return True


@callback(
    Output("prod_table", "data"),
    Output("edit_input", "value", allow_duplicate=True),
    Input("confirm_prod", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "prod_input", "index": ALL}, "value"),
    State({"type": "prod_input", "index": ALL}, "id"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def add_row(n_clicks, stock_trigger, vals, ids, edit_barcode):
    data = get_prods()
    if n_clicks is None:
        return no_update, no_update
    if n_clicks > 0:
        new = pd.DataFrame([{c: vals[i] for i, c in enumerate(data.columns)}])
        data = pd.concat([data, new])
    upload_values(data, "prods")

    if edit_barcode is not None and int(edit_barcode) < 999:
        trans = get_trans()
        trans.loc[trans["barcode_prod"] == str(edit_barcode), "barcode_prod"] = int(
            vals[0]
        )
        upload_values(trans, "transactions")

    return data.to_dict(orient="records"), None


@callback(
    Output({"type": "prod_input", "index": f"inp_barcode_prod"}, "invalid"),
    Input({"type": "prod_input", "index": f"inp_barcode_prod"}, "value"),
    prevent_initial_callback=True,
)
def validate_barcode_prod(value):
    bars = [row["barcode"] for row in get_prods().to_dict(orient="records")]
    bars.extend([row["barcode_prod"] for row in get_trans().to_dict(orient="records")])
    if (
        str(value) in set(bars)
        or value is None
        or type(value) != int
        or len(str(value)) != 3
    ):
        return True
    return False


@callback(
    Output("new_stock_modal", "is_open"),
    Input("open_update_stock", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "new_stock_inp", "index": ALL}, "value"),
)
def open_stock(trigger_open, trigger_close, inps):
    trigger = ctx.triggered_id
    if trigger == "open_update_stock":
        return True, no_update
    if trigger == "confirm_new_stock":
        prods = get_prods()
        prods["current_stock"] = list(inps)
        upload_values(prods, "prods")
        waste = calculate_waste()
        update_values(waste=waste)
        return False
    return no_update
