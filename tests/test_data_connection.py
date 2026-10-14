import pytest
import pandas as pd
import sqlite3
from contextlib import closing
from unittest.mock import Mock

from src.database import data_connection
from src.container import Container
from src.database.tables.product import ProductTable
from src.database.data_connection import (
    Database,
    get_prods,
    get_trans,
    get_users,
    get_current_trans,
    update_current_trans,
    add_transactions,
    upload_values,
    get_password,
    get_backup_time,
    get_bill_preview_waste_extra_percent,
    get_last_stock_update_at,
    get_show_bill,
    get_waste,
    update_values,
)

@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestWrapperFunctions:

    def test_get_prods_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = [
            "barcode",
            "name",
            "price",
            "category",
            "current_stock",
            "initial_stock",
        ]
        
        # Act
        result = get_prods()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    def test_get_trans_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = [
            "barcode_user",
            "barcode_prod",
            "timestamp",
        ]
        
        # Act
        result = get_trans()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    def test_get_users_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = [
            "barcode",
            "name",
            "rank",
            "team",
            "is_guest",
            "waste_cents",
            "paid_cents",
        ]
        
        # Act
        result = get_users()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    def test_get_current_trans_returns_correct_columns(self, test_db):
        # Arrange
        expected_columns = ["barcode_prod", "name"]
        
        # Act
        result = get_current_trans()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == expected_columns

    @pytest.mark.parametrize(
        "get_table_func",
        [get_prods, get_trans, get_users, get_current_trans],
    )
    def test_wrapper_functions_return_empty_on_init(self, test_db, get_table_func):
        # Arrange
        # (test_db fixture initializes empty database)
        
        # Act
        result = get_table_func()
        
        # Assert
        assert len(result) == 0

    def test_wrapper_functions_use_container_database(self, test_db):
        # Arrange
        container_db = Container.get(Database)
        
        # Act
        result = get_prods()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert Container.get(Database) is container_db


class TestProductValidation:

    def test_validate_prod_with_valid_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "10",
            "initial_stock": "20",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_prod(row, data)
        
        # Assert
        assert is_valid is True

    def test_validate_prod_rejects_invalid_barcode_length(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "12",
            "name": "Beer",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "10",
            "initial_stock": "20",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_prod(row, data)
        
        # Assert
        assert is_valid is False

    def test_validate_prod_rejects_missing_columns(self, test_db):
        # Arrange - missing required columns: category, current_stock, initial_stock
        db = Container.get(Database)
        row = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_prod(row, data)
        
        # Assert
        assert is_valid is False


class TestUserValidation:

    def test_validate_user_with_valid_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "1000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_user(row, data)
        
        # Assert
        assert is_valid is True

    def test_validate_user_rejects_short_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "999",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_user(row, data)
        
        # Assert
        assert is_valid is False

    def test_validate_user_rejects_long_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        row = {
            "barcode": "100000000000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        data = [row]
        
        # Act
        is_valid = db.validate_user(row, data)
        
        # Assert
        assert is_valid is False


class TestTransactionValidation:

    def test_validate_trans_rejects_nonexistent_product(self, test_db):
        # Arrange
        db = Container.get(Database)
        trans_row = {
            "barcode_user": "1000",
            "barcode_prod": "999",
            "timestamp": "2024-01-01 12:00:00",
        }
        
        # Act
        is_valid = db.validate_trans(trans_row, [trans_row])
        
        # Assert
        assert is_valid is False


class TestProductValidationWithDuplicates:

    def test_validate_prod_handles_duplicate_barcode(self, test_db):
        # Arrange - simulate existing products with duplicates in data
        db = Container.get(Database)
        existing_prod = {
            "barcode": "123",
            "name": "Beer",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "10",
            "initial_stock": "20",
        }
        duplicate_prod = {
            "barcode": "123",  # Same barcode as existing
            "name": "Beer Clone",
            "price": "5.00",
            "category": "Beverage",
            "current_stock": "5",
            "initial_stock": "15",
        }
        data = [existing_prod, duplicate_prod]
        
        # Act - validate the duplicate
        is_valid = db.validate_prod(duplicate_prod, data)
        
        # Assert - should auto-generate new barcode
        assert is_valid is False

    def test_validate_prod_accepts_barcode_gaps(self, test_db):
        # Arrange - products with gaps in barcode range
        db = Container.get(Database)
        data = [
            {"barcode": "100", "name": "A", "price": "1", "category": "X", "current_stock": "1", "initial_stock": "1"},
            {"barcode": "102", "name": "B", "price": "2", "category": "Y", "current_stock": "1", "initial_stock": "1"},
            {"barcode": "103", "name": "C", "price": "3", "category": "Z", "current_stock": "1", "initial_stock": "1"},
        ]
        new_row = {"barcode": "110", "name": "D", "price": "4", "category": "W", "current_stock": "1", "initial_stock": "1"}  # Invalid: 2 digits
        
        # Act
        is_valid = db.validate_prod(new_row, data)
        
        # Assert
        assert is_valid is True


class TestUserValidationWithDuplicates:

    def test_validate_user_handles_duplicate_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        existing_user = {
            "barcode": "1000",
            "name": "John",
            "rank": "Member",
            "team": "A",
        }
        duplicate_user = {
            "barcode": "1000",  # Same barcode as existing
            "name": "Jane",
            "rank": "Member",
            "team": "B",
        }
        data = [existing_user, duplicate_user]
        
        # Act
        is_valid = db.validate_user(duplicate_user, data)
        
        # Assert
        assert is_valid is False

    def test_validate_user_finds_rejects_invalid_barcode(self, test_db):
        # Arrange - users with gaps in barcode range
        db = Container.get(Database)
        data = [
            {"barcode": "1000", "name": "A", "rank": "M", "team": "X"},
            {"barcode": "1002", "name": "B", "rank": "M", "team": "Y"},
            {"barcode": "1003", "name": "C", "rank": "M", "team": "Z"},
        ]
        new_row = {"barcode": "999", "name": "D", "rank": "M", "team": "W"}
        
        # Act
        is_valid = db.validate_user(new_row, data)
        
        # Assert - barcode too short, should assign first valid gap (1000 is taken, so 1001)
        assert is_valid is False


class TestUploadValues:

    def test_upload_prods_validation_phase(self, test_db):
        # Arrange
        db = Container.get(Database)
        valid_prods = [
            {
                "barcode": "123",
                "name": "Beer",
                "price": "5.00",
                "category": "Beverage",
                "current_stock": "10",
                "initial_stock": "20",
            }
        ]
        
        # Act - test just the validation phase
        good_rows = []
        bad_rows = []
        for row in valid_prods:
            is_valid = db.validate_prod(row, valid_prods)
            if is_valid:
                good_rows.append(row)
            else:
                bad_rows.append(row)
        
        # Assert
        assert len(good_rows) == 1
        assert len(bad_rows) == 0

    def test_upload_prods_rejects_invalid_barcode(self, test_db):
        # Arrange
        db = Container.get(Database)
        invalid_prods = [
            {
                "barcode": "99",
                "name": "Beer",
                "price": "5.00",
                "category": "Beverage",
                "current_stock": "10",
                "initial_stock": "20",
            }
        ]
        
        # Act
        good_rows = []
        bad_rows = []
        for row in invalid_prods:
            is_valid = db.validate_prod(row, invalid_prods)
            if is_valid:
                good_rows.append(row)
            else:
                bad_rows.append(row)
        
        # Assert
        assert len(good_rows) == 0
        assert len(bad_rows) == 1

    def test_upload_values_returns_success_or_error(self, test_db):
        # Arrange
        valid_users = [
            {
                "barcode": "1000",
                "name": "John",
                "rank": "Member",
                "team": "A",
            }
        ]
        
        # Act
        result, bad_rows = upload_values(valid_users, "users")
        
        # Assert
        assert result in ["success", "users"]  # Either success or table name on error

    def test_upload_with_dataframe_input(self, test_db):
        # Arrange
        db = Container.get(Database)
        valid_prods_df = pd.DataFrame([
            {
                "barcode": "123",
                "name": "Beer",
                "price": "5.00",
                "category": "Beverage",
                "current_stock": "10",
                "initial_stock": "20",
            }
        ])
        
        # Act
        result, bad_rows = upload_values(valid_prods_df, "prods")
        
        # Assert
        assert result in ["success", "prods"]

    def test_add_transactions_rejects_invalid_rows(self, test_db):
        # Arrange
        invalid_rows = pd.DataFrame([
            {
                "barcode_user": "1000",
                "barcode_prod": "999",
                "timestamp": "2024-01-01 12:00:00",
            }
        ])

        # Act
        result, bad_rows = add_transactions(invalid_rows)

        # Assert
        assert result == "transactions"
        assert len(bad_rows) == 1
        assert len(get_trans()) == 0

    def test_product_append_rejects_duplicate_rows_in_same_batch(self, test_db):
        # Arrange
        duplicate_rows = pd.DataFrame([
            {"barcode": "123", "name": "Beer", "price": "5.00", "category": "Beverage", "current_stock": "10", "initial_stock": "20"},
            {"barcode": "123", "name": "Beer Clone", "price": "6.00", "category": "Beverage", "current_stock": "5", "initial_stock": "15"},
        ])

        # Act
        result, bad_rows = Container.get(Database)._product_table.append(duplicate_rows)

        # Assert
        assert result == "prods"
        assert len(bad_rows) == 2
        assert len(get_prods()) == 0


class TestSettingsOperations:

    def test_get_show_bill_returns_bool(self, test_db):
        # Arrange
        
        # Act
        show_bill = get_show_bill()
        
        # Assert
        assert isinstance(show_bill, bool)

    def test_get_waste_returns_integer(self, test_db):
        # Arrange
        
        # Act
        waste = get_waste()
        
        # Assert
        assert isinstance(waste, int)

    def test_update_values_accepts_multiple_params(self, test_db):
        # Arrange
        
        # Act
        # Should not raise an error
        update_values(password="test", waste=50)
        
        # Assert
        assert True

    def test_settings_round_trip_through_cache(self, test_db):
        # Arrange
        
        # Act
        update_values(
            password="alpha",
            show_bill=False,
            waste=12,
            backup_time=42,
            last_stock_update_at="2026-01-01T10:00:00",
            bill_preview_waste_extra_percent=25,
        )

        # Assert
        assert get_password() == "alpha"
        assert get_show_bill() is False
        assert get_waste() == 12
        assert get_backup_time() == 42
        assert get_last_stock_update_at() == "2026-01-01T10:00:00"
        assert get_bill_preview_waste_extra_percent() == 25

    def test_current_trans_round_trip_through_cache(self, test_db):
        # Arrange
        current = pd.DataFrame([
            {"barcode_prod": "123", "name": "Beer"},
        ])

        # Act
        update_current_trans(current)
        result = get_current_trans()

        # Assert
        assert len(result) == 1
        assert list(result["barcode_prod"])[0] == "123"

    def test_add_transactions_appends_and_refreshes_cache(self, test_db):
        # Arrange
        upload_values(
            [
                {
                    "barcode": "1000",
                    "name": "John",
                    "rank": "Member",
                    "team": "A",
                }
            ],
            "users",
        )
        upload_values(
            [
                {
                    "barcode": "123",
                    "name": "Beer",
                    "price": "5.00",
                    "category": "Beverage",
                    "current_stock": "10",
                    "initial_stock": "20",
                }
            ],
            "prods",
        )

        from src.database.data_connection import add_transactions

        new_rows = pd.DataFrame([
            {
                "barcode_user": "1000",
                "barcode_prod": "123",
                "timestamp": "2024-01-01 12:00:00",
            }
        ])

        # Act
        add_transactions(new_rows)

        # Assert
        result = get_trans()
        assert len(result) == 1


class TestCreateTables:

    def test_init_creates_all_tables(self, tmp_path):
        # Arrange
        db_file = str(tmp_path / "createdb.db")

        # Act
        db = Database(db_file)

        # Assert
        con, cur = db._connection.connect()
        assert db._connection.table_exists("prods") is True
        assert db._connection.table_exists("users") is True
        assert db._connection.table_exists("transactions") is True
        assert db._connection.table_exists("temporary") is True
        assert db._connection.table_exists("settings") is True
        con.close()

    def test__create_tables_recreates_dropped_table(self, test_db):
        # Arrange - ensure tables exist then drop one
        db = test_db
        con, cur = db._connection.connect()
        # Drop users table
        cur.execute("DROP TABLE IF EXISTS users")
        con.commit()
        con.close()

        assert db._connection.table_exists("users") is False

        # Act - call private method to (re)create missing tables
        db._create_tables()

        # Assert - users table recreated
        assert db._connection.table_exists("users") is True

    def test_init_closes_every_connection_it_opens(self, tmp_path, monkeypatch):
        # Arrange
        connections = []
        original_connect = sqlite3.connect

        def track_connection(*args, **kwargs):
            con = original_connect(*args, **kwargs)
            connections.append(con)
            return con

        monkeypatch.setattr(sqlite3, "connect", track_connection)

        # Act
        db = Database(str(tmp_path / "init.db"))
        db.init()

        # Assert
        for con in connections:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                con.execute("SELECT 1")

    def test_failed_table_creation_keeps_sql_error_and_undoes_prior_creates(self, test_db, monkeypatch):
        # Arrange: make creation necessary for two tables, with a failure in the second.
        with closing(sqlite3.connect(test_db.data_file)) as con:
            con.execute("DROP TABLE users")
            con.execute("DROP TABLE transactions")
        monkeypatch.setattr(test_db._transaction_table, "create_sql", "INVALID CREATE SQL")

        # Act
        with pytest.raises(sqlite3.OperationalError, match="syntax error"):
            test_db._create_tables()

        # Assert: the first CREATE is rolled back and the owned connection is closed.
        assert test_db._connection._active_con is None
        assert test_db._connection.table_exists("users") is False
        assert test_db._connection.table_exists("transactions") is False

    def test_init_does_not_commit_or_close_its_callers_transaction(self, test_db):
        # Arrange
        password = get_password()

        def initialize_then_fail():
            update_values(password="changed")
            test_db.init()
            raise RuntimeError("failure after init")

        # Act
        result = test_db.execute_in_transaction(initialize_then_fail)

        # Assert
        with pytest.raises(RuntimeError, match="failure after init"):
            result.raise_if_error()
        assert get_password() == password
        with closing(sqlite3.connect(test_db.data_file)) as con:
            assert con.execute("SELECT password FROM settings").fetchone() == (password,)


def _table_rows(db):
    return {name: table.get().to_dict(orient="records") for name, table in db.tables.items()}


@pytest.fixture
def populated_reset_db(test_db):
    test_db.upload_values_raises(
        [{"barcode": 1000, "name": "Alice", "rank": "Member", "team": "A",
          "paid_cents": 5000}], "users"
    )
    test_db.upload_values_raises(
        [{"barcode": 101, "name": "Beer", "price": 10, "category": "Drinks",
          "current_stock": 8, "initial_stock": 10}], "prods"
    )
    test_db.upload_values_raises(
        [{"barcode_user": 1000, "barcode_prod": 101,
          "timestamp": "12/10/2026 10:00:00"}], "transactions"
    )
    test_db.upload_values_raises([{"barcode_prod": 101, "name": "Beer"}], "temporary")
    update_values(password="changed", show_bill=False, waste=25, backup_time=42)
    return test_db


def test_reset_clears_configured_database_and_restores_default_settings(
    populated_reset_db, tmp_path, monkeypatch
):
    # Arrange
    db = populated_reset_db
    data_file = db.data_file
    expected = {name: [] for name in db.tables}
    expected["settings"] = [db._settings_table.default_row]
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(data_connection.k, "unhook_all", Mock())
    monkeypatch.setattr(data_connection.k, "send", Mock())

    # Act
    data_connection.reset_all_tables()

    # Assert
    assert Container.get(Database) is db
    assert not (tmp_path / "beerbase.db").exists()
    assert _table_rows(db) == expected
    with closing(sqlite3.connect(data_file)) as con:
        con.row_factory = sqlite3.Row
        saved_rows = {
            name: [dict(row) for row in con.execute(f"SELECT * FROM {name}")]
            for name in db.tables
        }
        assert saved_rows == expected
    assert _table_rows(Database(data_file)) == expected


@pytest.mark.parametrize(
    "failure_stage, error_message",
    [("drop", "not authorized"), ("create", "syntax error"), ("defaults", "defaults write failed")],
)
def test_failed_reset_restores_database_and_cache_without_exiting(
    populated_reset_db, failure_stage, error_message, monkeypatch
):
    # Arrange
    db = populated_reset_db
    before = _table_rows(db)
    exit_calls = []
    monkeypatch.setattr(data_connection.k, "unhook_all", lambda: exit_calls.append("unhook"))
    monkeypatch.setattr(data_connection.k, "send", exit_calls.append)
    if failure_stage == "drop":
        original_connect = db._connection.connect

        def deny_transaction_drop(action, table, *_args):
            if action == sqlite3.SQLITE_DROP_TABLE and table == "transactions":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        def connect_with_drop_failure():
            con, cur = original_connect()
            con.set_authorizer(deny_transaction_drop)
            return con, cur

        monkeypatch.setattr(db._connection, "connect", connect_with_drop_failure)
    elif failure_stage == "create":
        monkeypatch.setattr(db._transaction_table, "create_sql", "INVALID CREATE SQL")
    else:
        monkeypatch.setattr(db._settings_table, "set", Mock(side_effect=RuntimeError("defaults write failed")))

    # Act
    with pytest.raises((sqlite3.DatabaseError, RuntimeError), match=error_message):
        data_connection.reset_all_tables()

    # Assert: both stored rows and caches survive, and the kiosk stays open.
    assert exit_calls == []
    assert db._connection._active_con is None
    assert _table_rows(db) == before
    assert _table_rows(Database(db.data_file)) == before
