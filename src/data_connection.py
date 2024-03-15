import os

import pandas as pd
from numpy import array
from datetime import datetime
import sqlite3

from src.tables.create_tables import table_defs


def init():
    data_file = "beerbase.db"
    if not os.path.exists(data_file):
        open(data_file, "w")

    con = sqlite3.connect(data_file)
    cur = con.cursor()

    sql_query = """SELECT name FROM sqlite_master 
                                    WHERE type='table';"""
    cur.execute(sql_query)
    extraction = lambda x: str(x[0])
    tables = list(map(extraction, cur.fetchall()))
    defs = table_defs()
    for table in defs.keys():
        if table in tables:
            continue
        cur.execute(defs[table])
        con.commit()
    return con, cur


def get_prods():
    con, cur = init()
    cols = [
        "barcode",
        "name",
        "price",
        "category",
        "current_stock",
        "initial_stock",
    ]
    data = pd.DataFrame(cur.execute("SELECT * FROM prods"), columns=cols, dtype=str)
    if len(data) == 0:
        data = pd.DataFrame(columns=cols, dtype=str)
    else:
        data.columns = cols
    return data


def get_trans():
    con, cur = init()
    cols = [
        "barcode_user",
        "barcode_prod",
        "price",
        "timestamp",
    ]
    data = pd.DataFrame(
        cur.execute("SELECT * FROM transactions"), columns=cols, dtype=str
    )
    if len(data) == 0:
        data = pd.DataFrame(columns=cols, dtype=str)
    else:
        data.columns = cols
    return data


def get_users():
    con, cur = init()
    cols = ["barcode", "name", "rank", "team"]
    data = pd.DataFrame(cur.execute("SELECT * FROM users"), columns=cols, dtype=str)
    if len(data) == 0:
        data = pd.DataFrame(columns=cols, dtype=str)
    else:
        data.columns = cols
    return data


def get_current_trans():
    con, cur = init()
    cols = ["barcode_prod", "name"]
    data = pd.DataFrame(cur.execute("SELECT * FROM temporary"), columns=cols, dtype=str)
    if len(data) == 0:
        data = pd.DataFrame(columns=cols, dtype=str)
    else:
        data.columns = cols
    return data


def update_current_trans(data: pd.DataFrame):
    con, cur = init()
    if len(data.columns == 2):
        data.to_sql(name="temporary", con=con, if_exists="replace", index=False)
        con.commit()
    else:
        raise ValueError("Incorrect data")


def reset_table(table: str):
    con, cur = init()
    cur.execute(f"DELETE FROM {table}")
    print(f"Reset on {table}")
    con.commit()


def reset_current_trans():
    reset_table("temporary")


def upload_values(data: list, table: str):
    reset_table(table)
    if type(data) == pd.DataFrame:
        data = data.to_dict(orient="records")
    con, cur = init()
    n_cols = {"prods": 6, "transactions": 4, "users": 4}
    validation = {
        "prods": validate_prod,
        "transactions": validate_trans,
        "users": validate_user,
    }

    bad_rows = list()
    for row in data:
        row, bad = validation[table](row, data)
        for col, val in row.items():
            if val is None or str(val).replace(" ", "") == "":
                row[col] = "Unkown"
                bad = True
        if bad:
            bad_rows.append(row)

    data = pd.DataFrame(data)
    if n_cols[table] == len(data.columns):
        data.to_sql(name=table, con=con, if_exists="replace", index=False)
        con.commit()
        return "success", bad_rows
    else:
        return table, None


def validate_user(row: dict, data: list):
    users = pd.DataFrame(data)
    bad = False
    if sum(array(users["barcode"]) == row["barcode"]) > 1:
        bad = True
        row["barcode"] = max(users["barcode"]) + 1
    if len(str(row["barcode"])) < 4 or len(str(row["barcode"])) > 11:
        bad = True
        for i in range(1000, 100000000000):
            if i not in users["barcode"]:
                row["barcode"] = i
                break
        return row, bad
    return row, bad


def validate_prod(row: dict, data: list):
    prods = pd.DataFrame(data)
    bad = False
    if sum(array(prods["barcode"]) == row["barcode"]) > 1:
        bad = True
        row["barcode"] = max(prods["barcode"]) + 1
    if len(str(row["barcode"])) < 3 or len(str(row["barcode"])) > 3:
        bad = True
        for i in range(100, 1000):
            if i not in prods["barcode"]:
                row["barcode"] = i
                break
        return row, bad
    return row, bad


def validate_trans(row: dict, data: list):
    return row, True


def check_db(data, con, cur):
    if len(data) == 0:
        cur.execute("INSERT INTO settings VALUES ('OLProgram', TRUE)")
        con.commit()
        print("updated database")
        return False
    else:
        return True


def get_password():
    con, cur = init()
    data = list(cur.execute("SELECT password FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT password FROM settings"))
    return data[0][0]


def get_show_bill():
    con, cur = init()
    data = list(cur.execute("SELECT show_bill FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT show_bill FROM settings"))
    return bool(data[0])


def update_values(password, show_bill):
    con, cur = init()
    up = pd.DataFrame([{"password": password, "show_bill": show_bill}])
    up.to_sql("settings", con=con, if_exists="replace")
    con.commit()
