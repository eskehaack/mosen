from app import app
import keyboard as k
import time
from dash import dcc, html, callback, Input, Output, State, ctx, no_update
import pandas as pd
import plotly.express as px
import dash_bootstrap_components as dbc
import os
from src.container import Container
from src.analytics.TopUserChartData import TopUserChartData
from src.analytics.product_calculations import get_waste_table
from src.analytics.waste_allocation import get_strategy_options
from src.analytics.trans_calculations import (
    get_revenue,
    get_income,
    get_total_income,
    get_current_return,
)
from src.modals import (
    new_user_modal,
    new_prod_modal,
    update_stock_modal,
    password_modal,
    documentation_modal,
    export_payments_modal,
    remove_transaction_modal,
    bad_rows_mdl,
    edit_modal,
    reset_modal,
    study_users_modal,
)
from src.trans_layout import trans_modal
from src.error_handler import get_error_view_components,append_error,callback_with_error_queue
from src.analytics.overview_plot import create_overview
from src.components import get_upload, get_table
from src import main_page_callbacks  # Register main page callbacks
from src.tables import prod_callbacks  # Register product callbacks
from src.tables import user_callbacks  # Register user callbacks
from src.database.data_connection import (
    get_prods,
    get_trans,
    get_users,
    get_password,
    get_show_bill,
    get_waste,
    get_waste_strategy,
    get_backup_time,
    get_cache_validation_time,
    get_backup_interval_ms,
    get_cache_validation_interval_ms,
    get_bill_preview_waste_extra_percent,
)
from src import cache_validation  # register cache validation callback


def user_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    dbc.Button("Create new user", id="new_user_btn"),
                                    html.Hr(),
                                    dbc.Button(
                                        "Download users",
                                        id={
                                            "index": "users",
                                            "type": "download_trigger_btn",
                                        },
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Edit users",
                                        id="edit_users",
                                    ),
                                    dcc.Download(
                                        id={
                                            "index": "users",
                                            "type": "download_trigger",
                                        }
                                    ),
                                ],
                            ),
                            width=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [
                                    get_table(
                                        "user_table",
                                        get_users().to_dict(orient="records"),
                                        300,
                                    )
                                ],
                            ),
                            width=9,
                        ),
                    ],
                    align="center",
                    style={"height": "100%"},
                ),
                className="show_box",
            ),
            new_user_modal(),
            dcc.Store(id="edit_modal_row"),
            dcc.Store(id={"index": "users", "type": "bad_rows"}),
        ],
    )
    return layout


def product_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    dbc.Button("Create new product", id="new_prod_btn"),
                                    html.Hr(),
                                    dbc.Button("Update stock", id="open_update_stock"),
                                    html.Hr(),
                                    dbc.Button(
                                        "Download Products",
                                        id={
                                            "index": "prods",
                                            "type": "download_trigger_btn",
                                        },
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Edit products",
                                        id="edit_prods",
                                    ),
                                    dcc.Download(
                                        id={
                                            "index": "prods",
                                            "type": "download_trigger",
                                        }
                                    ),
                                ]
                            ),
                            width=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [
                                    get_table(
                                        "prod_table",
                                        get_prods().to_dict(orient="records"),
                                        200,
                                    ),
                                    html.Hr(),
                                    get_table(
                                        "waste_table",
                                        get_waste_table(),
                                        200,
                                    ),
                                ]
                            ),
                            width=9,
                        ),
                    ],
                    align="center",
                ),
                className="show_box",
            ),
            new_prod_modal(),
            update_stock_modal(),
            dcc.Store(id={"index": "prods", "type": "bad_rows"}),
        ]
    )
    return layout


def transaction_settings_layout():
    waste = get_waste()
    users = get_users()
    income_rows = get_income()
    allocated_waste = (
        users[users["waste_cents"].astype(int) >= 0]["waste_cents"].astype(int).sum()
        / 100
    )
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        dbc.Col(
                            html.Div(
                                [
                                    html.P(
                                        f"Initially Projected Revenue: {get_total_income()}"
                                    ),
                                    html.Hr(),
                                    html.P(f"Current Revenue: {get_revenue()}"),
                                    html.Hr(),
                                    html.P(f"Raw Waste: {waste}"),
                                    html.P(f"Allocated Waste: {allocated_waste}"),
                                    html.P(f"Next Strategy: {get_waste_strategy()}"),
                                    html.Hr(),
                                    html.P(f"Stock Value: {get_current_return()}"),
                                    html.Hr(),
                                    dbc.Button(
                                        "Export payments", id="export_payments_btn"
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Download Raw Transactions",
                                        id={
                                            "index": "transactions",
                                            "type": "download_trigger_btn",
                                        },
                                    ),
                                    dcc.Download(
                                        id={
                                            "index": "transactions",
                                            "type": "download_trigger",
                                        }
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Study Users",
                                        id="study_users_btn",
                                    ),
                                    html.Hr(),
                                    dbc.Button(
                                        "Remove selected transaction",
                                        id="remove_transaction_btn",
                                        color="danger",
                                        outline=True,
                                        disabled=True,
                                    ),
                                ]
                            ),
                            width=3,
                        ),
                        dbc.Col(
                            html.Div(
                                [
                                    get_table(
                                        "trans_table",
                                        get_trans().to_dict(orient="records"),
                                        200,
                                        row_selectable="single",
                                    ),
                                    html.Hr(),
                                    html.Label(
                                        "Find user by name or barcode",
                                        htmlFor="income_search",
                                    ),
                                    dbc.Input(
                                        id="income_search",
                                        placeholder="Type a name or scan a barcode",
                                        type="text",
                                        autoComplete="off",
                                    ),
                                    html.Div(
                                        id="income_search_status",
                                        className="text-danger",
                                        style={"minHeight": "24px"},
                                    ),
                                    get_table("income_table", income_rows, 200),
                                ]
                            ),
                            width=9,
                        ),
                    ]
                ),
                className="show_box",
            ),
            dcc.Store(id="placeholder_for_empty_output"),
            export_payments_modal(),
            remove_transaction_modal(),
            study_users_modal(),
            dcc.Download(id="payments_download"),
            dcc.Store(id="pending_transaction_removal"),
            dcc.Store(id="income_table_all_rows", data=income_rows),
            dcc.Store(id="income_lookup_focus"),
            dcc.Store(id={"index": "transactions", "type": "bad_rows"}),
        ],
    )
    return layout


def settings_settings_layout():
    layout = dbc.Container(
        [
            html.Div(
                dbc.Row(
                    [
                        html.Br(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Upload user database: "), width=4),
                                    dbc.Col(get_upload("users")),
                                    dbc.Col(
                                        html.P(
                                            id={
                                                "index": "users",
                                                "type": "show_upload_file",
                                            }
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Waste allocation:"), width=4),
                                    dbc.Col(
                                        dcc.Dropdown(
                                            get_strategy_options(),
                                            value=get_waste_strategy(),
                                            clearable=False,
                                            id="waste_strategy",
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.P("Upload product database: "), width=4
                                    ),
                                    dbc.Col(get_upload("prods")),
                                    dbc.Col(
                                        html.P(
                                            id={
                                                "index": "prods",
                                                "type": "show_upload_file",
                                            }
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.P(
                                            "Upload transaction database \n(not recommended): "
                                        ),
                                        width=4,
                                    ),
                                    dbc.Col(get_upload("transactions")),
                                    dbc.Col(
                                        html.P(
                                            id={
                                                "index": "transactions",
                                                "type": "show_upload_file",
                                            }
                                        ),
                                        width=4,
                                    ),
                                ]
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Bill preview: "), xs=12, lg=4),
                                    dbc.Col(
                                        dbc.Switch(
                                            id="display_bill_switch",
                                            value=get_show_bill(),
                                            className="d-grid gap-2 col-10 mx-auto",
                                        ),
                                        xs=12,
                                        lg=4,
                                    ),
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Extra waste (%)"),
                                                dbc.Input(
                                                    value=get_bill_preview_waste_extra_percent(),
                                                    id="bill_preview_waste_extra_percent",
                                                    type="number",
                                                    min=0,
                                                ),
                                            ]
                                        ),
                                        xs=12,
                                        lg=4,
                                    ),
                                ],
                                id="bill_preview_row",
                                align="center",
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        html.P("Toggle top user chart"), xs=12, lg=4
                                    ),
                                    dbc.Col(
                                        dbc.Switch(
                                            id="toggle_top_user_chart",
                                            value=False,
                                            className="d-grid gap-2 col-10 mx-auto",
                                        ),
                                        xs=12,
                                        lg=4,
                                    ),
                                ],
                                id="top_user_chart_row",
                                align="center",
                            ),
                            width=12,
                        ),
                        dbc.Tooltip(
                            """Forged in response to injustice.

After the Drinker of Cocio claimed his second consecutive OPtur title, the evil Beverage KABS refused to verify his glory in the database.

Now, with the sacred hat-trick complete, this feature ensures that the champions of the Swamp Machine may forever be found, ranked, and remembered.

WARNING: Do not use this on intro trips. It shows individual user data, so only use it for prep trips or similar events.""",
                            className="wide-tooltip",
                            target="toggle_top_user_chart",
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Timers:"), xs=12, lg=4),
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText("Backup (min)"),
                                                dbc.Input(
                                                    value=get_backup_time(),
                                                    id="settings_backup_time",
                                                    type="number",
                                                    minLength=0,
                                                ),
                                            ]
                                        ),
                                        xs=12,
                                        lg=4,
                                    ),
                                    dbc.Col(
                                        dbc.InputGroup(
                                            [
                                                dbc.InputGroupText(
                                                    "Cache validation (min)"
                                                ),
                                                dbc.Input(
                                                    value=get_cache_validation_time(),
                                                    id="settings_cache_validation_time",
                                                    type="number",
                                                    minLength=0,
                                                ),
                                            ]
                                        ),
                                        xs=12,
                                        lg=4,
                                    ),
                                    dbc.Tooltip(
                                        children="Timer for making backups of the database. Timer is set in minutes. Backups are stored in dedicated 'backups' folder. Setting this to 0, means the program will not create backups, and you will be on your own when the app inevitabily fails you",
                                        target="settings_backup_time",
                                        placement="right",
                                    ),
                                    dbc.Tooltip(
                                        children="Timer for checking if the cache is outdated. It should never happen, but just in case it will trigger a frontend error. This check blocks all other queries while it runs, so setting it to a very low value might cause performance issues. Setting it to 0 means the app will never validate the cache, which means that if it ever gets stale, you will be on your own.",
                                        target="settings_cache_validation_time",
                                        className="wide-tooltip",
                                        placement="right",
                                    ),
                                ],
                                id="timers_row",
                                align="center",
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(html.P("Password: "), width=4),
                                    dbc.Col(
                                        dbc.Input(
                                            value=get_password(),
                                            id="settings_password",
                                            type="text",
                                            minLength=1,
                                        ),
                                        width=4,
                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            "Confirm Password",
                                            id="confirm_new_password",
                                            className="d-grid gap-2 col-10 mx-auto",
                                        ),
                                        width=4,
                                        align="center",
                                    ),
                                ],
                                align="center",
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.P(
                                                "Diagnostics",
                                                className="fw-bold mb-1",
                                            ),
                                            html.Small(
                                                "Attach the downloaded ZIP when reporting "
                                                "a problem. Error messages may contain "
                                                "failed input.",
                                                className="text-muted",
                                            ),
                                        ],
                                        xs=12,
                                        lg=4,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Small(
                                                "Logging status",
                                                className="text-muted d-block mb-1",
                                            ),
                                            html.P(
                                                "Checked when Settings opens.",
                                                id="diagnostics_status",
                                                className="mb-0",
                                            ),
                                        ],
                                        xs=12,
                                        lg=4,
                                    ),
                                    dbc.Col(
                                        [
                                            dbc.Button(
                                                "Download diagnostic logs",
                                                id="download_diagnostics_btn",
                                                disabled=True,
                                                className="d-grid gap-2 col-10 mx-auto",
                                            ),
                                            dcc.Download(id="diagnostics_download"),
                                        ],
                                        xs=12,
                                        lg=4,
                                    ),
                                ],
                                id="diagnostics_row",
                                className="g-3",
                                align="center",
                            ),
                            width=12,
                        ),
                        html.Hr(),
                        dbc.Col(
                            [
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.Button(
                                                "Export Barcodes",
                                                id="export_barcodes_btn",
                                                className="d-grid gap-2 col-10 mx-auto",
                                            ),
                                            width=4,
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Reset app",
                                                id="reset_app",
                                                color="danger",
                                                className="d-grid gap-2 col-10 mx-auto",
                                            ),
                                            width=4,
                                        ),
                                        dbc.Col(
                                            dbc.Button(
                                                "Close app",
                                                id="close_app_btn",
                                                className="d-grid gap-2 col-10 mx-auto",
                                            ),
                                            width=4,
                                        ),
                                    ],
                                    align="center",
                                ),
                                dcc.Download(id="pdf_download"),
                            ],
                            width=12,
                        ),
                    ],
                    align="center",
                ),
                className="show_box",
            ),
            dbc.Alert(
                "You removed the password, I set it to OLProgram, as this is the default. Please remember this!!!",
                color="danger",
                id="bad_password_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            dbc.Alert(
                "There was an error in the data that you uploaded, please check the input and try again",
                color="danger",
                id="bad_data_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            dbc.Alert(
                "You have succesfully updated the password!",
                color="success",
                id="new_password_alert",
                is_open=False,
                fade=True,
                duration=4000,
            ),
            bad_rows_mdl(),
            reset_modal(),
        ]
    )
    return layout


def settings_mode_func():
    return dbc.Modal(
        [
            dbc.ModalHeader(html.H1("Settings")),
            dbc.ModalBody(
                dcc.Tabs(
                    id="setting_tabs",
                    children=[
                        dcc.Tab(
                            label="Users",
                            value="users",
                            children=user_settings_layout(),
                            id="user_settings",
                        ),
                        dcc.Tab(
                            label="Products",
                            value="products",
                            children=product_settings_layout(),
                            id="product_settings",
                        ),
                        dcc.Tab(
                            label="Economy",
                            value="economy",
                            children=transaction_settings_layout(),
                            id="economy_settings",
                        ),
                        dcc.Tab(
                            label="Settings",
                            value="settings",
                            children=settings_settings_layout(),
                            id="settings_settings",
                        ),
                    ],
                ),
            ),
        ],
        id="settings_modal",
        fullscreen=True,
        is_open=False,
    )

def top_user_chart_modal():
    data = Container.get(TopUserChartData)
    return dbc.Modal(
        [
            dbc.ModalHeader(html.H1("Top Buyers")),
            dbc.ModalBody([
                html.Div(
                            children=[dcc.Graph(
                                figure=data.get_chart(data.all_products),
                                config={"displayModeBar": False},
                                id="top_user_chart"
                            )],
                            id="top_user_chart_content",
                            className="show_box",
                        ),
                html.Br(),
                html.Div([
                    html.Div(
                        children=[
                            dbc.Button("Select/Deselect All", id="toggle_all_products_button", n_clicks=0),
                            dbc.Checklist(
                                id='products_selector',
                                options=[{'label': product, 'value': product} for product in data.all_products],
                                value=data.all_products,
                                inline=True,
                                className="mb-3"
                            ),
                        ],
                        className="d-flex justify-content-center",
                        style={"gap": "20px"}
                    ),
                ])
            ]),
        ],
        id="top_user_chart_modal",
        fullscreen=True,
        is_open=False,
    )

def layout_func():
    layout = dbc.Container(
        [
            html.Div(
                [
                    *get_error_view_components(),
                    dbc.Col(
                        [
                            dbc.Row(html.Br()),
                            dbc.Row(
                                [
                                    dbc.Col(html.H1(app.title), width=10),
                                    dbc.Col(
                                        dbc.Button(
                                            html.Img(
                                                src="assets/easterEgg.svg",
                                                style={"height": "24px", "width": "24px"},
                                            ),
                                            id="open_top_user_chart",

                                        ),
                                        width=1,
                                        id="open_top_user_chart_wrapper",
                                        style={'visibility': 'hidden'},

                                    ),
                                    dbc.Col(
                                        dbc.Button(
                                            html.Img(
                                                src="assets/sliders.svg",
                                                style={"height": "24px", "width": "24px"},
                                            ),
                                            id="open_settings",
                                        ),
                                        width=1,
                                    ),
                                ],
                            ),
                            dbc.Row(
                                dbc.Input(
                                    id="new_trans_inp",
                                    autoFocus=True,
                                    className="barcode-input",
                                ),
                                justify="center",
                            ),
                        ],
                        width=12,
                    ),
                    html.Div(
                        [
                            dbc.Col(
                                children=dcc.Graph(
                                    figure=create_overview(
                                        graph_col := "team", average=False
                                    ),
                                    id="overview_graph",
                                    config={"displayModeBar": False},
                                ),
                            ),
                            html.Br(),
                            dbc.Col(
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            dbc.RadioItems(
                                                options=[
                                                    {"label": "Teams", "value": "team"},
                                                    {"label": "Ranks", "value": "rank"},
                                                    {"label": "Products", "value": "products",},
                                                ],
                                                value=graph_col,
                                                id="graph_selection",
                                                inline=True,
                                            ),
                                            width=3,
                                        ),
                                        dbc.Col(
                                            dbc.Switch(
                                                id="graph_average",
                                                value=False,
                                                label="Average",
                                            ),
                                        ),
                                    ]
                                )
                            ),
                        ],
                        className="show_box",
                    ),
                ]
            ),
            settings_mode_func(),
            trans_modal(),
            password_modal(),
            documentation_modal(),
            edit_modal(),
            top_user_chart_modal(),
            dcc.Store(id="update_settings"),
            dcc.Store(id="transaction_removal_revision"),
            dcc.Store(id="retain_focus_main", data=None),
            dcc.Store(id="retain_focus_prod", data=None),
            dcc.Store(id="retain_focus_password", data=None),
            dcc.Interval(
                id="backup_interval",
                interval=get_backup_interval_ms(),
                n_intervals=0,  # default ten minutes
            ),
            dcc.Interval(
                id="cache_validation_interval",
                interval=get_cache_validation_interval_ms(),
                n_intervals=0,
            ),
            dcc.Store(id="backup_filename", data=None),
        ]
    )
    return layout


@callback(
    Output("password_modal", "is_open"),
    Input("open_settings", "n_clicks"),
    Input("confirm_password", "n_clicks"),
    Input("password_input", "n_submit"),
    State("password_input", "value"),
)
def open_password(trigger_open, trigger_close, trigger_enter, password):
    trigger = ctx.triggered_id
    if trigger is not None and trigger == "open_settings":
        return True
    elif trigger is not None and (
        trigger == "confirm_password" or trigger == "password_input"
    ):
        if password == get_password():
            return False
    return no_update
@callback(
    Output("settings_modal", "is_open"),
    Output("password_input", "value"),
    Output("error-queue", "data", allow_duplicate=True),
    Input("confirm_password", "n_clicks"),
    Input("password_input", "n_submit"),
    State("password_input", "value"),
    State("error-queue", "data"),
    prevent_initial_call="initial_duplicate",
)
def open_settings(trigger, trigger_enter, password, error_queue):
    if (trigger is not None and trigger > 0) or (
        trigger_enter is not None and trigger_enter > 0
    ):
        if password == get_password():
            return True, "", no_update
        return False, no_update, append_error(error_queue,msg="Wrong Password", src="login")
    return False, no_update, no_update

@callback(
    Output("top_user_chart_modal", "is_open"),
    Output('products_selector', 'options'),
    Output('products_selector', 'value', allow_duplicate=True),
    Input("open_top_user_chart", "n_clicks"),
    prevent_initial_call=True,
)
def open_report(trigger):
    if trigger:
        data = Container.get(TopUserChartData)
        data.refresh()
        options = [{'label': product, 'value': product} for product in data.all_products]
        return True, options, data.all_products
    return no_update, no_update, no_update

@callback(
    Output("top_user_chart", "figure"),
    Input("top_user_chart_modal", "is_open"),
    Input("products_selector", "value"),
)
def update_top_user_chart(is_open,selected_traces):
    if not is_open:
        return no_update
    fig = Container.get(TopUserChartData).get_chart(selected_traces)
    fig.update_layout(
        legend_itemclick=False,
        legend_itemdoubleclick=False,
        xaxis={'categoryorder': 'total descending'}
    )
    return fig

@callback(
    Output("open_top_user_chart_wrapper", "style"),
    Input("toggle_top_user_chart", "value"),
    State("open_top_user_chart_wrapper", "style"),
    prevent_initial_call=True
)
def toggle_visibility(value, current_style):
    if value:
        return {"visibility": "visible"}
    return {"visibility": "hidden"}

@app.callback(
    Output('products_selector', 'value'),
    Input('toggle_all_products_button', 'n_clicks'),
    State('products_selector', 'value'),
)
def toggle_checkboxes(n_clicks, current_values):
    if not n_clicks:
        return no_update
    current_values = current_values or []
    product_names = Container.get(TopUserChartData).all_products

    if set(product_names).issubset(current_values):
        return []
    return product_names


@callback(
    Output("user_settings", "children"),
    Output("product_settings", "children"),
    Output("economy_settings", "children"),
    Input("setting_tabs", "value"),
    Input("settings_modal", "is_open"),
    Input("confirm_prod", "n_clicks"),
    Input("confirm_user", "n_clicks"),
    Input("delete_data_btn", "n_clicks"),
    Input("confirm_new_stock", "n_clicks"),
    Input("confirm_payments", "n_clicks"),
    Input("transaction_removal_revision", "data"),
)
def update_settings_layout(
    trigger,
    settings_open,
    prods_trigger,
    user_trigger,
    reset_trigger,
    stock_trigger,
    payments_trigger,
    transaction_removal_revision=None,
):
    #Currently works by guessing that any db changes are done 1 sec after a callback possibly changing anything
    #Ideally this is moved to only trigger after a callback sucessfully changes db.
    if all(
        action is None
        for action in [
            prods_trigger,
            user_trigger,
            reset_trigger,
            stock_trigger,
            payments_trigger,
            transaction_removal_revision,
            settings_open,
        ]
    ):
        return no_update, no_update, no_update
    time.sleep(1)
    return (
        user_settings_layout(),
        product_settings_layout(),
        transaction_settings_layout(),
    )


@callback(
    Output("documentation_modal", "is_open"),
    Input("open_documentation", "n_clicks"),
    Input("password_modal", "is_open"),
    prevent_initial_call=True,
)
def toggle_documentation(open_clicks, password_open):
    if not password_open:
        return False
    if ctx.triggered_id == "open_documentation" and open_clicks:
        return True
    return no_update


@callback(
    Output("close_app_btn", "disabled"),
    Input("close_app_btn", "n_clicks"),
)
def close_appI(trigger):
    if trigger is not None:
        k.unhook_all()
        k.send("alt+f4")
    return no_update
