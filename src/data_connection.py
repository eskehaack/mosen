import os

import pandas as pd
from numpy import array
from datetime import datetime
import sqlite3
import keyboard as k

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

def get_query(query:str,columns:list) -> pd.DataFrame:
    _, cur = init()
    data = pd.DataFrame(cur.execute(query),columns=columns)
    if len(data) == 0:
        data = pd.DataFrame(columns=columns)
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
    n_cols = {"prods": 6, "transactions": 3, "users": 4}
    validation = {
        "prods": validate_prod,
        "transactions": validate_trans,
        "users": validate_user,
    }

    bad_rows = list()
    good_rows = list()
    for row in data:
        row, bad = validation[table](row, data)
        for col, val in row.items():
            if val is None or str(val).replace(" ", "") == "":
                row[col] = "Unkown"
                bad = True
        if bad:
            bad_rows.append(row)
        else:
            good_rows.append(row)

    data = pd.DataFrame(good_rows)
    if n_cols[table] == len(data.columns):
        data.to_sql(name=table, con=con, if_exists="replace", index=False)
        con.commit()
        return "success", bad_rows
    else:
        return table, None


def add_transactions(trans_df):
    con, cur = init()
    trans_df.to_sql(name="transactions", con=con, if_exists="append", index=False)


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
    actual_colums = [
        "barcode",
        "name",
        "price",
        "category",
        "current_stock",
        "initial_stock",
    ]
    if set(prods.columns) != set(actual_colums):
        bad = True
        print(
            f"It seems that there is a mismatch in the column names of your file. Make sure that the columns are: \n{actual_colums}"
        )
        return row, bad
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
    prods = get_prods()
    if str(row["barcode_prod"]) not in list(prods["barcode"]):
        return row, True
    return row, False


def check_db(data, con, cur):
    if len(data) == 0:
        out = cur.execute("SELECT * FROM settings")
        cur.execute("INSERT INTO settings VALUES ('OLProgram', 'True', '0', '10')")
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


def get_backup_time():
    con, cur = init()
    data = list(cur.execute("SELECT backup FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT backup FROM settings"))
    return int(data[0][0])


def get_show_bill():
    con, cur = init()
    data = list(cur.execute("SELECT show_bill FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT show_bill FROM settings"))
    return data[0][0] == "True"


def get_waste():
    con, cur = init()
    data = list(cur.execute("SELECT waste FROM settings"))
    if not check_db(data, con, cur):
        data = list(cur.execute("SELECT waste FROM settings"))
    return int(data[0][0])


def update_values(password=None, show_bill=None, waste=None, backup_time=None):
    con, cur = init()
    inps = {
        "password": password,
        "show_bill": show_bill,
        "waste": waste,
        "backup": backup_time,
    }
    for key, value in inps.items():
        if value is None:
            continue
        cur.execute(f"""UPDATE settings SET "{key}" = '{value}'""")
        con.commit()


def reset_all_tables():
    con, cur = init()
    for table in table_defs().keys():
        cur.execute(f"DROP TABLE {table}")
        con.commit()
    con, cur = init()
    k.unhook_all()
    k.send("alt+f4")
