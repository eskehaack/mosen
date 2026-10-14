from src.database.tables.base_table import BaseTable
from src.database.tables.product import ProductTable 
from src.database.tables.user import UserTable
from src.database.connection import Connection
from src.database.tables.column import BarcodeColumn, Column
from src.barcode import BarcodePartition


class TransactionTable(BaseTable):
    table_name = "transactions"
    columns = [
        BarcodeColumn("barcode_user", int, partition=BarcodePartition.USER, required=True),
        BarcodeColumn("barcode_prod", int, partition=BarcodePartition.PRODUCT, required=True),
        Column("timestamp", str, required=True),
    ]
    
    create_sql = """
        CREATE TABLE transactions (
            barcode_user INTEGER,
            barcode_prod INTEGER,
            timestamp VARCHAR(255)
        )
    """
    
    def __init__(self, connection: Connection, product_table: ProductTable, user_table: UserTable):
        self.product_table = product_table
        self.user_table = user_table
        super().__init__(connection)
    
    def is_valid_batch(self, row: dict, all_rows: list) -> bool:
        """Validate transaction: standard checks + product/user existence."""
        if not super().is_valid_batch(row, all_rows):
            return False
        
        if not self._validate_product_exists(row):
            return False
        
        if not self._validate_user_exists(row):
            return False

        return True
    
    def _validate_product_exists(self, row: dict) -> bool:
        """Check that barcode_prod exists in products table."""
        prods = self.product_table.get()
        return int(row["barcode_prod"]) in list(prods["barcode"])
    
    def _validate_user_exists(self, row: dict) -> bool:
        """Check that barcode_user exists in users table."""
        users = self.user_table.get()
        return int(row["barcode_user"]) in list(users["barcode"])
