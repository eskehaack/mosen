import time
import types
from threading import Event, Thread

import pandas as pd
import pytest
from dash import no_update

from src import main_page_callbacks
from src import trans_layout
from src.analytics.overview_plot import create_overview_data, create_overview_figure
from src.container import Container
from src.database.data_connection import (
    Database,
    get_prods,
    get_trans,
    get_users,
    update_values,
)

#Testing that key workflows are respondant under large loads.
#We test callback time, not render, transport or other parts.
#This is machine dependent, so tune it to your machine and see if performance is good enough.
OPEN_WORKFLOW_LIMIT_SECONDS = 0.3
PRODUCT_SCAN_WORKFLOW_LIMIT_SECONDS = 0.1
SUBMIT_WORKFLOW_LIMIT_SECONDS = 0.4
CHECKOUT_PHASE_LIMIT_SECONDS = 0.15
CART_RESET_PHASE_LIMIT_SECONDS = 0.1
OVERVIEW_PHASE_LIMIT_SECONDS = 0.2
OVERVIEW_DB_READS_PHASE_LIMIT_SECONDS = 0.1
OVERVIEW_DATA_PHASE_LIMIT_SECONDS = 0.1
OVERVIEW_FIGURE_PHASE_LIMIT_SECONDS = 0.1
BURST_SCAN_COUNT = 20
BURST_LIMIT_SECONDS = 0.5
USER_BARCODE = "1000"
PRODUCT_BARCODE = "100"
AVG_PURCHASES_PER_USER = 30

@pytest.fixture
def scan_db(tmp_path):
    db = Database(str(tmp_path / "scan_performance.db"))
    Container.set(Database, db)
    _load_realistic_scan_data(db)
    yield db
    Container.reset()


@pytest.fixture
def hot_user_scan_db(tmp_path):
    db = Database(str(tmp_path / "hot_user_scan_performance.db"))
    Container.set(Database, db)
    _load_hot_user_scan_data(db)
    yield db
    Container.reset()


@pytest.fixture
def skewed_category_scan_db(tmp_path):
    db = Database(str(tmp_path / "skewed_category_scan_performance.db"))
    Container.set(Database, db)
    _load_skewed_category_scan_data(db)
    yield db
    Container.reset()


@pytest.fixture
def wide_group_scan_db(tmp_path):
    db = Database(str(tmp_path / "wide_group_scan_performance.db"))
    Container.set(Database, db)
    _load_wide_group_scan_data(db)
    yield db
    Container.reset()


def _load_realistic_scan_data(db):
    users = [
        {
            "barcode": 1000 + index,
            "name": f"User {index}",
            "rank": "Member",
            "team": f"Team {index % 8}",
            "is_guest": 0,
        }
        for index in range(150)
    ]
    products = [
        {
            "barcode": 100 + index,
            "name": f"Product {index}",
            "price": 1 + (index % 20) * 0.5,
            "category": f"Category {index % 6}",
            "current_stock": 500,
            "initial_stock": 600,
        }
        for index in range(80)
    ]
    transactions = [
        {
            "barcode_user": 1000 + (index % 150),
            "barcode_prod": 100 + (index % 80),
            "timestamp": (
                f"01/01/2026 {10 + (index // 3600):02d}:"
                f"{(index // 60) % 60:02d}:{index % 60:02d}"
            ),
        }
        for index in range(2000)
    ]

    db.upload_values_raises(pd.DataFrame(users), "users")
    db.upload_values_raises(pd.DataFrame(products), "prods")
    db._transaction_table.append(pd.DataFrame(transactions))
    update_values(show_bill=True, waste_cents=0)


def _load_hot_user_scan_data(db):
    user_count = 240
    users = _profile_users(user_count=user_count, team_count=13, ranks=("Member", "Leader", "Helper"))
    products = _profile_products(category_count=5)
    hot_user_transactions = [
        _transaction(
            barcode_user=USER_BARCODE,
            barcode_prod=100 + (index % 20),
            index=index,
        )
        for index in range(200)
    ]
    other_transactions = [
        _transaction(
            barcode_user=1001 + (index % 239),
            barcode_prod=100 + ((index * 7) % 80),
            index=200 + index,
        )
        for index in range(user_count*AVG_PURCHASES_PER_USER)
    ]
    _load_scan_data(db, users, products, hot_user_transactions + other_transactions)


def _load_skewed_category_scan_data(db):
    users = _profile_users(user_count=220, team_count=7, ranks=("Rover", "Senior", "Junior"))
    products = _profile_products(category_count=5)
    category_product_ranges = [
        range(100, 132),
        range(132, 152),
        range(152, 166),
        range(166, 174),
        range(174, 180),
    ]
    category_weights = [1500, 600, 320, 60, 20]
    transactions = []

    for category_index, count in enumerate(category_weights):
        product_barcodes = list(category_product_ranges[category_index])
        for local_index in range(count):
            transaction_index = len(transactions)
            transactions.append(
                _transaction(
                    barcode_user=1000 + (transaction_index % 220),
                    barcode_prod=product_barcodes[local_index % len(product_barcodes)],
                    index=transaction_index,
                )
            )

    _load_scan_data(db, users, products, transactions)


def _load_wide_group_scan_data(db):
    user_count = 280
    users = _profile_users(
        user_count=user_count,
        team_count=10,
        ranks=("Rover", "Senior", "Junior", "Mini", "Leader"),
    )
    products = _profile_products(category_count=5)
    transactions = [
        _transaction(
            barcode_user=1000 + ((index * 37) % 280),
            barcode_prod=100 + ((index * 11) % 80),
            index=index,
        )
        for index in range(AVG_PURCHASES_PER_USER*user_count)
    ]
    _load_scan_data(db, users, products, transactions)


def _profile_users(user_count, team_count, ranks):
    return [
        {
            "barcode": 1000 + index,
            "name": f"User {index}",
            "rank": ranks[index % len(ranks)],
            "team": f"Team {index % team_count}",
            "is_guest": 0,
        }
        for index in range(user_count)
    ]


def _profile_products(category_count):
    return [
        {
            "barcode": 100 + index,
            "name": f"Product {index}",
            "price": 1 + (index % 20) * 0.5,
            "category": f"Category {index % category_count}",
            "current_stock": 500,
            "initial_stock": 600,
        }
        for index in range(80)
    ]


def _transaction(barcode_user, barcode_prod, index):
    return {
        "barcode_user": barcode_user,
        "barcode_prod": barcode_prod,
        "timestamp": (
            f"01/01/2026 {10 + (index // 3600):02d}:"
            f"{(index // 60) % 60:02d}:{index % 60:02d}"
        ),
    }


def _load_scan_data(db, users, products, transactions):
    db.upload_values_raises(pd.DataFrame(users), "users")
    db.upload_values_raises(pd.DataFrame(products), "prods")
    db._transaction_table.append(pd.DataFrame(transactions))
    update_values(show_bill=True, waste_cents=0)


def _run_concurrently(actions):
    start_event = Event()
    results = {}
    errors = {}

    def run_action(name, action):
        start_event.wait()
        try:
            results[name] = action()
        except Exception as exc:
            errors[name] = exc

    threads = [
        Thread(target=run_action, args=(name, action))
        for name, action in actions.items()
    ]
    for thread in threads:
        thread.start()

    start = time.perf_counter()
    start_event.set()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - start

    return results, errors, elapsed


def _assert_group_runs_under(label, limit_seconds, action):
    start = time.perf_counter()
    result = action()
    elapsed = time.perf_counter() - start
    assert elapsed < limit_seconds, (
        f"{label} took {elapsed:.3f}s, expected under {limit_seconds:.3f}s"
    )
    return result


def _measure(action):
    start = time.perf_counter()
    result = action()
    elapsed = time.perf_counter() - start
    return result, elapsed


def _format_phase_timings(timings):
    return " ".join(
        f"{phase}={elapsed:.3f}s" for phase, elapsed in timings.items()
    )


def _set_trans_trigger(monkeypatch, trigger_id):
    monkeypatch.setattr(
        trans_layout,
        "ctx",
        types.SimpleNamespace(triggered_id=trigger_id),
    )


def _set_overview_trigger(monkeypatch):
    monkeypatch.setattr(
        main_page_callbacks,
        "ctx",
        types.SimpleNamespace(triggered_id="new_trans_modal"),
    )


def _open_basket(monkeypatch, user_barcode=USER_BARCODE):
    _set_trans_trigger(monkeypatch, "new_trans_inp")
    return trans_layout.open_trans_modal(1, None, user_barcode, None, [])


def _scan_product(monkeypatch, product_barcode=PRODUCT_BARCODE, user_barcode=USER_BARCODE):
    _set_trans_trigger(monkeypatch, "prod_barcode")
    return trans_layout.new_trans(1, product_barcode, user_barcode, [])


def _submit_basket(monkeypatch, user_barcode=USER_BARCODE):
    _set_trans_trigger(monkeypatch, "prod_barcode")
    return trans_layout.open_trans_modal(None, 1, user_barcode, user_barcode, [])


def _reset_cart_display(monkeypatch, user_barcode=USER_BARCODE):
    _set_trans_trigger(monkeypatch, "prod_barcode")
    return trans_layout.new_trans(1, user_barcode, user_barcode, [])


def _refresh_overview(monkeypatch, graph_col="rank", average=False):
    _set_overview_trigger(monkeypatch)
    return main_page_callbacks.update_overview_graph(False, graph_col, average)


def _refresh_overview_parts(graph_col="rank", average=False):
    timings = {}

    inputs, timings["overview_db_reads"] = _measure(
        lambda: {
            "prods": get_prods(),
            "transactions": get_trans(),
            "users": get_users(),
        }
    )
    overview_data, timings["overview_data"] = _measure(
        lambda: create_overview_data(
            inputs["prods"],
            inputs["transactions"],
            inputs["users"],
            graph_col,
            average,
        )
    )
    overview_figure, timings["overview_figure"] = _measure(
        lambda: create_overview_figure(overview_data)
    )

    return overview_figure, timings


def _open_basket_workflow(monkeypatch, user_barcode=USER_BARCODE):
    _set_trans_trigger(monkeypatch, "new_trans_inp")
    return _run_concurrently(
        {
            "open_modal": lambda: trans_layout.open_trans_modal(
                1,
                None,
                user_barcode,
                None,
                [],
            ),
            "transaction_graph": lambda: trans_layout.get_transactions(
                1,
                user_barcode,
                [],
            ),
            "bill_preview": lambda: trans_layout.show_balance(1, user_barcode),
        }
    )


def _product_scan_workflow(
    monkeypatch,
    product_barcode=PRODUCT_BARCODE,
    set_trigger=True,
):
    if set_trigger:
        _set_trans_trigger(monkeypatch, "prod_barcode")
    return _run_concurrently(
        {
            "add_product": lambda: trans_layout.new_trans(
                1,
                product_barcode,
                USER_BARCODE,
                [],
            ),
            "close_guard": lambda: trans_layout.open_trans_modal(
                None,
                1,
                USER_BARCODE,
                product_barcode,
                [],
            ),
        }
    )


def _submit_purchase_workflow(monkeypatch, graph_col="rank", average=False):
    checkout_result = _submit_basket(monkeypatch)
    downstream_results, downstream_errors, _ = _run_concurrently(
        {
            "cart_reset": lambda: _reset_cart_display(monkeypatch),
            "overview": lambda: _refresh_overview(monkeypatch, graph_col, average),
        }
    )
    return checkout_result, downstream_results, downstream_errors


def _measure_submit_phases(monkeypatch, graph_col="rank", average=False):
    timings = {}

    checkout_result, timings["checkout"] = _measure(
        lambda: _submit_basket(monkeypatch)
    )
    cart_reset_result, timings["cart_reset"] = _measure(
        lambda: _reset_cart_display(monkeypatch)
    )
    (overview_result, overview_timings), timings["overview"] = _measure(
        lambda: _refresh_overview_parts(graph_col, average)
    )
    timings.update(overview_timings)

    return (
        {
            "checkout": checkout_result,
            "cart_reset": cart_reset_result,
            "overview": overview_result,
        },
        timings,
    )


def _assert_submit_phases_under_limits(label, results, timings):
    timing_details = _format_phase_timings(timings)

    assert timings["checkout"] < CHECKOUT_PHASE_LIMIT_SECONDS, (
        f"{label} checkout phase exceeded "
        f"{CHECKOUT_PHASE_LIMIT_SECONDS:.3f}s: {timing_details}"
    )
    assert timings["cart_reset"] < CART_RESET_PHASE_LIMIT_SECONDS, (
        f"{label} cart reset phase exceeded "
        f"{CART_RESET_PHASE_LIMIT_SECONDS:.3f}s: {timing_details}"
    )
    assert timings["overview"] < OVERVIEW_PHASE_LIMIT_SECONDS, (
        f"{label} overview phase exceeded "
        f"{OVERVIEW_PHASE_LIMIT_SECONDS:.3f}s: {timing_details}"
    )
    assert timings["overview_db_reads"] < OVERVIEW_DB_READS_PHASE_LIMIT_SECONDS, (
        f"{label} overview DB reads phase exceeded "
        f"{OVERVIEW_DB_READS_PHASE_LIMIT_SECONDS:.3f}s: {timing_details}"
    )
    assert timings["overview_data"] < OVERVIEW_DATA_PHASE_LIMIT_SECONDS, (
        f"{label} overview data phase exceeded "
        f"{OVERVIEW_DATA_PHASE_LIMIT_SECONDS:.3f}s: {timing_details}"
    )
    assert timings["overview_figure"] < OVERVIEW_FIGURE_PHASE_LIMIT_SECONDS, (
        f"{label} overview figure phase exceeded "
        f"{OVERVIEW_FIGURE_PHASE_LIMIT_SECONDS:.3f}s: {timing_details}"
    )

    assert results["checkout"][0] is False
    assert results["checkout"][3] is no_update
    assert results["cart_reset"][1] == ""
    assert results["cart_reset"][2] is no_update
    assert results["overview"] is not no_update


def _load_temporary_basket(db, product_count):
    db.upload_values_raises(
        pd.DataFrame(
            [
                {
                    "barcode_prod": str(100 + (index % 80)),
                    "name": f"Product {index % 80}",
                }
                for index in range(product_count)
            ]
        ),
        "temporary",
    )


def test_scan_user_barcode_opens_basket_workflow_under_limit(scan_db, monkeypatch):
    # Arrange
    _open_basket_workflow(monkeypatch, "1001")

    # Act
    results, errors, elapsed = _open_basket_workflow(monkeypatch)

    # Assert
    assert elapsed < OPEN_WORKFLOW_LIMIT_SECONDS, (
        f"open basket workflow took {elapsed:.3f}s, "
        f"expected under {OPEN_WORKFLOW_LIMIT_SECONDS:.3f}s"
    )
    assert errors == {}
    assert results["open_modal"][0] is True
    assert results["open_modal"][3] is no_update
    assert results["transaction_graph"][1] is no_update
    assert "Current bill" in results["bill_preview"]
    assert len(scan_db._temporary_table.get()) == 0


def test_hot_user_opens_basket_workflow_under_limit(hot_user_scan_db, monkeypatch):
    # Arrange
    _open_basket_workflow(monkeypatch, USER_BARCODE)

    # Act
    results, errors, elapsed = _open_basket_workflow(monkeypatch, USER_BARCODE)

    # Assert
    assert elapsed < OPEN_WORKFLOW_LIMIT_SECONDS, (
        f"hot user open basket workflow took {elapsed:.3f}s, "
        f"expected under {OPEN_WORKFLOW_LIMIT_SECONDS:.3f}s"
    )
    assert errors == {}
    assert results["open_modal"][0] is True
    assert results["transaction_graph"][1] is no_update
    assert "Current bill" in results["bill_preview"]
    assert len(hot_user_scan_db._temporary_table.get()) == 0


def test_scan_product_barcode_workflow_adds_to_basket_under_limit(
    scan_db,
    monkeypatch,
):
    # Arrange
    _open_basket(monkeypatch)
    _scan_product(monkeypatch, "101")
    scan_db.upload_values_raises([], "temporary")

    # Act
    results, errors, elapsed = _product_scan_workflow(monkeypatch)

    # Assert
    assert elapsed < PRODUCT_SCAN_WORKFLOW_LIMIT_SECONDS, (
        f"product scan workflow took {elapsed:.3f}s, "
        f"expected under {PRODUCT_SCAN_WORKFLOW_LIMIT_SECONDS:.3f}s"
    )
    assert errors == {}
    assert results["add_product"][1] == ""
    assert results["add_product"][2] is no_update
    assert results["close_guard"] == (
        no_update,
        no_update,
        no_update,
        no_update,
    )
    assert len(scan_db._temporary_table.get()) == 1


def test_scan_user_barcode_submits_purchase_workflow_under_limit(
    scan_db,
    monkeypatch,
):
    # Arrange
    _refresh_overview(monkeypatch)
    _load_temporary_basket(scan_db, product_count=10)
    transactions_before = len(scan_db._transaction_table.get())

    # Act
    checkout_result, downstream_results, downstream_errors = _assert_group_runs_under(
        "submit purchase workflow",
        SUBMIT_WORKFLOW_LIMIT_SECONDS,
        lambda: _submit_purchase_workflow(monkeypatch),
    )

    # Assert
    assert checkout_result[0] is False
    assert checkout_result[3] is no_update
    assert downstream_errors == {}
    assert downstream_results["cart_reset"][1] == ""
    assert downstream_results["cart_reset"][2] is no_update
    assert downstream_results["overview"] is not no_update
    assert len(scan_db._transaction_table.get()) == transactions_before + 10


def test_submit_phase_diagnostics_baseline(scan_db, monkeypatch):
    # Arrange
    _refresh_overview(monkeypatch)
    _load_temporary_basket(scan_db, product_count=10)
    transactions_before = len(scan_db._transaction_table.get())

    # Act
    results, timings = _measure_submit_phases(monkeypatch)

    # Assert
    _assert_submit_phases_under_limits("baseline submit", results, timings)
    assert len(scan_db._transaction_table.get()) == transactions_before + 10


def test_skewed_category_submit_product_overview_under_limit(
    skewed_category_scan_db,
    monkeypatch,
):
    # Arrange
    _refresh_overview(monkeypatch, graph_col="products", average=True)
    _load_temporary_basket(skewed_category_scan_db, product_count=10)
    transactions_before = len(skewed_category_scan_db._transaction_table.get())

    # Act
    checkout_result, downstream_results, downstream_errors = _assert_group_runs_under(
        "skewed category submit purchase workflow",
        SUBMIT_WORKFLOW_LIMIT_SECONDS,
        lambda: _submit_purchase_workflow(
            monkeypatch,
            graph_col="products",
            average=True,
        ),
    )

    # Assert
    assert checkout_result[0] is False
    assert downstream_errors == {}
    assert downstream_results["cart_reset"][1] == ""
    assert downstream_results["overview"] is not no_update
    assert len(skewed_category_scan_db._transaction_table.get()) == (
        transactions_before + 10
    )


def test_submit_phase_diagnostics_skewed_category_product_overview(
    skewed_category_scan_db,
    monkeypatch,
):
    # Arrange
    _refresh_overview(monkeypatch, graph_col="products", average=True)
    _load_temporary_basket(skewed_category_scan_db, product_count=10)
    transactions_before = len(skewed_category_scan_db._transaction_table.get())

    # Act
    results, timings = _measure_submit_phases(
        monkeypatch,
        graph_col="products",
        average=True,
    )

    # Assert
    _assert_submit_phases_under_limits(
        "skewed category product overview submit",
        results,
        timings,
    )
    assert len(skewed_category_scan_db._transaction_table.get()) == (
        transactions_before + 10
    )


@pytest.mark.parametrize("graph_col", ["team", "rank"])
def test_wide_group_submit_overview_under_limit(
    wide_group_scan_db,
    monkeypatch,
    graph_col,
):
    # Arrange
    _refresh_overview(monkeypatch, graph_col=graph_col)
    _load_temporary_basket(wide_group_scan_db, product_count=10)
    transactions_before = len(wide_group_scan_db._transaction_table.get())

    # Act
    checkout_result, downstream_results, downstream_errors = _assert_group_runs_under(
        f"wide {graph_col} submit purchase workflow",
        SUBMIT_WORKFLOW_LIMIT_SECONDS,
        lambda: _submit_purchase_workflow(monkeypatch, graph_col=graph_col),
    )

    # Assert
    assert checkout_result[0] is False
    assert downstream_errors == {}
    assert downstream_results["cart_reset"][1] == ""
    assert downstream_results["overview"] is not no_update
    assert len(wide_group_scan_db._transaction_table.get()) == transactions_before + 10


@pytest.mark.parametrize("graph_col", ["team", "rank"])
def test_submit_phase_diagnostics_wide_group_overview(
    wide_group_scan_db,
    monkeypatch,
    graph_col,
):
    # Arrange
    _refresh_overview(monkeypatch, graph_col=graph_col)
    _load_temporary_basket(wide_group_scan_db, product_count=10)
    transactions_before = len(wide_group_scan_db._transaction_table.get())

    # Act
    results, timings = _measure_submit_phases(monkeypatch, graph_col=graph_col)

    # Assert
    _assert_submit_phases_under_limits(
        f"wide {graph_col} overview submit",
        results,
        timings,
    )
    assert len(wide_group_scan_db._transaction_table.get()) == transactions_before + 10


def test_rapid_product_scans_drain_under_burst_limit(scan_db, monkeypatch):
    # Arrange
    _open_basket(monkeypatch)
    _set_trans_trigger(monkeypatch, "prod_barcode")
    start_event = Event()
    results = []
    errors = []

    def scan_worker(index):
        start_event.wait()
        try:
            workflow_results, workflow_errors, _ = _product_scan_workflow(
                monkeypatch,
                str(100 + (index % 80)),
                set_trigger=False,
            )
            results.append(workflow_results)
            if workflow_errors:
                errors.append(workflow_errors)
        except Exception as exc:
            errors.append(exc)

    threads = [Thread(target=scan_worker, args=(index,)) for index in range(BURST_SCAN_COUNT)]
    for thread in threads:
        thread.start()

    # Act
    start = time.perf_counter()
    start_event.set()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - start

    # Assert
    assert elapsed < BURST_LIMIT_SECONDS, (
        f"{BURST_SCAN_COUNT} rapid product scans drained in {elapsed:.3f}s, "
        f"expected under {BURST_LIMIT_SECONDS:.3f}s"
    )
    assert errors == []
    assert len(results) == BURST_SCAN_COUNT
    assert all(result["add_product"][2] is no_update for result in results)
    assert all(
        result["close_guard"] == (no_update, no_update, no_update, no_update)
        for result in results
    )
    assert len(scan_db._temporary_table.get()) == BURST_SCAN_COUNT
