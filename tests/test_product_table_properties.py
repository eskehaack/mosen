import pandas as pd

from property_helpers import property_context, property_rng
from src.container import Container
from src.database.data_connection import Database


SCENARIO_COUNT = 30


def _product_rows(rng, count, barcode_start=100):
    barcodes = rng.sample(range(barcode_start, 1000), count)
    rows = []
    for index, barcode in enumerate(barcodes):
        initial_stock = rng.randint(0, 50)
        rows.append(
            {
                "barcode": barcode,
                "name": f"Product {barcode}",
                "price": rng.randint(50, 1000) / 100,
                "category": f"Category {rng.randint(1, 4)}",
                "current_stock": rng.randint(0, initial_stock),
                "initial_stock": initial_stock,
            }
        )
    return rows


def _typed_product_records(rows):
    return sorted(
        [
            {
                "barcode": int(row["barcode"]),
                "name": str(row["name"]),
                "price": float(row["price"]),
                "category": str(row["category"]),
                "current_stock": int(row["current_stock"]),
                "initial_stock": int(row["initial_stock"]),
            }
            for row in rows
        ],
        key=lambda row: row["barcode"],
    )


def _table_records(table):
    return _typed_product_records(table.get().to_dict(orient="records"))


def _assert_set_accepts_rows(table, rows, context):
    result, bad_rows = table.set(pd.DataFrame(rows))
    assert result == "success", context
    assert bad_rows == [], context


def _assert_append_accepts_rows(table, rows, context):
    result, bad_rows = table.append(pd.DataFrame(rows))
    assert result == "success", context
    assert bad_rows == [], context


def _assert_table_contains_rows(table, rows, context):
    assert _table_records(table) == _typed_product_records(rows), context


def test_valid_product_rows_can_be_set_then_appended(tmp_path):
    seed, rng = property_rng()
    test_name = "test_valid_product_rows_can_be_set_then_appended"

    for scenario_index in range(SCENARIO_COUNT):
        context = property_context(test_name, seed, scenario_index)
        db = Database(str(tmp_path / f"product_round_trip_{scenario_index}.db"))
        Container.set(Database, db)
        try:
            # Arrange
            table = db._product_table
            rows = _product_rows(rng, rng.randint(2, 8))
            split_index = rng.randint(1, len(rows) - 1)
            first_rows = rows[:split_index]
            appended_rows = rows[split_index:]

            # Act / Assert
            _assert_set_accepts_rows(table, first_rows, context)
            _assert_table_contains_rows(table, first_rows, context)

            _assert_append_accepts_rows(table, appended_rows, context)
            _assert_table_contains_rows(table, rows, context)
        finally:
            Container.reset()


def test_invalid_product_replacement_keeps_existing_rows(tmp_path):
    seed, rng = property_rng()
    test_name = "test_invalid_product_replacement_keeps_existing_rows"

    invalid_variants = ["bad_barcode", "duplicate_barcode", "empty_name", "missing_category"]

    for scenario_index in range(SCENARIO_COUNT):
        context = property_context(test_name, seed, scenario_index)
        db = Database(str(tmp_path / f"product_invalid_{scenario_index}.db"))
        Container.set(Database, db)
        try:
            # Arrange
            table = db._product_table
            initial_rows = _product_rows(rng, rng.randint(1, 5))
            _assert_set_accepts_rows(table, initial_rows, context)
            initial_state = _table_records(table)

            replacement_rows = _product_rows(rng, rng.randint(2, 6))
            variant = rng.choice(invalid_variants)
            if variant == "bad_barcode":
                replacement_rows[-1]["barcode"] = 99
            elif variant == "duplicate_barcode":
                replacement_rows[-1]["barcode"] = replacement_rows[0]["barcode"]
            elif variant == "empty_name":
                replacement_rows[-1]["name"] = ""
            else:
                replacement_rows[-1].pop("category")

            # Act
            result, bad_rows = table.set(replacement_rows)

            # Assert
            assert result == table.table_name, context
            assert bad_rows, context
            assert _table_records(table) == initial_state, context
        finally:
            Container.reset()
