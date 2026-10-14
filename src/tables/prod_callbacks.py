import pandas as pd
from datetime import datetime
from dash import callback, Output, Input, State, html, ctx, ALL, MATCH, no_update
from src.barcode import BarcodePartition, is_barcode
from src.database.data_connection import (
    get_prods,
    get_trans,
    db_transaction_raises,
    update_values,
)
from src.analytics.waste_allocation import allocate_waste
from src.container import Container
from src.database.data_connection import Database
from src.error_handler import callback_with_error_queue, Result

PRODUCT_FORM_COLUMNS = ["barcode", "name", "price", "category", "initial_stock"]


@callback(
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output({"type": "prod_input", "index": "inp_barcode_prod"}, "value"),
    Input("new_prod_btn", "n_clicks"),
    Input("confirm_prod", "n_clicks"),
    Input("cancel_prod", "n_clicks"),
    prevent_initial_call=True,
)
def open_prod_modal(new_prod, confirm, cancel):
    try:
        table_data = Container.get(Database)._product_table.get()
        barcode = max(table_data["barcode"]) + 1
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


def add_row(n_clicks, stock_trigger, vals, edit_barcode):
    """add or edit a product. edit_barcode allows changing the barcode of a product, otherwise just upsert on barcode"""
    db = Container.get(Database)
    table = db._product_table
    
    if n_clicks is None:
        return no_update, no_update
    if n_clicks > 0:
        data = table.get()
        
        if db.barcode_exists(edit_barcode, BarcodePartition.PRODUCT):
            barcode_mask = data["barcode"] == int(edit_barcode)
            data = data[~barcode_mask].copy()

        form_row = {
            column: val for column, val in zip(PRODUCT_FORM_COLUMNS, vals)
        }
        existing_current_stock = None
        if db.barcode_exists(edit_barcode, BarcodePartition.PRODUCT):
            existing = table.get()
            existing = existing[existing["barcode"] == int(edit_barcode)]
            existing_current_stock = int(existing.iloc[0]["current_stock"])
            
        new_row = {
            **form_row,
            "current_stock": (
                existing_current_stock
                if existing_current_stock is not None
                else form_row["initial_stock"]
            ),
        }
        
        data = pd.concat([data, pd.DataFrame([new_row])])
        success, bad_rows = db.try_upload_values(data, "prods") 
        if not success:
             raise ValueError(f"Failed to upload product data. Bad rows: {bad_rows}")

    if is_barcode(edit_barcode, BarcodePartition.PRODUCT):
        trans = db.get_table("transactions").get()
        trans.loc[trans["barcode_prod"] == int(edit_barcode), "barcode_prod"] = int(
            vals[0]
        )
        success, bad_rows = db.try_upload_values(trans, "transactions")
        if not success:
             raise ValueError(f"Failed to upload product data. Bad rows: {bad_rows}")

    return table.get().to_dict(orient="records"), None


@callback_with_error_queue(
    2,
    Output("prod_table", "data"),
    Output("edit_input", "value", allow_duplicate=True),
    Input("confirm_prod", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "prod_input", "index": ALL}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
@db_transaction_raises
def add_row_callback(n_clicks, stock_trigger, vals, edit_barcode):
    return add_row(n_clicks, stock_trigger, vals, edit_barcode)


@callback(
    Output({"type": "prod_input", "index": f"inp_barcode_prod"}, "invalid"),
    Input({"type": "prod_input", "index": f"inp_barcode_prod"}, "value"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def validate_barcode_prod(value, edit_barcode):
    bars = [row["barcode"] for row in get_prods().to_dict(orient="records")]
    bars.extend([row["barcode_prod"] for row in get_trans().to_dict(orient="records")])
    if str(value) != str(edit_barcode) and (
        str(value) in set(bars)
        or value is None
        or type(value) != int
        or len(str(value)) != 3
    ):
        return True
    return False


@callback_with_error_queue(1,
    Output("new_stock_modal", "is_open"),
    Input("open_update_stock", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "new_stock_inp", "index": ALL}, "value"),
)
def open_stock(trigger_open, trigger_close, inps):
    trigger = ctx.triggered_id
    if trigger == "open_update_stock" and trigger_open:
        return True
    if trigger == "confirm_new_stock" and trigger_close:
        try:
            confirm_new_stock(inps)
            return False
        except Exception as e:
            #close on error, as clicking the button will do that anyway...
            #can be fixed by changing update_settings_layout to triggero on succesful db changes instead of button presses.
            return Result(False, error=e) 
    return no_update

@db_transaction_raises
def confirm_new_stock(inps):
    db = Container.get(Database)
    prods = db.get_table("prods").get()
    if None in inps or any(int(a) < 0 for a in inps): #While current stock can become negative, if someone scans too much, i don't think you would ever set it as negative.
        raise ValueError("You cannot set a negative stock value or leave it empty.")
    prods["current_stock"] = [int(val) for val in list(inps)]
    db.upload_values_raises(prods, "prods")
    allocate_waste(db)
    update_values(last_stock_update_at=datetime.now().isoformat(timespec="seconds"))
