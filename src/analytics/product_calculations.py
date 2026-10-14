from src.database.data_connection import get_prods, get_trans


def _waste_rows(prods, transactions):
    sold_counts = (
        transactions["barcode_prod"].astype(str).value_counts().to_dict()
        if len(transactions)
        else {}
    )
    rows = []
    for _, product in prods.iterrows():
        sold = int(sold_counts.get(str(product["barcode"]), 0))
        amount = (
            int(product["initial_stock"])
            - int(product["current_stock"])
            - sold
        )
        price_cents = int(round(float(product["price"]) * 100))
        rows.append(
            {
                "Barcode": int(product["barcode"]),
                "Product": product["name"],
                "Amount Sold": sold,
                "Waste": amount,
                "Total Price": amount * price_cents / 100,
                "_total_cents": amount * price_cents,
                "_category": str(product["category"]),
            }
        )
    return rows


def calculate_category_waste_cents(prods, transactions) -> dict[str, int]:
    category_waste = {}
    for row in _waste_rows(prods, transactions):
        category = row["_category"]
        category_waste[category] = (
            category_waste.get(category, 0) + row["_total_cents"]
        )
    return category_waste


def calculate_waste_cents(prods=None, transactions=None):
    prods = get_prods() if prods is None else prods
    transactions = get_trans() if transactions is None else transactions
    return max(0, sum(row["_total_cents"] for row in _waste_rows(prods, transactions)))


def calculate_waste():
    cents = calculate_waste_cents()
    return cents // 100 if cents % 100 == 0 else cents / 100


def get_waste_table():
    rows = _waste_rows(get_prods(), get_trans())
    for row in rows:
        row.pop("_total_cents")
        row.pop("_category")
    return rows
