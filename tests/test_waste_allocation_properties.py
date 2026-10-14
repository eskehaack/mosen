import pandas as pd
import pytest

from property_helpers import property_context, property_rng
from src.analytics.product_calculations import calculate_waste_cents
from src.analytics.waste_allocation import allocate_waste, get_strategy_options
from src.container import Container
from src.database.data_connection import Database, update_values


SCENARIO_COUNT = 30


def _price_from_cents(cents):
    return cents / 100


def _generated_waste_scenario(rng):
    user_count = rng.randint(1, 6)
    product_count = rng.randint(1, 4)
    unsettled_indexes = set(rng.sample(range(user_count), rng.randint(1, user_count)))

    users = [
        {
            "barcode": 1000 + index,
            "name": f"User {index}",
            "rank": "Rank",
            "team": "Team",
            "is_guest": rng.randint(0, 1),
            "paid_cents": 0,
        }
        for index in range(user_count)
    ]
    user_barcodes = [user["barcode"] for user in users]

    products = []
    transactions = []
    transaction_index = 0
    for index in range(product_count):
        initial_stock = rng.randint(3, 20)
        sold = rng.randint(0, min(6, initial_stock))
        waste = rng.randint(0, initial_stock - sold)
        current_stock = initial_stock - sold - waste
        product_barcode = 100 + index
        products.append(
            {
                "barcode": product_barcode,
                "name": f"Product {index}",
                "price": _price_from_cents(rng.choice([100, 150, 200, 250, 300])),
                "category": "Generated",
                "current_stock": current_stock,
                "initial_stock": initial_stock,
            }
        )
        for _ in range(sold):
            transactions.append(
                {
                    "barcode_user": rng.choice(user_barcodes),
                    "barcode_prod": product_barcode,
                    "timestamp": f"01/01/2026 10:00:{transaction_index:02d}",
                }
            )
            transaction_index += 1

    purchase_totals = {barcode: 0 for barcode in user_barcodes}
    prices = {product["barcode"]: int(round(product["price"] * 100)) for product in products}
    for transaction in transactions:
        purchase_totals[transaction["barcode_user"]] += prices[transaction["barcode_prod"]]

    for index, user in enumerate(users):
        if index not in unsettled_indexes:
            user["paid_cents"] = purchase_totals[user["barcode"]] + rng.choice(
                [100, 200, 300, 500]
            )

    return users, products, transactions, purchase_totals


def _load_scenario(db, users, products, transactions):
    db.upload_values_raises(pd.DataFrame(users), "users")
    db.upload_values_raises(pd.DataFrame(products), "prods")
    if transactions:
        db._transaction_table.append(pd.DataFrame(transactions))


def _expected_prepaid_waste_by_user(stored_users, purchase_totals):
    prepaid_waste = {}
    for _, user in stored_users.iterrows():
        paid_cents = int(user["paid_cents"])
        if paid_cents <= 0:
            continue
        barcode = int(user["barcode"])
        prepaid_waste[barcode] = max(
            0,
            paid_cents - purchase_totals.get(barcode, 0),
        )
    return prepaid_waste


def _assert_raw_waste_is_stored(db, expected_raw_waste, context):
    stored_raw_waste = int(db._settings_table.get().iloc[0]["waste_cents"])
    assert stored_raw_waste == expected_raw_waste, context


def _assert_no_user_has_negative_waste(stored_users, context):
    assert (stored_users["waste_cents"] >= 0).all(), context


def _assert_prepaid_users_keep_prepaid_waste(
    stored_users,
    purchase_totals,
    context,
):
    prepaid_waste = _expected_prepaid_waste_by_user(stored_users, purchase_totals)
    for _, user in stored_users.iterrows():
        barcode = int(user["barcode"])
        if barcode in prepaid_waste:
            assert int(user["waste_cents"]) == prepaid_waste[barcode], context
    return prepaid_waste


def _assert_total_user_waste_covers_raw_waste(
    stored_users,
    expected_raw_waste,
    context,
):
    covered_waste = int(stored_users["waste_cents"].sum())
    assert covered_waste >= expected_raw_waste, context


def _assert_rounding_overage_stays_within_whole_krone_rule(
    stored_users,
    expected_raw_waste,
    prepaid_waste,
    context,
):
    unsettled = stored_users[stored_users["paid_cents"].astype(int) <= 0]
    allocatable_waste = max(0, expected_raw_waste - sum(prepaid_waste.values()))
    unsettled_allocated = int(unsettled["waste_cents"].sum())
    charged_users = int((unsettled["waste_cents"] > 0).sum())
    rounding_overage = unsettled_allocated - allocatable_waste

    assert rounding_overage >= 0, context
    if charged_users:
        assert rounding_overage < charged_users * 100, context


@pytest.mark.parametrize(
    "strategy",
    [option["value"] for option in get_strategy_options()],
)
def test_waste_allocation_invariants_hold_for_generated_scenarios(tmp_path, strategy):
    seed, rng = property_rng()
    test_name = f"test_waste_allocation_invariants_hold_for_generated_scenarios[{strategy}]"

    for scenario_index in range(SCENARIO_COUNT):
        context = property_context(test_name, seed, scenario_index)
        db = Database(str(tmp_path / f"{strategy}_{scenario_index}.db"))
        Container.set(Database, db)
        try:
            # Arrange
            users, products, transactions, purchase_totals = _generated_waste_scenario(rng)
            _load_scenario(db, users, products, transactions)
            update_values(waste_strategy=strategy)
            expected_raw_waste = calculate_waste_cents(
                db._product_table.get(),
                db._transaction_table.get(),
            )

            # Act
            allocate_waste(db)

            # Assert
            stored_users = db._user_table.get()
            _assert_raw_waste_is_stored(db, expected_raw_waste, context)
            _assert_no_user_has_negative_waste(stored_users, context)
            prepaid_waste = _assert_prepaid_users_keep_prepaid_waste(
                stored_users,
                purchase_totals,
                context,
            )
            _assert_total_user_waste_covers_raw_waste(
                stored_users,
                expected_raw_waste,
                context,
            )
            _assert_rounding_overage_stays_within_whole_krone_rule(
                stored_users,
                expected_raw_waste,
                prepaid_waste,
                context,
            )
        except AssertionError:
            raise
        except Exception as exc:
            pytest.fail(f"{context}. Unexpected {type(exc).__name__}: {exc}")
        finally:
            Container.reset()
