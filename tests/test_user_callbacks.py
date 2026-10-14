import pytest
import pandas as pd
from unittest.mock import patch
from dash import no_update
from src.container import Container
from src.database.data_connection import Database, get_users, get_trans, upload_values, add_transactions
from src.tables.user_callbacks import add_row, validate_barcode_user, open_user_modal


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestValidateBarcodUser:

    def test_validate_barcode_user_rejects_none(self, test_db):
        # Arrange & Act
        result = validate_barcode_user(None, None)
        # Assert
        assert result is True

    def test_validate_barcode_user_rejects_non_digit(self, test_db):
        # Arrange & Act
        result = validate_barcode_user("abc", None)
        # Assert
        assert result is True

    def test_validate_barcode_user_rejects_less_than_4_digits(self, test_db):
        # Arrange & Act
        result = validate_barcode_user("123", None)
        # Assert
        assert result is True

    def test_validate_barcode_user_accepts_valid_barcode(self, test_db):
        # Arrange & Act
        result = validate_barcode_user("1234", None)
        # Assert
        assert result is False

    def test_validate_barcode_user_rejects_duplicate_barcode(self, test_db):
        # Arrange
        user_data = pd.DataFrame([
            {"barcode": 1500, "name": "John", "rank": "Admin", "team": "Team A", "is_guest": 0}
        ])
        upload_values(user_data, "users")
        
        # Act
        result = validate_barcode_user("1500", None)
        
        # Assert
        assert result is True

    def test_validate_barcode_user_allows_duplicate_when_editing_same(self, test_db):
        # Arrange
        user_data = pd.DataFrame([
            {"barcode": 1500, "name": "John", "rank": "Admin", "team": "Team A", "is_guest": 0}
        ])
        upload_values(user_data, "users")
        
        # Act
        result = validate_barcode_user("1500", "1500")
        
        # Assert
        assert result is False


class TestUserCallbacksAddRow:

    def test_add_row_creates_new_user(self, test_db):
        # Arrange
        vals = [1234, "Alice", "User", "Team B", 0]
        
        # Act
        result, edit_value = add_row(1, vals, None)
        
        # Assert
        users = get_users()
        assert len(users) == 1
        assert users.iloc[0]["barcode"] == "1234"
        assert users.iloc[0]["name"] == "Alice"

    def test_add_row_with_edit_replaces_existing_user(self, test_db):
        # Arrange
        user_data = pd.DataFrame([
            {"barcode": 1500, "name": "Old User", "rank": "Admin", "team": "Team A", "is_guest": 0}
        ])
        upload_values(user_data, "users")
        vals = [1600, "New User", "User", "Team B", 0]
        
        # Act
        result, edit_value = add_row(1, vals, 1500)
        
        # Assert
        users = get_users()
        assert len(users) == 1
        assert users.iloc[0]["barcode"] == "1600"
        assert users.iloc[0]["name"] == "New User"

    def test_add_row_records_paid_amount_in_cents(self, test_db):
        # Arrange
        vals = [1234, "Alice", "User", "Team B", 0, 12.5]

        # Act
        add_row(1, vals, None)

        # Assert
        users = get_users()
        assert users.iloc[0]["paid_cents"] == "1250"

    def test_add_row_edit_preserves_paid_amount_when_field_missing(self, test_db):
        # Arrange
        upload_values(
            pd.DataFrame([
                {
                    "barcode": 1500,
                    "name": "Old User",
                    "rank": "Admin",
                    "team": "Team A",
                    "is_guest": 0,
                    "paid_cents": 2500,
                }
            ]),
            "users",
        )
        vals = [1600, "New User", "User", "Team B", 0]

        # Act
        add_row(1, vals, 1500)

        # Assert
        users = get_users()
        assert users.iloc[0]["paid_cents"] == "2500"

    def test_add_row_edit_updates_paid_amount_in_cents(self, test_db):
        # Arrange
        upload_values(
            pd.DataFrame([
                {
                    "barcode": 1500,
                    "name": "Old User",
                    "rank": "Admin",
                    "team": "Team A",
                    "is_guest": 0,
                    "paid_cents": 2500,
                }
            ]),
            "users",
        )
        vals = [1600, "New User", "User", "Team B", 0, 30]

        # Act
        add_row(1, vals, 1500)

        # Assert
        users = get_users()
        assert users.iloc[0]["paid_cents"] == "3000"

    def test_add_row_edit_can_set_paid_for_user_with_existing_transactions(self, test_db):
        # Arrange
        upload_values(
            pd.DataFrame([
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 5.0,
                    "category": "Beverage",
                    "current_stock": 10,
                    "initial_stock": 20,
                }
            ]),
            "prods",
        )
        upload_values(
            pd.DataFrame([
                {
                    "barcode": 1500,
                    "name": "John",
                    "rank": "Member",
                    "team": "A",
                    "is_guest": 0,
                }
            ]),
            "users",
        )
        add_transactions(
            pd.DataFrame(
                [
                    {
                        "barcode_user": "1500",
                        "barcode_prod": "123",
                        "timestamp": "2024-01-01 12:00:00",
                    }
                ]
            )
        )
        vals = [1500, "John", "Member", "A", 0, 10]

        # Act
        add_row(1, vals, 1500)

        # Assert
        users = get_users()
        trans = get_trans()
        assert users.iloc[0]["paid_cents"] == "1000"
        assert trans.iloc[0]["barcode_user"] == "1500"

    def test_add_row_no_cascade_on_new_user(self, test_db):
        # Arrange
        upload_values(
            pd.DataFrame([
                {"barcode": 123, "name": "Beer", "price": 5.0, "category": "Beverage", "current_stock": 10, "initial_stock": 20}
            ]),
            "prods",
        )
        upload_values(
            pd.DataFrame([
                {"barcode": 1500, "name": "John", "rank": "Member", "team": "A", "is_guest": 0}
            ]),
            "users",
        )
        trans_data = [
            {"barcode_user": "1500", "barcode_prod": "123", "timestamp": "2024-01-01 12:00:00"}
        ]
        add_transactions(pd.DataFrame(trans_data))
        vals = [1234, "Alice", "User", "Team B", 0]
        
        # Act
        result, edit_value = add_row(1, vals, None)
        
        # Assert
        trans = get_trans()
        assert trans.iloc[0]["barcode_user"] == "1500"

    def test_add_row_with_n_clicks_none_returns_no_update(self, test_db):
        # Arrange
        vals = [1234, "Alice", "User", "Team B", 0]
        
        # Act
        result, edit_value = add_row(None, vals, None)
        
        # Assert
        assert result is no_update

    def test_add_row_returns_updated_user_table(self, test_db):
        # Arrange
        vals = [1234, "Alice", "User", "Team B", 0]
        
        # Act
        result, edit_value = add_row(1, vals, None)
        
        # Assert
        assert isinstance(result, list)
        assert len(result) == 1


class TestOpenUserModal:

    @patch('src.tables.user_callbacks.ctx')
    def test_open_user_modal_generates_next_barcode(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "new_user_btn"
        test_db._user_table.set(pd.DataFrame([
            {"barcode": 1600, "name": "John", "rank": "Admin", "team": "Team A", "is_guest": 0}
        ]))

        # Act
        is_open, barcode = open_user_modal(1, 0, 0)
        
        # Assert
        assert is_open is True
        assert barcode == 1601

    @patch('src.tables.user_callbacks.ctx')
    def test_open_user_modal_default_barcode_when_empty(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "new_user_btn"
        
        # Act
        is_open, barcode = open_user_modal(1, 0, 0)
        
        # Assert
        assert is_open is True
        assert barcode == 1000

    @patch('src.tables.user_callbacks.ctx')
    def test_open_user_modal_closes_on_confirm(self, mock_ctx, test_db):
        # Arrange
        mock_ctx.triggered_id = "confirm_user"
        
        # Act
        is_open, barcode = open_user_modal(0, 1, 0)
        
        # Assert
        assert is_open is False
