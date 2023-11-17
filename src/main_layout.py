from dash import dcc, html, callback, Input, Output
import plotly.express as px
import dash_bootstrap_components as dbc
from dash import dash_table
from src.tables.user_table import get_users
from src.tables.prod_table import get_prods, get_waste
from src.tables.trans_table import get_trans, get_revenue, get_income
from src.modals import new_user_modal, new_prod_modal, update_stock_modal
from src.trans_layout import trans_modal
from src.main_page_callbacks import create_overview
from app import app

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
    layout = dbc.Container([
        dbc.Row([
                dbc.Col(
                    html.Div([
                        dbc.Button("Create new product", id="new_prod_btn"),
                        html.Hr(),
                        dbc.Button("Update stock", id='open_update_stock')
                    ]),
                    width=3
                ),
                dbc.Col(
                    html.Div([
                        dash_table.DataTable(id="prod_table", data=get_prods().to_dict(orient="records"))
                    ]),
                    width=9
                )
            ],
            align="center"
        ),
        new_prod_modal(),
        update_stock_modal()
    ])
    return layout

def transaction_settings_layout():
    layout = dbc.Container([
        dbc.Row(
            [
                dbc.Col(
                    html.Div([
                        html.P(f"Total revenue: {get_revenue()}"),
                        html.Hr(),
                        html.P(f"Total waste generated: {get_waste()}")
                    ]),
                    width=3
                ),
                dbc.Col(
                    html.Div(
                        [
                            dash_table.DataTable(
                                id="trans_table", 
                                data=get_trans()[['barcode_user', 'user', 'product', 'price', 'timestamp']].to_dict(orient="records"),
                                style_table={'height': '300px', 'overflowY': 'auto'},
                            ),
                            html.Hr(),
                            dash_table.DataTable(
                                id="income_table", 
                                data=get_income(),
                                style_table={'height': '300px', 'overflowY': 'auto'},
                            ),
                        ]
                        ),
                    width=9
                )
            ]
        )
    ])
    return layout

settings_modal = dbc.Modal([
            dbc.ModalHeader(html.H1("Settings")),
            
            dbc.ModalBody(
                dcc.Tabs(id="setting_tabs", children=[
                    dcc.Tab(label='Users', value='users', children=user_settings_layout(), id="user_settings"),
                    dcc.Tab(label='Products', value='products', children=product_settings_layout(), id="product_settings"),
                    dcc.Tab(label='Economy', value='economy', children=transaction_settings_layout(), id="economy_settings"),
                ]),
            )

        ],
        id="settings_modal",
        fullscreen=True,
        is_open=False     
    )

def layout_func():
    
    layout = dbc.Container(
        [
            html.Div(
                [
                    dbc.Col(
                        [
                            dbc.Row(html.Br()),
                            dbc.Row(
                                [
                                    dbc.Col(html.H1(app.title), width=11),
                                    dbc.Col(dbc.Button(html.I(className="bi bi-sliders"), id="open_settings"), width=1),
                                ],
                            ),
                            dbc.Row(
                                dbc.Input(
                                    id="new_trans_inp",
                                    autoFocus=True
                                ),
                            )
                        ],
                        width=12
                    ),
                    html.Div(
                        [
                            dbc.Col(
                                children=dcc.Graph(figure=create_overview('team'), id="overview_graph", config={"displayModeBar": False}),
                            )
                        ]
                    ),
                ]
            ),
            settings_modal,
            trans_modal(),
        ]
    )
    
    return layout

@callback(
    Output("settings_modal", "is_open"),
    Input("open_settings", "n_clicks")
)
def open_settings(trigger):
    if trigger is not None and trigger > 0:
        return True
    return False

@callback(
    Output("user_settings", "children"),
    Output("product_settings", "children"),
    Output("economy_settings", "children"),
    Input("setting_tabs", "value")
)
def update_trans_table(trigger):
    return user_settings_layout(), product_settings_layout(), transaction_settings_layout()