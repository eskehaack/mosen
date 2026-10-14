from src.database.tables.base_table import BaseTable
from src.database.tables.column import Column


class SettingsTable(BaseTable):
    table_name = "settings"
    columns = [
        Column("password", str, required=True),
        Column("show_bill", str, required=True),
        Column("waste_cents", int, required=True),
        Column("waste_strategy", str, required=True),
        Column("backup", int, required=True),
        Column("cache_validation", int, required=True),
        Column("last_stock_update_at", str, required=False, default=""),
        Column("bill_preview_waste_extra_percent", int, required=True),
    ]

    create_sql = """
        CREATE TABLE settings (
            password varchar(255),
            show_bill varchar(255),
            waste_cents INTEGER,
            waste_strategy varchar(255),
            backup INTEGER,
            cache_validation INTEGER,
            last_stock_update_at varchar(255),
            bill_preview_waste_extra_percent INTEGER
        )
    """

    default_row = {
        "password": "OLProgram",
        "show_bill": "True",
        "waste_cents": 0,
        "waste_strategy": "equal_category_purchasers",
        "backup": 10,
        "cache_validation": 5,
        "last_stock_update_at": "",
        "bill_preview_waste_extra_percent": 50,
    }

    def ensure_defaults(self) -> None:
        """Ensure the settings table contains the expected default row."""
        with self.connection._lock:
            if self.get_untyped().empty:
                self.set([self.default_row.copy()])
