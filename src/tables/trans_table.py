import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL

def get_trans(path):
    return pd.read_csv(path)

def get_revenue(trans_path):
    try:
        return sum(map(int, list(get_trans(trans_path)['price'])))
    except KeyError:
        return 0
    
def get_income(trans_path, users_path):
    trans = get_trans(trans_path)
    users = pd.read_csv(users_path)
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