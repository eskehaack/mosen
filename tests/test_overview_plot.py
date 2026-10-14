import pandas as pd
import pytest
from math import isnan

from property_helpers import property_context, property_rng
from src.analytics.overview_plot import (
    create_overview_data,
    create_overview_figure,
    filter_guest_users,
)


SCENARIO_COUNT = 25


def _assert_values_with_nan(actual, expected):
    assert len(actual) == len(expected)
    for actual_value, expected_value in zip(actual, expected):
        if isinstance(expected_value, float) and isnan(expected_value):
            assert isnan(actual_value)
        else:
            assert actual_value == pytest.approx(expected_value)


def _users(rows):
    return pd.DataFrame(rows)


def _products(rows):
    return pd.DataFrame(rows)


def _transactions(rows):
    return pd.DataFrame(rows, columns=["barcode_user", "barcode_prod", "timestamp"])


def _base_users():
    return _users(
        [
            {
                "barcode": "1000",
                "name": "Anna",
                "rank": "Senior",
                "team": "Blue",
                "is_guest": 0,
            },
            {
                "barcode": "1001",
                "name": "Bo",
                "rank": "Junior",
                "team": "Red",
                "is_guest": 0,
            },
            {
                "barcode": "1002",
                "name": "Guest",
                "rank": "Guest",
                "team": "Red",
                "is_guest": 1,
            },
        ]
    )


def _base_products():
    return _products(
        [
            {
                "barcode": "100",
                "name": "Beer",
                "price": 10.0,
                "category": "Drinks",
                "current_stock": 8,
                "initial_stock": 10,
            },
            {
                "barcode": "101",
                "name": "Soda",
                "price": 5.0,
                "category": "Drinks",
                "current_stock": 5,
                "initial_stock": 10,
            },
            {
                "barcode": "102",
                "name": "Chips",
                "price": 4.0,
                "category": "Snacks",
                "current_stock": 3,
                "initial_stock": 6,
            },
        ]
    )


def _base_transactions():
    return _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t1"},
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t2"},
            {"barcode_user": "1000", "barcode_prod": "102", "timestamp": "t3"},
            {"barcode_user": "1001", "barcode_prod": "101", "timestamp": "t4"},
            {"barcode_user": "1002", "barcode_prod": "100", "timestamp": "guest"},
        ]
    )


def _reference_overview_data(prods, transactions, users, plot_col, average=False):
    transactions, users = filter_guest_users(transactions, users)

    if len(transactions) == 0:
        return {"overview_df": [], "ranks": [], "y": []}

    def translation(x, t_dict):
        try:
            ret = t_dict[str(x)]
        except Exception:
            ret = "UNKNOWN"
        return ret

    if plot_col == "products":
        text = lambda x: f"{x} category"
        ranks = [text(cat) for cat in list(prods["category"].unique())]
        rank_dict = {
            str(row["barcode"]): text(row["category"]) for _, row in prods.iterrows()
        }
        transactions["rank"] = transactions["barcode_prod"].apply(
            translation,
            t_dict=rank_dict,
        )

    else:
        text = lambda x: f"{x} {plot_col.lower()}"
        ranks = [text(rank) for rank in list(users[str(plot_col)].unique())]
        rank_dict = {
            str(row["barcode"]): text(row[str(plot_col)])
            for _, row in users.iterrows()
        }

        transactions["rank"] = transactions["barcode_user"].apply(
            translation,
            t_dict=rank_dict,
        )

    prod_dict = {str(row["barcode"]): row["name"] for _, row in prods.iterrows()}
    transactions["prod_names"] = transactions["barcode_prod"].apply(
        translation,
        t_dict=prod_dict,
    )
    overview_df = [
        transactions[transactions["rank"] == rank]
        .value_counts("prod_names")
        .to_dict()
        for rank in ranks
    ]

    if average:
        if plot_col == "products":
            overview_df = [
                {
                    rank: (
                        0
                        if (
                            number := int(
                                prods[prods["category"] == ranks[i][:-9]][
                                    "initial_stock"
                                ].sum()
                            )
                        )
                        == 0
                        else int(count) / number
                    )
                    for rank, count in overview.items()
                }
                for i, overview in enumerate(overview_df)
            ]
        else:
            overview_df = [
                {
                    rank: (
                        0
                        if (
                            number := len(
                                users[
                                    users[str(plot_col)]
                                    == ranks[i][: -(len(plot_col) + 1)]
                                ]
                            )
                        )
                        == 0
                        else int(count) / number
                    )
                    for rank, count in overview.items()
                }
                for i, overview in enumerate(overview_df)
            ]
    y = list(transactions["prod_names"].drop_duplicates())
    return {"overview_df": overview_df, "ranks": ranks, "y": y}


def _generated_overview_inputs(rng):
    user_count = rng.randint(1, 8)
    product_count = rng.randint(1, 6)
    users = _users(
        [
            {
                "barcode": str(1000 + index),
                "name": f"User {index}",
                "rank": rng.choice(["Senior", "Junior", "Guest"]),
                "team": rng.choice(["Blue", "Red", "Green"]),
                "is_guest": 1 if rng.random() < 0.2 else 0,
            }
            for index in range(user_count)
        ]
    )
    if (users["is_guest"].astype(int) != 0).all():
        users.loc[0, "is_guest"] = 0

    prods = _products(
        [
            {
                "barcode": str(100 + index),
                "name": f"Product {index}",
                "price": rng.randint(1, 20),
                "category": rng.choice(["Drinks", "Snacks", "Other"]),
                "current_stock": rng.randint(0, 10),
                "initial_stock": rng.randint(1, 20),
            }
            for index in range(product_count)
        ]
    )
    transactions = _transactions(
        [
            {
                "barcode_user": str(users.sample(1, random_state=rng.randint(0, 999999)).iloc[0]["barcode"]),
                "barcode_prod": str(prods.sample(1, random_state=rng.randint(0, 999999)).iloc[0]["barcode"]),
                "timestamp": f"t{index}",
            }
            for index in range(rng.randint(0, 25))
        ]
    )
    return prods, transactions, users


def test_team_overview_counts_product_purchases_per_team():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "team",
    )

    assert data["ranks"] == ["Blue team", "Red team"]
    assert data["overview_df"] == [{"Beer": 2, "Chips": 1}, {"Soda": 1}]


def test_rank_overview_counts_product_purchases_per_rank():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "rank",
    )

    assert data["ranks"] == ["Senior rank", "Junior rank"]
    assert data["overview_df"] == [{"Beer": 2, "Chips": 1}, {"Soda": 1}]


def test_product_overview_counts_purchases_per_category():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "products",
    )

    assert data["ranks"] == ["Drinks category", "Snacks category"]
    assert data["overview_df"] == [{"Beer": 2, "Soda": 1}, {"Chips": 1}]


def test_product_overview_keeps_category_with_no_transactions():
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t1"},
            {"barcode_user": "1001", "barcode_prod": "101", "timestamp": "t2"},
        ]
    )

    data = create_overview_data(
        _base_products(),
        transactions,
        _base_users(),
        "products",
    )

    assert data["ranks"] == ["Drinks category", "Snacks category"]
    assert data["overview_df"] == [{"Beer": 1, "Soda": 1}, {}]


def test_product_overview_omits_product_with_no_transactions():
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t1"},
            {"barcode_user": "1001", "barcode_prod": "102", "timestamp": "t2"},
        ]
    )

    data = create_overview_data(
        _base_products(),
        transactions,
        _base_users(),
        "products",
    )

    assert data["overview_df"] == [{"Beer": 1}, {"Chips": 1}]
    assert "Soda" not in data["overview_df"][0]
    assert data["y"] == ["Beer", "Chips"]


def test_team_overview_keeps_team_with_no_transactions():
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t1"},
        ]
    )

    data = create_overview_data(
        _base_products(),
        transactions,
        _base_users(),
        "team",
    )

    assert data["ranks"] == ["Blue team", "Red team"]
    assert data["overview_df"] == [{"Beer": 1}, {}]


def test_rank_overview_keeps_rank_with_no_transactions():
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t1"},
        ]
    )

    data = create_overview_data(
        _base_products(),
        transactions,
        _base_users(),
        "rank",
    )

    assert data["ranks"] == ["Senior rank", "Junior rank"]
    assert data["overview_df"] == [{"Beer": 1}, {}]


def test_guest_user_transactions_are_excluded():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "team",
    )

    assert data["overview_df"] == [{"Beer": 2, "Chips": 1}, {"Soda": 1}]
    assert data["y"] == ["Beer", "Chips", "Soda"]


def test_all_guest_user_transactions_return_empty_overview_data():
    transactions = _transactions(
        [
            {"barcode_user": "1002", "barcode_prod": "100", "timestamp": "guest"},
        ]
    )

    data = create_overview_data(
        _base_products(),
        transactions,
        _base_users(),
        "team",
    )

    assert data == {"overview_df": [], "ranks": [], "y": []}


def test_unknown_product_barcode_raises():
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "999", "timestamp": "unknown"},
        ]
    )

    with pytest.raises(IndexError):
        create_overview_data(
            _base_products(),
            transactions,
            _base_users(),
            "team",
        )


def test_empty_transactions_return_empty_overview_data_and_formatted_figure():
    data = create_overview_data(_base_products(), _transactions([]), _base_users(), "team")
    fig = create_overview_figure(data)

    assert data == {"overview_df": [], "ranks": [], "y": []}
    assert len(fig.data) == 0
    assert fig.layout.xaxis.title.text is None
    assert fig.layout.yaxis.title.text == "amount"
    assert fig.layout.yaxis.dtick == 1


def test_average_mode_divides_by_user_count_for_team():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "team",
        average=True,
    )

    assert data["overview_df"] == [{"Beer": 2.0, "Chips": 1.0}, {"Soda": 1.0}]


def test_average_mode_divides_by_category_initial_stock():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "products",
        average=True,
    )

    assert data["overview_df"] == [{"Beer": 0.1, "Soda": 0.05}, {"Chips": 1 / 6}]


def test_product_average_uses_total_category_stock():
    prods = _products(
        [
            {
                "barcode": "100",
                "name": "Beer",
                "price": 10.0,
                "category": "Drinks",
                "current_stock": 8,
                "initial_stock": 10,
            },
            {
                "barcode": "101",
                "name": "Soda",
                "price": 5.0,
                "category": "Drinks",
                "current_stock": 5,
                "initial_stock": 20,
            },
            {
                "barcode": "102",
                "name": "Chips",
                "price": 4.0,
                "category": "Snacks",
                "current_stock": 3,
                "initial_stock": 6,
            },
        ]
    )
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "101", "timestamp": "t1"},
            {"barcode_user": "1001", "barcode_prod": "101", "timestamp": "t2"},
        ]
    )

    data = create_overview_data(
        prods,
        transactions,
        _base_users(),
        "products",
        average=True,
    )

    assert data["overview_df"] == [{"Soda": 2 / 30}, {}]


def test_product_average_returns_zero_when_category_stock_is_zero():
    prods = _products(
        [
            {
                "barcode": "100",
                "name": "Beer",
                "price": 10.0,
                "category": "Drinks",
                "current_stock": 0,
                "initial_stock": 0,
            },
            {
                "barcode": "101",
                "name": "Soda",
                "price": 5.0,
                "category": "Drinks",
                "current_stock": 0,
                "initial_stock": 0,
            },
        ]
    )
    transactions = _transactions(
        [
            {"barcode_user": "1000", "barcode_prod": "100", "timestamp": "t1"},
        ]
    )

    data = create_overview_data(
        prods,
        transactions,
        _base_users(),
        "products",
        average=True,
    )

    assert data["overview_df"] == [{"Beer": 0}]


def test_create_overview_figure_applies_count_chart_formatting():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "team",
    )
    fig = create_overview_figure(data)

    assert fig.layout.xaxis.title.text is None
    assert fig.layout.yaxis.title.text == "amount"
    assert fig.layout.yaxis.dtick == 1
    assert fig.layout.barmode == "relative"


def test_create_overview_figure_uses_expected_product_traces_and_values():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "team",
    )
    fig = create_overview_figure(data)

    assert [trace.name for trace in fig.data] == ["Beer", "Chips", "Soda"]
    assert [list(trace.x) for trace in fig.data] == [
        ["Blue team", "Red team"],
        ["Blue team", "Red team"],
        ["Blue team", "Red team"],
    ]
    _assert_values_with_nan(list(fig.data[0].y), [2, float("nan")])
    _assert_values_with_nan(list(fig.data[1].y), [1, float("nan")])
    _assert_values_with_nan(list(fig.data[2].y), [float("nan"), 1])


def test_create_overview_figure_renders_average_mode_values():
    data = create_overview_data(
        _base_products(),
        _base_transactions(),
        _base_users(),
        "products",
        average=True,
    )
    fig = create_overview_figure(data)

    assert [trace.name for trace in fig.data] == ["Beer", "Chips", "Soda"]
    assert [list(trace.x) for trace in fig.data] == [
        ["Drinks category", "Snacks category"],
        ["Drinks category", "Snacks category"],
        ["Drinks category", "Snacks category"],
    ]
    _assert_values_with_nan(list(fig.data[0].y), [0.1, float("nan")])
    _assert_values_with_nan(list(fig.data[1].y), [float("nan"), 1 / 6])
    _assert_values_with_nan(list(fig.data[2].y), [0.05, float("nan")])


def test_overview_data_matches_reference_for_generated_scenarios():
    seed, rng = property_rng()
    test_name = "test_overview_data_matches_reference_for_generated_scenarios"

    for scenario_index in range(SCENARIO_COUNT):
        context = property_context(test_name, seed, scenario_index)
        prods, transactions, users = _generated_overview_inputs(rng)

        for plot_col in ["team", "rank", "products"]:
            for average in [False, True]:
                actual = create_overview_data(
                    prods.copy(),
                    transactions.copy(),
                    users.copy(),
                    plot_col,
                    average,
                )
                expected = _reference_overview_data(
                    prods.copy(),
                    transactions.copy(),
                    users.copy(),
                    plot_col,
                    average,
                )

                assert actual == expected, context
