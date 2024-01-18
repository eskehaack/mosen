from dash import Output, Input, State, callback, ctx, no_update, html, ALL
import pandas as pd
import plotly.express as px
from src.connection import update_values
from src.data_connectors import get_prods, get_trans, get_users, upload_values

import base64
import io


def create_overview(plot_col):
    prods = get_prods()
    transactions = get_trans()
    users = get_users()

    if len(transactions) == 0:
        return px.bar()

    concatinated_dict = {row["name"]: row[plot_col] for i, row in users.iterrows()}
    ranks = list(users[plot_col].unique())

    overview_df = [0 for _ in range(len(ranks))]
    trans_dict = {prod: 0 for prod in prods["name"]}
    for i, rank in enumerate(ranks):
        temp = trans_dict.copy()
        temp["rank"] = rank
        overview_df[i] = temp

    for i, row in transactions.iterrows():
        overview_df[ranks.index(concatinated_dict[row["user"]])][row["product"]] += 1
    return px.bar(overview_df, x=ranks, y=list(prods["name"]))


@callback(Output("overview_graph", "figure"), Input("new_trans_modal", "is_open"))
def update_overview_graph(trans_modal_open):
    if not (ctx.triggered_id is not None and trans_modal_open == False):
        return no_update

    return create_overview("team")


@callback(
    Output("update_settings", "data"),
    Output("bad_password_alert", "is_open"),
    Output("bad_data_alert", "is_open"),
    Input("confirm_settings", "n_clicks"),
    State("settings_password", "value"),
    State("display_bill_switch", "value"),
    State({"index": ALL, "type": "database_upload"}, "contents"),
    State({"index": ALL, "type": "database_upload"}, "id"),
)
def update_settings(trigger, password, show_bill, db_tables, table_ids):
    if trigger is None:
        return None, no_update, no_update
    open_warning_password = False
    if password is None or len(password) == 0:
        open_warning_password = True
        password = "OLProgram"
    update_values(password, show_bill)

    for i, table in enumerate(db_tables):
        if table is None:
            continue
        _, content_string = table.split(",")
        content = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        if len(df) > 0:
            response = upload_values(df, table_ids[i]["index"])
            open_warning_data = False if response == "success" else True

    return None, open_warning_password, open_warning_data


@callback(
    Output("user_upload_text", "children"),
    Input({"index": "users", "type": "database_upload"}, "filename"),
    Input("confirm_settings", "n_clicks"),
)
def show_new_users(user_file, confirm):
    trigger = ctx.triggered_id
    if trigger == "confirm_settings":
        return ""
    if user_file is not None and len(user_file) > 0:
        return str(user_file)
    else:
        return no_update


@callback(
    Output("transactions_upload_text", "children"),
    Input({"index": "transactions", "type": "database_upload"}, "filename"),
    Input("confirm_settings", "n_clicks"),
)
def show_new_users(trans_file, confirm):
    trigger = ctx.triggered_id
    if trigger == "confirm_settings":
        return ""
    if trans_file is not None and len(trans_file) > 0:
        return str(trans_file)
    else:
        return no_update


@callback(
    Output("prods_upload_text", "children"),
    Input({"index": "prods", "type": "database_upload"}, "filename"),
    Input("confirm_settings", "n_clicks"),
)
def show_new_users(prods_file, confirm):
    trigger = ctx.triggered_id
    if trigger == "confirm_settings":
        return ""
    if prods_file is not None and len(prods_file) > 0:
        return str(prods_file)
    else:
        return no_update
