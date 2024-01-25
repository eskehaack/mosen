from dash import Output, Input, State, callback, ctx, no_update, html, ALL, MATCH, dcc
import pandas as pd
import plotly.express as px
from src.connection import update_values
from src.data_connectors import get_prods, get_trans, get_users, upload_values
from src.tables.prod_table import get_waste
from src.tables.trans_table import get_income
from src.barcode_generator import generate_pdf

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
    Output({"index": ALL, "type": "bad_rows"}, "data"),
    Input("confirm_settings", "n_clicks"),
    State("settings_password", "value"),
    State("display_bill_switch", "value"),
    State({"index": ALL, "type": "database_upload"}, "contents"),
    State({"index": ALL, "type": "database_upload"}, "id"),
)
def update_settings(trigger, password, show_bill, db_tables, table_ids):
    if trigger is None:
        return None, no_update, no_update, [no_update] * 3
    open_warning_password = False
    if password is None or len(password) == 0:
        open_warning_password = True
        password = "OLProgram"
    update_values(password, show_bill)

    bad_rows_list = [[], [], []]
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
    return True, open_warning_password, open_warning_data, bad_rows_list


@callback(
    Output({"index": MATCH, "type": "show_upload_file"}, "children"),
    Input({"index": MATCH, "type": "database_upload"}, "filename"),
    Input("confirm_settings", "n_clicks"),
)
def show_new_upload(file, confirm):
    trigger = ctx.triggered_id
    if trigger == "confirm_settings":
        return ""
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
        income = pd.DataFrame(get_income())
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
        or all([table is None for table in data])
        or max([len(table) for table in data]) == 0
    ):
        return no_update, [no_update, no_update, no_update]
    else:
        return True, data
