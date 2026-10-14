import pytest
import sqlite3
from contextlib import closing
from src.container import Container
from src.database.data_connection import Database, TransactionResult, db_transaction_raises, db_transaction_result
from src.error_handler import Result

@pytest.fixture
def test_db(tmp_path):
    # Arrange: create Database and register in Container
    db_file = str(tmp_path / "tx_fixture.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()

def test_execute_in_transaction_rolls_back_on_exception(test_db):
    # Arrange
    db = test_db
    product_row = {
        'barcode': '999',
        'name': 'CrashBeer',
        'price': '1.00',
        'category': 'Crash',
        'current_stock': '5',
        'initial_stock': '5',
    }

    # Act
    def tx_body():
        db._product_table.set([product_row])
        raise RuntimeError('simulated crash')

    with pytest.raises(RuntimeError):
        db.execute_in_transaction(tx_body).raise_if_error()

    # Assert - DB must not contain the row and cache must reflect that
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0

def test_db_transaction_decorator_rolls_back_and_refreshes_cache(test_db):
    # Arrange
    db = test_db
    product_row = {
        'barcode': '1234',
        'name': 'DecorBeer',
        'price': '2.00',
        'category': 'Decor',
        'current_stock': '3',
        'initial_stock': '3',
    }

    @db_transaction_raises
    def callback_that_crashes():
        db._product_table.set([product_row])
        raise ValueError('boom in callback')

    # Act / Assert
    with pytest.raises(ValueError):
        callback_that_crashes()

    # Assert - no row persisted and cache empty
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0


def test_db_transaction_result_uses_fallback_values_on_exception(test_db):
    @db_transaction_result(fallback_values=("fallback", "reset"))
    def callback_that_crashes():
        raise ValueError('boom')

    result = callback_that_crashes()

    assert isinstance(result, Result)
    assert result.values == ("fallback", "reset")
    assert isinstance(result.error, ValueError)

def test_set_then_error_between_sets_rolls_back(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '200', 'name': 'A', 'price': '1.00', 'category': 'X', 'current_stock': '1', 'initial_stock': '1'}
    row2 = {'barcode': '201', 'name': 'B', 'price': '2.00', 'category': 'Y', 'current_stock': '1', 'initial_stock': '1'}

    # Act
    def tx_body():
        db._product_table.set([row1])
        # simulate crash between sets
        raise Exception('crash between sets')
        db._product_table.set([row2])

    with pytest.raises(Exception):
        db.execute_in_transaction(tx_body).raise_if_error()

    # Assert - neither row should be persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0

def test_set_multiple_rows_commit_on_success(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '300', 'name': 'C', 'price': '3.00', 'category': 'Z', 'current_stock': '2', 'initial_stock': '2'}
    row2 = {'barcode': '301', 'name': 'D', 'price': '4.00', 'category': 'W', 'current_stock': '2', 'initial_stock': '2'}

    # Act
    def tx_body():
        db._product_table.set([row1])
        db._product_table.set([row1, row2])

    db.execute_in_transaction(tx_body)

    # Assert - both rows persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 2
    assert len(db._product_table.get()) == 2


def test_append_then_error_between_appends_rolls_back(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '400', 'name': 'E', 'price': '5.00', 'category': 'M', 'current_stock': '1', 'initial_stock': '1'}
    row2 = {'barcode': '401', 'name': 'F', 'price': '6.00', 'category': 'N', 'current_stock': '1', 'initial_stock': '1'}

    # Act
    def tx_body():
        db._product_table.append([row1])
        # simulate crash between appends
        raise Exception('crash between appends')
        db._product_table.append([row2])

    with pytest.raises(Exception):
        db.execute_in_transaction(tx_body).raise_if_error()


    # Assert - neither row should be persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 0
    assert len(db._product_table.get()) == 0


def test_append_multiple_rows_commit_on_success(test_db):
    # Arrange
    db = test_db
    row1 = {'barcode': '500', 'name': 'G', 'price': '7.00', 'category': 'O', 'current_stock': '2', 'initial_stock': '2'}
    row2 = {'barcode': '501', 'name': 'H', 'price': '8.00', 'category': 'P', 'current_stock': '2', 'initial_stock': '2'}

    # Act
    def tx_body():
        db._product_table.append([row1])
        db._product_table.append([row2])

    db.execute_in_transaction(tx_body)

    # Assert - both rows persisted
    con = sqlite3.connect(db.data_file)
    cur = con.cursor()
    cur.execute('SELECT COUNT(*) FROM prods')
    count = cur.fetchone()[0]
    con.close()
    assert count == 2
    assert len(db._product_table.get()) == 2


@pytest.mark.parametrize(
    "error, values",
    [(RuntimeError("inner failure"), ()), (None, ("cancelled",))],
    ids=["exception", "commit-false"],
)
def test_nested_rollback_preserves_outcome_and_owner_restores_users_and_cache(test_db, error, values):
    test_db.upload_values_raises(
        [{"barcode": 1000, "name": "Alice", "rank": "Member", "team": "A"}], "users"
    )
    before = test_db.users

    def inner():
        if error is not None:
            raise error
        return TransactionResult(values=values, commit=False)

    def outer():
        test_db.upload_values_raises([], "users")
        _, cur = test_db._connection.connect()
        cur.execute("DROP TABLE users")
        result = test_db.execute_in_transaction(inner)
        return TransactionResult(values=result.to_values(), commit=False)

    result = test_db.execute_in_transaction(outer)

    assert result.error is error
    assert result.values == values
    assert test_db.users.equals(before)
    with closing(sqlite3.connect(test_db.data_file)) as con:
        assert con.execute("SELECT barcode FROM users").fetchall() == [(1000,)]
