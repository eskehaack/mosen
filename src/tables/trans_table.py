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
    for user in set(trans["barcode_user"]):
        user_row = users[users["barcode"] == int(user)]
        user_income.append(
            {
                "barcode": user,
                "name": str(user_row["name"][0]),
                "rank": str(user_row["rank"][0]),
                "team": str(user_row["team"][0]),
                "price": sum(list(trans[trans["barcode_user"] == int(user)]["price"])),
            }
        )
    return user_income


@callback(
    Output("placeholder_for_empty_output", "data"),
    Input("export_payments", "n_clicks"),
)
def export_payments(trigger):
    if trigger is not None and trigger > 0:
        data = get_income()
        data = pd.DataFrame(data).to_csv("./data/payments.csv")

    return None


def get_currently_sold(prod: str, initial_stock: str):
    trans = get_trans()
    return initial_stock - len(trans[trans["product"] == prod["name"]])
