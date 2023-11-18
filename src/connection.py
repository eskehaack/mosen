import sqlite3

def init():
    con = sqlite3.connect(".\data\settings.db")
    cur = con.cursor()
    return con, cur

def get_password():
    con, cur = init()
    data = list(cur.execute("SELECT password FROM settings"))
    if len(data) == 0:
        cur.execute("INSERT INTO settings VALUES ('OLProgram', '.\\data\\prods.csv', '.\\data\\transactions.csv', '.\\data\\users.csv')")
        con.commit()
        data = list(cur.execute("SELECT password FROM settings"))
    return data[0][0]

def get_paths():
    con, cur = init()
    data = list(cur.execute("SELECT prods_table, trans_table, users_table FROM settings"))
    if len(data) == 0:
        cur.execute("INSERT INTO settings VALUES ('OLProgram', '.\\data\\prods.csv', '.\\data\\transactions.csv', '.\\data\\users.csv')")
        con.commit()
        data = list(cur.execute("SELECT prods_table, trans_table, users_table FROM settings"))
    return data[0]

def update_values(password, prod_file, trans_file, user_file):
    con, cur = init()
    inputs = [password, prod_file, trans_file, user_file]
    cols = ["password", "prods_table", "trans_table", "users_table"]
    sqlify = ", ".join([f"{cols[i]} = '{val}'" for i, val in enumerate(inputs) if val is not None and val != ""])
    cur.execute(f"UPDATE settings SET {sqlify} WHERE TRUE")
    con.commit()