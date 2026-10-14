"""Tests for the Column-based table system."""
import pytest
import pandas as pd
from src.container import Container
from src.database.data_connection import Database
from src.database.tables.column import Column
from src.database.tables.product import ProductTable
from src.database.tables.user import UserTable
from src.barcode import BarcodePartition


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()



class TestValidateColumns:
    """Test column validation logic."""

    def test_validate_columns_accepts_all_columns(self, test_db):
        table = ProductTable(test_db._connection)
        row = {
            "barcode": "100",
            "name": "Widget",
            "price": "9.99",
            "category": "Electronics",
            "current_stock": "50",
            "initial_stock": "100"
        }
        assert table.validate_columns(row) == True

    def test_validate_columns_rejects_invalid_column(self, test_db):
        table = ProductTable(test_db._connection)
        row = {
            "barcode": "100",
            "name": "Widget",
            "price": "9.99",
            "category": "Electronics",
            "current_stock": "50",
            "initial_stock": "100",
            "invalid_column": "should reject"
        }
        assert table.validate_columns(row) == False

    def test_validate_columns_rejects_missing_required(self, test_db):
        table = ProductTable(test_db._connection)
        row = {
            "barcode": "100",
            "name": "Widget",
            "price": "9.99",
            "current_stock": "50",
            "initial_stock": "100"
        }
        assert table.validate_columns(row) == False

    def test_validate_columns_accepts_missing_optional(self, test_db):
        """Test that missing optional columns are accepted by validate_columns."""
        table = UserTable(test_db._connection)
        row = {
            "barcode": "1001",
            "name": "Alice",
            "rank": "Manager",
            "team": "Sales"
        }
        assert table.validate_columns(row) == True


class TestOptionalColumnFilling:
    """Test that optional columns are auto-filled with defaults."""

    def test_set_fills_missing_optional_column(self, test_db):
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1001",
                "name": "Alice",
                "rank": "Manager",
                "team": "Sales"
                # is_guest not provided
            }
        ]
        
        result, bad_rows = table.set(data)
        assert result == "success"
        assert len(bad_rows) == 0
        
        # Verify is_guest was filled with default
        df = table.get()
        assert len(df) == 1
        assert df.iloc[0]["is_guest"] == 0
        assert df.iloc[0]["paid_cents"] == 0

    def test_set_preserves_explicit_optional_value(self, test_db):
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1001",
                "name": "Alice",
                "rank": "Manager",
                "team": "Sales",
                "is_guest": 1  # Explicitly set
            }
        ]
        
        result, bad_rows = table.set(data)
        assert result == "success"
        
        df = table.get()
        assert df.iloc[0]["is_guest"] == 1 or df.iloc[0]["is_guest"] == "1"


class TestColumnIntegration:
    """Integration tests for the Column system."""

    def test_product_table_columns_are_column_objects(self):
        assert all(isinstance(col, Column) for col in ProductTable.columns)
        assert len(ProductTable.columns) == 6

    def test_product_table_barcode_is_primary_key(self):
        barcode = next(col for col in ProductTable.columns if col.name == "barcode")
        assert barcode.is_primary_key == True

    def test_user_table_has_optional_is_guest(self):
        is_guest = next(col for col in UserTable.columns if col.name == "is_guest")
        assert is_guest.required == False
        assert is_guest.default == 0

    def test_user_table_has_optional_paid_cents(self):
        paid_cents = next(col for col in UserTable.columns if col.name == "paid_cents")
        assert paid_cents.required == False
        assert paid_cents.default == 0

    def test_get_returns_correct_column_names(self, test_db):
        table = ProductTable(test_db._connection)
        df = table.get()
        expected_cols = [col.name for col in ProductTable.columns]
        assert list(df.columns) == expected_cols

    def test_get_typed_uses_column_dtypes(self, test_db):
        table = ProductTable(test_db._connection)
        data = [
            {
                "barcode": "100",
                "name": "Widget",
                "price": "9.99",
                "category": "Electronics",
                "current_stock": "50",
                "initial_stock": "100"
            }
        ]
        table.set(data)
        
        df_typed = table.get()
        assert df_typed["barcode"].dtype == int
        assert df_typed["price"].dtype == float
        assert df_typed["current_stock"].dtype == int


class TestBarcodePartitions:
    def test_partitions_do_not_overlap(self):
        partitions = list(BarcodePartition)
        for index, left in enumerate(partitions):
            for right in partitions[index + 1:]:
                assert left.maximum < right.minimum or right.maximum < left.minimum

    def test_enum_has_no_aliases(self):
        members = BarcodePartition.__members__
        for name, member in members.items():
            assert name == member.name, f"Enum alias detected: {name} -> {member.name}"


class TestEmptyValueHandling:
    """Test empty value handling for required and optional columns."""

    def test_required_empty_string_is_rejected(self, test_db):
        """Required column with empty string should be rejected."""
        # Arrange
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1001",
                "name": "",  # Empty required column
                "rank": "Manager",
                "team": "Sales"
            }
        ]

        # Act
        result, bad_rows = table.set(data)

        # Assert
        assert result == "users"
        assert len(bad_rows) == 1
        assert bad_rows[0]["name"] == ""

    def test_required_none_is_rejected(self, test_db):
        """Required column with None should be rejected."""
        # Arrange
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1002",
                "name": None,  # None required column
                "rank": "Manager",
                "team": "Sales"
            }
        ]

        # Act
        result, bad_rows = table.set(data)

        # Assert
        assert result == "users"
        assert len(bad_rows) == 1
        assert bad_rows[0]["name"] is None

    def test_optional_empty_string_uses_default(self, test_db):
        """Optional column with empty string should use default value."""
        # Arrange
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1003",
                "name": "Bob",
                "rank": "Manager",
                "team": "Sales",
                "is_guest": ""  # Empty optional column
            }
        ]

        # Act
        result, bad_rows = table.set(data)

        # Assert
        assert result == "success"
        assert len(bad_rows) == 0
        df = table.get_untyped()
        assert len(df) == 1
        assert df.iloc[0]["is_guest"] == "0"

    def test_optional_none_uses_default(self, test_db):
        """Optional column with None should use default value."""
        # Arrange
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1004",
                "name": "Charlie",
                "rank": "Manager",
                "team": "Sales",
                "is_guest": None  # None optional column
            }
        ]

        # Act
        result, bad_rows = table.set(data)

        # Assert
        assert result == "success"
        assert len(bad_rows) == 0
        df = table.get_untyped()
        assert len(df) == 1
        assert df.iloc[0]["is_guest"] == "0"

    def test_mixed_empty_values_in_batch(self, test_db):
        """Batch with mixed empty values: some rows valid, some invalid."""
        # Arrange
        table = UserTable(test_db._connection)
        data = [
            {
                "barcode": "1005",
                "name": "Diana",
                "rank": "Manager",
                "team": "Sales",
                "is_guest": ""
            },
            {
                "barcode": "1006",
                "name": "",
                "rank": "Manager",
                "team": "Sales",
                "is_guest": "1"
            }
        ]

        # Act
        result, bad_rows = table.set(data)

        # Assert
        assert result == "users"
        assert len(bad_rows) == 1
        assert bad_rows[0]["name"] == ""


class TestCompositeKeyLogic:
    """Test composite primary key logic with actual composite keys."""
    
    @pytest.fixture
    def composite_table(self, test_db):
        """Create a test table with composite primary key (col1, col2)."""
        from src.database.tables.base_table import BaseTable
        
        class OrderLineTable(BaseTable):
            table_name = "order_lines"
            columns = [
                Column("order_id", int, required=True, is_primary_key=True),
                Column("line_no", int, required=True, is_primary_key=True),
                Column("product", str, required=True),
                Column("qty", int, required=True),
            ]
            create_sql = """
                CREATE TABLE order_lines (
                    order_id INT,
                    line_no INT,
                    product TEXT,
                    qty INT,
                    PRIMARY KEY (order_id, line_no)
                )
            """
        
        return OrderLineTable(test_db._connection)

    def test_composite_pk_allows_same_col1_different_col2(self, composite_table):
        """Same value in col1 OK if col2 differs - unique composite key."""
        # Arrange
        data = [
            {"order_id": "100", "line_no": "1", "product": "Beer", "qty": "10"},
            {"order_id": "100", "line_no": "2", "product": "Soda", "qty": "5"},   # Same order_id, different line_no
        ]

        # Act
        result, bad_rows = composite_table.set(data)

        # Assert - both valid because (100,1) and (100,2) are unique combos
        assert result == "success"
        assert len(bad_rows) == 0
        assert len(composite_table.get()) == 2

    def test_composite_pk_rejects_duplicate_combo(self, composite_table):
        """Rejects only when entire (col1, col2) combo duplicated."""
        # Arrange
        data = [
            {"order_id": "100", "line_no": "1", "product": "Beer", "qty": "10"},
            {"order_id": "100", "line_no": "1", "product": "Different", "qty": "20"},  # Duplicate combo
        ]

        # Act
        result, bad_rows = composite_table.set(data)

        # Assert - both rows with same combo marked bad
        assert result == "order_lines"
        assert len(bad_rows) == 2
        assert bad_rows[0]["order_id"] == "100"
        assert bad_rows[0]["line_no"] == "1"
        assert bad_rows[1]["order_id"] == "100"
        assert bad_rows[1]["line_no"] == "1"

    def test_composite_pk_mixed_valid_invalid(self, composite_table):
        """Batch with mix of unique and duplicate combos - all valid ones accepted."""
        # Arrange
        data = [
            {"order_id": "100", "line_no": "1", "product": "Beer", "qty": "10"},      # Is duplicated
            {"order_id": "100", "line_no": "2", "product": "Soda", "qty": "5"},       # Valid (different line)
            {"order_id": "200", "line_no": "1", "product": "Wine", "qty": "3"},       # Valid (different order)
            {"order_id": "100", "line_no": "1", "product": "Spam", "qty": "1"},       # Duplicate of first
        ]

        # Act
        result, bad_rows = composite_table.set(data)

        # Assert - only the duplicate rejected
        assert result == "order_lines"
        assert len(bad_rows) == 2
        assert bad_rows[0] == data[0]
        assert bad_rows[1] == data[-1]
