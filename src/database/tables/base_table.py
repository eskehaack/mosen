from abc import ABC, abstractmethod
import sqlite3
import uuid
import pandas as pd
from src.database.connection import Connection
from src.database.tables.column import Column, BarcodeColumn


class BaseTable(ABC):
    """Abstract base for all table operations."""
    
    table_name: str      # Override: "prods", "users", etc
    columns: list        # Override: list of Column objects
    create_sql: str      # Override: SQL to create table
    
    def __init__(self, connection: Connection):
        self.connection = connection
        self._cache = self._empty_cache()
        with self.connection._lock:
            self._ensure_table_exists()
            self._refresh_cache()

    def _empty_cache(self) -> pd.DataFrame:
        return pd.DataFrame({col.name: pd.Series(dtype="str") for col in self.columns})
    
    @property
    def primary_keys(self) -> list:
        """Return list of primary key column names."""
        return [col.name for col in self.columns if col.is_primary_key]
    
    def validate_columns(self, row: dict) -> bool:
        """Check that all present columns are valid and all required columns exist.
        Returns True if the row is valid (helper method for testing)."""
        valid_col_names = {col.name for col in self.columns}
        
        for col_name in row.keys():
            if col_name not in valid_col_names:
                return False
        
        for col in self.columns:
            if col.required and col.name not in row:
                return False
        
        return True
    
    def _check_primary_key_duplicates(self, row: dict, all_rows: list) -> bool:
        """Check if the complete composite primary key is duplicated.
        Returns True if this exact combination of all primary keys already exists, False otherwise."""
        
        if not self.primary_keys:
            return False
        
        df = pd.DataFrame(all_rows)
        
        mask = pd.Series([True] * len(df))
        for pk_col in self.primary_keys:
            mask = mask & (df[pk_col] == row[pk_col])
        
        return sum(mask) > 1
    
    def _ensure_table_exists(self):
        """Create table if it doesn't exist."""
        if not self.connection.table_exists(self.table_name):
            def _create(con, cur):
                cur.execute(self.create_sql)
            self._with_transaction(_create)

    def _refresh_cache(self):
        query = f"SELECT * FROM {self.table_name}"
        col_names = [col.name for col in self.columns]
        self._cache = self.connection.get_query(query, col_names)
    
    def is_valid_batch(self, row: dict, all_rows: list) -> bool:
        """Validate row against all_rows (includes row being tested)."""
        if not self.validate_columns(row):
            return False
        
        # Check required columns are not empty
        for col in self.columns:
            if col.required:
                val = row.get(col.name)
                if val is None or str(val).strip() == "":
                    return False
        
        if self._check_primary_key_duplicates(row, all_rows):
            return False
        
        for col in self.columns:
            if type(col) == BarcodeColumn and not col.is_valid_barcode(row[col.name]):
                return False

        return True
    
    def is_valid_single(self, row: dict, all_other_rows: list) -> bool:
        """Validate single row against other existing rows.
        Used for single inserts: all_other_rows does NOT include the row being tested."""
        all_rows_with_new = all_other_rows + [row]
        return self.is_valid_batch(row, all_rows_with_new)
    
    def get_untyped(self) -> pd.DataFrame:
        """Return all rows as strings."""
        with self.connection._lock:
            return self._cache.copy()
    
    def get(self) -> pd.DataFrame:
        """Return all rows with correct Python types."""
        df = self.get_untyped()
        if df.empty:
            return pd.DataFrame({col.name: pd.Series([], dtype=col.dtype) 
                               for col in self.columns})
        for col in self.columns:
            df[col.name] = df[col.name].astype(col.dtype)
        return df
    
    def _fill_optional_defaults(self, row: dict) -> dict:
        """Fill missing or empty optional columns with their defaults."""
        for col in self.columns:
            if not col.required:
                val = row.get(col.name)
                if self._is_missing_optional_value(val):
                    row[col.name] = col.default
                    val = row[col.name]
                if col.dtype is int and isinstance(val, float) and val.is_integer():
                    row[col.name] = int(val)
        return row

    @staticmethod
    def _is_missing_optional_value(val) -> bool:
        if val is None:
            return True
        try:
            if pd.isna(val):
                return True
        except (TypeError, ValueError):
            pass
        return str(val).strip() == ""
    
    def set(self, data: list | pd.DataFrame) -> tuple[str, list]:
        """Replace mode: fill optional defaults, validate, delete all, insert."""
        if isinstance(data, pd.DataFrame):
            data = data.to_dict(orient="records")
        with self.connection._lock:
            bad_rows = []
            good_rows = []

            for row in data:
                self._fill_optional_defaults(row)
                is_valid = self.is_valid_batch(row, data)

                if not is_valid:
                    bad_rows.append(row)
                else:
                    good_rows.append(row)

            if bad_rows:
                return self.table_name, bad_rows

            def _do_replace(con, cur):
                cur.execute(f"DELETE FROM {self.table_name}")
                if good_rows:
                    cols = ", ".join(good_rows[0].keys())
                    placeholders = ", ".join(["?" for _ in good_rows[0].keys()])
                    cur.executemany(
                        f"INSERT INTO {self.table_name} ({cols}) VALUES ({placeholders})",
                        [list(row.values()) for row in good_rows],
                    )
                self._refresh_cache()

            self._with_transaction(_do_replace)

            return "success", bad_rows

    def append(self, data: list | pd.DataFrame) -> tuple[str, list]:
        """Append mode: validate rows, insert them, and refresh the cache."""
        if isinstance(data, pd.DataFrame):
            data = data.to_dict(orient="records")

        with self.connection._lock:
            if not data:
                return "success", []

            working_rows = self._cache.to_dict(orient="records")
            data = [self._fill_optional_defaults(row).copy() for row in data]
            candidate_rows = working_rows + data
            bad_rows = []
            good_rows = []

            for row in data:
                candidate_row = row
                is_valid = self.is_valid_batch(candidate_row, candidate_rows)

                if not is_valid:
                    bad_rows.append(candidate_row)
                else:
                    good_rows.append(candidate_row)
                    working_rows.append(candidate_row)

            if bad_rows:
                return self.table_name, bad_rows

            def _do_append(con, cur):
                cols = ", ".join(good_rows[0].keys())
                placeholders = ", ".join(["?" for _ in good_rows[0].keys()])
                cur.executemany(
                    f"INSERT INTO {self.table_name} ({cols}) VALUES ({placeholders})",
                    [list(row.values()) for row in good_rows],
                )
                self._refresh_cache()

            self._with_transaction(_do_append)
            return "success", bad_rows

    def _with_transaction(self, fn):
        """Helper: run `fn(con, cur)` inside a DB transaction.

        Uses Connection's first-token-ownership semantics:
        - First caller's token becomes owner and controls commit/close
        - Nested tokens don't affect transaction control
        - Nested calls reuse the active connection
        """
        with self.connection._lock:
            token = self.connection.begin_transaction()
            try:
                con, cur = self.connection.connect()
                result = fn(con, cur)
            except Exception:
                self.connection.end_transaction(token, commit=False)
                self._refresh_cache() 
                raise
            else:
                self.connection.end_transaction(token, commit=True)
                return result
        
