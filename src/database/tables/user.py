from src.database.tables.base_table import BaseTable
from src.database.tables.column import Column, BarcodeColumn
from src.barcode import BarcodePartition


class UserTable(BaseTable):
    table_name = "users"
    columns = [
        BarcodeColumn("barcode", int, partition=BarcodePartition.USER, required=True, is_primary_key=True),
        Column("name", str, required=True),
        Column("rank", str, required=True),
        Column("team", str, required=True),
        Column("is_guest", int, required=False, default=0),
        Column("waste_cents", int, required=False, default=-1),
        Column("paid_cents", int, required=False, default=0),
    ]
    
    create_sql = """
        CREATE TABLE users (
            barcode INTEGER,
            name varchar(255),
            rank varchar(255),
            team varchar(255),
            is_guest INTEGER,
            waste_cents INTEGER,
            paid_cents INTEGER
        )
    """
