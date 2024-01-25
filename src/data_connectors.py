import pandas as pd
from numpy import array
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
    n_cols = {"prods": 6, "transactions": 6, "users": 4}
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
    print(data)
    users = pd.DataFrame(data)
    bad = False
    if sum(array(users["barcode"]) == row["barcode"]) > 1:
        bad = True
        row["barcode"] = max(users["barcode"]) + 1
        print(row)
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
