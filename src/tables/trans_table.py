import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL

def get_trans():
    return pd.read_csv("data/transactions.csv")

def get_revenue():
    try:
        return sum(map(int, list(get_trans()['price'])))
    except KeyError:
        return 0
    
def get_income():
    trans = get_trans()
    users = pd.read_csv("data/users.csv")
    user_income = list()
    for user in set(trans['barcode_user']):
        user_income.append(
            {
                'barcode': user, 
                'name': str(users[users['barcode'] == int(user)]['name'][0]),
                'price': sum(list(trans[trans['barcode_user'] == int(user)]['price']))
            }
        )
    return user_income