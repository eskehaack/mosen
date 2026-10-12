import base64
import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import io
import sqlite3
import types
import zipfile
from unittest.mock import Mock

import pytest
import pandas as pd
from dash import no_update

from src import main_layout, main_page_callbacks
from src.analytics.product_calculations import get_waste_table
from src.analytics.trans_calculations import get_income, get_revenue
from src.database.data_connection import Database, get_last_stock_update_at, update_values
from src.container import Container


def _encoded_csv(csv):
    return "data:text/csv;base64," + base64.b64encode(
        csv.encode("utf-8")
    ).decode("ascii")


def _user_row(barcode=1000, name="Alice", **optional_values):
    return {"barcode": barcode, "name": name, "rank": "Member", "team": "A", **optional_values}


def _users_csv(*rows):
    return pd.DataFrame(rows).to_csv(index=False)


def _database_rows(db):
    return {
        name: table.get_untyped().to_dict(orient="records")
        for name, table in db.tables.items()
    }


@pytest.fixture
def settings_upload(monkeypatch, tmp_path):
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(tmp_path / "backups"))
    context = types.SimpleNamespace(triggered_id=None)
    monkeypatch.setattr(main_page_callbacks, "ctx", context)

    def upload(content, filename="users.csv", table="users"):
        context.triggered_id = {"index": table, "type": "database_upload"}
        tables = ["users", "prods", "transactions"]
        index = tables.index(table)
        uploads = [None] * 3
        filenames = [None] * 3
        if isinstance(content, str):
            content = content.encode("utf-8")
        uploads[index] = (
            "data:application/octet-stream;base64," + base64.b64encode(content).decode("ascii")
        )
        filenames[index] = filename
        return main_page_callbacks.update_settings(
            None, True, uploads, [{"index": name} for name in tables],
            "equal_all", 75, "pw", filenames, [],
        )

    return upload


def _find_component(component, component_id):
    if getattr(component, "id", None) == component_id:
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]

    for child in children:
        found = _find_component(child, component_id)
        if found is not None:
            return found
    return None


def _load_transaction_data(temp_db, transactions=None):
    temp_db.upload_values(
        [
            {
                "barcode": "1000",
                "name": "Alice",
                "rank": "Member",
                "team": "A",
            }
        ],
        "users",
    )
    temp_db.upload_values(
        [
            {
                "barcode": "101",
                "name": "Beer",
                "price": 10,
                "category": "Drinks",
                "current_stock": 8,
                "initial_stock": 10,
            }
        ],
        "prods",
    )
    temp_db.upload_values(
        transactions
        or [
            {
                "barcode_user": "1000",
                "barcode_prod": "101",
                "timestamp": "26/07/2026 10:00:00",
            }
        ],
        "transactions",
    )


def _load_barcode_export_data(temp_db, users):
    temp_db.upload_values(users, "users")
    temp_db.upload_values(
        [
            {
                "barcode": 101,
                "name": "Beer",
                "price": 10,
                "category": "Drinks",
                "current_stock": 8,
                "initial_stock": 10,
            }
        ],
        "prods",
    )


@pytest.fixture
def reset_all_tables(monkeypatch):
    reset = Mock()
    monkeypatch.setattr(main_page_callbacks, "reset_all_tables", reset)
    return reset


@pytest.mark.parametrize(
    "trigger, expected",
    [
        pytest.param("reset_app", True, id="open"),
        pytest.param("cancel_delete_data_btn", False, id="cancel"),
        pytest.param(None, no_update, id="initial-render"),
    ],
)
def test_reset_dialog_never_resets_data_without_confirmation(
    monkeypatch, reset_all_tables, trigger, expected
):
    monkeypatch.setattr(main_page_callbacks, "ctx", types.SimpleNamespace(triggered_id=trigger))

    result = main_page_callbacks.reset_database(1, 1, 1, [])

    assert result == (expected, no_update)
    reset_all_tables.assert_not_called()


def test_confirming_reset_resets_tables_and_closes_dialog(
    monkeypatch, reset_all_tables
):
    monkeypatch.setattr(main_page_callbacks, "ctx", types.SimpleNamespace(triggered_id="delete_data_btn"))

    result = main_page_callbacks.reset_database(1, 1, None, [])

    assert result == (False, no_update)
    reset_all_tables.assert_called_once_with()


def test_reset_failure_preserves_dialog_and_appends_original_error(
    monkeypatch, reset_all_tables
):
    reset_all_tables.side_effect = RuntimeError("reset failed")
    monkeypatch.setattr(main_page_callbacks, "ctx", types.SimpleNamespace(triggered_id="delete_data_btn"))
    previous_error = {"msg": "earlier error"}

    is_open, errors = main_page_callbacks.reset_database(1, 1, None, [previous_error])

    assert is_open is no_update
    assert errors[0] == previous_error
    assert len(errors) == 2
    assert errors[-1]["src"] == "reset_database"
    assert errors[-1]["msg"] == "reset failed"


def test_income_lookup_empty_query_returns_all_rows_without_mutating_source():
    # Arrange
    rows = [
        {"barcode": "1000", "name": "Alice", "price": 12.5},
        {"barcode": "1001", "name": "Bob", "price": 8},
    ]
    original_rows = copy.deepcopy(rows)

    # Act
    result = main_page_callbacks.filter_income_rows(rows, "  ")

    # Assert
    assert result == rows
    assert result is not rows
    assert all(
        result_row is not source_row
        for result_row, source_row in zip(result, rows)
    )
    assert rows == original_rows


def test_income_lookup_matches_partial_names_case_insensitively():
    # Arrange
    rows = [
        {"barcode": "1000", "name": "Alice Jensen", "price": 12.5},
        {"barcode": "1001", "name": "ALICE Nielsen", "price": 8},
        {"barcode": "1002", "name": "Bob", "price": 4},
    ]

    # Act
    result = main_page_callbacks.filter_income_rows(rows, "alice")

    # Assert
    assert [row["barcode"] for row in result] == ["1000", "1001"]


def test_income_lookup_uses_prefix_until_barcode_is_exact():
    # Arrange
    rows = [
        {"barcode": "100", "name": "Alice", "price": 12.5},
        {"barcode": "1000", "name": "Bob", "price": 8},
        {"barcode": "2000", "name": "Carol", "price": 4},
    ]

    # Act
    partial_result = main_page_callbacks.filter_income_rows(rows, "10")
    exact_result = main_page_callbacks.filter_income_rows(rows, "100")

    # Assert
    assert [row["barcode"] for row in partial_result] == ["100", "1000"]
    assert exact_result == [{"barcode": "100", "name": "Alice", "price": 12.5}]


def test_income_lookup_callback_preserves_payment_values_and_tooltips():
    # Arrange
    rows = [
        {
            "barcode": "1000",
            "name": "Alice",
            "purchases": 10,
            "waste": 2.5,
            "paid": 0,
            "price": 12.5,
        },
        {
            "barcode": "1001",
            "name": "Bob",
            "purchases": 8,
            "waste": None,
            "paid": 0,
            "price": 8,
        },
    ]

    # Act
    filtered, tooltips, status = main_page_callbacks.update_income_lookup(
        "1000", rows
    )

    # Assert
    assert filtered == [rows[0]]
    assert filtered[0]["price"] == 12.5
    assert tooltips[0]["price"]["value"] == "12.5"
    assert status == ""


def test_income_lookup_callback_reports_no_match():
    # Arrange
    rows = [{"barcode": "1000", "name": "Alice", "price": 12.5}]

    # Act
    filtered, tooltips, status = main_page_callbacks.update_income_lookup(
        "missing", rows
    )

    # Assert
    assert filtered == []
    assert tooltips == []
    assert status == "No matching user."


def test_economy_layout_reuses_one_income_snapshot(monkeypatch, temp_db):
    # Arrange
    _load_transaction_data(temp_db)
    expected_rows = get_income()
    income_calls = 0

    def tracked_get_income():
        nonlocal income_calls
        income_calls += 1
        return copy.deepcopy(expected_rows)

    monkeypatch.setattr(main_layout, "get_income", tracked_get_income)

    # Act
    layout = main_layout.transaction_settings_layout()

    # Assert
    income_table = _find_component(layout, "income_table")
    income_store = _find_component(layout, "income_table_all_rows")
    income_search = _find_component(layout, "income_search")
    assert income_calls == 1
    assert income_table.data == expected_rows
    assert income_store.data == expected_rows
    assert income_search.placeholder == "Type a name or scan a barcode"


def test_payment_modal_stays_closed_when_economy_tab_renders(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="export_payments_btn"),
    )

    # Act
    result = main_page_callbacks.control_payments_modal(
        None, None, 0, "Up", 0, []
    )

    # Assert
    assert result == (no_update, no_update, no_update)


def test_selected_transaction_uses_sorted_virtual_table_position():
    # Arrange
    sorted_rows = [
        {
            "barcode_user": "1001",
            "barcode_prod": "102",
            "timestamp": "26/07/2026 11:00:00",
        },
        {
            "barcode_user": "1000",
            "barcode_prod": "101",
            "timestamp": "26/07/2026 10:00:00",
        },
    ]

    # Act
    selected = main_page_callbacks.get_selected_transaction(sorted_rows, [1])

    # Assert
    assert selected == sorted_rows[1]


def test_remove_transaction_button_requires_selection(monkeypatch, temp_db):
    # Arrange
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="remove_transaction_btn"),
    )

    # Act
    result = main_page_callbacks.control_transaction_removal(
        1, None, None, [], [], None, None, []
    )

    # Assert
    assert result[:4] == (no_update, no_update, no_update, no_update)
    assert "Select a transaction" in result[4][0]["msg"]


def test_remove_transaction_confirmation_shows_transaction_details(
    monkeypatch, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    transaction = temp_db.transactions.iloc[0].to_dict()
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="remove_transaction_btn"),
    )

    # Act
    result = main_page_callbacks.control_transaction_removal(
        1, None, None, [transaction], [0], None, None, []
    )

    # Assert
    assert result[0] is True
    assert result[2] == transaction
    summary = str(result[1])
    assert "Alice (1000)" in summary
    assert "Beer (101)" in summary
    assert "26/07/2026 10:00:00" in summary
    assert result[4] is no_update


def test_cancel_transaction_removal_changes_nothing(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="cancel_remove_transaction"),
    )
    before = temp_db.transactions.to_dict(orient="records")

    # Act
    result = main_page_callbacks.control_transaction_removal(
        None, 1, None, None, None, before[0], 2, []
    )

    # Assert
    assert result == (False, no_update, None, no_update, no_update)
    assert temp_db.transactions.to_dict(orient="records") == before
    assert not backup_dir.exists()


def test_confirm_transaction_removal_deletes_one_match_backs_up_and_blocks_export(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    duplicate = {
        "barcode_user": "1000",
        "barcode_prod": "101",
        "timestamp": "26/07/2026 10:00:00",
    }
    _load_transaction_data(temp_db, [duplicate.copy(), duplicate.copy()])
    update_values(last_stock_update_at="2026-07-26T10:30:00")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_remove_transaction"),
    )
    stock_before = temp_db.prods.iloc[0].to_dict()

    # Act
    result = main_page_callbacks.control_transaction_removal(
        None, None, 1, None, None, duplicate, 4, []
    )

    # Assert
    assert result == (False, no_update, None, 5, no_update)
    assert temp_db.transactions.to_dict(orient="records") == [duplicate]
    assert temp_db.prods.iloc[0].to_dict() == stock_before
    assert get_last_stock_update_at() == ""
    warning = main_page_callbacks._validate_payment_export_stock_freshness()
    assert warning.block_export is True
    assert "Update stock" in warning.message

    backups = list(backup_dir.glob("*_pre_transaction_delete_*.db"))
    assert len(backups) == 1
    con = sqlite3.connect(backups[0])
    try:
        backed_up_count = con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        backed_up_stock_timestamp = con.execute(
            "SELECT last_stock_update_at FROM settings"
        ).fetchone()[0]
    finally:
        con.close()
    assert backed_up_count == 2
    assert backed_up_stock_timestamp == "2026-07-26T10:30:00"


def test_confirm_missing_transaction_reports_error_without_changing_anything(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    update_values(last_stock_update_at="2026-07-26T10:30:00")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_remove_transaction"),
    )
    missing = {
        "barcode_user": "1000",
        "barcode_prod": "101",
        "timestamp": "26/07/2026 12:00:00",
    }
    transactions_before = temp_db.transactions.to_dict(orient="records")
    settings_before = temp_db.settings.to_dict(orient="records")
    products_before = temp_db.prods.to_dict(orient="records")

    # Act
    result = main_page_callbacks.control_transaction_removal(
        None, None, 1, None, None, missing, 9, []
    )

    # Assert
    assert result[:4] == (no_update, no_update, no_update, no_update)
    assert "no longer exists" in result[4][0]["msg"]
    assert temp_db.transactions.to_dict(orient="records") == transactions_before
    assert temp_db.settings.to_dict(orient="records") == settings_before
    assert temp_db.prods.to_dict(orient="records") == products_before
    assert not backup_dir.exists()


def test_transaction_removal_write_failure_rolls_back_data_and_stock_timestamp(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    update_values(last_stock_update_at="2026-07-26T10:30:00")
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(backup_dir))
    transaction = temp_db.transactions.iloc[0].to_dict()
    transactions_before = temp_db.transactions.to_dict(orient="records")
    settings_before = temp_db.settings.to_dict(orient="records")
    monkeypatch.setattr(
        temp_db._settings_table,
        "set",
        lambda _rows: ("settings", [{"last_stock_update_at": ""}]),
    )

    # Act
    with pytest.raises(ValueError, match="Failed to update settings"):
        main_page_callbacks.remove_transaction(transaction)

    # Assert
    assert temp_db.transactions.to_dict(orient="records") == transactions_before
    assert temp_db.settings.to_dict(orient="records") == settings_before
    assert len(list(backup_dir.glob("*_pre_transaction_delete_*.db"))) == 1


def test_removing_final_transaction_refreshes_live_calculations(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    transaction = temp_db.transactions.iloc[0].to_dict()
    monkeypatch.setattr(
        main_page_callbacks,
        "BACKUP_DIR",
        str(tmp_path / "backups"),
    )
    assert get_revenue() == 10
    assert get_income()[0]["#products"] == 1
    assert get_waste_table()[0]["Amount Sold"] == 1

    # Act
    main_page_callbacks.remove_transaction(transaction)

    # Assert
    assert temp_db.transactions.empty
    assert get_revenue() == 0
    assert get_income()[0]["#products"] == 0
    assert get_waste_table()[0]["Amount Sold"] == 0
    assert get_waste_table()[0]["Waste"] == 2


def test_transaction_removal_revision_refreshes_settings_layouts(
    monkeypatch, temp_db
):
    # Arrange
    marker = object()
    monkeypatch.setattr(main_layout.time, "sleep", lambda _: None)
    monkeypatch.setattr(main_layout, "user_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "product_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "transaction_settings_layout", lambda: marker)

    # Act
    result = main_layout.update_settings_layout(
        None, False, None, None, None, None, None, 1
    )

    # Assert
    assert result == (marker, marker, marker)


@pytest.mark.parametrize("filename", ["users.csv", "USERS.CSV"])
def test_first_user_import_commits_settings_and_data_after_backup(
    settings_upload, tmp_path, temp_db, filename
):
    # Arrange / Act
    result = settings_upload(_users_csv(_user_row()), filename=filename)

    # Assert
    assert result[2] is False
    assert result[5] is no_update
    user = temp_db._user_table.get().iloc[0]
    assert user["name"] == "Alice"
    assert user[["is_guest", "waste_cents", "paid_cents"]].tolist() == [0, -1, 0]
    assert temp_db.settings.iloc[0]["password"] == "pw"

    backups = list((tmp_path / "backups").glob("*_pre_import_*.db"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as con:
        assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


@pytest.mark.parametrize(
    "table, filename, content, message",
    [
        pytest.param("users", "backup.db", b"SQLite format 3\0", "Upload a CSV file", id="users-db"),
        pytest.param("prods", "backup.db", b"SQLite format 3\0", "Upload a CSV file", id="products-db"),
        pytest.param("transactions", "backup.db", b"SQLite format 3\0", "Upload a CSV file", id="transactions-db"),
        pytest.param("users", "users.txt", b"barcode,name,rank,team\n", "Upload a CSV file", id="wrong-extension"),
        pytest.param("users", None, b"barcode,name,rank,team\n", "Upload a CSV file", id="missing-filename"),
        pytest.param("users", "users.csv", b"SQLite format 3\0", "Cannot read users.csv as CSV", id="renamed-db"),
        pytest.param("users", "users.csv", b"\xff", "Cannot read users.csv as CSV", id="invalid-utf8"),
        pytest.param(
            "users", "users.csv", b'barcode,name\n1000,"unfinished\n',
            "Cannot read users.csv as CSV", id="malformed-csv",
        ),
        pytest.param("users", "users.csv", b"", "Cannot read users.csv as CSV", id="empty-file"),
        pytest.param("users", "users.csv", b"Not a table export\n", "missing required columns", id="missing-headers"),
    ],
)
def test_invalid_upload_reports_clear_error_without_changing_data(
    settings_upload, tmp_path, temp_db, table, filename, content, message
):
    # Arrange
    _load_transaction_data(temp_db)
    before = _database_rows(temp_db)

    # Act
    result = settings_upload(content, filename=filename, table=table)

    # Assert
    assert result[:5] == (no_update, no_update, True, [no_update] * 3, no_update)
    assert message in result[5][0]["msg"]
    assert _database_rows(temp_db) == before
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize(
    "column, stored_value, changed_value",
    [("is_guest", 1, 0), ("waste_cents", 450, 600), ("paid_cents", 2500, 900)],
)
@pytest.mark.parametrize("form", ["omitted", "blank", "changed"])
def test_user_reimport_cannot_overwrite_non_default_optional_values(
    settings_upload, tmp_path, temp_db, column, stored_value, changed_value, form
):
    # Arrange
    temp_db.upload_values_raises([_user_row(**{column: stored_value})], "users")
    before = _database_rows(temp_db)
    imported_user = _user_row(name="Changed User")
    if form != "omitted":
        imported_user[column] = None if form == "blank" else changed_value

    # Act
    result = settings_upload(_users_csv(imported_user))

    # Assert
    assert result[:5] == (no_update, no_update, True, [no_update] * 3, no_update)
    assert "would overwrite non-default values" in result[5][0]["msg"]
    assert column in result[5][0]["msg"]
    assert "1000" in result[5][0]["msg"]
    assert _database_rows(temp_db) == before
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize(
    "stored, imported, expected",
    [
        pytest.param([0, -1, 0], {}, [0, -1, 0], id="omitted-defaults"),
        pytest.param(
            [0, -1, 0], dict(is_guest=None, waste_cents=None, paid_cents=None),
            [0, -1, 0], id="blank-defaults",
        ),
        pytest.param(
            [0, -1, 0], dict(is_guest=1, waste_cents=1200, paid_cents=900),
            [1, 1200, 900], id="change-defaults",
        ),
        pytest.param(
            [1, 450, 0], dict(is_guest=1, waste_cents=450, paid_cents=2500),
            [1, 450, 2500], id="change-only-default",
        ),
        pytest.param(
            [1, 450, 2500], dict(is_guest=1, waste_cents=450, paid_cents=2500),
            [1, 450, 2500], id="matching-values",
        ),
        pytest.param(
            [1, 450, 2500], dict(is_guest=1.0, waste_cents=450.0, paid_cents=2500.0),
            [1, 450, 2500], id="matching-floats",
        ),
        pytest.param([0, 450, 2500], dict(waste_cents=450, paid_cents=2500), [0, 450, 2500], id="omit-default-guest"),
        pytest.param([1, -1, 2500], dict(is_guest=1, paid_cents=2500), [1, -1, 2500], id="omit-default-waste"),
        pytest.param([1, 450, 0], dict(is_guest=1, waste_cents=450), [1, 450, 0], id="omit-default-payment"),
    ],
)
def test_user_reimport_allows_defaults_and_matching_values(
    settings_upload, temp_db, stored, imported, expected
):
    # Arrange
    columns = ["is_guest", "waste_cents", "paid_cents"]
    temp_db.upload_values_raises([_user_row(**dict(zip(columns, stored)))], "users")

    # Act
    result = settings_upload(_users_csv(_user_row(name="Changed User", **imported)))

    # Assert
    assert result[2] is False
    assert result[5] is no_update
    user = temp_db._user_table.get().iloc[0]
    assert user["name"] == "Changed User"
    assert user[columns].tolist() == expected


@pytest.mark.parametrize("include_optional", [False, True])
def test_user_reimport_matches_by_barcode_when_adding_and_removing_users(
    settings_upload, temp_db, include_optional
):
    # Arrange: only Alice has purchases; unpaid Bob can be removed.
    _load_transaction_data(temp_db)
    optional = dict(is_guest=1, waste_cents=450, paid_cents=2500) if include_optional else {}
    temp_db.upload_values_raises([_user_row(**optional)], "users")
    temp_db._user_table.append([_user_row(1001, "Bob", is_guest=1, waste_cents=200)])
    transactions_before = temp_db.transactions.to_dict(orient="records")

    # Act: a new row first also checks that matching is independent of row order.
    result = settings_upload(_users_csv(
        _user_row(1002, "New User"), _user_row(name="Renamed Alice", **optional)
    ))

    # Assert
    assert result[2] is False
    assert result[5] is no_update
    users = temp_db._user_table.get().set_index("barcode")
    columns = ["is_guest", "waste_cents", "paid_cents"]
    assert set(users.index) == {1000, 1002}
    assert users.loc[1000, "name"] == "Renamed Alice"
    assert users.loc[1000, columns].tolist() == ([1, 450, 2500] if include_optional else [0, -1, 0])
    assert users.loc[1002, columns].tolist() == [0, -1, 0]
    assert temp_db.transactions.to_dict(orient="records") == transactions_before


def test_user_reimport_cannot_swap_non_default_values_between_barcodes(
    settings_upload, tmp_path, temp_db
):
    # Arrange
    temp_db.upload_values_raises([
        _user_row(is_guest=1, waste_cents=450, paid_cents=2500),
        _user_row(1001, "Bob", is_guest=0, waste_cents=-1, paid_cents=900),
    ], "users")
    before = _database_rows(temp_db)

    # Act: the same values are present, but assigned to the wrong barcodes.
    result = settings_upload(_users_csv(
        _user_row(1001, "Bob", is_guest=1, waste_cents=450, paid_cents=2500),
        _user_row(is_guest=0, waste_cents=-1, paid_cents=900),
    ))

    # Assert
    assert "would overwrite non-default values" in result[5][0]["msg"]
    assert "1000" in result[5][0]["msg"]
    assert "1001" in result[5][0]["msg"]
    assert _database_rows(temp_db) == before
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize("include_optional", [False, True])
@pytest.mark.parametrize(
    "paid_cents, has_purchase, message",
    [
        pytest.param(0, True, "transactions", id="purchases"),
        pytest.param(1, False, "recorded early payments", id="paid-early"),
    ],
)
def test_user_import_cannot_remove_users_with_purchases_or_payments(
    settings_upload, tmp_path, temp_db, include_optional, paid_cents, has_purchase, message
):
    # Arrange: keep Alice and attempt to remove Bob.
    _load_transaction_data(temp_db)
    temp_db._user_table.append([_user_row(1001, "Bob", paid_cents=paid_cents)])
    if has_purchase:
        temp_db._transaction_table.append([{
            "barcode_user": 1001, "barcode_prod": 101, "timestamp": "26/07/2026 11:00:00",
        }])
    before = _database_rows(temp_db)
    optional = dict(is_guest=0, waste_cents=-1, paid_cents=0) if include_optional else {}

    # Act
    result = settings_upload(_users_csv(
        _user_row(name="Renamed Alice", **optional),
        _user_row(1002, "New User", **optional),
    ))

    # Assert: reject all changes and keep Bob's payment persisted.
    assert result[:5] == (no_update, no_update, True, [no_update] * 3, no_update)
    assert f"removes users with {message}" in result[5][0]["msg"]
    assert _database_rows(temp_db) == before
    with closing(sqlite3.connect(temp_db.data_file)) as con:
        assert con.execute(
            "SELECT paid_cents FROM users WHERE barcode = 1001"
        ).fetchone() == (paid_cents,)
    assert not (tmp_path / "backups").exists()


def test_empty_user_import_leaves_existing_users_untouched(
    settings_upload, tmp_path, temp_db
):
    # Arrange
    _load_transaction_data(temp_db)
    users_before = temp_db.users.to_dict(orient="records")

    # Act
    result = settings_upload("barcode,name,rank,team\n")

    # Assert
    assert result[2] is False
    assert result[5] is no_update
    assert temp_db.users.to_dict(orient="records") == users_before
    assert not (tmp_path / "backups").exists()


@pytest.mark.parametrize(
    "table_name, changed_column, expected_value",
    [("prods", "name", "Changed Product"), ("transactions", "timestamp", "26/07/2026 11:00:00")],
)
def test_other_table_import_ignores_stale_user_upload(
    monkeypatch, tmp_path, temp_db, table_name, changed_column, expected_value
):
    # Arrange
    _load_transaction_data(temp_db)
    other_table = "transactions" if table_name == "prods" else "prods"
    before = _database_rows(temp_db)
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(main_page_callbacks, "ctx", types.SimpleNamespace(
        triggered_id={"index": table_name, "type": "database_upload"}
    ))
    uploads = [
        _encoded_csv(_users_csv(_user_row(name="Stale User"))),
        _encoded_csv("barcode,name,price,category,current_stock,initial_stock\n101,Changed Product,12,Drinks,8,10\n"),
        _encoded_csv("barcode_user,barcode_prod,timestamp\n1000,101,26/07/2026 11:00:00\n"),
    ]

    # Act
    result = main_page_callbacks.update_settings(
        None, True, uploads,
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_all", 75, "pw", ["users.csv", "prods.csv", "transactions.csv"], [],
    )

    # Assert
    assert result[2] is False
    assert result[5] is no_update
    after = _database_rows(temp_db)
    assert after["users"] == before["users"]
    assert after[other_table] == before[other_table]
    assert after[table_name][0][changed_column] == expected_value
    assert len(list((tmp_path / "backups").glob("*_pre_import_*.db"))) == 1


def test_non_upload_settings_trigger_does_not_reimport_stale_upload(
    monkeypatch, tmp_path, temp_db
):
    # Arrange
    monkeypatch.setattr(main_page_callbacks, "BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setattr(
        main_page_callbacks, "ctx", types.SimpleNamespace(triggered_id="confirm_new_password")
    )
    temp_db.upload_values_raises([_user_row(name="Original User")], "users")
    stale_upload = _encoded_csv(_users_csv(_user_row(1001, "Imported User")))

    # Act
    result = main_page_callbacks.update_settings.__wrapped__(
        1, True, [stale_upload, None, None],
        [{"index": "users"}, {"index": "prods"}, {"index": "transactions"}],
        "equal_category_purchasers", 50, "pw", ["users.csv", "prods.csv", "transactions.csv"],
    )

    # Assert
    assert result.error is None
    assert result.values[-1] is True
    assert temp_db.users.iloc[0]["name"] == "Original User"
    assert not (tmp_path / "backups").exists()


def test_failed_import_rolls_back_changes_but_keeps_pre_import_backup(
    settings_upload, tmp_path, temp_db
):
    # Arrange
    before = _database_rows(temp_db)
    invalid_csv = _users_csv(_user_row(999, "Bad User"))

    # Act
    result = settings_upload(invalid_csv)

    # Assert
    assert result[2] is True
    assert result[5] is no_update
    assert _database_rows(temp_db) == before
    backups = list((tmp_path / "backups").glob("*_pre_import_*.db"))
    assert len(backups) == 1
    with closing(sqlite3.connect(backups[0])) as con:
        assert con.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0

    # A failed first import must still allow a corrected file.
    retry = settings_upload(_users_csv(_user_row(name="Corrected User")))
    assert retry[2] is False
    assert retry[5] is no_update
    assert temp_db.users.iloc[0]["name"] == "Corrected User"


def test_export_barcodes_returns_zip_with_pdfs_and_complete_label_report(temp_db):
    # Arrange
    _load_barcode_export_data(
        temp_db,
        [
            {
                "barcode": 1000,
                "name": "Testuser Alpha Example",
                "rank": "Member",
                "team": "A",
            },
            {
                "barcode": 1001,
                "name": "Testuser Another Example",
                "rank": "Member",
                "team": "A",
            },
        ],
    )
    # Act
    download = main_page_callbacks.export_barcodes.__wrapped__(1)
    archive_bytes = base64.b64decode(download["content"])

    # Assert
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        assert set(archive.namelist()) == {
            "user_barcodes.pdf",
            "prod_barcodes.pdf",
            "multiplier_barcodes.pdf",
            "Barcode label report.txt",
        }
        report = archive.read("Barcode label report.txt").decode("utf-8")
    assert "Labels changed: 2" in report
    assert "Printed-name collision groups: 1" in report
    assert (
        "1000 'Testuser Alpha Example'; "
        "1001 'Testuser Another Example'"
    ) in report


def test_export_barcodes_surfaces_product_name_width_error(monkeypatch):
    # Arrange
    message = (
        "Product name 'An extremely long name' (barcode 102) is too long for "
        "its printed barcode label. Shorten the name and export again."
    )

    def reject_product_name(**_kwargs):
        raise ValueError(message)

    monkeypatch.setattr(main_page_callbacks, "generate_pdf", reject_product_name)

    # Act
    download, errors = main_page_callbacks.export_barcodes(1, [])

    # Assert
    assert download is no_update
    assert errors[0]["msg"] == message


def test_concurrent_barcode_exports_use_independent_temporary_files(temp_db):
    # Arrange
    _load_barcode_export_data(
        temp_db,
        [
            {
                "barcode": 1000,
                "name": "Testuser",
                "rank": "Member",
                "team": "A",
            }
        ],
    )

    def export_once(_index):
        return main_page_callbacks.export_barcodes.__wrapped__(1)

    # Act
    with ThreadPoolExecutor(max_workers=4) as pool:
        downloads = list(pool.map(export_once, range(4)))

    # Assert
    for download in downloads:
        archive_bytes = base64.b64decode(download["content"])
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            assert archive.testzip() is None
            assert set(archive.namelist()) == {
                "user_barcodes.pdf",
                "prod_barcodes.pdf",
                "multiplier_barcodes.pdf",
                "Barcode label report.txt",
            }


def test_settings_layout_contains_compact_diagnostics_controls(temp_db):
    # Act
    layout = main_layout.settings_settings_layout()

    # Assert
    status = _find_component(layout, "diagnostics_status")
    download_button = _find_component(layout, "download_diagnostics_btn")
    download = _find_component(layout, "diagnostics_download")
    diagnostics_row = _find_component(layout, "diagnostics_row")
    assert status is not None
    assert download_button is not None
    assert download_button.disabled is True
    assert download_button.className == "d-grid gap-2 col-10 mx-auto"
    assert download is not None
    assert diagnostics_row is not None
    assert [column.xs for column in diagnostics_row.children] == [12, 12, 12]
    assert [column.lg for column in diagnostics_row.children] == [4, 4, 4]


def test_settings_layout_combines_bill_preview_controls(temp_db):
    # Act
    layout = main_layout.settings_settings_layout()

    # Assert
    bill_preview_row = _find_component(layout, "bill_preview_row")
    display_switch = _find_component(layout, "display_bill_switch")
    extra_waste_input = _find_component(
        layout, "bill_preview_waste_extra_percent"
    )
    assert bill_preview_row is not None
    assert len(bill_preview_row.children) == 3
    assert [column.xs for column in bill_preview_row.children] == [12, 12, 12]
    assert [column.lg for column in bill_preview_row.children] == [4, 4, 4]
    assert bill_preview_row.children[0].children.children == "Bill preview: "
    assert getattr(display_switch, "label", None) is None
    assert extra_waste_input is not None


def test_settings_layout_aligns_switches_on_wide_screens(temp_db):
    # Act
    layout = main_layout.settings_settings_layout()

    # Assert
    bill_preview_row = _find_component(layout, "bill_preview_row")
    top_user_chart_row = _find_component(layout, "top_user_chart_row")
    assert bill_preview_row.children[1].lg == 4
    assert top_user_chart_row.children[1].lg == 4
    assert bill_preview_row.children[1].xs == 12
    assert top_user_chart_row.children[1].xs == 12


def test_settings_layout_combines_timer_controls(temp_db):
    # Act
    layout = main_layout.settings_settings_layout()

    # Assert
    timers_row = _find_component(layout, "timers_row")
    backup_timer = _find_component(layout, "settings_backup_time")
    cache_timer = _find_component(layout, "settings_cache_validation_time")
    assert timers_row is not None
    assert len(timers_row.children) == 5
    assert [column.xs for column in timers_row.children[:3]] == [12, 12, 12]
    assert [column.lg for column in timers_row.children[:3]] == [4, 4, 4]
    assert timers_row.children[0].children.children == "Timers:"
    assert backup_timer is not None
    assert cache_timer is not None


@pytest.mark.parametrize(
    ("status_text", "available", "expected_disabled"),
    [
        ("Logging active | 2 files | 6.0 MB", True, False),
        ("Logging unavailable: access denied", False, True),
    ],
)
def test_refresh_diagnostics_status(
    monkeypatch,
    status_text,
    available,
    expected_disabled,
):
    monkeypatch.setattr(
        main_page_callbacks,
        "get_diagnostics_status",
        lambda: (status_text, available),
    )

    # Act
    text, disabled = main_page_callbacks.refresh_diagnostics_status(True)

    # Assert
    assert text == status_text
    assert disabled is expected_disabled


def test_download_diagnostics_returns_archive(monkeypatch):
    # Arrange
    archive_bytes = b"diagnostics archive"
    monkeypatch.setattr(
        main_page_callbacks,
        "build_diagnostics_archive",
        lambda: archive_bytes,
    )

    # Act
    download = main_page_callbacks.download_diagnostics.__wrapped__(1)

    # Assert
    assert base64.b64decode(download["content"]) == archive_bytes
    assert download["filename"].startswith("swampmachine_diagnostics_")
    assert download["filename"].endswith(".zip")
