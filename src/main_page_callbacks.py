from dash import (
    Output,
    Input,
    State,
    callback,
    clientside_callback,
    ctx,
    no_update,
    html,
    ALL,
    MATCH,
    dcc,
)
import pandas as pd
import plotly.express as px
from src.database.data_connection import (
    TransactionResult,
    db_transaction_raises,
    db_transaction_result,
    get_prods,
    get_trans,
    get_users,
    upload_values,
    update_values,
    reset_all_tables,
    get_waste,
    get_last_stock_update_at,
)
from src.analytics.trans_calculations import get_income
from src.analytics.timestamps import parse_timestamp, parse_transaction_timestamps
from src.analytics.waste_allocation import allocate_waste
from src.barcode_generator import (
    BARCODE_EXPORT_REPORT_FILENAME,
    build_barcode_export_report,
    generate_pdf,
)
from src.error_handler import append_error, callback_with_error_queue
from src.container import Container
from src.database.data_connection import Database
from src.database.tables.user import UserTable
from src.analytics.overview_plot import create_overview
from src.analytics.bar_chart_format import format_count_bar_chart
from src.components import get_tooltip_data
from src.diagnostics import (
    build_diagnostics_archive,
    get_diagnostics_status,
)

import base64
import binascii
import io
import shutil
import os
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime


BACKUP_DIR = "swamp_backups"
TRANSACTION_COLUMNS = ("barcode_user", "barcode_prod", "timestamp")


def filter_income_rows(rows, query):
    source_rows = [dict(row) for row in (rows or [])]
    search = str(query or "").strip().casefold()
    if not search:
        return source_rows

    exact_barcode_matches = [
        row
        for row in source_rows
        if str(row.get("barcode", "")).strip().casefold() == search
    ]
    if exact_barcode_matches:
        return exact_barcode_matches

    return [
        row
        for row in source_rows
        if search in str(row.get("name", "")).casefold()
        or str(row.get("barcode", "")).strip().casefold().startswith(search)
    ]


@callback(
    Output("income_table", "data"),
    Output("income_table", "tooltip_data"),
    Output("income_search_status", "children"),
    Input("income_search", "value"),
    Input("income_table_all_rows", "data"),
)
def update_income_lookup(query, rows):
    filtered_rows = filter_income_rows(rows, query)
    has_query = bool(str(query or "").strip())
    status = "No matching user." if has_query and not filtered_rows else ""
    return filtered_rows, get_tooltip_data(filtered_rows), status


clientside_callback(
    """
    function(activeTab, submissions, rowsUpdated) {
        if (activeTab !== "economy") {
            return window.dash_clientside.no_update;
        }

        window.setTimeout(function() {
            const input = document.getElementById("income_search");
            if (input) {
                input.focus();
                input.select();
            }
        }, 0);
        return Date.now();
    }
    """,
    Output("income_lookup_focus", "data"),
    Input("setting_tabs", "value"),
    Input("income_search", "n_submit"),
    Input("income_table_all_rows", "modified_timestamp"),
    prevent_initial_call=True,
)


def create_database_backup(data_file="beerbase.db", label="backup", backup_dir=None):
    backup_dir = backup_dir or BACKUP_DIR
    os.makedirs(backup_dir, exist_ok=True)

    db_name = os.path.splitext(os.path.basename(data_file))[0]
    timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S_%f")
    filename = os.path.join(backup_dir, f"{db_name}_{label}_{timestamp}.db")
    shutil.copy(data_file, filename)
    return filename


def get_selected_transaction(virtual_data, selected_rows):
    if not selected_rows:
        raise ValueError("Select a transaction to remove.")
    if not virtual_data:
        raise ValueError("The selected transaction is no longer available.")

    selected_index = selected_rows[0]
    if selected_index < 0 or selected_index >= len(virtual_data):
        raise ValueError("The selected transaction is no longer available.")

    selected = virtual_data[selected_index]
    if any(selected.get(column) is None for column in TRANSACTION_COLUMNS):
        raise ValueError("The selected transaction is missing required data.")
    return {column: str(selected[column]) for column in TRANSACTION_COLUMNS}


def get_transaction_removal_summary(transaction):
    user_barcode = str(transaction["barcode_user"])
    product_barcode = str(transaction["barcode_prod"])

    users = get_users()
    user_matches = users[users["barcode"].astype(str) == user_barcode]
    user_name = (
        str(user_matches.iloc[0]["name"]) if len(user_matches) else "Unknown user"
    )

    products = get_prods()
    product_matches = products[products["barcode"].astype(str) == product_barcode]
    product_name = (
        str(product_matches.iloc[0]["name"])
        if len(product_matches)
        else "Unknown product"
    )

    return html.Div(
        [
            html.P("Are you sure you want to remove this transaction?"),
            html.P(f"User: {user_name} ({user_barcode})"),
            html.P(f"Product: {product_name} ({product_barcode})"),
            html.P(f"Timestamp: {transaction['timestamp']}"),
        ]
    )


@db_transaction_raises
def remove_transaction(transaction):
    if not isinstance(transaction, dict) or any(
        transaction.get(column) is None for column in TRANSACTION_COLUMNS
    ):
        raise ValueError("No valid transaction is pending removal.")

    db = Container.get(Database)
    transactions = db._transaction_table.get()
    matches = pd.Series(True, index=transactions.index, dtype=bool)
    for column in TRANSACTION_COLUMNS:
        matches &= transactions[column].astype(str).eq(str(transaction[column]))

    matching_indices = transactions.index[matches].tolist()
    if not matching_indices:
        raise ValueError(
            "The selected transaction no longer exists. Nothing was changed."
        )

    backup_path = create_database_backup(
        db.data_file,
        label="pre_transaction_delete",
    )
    remaining = transactions.drop(index=matching_indices[0]).reset_index(drop=True)
    db.upload_values_raises(remaining, "transactions")
    update_values(last_stock_update_at="")
    return backup_path


@callback(
    Output("remove_transaction_btn", "disabled"),
    Input("trans_table", "derived_virtual_selected_rows"),
)
def disable_remove_transaction_button(selected_rows):
    return not bool(selected_rows)


@callback_with_error_queue(
    4,
    Output("remove_transaction_modal", "is_open"),
    Output("remove_transaction_summary", "children"),
    Output("pending_transaction_removal", "data"),
    Output("transaction_removal_revision", "data"),
    Input("remove_transaction_btn", "n_clicks"),
    Input("cancel_remove_transaction", "n_clicks"),
    Input("confirm_remove_transaction", "n_clicks"),
    State("trans_table", "derived_virtual_data"),
    State("trans_table", "derived_virtual_selected_rows"),
    State("pending_transaction_removal", "data"),
    State("transaction_removal_revision", "data"),
)
def control_transaction_removal(
    remove_clicks,
    cancel_clicks,
    confirm_clicks,
    virtual_data,
    selected_rows,
    pending_transaction,
    revision,
):
    trigger = ctx.triggered_id
    if trigger == "remove_transaction_btn" and remove_clicks:
        selected = get_selected_transaction(virtual_data, selected_rows)
        return (
            True,
            get_transaction_removal_summary(selected),
            selected,
            no_update,
        )
    if trigger == "cancel_remove_transaction" and cancel_clicks:
        return False, no_update, None, no_update
    if trigger == "confirm_remove_transaction" and confirm_clicks:
        remove_transaction(pending_transaction)
        return False, no_update, None, (revision or 0) + 1
    return no_update, no_update, no_update, no_update


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


def parse_csv_upload(contents: str, filename: str | None) -> pd.DataFrame:
    if not filename or not filename.lower().endswith(".csv"):
        raise ValueError(
            "Upload a CSV file (.csv). Database backups (.db) cannot be imported here."
        )
    try:
        _, encoded = contents.split(",", 1)
        content = base64.b64decode(encoded, validate=True)
        if b"\x00" in content:
            raise ValueError("Binary file contents")
        return pd.read_csv(io.StringIO(content.decode("utf-8-sig")))
    except (ValueError, binascii.Error) as error:
        raise ValueError(
            f"Cannot read {filename} as CSV. Upload a valid UTF-8 CSV file."
        ) from error


def validate_user_import(imported_users: pd.DataFrame) -> None:
    """Allow additions and edits while protecting existing trip data.

    Users with purchases or early payments must remain in the import.
    Existing non-default optional values must match for the same barcode.
    """
    if "barcode" not in imported_users.columns:
        return  # Required-column validation is handled by the table.

    db = Container.get(Database)
    user_table = db._user_table
    existing_users = user_table.get()
    imported_barcodes = pd.to_numeric(imported_users["barcode"], errors="coerce")

    users_to_remove = existing_users[
        ~existing_users["barcode"].isin(imported_barcodes)
    ]
    _validate_user_removals(users_to_remove, db._transaction_table.get())
    _validate_optional_user_values(
        imported_users, imported_barcodes, existing_users, user_table
    )


def _validate_user_removals(
    users_to_remove: pd.DataFrame, transactions: pd.DataFrame
) -> None:
    """Prevent imports from deleting users with purchases or early payments."""
    has_purchases = users_to_remove["barcode"].isin(transactions["barcode_user"]).any()
    if has_purchases:
        raise ValueError(
            "Cannot import users because the file removes users with transactions. "
            "Keep those users in the CSV file or remove their transactions first."
        )

    has_early_payments = users_to_remove["paid_cents"].ne(0).any()
    if has_early_payments:
        raise ValueError(
            "Cannot import users because the file removes users with recorded early payments. "
            "Keep those users in the CSV file or remove their early payments first."
        )


def _validate_optional_user_values(
    imported_users: pd.DataFrame,
    imported_barcodes: pd.Series,
    existing_users: pd.DataFrame,
    user_table: UserTable,
) -> None:
    """Allow default values to change; preserve every existing non-default value."""
    # Missing columns and blank cells get the same defaults as an actual import.
    imported_with_defaults = pd.DataFrame([
        user_table._fill_optional_defaults(row)
        for row in imported_users.to_dict(orient="records")
    ])
    existing_by_barcode = existing_users.set_index("barcode")
    unsafe_columns = []
    unsafe_barcodes = set()
    for column in user_table.columns:
        if column.required:
            continue

        # Match import rows to saved values by barcode. New users have no saved value.
        stored_values = imported_barcodes.map(existing_by_barcode[column.name])
        imported_values = pd.to_numeric(
            imported_with_defaults[column.name], errors="coerce"
        )
        is_existing_user = stored_values.notna()
        has_non_default_value = stored_values.ne(column.default)
        value_would_change = stored_values.ne(imported_values)
        would_overwrite = is_existing_user & has_non_default_value & value_would_change

        if would_overwrite.any():
            unsafe_columns.append(column.name)
            unsafe_barcodes.update(imported_barcodes[would_overwrite].astype(int))
    if unsafe_columns:
        barcodes = ", ".join(str(barcode) for barcode in sorted(unsafe_barcodes)[:5])
        if len(unsafe_barcodes) > 5:
            barcodes += ", ..."
        raise ValueError(
            "Cannot import users because it would overwrite non-default values "
            f"in columns: {', '.join(unsafe_columns)} for barcodes: {barcodes}. "
            "Export the current users and edit the CSV file before importing."
        )


@callback_with_error_queue(5,
    Output("update_settings", "data"),
    Output("bad_password_alert", "is_open"),
    Output("bad_data_alert", "is_open"),
    Output({"index": ALL, "type": "bad_rows"}, "data"),
    Output("new_password_alert", "is_open"),
    Input("confirm_new_password", "n_clicks"),
    Input("display_bill_switch", "value"),
    Input({"index": ALL, "type": "database_upload"}, "contents"),
    Input({"index": ALL, "type": "database_upload"}, "id"),
    Input("waste_strategy", "value"),
    Input("bill_preview_waste_extra_percent", "value"),
    State("settings_password", "value"),
    State({"index": ALL, "type": "database_upload"}, "filename"),
)
@db_transaction_result
def update_settings(
    pass_trigger,
    show_bill,
    db_tables,
    table_ids,
    waste_strategy,
    bill_preview_waste_extra_percent,
    password,
    filenames,
):
    if (trigger := ctx.triggered_id) is None:
        return None, no_update, no_update, [no_update] * 3, no_update
    open_warning_password = False
    if password is None or len(password) == 0:
        open_warning_password = True
        password = "OLProgram"

    db = Container.get(Database)
    imports = []
    import_triggered = isinstance(trigger, dict) and trigger.get("type") == "database_upload"
    if import_triggered:
        for i, table in enumerate(db_tables):
            if table is None or table_ids[i]["index"] != trigger.get("index"):
                continue
            table_name = table_ids[i]["index"]
            try:
                df = parse_csv_upload(table, filenames[i])
                missing_columns = [
                    column.name for column in db.get_table(table_name).columns
                    if column.required and column.name not in df.columns
                ]
                if missing_columns:
                    raise ValueError(
                        f"CSV for {table_name} is missing required columns: "
                        f"{', '.join(missing_columns)}."
                    )
                if len(df) > 0 and table_name == "users":
                    validate_user_import(df)
            except ValueError as error:
                return TransactionResult(
                    (no_update, no_update, True, [no_update] * 3, no_update),
                    error=error,
                    commit=False,
                )
            if len(df) > 0:
                imports.append((i, df, table_name))

    if imports:
        create_database_backup(db.data_file, label="pre_import")

    update_values(
        password,
        show_bill,
        waste_strategy=waste_strategy,
        bill_preview_waste_extra_percent=bill_preview_waste_extra_percent,
    )
    if trigger == "confirm_new_password":
        return None, no_update, no_update, [no_update] * 3, True

    bad_rows_list = [[], [], []]
    open_warning_data = False
    for i, df, table_name in imports:
        success, bad_rows = db.try_upload_values(df, table_name)
        bad_rows_list[i] = bad_rows
        if not success:
            open_warning_data = True
    return TransactionResult((True, open_warning_password, open_warning_data, bad_rows_list, False), commit=not open_warning_data)


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


@callback_with_error_queue(2,
    Output("payments_modal", "is_open"),
    Output("payments_download", "data"),
    Input("export_payments_btn", "n_clicks"),
    Input("confirm_payments", "n_clicks"),
    State("added_amount_inp", "value"),
)
@db_transaction_result
def control_payments_modal(open_trigger, close_trigger, added_value):
    trigger = ctx.triggered_id
    if trigger == "export_payments_btn" and open_trigger:
        return True, no_update
    elif trigger == "confirm_payments" and close_trigger:
        db = Container.get(Database)
        warning = _validate_payment_export_stock_freshness()
        if warning.block_export:
            return TransactionResult(
                (no_update, no_update),
                error=ValueError(warning.message),
                commit=False,
            )
        allocate_waste(db)
        income = pd.DataFrame(get_income())
        active = (income["#products"] > 0) & (income["price"] > 0)
        if active.any():
            income.loc[active, "price"] += float(added_value) / int(active.sum())
        result = (
            False,
            dcc.send_data_frame(
                income.to_excel,
                filename="swamp_machine_payments.xlsx",
                index=False,
            ),
        )
        if warning.message:
            return TransactionResult(result, error=ValueError(warning.message))
        return result
    else:
        return no_update, no_update


@dataclass
class PaymentExportWarning:
    message: str = ""
    block_export: bool = False


def _validate_payment_export_stock_freshness():
    last_stock_update = parse_timestamp(get_last_stock_update_at())
    if last_stock_update is None:
        return PaymentExportWarning(
            "Update stock before exporting payments.",
            block_export=True,
        )

    transactions = get_trans()
    if len(transactions) == 0:
        return PaymentExportWarning()

    parsed, failures = parse_transaction_timestamps(transactions["timestamp"])
    if parsed and max(parsed) > last_stock_update:
        return PaymentExportWarning(
            "Update stock after the latest purchase before exporting payments.",
            block_export=True,
        )
    if failures:
        return PaymentExportWarning(
            "Payment export created, but some transaction timestamps could not be checked against the last stock update.",
            block_export=False,
        )
    return PaymentExportWarning()


@callback_with_error_queue(1,
    Output("pdf_download", "data"),
    Input("export_barcodes_btn", "n_clicks"),
    prevent_initial_call=True,
)
def export_barcodes(trigger):
    if trigger is None:
        return no_update

    generated_at = datetime.now()
    barcode_types = ["prods", "users", "multipliers"]
    zip_buffer = io.BytesIO()
    zip_filename = f"barcodes_{generated_at.strftime('%d_%m_%Y_%H_%M_%S')}.zip"

    with tempfile.TemporaryDirectory(prefix="barcode_export_") as temp_dir:
        pdf_files = []
        user_labels = []
        for barcode_type in barcode_types:
            pdf_filename = f"{barcode_type[:-1]}_barcodes.pdf"
            pdf_path = os.path.join(temp_dir, pdf_filename)
            generated_labels = generate_pdf(
                barcode_type=barcode_type,
                pdf_filename=pdf_path,
            )
            if barcode_type == "users":
                user_labels = generated_labels
            pdf_files.append((pdf_filename, pdf_path))

        report = build_barcode_export_report(user_labels, generated_at)
        with zipfile.ZipFile(zip_buffer, "w") as zipf:
            for pdf_filename, pdf_path in pdf_files:
                zipf.write(pdf_path, arcname=pdf_filename)
            zipf.writestr(BARCODE_EXPORT_REPORT_FILENAME, report.encode("utf-8"))

    zip_buffer.seek(0)
    return dcc.send_bytes(zip_buffer.getvalue(), filename=zip_filename)


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
    Input("edit_input", "n_submit"),
    prevent_initial_call=True,
)
def open_edit_modal(open_user, open_prod, close_delete, close_edit, submit_edit):
    trigger = ctx.triggered_id
    if trigger in ["edit_users", "edit_prods"] and any(
        [trig is not None for trig in [open_user, open_prod]]
    ):
        text = "user" if "user" in trigger else "product"
        return True, trigger.split("_")[1], f"Input barcode for {text}"
    if trigger == "edit_input" and submit_edit:
        return False, None, no_update
    if trigger in ["edit_modal_delete", "edit_modal_edit"] and any(
        [trig is not None for trig in [close_delete, close_edit]]
    ):
        return False, None, no_update
    return no_update, no_update, no_update


@callback_with_error_queue(6,
    Output("new_user_modal", "is_open", allow_duplicate=True),
    Output("new_prod_modal", "is_open", allow_duplicate=True),
    Output({"index": ALL, "type": "user_input"}, "value", allow_duplicate=True),
    Output({"index": ALL, "type": "prod_input"}, "value", allow_duplicate=True),
    Output("user_table", "data", allow_duplicate=True),
    Output("prod_table", "data", allow_duplicate=True),
    Input("edit_modal_delete", "n_clicks"),
    Input("edit_modal_edit", "n_clicks"),
    Input("edit_input", "n_submit"),
    State("edit_modal_row", "data"),
    State("edit_input", "value"),
    prevent_initial_call=True,
)
@db_transaction_result(
    fallback_values=(
        no_update,
        no_update,
        [no_update] * 6,
        [no_update] * 5,
        no_update,
        no_update,
    )
)
def edit_new_data_modals(delete, edit, submit_edit, table, barcode):
    db = Container.get(Database)
    user_table = db._user_table
    prod_table = db._product_table
    user_col_count = 6
    prod_col_count = 5

    trigger = ctx.triggered_id
    if trigger == "edit_modal_delete" and barcode is not None:
        transactions = db._transaction_table.get()
        if table == "users":
            data = user_table.get()
            other_table_data = no_update
            in_use = transactions["barcode_user"].astype(str).eq(str(barcode)).any()
            delete_type = "user"
        elif table == "prods":
            data = prod_table.get()
            other_table_data = no_update
            in_use = transactions["barcode_prod"].astype(str).eq(str(barcode)).any()
            delete_type = "product"
        if in_use:
            raise ValueError(
                f"Cannot delete {delete_type} {barcode} because it has transactions."
            )
        barcode_mask = data["barcode"] == int(barcode)
        data = data[~barcode_mask].copy()
        db.upload_values_raises(data, table)
        if table == "users":
            return (
                no_update,
                no_update,
                [no_update] * user_col_count,
                [no_update] * prod_col_count,
                data.to_dict(orient="records"),
                other_table_data,
            )
        return (
            no_update,
            no_update,
            [no_update] * user_col_count,
            [no_update] * prod_col_count,
            other_table_data,
            data.to_dict(orient="records"),
        )
    elif trigger in ["edit_modal_edit", "edit_input"] and barcode is not None:
        if table == "users":
            data = user_table.get()
            row = data[data["barcode"] == int(barcode)]
            if len(row) == 0:
                return no_update, no_update, [no_update] * user_col_count, [no_update] * prod_col_count, no_update, no_update
            row_dict = row.iloc[0].to_dict()
            is_guest = int(str(row_dict.get("is_guest", 0))) == 1
            paid = int(row_dict.get("paid_cents", 0)) / 100
            row_list = [
                row_dict["barcode"],
                row_dict["name"],
                row_dict["rank"],
                row_dict["team"],
                [1] if is_guest else [],
                paid,
            ]
            return True, False, row_list, [no_update] * prod_col_count, no_update, no_update
        if table == "prods":
            data = prod_table.get()
            row = data[data["barcode"] == int(barcode)]
            if len(row) == 0:
                return no_update, no_update, [no_update] * user_col_count, [no_update] * prod_col_count, no_update, no_update
            row_dict = row.iloc[0].to_dict()
            row = [
                row_dict["barcode"],
                row_dict["name"],
                row_dict["price"],
                row_dict["category"],
                row_dict["initial_stock"],
            ]
            return False, True, [no_update] * user_col_count, row, no_update, no_update
    else:
        return no_update, no_update, [no_update] * user_col_count, [no_update] * prod_col_count, no_update, no_update


@callback_with_error_queue(1,
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


@callback_with_error_queue(1,
    Output("backup_filename", "data"),
    Input("backup_interval", "n_intervals"),
    State("backup_interval", "interval"),
)
def backup_database(trigger, interval):
    if trigger is not None and interval != 0:
        db = Container.get(Database)
        return create_database_backup(db.data_file, label="backup")
    return no_update


@callback(
    Output("diagnostics_status", "children"),
    Output("download_diagnostics_btn", "disabled"),
    Input("settings_modal", "is_open"),
)
def refresh_diagnostics_status(settings_open):
    if not settings_open:
        return no_update, no_update

    status_text, download_available = get_diagnostics_status()
    return status_text, not download_available


@callback_with_error_queue(
    1,
    Output("diagnostics_download", "data"),
    Input("download_diagnostics_btn", "n_clicks"),
)
def download_diagnostics(trigger):
    if trigger is None:
        return no_update

    archive = build_diagnostics_archive()
    timestamp = datetime.now().strftime("%d_%m_%Y_%H_%M_%S")
    filename = f"swampmachine_diagnostics_{timestamp}.zip"
    return dcc.send_bytes(archive, filename=filename)


@callback(Output("backup_interval", "interval"), Input("settings_backup_time", "value"))
def set_backup_timer(interval):
    if interval is not None:
        update_values(backup_time=interval)
        return interval * 60000  # Convert to minutes
    return no_update


@callback(
    Output("cache_validation_interval", "interval"),
    Input("settings_cache_validation_time", "value"),
)
def set_cache_validation_timer(interval):
    if interval is not None:
        update_values(cache_validation_time=interval)
        return interval * 60000
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

    return format_count_bar_chart(px.bar(study_table, text="user"))
