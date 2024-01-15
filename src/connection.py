import sqlite3
import pandas as pd


def init():
    con = sqlite3.connect(".\data\settings.db")
    cur = con.cursor()
    return con, cur


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
