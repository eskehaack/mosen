import sqlite3
from contextlib import closing
from src.database.connection import Connection


def test_owner_token_controls_commit_and_close(tmp_path):
    dbfile = str(tmp_path / "owner.db")
    conn = Connection(dbfile)

    owner = conn.begin_transaction()
    con, cur = conn.connect()
    cur.execute("CREATE TABLE t(x INTEGER)")
    cur.execute("INSERT INTO t(x) VALUES (1)")

    other = conn.begin_transaction()
    # non-owner end should be ignored
    conn.end_transaction(other, commit=False)
    assert conn._active_con is not None

    # owner end should commit and close
    conn.end_transaction(owner, commit=True)
    assert conn._active_con is None

    # verify committed
    con2 = sqlite3.connect(dbfile)
    res = con2.execute("SELECT x FROM t").fetchone()[0]
    con2.close()
    assert res == 1


def test_maybe_close_ignores_active_connection(tmp_path):
    dbfile = str(tmp_path / "maybe.db")
    conn = Connection(dbfile)

    owner = conn.begin_transaction()
    con_active, cur = conn.connect()
    cur.execute("CREATE TABLE t2(y INTEGER)")

    # _maybe_close should not close the active connection
    conn._maybe_close(con_active)
    cur.execute("INSERT INTO t2(y) VALUES (2)")
    cur.execute("SELECT y FROM t2")
    assert cur.fetchone()[0] == 2

    conn.end_transaction(owner, commit=True)


def test_owner_rollback_undoes_drop_and_create_after_nested_commit(tmp_path):
    dbfile = tmp_path / "schema.db"
    with closing(sqlite3.connect(dbfile)) as con:
        con.execute("CREATE TABLE original(x INTEGER)")
        con.execute("INSERT INTO original VALUES (1)")
        con.commit()
    conn = Connection(dbfile)

    owner = conn.begin_transaction()
    _, cur = conn.connect()
    # No inserts or updates here: table changes alone must be transactional.
    cur.execute("DROP TABLE original")
    cur.execute("CREATE TABLE replacement(y INTEGER)")
    conn.end_transaction(conn.begin_transaction(), commit=True)
    conn.end_transaction(owner, commit=False)

    with closing(sqlite3.connect(dbfile)) as con:
        assert con.execute("SELECT x FROM original").fetchall() == [(1,)]
        assert con.execute("SELECT name FROM sqlite_master WHERE name='replacement'").fetchone() is None
