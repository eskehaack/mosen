"""Tests for validator failures, constraints, and multi-table atomicity.

NOTE: This file tests two separate concerns:
1. Validation-time rejections (set/append return bad_rows without raising)
2. Multi-table transaction atomicity (exception-based rollback)

Validation rejections do NOT raise exceptions, so they don't trigger multi-table
rollback. Only actual exceptions (RuntimeError, ValueError, etc.) trigger atomicity.
"""
import pytest
import sqlite3
from threading import Thread

from src.container import Container
from src.database.data_connection import Database, db_transaction_raises


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "constraints_test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestValidationFailures:
    """Validator failures reject batches at validation time (no exception)."""

    def test_mixed_valid_invalid_rows_all_rejected(self, test_db):
        """Batch with 3 valid + 1 invalid row: entire batch rejected at validation."""
        db = test_db
        
        # Insert 1 row first so we have a baseline
        db._product_table.append([
            {
                'barcode': '100',
                'name': 'Baseline',
                'price': '1.00',
                'category': 'Test',
                'current_stock': '1',
                'initial_stock': '1'
            }
        ])
        baseline_count = len(db._product_table.get())
        assert baseline_count == 1
        
        # Try to append batch: 3 valid + 1 invalid (missing required field)
        rows = [
            {'barcode': '101', 'name': 'Good1', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'},
            {'barcode': '102', 'name': 'Good2', 'price': '2.00', 'category': 'Test', 'current_stock': '2', 'initial_stock': '2'},
            {'barcode': '103', 'name': 'Good3', 'price': '3.00', 'category': 'Test', 'current_stock': '3', 'initial_stock': '3'},
            {'barcode': '104', 'name': 'Bad', 'price': '4.00', 'category': 'Test', 'current_stock': '4'},  # Missing initial_stock
        ]
        
        result, bad_rows = db._product_table.append(rows)
        
        # One row fails validation: entire batch rejected at validation level
        assert result == "prods", f"Expected 'prods' (table name), got {result}"
        assert len(bad_rows) == 1, f"Expected 1 bad row, got {len(bad_rows)}"
        
        # Count should remain at baseline (nothing written)
        final_count = len(db._product_table.get())
        assert final_count == 1, f"Expected 1 row (baseline unchanged), got {final_count}"
        
        # Verify cache matches DB
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        db_count = cur.fetchone()[0]
        con.close()
        assert db_count == final_count, f"Cache/DB mismatch: {final_count} vs {db_count}"

    def test_duplicate_barcode_in_batch_rejects_entire_batch(self, test_db):
        """Batch with duplicate barcodes: entire batch rejected at validation."""
        db = test_db
        
        rows = [
            {'barcode': '110', 'name': 'Item1', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'},
            {'barcode': '110', 'name': 'Item1_Dup', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'},
        ]
        
        result, bad_rows = db._product_table.append(rows)
        
        # Duplicate in batch: entire batch rejected
        assert result == "prods", f"Expected 'prods' (table name), got {result}"
        # Both rows flagged as invalid (both have duplicate barcodes)
        assert len(bad_rows) >= 1, "At least one duplicate should be in bad_rows"
        
        # No rows persisted
        final_count = len(db._product_table.get())
        assert final_count == 0, f"Expected 0 rows (batch rejected), got {final_count}"

    def test_invalid_barcode_partition_rejected(self, test_db):
        """Row with invalid barcode (wrong partition) causes batch rejection."""
        db = test_db
        
        # USER barcode (1000+) in product batch (should be 100-999)
        rows = [
            {'barcode': '115', 'name': 'Good', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'},
            {'barcode': '2000', 'name': 'Bad_Partition', 'price': '2.00', 'category': 'Test', 'current_stock': '2', 'initial_stock': '2'},
        ]
        
        result, bad_rows = db._product_table.append(rows)
        
        # Invalid barcode in batch: entire batch rejected
        assert result == "prods", f"Expected 'prods', got {result}"
        assert len(bad_rows) == 1, "Invalid barcode should be in bad_rows"
        
        # No rows persisted (batch rejected at validation)
        final_count = len(db._product_table.get())
        assert final_count == 0, f"Expected 0 rows (batch rejected), got {final_count}"


class TestExceptionBasedRollback:
    """Exception-based rollback during multi-table transactions."""

    def test_exception_after_write_rolls_back(self, test_db):
        """Exception after write should rollback that write."""
        db = test_db
        
        try:
            @db_transaction_raises
            def write_then_fail():
                db._product_table.append([
                    {'barcode': '120', 'name': 'ShouldRollback', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
                ])
                raise RuntimeError("Simulated failure")
            
            write_then_fail()
        except RuntimeError:
            pass
        
        # Write should be rolled back
        final_count = len(db._product_table.get())
        assert final_count == 0, f"Expected 0 rows (rolled back), got {final_count}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        db_count = cur.fetchone()[0]
        con.close()
        assert db_count == 0, "DB should match cache (rollback)"

    def test_concurrent_writes_serialize_atomically(self, test_db):
        """Two threads writing sequentially - both should persist atomically."""
        db = test_db
        
        def worker(barcode, name):
            @db_transaction_raises
            def write():
                db._product_table.append([
                    {
                        'barcode': str(barcode),
                        'name': name,
                        'price': '1.00',
                        'category': 'Test',
                        'current_stock': '1',
                        'initial_stock': '1'
                    }
                ])
            
            write()
        
        # Two threads writing different barcodes
        t1 = Thread(target=worker, args=(130, 'Thread1'))
        t2 = Thread(target=worker, args=(131, 'Thread2'))
        
        t1.start()
        t2.start()
        t1.join()
        t2.join()
        
        # Both should persist
        final_count = len(db._product_table.get())
        assert final_count == 2, f"Expected 2 rows, got {final_count}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        db_count = cur.fetchone()[0]
        con.close()
        assert db_count == final_count, "Cache/DB mismatch"


class TestMultiTableAtomicity:
    """Writes across multiple tables must be atomic (exception-based)."""

    def test_product_and_user_write_both_succeed(self, test_db):
        """Write to product table, then user table - both should persist."""
        db = test_db
        
        @db_transaction_raises
        def write_both():
            # Write product
            db._product_table.append([
                {'barcode': '200', 'name': 'Prod1', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
            ])
            
            # Write user
            db._user_table.append([
                {'barcode': '2000', 'name': 'User1', 'rank': 'Admin', 'team': 'TeamA', 'is_guest': '0'}
            ])
        
        write_both()
        
        # Both should persist
        prod_count = len(db._product_table.get())
        user_count = len(db._user_table.get())
        
        assert prod_count == 1, f"Expected 1 product, got {prod_count}"
        assert user_count == 1, f"Expected 1 user, got {user_count}"

    def test_product_write_then_exception_rolls_back_both(self, test_db):
        """If exception after product write, product write should rollback too."""
        db = test_db
        
        try:
            @db_transaction_raises
            def write_then_fail():
                # Write product (valid)
                db._product_table.append([
                    {'barcode': '210', 'name': 'Prod2', 'price': '2.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
                ])
                
                # Raise exception (would rollback product write)
                raise RuntimeError("Simulated failure after product write")
            
            write_then_fail()
        except RuntimeError:
            pass  # Expected
        
        # Product should be rolled back
        prod_count = len(db._product_table.get())
        assert prod_count == 0, f"Product should rollback; got {prod_count}"

    def test_three_table_write_all_or_nothing(self, test_db):
        """Write to product, user, and temporary table - all succeed."""
        db = test_db
        
        @db_transaction_raises
        def write_three():
            db._product_table.append([
                {'barcode': '230', 'name': 'Prod3', 'price': '3.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
            ])
            
            db._user_table.append([
                {'barcode': '2003', 'name': 'User4', 'rank': 'User', 'team': 'TeamD', 'is_guest': '0'}
            ])
            
            # TemporaryTable requires barcode_prod (PRODUCT partition) and name
            db._temporary_table.append([
                {'barcode_prod': '231', 'name': 'TempItem'}
            ])
        
        write_three()
        
        prod_count = len(db._product_table.get())
        user_count = len(db._user_table.get())
        temp_count = len(db._temporary_table.get())
        
        assert prod_count == 1
        assert user_count == 1
        assert temp_count == 1

    def test_three_table_write_exception_rolls_back_all(self, test_db):
        """If exception occurs, all tables should rollback."""
        db = test_db
        
        try:
            @db_transaction_raises
            def write_three_fail():
                db._product_table.append([
                    {'barcode': '240', 'name': 'Prod4', 'price': '4.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
                ])
                
                db._user_table.append([
                    {'barcode': '2004', 'name': 'User5', 'rank': 'Admin', 'team': 'TeamE', 'is_guest': '0'}
                ])
                
                db._temporary_table.append([
                    {'barcode_prod': '241', 'name': 'TempItem2'}
                ])
                
                # Fail after all writes
                raise RuntimeError("Simulated failure after three writes")
            
            write_three_fail()
        except RuntimeError:
            pass
        
        prod_count = len(db._product_table.get())
        user_count = len(db._user_table.get())
        temp_count = len(db._temporary_table.get())
        
        assert prod_count == 0, "All tables should rollback"
        assert user_count == 0
        assert temp_count == 0

    def test_cache_consistency_after_multi_table_rollback(self, test_db):
        """Verify caches match DB after multi-table rollback."""
        db = test_db
        
        # Insert some baseline data
        db._product_table.append([
            {'barcode': '250', 'name': 'Baseline', 'price': '1.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
        ])
        
        prod_baseline = len(db._product_table.get())
        assert prod_baseline == 1
        
        # Try multi-table write that fails
        try:
            @db_transaction_raises
            def write_fail():
                db._product_table.append([
                    {'barcode': '251', 'name': 'NewProd', 'price': '2.00', 'category': 'Test', 'current_stock': '1', 'initial_stock': '1'}
                ])
                
                raise RuntimeError("Simulated failure after product write")
            
            write_fail()
        except RuntimeError:
            pass
        
        # Product cache should be back to baseline
        prod_after = len(db._product_table.get())
        assert prod_after == prod_baseline, f"Cache not refreshed: {prod_after} vs {prod_baseline}"
        
        # Verify DB matches cache
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        db_count = cur.fetchone()[0]
        con.close()
        
        assert db_count == prod_after, f"DB/cache mismatch: {db_count} vs {prod_after}"
