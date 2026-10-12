import pandas as pd
from src.database.tables.base_table import BaseTable
from src.database.tables.column import Column, BarcodeColumn
from src.barcode import BarcodePartition


class ProductTable(BaseTable):
    table_name = "prods"
    columns = [
        BarcodeColumn("barcode", int, partition=BarcodePartition.PRODUCT, required=True, is_primary_key=True),
        Column("name", str, required=True),
        Column("price", float, required=True),
        Column("category", str, required=True),
        Column("current_stock", int, required=True),
        Column("initial_stock", int, required=True),
    ]
    
    create_sql = """
        CREATE TABLE prods (
            barcode varchar(255),
            name varchar(255),
            price varchar(255),
            category varchar(255),
            current_stock varchar(255),
            initial_stock varchar(255)
        )
    """

    def is_valid_batch(self, row: dict, all_rows: list) -> bool:
        if not super().is_valid_batch(row, all_rows):
            return False
        name = str(row["name"])
        return sum(str(other.get("name")) == name for other in all_rows) <= 1
