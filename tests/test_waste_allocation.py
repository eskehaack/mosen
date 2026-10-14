import base64
import io
import pandas as pd
import pytest
import types

from src.analytics.product_calculations import get_waste_table
from src.analytics.trans_calculations import (
    get_income,
    get_preview_user_waste_cents,
)
from src.analytics.waste_allocation import allocate_waste, get_strategy_options
from src.container import Container
from src.database.data_connection import (
    Database,
    add_transactions,
    get_last_stock_update_at,
    get_waste_cents,
    update_values,
    upload_values,
)
from src.tables.prod_callbacks import confirm_new_stock
from src.tables.user_callbacks import add_row
from src import main_page_callbacks
from src import main_layout


@pytest.fixture
def test_db(tmp_path):
    db = Database(str(tmp_path / "waste.db"))
    Container.set(Database, db)
    yield db
    Container.reset()


def add_users(users):
    upload_values(pd.DataFrame(users), "users")


def read_downloaded_excel(download):
    data = base64.b64decode(download["content"])
    return pd.read_excel(io.BytesIO(data))


def add_product(current_stock=7):
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 2.5,
                    "category": "Beverage",
                    "current_stock": current_stock,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )


def add_sales(barcodes):
    if not barcodes:
        return
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": barcode,
                    "barcode_prod": 123,
                    "timestamp": f"2026-01-01 10:00:0{index}",
                }
                for index, barcode in enumerate(barcodes)
            ]
        )
    )


def _find_component_by_id(component, target_id):
    if getattr(component, "id", None) == target_id:
        return component

    children = getattr(component, "children", None)
    if children is None:
        return None
    if not isinstance(children, (list, tuple)):
        children = [children]

    for child in children:
        found = _find_component_by_id(child, target_id)
        if found is not None:
            return found
    return None

def test_settings_dropdown_uses_strategy_options_with_hover_titles(test_db):
    layout = main_layout.settings_settings_layout()

    dropdown = _find_component_by_id(layout, "waste_strategy")

    assert dropdown is not None
    assert dropdown.options == get_strategy_options()


def test_equal_active_includes_guests_and_rounds_up(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 1},
            {"barcode": 1002, "name": "C", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    add_sales([1000, 1001])
    update_values(waste_strategy="equal_active")

    allocate_waste(test_db)

    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 250
    assert users.loc[1000, "waste_cents"] == 200
    assert users.loc[1001, "waste_cents"] == 200
    assert users.loc[1002, "waste_cents"] == 0


def test_equal_active_falls_back_to_equal_all(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    update_values(waste_strategy="equal_active")

    allocate_waste(test_db)

    assert get_waste_cents() == 750
    assert test_db._user_table.get()["waste_cents"].tolist() == [400, 400]


def test_settlement_with_no_users_still_stores_raw_waste(test_db):
    add_product()
    update_values(waste_strategy="equal_active")

    allocate_waste(test_db)

    assert get_waste_cents() == 750
    assert len(test_db._user_table.get()) == 0


def test_negative_calculated_waste_is_clamped_to_zero(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product(current_stock=10)
    add_sales([1000])
    update_values(waste_strategy="equal_active")

    allocate_waste(test_db)

    assert get_waste_cents() == 0
    assert test_db._user_table.get().iloc[0]["waste_cents"] == 0


def test_equal_all_charges_users_without_purchases(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    add_sales([1000])
    update_values(waste_strategy="equal_all")

    allocate_waste(test_db)

    assert test_db._user_table.get()["waste_cents"].tolist() == [300, 300]


def test_strategy_change_does_not_recalculate(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    allocate_waste(test_db)
    before = test_db._user_table.get()["waste_cents"].tolist()

    update_values(waste_strategy="equal_all")

    assert test_db._user_table.get()["waste_cents"].tolist() == before


def test_stock_confirmation_replaces_allocations(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product(current_stock=9)
    allocate_waste(test_db)
    assert test_db._user_table.get().iloc[0]["waste_cents"] == 300

    confirm_new_stock([7])

    assert test_db._user_table.get().iloc[0]["waste_cents"] == 800
    assert get_waste_cents() == 750


def test_new_user_uses_preview_fallback_and_edit_preserves_waste(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": 600,
            }
        ]
    )
    update_values(waste_cents=600)
    add_row(1, [1001, "B", "R", "T", 0], None)
    users = test_db._user_table.get()
    new_user = users[users["barcode"] == 1001].iloc[0]
    assert new_user["waste_cents"] == -1
    assert get_preview_user_waste_cents(new_user, 600, len(users)) == 450

    add_row(1, [2000, "A", "R", "T", 0], 1000)
    edited = test_db._user_table.get()
    edited = edited[edited["barcode"] == 2000].iloc[0]
    assert edited["waste_cents"] == 600


def test_admin_income_does_not_use_preview_fallback(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": -1,
            }
        ]
    )
    update_values(waste_cents=600)

    income = get_income()[0]

    assert income["waste"] is None
    assert income["price"] == income["purchases"]


def test_user_import_defaults_paid_cents_to_zero(test_db):
    # Arrange
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )

    # Act
    user = test_db._user_table.get().iloc[0]

    # Assert
    assert user["paid_cents"] == 0


def test_settled_user_transaction_import_is_allowed(test_db):
    # Arrange
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 100,
            }
        ]
    )
    add_product()

    # Act
    result, bad_rows = add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": 1000,
                    "barcode_prod": 123,
                    "timestamp": "2026-01-01 10:00:00",
                }
            ]
        )
    )

    # Assert
    assert result == "success"
    assert bad_rows == []
    assert len(test_db._transaction_table.get()) == 1


def test_settled_prepaid_waste_is_subtracted_before_equal_split(test_db):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 5,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 300,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    update_values(waste_strategy="equal_all")

    # Act
    allocate_waste(test_db)

    # Assert
    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 400
    assert users.loc[1000, "waste_cents"] == 200
    assert users.loc[1001, "waste_cents"] == 200


def test_equal_active_excludes_settled_active_purchasers(test_db):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 6,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000, 1001])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 200,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    update_values(waste_strategy="equal_active")

    # Act
    allocate_waste(test_db)

    # Assert
    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 400
    assert users.loc[1000, "waste_cents"] == 100
    assert users.loc[1001, "waste_cents"] == 300


def test_category_strategy_excludes_settled_category_purchasers(test_db):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 6,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000, 1001])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 200,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )

    # Act
    allocate_waste(test_db)

    # Assert
    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 400
    assert users.loc[1000, "waste_cents"] == 100
    assert users.loc[1001, "waste_cents"] == 300


def test_settled_prepaid_waste_is_recomputed_when_prices_change(test_db):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 5,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 300,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    update_values(waste_strategy="equal_all")

    # Act
    allocate_waste(test_db)
    users = test_db._user_table.get().set_index("barcode")

    # Assert
    assert users.loc[1000, "waste_cents"] == 200
    assert users.loc[1001, "waste_cents"] == 200

    # Arrange
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 2,
                    "category": "Beverage",
                    "current_stock": 5,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )

    # Act
    allocate_waste(test_db)

    # Assert
    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 800
    assert users.loc[1000, "waste_cents"] == 100
    assert users.loc[1001, "waste_cents"] == 700


def test_settled_prepaid_waste_can_cover_all_waste(test_db):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 5,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 1000,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    update_values(waste_strategy="equal_all")

    # Act
    allocate_waste(test_db)

    # Assert
    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 400
    assert users.loc[1000, "waste_cents"] == 900
    assert users.loc[1001, "waste_cents"] == 0


def test_settled_payment_below_purchases_has_no_prepaid_waste(test_db):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 6,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000, 1001])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 50,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    update_values(waste_strategy="equal_all")

    # Act
    allocate_waste(test_db)

    # Assert
    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 400
    assert users.loc[1000, "waste_cents"] == 0
    assert users.loc[1001, "waste_cents"] == 400


def test_settled_prepaid_waste_must_cover_total_waste_when_no_one_can_be_charged(test_db):
    # Arrange
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 5,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 300,
            }
        ]
    )
    update_values(waste_strategy="equal_all")

    # Act / Assert
    with pytest.raises(ValueError, match="did not cover"):
        allocate_waste(test_db)


def test_settled_user_has_zero_remaining_income(test_db):
    # Arrange
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 5,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 500,
            }
        ]
    )

    # Act
    allocate_waste(test_db)
    income = get_income()[0]

    # Assert
    assert income["paid"] == 5
    assert income["price"] == 0


def test_payment_export_added_income_ignores_settled_users(test_db, monkeypatch):
    # Arrange
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 5,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000, 1001])
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "paid_cents": 300,
            },
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    update_values(
        waste_strategy="equal_all",
        last_stock_update_at="2026-01-01 10:01:00",
    )
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    # Act
    result = main_page_callbacks.control_payments_modal(
        None, 1, 10, []
    )

    # Assert
    income = read_downloaded_excel(result[1]).set_index("barcode")
    assert result[0] is False
    assert income.loc[1000, "price"] == 0
    assert income.loc[1001, "price"] == 12


def test_payment_export_shares_added_income_only_between_buyers_with_amounts_due(
    test_db, monkeypatch
):
    # Arrange: two eligible buyers (including a guest), a non-buyer and a settled buyer.
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T"},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 1},
            {"barcode": 1002, "name": "C", "rank": "R", "team": "T"},
            {"barcode": 1003, "name": "D", "rank": "R", "team": "T", "paid_cents": 250},
        ]
    )
    upload_values(
        pd.DataFrame(
            [{
                "barcode": 123, "name": "Beer", "price": 2.5,
                "category": "Beverage", "current_stock": 0, "initial_stock": 4,
            }]
        ),
        "prods",
    )
    add_sales([1000, 1001, 1003])
    update_values(
        waste_strategy="equal_all",
        last_stock_update_at="2026-01-01 10:01:00",
    )
    monkeypatch.setattr(
        main_page_callbacks, "ctx", types.SimpleNamespace(triggered_id="confirm_payments")
    )

    # Act
    result = main_page_callbacks.control_payments_modal(None, 1, 0.5, [])

    # Assert: waste still rounds up separately; only the two eligible buyers share 0.50.
    income = read_downloaded_excel(result[1]).set_index("barcode")
    assert result[0] is False
    assert result[2] is main_page_callbacks.no_update
    assert income["waste"].to_dict() == {1000: 1, 1001: 1, 1002: 1, 1003: 0}
    assert income["price"].to_dict() == {1000: 3.75, 1001: 3.75, 1002: 1, 1003: 0}
    assert test_db._user_table.get()["waste_cents"].tolist() == [100, 100, 100, 0]


@pytest.mark.parametrize("price", [20, 12.5])
def test_payment_export_uses_excel_file_without_rounding(test_db, monkeypatch, price):
    # Arrange
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": price,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 1,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000])
    update_values(
        waste_strategy="equal_all",
        last_stock_update_at="2026-01-01 10:01:00",
    )
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    # Act
    result = main_page_callbacks.control_payments_modal(
        None, 1, 0, []
    )

    # Assert
    download = result[1]
    assert download["filename"] == "swamp_machine_payments.xlsx"
    assert download["base64"] is True
    income = read_downloaded_excel(download).set_index("barcode")
    assert income.loc[1000, "purchases"] == price
    assert income.loc[1000, "price"] == price
    assert result[2] is main_page_callbacks.no_update




def test_category_strategy_is_default_for_new_databases(test_db):
    assert (
        test_db.settings.iloc[0]["waste_strategy"]
        == "equal_category_purchasers"
    )


def test_existing_strategy_selection_is_preserved(test_db):
    update_values(waste_strategy="equal_all")

    test_db._settings_table.ensure_defaults()

    assert test_db.settings.iloc[0]["waste_strategy"] == "equal_all"


def test_category_strategy_aggregates_before_rounding(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 3,
                },
                {
                    "barcode": 124,
                    "name": "Chips",
                    "price": 1,
                    "category": "Snacks",
                    "current_stock": 0,
                    "initial_stock": 3,
                },
            ]
        ),
        "prods",
    )
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": user,
                    "barcode_prod": product,
                    "timestamp": f"2026-01-01 10:00:0{index}",
                }
                for index, (user, product) in enumerate(
                    [(1000, 123), (1001, 123), (1000, 124), (1001, 124)]
                )
            ]
        )
    )

    allocate_waste(test_db)

    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 200
    assert users.loc[1000, "waste_cents"] == 100
    assert users.loc[1001, "waste_cents"] == 100


def test_category_strategy_ignores_purchase_quantity(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 0,
                    "initial_stock": 6,
                }
            ]
        ),
        "prods",
    )
    add_sales([1000, 1000, 1001])

    allocate_waste(test_db)

    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 300
    assert users.loc[1000, "waste_cents"] == 200
    assert users.loc[1001, "waste_cents"] == 200


def test_category_without_purchases_falls_back_to_active_users(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 2,
                    "initial_stock": 3,
                },
                {
                    "barcode": 124,
                    "name": "Chips",
                    "price": 1,
                    "category": "Snacks",
                    "current_stock": 2,
                    "initial_stock": 3,
                },
            ]
        ),
        "prods",
    )
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": 1000,
                    "barcode_prod": 124,
                    "timestamp": "2026-01-01 10:00:00",
                }
            ]
        )
    )

    allocate_waste(test_db)

    users = test_db._user_table.get().set_index("barcode")
    assert users.loc[1000, "waste_cents"] == 100
    assert users.loc[1001, "waste_cents"] == 0


def test_category_without_active_users_falls_back_to_all_users(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product(current_stock=9)

    allocate_waste(test_db)

    assert test_db._user_table.get()["waste_cents"].tolist() == [200, 200]


def test_category_strategy_distributes_globally_netted_waste(test_db):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": "Beer",
                    "price": 1,
                    "category": "Beverage",
                    "current_stock": 3,
                    "initial_stock": 10,
                },
                {
                    "barcode": 124,
                    "name": "Chips",
                    "price": 1,
                    "category": "Snacks",
                    "current_stock": 5,
                    "initial_stock": 10,
                },
                {
                    "barcode": 125,
                    "name": "Water",
                    "price": 1,
                    "category": "Water",
                    "current_stock": 12,
                    "initial_stock": 10,
                },
            ]
        ),
        "prods",
    )
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": 1000,
                    "barcode_prod": 123,
                    "timestamp": "2026-01-01 10:00:00",
                },
                {
                    "barcode_user": 1001,
                    "barcode_prod": 124,
                    "timestamp": "2026-01-01 10:00:01",
                },
            ]
        )
    )

    allocate_waste(test_db)

    users = test_db._user_table.get().set_index("barcode")
    assert get_waste_cents() == 800
    assert users.loc[1000, "waste_cents"] == 500
    assert users.loc[1001, "waste_cents"] == 400


def test_product_waste_table_remains_live(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    before = get_waste_table()

    add_sales([1000])

    after = get_waste_table()
    assert before[0]["Waste"] == 3
    assert after[0]["Waste"] == 2


def test_payment_export_persists_fresh_allocations(test_db, monkeypatch):
    add_users(
        [
            {"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0},
            {"barcode": 1001, "name": "B", "rank": "R", "team": "T", "is_guest": 0},
        ]
    )
    add_product()
    add_sales([1000])
    update_values(
        waste_strategy="equal_all",
        last_stock_update_at="2026-01-01 10:01:00",
    )
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, 1, 0, []
    )

    assert result[0] is False
    assert test_db._user_table.get()["waste_cents"].tolist() == [300, 300]


def test_payment_export_requires_stock_update(test_db, monkeypatch):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    add_sales([1000])
    update_values(waste_strategy="equal_all")
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, 1, 0, []
    )

    assert result[1] is main_page_callbacks.no_update
    assert "Update stock before exporting payments" in result[2][0]["msg"]


def test_payment_export_requires_stock_after_latest_purchase(test_db, monkeypatch):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    add_sales([1000])
    update_values(
        waste_strategy="equal_all",
        last_stock_update_at="2026-01-01 09:59:00",
    )
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, 1, 0, []
    )

    assert result[1] is main_page_callbacks.no_update
    assert "Update stock after the latest purchase" in result[2][0]["msg"]


def test_payment_export_warns_but_creates_file_for_unparseable_timestamps(
    test_db, monkeypatch
):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product()
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": 1000,
                    "barcode_prod": 123,
                    "timestamp": "not a timestamp",
                }
            ]
        )
    )
    update_values(
        waste_strategy="equal_all",
        last_stock_update_at="2026-01-01 10:01:00",
    )
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )

    result = main_page_callbacks.control_payments_modal(
        None, 1, 0, []
    )

    assert result[0] is False
    assert result[1]["filename"] == "swamp_machine_payments.xlsx"
    assert "timestamps could not be checked" in result[2][0]["msg"]


def test_stock_confirmation_records_timestamp(test_db):
    add_users(
        [{"barcode": 1000, "name": "A", "rank": "R", "team": "T", "is_guest": 0}]
    )
    add_product(current_stock=9)

    confirm_new_stock([7])

    assert get_last_stock_update_at() != ""


def test_bill_preview_default_extra_percent_increases_stored_waste(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": 200,
            }
        ]
    )
    user = test_db._user_table.get().iloc[0]

    waste = get_preview_user_waste_cents(user, 200, 1)

    assert waste == pytest.approx(300)


def test_bill_preview_zero_extra_percent_preserves_base_waste(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": 200,
            }
        ]
    )
    update_values(bill_preview_waste_extra_percent=0)
    user = test_db._user_table.get().iloc[0]

    assert get_preview_user_waste_cents(user, 200, 1) == 200


def test_bill_preview_custom_extra_percent_is_applied(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": 200,
            }
        ]
    )
    update_values(bill_preview_waste_extra_percent=25)
    user = test_db._user_table.get().iloc[0]

    assert get_preview_user_waste_cents(user, 200, 1) == 250


def test_bill_preview_extra_percent_applies_to_fallback_share(test_db):
    add_users(
        [
            {
                "barcode": 1000,
                "name": "A",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": -1,
            },
            {
                "barcode": 1001,
                "name": "B",
                "rank": "R",
                "team": "T",
                "is_guest": 0,
                "waste_cents": 600,
            },
        ]
    )
    update_values(waste_cents=600)
    user = test_db._user_table.get()
    user = user[user["barcode"] == 1000].iloc[0]

    assert get_preview_user_waste_cents(user, 600, 2) == 450


def test_payment_confirmation_refreshes_economy_layout(monkeypatch):
    monkeypatch.setattr(
        main_layout,
        "ctx",
        types.SimpleNamespace(triggered_id="confirm_payments"),
    )
    monkeypatch.setattr(main_layout.time, "sleep", lambda _: None)
    marker = object()
    monkeypatch.setattr(main_layout, "user_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "product_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "transaction_settings_layout", lambda: marker)

    result = main_layout.update_settings_layout(None, False, None, None, None, None, 1)

    assert result == (marker, marker, marker)


def test_settings_modal_open_refreshes_settings_layouts(monkeypatch):
    monkeypatch.setattr(
        main_layout,
        "ctx",
        types.SimpleNamespace(triggered_id="settings_modal"),
    )
    marker = object()
    monkeypatch.setattr(main_layout, "user_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "product_settings_layout", lambda: marker)
    monkeypatch.setattr(main_layout, "transaction_settings_layout", lambda: marker)

    result = main_layout.update_settings_layout(None, True, None, None, None, None, None)

    assert result == (marker, marker, marker)
