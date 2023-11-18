import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL, MATCH, no_update
from src.tables.user_table import get_users

def get_prods(path):
    return pd.read_csv(path)

def get_waste(prods_path):
    prods = get_prods(prods_path)
    waste = sum([(p['initial stock'] - p['current stock']) * p['price'] for _, p in prods.iterrows()])
    return waste

@callback(
    Output('new_prod_modal', 'is_open'),
    Output({"type": "prod_input", "index": "inp_barcode_prod"}, "value"),
    Input('new_prod_btn', 'n_clicks'),
    Input('confirm_prod', 'n_clicks'),
    Input('cancel_prod', 'n_clicks'),
    State("prod_table", "data"),
    prevent_initial_call=True
)
def open_prod_modal(new_prod, confirm, cancel, data):
    try:
        barcode = max(pd.DataFrame(data)['barcode']) + 1
    except:
        barcode = 100001
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
)
def enable_confirm(inps):
    if None not in inps:
        return False
    return True

@callback(
    Output('prod_table', 'data'),
    Input('confirm_prod', 'n_clicks'),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "prod_input", "index": ALL}, "value"),
    State({"type": "prod_input", "index": ALL}, "id"),
    State("prods_file", "filename"),
    prevent_initial_call=True
)
def add_row(n_clicks, stock_trigger, vals, ids, prods_path):
    data = get_prods(prods_path).to_dict(orient="records")
    try:
        columns = data[0]
    except:
        columns = [inp['index'].split("_")[1] for inp in ids]
    if n_clicks is not None and n_clicks > 0:
        data.append({c: vals[i] for i, c in enumerate(columns)})
    pd.DataFrame(data).to_csv(prods_path,index=False)
    return data


@callback(
    Output({"type": "prod_input", "index": f"inp_barcode_prod"}, "invalid"),
    Input({"type": "prod_input", "index": f"inp_barcode_prod"}, "value"),
    State("prod_table", "data"),
    prevent_initial_callback = True
)
def validate_barcode_user(value, data):
    bars = [row['barcode'] for row in data]
    if value in bars or value is None or type(value) != int or len(str(value)) != 6:
        return True    
    return False

@callback(
    Output("new_stock_modal", "is_open"),
    Output("waste_value", "data"),
    Input("open_update_stock", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    State({"type": "new_stock_inp", "index": ALL}, "value"),
    State("prods_file", "filename")
)
def open_stock(trigger_open, trigger_close, inps, prods_file):
    trigger = ctx.triggered_id
    if trigger == "open_update_stock":
        return True, no_update
    if trigger == "confirm_new_stock":
        prods = pd.read_csv(prods_file)
        prods['current stock'] = list(inps)
        prods['waste'] = [((p['initial stock'] - p['current stock']) - p['sold']) * p['price'] for _, p in prods.iterrows()]
        prods.to_csv(prods_file, index=False)
        
        n_users = len(get_users())
        general_waste = sum(prods["waste"]) / n_users
        return False, general_waste
    return no_update, no_update