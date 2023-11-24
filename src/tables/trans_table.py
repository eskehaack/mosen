import pandas as pd
from dash import callback, Output, Input, State, html, ctx, ALL
from src.data_connectors import get_trans, get_users

def get_revenue(trans_path):
    try:
        return sum(map(int, list(get_trans(trans_path)['price'])))
    except KeyError:
        return 0
    
def get_income(trans_path, users_path):
    trans = get_trans(trans_path)
    users = get_users(users_path)
    user_income = list()
    for user in set(trans['barcode_user']):
        user_row = users[users['barcode'] == int(user)]
        user_income.append(
            {
                'barcode': user, 
                'name': str(user_row['name'][0]),
                'rank': str(user_row['rank'][0]),
                'team': str(user_row['team'][0]),
                'price': sum(list(trans[trans['barcode_user'] == int(user)]['price']))
            }
        )
    return user_income

@callback(
    Output("placeholder_for_empty_output", "data"),
    Input("export_payments", "n_clicks"),
    State("user_file", "value"),
    State("trans_file", "value"),
    
)
def export_payments(trigger, user_path, trans_path):
    if trigger is not None and trigger > 0:
        data = get_income(trans_path, user_path)
        data = pd.DataFrame(data).to_csv("./data/payments.csv")
    
    return None