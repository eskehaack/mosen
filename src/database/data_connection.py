import pandas as pd
import functools
import keyboard as k
import hashlib

from src.barcode import BarcodePartition, is_barcode
from src.container import Container
from src.database.tables.base_table import BaseTable
from src.database.tables.product import ProductTable
from src.database.tables.settings import SettingsTable
from src.database.tables.temporary import TemporaryTable
from src.database.tables.user import UserTable
from src.database.tables.transaction import TransactionTable
from src.database.connection import Connection
from src.error_handler import Result

from dataclasses import dataclass
from typing import Any



@dataclass
class TransactionResult(Result):
    commit: bool = True

    def to_result(self) -> Result:
        return Result(values=self.values, error=self.error)
    
    @staticmethod
    def from_return(value: Any) -> 'TransactionResult':
        if isinstance(value, TransactionResult):
            return value
        if isinstance(value, Result):
            return TransactionResult(values=value.values, error=value.error, commit=True)
        if isinstance(value, tuple):
            return TransactionResult(values=value, commit=True)
        return TransactionResult(values=(value,), commit=True)



class Database:
    """DB Handler.
    Warning: You risk data corruption if you have more than one instance or you use the Connection directly.
    Always use Container.get(Database) to get the instance and never use Connection directly."""
    def __init__(self, data_file="beerbase.db"):
        self._connection = Connection(data_file)
        self._product_table = ProductTable(self._connection)
        self._user_table = UserTable(self._connection)
        self._transaction_table = TransactionTable(
            self._connection,
            product_table=self._product_table,
            user_table=self._user_table
        )
        self._temporary_table = TemporaryTable(self._connection)
        self._settings_table = SettingsTable(self._connection)
        self.tables = {
            self._product_table.table_name: self._product_table,
            self._user_table.table_name: self._user_table,
            self._transaction_table.table_name: self._transaction_table,
            self._temporary_table.table_name: self._temporary_table,
            self._settings_table.table_name: self._settings_table,
        }
        self.init()
    
    def init(self):
        """Initialize tables and defaults without leaking or closing borrowed connections."""
        def initialize():
            self._create_tables()
            self.refresh_caches()
            self._settings_table.ensure_defaults()

        self.execute_in_transaction(initialize).raise_if_error()
    
    def _create_tables(self):
        """Create all required tables if they don't exist."""
        def create_tables():
            _, cur = self._connection.connect()
            for table_name, table in self.tables.items():
                if not self._table_exists(table_name):
                    cur.execute(table.create_sql)

        #leaves caches untouched; on failure some tables may still be missing.
        self.execute_in_transaction(create_tables, refresh_on_rollback=False).raise_if_error()
    
    def _table_exists(self, table_name: str) -> bool:
        with self._connection._lock:
            return self._connection.table_exists(table_name)
    
    def get_query(self, query: str, columns: list):
        with self._connection._lock:
            return self._connection.get_query(query, columns)
    
    def validate_prod(self, row: dict, data: list) -> bool:
        """Validate product (batch mode: data includes row being tested)."""
        return self._product_table.is_valid_batch(row, data)
    
    def validate_user(self, row: dict, data: list) -> bool:
        """Validate user (batch mode: data includes row being tested)."""
        return self._user_table.is_valid_batch(row, data)
    
    def validate_trans(self, row: dict, data: list) -> bool:
        """Validate transaction (batch mode: data includes row being tested)."""
        return self._transaction_table.is_valid_batch(row, data)
    
    def get_table(self,table_name: str) -> BaseTable:
        if table_name not in self.tables:
            raise ValueError(f"Unknown table: {table_name}")
        return self.tables[table_name]
    
    def upload_values(self, data: list, table: str) -> tuple[str, list]:
        """Upload data to table."""
        return self.get_table(table).set(data)
    
    def try_upload_values(self, data: list, table: str) -> tuple[bool, list]:
        """Upload data to table, return (success, bad_rows). On failure, no data is uploaded."""
        result, bad_rows = self.get_table(table).set(data)
        return result == "success", bad_rows
    
    def upload_values_raises(self, data: list, table: str) -> tuple[bool, list]:
        """Upload data to table, return (success, bad_rows). On failure, no data is uploaded."""
        success, bad_rows = self.try_upload_values(data, table)
        if not success:
            raise ValueError(f"Failed to upload data to {table}. Bad rows: {bad_rows}")

    
    def barcode_exists(self, barcode: int, partition: BarcodePartition) -> bool:
        """Check if barcode exists in the relevant table based on partition."""
        if not is_barcode(barcode, partition):
            return False

        if partition == BarcodePartition.PRODUCT:
            return int(barcode) in list(self._product_table.get()["barcode"])
        elif partition == BarcodePartition.USER:
            return int(barcode) in list(self._user_table.get()["barcode"])
        else:
            raise ValueError("Unknown barcode partition")

    @property
    def prods(self):
        return self._product_table.get_untyped()

    @property
    def users(self):
        return self._user_table.get_untyped()

    @property
    def transactions(self):
        return self._transaction_table.get_untyped()

    @property
    def temporary(self):
        return self._temporary_table.get_untyped()

    @property
    def settings(self):
        return self._settings_table.get_untyped()
    
    @property
    def data_file(self):
        return self._connection.data_file
    
    def refresh_caches(self):
        """Refresh all table caches under DB lock."""
        with self._connection._lock:
            for table in self.tables.values():
                table._refresh_cache()

    def validate_cache_hashes(self):
        """Under DB lock: for each table, copy current cache, refresh it, compute MD5 hashes and
        report which tables changed. Returns a list of table names that changed (empty list if none)."""
        changed = []

        def hash_df(df: pd.DataFrame) -> str:
            bytes_data = df.to_csv(index=False).encode("utf-8")
            return hashlib.md5(bytes_data).hexdigest()
        
        with self._connection._lock:
            for name, table in self.tables.items():
                old_hash = hash_df(table.get())
                table._refresh_cache()
                new_hash = hash_df(table.get())

                if old_hash != new_hash:
                    changed.append(name)
        return changed

    def execute_in_transaction(self, function, *, refresh_on_rollback: bool = True) -> Result:
        """Run callable `function` inside a single DB transaction/connection under the DB lock.
        Respects TransactionResult.commit if returned by 'function'. Otherwise commits on success, rolls back on exception
        Only the transaction owner refreshes caches after rollback, unless disabled for schema creation,
        which leaves caches untouched and may involve tables that do not yet exist.
        """
        with self._connection._lock:
            token = None
            try:
                token = self._connection.begin_transaction()
                result = function()
                transaction_result = TransactionResult.from_return(result)

                self._connection.end_transaction(token, commit=transaction_result.commit)
                if token is not None and refresh_on_rollback and not transaction_result.commit:
                    self.refresh_caches()
                return transaction_result.to_result()
                    
            except Exception as e:
                try:
                    self._connection.end_transaction(token, commit=False)
                finally:
                    if token is not None and refresh_on_rollback:
                        self.refresh_caches()
                return Result.from_exception(e)


def get_prods():
    return Container.get(Database).prods

def handle_result(result: Result,*args, **kwargs):
    return result.to_values()


def db_transaction_raises(func):
    """Decorator: run the wrapped callable inside a DB transaction and re-raise exceptions."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        db = Container.get(Database)
        result = db.execute_in_transaction(lambda: func(*args, **kwargs))
        return result.to_values()

    return wrapper

def db_transaction_result(_func=None, *, fallback_values: tuple[Any, ...] | None = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            db = Container.get(Database)
            result = db.execute_in_transaction(lambda: func(*args, **kwargs))
            if result.error is not None and fallback_values is not None:
                return Result(values=fallback_values, error=result.error)
            return result
        return wrapper

    if _func is not None:
        return decorator(_func)
    return decorator


def get_trans():
    return Container.get(Database).transactions

def get_users():
    return Container.get(Database).users

def get_current_trans():
    return Container.get(Database).temporary

def update_current_trans(data: pd.DataFrame):
    if len(data.columns) == 2:
        Container.get(Database)._temporary_table.set(data)
    else:
        raise ValueError("Incorrect data")



def reset_table(table: str):
    db = Container.get(Database)
    if table not in db.tables:
        raise ValueError(f"Unknown table: {table}")
    db.get_table(table).set([])
    print(f"Reset on {table}")

def reset_current_trans():
    reset_table("temporary")

def upload_values(data: list, table: str):
    return Container.get(Database).upload_values(data, table)

def add_transactions(trans_df):
    return Container.get(Database)._transaction_table.append(trans_df)

def get_password():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return str(db.settings.iloc[0]["password"])

def get_backup_time():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return int(db.settings.iloc[0]["backup"])


def get_cache_validation_time():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return int(db.settings.iloc[0]["cache_validation"])


def get_backup_interval_ms():
    try:
        minutes = get_backup_time()
        return int(minutes) * 60000
    except Exception:
        return 10 * 60000


def get_cache_validation_interval_ms():
    try:
        minutes = get_cache_validation_time()
        return int(minutes) * 60000
    except Exception:
        return 5 * 60000

def get_show_bill():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return db.settings.iloc[0]["show_bill"] == "True"

def get_waste():
    cents = get_waste_cents()
    return cents // 100 if cents % 100 == 0 else cents / 100

def get_waste_cents():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return int(db.settings.iloc[0]["waste_cents"])

def get_waste_strategy():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return str(db.settings.iloc[0]["waste_strategy"])

def get_last_stock_update_at():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return str(db.settings.iloc[0]["last_stock_update_at"])

def get_bill_preview_waste_extra_percent():
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    return int(db.settings.iloc[0]["bill_preview_waste_extra_percent"])

def update_values(
    password=None,
    show_bill=None,
    waste=None,
    waste_cents=None,
    waste_strategy=None,
    backup_time=None,
    cache_validation_time=None,
    last_stock_update_at=None,
    bill_preview_waste_extra_percent=None,
):
    db = Container.get(Database)
    db._settings_table.ensure_defaults()
    settings_row = db.settings.iloc[0].to_dict()
    inps = {
        "password": password,
        "show_bill": show_bill,
        "waste_cents": waste_cents if waste_cents is not None else (
            int(round(float(waste) * 100)) if waste is not None else None
        ),
        "waste_strategy": waste_strategy,
        "backup": backup_time,
        "cache_validation": cache_validation_time,
        "last_stock_update_at": last_stock_update_at,
        "bill_preview_waste_extra_percent": bill_preview_waste_extra_percent,
    }
    for key, value in inps.items():
        if value is None:
            continue
        settings_row[key] = str(value)
    result, bad_rows = db._settings_table.set([settings_row])
    success = result == "success"
    if not success:
         raise ValueError(f"Failed to update settings. Bad rows: {bad_rows}")

@db_transaction_raises
def _reset_all_tables():
    """Recreate the configured database's tables and defaults in one transaction."""
    db = Container.get(Database)
    _, cur = db._connection.connect()
    for table in db.tables:
        cur.execute(f"DROP TABLE IF EXISTS {table}")
    db.init()


def reset_all_tables():
    _reset_all_tables()
    k.unhook_all()
    k.send("alt+f4")
