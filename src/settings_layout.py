from dash import dcc, html, callback, Input, Output
import dash_bootstrap_components as dbc
from dash import dash_table
from src.tables.user_table import get_users
from src.tables.prod_table import get_prods
from src.modals import new_user_modal

def user_settings_layout():
    layout = dbc.Container([
            dbc.Row(
                [
                    dbc.Col(
                        html.Div([
                                dbc.Button("Create new user", id="new_user_btn"),
                            ],
                        ),
                        width=3
                    ),
                    dbc.Col(
                        html.Div([
                                dash_table.DataTable(
                                    id="user_table", 
                                    data=get_users().to_dict(orient="records"), 
                                    row_deletable=True,
                                )
                            ],
                        ),
                        width=9
                    )
                ],
                align="center",
                style={"height": "100%"}
            ),
            new_user_modal()
        ],
    )
    return layout

def product_settings_layout():
    layout = html.Div([
        dbc.Row([
            dbc.Col(
                html.Div([
                    dbc.Button("Create new product", id="new_prod_btn"),
                    html.Br(),
                    dbc.Button("Exit", id="exit_btn_prod")
                ],
                style={"border":"2px black solid"}),
                width=3
            ),
            dbc.Col(
                html.Div([
                    dash_table.DataTable(id="prod_table", data=get_prods().to_dict(orient="records"))
                ],
                style={"border":"2px black solid"}),
                width=10
            )
        ])
    ])
    return layout

def layout_func():
    
    layout = html.Div([
        html.H1("Settings"),
        
        dcc.Tabs(id="setting_tabs", children=[
            dcc.Tab(label='Users', children=user_settings_layout(), id="user_settings"),
            dcc.Tab(label='Products', children=product_settings_layout(), id="product_settings"),
            dcc.Tab(label='Economy', children=html.H1("test"), id="economy_settings"),
        ]),

    ])
    
    return layout