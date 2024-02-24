import sqlite3
import os
import pandas as pd

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
