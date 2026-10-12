import pytest
import pandas as pd
from src.container import Container
from src.database.data_connection import Database
from src.database.tables.product import ProductTable


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestProductTableBasics:

    def test_product_table_creates_table(self, test_db):
        # Arrange & Act
        table = ProductTable(test_db._connection)
        
        # Assert - table should exist
        assert test_db._connection.table_exists('prods')

    def test_get_returns_empty_dataframe(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        
        # Act
        result = table.get_untyped()
        
        # Assert
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0
        assert list(result.columns) == ["barcode", "name", "price", "category", "current_stock", "initial_stock"]

    def test_get_typed_returns_correct_dtypes(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        
        # Act
        result = table.get()
        
        # Assert - empty but with correct dtypes
        assert result["barcode"].dtype == int
        assert result["name"].dtype == object  # str
        assert result["price"].dtype == float
        assert result["category"].dtype == object  # str
        assert result["current_stock"].dtype == int
        assert result["initial_stock"].dtype == int


class TestProductTableSet:

    def test_set_inserts_valid_products(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert result == "success"
        assert len(bad_rows) == 0
        assert len(table.get_untyped()) == 1

    def test_set_replaces_all_data(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data1 = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        data2 = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                "category": "Soda",
                "current_stock": 15,
                "initial_stock": 30,
            }
        ]
        
        # Act
        table.set(data1)
        table.set(data2)
        
        # Assert - should only have second dataset
        result = table.get_untyped()
        assert len(result) == 1
        assert result.iloc[0]["barcode"] == "456"

    def test_set_rejects_invalid_barcode_length(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 12,  # Invalid: 2 digits
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert result == table.table_name
        assert len(bad_rows) == 1

    def test_set_detects_duplicates(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            },
            {
                "barcode": 123,  # Duplicate
                "name": "Beer Clone",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 5,
                "initial_stock": 15,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert - both duplicate rows marked bad, neither modified
        assert len(bad_rows) == 2
        assert bad_rows[0]["barcode"] == 123  # First duplicate unchanged
        assert bad_rows[1]["barcode"] == 123  # Second duplicate unchanged

    def test_set_handles_empty_values(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "",  # Empty
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        
        # Act
        result, bad_rows = table.set(data)
        
        # Assert
        assert len(bad_rows) == 1

    def test_set_accepts_dataframe(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        df = pd.DataFrame([
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ])
        
        # Act
        result, bad_rows = table.set(df)
        
        # Assert
        assert result == "success"
        assert len(bad_rows) == 0
        assert len(table.get_untyped()) == 1



class TestProductTableGetTyped:

    def test_get_typed_returns_correct_types(self, test_db):
        # Arrange
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.50,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(data)
        
        # Act
        df = table.get()
        
        # Assert
        assert df["barcode"].dtype == int
        assert df["name"].dtype == object
        assert df["price"].dtype == float
        assert df["current_stock"].dtype == int
        assert df["initial_stock"].dtype == int
        assert df.iloc[0]["barcode"] == 123
        assert df.iloc[0]["price"] == 5.50


class TestProductTableSetAtomicity:
    """Test that set() is atomic: if any rows are rejected, no changes to database."""

    def test_set_atomic_with_invalid_barcode_length(self, test_db):
        """If some rows are invalid, database should remain unchanged."""
        # Arrange - insert initial data
        table = ProductTable(test_db._connection)
        initial_data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(initial_data)
        initial_state = table.get_untyped()
        
        # Act - attempt to set with one bad row (invalid barcode)
        new_data = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                "category": "Soda",
                "current_stock": 15,
                "initial_stock": 30,
            },
            {
                "barcode": 12,  # Invalid: 2 digits instead of 3
                "name": "Water",
                "price": 1.0,
                "category": "Beverage",
                "current_stock": 100,
                "initial_stock": 200,
            }
        ]
        result, bad_rows = table.set(new_data)
        
        # Assert - database should still contain original data
        assert len(bad_rows) == 1  # One row was rejected
        assert result == table.table_name  # Indicates rejection
        current_state = table.get_untyped()
        assert len(current_state) == 1
        assert current_state.iloc[0]["barcode"] == "123"  # Original data untouched

    def test_set_atomic_with_duplicate_barcode(self, test_db):
        """If duplicate barcode is detected, database should remain unchanged."""
        # Arrange - insert initial data
        table = ProductTable(test_db._connection)
        initial_data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(initial_data)
        
        # Act - attempt to set with duplicate barcode
        new_data = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                "category": "Soda",
                "current_stock": 15,
                "initial_stock": 30,
            },
            {
                "barcode": 456,  # Duplicate
                "name": "Water",
                "price": 1.0,
                "category": "Beverage",
                "current_stock": 100,
                "initial_stock": 200,
            }
        ]
        result, bad_rows = table.set(new_data)
        
        # Assert
        assert len(bad_rows) == 2  # Both duplicate barcodes marked bad
        assert result == table.table_name
        current_state = table.get_untyped()
        assert len(current_state) == 1
        assert current_state.iloc[0]["barcode"] == "123"  # Original data preserved

    def test_set_atomic_with_empty_field(self, test_db):
        """If any field is empty, database should remain unchanged."""
        # Arrange
        table = ProductTable(test_db._connection)
        initial_data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(initial_data)
        
        # Act - attempt to set with empty field
        new_data = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                "category": "Soda",
                "current_stock": 15,
                "initial_stock": 30,
            },
            {
                "barcode": 789,
                "name": "",  # Empty field
                "price": 1.0,
                "category": "Beverage",
                "current_stock": 100,
                "initial_stock": 200,
            }
        ]
        result, bad_rows = table.set(new_data)
        
        # Assert - database should still contain original data
        assert len(bad_rows) == 1
        assert result == table.table_name
        current_state = table.get_untyped()
        assert len(current_state) == 1
        assert current_state.iloc[0]["barcode"] == "123"

    def test_set_atomic_all_valid_rows_succeed(self, test_db):
        """When all rows are valid, database should be replaced."""
        # Arrange
        table = ProductTable(test_db._connection)
        initial_data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(initial_data)
        
        # Act - set with valid rows
        new_data = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                "category": "Soda",
                "current_stock": 15,
                "initial_stock": 30,
            },
            {
                "barcode": 789,
                "name": "Water",
                "price": 1.0,
                "category": "Beverage",
                "current_stock": 100,
                "initial_stock": 200,
            }
        ]
        result, bad_rows = table.set(new_data)
        
        # Assert - database should have new data
        assert result == "success"
        assert len(bad_rows) == 0
        current_state = table.get_untyped()
        assert len(current_state) == 2
        barcodes = sorted([row["barcode"] for row in current_state.to_dict("records")])
        assert barcodes == ["456", "789"]

    def test_set_atomic_mixed_valid_invalid_with_existing_data(self, test_db):
        """With existing data and mixed valid/invalid new data, preserve existing."""
        # Arrange - Multiple initial products
        table = ProductTable(test_db._connection)
        initial_data = [
            {
                "barcode": 111,
                "name": "Product A",
                "price": 10.0,
                "category": "Category1",
                "current_stock": 5,
                "initial_stock": 10,
            },
            {
                "barcode": 222,
                "name": "Product B",
                "price": 20.0,
                "category": "Category2",
                "current_stock": 3,
                "initial_stock": 5,
            }
        ]
        table.set(initial_data)
        initial_count = len(table.get_untyped())
        
        # Act - attempt to replace with mixed valid/invalid data
        new_data = [
            {
                "barcode": 333,  # Valid: 3 digits
                "name": "Product C",
                "price": 15.0,
                "category": "Category3",
                "current_stock": 20,
                "initial_stock": 25,
            },
            {
                "barcode": 34,  # Invalid: 2 digits
                "name": "Product D",
                "price": 12.0,
                "category": "Category4",
                "current_stock": 8,
                "initial_stock": 10,
            }
        ]
        result, bad_rows = table.set(new_data)
        
        # Assert - original data unchanged
        assert len(bad_rows) == 1
        assert result == table.table_name
        current_state = table.get_untyped()
        assert len(current_state) == initial_count
        barcodes = sorted([row["barcode"] for row in current_state.to_dict("records")])
        assert barcodes == ["111", "222"]

    def test_set_atomic_invalid_column_format(self, test_db):
        """If columns are invalid, database should remain unchanged."""
        # Arrange
        table = ProductTable(test_db._connection)
        initial_data = [
            {
                "barcode": 123,
                "name": "Beer",
                "price": 5.0,
                "category": "Beverage",
                "current_stock": 10,
                "initial_stock": 20,
            }
        ]
        table.set(initial_data)
        
        # Act - attempt to set with missing column
        new_data = [
            {
                "barcode": 456,
                "name": "Soda",
                "price": 3.0,
                # Missing "category" column
                "current_stock": 15,
                "initial_stock": 30,
            }
        ]
        result, bad_rows = table.set(new_data)
        
        # Assert - database should still contain original data
        assert len(bad_rows) == 1
        assert result == table.table_name
        current_state = table.get_untyped()
        assert len(current_state) == 1
        assert current_state.iloc[0]["barcode"] == "123"


def _product_row(barcode, name):
    return {
        "barcode": barcode, "name": name, "price": 5.0, "category": "Drinks",
        "current_stock": 10, "initial_stock": 20,
    }


@pytest.mark.parametrize("operation", ["set", "append"])
@pytest.mark.parametrize("names", [("Cola", "Cola"), (123, "123")], ids=["same-name", "same-stored-name"])
def test_duplicate_product_names_reject_batch_and_preserve_database_and_cache(test_db, operation, names):
    table = test_db._product_table
    table.set([_product_row(123, "Beer")])
    before = table.get_untyped()
    rows = [_product_row(456, names[0]), _product_row(789, names[1])]

    result, bad_rows = getattr(table, operation)(rows)

    assert result == "prods"
    assert bad_rows == rows
    pd.testing.assert_frame_equal(table.get_untyped(), before)
    stored_rows = test_db._connection.get_query("SELECT * FROM prods", list(before.columns))
    pd.testing.assert_frame_equal(stored_rows, before)


def test_appending_existing_product_name_rejects_entire_batch_and_preserves_data(test_db):
    table = test_db._product_table
    table.set([_product_row(123, "Beer")])
    before = table.get_untyped()
    rows = [_product_row(456, "Cola"), _product_row(789, "Beer")]

    result, bad_rows = table.append(rows)

    assert result == "prods"
    assert bad_rows == [rows[1]]
    pd.testing.assert_frame_equal(table.get_untyped(), before)
    stored_rows = test_db._connection.get_query("SELECT * FROM prods", list(before.columns))
    pd.testing.assert_frame_equal(stored_rows, before)
