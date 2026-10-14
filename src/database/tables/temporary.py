from src.database.tables.base_table import BaseTable
from src.database.tables.column import BarcodeColumn, Column
from src.barcode import BarcodePartition


class TemporaryTable(BaseTable):
    table_name = "temporary"
    columns = [
        BarcodeColumn("barcode_prod", int, partition=BarcodePartition.PRODUCT, required=True),
        Column("name", str, required=True),
    ]

    create_sql = """
        CREATE TABLE temporary (
            barcode_prod INTEGER,
            name varchar(255)
        )
    """