"""Pure SQLite connection wrapper. No table knowledge."""
import sqlite3
from threading import RLock
import pandas as pd
import uuid


class Connection:
    """Low-level SQLite connection provider.

    By default callers get fresh connections. Callers that want a multi-step
    transaction can use `begin_transaction()` / `end_transaction()` to create a
    single connection reused by `connect()` while the transaction is active.
    """

    def __init__(self, data_file: str = "beerbase.db"):
        self.data_file = data_file
        self._lock = RLock()
        self._active_con = None
        self._active_token = None

    def connect(self):
        """Return (con, cur). If a transaction connection is active, return it."""
        if self._active_con is not None:
            return self._active_con, self._active_con.cursor()
        con = sqlite3.connect(self.data_file, timeout=5)
        return con, con.cursor()

    def begin_transaction(self):
        """Begin a SQL transaction and return its owner token, or None for nested calls.
        Only the owner token (the first caller's UUID) will have effect when passed to
        `end_transaction()`; other tokens are ignored by `end_transaction()`.
        """
        with self._lock:
            token = uuid.uuid4().hex
            if self._active_con is not None:
                return None
            con = sqlite3.connect(self.data_file, timeout=5, check_same_thread=False)
            try:
                con.execute("BEGIN")
            except Exception:
                con.close()
                raise
            self._active_con = con
            self._active_token = token
            return token

    def end_transaction(self, token: str, commit: bool = True):
        """If `token` matches the owner token, commit/rollback and close.

        Tokens that do not match the owner token are ignored. This keeps the
        ownership model simple: the first caller to `begin_transaction()` owns
        the active connection and only that caller's token will trigger commit
        / rollback / close when calling `end_transaction()`.
        """
        with self._lock:
            if token is None or token != self._active_token:
                return
            con = self._active_con
            try:
                if commit:
                    con.commit()
                else:
                    con.rollback()
            finally:
                try:
                    con.close()
                finally:
                    self._active_con = None
                    self._active_token = None
                    self._active_count = 0

    def _maybe_close(self, con):
        """Close the connection only if it is not the active transaction connection."""
        if con is None:
            return
        if con is self._active_con:
            return
        try:
            con.close()
        except Exception:
            pass

    def execute(self, query: str) -> list:
        """Execute raw SQL and return results."""
        con, cur = self.connect()
        result = cur.execute(query).fetchall()
        self._maybe_close(con)
        return result

    def execute_commit(self, query: str):
        """Execute SQL and commit."""
        con, cur = self.connect()
        cur.execute(query)
        con.commit()
        self._maybe_close(con)

    def get_query(self, query: str, columns: list) -> pd.DataFrame:
        """Execute query and return DataFrame with string columns."""
        con, cur = self.connect()
        data = pd.DataFrame(cur.execute(query), columns=columns, dtype=str)
        self._maybe_close(con)
        return data

    def table_exists(self, table_name: str) -> bool:
        """Check if table exists."""
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        con, cur = self.connect()
        result = cur.execute(sql, (table_name,)).fetchone() is not None
        self._maybe_close(con)
        return result

    def init(self):
        """Get connection (backward compatibility with Database.init())."""
        return self.connect()
