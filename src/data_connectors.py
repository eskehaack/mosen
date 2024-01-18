import pandas as pd
import sqlite3


def init():
    con = sqlite3.connect(".\data\settings.db")
    cur = con.cursor()
    return con, cur


def get_prods():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM prods"))
    cols = [
        "barcode",
        "name",
        "price",
        "category",
        "current_stock",
        "initial_stock",
    ]
    if len(data) == 0:
        data = pd.DataFrame(columns=cols)
    else:
        data.columns = cols
    return data


def get_trans():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM transactions"))
    cols = [
        "barcode_user",
        "user",
        "barcode_prod",
        "product",
        "price",
        "timestamp",
    ]
    if len(data) == 0:
        data = pd.DataFrame(columns=cols)
    else:
        data.columns = cols
    return data


def get_users():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM users"))
    cols = ["barcode", "name", "rank", "team"]
    if len(data) == 0:
        data = pd.DataFrame(columns=cols)
    else:
        data.columns = cols
    return data


def get_current_trans():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM temporary"))
    cols = ["barcode_prod", "name"]
    if len(data) == 0:
        data = pd.DataFrame(columns=cols)
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


def reset_current_trans():
    con, cur = init()
    cur.execute("DELETE FROM temporary")
    con.commit()


def upload_values(data: list, table: str):
    con, cur = init()
    n_cols = {"prods": 8, "transactions": 6, "users": 4}
    data = pd.DataFrame(data)
    if n_cols[table] == len(data.columns):
        data.to_sql(name=table, con=con, if_exists="replace", index=False)
        con.commit()
        return "success"
    else:
        return table
