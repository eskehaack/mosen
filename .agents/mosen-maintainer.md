---
name: mosen-maintainer
description: Maintain and extend this repository's Swamp Machine/Mosemaskinen Dash application. Use when working in this repo on database tables, trip/payment logic, barcode flows, admin settings, Dash callbacks/modals, offline packaging, tests, or UI fixes for the local trip purchase machine.
---

# Mosen Maintainer Agent Guide

## Purpose

Use this guide for changes to the Swamp Machine trip app. The app is a Danish-style "stregsystem": a self-checkout/accounting system for trip purchases, combined with admin dashboards and graphs. It runs on poor Windows laptops, often offline, with the UI normally locked down so ordinary users cannot exit the app. Favor reliability, local-first behavior, simple dependencies, and fast recovery over architectural cleverness.

Before non-trivial code changes, read `.agents/references/mosen-repo-guide.md`. Treat both this file and that reference as active repo instructions, not optional background.

## Working Rules

- Treat the current trip database as disposable between versions unless the user explicitly asks for compatibility. Migrations and schema-compatibility shims are not usually needed because old data is not reused across released versions.
- Do not add runtime internet requirements. Avoid CDN assets, remote APIs, telemetry, or features that need network access during trips.
- Keep dependencies pinned in `requirements.txt`; add dependencies only when they improve reliability enough to justify offline installation and packaging cost.
- Preserve keyboard/barcode workflow speed. The main flow should remain scan-focused and low-friction.
- Keep full data import robust. Admins may import users, products, and transactions at any time, not only during initial setup.
- Prefer typed data when adding new features or changing data logic.
- Prefer small, direct fixes that match existing Dash callback and table patterns.
- Validate with the local venv: `.\.venv\Scripts\python.exe -m pytest ...`. If this fails due to sandbox/process-launch restrictions, rerun the same command with escalated permissions rather than switching to another Python.

## Common Workflow

1. Inspect the relevant layout, callback, table, and tests before editing.
2. Keep DB writes inside transaction decorators from `src.database.data_connection`.
3. If a callback can show a user-facing failure, use `callback_with_error_queue` and return correctly shaped fallback outputs for pattern-matching outputs.
4. Add focused regression tests next to the behavior. Keep tests readable with a minimal Arrange / Act / Assert structure:
   - user/product modal and edit behavior: `tests/test_user_callbacks.py`, `tests/test_prod_callbacks.py`, `tests/test_edit_data_modals.py`
   - transaction modal: `tests/test_open_trans_modal.py`
   - payments, waste, export, economy refresh: `tests/test_waste_allocation.py`
   - top buyer chart: `tests/test_top_user_chart.py`
   - table/schema/cache behavior: table-specific tests under `tests/`
5. Run the smallest relevant pytest set first, then broaden if shared behavior changed.

## High-Risk Areas

- Pattern-matching Dash outputs (`ALL`, `MATCH`) must receive lists of the right length, even on error paths.
- Rebuilding settings tab children can reset modals. Avoid passive layout refreshes that race user clicks.
- `BaseTable.set()` replaces whole tables; use it carefully with transactions and validation.
- Transactions require existing users/products. Do not delete referenced users/products unless explicitly designing a historical cleanup flow.
- Money is stored as cents for persisted user fields (`paid_cents`, `waste_cents`) but many UI/export surfaces display DKK.
- Excel exports need `openpyxl`; CSV decimal parsing is locale-sensitive on Danish Excel setups.

## Build And Runtime Notes

- The entrypoint is `main.py`; it wraps Dash in `pywebview`, fullscreen, and blocks some Windows keys.
- The app should continue to work without internet once dependencies are installed.
- PyInstaller build command is documented in `README.md`; keep asset paths and dependencies compatible with freezing.
