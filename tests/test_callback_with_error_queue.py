from dash import Input, Output, no_update

from src.database.data_connection import Result
from src import error_handler
from src.error_handler import callback_with_error_queue


def test_callback_with_error_queue_passes_through_single_output(monkeypatch):
    logged_errors = []
    monkeypatch.setattr(
        error_handler,
        "log_displayed_error",
        lambda *args: logged_errors.append(args),
    )

    @callback_with_error_queue(
        1,
        Output("single-output", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        return "ok"

    assert handler(1, []) == ("ok", no_update)
    assert logged_errors == []


def test_callback_with_error_queue_unwraps_result_values():
    @callback_with_error_queue(
        2,
        Output("first", "children"),
        Output("second", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        return Result(values=("one", "two"))

    assert handler(1, []) == ("one", "two", no_update)


def test_callback_with_error_queue_adds_error_and_no_updates_on_exception(monkeypatch):
    logged_errors = []
    monkeypatch.setattr(
        error_handler,
        "log_displayed_error",
        lambda *args: logged_errors.append(args),
    )

    @callback_with_error_queue(
        1,
        Output("single-output", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        raise RuntimeError("boom")

    result = handler(1, [])

    assert result[0] is no_update
    assert result[1][0]["msg"] == "boom"
    assert len(logged_errors) == 1
    assert logged_errors[0][0:2] == ("handler", "boom")
    assert logged_errors[0][2].__traceback__ is not None


def test_callback_with_error_queue_preserves_result_error_when_shape_is_wrong(monkeypatch):
    logged_errors = []
    monkeypatch.setattr(
        error_handler,
        "log_displayed_error",
        lambda *args: logged_errors.append(args),
    )

    @callback_with_error_queue(
        2,
        Output("first", "children"),
        Output("second", "children"),
        Input("trigger", "n_clicks"),
    )
    def handler(_n_clicks):
        return Result(values=("only-one",), error=RuntimeError("inner boom"))

    result = handler(1, [])

    assert result[0] is no_update
    assert result[1] is no_update
    assert result[2][0]["msg"] == "inner boom"
    assert result[2][1]["msg"] == "Expected 2 outputs, got 1"
    assert len(logged_errors) == 2
    assert logged_errors[0][0:2] == ("handler", "inner boom")
    assert logged_errors[0][2].__traceback__ is None
