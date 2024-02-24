import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL
from src.data_connectors import get_trans, get_users


def get_revenue():
    try:
        return sum(map(int, list(get_trans()["price"])))
    except:
        return 0


def get_income():
    trans = get_trans()
    users = get_users()
    user_income = list()
    if len(trans) > 0:
        price = lambda x: sum(map(int, trans[trans["barcode_user"] == str(x)]["price"]))
        n_prods = lambda x: len(trans[trans["barcode_user"] == str(x)])
    else:
        price = lambda x: 0
        n_prods = lambda x: 0
    for _, user_row in users.iterrows():
        barcode = str(user_row["barcode"])
        user_income.append(
            {
                "barcode": barcode,
                "name": str(user_row["name"]),
                "rank": str(user_row["rank"]),
                "team": str(user_row["team"]),
                "#products": n_prods(barcode),
                "price": price(barcode),
            }
        )
    return user_income


def get_currently_sold(prod: str, initial_stock: str):
    trans = get_trans()
    return len(trans[trans["barcode_prod"] == prod["barcode"]])
