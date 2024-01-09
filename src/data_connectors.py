import pandas as pd
import sqlite3


def init():
    con = sqlite3.connect(".\data\settings.db")
    cur = con.cursor()
    return con, cur


def get_prods():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM prods"))
    if len(data) == 0:
        return False
    data.columns = [
        "barcode",
        "name",
        "price",
        "category",
        "current_stock",
        "initial_stock",
        "waste",
        "sold",
    ]
    return data


def get_trans():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM transactions"))
    if len(data) == 0:
        return False
    data.columns = [
        "barcode_user",
        "user",
        "barcode_prod",
        "product",
        "price",
        "timestamp",
    ]
    return data


def get_users():
    con, cur = init()
    data = pd.DataFrame(cur.execute("SELECT * FROM users"))
    if len(data) == 0:
        return False
    data.columns = ["barcode", "name", "rank", "team"]
    return data
