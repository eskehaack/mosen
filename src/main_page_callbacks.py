from dash import Output, Input, State, callback, ctx, no_update
import pandas as pd
import plotly.express as px
from src.connection import update_values

def create_overview(plot_col):   
    transactions = pd.read_csv("data/transactions.csv")
    users = pd.read_csv("data/users.csv")
    prods = pd.read_csv("data/prods.csv")
    
    concatinated_dict = {row['name']: row[plot_col] for i, row in users.iterrows()}
    ranks = list(users[plot_col].unique())
    
    overview_df = [0 for _ in range(len(ranks))]
    trans_dict = {prod: 0 for prod in prods['name']}
    for i, rank in enumerate(ranks):
        temp = trans_dict.copy()
        temp['rank'] = rank
        overview_df[i] = temp
    
    for i, row in transactions.iterrows():
        overview_df[ranks.index(concatinated_dict[row['user']])][row['product']] += 1
    return px.bar(overview_df, x = ranks, y = list(prods['name']))

@callback(
    Output("overview_graph", "figure"),
    Input("new_trans_modal", "is_open")
)
def update_overview_graph(trans_modal_open):
    if not (ctx.triggered_id is not None and trans_modal_open == False):
        return no_update

    return create_overview("team")

@callback(
    Output("update_settings", "data"),
    Input("confirm_settings", "n_clicks"),
    State("settings_password", "value"),
    State("user_file", "value"),
    State("trans_file", "value"),
    State("prod_file", "value"),
)
def update_settings(trigger, password, user_file, trans_file, prod_file):
    if trigger is None:
        return None
    update_values(password, prod_file, trans_file, user_file)
    return None