import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL
from src.data_connectors import get_trans, get_users, get_prods


def get_revenue():
    trans = get_trans()
    prods = get_prods()
    price_dict = {str(p["barcode"]): p["price"] for _, p in prods.iterrows()}
    trans["price"] = trans["barcode_prod"].apply(
        lambda x: price_dict[str(x)] if str(x) in list(price_dict.keys()) else 0
    )
    try:
        return sum(map(int, list(trans["price"])))
    except:
        return 0


def get_total_income():
    prods = get_prods().to_dict(orient="records")
    try:
        return sum([int(row["initial_stock"]) * int(row["price"]) for row in prods])
    except:
        return 0


def get_current_return():
    prods = get_prods().to_dict(orient="records")
    try:
        return sum([int(row["current_stock"]) * int(row["price"]) for row in prods])
    except:
        return 0


def get_income():
    trans = get_trans()
    users = get_users()
    prods = get_prods()
    price_dict = {str(p["barcode"]): p["price"] for _, p in prods.iterrows()}
    trans["price"] = trans["barcode_prod"].apply(
        lambda x: price_dict[str(x)] if str(x) in list(price_dict.keys()) else 0
    )
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


def get_currently_sold(prod):
    trans = get_trans()
    return len(trans[trans["barcode_prod"] == str(prod["barcode"])])
