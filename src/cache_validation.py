from dash import callback, Input, Output, State, no_update
from src.container import Container
from src.database.data_connection import Database
from src.error_handler import append_error, ERROR_QUEUE_ID


@callback(
    Output(ERROR_QUEUE_ID, "data", allow_duplicate=True),
    Input("cache_validation_interval", "n_intervals"),
    State(ERROR_QUEUE_ID, "data"),
    prevent_initial_call=True,
)
def on_cache_validation(_n, error_queue):
    db = Container.get(Database)
    try:
        changed = db.validate_cache_hashes()
    except Exception as e:
        return append_error(
            error_queue,
            msg=f"Cache validation failed: {e}",
            src="cache",
            error=e,
        )

    if not changed:
        return no_update

    tables = ", ".join(changed)
    return append_error(error_queue, msg=f"Cache validation detected changes: {tables} \nContact your administrator.", src="cache")