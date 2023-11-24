import pandas as pd

def get_prods(path):
    return pd.read_csv(path)

def get_trans(path):
    return pd.read_csv(path)

def get_users(path):
    return pd.read_csv(path)