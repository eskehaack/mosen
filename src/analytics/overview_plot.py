from math import nan

from plotly import graph_objects as go
from src.analytics.bar_chart_format import format_count_bar_chart
from src.database.data_connection import (
    get_prods,
    get_trans,
    get_users,
)


def filter_guest_users(transactions, users):
    users = users[users["is_guest"].astype(int) != 1]

    valid_barcodes = set(users["barcode"].astype(str))
    transactions = transactions[
        transactions["barcode_user"].astype(str).isin(valid_barcodes)
    ]
    return transactions, users


def create_overview_data(prods, transactions, users, plot_col, average=False):
    transactions, users = filter_guest_users(transactions, users)

    if len(transactions) == 0:
        return {"overview_df": [], "ranks": [], "y": []}

    transactions = transactions.copy()
    users = users.copy()
    prods = prods.copy()
    transactions["barcode_user"] = transactions["barcode_user"].astype(str)
    transactions["barcode_prod"] = transactions["barcode_prod"].astype(str)
    users["barcode"] = users["barcode"].astype(str)
    prods["barcode"] = prods["barcode"].astype(str)

    if plot_col == "products":
        text = lambda x: f"{x} category"
        ranks = [text(cat) for cat in list(prods["category"].unique())]
        product_lookup = prods[["barcode", "name", "category"]].rename(
            columns={
                "barcode": "barcode_prod",
                "name": "prod_names",
                "category": "rank_value",
            }
        )
        transactions = transactions.merge(
            product_lookup,
            on="barcode_prod",
            how="left",
        )
        transactions["rank"] = transactions["rank_value"].apply(text)

    else:
        text = lambda x: f"{x} {plot_col.lower()}"
        ranks = [text(rank) for rank in list(users[str(plot_col)].unique())]
        user_lookup = users[["barcode", str(plot_col)]].rename(
            columns={"barcode": "barcode_user", str(plot_col): "rank_value"}
        )
        product_lookup = prods[["barcode", "name"]].rename(
            columns={"barcode": "barcode_prod", "name": "prod_names"}
        )
        transactions = transactions.merge(
            user_lookup,
            on="barcode_user",
            how="left",
        ).merge(
            product_lookup,
            on="barcode_prod",
            how="left",
        )
        transactions["rank"] = transactions["rank_value"].apply(text)

    if transactions["prod_names"].isna().any():
        raise IndexError("Transaction references an unknown product barcode")

    counts = (
        transactions.groupby(["rank", "prod_names"], sort=False)
        .size()
        .rename("count")
        .reset_index()
    )

    if average:
        if plot_col == "products":
            category_stock = (
                prods.assign(
                    initial_stock=prods["initial_stock"].astype(int),
                    rank=prods["category"].apply(text),
                )
                .groupby("rank", sort=False)["initial_stock"]
                .sum()
                .to_dict()
            )
            denominators = counts["rank"].map(category_stock)
            counts["count"] = counts["count"].astype(int).div(denominators).where(
                denominators != 0,
                0,
            )
        else:
            user_counts = users[str(plot_col)].apply(text).value_counts().to_dict()
            denominators = counts["rank"].map(user_counts)
            counts["count"] = counts["count"].astype(int).div(denominators).where(
                denominators != 0,
                0,
            )

    grouped_counts = {
        rank: dict(zip(group["prod_names"], group["count"]))
        for rank, group in counts.groupby("rank", sort=False)
    }
    overview_df = [grouped_counts.get(rank, {}) for rank in ranks]
    y = list(counts["prod_names"].drop_duplicates())
    return {"overview_df": overview_df, "ranks": ranks, "y": y}


def create_overview_figure(overview_data):
    fig = go.Figure()
    for product_name in overview_data["y"]:
        fig.add_bar(
            name=product_name,
            x=overview_data["ranks"],
            y=[
                rank_counts.get(product_name, nan)
                for rank_counts in overview_data["overview_df"]
            ],
        )

    fig.update_layout(barmode="relative")
    return format_count_bar_chart(fig)


def create_overview(plot_col, average=False):
    prods = get_prods()
    transactions = get_trans()
    users = get_users()
    return create_overview_figure(
        create_overview_data(prods, transactions, users, plot_col, average)
    )
