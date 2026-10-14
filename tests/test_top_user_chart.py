import pandas as pd
import pytest
from dash import no_update

from src import main_layout
from src.analytics.TopUserChartData import TopUserChartData
from src.container import Container
from src.database.data_connection import Database, add_transactions, upload_values


@pytest.fixture
def top_chart_db(tmp_path):
    db = Database(str(tmp_path / "top_chart.db"))
    Container.set(Database, db)
    Container.set(TopUserChartData, TopUserChartData())
    yield db
    Container.reset()


def add_product(name="Beer"):
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 123,
                    "name": name,
                    "price": 2.5,
                    "category": "Beverage",
                    "current_stock": 7,
                    "initial_stock": 10,
                }
            ]
        ),
        "prods",
    )


def add_user():
    upload_values(
        pd.DataFrame(
            [
                {
                    "barcode": 1000,
                    "name": "Alice",
                    "rank": "R",
                    "team": "T",
                    "is_guest": 0,
                }
            ]
        ),
        "users",
    )


def add_transaction():
    add_transactions(
        pd.DataFrame(
            [
                {
                    "barcode_user": 1000,
                    "barcode_prod": 123,
                    "timestamp": "2026-01-01 10:00:00",
                }
            ]
        )
    )


def test_open_report_refreshes_options_and_selected_values(top_chart_db):
    add_product()

    is_open, options, value = main_layout.open_report(1)

    assert is_open is True
    assert options == [{"label": "Beer", "value": "Beer"}]
    assert value == ["Beer"]


def test_open_report_ignores_missing_click(top_chart_db):
    assert main_layout.open_report(None) == (no_update, no_update, no_update)


def test_update_top_user_chart_handles_no_selection(top_chart_db):
    add_product()
    Container.get(TopUserChartData).refresh()

    fig = main_layout.update_top_user_chart(True, None)

    assert fig.layout.xaxis.categoryorder == "total descending"
    assert fig.layout.xaxis.title.text is None
    assert fig.layout.yaxis.title.text == "amount"
    assert fig.layout.yaxis.dtick == 1


def test_top_user_chart_uses_clean_axis_labels(top_chart_db):
    add_product()
    add_user()
    add_transaction()
    Container.get(TopUserChartData).refresh()

    fig = main_layout.update_top_user_chart(True, ["Beer"])

    assert fig.layout.xaxis.title.text is None
    assert fig.layout.yaxis.title.text == "amount"
    assert fig.layout.yaxis.dtick == 1


def test_toggle_checkboxes_handles_empty_current_values(top_chart_db):
    add_product()
    Container.get(TopUserChartData).refresh()

    assert main_layout.toggle_checkboxes(1, None) == ["Beer"]
