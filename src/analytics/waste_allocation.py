import math
from abc import ABC, abstractmethod
from fractions import Fraction

from src.analytics.product_calculations import (
    calculate_category_waste_cents,
    calculate_waste_cents,
)


class WasteAllocationStrategy(ABC):
    label: str
    description: str

    @abstractmethod
    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        raise NotImplementedError

    @staticmethod
    def equal_split(total_waste_cents: int, barcodes: list[str]) -> dict[str, int]:
        if total_waste_cents <= 0 or not barcodes:
            return {barcode: 0 for barcode in barcodes}
        share_cents = math.ceil(total_waste_cents / len(barcodes) / 100) * 100
        return {barcode: share_cents for barcode in barcodes}


def _unsettled_barcodes(users) -> set[str]:
    if len(users) == 0:
        return set()
    return set(
        users[users["paid_cents"].astype(int) <= 0]["barcode"].astype(str)
    )


def _purchase_totals_cents(products, transactions) -> dict[str, int]:
    prices = {
        str(product["barcode"]): int(round(float(product["price"]) * 100))
        for _, product in products.iterrows()
    }
    totals = {}
    for _, transaction in transactions.iterrows():
        user_barcode = str(transaction["barcode_user"])
        product_barcode = str(transaction["barcode_prod"])
        totals[user_barcode] = totals.get(user_barcode, 0) + prices.get(product_barcode, 0)
    return totals


def _settled_prepaid_waste_cents(users, products, transactions) -> dict[str, int]:
    purchase_totals = _purchase_totals_cents(products, transactions)
    prepaid_waste = {}
    for _, user in users.iterrows():
        paid_cents = int(user.get("paid_cents", 0))
        if paid_cents <= 0:
            continue
        barcode = str(user["barcode"])
        prepaid_waste[barcode] = max(0, paid_cents - purchase_totals.get(barcode, 0))
    return prepaid_waste


class EqualAllStrategy(WasteAllocationStrategy):
    label = "Equal all users"
    description = (
        "Split all waste equally between all unsettled users, including users "
        "without purchases."
    )

    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        users = db._user_table.get()
        barcodes = sorted(_unsettled_barcodes(users))
        return self.equal_split(total_waste_cents, barcodes)


class EqualActiveStrategy(WasteAllocationStrategy):
    label = "Equal active users"
    description = (
        "Split all waste equally between unsettled users who have made purchases. "
        "Falls back to all unsettled users if no active users exist."
    )

    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        users = db._user_table.get()
        current_barcodes = _unsettled_barcodes(users)
        transactions = db._transaction_table.get()
        active_barcodes = (
            set(transactions["barcode_user"].astype(str))
            if len(transactions)
            else set()
        )
        eligible = sorted(current_barcodes & active_barcodes)
        if not eligible:
            return EqualAllStrategy().allocate(db, total_waste_cents)
        allocations = {barcode: 0 for barcode in current_barcodes}
        allocations.update(self.equal_split(total_waste_cents, eligible))
        return allocations


class EqualCategoryPurchasersStrategy(WasteAllocationStrategy):
    label = "Equal category purchasers"
    description = (
        "Split waste by product category, charging users who bought from "
        "categories with waste. Falls back to active users, then all users, if "
        "needed."
    )

    @staticmethod
    def _round_up_to_whole_krone(amount: Fraction) -> int:
        if amount <= 0:
            return 0
        whole_kroner = (
            amount.numerator + amount.denominator * 100 - 1
        ) // (amount.denominator * 100)
        return whole_kroner * 100

    def allocate(self, db, total_waste_cents: int) -> dict[str, int]:
        users = db._user_table.get()
        current_barcodes = _unsettled_barcodes(users)
        allocations = {
            barcode: Fraction(0) for barcode in current_barcodes
        }
        if total_waste_cents <= 0 or not current_barcodes:
            return {barcode: 0 for barcode in current_barcodes}

        products = db._product_table.get()
        transactions = db._transaction_table.get()
        category_waste = calculate_category_waste_cents(products, transactions)
        positive_waste = {
            category: waste
            for category, waste in category_waste.items()
            if waste > 0
        }
        total_positive_waste = sum(positive_waste.values())

        active_barcodes = (
            current_barcodes & set(transactions["barcode_user"].astype(str))
            if len(transactions)
            else set()
        )
        product_categories = {
            str(product["barcode"]): str(product["category"])
            for _, product in products.iterrows()
        }
        category_purchasers = {}
        for _, transaction in transactions.iterrows():
            category = product_categories.get(str(transaction["barcode_prod"]))
            barcode = str(transaction["barcode_user"])
            if category is not None and barcode in current_barcodes:
                category_purchasers.setdefault(category, set()).add(barcode)

        for category, waste_cents in positive_waste.items():
            category_budget = Fraction(
                total_waste_cents * waste_cents,
                total_positive_waste,
            )
            eligible = category_purchasers.get(category, set())
            if not eligible:
                eligible = active_barcodes or current_barcodes
            share = category_budget / len(eligible)
            for barcode in eligible:
                allocations[barcode] += share

        return {
            barcode: self._round_up_to_whole_krone(amount)
            for barcode, amount in allocations.items()
        }


STRATEGIES = {
    "equal_category_purchasers": EqualCategoryPurchasersStrategy(),
    "equal_active": EqualActiveStrategy(),
    "equal_all": EqualAllStrategy(),
}


def get_strategy_options() -> list[dict[str, str]]:
    return [
        {"label": strategy.label, "value": key, "title": strategy.description}
        for key, strategy in STRATEGIES.items()
    ]


def allocate_waste(db) -> dict[str, int]:
    strategy_key = str(db.settings.iloc[0]["waste_strategy"])
    if strategy_key not in STRATEGIES:
        raise ValueError(f"Unknown waste strategy: {strategy_key}")

    products = db._product_table.get()
    transactions = db._transaction_table.get()
    total_waste_cents = calculate_waste_cents(products, transactions)
    users = db._user_table.get()
    prepaid_waste = _settled_prepaid_waste_cents(users, products, transactions)
    allocatable_waste_cents = max(0, total_waste_cents - sum(prepaid_waste.values()))
    allocations = STRATEGIES[strategy_key].allocate(db, allocatable_waste_cents)

    users["waste_cents"] = (
        users["barcode"].astype(str).map(allocations).fillna(0).astype(int)
    )
    settled_mask = users["barcode"].astype(str).isin(prepaid_waste)
    users.loc[settled_mask, "waste_cents"] = (
        users.loc[settled_mask, "barcode"].astype(str).map(prepaid_waste).astype(int)
    )
    db.upload_values_raises(users, "users")

    settings = db._settings_table.get()
    settings.loc[0, "waste_cents"] = total_waste_cents
    db.upload_values_raises(settings, "settings")

    unsettled_mask = users["paid_cents"].astype(int) <= 0
    covered_waste = int(users["waste_cents"].sum()) if len(users) else 0
    unsettled_allocated = (
        int(users.loc[unsettled_mask, "waste_cents"].sum()) if len(users) else 0
    )
    charged_users = int((users.loc[unsettled_mask, "waste_cents"] > 0).sum()) if len(users) else 0
    rounding_overage_cents = unsettled_allocated - allocatable_waste_cents
    if len(users) and covered_waste < total_waste_cents:
        raise ValueError("Waste allocation did not cover the calculated waste")
    if charged_users and rounding_overage_cents >= charged_users * 100:
        raise ValueError("Waste allocation exceeded the allowed rounding overage")
    return allocations
