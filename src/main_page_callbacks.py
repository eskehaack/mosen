from dash import Output, Input, State, callback, ctx, no_update, html, ALL, MATCH, dcc
import pandas as pd
import plotly.express as px
from src.data_connection import (
    get_prods,
    get_trans,
    get_user_products,
    get_users,
    upload_values,
    update_values,
    reset_all_tables,
    get_waste,
)
from src.tables.trans_table import get_income
from src.barcode_generator import generate_pdf

import base64
import io
import shutil
import os
from datetime import datetime


def create_overview(plot_col, average=False):
    prods = get_prods()
    transactions = get_trans()
    users = get_users()

    if len(transactions) == 0:
        return px.bar()

    def translation(x, t_dict):
        try:
            ret = t_dict[str(x)]
        except:
            ret = "UNKNOWN"
        return ret

    if plot_col == "products":
        text = lambda x: f"{x} category"
        ranks = [text(cat) for cat in list(prods["category"].unique())]
        rank_dict = {
            str(row["barcode"]): text(row["category"]) for i, row in prods.iterrows()
        }
        transactions["rank"] = transactions["barcode_prod"].apply(
            translation, t_dict=rank_dict
        )

    else:
        text = lambda x: f"{x} {plot_col.lower()}"
        ranks = [text(rank) for rank in list(users[str(plot_col)].unique())]
        rank_dict = {
            str(row["barcode"]): text(row[str(plot_col)]) for i, row in users.iterrows()
        }

        transactions["rank"] = transactions["barcode_user"].apply(
            translation, t_dict=rank_dict
        )

    prod_dict = {str(row["barcode"]): row["name"] for i, row in prods.iterrows()}
    transactions["prod_names"] = transactions["barcode_prod"].apply(
        translation, t_dict=prod_dict
    )
    overview_df = [
        transactions[transactions["rank"] == rank].value_counts("prod_names").to_dict()
        for rank in ranks
    ]

    if average:
        if plot_col == "products":
            overview_df = [
                {
                    rank: (
                        0
                        if (
                            number := int(
                                prods[prods["category"] == ranks[i][:-9]][
                                    "initial_stock"
                                ].values[0]
                            )
                        )
                        == 0
                        else int(count) / number
                    )
                    for rank, count in overview.items()
                }
                for i, overview in enumerate(overview_df)
            ]
        else:
            overview_df = [
                {
                    rank: (
                        0
                        if (
                            number := len(
                                users[
                                    users[str(plot_col)]
                                    == ranks[i][: -(len(plot_col) + 1)]
                                ]
                            )
                        )
                        == 0
                        else int(count) / number
                    )
                    for rank, count in overview.items()
                }
                for i, overview in enumerate(overview_df)
            ]
    y = [
        prods[prods["barcode"] == str(p)]["name"].values[0]
        for p in transactions["barcode_prod"]
    ]
    return px.bar(overview_df, x=ranks, y=y)

def create_top_user_overview(selected_products):
    all_user_products = get_user_products()
    filtered_user_products = all_user_products[all_user_products['product'].isin(selected_products)]
    #ensure every user product combination is listed
    filtered_user_products = (
        filtered_user_products
        .pivot_table(index="user", columns="product", values="amount", fill_value=0)
        .reset_index()
        .melt(id_vars="user", var_name="product", value_name="amount")
    )
    print(1)
    return px.bar(filtered_user_products,x="user",y="amount",color="product")

@callback(
    Output("overview_graph", "figure"),
    Input("new_trans_modal", "is_open"),
    Input("graph_selection", "value"),
    Input("graph_average", "value"),
)
def update_overview_graph(trans_modal_open, graph_col, average):
    if not (ctx.triggered_id is not None and trans_modal_open == False):
        return no_update

    return create_overview(graph_col, average)


@callback(
    Output("update_settings", "data"),
    Output("bad_password_alert", "is_open"),
    Output("bad_data_alert", "is_open"),
    Output({"index": ALL, "type": "bad_rows"}, "data"),
    Output("new_password_alert", "is_open"),
    Input("confirm_new_password", "n_clicks"),
    Input("display_bill_switch", "value"),
    Input({"index": ALL, "type": "database_upload"}, "contents"),
    Input({"index": ALL, "type": "database_upload"}, "id"),
    State("settings_password", "value"),
)
def update_settings(pass_trigger, show_bill, db_tables, table_ids, password):
    if (trigger := ctx.triggered_id) is None:
        return None, no_update, no_update, [no_update] * 3, no_update
    open_warning_password = False
    if password is None or len(password) == 0:
        open_warning_password = True
        password = "OLProgram"
    update_values(password, show_bill)
    if trigger == "confirm_new_password":
        return None, no_update, no_update, [no_update] * 3, True

    bad_rows_list = [[], [], []]
    open_warning_data = False
    for i, table in enumerate(db_tables):
        if table is None:
            continue
        _, content_string = table.split(",")
        content = base64.b64decode(content_string)
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
        if len(df) > 0:
            response, bad_rows = upload_values(df, table_ids[i]["index"])
            open_warning_data = False if response == "success" else True
            bad_rows_list[i] = bad_rows
    return True, open_warning_password, open_warning_data, bad_rows_list, False


@callback(
    Output({"index": MATCH, "type": "show_upload_file"}, "children"),
    Input({"index": MATCH, "type": "database_upload"}, "filename"),
)
def show_new_upload(file):
    if file is not None and len(file) > 0:
        return str(file)
    else:
        return no_update


@callback(
    Output({"index": MATCH, "type": "download_trigger"}, "data"),
    Input({"index": MATCH, "type": "download_trigger_btn"}, "n_clicks"),
)
def download_tables(trigger):
    trigger = ctx.triggered_id
    if trigger is None:
        return no_update
    data_translation = {
        "users": get_users,
        "prods": get_prods,
        "transactions": get_trans,
    }
    trigger = trigger["index"]
    data = data_translation[trigger]().to_csv
    return dcc.send_data_frame(data, filename=f"{trigger}_data.csv", index=False)


@callback(
    Output("payments_modal", "is_open"),
    Output("payments_download", "data"),
    Input("export_payments_btn", "n_clicks"),
    Input("confirm_payments", "n_clicks"),
    State("added_amount_inp", "value"),
    State("up_down_dd", "value"),
    State("round_dd", "value"),
)
def control_payments_modal(open_trigger, close_trigger, added_value, up_down, round):
    trigger = ctx.triggered_id
    if trigger == "export_payments_btn":
        return True, no_update
    elif trigger == "confirm_payments":
        waste = get_waste()
        user_prices = pd.DataFrame(get_income())
        zero_users = user_prices[user_prices["price"] <= 0].copy()
        income = user_prices[user_prices["price"] > 0].copy()
        income["price"] += float(waste) / len(income)
        income["price"] += float(added_value) / len(income)
        if int(round) != 0:
            if up_down == "Nearest":
                rounding = lambda x: int(round * round(float(x) / round))
            elif up_down == "Up":
                rounding = lambda x: float(x) + round - (float(x) % round)
            else:
                rounding = lambda x: float(x) - (float(x) % round)
            income["price"] = income["price"].apply(rounding)

        income = pd.concat([income, zero_users])
        return False, dcc.send_data_frame(
            income.to_csv, filename="swamp_machine_payments.csv", index=False
        )
    else:
        return no_update, no_update


@callback(
    Output("export_barcodes_modal", "is_open"),
    Input("export_barcodes_btn", "n_clicks"),
    Input("confirm_export_barcodes", "n_clicks"),
)
def open_export_barcodes(trigger_open, trigger_close):
    trigger = ctx.triggered_id
    if trigger == "export_barcodes_btn":
        return True
    elif trigger == "confirm_export_barcodes":
        return False
    else:
        return no_update


@callback(
    Output("pdf_download", "data"),
    Input("confirm_export_barcodes", "n_clicks"),
    State("guest_barcodes_inp", "value"),
)
def export_barcodes(trigger, guest_barcodes):
    if trigger is None:
        return no_update

    types = ["users", "prods", "guests", "multipliers"]
    for type in types:
        generate_pdf(
            type=type,
            pdf_filename=f"{type[:-1]}_barcodes.pdf",
            number_of_guest_codes=guest_barcodes,
        )

    return no_update


@callback(
    Output("bad_rows_modal", "is_open"),
    Output({"index": ALL, "type": "bad_rows_table"}, "data"),
    Input("update_settings", "data"),
    State({"index": ALL, "type": "bad_rows"}, "data"),
)
def open_bad_rows(trigger, data):
    if (
        trigger is None
        or max([0 if table is None else len(table) for table in data]) == 0
    ):
        return no_update, [no_update, no_update, no_update]
    else:
        print(data)
        return True, data


@callback(
    Output("edit_data_modal", "is_open"),
    Output("edit_modal_row", "data"),
    Output("edit_text", "children"),
    Input("edit_users", "n_clicks"),
    Input("edit_prods", "n_clicks"),
    Input("edit_modal_delete", "n_clicks"),
    Input("edit_modal_edit", "n_clicks"),
    prevent_initial_call=True,
)
def open_edit_modal(open_user, open_prod, close_delete, close_edit):
    trigger = ctx.triggered_id
    if trigger in ["edit_users", "edit_prods"] and any(
        [trig is not None for trig in [open_user, open_prod]]
    ):
        text = "user" if "user" in trigger else "product"
        return True, trigger.split("_")[1], f"Input barcode for {text}"
    if trigger in ["edit_modal_delete", "edit_modal_edit"] and any(
        [trig is not None for trig in [close_delete, close_edit]]
    ):
        return False, None, no_update
    return no_update, no_update, no_update


@callback(
    Output("new_user_modal", "is_open", allow_duplicate=True),
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output({"index": ALL, "type": "user_input"}, "value", allow_duplicate=True),
    Output({"index": ALL, "type": "prod_input"}, "value", allow_duplicate=True),
    Input("edit_modal_delete", "n_clicks"),
    Input("edit_modal_edit", "n_clicks"),
    State("edit_modal_row", "data"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
def edit_new_data_modals(delete, edit, table, barcode):
    trigger = ctx.triggered_id
    if trigger == "edit_modal_delete" and barcode is not None:
        if table == "users":
            data = get_users()
        elif table == "prods":
            data = get_prods()
        indecies = data[data["barcode"] == str(barcode)].index
        data.drop(indecies, inplace=True)
        upload_values(data, table)
        return no_update, no_update, [no_update] * 4, [no_update] * 6
    elif trigger == "edit_modal_edit" and barcode is not None:
        if table == "users":
            data = get_users()
            row = data[data["barcode"] == str(barcode)]
            if len(row) == 0:
                return no_update, no_update, [no_update] * 4, [no_update] * 6
            row = list(row.values[0])
            return True, False, row, [no_update] * 6
        if table == "prods":
            data = get_prods()
            row = data[data["barcode"] == str(barcode)]
            if len(row) == 0:
                return no_update, no_update, [no_update] * 4, [no_update] * 6
            row = list(row.values[0])
            return False, True, [no_update] * 4, row
    else:
        return no_update, no_update, [no_update] * 4, [no_update] * 6


@callback(
    Output("reset_data_modal", "is_open"),
    Input("reset_app", "n_clicks"),
    Input("delete_data_btn", "n_clicks"),
    Input("cancel_delete_data_btn", "n_clicks"),
)
def reset_database(trigger, delete, cancel):
    trigger = ctx.triggered_id
    if trigger == "reset_app":
        return True
    elif trigger == "delete_data_btn":
        reset_all_tables()
        return False
    elif trigger == "cancel_delete_data_btn":
        return False
    else:
        return no_update


@callback(
    Output("backup_filename", "data"),
    Input("backup_interval", "n_intervals"),
    State("backup_interval", "interval"),
)
def backup_database(trigger, interval):
    if trigger is not None and interval != 0:
        if not os.path.isdir("swamp_backups"):
            os.mkdir("swamp_backups")
        filename = f"swamp_backups/beerbase_backup_{str(datetime.now().strftime('%d_%m_%Y_%H_%M_%S'))}.db"
        shutil.copy("beerbase.db", filename)
        return filename
    return no_update


@callback(Output("backup_interval", "interval"), Input("settings_backup_time", "value"))
def set_backup_timer(interval):
    if interval is not None:
        update_values(backup_time=interval)
        return interval * 60000  # Convert to minutes
    return no_update


@callback(Output("study_users_modal", "is_open"), Input("study_users_btn", "n_clicks"))
def open_study_users(trigger):
    if trigger is not None:
        return True
    return no_update


@callback(Output("study_user_table", "figure"), Input("study_users_dd", "value"))
def study_users(users):
    if users is None or len(users) < 1:
        return no_update

    prods = get_prods()
    trans = get_trans().merge(
        prods, "right", left_on="barcode_prod", right_on="barcode"
    )

    if not isinstance(users, list):
        users = [users]

    study_table = list()
    for user in users:
        prod_dict = {prod: 0 for prod in list(prods["name"])}
        prod_dict["user"] = user
        user_trans = trans[trans["barcode_user"] == str(user)]
        counts = user_trans["name"].value_counts().to_dict()
        prod_dict.update(counts)
        study_table.append(prod_dict)

    return px.bar(study_table, text="user")
