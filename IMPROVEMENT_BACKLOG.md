# Swamp Machine improvement backlog

Review date: 12 October 2026. Baseline: app version 5.0.0; all 369 existing tests passed during the review. Additional isolated probes reproduced the confirmed issues below. This file records proposed work and completed maintenance; item statuses are updated as work is finished.

## How to use this file

Pick one numbered item and complete it independently. The order favors small, confirmed fixes first, followed by changes involving several callbacks. Optional ideas and admin performance work come later. This is an effort-first order, not a ranking of severity: item 07 can reassign a person's purchases and payment and deserves particular care.

Before implementation, read [the maintainer rules](.agents/mosen-maintainer.md) and [the repository guide](.agents/references/mosen-repo-guide.md). Recheck the current code and reproduce the issue: earlier items may change the relevant behavior. The proposals are starting points, and an agent should record any reason the proposed approach no longer makes sense.

For each item:

- Keep the change within that item's scope; avoid an unrelated refactor or new dependency.
- Use the existing database transaction and error-queue patterns. Preserve correctly shaped Dash pattern outputs on failures.
- Add focused regression coverage for confirmed bugs, then run the relevant tests with `.\.venv\Scripts\python.exe -m pytest ...`. Follow the repository's escalation instructions if the venv cannot launch in the sandbox.
- Update the item's status and record the change and verification when finished. Describe remaining uncertainty instead of marking an unverified fix complete.

Code locations below use file paths and function names. Function names are the primary references because line numbers will move as items are completed.

## User preferences and scope

- Expected trips have fewer than 300 users and fewer than roughly 16 purchases per user on average. Performance work should improve opening a basket, scanning products, checkout, and responsiveness during background work. Admin imports and exports may take longer.
- Product names must remain visible. A barcode may identify a component internally and may also be displayed alongside its name. Do not replace readable names with barcode-only labels.
- The preferred proposal for export rounding is to remove the optional whole-DKK rounding feature. Waste allocation has its own rounding rules; those are separate.
- Importing transactions is generally an administrator's responsibility. Keep proposed import safeguards narrow: prevent obvious invalid references or values that make ordinary app operations fail. Do not add a broad import-policy redesign.
- Failed checkout should keep the basket open, show the error, and preserve both pending data and the visible product list.
- Preserve offline operation, barcode/keyboard speed, and the locked-down kiosk behavior. Old database compatibility and migrations are not required by default.

## Work order

| Order | Item | Approximate scope | Evidence / priority |
| --- | --- | --- | --- |
| 01 | ~~Fix Reset data~~ | Small | **Done** |
| 02 | ~~Require unique product names~~ | Small | **Done** |
| 03 | Protect early payments during direct user deletion | Small | Confirmed bug |
| 04 | ~~Remove optional payment-export rounding~~ | Small | **Done** |
| 05 | Prevent product imports from removing purchased products | Small | Confirmed bug |
| 06 | Preserve the visible basket after failed checkout | Small to medium | Confirmed bug |
| 07 | Clear stale edit state on Create and Cancel | Small to medium | Confirmed user bug; analogous product path |
| 08 | Validate numeric values before table replacement | Medium | Confirmed bug in shared table logic |
| 09 | Refresh settings after successful changes | Medium | Confirmed callback/design issue |
| 10 | Make backups consistent without holding up buying | Medium | Confirmed unsafe copy; implementation proposal |
| 12 | Show the current basket's price and item count | Small to medium | Optional usability idea |
| 17 | Validate transaction references once per batch | Medium | Deferred admin performance work |

## 01. Fix Reset data

**Status:** Done (12 October 2026). **Evidence:** Reproduced through the reset callback with a temporary database and keyboard functions patched before applying the fix.

**Issue:** Reset fails with `near "IF": syntax error`, and the existing data remains.

**Why it matters:** Administrators cannot reliably clear a finished trip or recover to a fresh setup.

**Cause:** `reset_all_tables()` constructs `DROP TABLE {table} IF EXISTS`, which has the SQL keywords in the wrong order.

**Proposed change:** Correct it to `DROP TABLE IF EXISTS {table}`. Check that the reset consistently uses the configured database, closes connections it owns, and does not leave a partially reset database on a write failure. Follow the existing transaction pattern. Preserve the intended kiosk exit behavior.

**Where:** `src/database/data_connection.py`: `reset_all_tables()`, `Database.init()`; `src/main_page_callbacks.py`: `reset_database()`.

**Acceptance:** Reset a populated temporary database and verify all five tables are reset as intended, settings defaults are restored when reopened, and a custom database path is respected. Stub keyboard/exit functions; never test reset against the real trip database. Relevant tests: `tests/test_data_connection.py`, `tests/test_main_page_callbacks.py`.

**Implemented:** Corrected the DROP syntax. Reset now drops all five tables and calls `Database.init()` to recreate them and restore settings defaults in one transaction, retaining the registered database and its configured path. `Connection.begin_transaction()` starts the SQL transaction once for its owner; callers do not need their own BEGIN guards. `Database.init()` and `_create_tables()` use the common transaction executor, which closes only owned connections and preserves an enclosing transaction. Cache refresh after rollback is performed only by the transaction owner, after the database is restored. Table creation skips rollback cache refresh because it leaves caches untouched and may fail while tables are missing. Keyboard unhooking and the existing Alt+F4 exit run after a successful commit; write failures restore stored rows and caches and flow through the existing callback error queue.

**Verification:** Final verification with `.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_barcode_scan_performance.py` passed **372 tests**, including 15 new regressions for populated custom-path reset, defaults after reopening, connection cleanup/ownership, rollback during DROP/recreation/default writes, reset dialog success/cancel/error behavior, standalone creation failures preserving the original SQL error, and owner-only cache refresh for nested exceptions and rollback results. A schema-only rollback test verifies that the common transaction helper rolls back DROP/CREATE statements even after a nested commit request. The 12 barcode-performance cases passed in the preceding full run of 382 tests, before the final rollback-only change to reuse `init()`. Reset tests use isolated temporary databases and stubbed keyboard actions.

## 02. Require unique product names

**Status:** Done (12 October 2026). **Evidence:** Before the fix, two products named "Cola" were accepted and created stock fields with the same ID, which prevented Dash from loading the layout.

**Issue:** Duplicate product names could prevent the app from loading, including after a restart.

**Why it matters:** Importing or saving conflicting product names should fail before it can make the machine unusable. Product names must remain visible in the existing stock controls.

**Cause:** The stock dialog identifies each input by product name. Duplicate names therefore produced duplicate input IDs.

**Chosen change:** Require unique product names during product writes. Compare names as stored strings, preserving case and whitespace. Reject duplicate names before writing, including conflicts within an import or append batch and conflicts with existing products during append. An existing product can keep its own name when edited. Keep the stock controls and their callback signatures unchanged.

**Where:** `src/database/tables/product.py`: `ProductTable.is_valid_batch()`; existing callers in `BaseTable.set()` and `BaseTable.append()`.

**Acceptance:** Product creation, editing and imports reject duplicate names and report the offending rows. Failed batches preserve both stored products and the cache. Editing a product while retaining its own name still succeeds. No name validation is added to basket opening, product scanning or checkout.

**Implemented:** Added a product-specific name check to the existing batch validation. It covers replacement and append writes without changing shared table code, the database schema or scan/checkout logic. Names that become the same stored string, such as numeric `123` and text `"123"`, are treated as duplicates. Validation runs only for product writes.

**Verification:** `.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_barcode_scan_performance.py` passed **377 tests**, including five new cases for duplicate names, replacement/append rejection, conflicts with existing products and preservation of stored rows/cache. Existing product-edit tests verify that retaining a product's own name remains valid. The three basket-opening, product-scan and checkout tests in `tests/test_barcode_scan_performance.py` also passed their existing callback-workflow limits of 300 ms, 100 ms and 400 ms respectively.

## 03. Protect early payments during direct user deletion

**Status:** Open. **Evidence:** A user with `paid_cents=5000` and no transactions can be deleted without an error.

**Issue:** Direct deletion silently removes a recorded early payment.

**Why it matters:** An administrator can lose payment bookkeeping through an ordinary edit/delete action. CSV replacement already prevents the equivalent removal.

**Cause:** `edit_new_data_modals()` checks whether the user has transactions, but does not check their payment. `_validate_user_removals()` already checks both conditions for imports.

**Proposed change:** Reuse the existing removal guard for the selected user before mutation. Protect any nonzero `paid_cents`, matching the import behavior. Keep the existing product deletion guard.

**Where:** `src/main_page_callbacks.py`: `edit_new_data_modals()`, `_validate_user_removals()`.

**Acceptance:** Deleting a user with an early payment and no purchases displays an error and changes nothing. A user with neither remains deletable. Verify correctly shaped error outputs. Relevant tests: `tests/test_edit_data_modals.py`, `tests/test_main_page_callbacks.py`.

## 04. Remove optional payment-export rounding

**Status:** Done (12 October 2026). **Evidence:** Reproduced before the change using an isolated temporary database and a real Excel export: rounding "Up" to 10 turned a 20 DKK purchase with no waste into 30 DKK.

**Issue:** The rounding feature can overcharge amounts that are already exact multiples, and its practical use is unclear.

**Why it matters:** Payment files should contain understandable calculated amounts. Removing unused controls also simplifies the export dialog.

**Cause:** The "Up" formula always adds an increment, even when the remainder is zero. Two dropdowns and callback parameters exist solely for this optional final rounding step.

**Proposed change:** Remove the Up/Down/Nearest and increment controls, their callback States/parameters, and the final whole-DKK rounding branch. Remove imports only if they become unused. Preserve waste allocation's separate rounding policy and the existing added-income eligibility/distribution policy. Do not introduce a different surcharge policy as part of this small removal. Check normal currency display precision, including fractional-cent shares produced by added income, and record any separate precision issue discovered.

**Where:** `src/modals.py`: `export_payments_modal()`; `src/main_page_callbacks.py`: `control_payments_modal()`.

**Acceptance:** 20 DKK exports as 20; 12.50 DKK remains 12.50. Existing stock-freshness checks, settled-user behavior, added income, waste allocation and real Excel output still work. Update callback-call tests for the new signature. Relevant tests: `tests/test_waste_allocation.py`, `tests/test_main_page_callbacks.py`.

**Implemented:** Removed both rounding dropdowns, their callback States and parameters, and the final whole-DKK rounding branch. Removed the unused `builtins` import and dropdown CSS. The dialog retains Add income and Confirm. Waste allocation still applies its own rounding policy, and added income is still shared equally only among users with purchases and a positive amount due, including eligible guests. Stock-freshness checks and settled-user handling are unchanged.

**Verification:** `.\.venv\Scripts\python.exe -m pytest -q tests/test_waste_allocation.py tests/test_main_page_callbacks.py` passed **116 tests**. The broader suite, `.\.venv\Scripts\python.exe -m pytest -q --ignore=tests/test_barcode_scan_performance.py`, passed **379 tests**. Real Excel regressions verify unchanged 20 DKK and 12.50 DKK amounts, equal added-income shares, exclusion of settled users and non-buyers with allocated waste, inclusion of eligible guests, and separately rounded persisted waste. Existing export stock checks and warning paths pass with the new callback signature. An isolated Dash app served layout and dependency endpoints successfully and confirmed that the payment callback no longer requests rounding States and the modal has no rounding dropdowns. Performance tests were not rerun because this change does not touch the purchase workflow.

**Separate precision follow-up:** Existing added-income division can produce fractional-cent amounts, and monetary Excel cells use `General` formatting rather than a fixed two-decimal display. With optional rounding already disabled, three buyers owing 12.50 DKK each and 0.01 DKK added income exported approximately 12.50333333333333 DKK each. Plain 12.50 DKK exports as numeric 12.5 without losing value. This issue remains open: assigning cent remainders needs a separate distribution decision, so this removal does not round individual shares or change eligibility.

## 05. Prevent product imports from removing purchased products

**Status:** Open. **Evidence:** A replacement product import omitting a purchased product reduced both a user's purchases and total revenue from 12.50 DKK to zero.

**Issue:** Importing products can leave existing transactions referring to a product that no longer exists. Those purchases are subsequently priced at zero.

**Why it matters:** An ordinary product-list replacement can silently alter accounting without touching the transaction file.

**Cause:** Product imports replace the table. Import validation protects removal of users, but has no equivalent product-reference check. Revenue and income calculations assign zero to unknown product barcodes.

**Proposed change:** Before replacing products, reject an import omitting any product barcode referenced by existing transactions. Explain which purchased products must remain. Allow removal of unused products, normal edits/additions, and initial imports. Keep the safeguard narrow; transaction import itself remains an administrator responsibility. Do not redesign historical pricing or store price snapshots in this task.

**Where:** `src/main_page_callbacks.py`: `update_settings()`, adjacent to `validate_user_import()`; `src/analytics/trans_calculations.py`: `get_income()`, `get_revenue()` for the observed consequence.

**Acceptance:** An unsafe product replacement is rejected without changing products, transactions or accounting. A replacement retaining purchased barcodes succeeds, as does removing an unused product. Relevant tests: `tests/test_main_page_callbacks.py`.

## 06. Preserve the visible basket after failed checkout

**Status:** Open. **Evidence:** A forced checkout failure preserved a pending database item but left only the "Products:" heading on screen.

**Issue:** The basket modal stays open and the red error appears, but the product list looks empty despite products still being pending.

**Why it matters:** After dismissing the error, a person may scan the same products again or misunderstand what a retry will purchase.

**Cause:** Scanning the user's barcode triggers both checkout and `new_trans()`. The latter clears the displayed list independently of checkout success.

**Proposed change:** Preserve the displayed products when the user barcode is submitted. Clear the display only after successful checkout or successful opening of a fresh basket. Coordinate that reset with the callback that owns those successful transitions, while preserving existing rollback and duplicate-checkout protection.

**Where:** `src/trans_layout.py`: `new_trans()`, `open_trans_modal()`, `checkout_cart_to()`.

**Acceptance:** Forced append/clear failures preserve the open modal, visible names/counts and database basket, and show the error. Retrying records each item once. A fresh basket has an empty display. Relevant tests: `tests/test_open_trans_modal.py`, `tests/test_transaction_rollback_behavior.py`; check both callbacks, not just database rollback.

## 07. Clear stale edit state on Create and Cancel

**Status:** Open. **Evidence:** Confirmed for users; product callbacks have the analogous stale-edit pattern and need their own reproduction.

**Issue:** Edit an existing person, cancel, then Create and Confirm a new person: the original can disappear and their purchases and payment can move to the new barcode.

**Why it matters:** This is accidental reassignment of accounting data, not merely a form display problem.

**Cause:** The shared `edit_input` barcode survives Cancel/Create. Save callbacks interpret that barcode as an active edit. Create initializes only part of the form, leaving previous context or values available.

**Proposed change:** Clear active edit context on explicit Create and Cancel, including other dismissal paths that exist. Initialize all creation fields to fresh defaults. Preserve context during an actual Edit, failed-save retries, and deliberate barcode changes. Do not clear edit context on the raw Confirm click before the save consumes it.

**Where:** `src/tables/user_callbacks.py`: `open_user_modal()`, `add_row_callback()`, `add_row()`; equivalent functions in `src/tables/prod_callbacks.py`; `src/main_page_callbacks.py`: `edit_new_data_modals()`; `src/modals.py`: `edit_modal()`.

**Acceptance:** Edit -> Cancel -> Create -> Confirm adds a separate user/product and leaves the original record, payments, purchases and stock unchanged. New user defaults include `paid_cents=0`, `waste_cents=-1` and the default guest flag. Actual edits and failed-save retries still work. Relevant tests: `tests/test_user_callbacks.py`, `tests/test_prod_callbacks.py`, `tests/test_edit_data_modals.py`.

## 08. Validate numeric values before table replacement

**Status:** Open. **Evidence:** A quoted CSV price of `"12,50"` committed successfully, then typed product reads raised a conversion error.

**Issue:** Import validation can accept values that the application cannot subsequently read using its declared column types.

**Why it matters:** One bad numeric cell can leave checkout, product editing or stock handling failing until the data is repaired.

**Cause:** `BaseTable.is_valid_batch()` checks required fields, columns, duplicate primary keys and barcode validity, but not ordinary numeric types. `get()` performs conversion later, after replacement has committed.

**Proposed change:** Validate declared numeric conversions before any replacement/insertion. Reject non-finite numbers and fractional values for integer columns; fill optional defaults before checking them. Return useful bad rows and preserve the previous table on failure. Reject unsupported decimal formats clearly rather than silently guessing a locale. Respect valid sentinels such as `waste_cents=-1` and legitimately negative current stock; do not add unrelated domain restrictions.

**Where:** `src/database/tables/base_table.py`: `is_valid_batch()`, `set()`, `append()`, `get()`; `src/database/tables/column.py`; product/user column definitions.

**Acceptance:** Malformed numbers, infinity and fractional integer fields fail before writes; typed reads continue working. Valid numeric inputs, optional defaults and existing sentinel values still round-trip. Check both replacement and append. Relevant tests: `tests/test_column_system.py`, `tests/test_product_table.py`, `tests/test_product_table_properties.py`, `tests/test_main_page_callbacks.py`, transaction/atomicity tests affected by shared validation.

## 09. Refresh settings after successful changes

**Status:** Open. **Evidence:** A passive tab event requests a one-second sleep and rebuilds all three data tabs, including their nested modals.

**Issue:** Settings refresh can close/reset forms and can read data before the operation that triggered it has completed.

**Why it matters:** Typed input may disappear, failed saves become hard to correct, and tables can display stale values. The arbitrary delay also makes admin interactions slower.

**Cause:** `update_settings_layout()` listens to button clicks and passive UI events, guesses that writes finish within one second, then replaces whole tab children. Forms, modals and state stores are nested in those children.

**Proposed change:** Keep forms, action controls, search input and modals mounted. Emit unique change revisions from successful mutation callbacks, with the response returned after commit. Use those revisions to refresh table data/tooltips, income backing rows, waste figures and a small economy-summary container. Refresh on settings opening to capture purchases since the previous visit. Populate stock rows and study-user choices when their dialogs open. Remove the sleep and whole-tab replacement.

**Dependencies and cautions:** Revalidate items 02, 06 and 07 after this change. Remove the unrelated `confirm_new_stock` trigger from the product-save callback; stock saving should have one owner. `update_settings.data=True` currently also occurs after invalid imports roll back, so it is not a reliable success signal. Payment export can commit while displaying a warning; such committed changes still need refresh. Failed saves should preserve the open form and its input. Handle tables that were initially empty as well as table columns and tooltips.

**Where:** `src/main_layout.py`: `update_settings_layout()`, the settings layout builders; mutation callbacks in `src/main_page_callbacks.py` and `src/tables/`; existing `transaction_removal_revision` demonstrates part of the approach.

**Acceptance:** Switching tabs does not close or clear forms. Successful writes update all affected views; failed writes preserve input. Reopening settings after purchases shows current data. Stock saves do not replay product creation. Verify the interaction in a browser as well as focused callback tests. Relevant tests: `tests/test_main_page_callbacks.py`, `tests/test_edit_data_modals.py`, `tests/test_user_callbacks.py`, `tests/test_prod_callbacks.py`, `tests/test_waste_allocation.py`.

## 10. Make backups consistent without holding up buying

**Status:** Open. **Evidence:** Copying an isolated SQLite database during a write captured a mixture containing changes that were subsequently rolled back.

**Issue:** Periodic backups copy the live database file without coordinating with writes, so a backup may not represent a valid committed trip state.

**Why it matters:** Recovery files must be trustworthy, while background backup work should avoid noticeable scan/checkout delays.

**Cause:** `create_database_backup()` uses `shutil.copy()`. The periodic callback does not participate in the database lock. A global lock around the entire copy would serialize it safely within this app, but a purchase arriving during the copy would wait.

**Proposed change:** Put a native SQLite backup helper in the existing database/connection layer. Periodic backups should use a fresh dedicated source connection and incremental backup, with a separate backup mutex preventing overlap. Avoid holding the app-wide lock through the entire periodic backup. Publish the filename only after successful completion and clean up incomplete output on failure. Pre-import and pre-deletion snapshots should remain blocking under the existing transaction lock and complete before the first write.

**Cautions:** Do not use `Connection.connect()` to obtain the backup source inside a transaction: it may return the active write connection. Backing up a source connection with its own uncommitted write can self-block. Short SQLite read locks still occur; do not promise zero latency. Use no new dependency. See the [SQLite online backup documentation](https://www.sqlite.org/backup.html).

**Where:** `src/main_page_callbacks.py`: `create_database_backup()`, `backup_database()`, pre-import and transaction-removal call sites; `src/database/data_connection.py`; `src/database/connection.py`.

**Acceptance:** Concurrent purchases and periodic backups produce readable snapshots of committed data, without errors or overlap. A failed backup is not advertised as complete. A required pre-action backup failure prevents that action. Existing pre-import/deletion snapshot tests still pass. Measure purchase latency with backups active on realistic data; the review's 176 KB database took roughly 6-8 ms to back up on one machine, not a target-laptop guarantee.

## 12. Show the current basket's price and item count

**Status:** Open, optional. **Evidence:** The basket displays counts per product, while its header's bill describes previous purchases rather than the pending basket subtotal.

**Issue:** Users cannot easily check the total amount or total number of items they are about to buy.

**Example:** A person already owes approximately 20 DKK from earlier purchases and any waste estimate. They now scan two beers at 10 DKK each and one cola at 5 DKK. The existing header still describes that earlier bill, and the product list shows `2x: Beer` and `1x: Cola`. This proposal adds `Current basket: 3 items - 25.00 DKK`. The count includes every unit, not just the two different product types. The basket price excludes previous purchases and waste.

**Why it matters:** A combined price and count could help someone spot an extra scan or wrong multiplier before checkout. This is an optional convenience; no checkout or accounting bug has been demonstrated here.

**Cause:** `new_trans()` renders names and per-product counts without combined totals. `show_balance()` reads saved purchases and a waste estimate when the basket opens; it does not calculate the pending basket's price after each product scan.

**Proposed change:** Add a clearly labelled pending-basket subtotal and total item count, calculated from current products and the basket. Preserve the visible product names and distinguish this subtotal from the historical bill/waste preview. Derive it from current data without another full-history calculation on every product scan.

**Where:** `src/trans_layout.py`: `new_trans()`, `show_balance()`, `trans_modal()`.

**Acceptance:** Feedback updates for additions, multipliers and product removal, resets for a fresh basket, and remains correct after failed checkout. Check decimal prices and repeated products. Prerequisite: item 06. Relevant tests: `tests/test_open_trans_modal.py`; manually inspect layout and scan responsiveness.

## 17. Validate transaction references once per batch

**Status:** Deferred. **Evidence:** Importing 5,000 transactions took about 18 seconds; an isolated membership-set approach handled the same batch in about 0.07 seconds. This chiefly concerns imports.

**Issue:** Bulk transaction validation repeatedly obtains and converts the same user and product tables.

**Why it matters:** Large admin imports are unnecessarily slow. Normal checkout validates the new basket rows, so the bulk number does not establish a main-workflow problem.

**Cause:** Each transaction's existence checks call typed `get()` on both reference tables and build lists again.

**Proposed change:** If worthwhile, build user/product barcode sets once for each set/append batch under the existing lock, and validate rows using membership checks. Rebuild sets for every batch so edits/imports cannot leave stale reference state. Avoid permanent caches or a shared mutable validation context. Preserve all-or-nothing writes.

**Where:** `src/database/tables/transaction.py`: `is_valid_batch()`, `_validate_product_exists()`, `_validate_user_exists()`; batching in `src/database/tables/base_table.py`.

**Acceptance if implemented:** Valid and invalid batches behave identically; changing users/products affects the next batch; failed writes roll back. Profile ordinary checkout too and avoid regressing it. Relevant tests: `tests/test_constraints_and_atomicity.py`, `tests/test_transaction_atomicity.py`, `tests/test_transaction_rollback_behavior.py`, `tests/test_barcode_scan_performance.py`.

## Removed ideas

Items 11, 13, 14, 15 and 16 were removed from the active backlog on 12 October 2026. Remaining item numbers are unchanged.

- **11 - Scanning instructions:** No user confusion has been demonstrated. Extra guidance is optional UI work without an established need.
- **13 - Saved-purchase confirmation:** Successful checkout already closes the basket. An additional message has no demonstrated need.
- **14 - Persistent scanner visibility:** The fullscreen modal body already scrolls (`assets/bootstrap.css`). No failure on an actual laptop viewport has been reproduced.
- **15 - Browser scan investigation:** No lost or duplicated scan has been reproduced. Callback-only tests leave browser behavior unverified; check consecutive browser/scanner input when changing the scan flow rather than scheduling a speculative fix.
- **16 - Economy/payment aggregation:** The recorded speedup used 500 users and 30,000 purchases, beyond expected trips. No meaningful admin delay at realistic scale has been established; reconsider after measuring one.

## Performance evidence to retain

The existing purchase tests passed with histories of roughly 7,400-8,400 transactions, above expected usage. Their callback-workflow limits include 300 ms to open a basket, 100 ms for a product scan and 400 ms to submit. They do not measure the complete browser/scanner experience.

Additional isolated checkout probes at 300 users, 80 products and 4,500 transactions measured median core checkout times of about 74 ms for one item, 73 ms for five items and 109 ms for sixteen items. These measurements support prioritizing reliability and actual scan responsiveness over admin batch optimization. They are not latency guarantees for the trip laptop or its storage.
