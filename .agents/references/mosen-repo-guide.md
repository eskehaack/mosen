# Swamp Machine Repo Guide

## Domain

Swamp Machine/Mosemaskinen is a local trip purchase system. It is a Danish "stregsystem": a self-checkout/accounting system for trip purchases, combined with dashboards and graphs. Users and products are represented by barcodes. During trips, people scan purchases through the machine, admins update products/users/settings, and the app exports payment information at the end.

Operational assumptions:

- Trips use fresh data for each version; migrations and schema-compatibility shims are normally unnecessary.
- Laptops are weak and often offline.
- The app can run in a browser, but is usually run as a locked-down self-checkout where normal users should not casually exit the app.
- Runtime reliability matters more than broad extensibility.
- UI should be clear under stress and friendly to barcode scanner workflows.

## Application Shape

- `main.py`: desktop entrypoint; starts Dash server and opens `pywebview`.
- `app.py`: creates the Dash app and initializes `Container` with `Database` and `TopUserChartData`.
- `src/main_layout.py`: main page, settings modal, top user chart modal, and layout-level callbacks.
- `src/main_page_callbacks.py`: settings uploads/downloads, payment export, edit/delete modal, backup, study users.
- `src/trans_layout.py`: transaction modal and barcode scanning flow.
- `src/modals.py`: modal body definitions for users, products, payments, settings dialogs.
- `src/tables/user_callbacks.py` and `src/tables/prod_callbacks.py`: create/edit callbacks for users/products and product stock.
- `assets/styling.css`: app-specific CSS. `assets/bootstrap.css` is vendor-style and should rarely be edited.

## Database Pattern

Use `Container.get(Database)` for DB access. Do not instantiate extra production `Database` objects or use `Connection` directly outside tests.

Tables live in `src/database/tables/`:

- `users`: `barcode`, `name`, `rank`, `team`, `is_guest`, `waste_cents`, `paid_cents`
- `prods`: `barcode`, `name`, `price`, `category`, `current_stock`, `initial_stock`
- `transactions`: `barcode_user`, `barcode_prod`, `timestamp`
- `temporary`: current transaction basket, `barcode_prod`, `name`
- `settings`: password/show bill/waste/backup/cache settings

`BaseTable.get_untyped()` returns string data from cache. `BaseTable.get()` returns typed columns. Public helpers like `get_users()` return untyped data; table internals often use typed data. Prefer typed data when adding new behavior or changing existing data logic.

`BaseTable.set()` is replace mode: validate all rows, delete table contents, insert valid rows. `append()` validates against existing plus new rows and inserts only on full success.

No migrations or schema-compatibility shims are expected by default. If schema changes are needed, update the table class, tests, and fresh DB behavior. Only add migrations or old-DB read fallbacks if the user explicitly says old trip databases must survive.

## Data Import

Importing full data sets is a common admin workflow and may happen at initial setup or later during a trip. Treat upload/import behavior as a first-class path.

Initial bootstrap imports may omit optional columns because the app can safely fill defaults. Later replacement imports are different: once optional fields have been set or maintained by the program, missing columns can accidentally overwrite meaningful state with defaults. For example, an initial user import may omit `is_guest`, but a later user export/edit/reimport should include it so guest flags are not silently reset.

In general:

- Keep optional columns optional for true first-load/bootstrap imports when defaults are safe.
- For replacement imports into non-empty tables, preserve existing optional values or require the import to include columns that may already contain meaningful data.
- Fill defaults through table definitions instead of scattered callback code.
- Add tests for both initial imports and later replacement imports when changing columns.
- Avoid making imports depend on current UI-only fields unless the table schema truly requires them.

## Transactions And Errors

Use:

- `@db_transaction_raises` when exceptions should propagate into `callback_with_error_queue`.
- `@db_transaction_result(fallback_values=...)` when callback error paths need shaped fallback outputs.
- `TransactionResult(..., commit=False)` when returning values but intentionally rolling back.

`callback_with_error_queue(num_outputs, ...)` appends one extra error queue output. Tests usually call the decorated callback and receive normal outputs plus the error output.

Important Dash gotcha: pattern-matching outputs such as `Output({"type": "user_input", "index": ALL}, "value")` need a list of outputs, even when returning `no_update`. Use `[no_update] * expected_count`, not a single `no_update`.

## UI Patterns

Keep admin screens functional and dense. Avoid marketing-style layouts.

Tables should let admins see a full row where possible. Headers may wrap, but avoid horizontal scrolling unless truly necessary.

Modals under settings are nested in tab children. Do not rebuild settings tab children on passive tab render; rebuilding closes open modals.

Graphs showing counts should use `src.analytics.bar_chart_format.format_count_bar_chart`: no x-axis title, y-axis title `amount`, integer y ticks. Hide x tick labels for charts whose x-axis is only a Plotly index.

## Money And Exports

Persist money-like per-user fields in cents:

- `paid_cents`: early/pre-settled payment
- `waste_cents`: allocated waste; `-1` means no persisted allocation yet

Display/export DKK amounts for people. Payment export uses Excel (`to_excel`) to avoid locale-dependent CSV decimal issues. Keep `openpyxl` in `requirements.txt` and test real workbook output when touching exports.

Waste allocation lives in `src/analytics/waste_allocation.py`. Payment export recalculates and persists waste before exporting.

## Testing

Use the local venv:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_file.py
```

Do not substitute another Python interpreter for test runs. In the managed Codex sandbox this venv launcher may need escalated execution; if process launch fails, rerun the same venv command with escalation.

Run focused tests first:

- User create/edit/delete: `tests/test_user_callbacks.py`, `tests/test_edit_data_modals.py`
- Product create/edit/stock: `tests/test_prod_callbacks.py`
- Transaction flow: `tests/test_open_trans_modal.py`
- Payment/waste/export/economy: `tests/test_waste_allocation.py`
- Top buyer graph: `tests/test_top_user_chart.py`
- DB/table behavior: `tests/test_*table*.py`, `tests/test_data_connection.py`, transaction tests

Test fixtures usually create `Database(tmp_path / "...db")` and register it with `Container.set(Database, db)`. If code needs `TopUserChartData`, register it too.

Prefer minimal Arrange / Act / Assert tests. Use comments or whitespace to make the three phases clear, but avoid heavy setup abstractions unless they remove repeated noise.

## Offline And Packaging

Avoid runtime network dependencies. Keep assets local under `assets/`. Be cautious with packages that make PyInstaller builds larger or more fragile.

Build command from `README.md`:

```powershell
pyinstaller -F -n "swampmachine.exe" --distpath "." --clean --icon "assets\favicon.ico" --add-data "assets:assets" --log-level=WARN main.py
```

The app blocks some keys and hides the taskbar in `main.py`; do not casually change this without considering the locked-down self-checkout use case.
