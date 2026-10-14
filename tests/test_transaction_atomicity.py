"""Comprehensive atomicity tests for transaction semantics."""
import pytest
import sqlite3
from threading import Thread

from src.container import Container
from src.database.data_connection import Database, db_transaction_raises


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "atomicity_test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestNestedDecoratorCalls:
    """Test that @db_transaction calls can be nested safely."""

    def test_nested_decorated_functions_commit_atomically(self, test_db):
        # Arrange
        db = test_db
        row1 = {'barcode': '300', 'name': 'D', 'price': '4.00', 'category': 'A', 'current_stock': '1', 'initial_stock': '1'}
        row2 = {'barcode': '301', 'name': 'E', 'price': '5.00', 'category': 'B', 'current_stock': '1', 'initial_stock': '1'}
        
        @db_transaction_raises
        def inner_write():
            db._product_table.set([row1])
        
        @db_transaction_raises
        def outer_write():
            inner_write()
            db._product_table.append([row2])
        
        # Act
        outer_write()
        
        # Assert - both rows committed
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        assert count == 2

    def test_nested_decorated_functions_rollback_atomically(self, test_db):
        # Arrange
        db = test_db
        row1 = {'barcode': '400', 'name': 'F', 'price': '6.00', 'category': 'C', 'current_stock': '1', 'initial_stock': '1'}
        
        @db_transaction_raises
        def inner_write():
            db._product_table.set([row1])
        
        @db_transaction_raises
        def outer_write_fails():
            inner_write()
            raise ValueError("outer fails after inner")
        
        # Act
        with pytest.raises(ValueError):
            outer_write_fails()
        
        # Assert - nothing committed
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        assert count == 0


class TestMixedSetAndAppendInSingleTransaction:
    """Test set + append in one transaction rolls back together."""

    def test_set_then_append_succeeds(self, test_db):
        # Arrange
        db = test_db
        row1 = {'barcode': '500', 'name': 'H', 'price': '8.00', 'category': 'E', 'current_stock': '1', 'initial_stock': '1'}
        row2 = {'barcode': '501', 'name': 'I', 'price': '9.00', 'category': 'F', 'current_stock': '1', 'initial_stock': '1'}
        
        # Act
        def tx_body():
            db._product_table.set([row1])
            db._product_table.append([row2])
        
        db.execute_in_transaction(tx_body)
        
        # Assert - both rows committed
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        assert count == 2
        assert len(db._product_table.get()) == 2

    def test_set_then_append_fails_rolls_back_both(self, test_db):
        # Arrange
        db = test_db
        row1 = {'barcode': '600', 'name': 'J', 'price': '10.00', 'category': 'G', 'current_stock': '1', 'initial_stock': '1'}
        row2 = {'barcode': '601', 'name': 'K', 'price': '11.00', 'category': 'H', 'current_stock': '1', 'initial_stock': '1'}
        
        # Act
        def tx_body():
            db._product_table.set([row1])
            db._product_table.append([row2])
            raise Exception("fail after mixed ops")
        
        with pytest.raises(Exception):
            db.execute_in_transaction(tx_body).raise_if_error()
        
        # Assert - nothing committed
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        assert count == 0
        assert len(db._product_table.get()) == 0


class TestCacheMatchesDbAfterRollback:
    """Test that cache exactly matches DB after a rollback."""

    def test_cache_matches_db_after_exception_during_write(self, test_db):
        # Arrange
        db = test_db
        row1 = {'barcode': '700', 'name': 'L', 'price': '12.00', 'category': 'I', 'current_stock': '1', 'initial_stock': '1'}
        row2 = {'barcode': '701', 'name': 'M', 'price': '13.00', 'category': 'J', 'current_stock': '1', 'initial_stock': '1'}
        
        # First insert a row
        db._product_table.set([row1])
        initial_cache = db._product_table.get().to_dict(orient='records')
        
        # Act - attempt an operation that fails
        def tx_body():
            db._product_table.append([row2])
            raise Exception("crash after append")
        
        with pytest.raises(Exception):
            db.execute_in_transaction(tx_body).raise_if_error()
        
        # Assert - cache matches initial state (rollback happened)
        final_cache = db._product_table.get().to_dict(orient='records')
        assert final_cache == initial_cache
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT barcode FROM prods ORDER BY barcode')
        db_barcodes = [str(row[0]) for row in cur.fetchall()]
        con.close()
        
        cache_barcodes = [str(row['barcode']) for row in final_cache]
        assert db_barcodes == cache_barcodes


class TestConcurrentWriteAtomicity:
    """Test that concurrent transactions don't corrupt data or cache - lock ensures atomicity."""

    def test_concurrent_appends_from_multiple_threads(self, test_db):
        # Arrange - multiple threads appending rows concurrently
        db = test_db
        errors = []
        
        def worker(worker_id):
            try:
                @db_transaction_raises
                def append_rows():
                    rows = [
                        {
                            'barcode': f'{100 + worker_id * 10 + i}',
                            'name': f'W{worker_id}Item{i}',
                            'price': f'{1.00 + i}',
                            'category': f'Cat{worker_id}',
                            'current_stock': '1',
                            'initial_stock': '1'
                        }
                        for i in range(3)
                    ]
                    db._product_table.append(rows)
                
                append_rows()
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Act - spawn 3 threads all appending concurrently
        threads = [Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Assert - no errors, all 9 rows persisted atomically
        assert len(errors) == 0, f"Errors during concurrent writes: {errors}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        db_count = cur.fetchone()[0]
        con.close()
        
        cache_count = len(db._product_table.get())
        assert db_count == 9, f"Expected 9 rows in DB (3 threads × 3 rows), got {db_count}"
        assert cache_count == 9, f"Expected 9 rows in cache, got {cache_count}"
        assert db_count == cache_count, "DB and cache must match"

    def test_concurrent_writes_with_partial_failure(self, test_db):
        # Arrange - concurrent writes where one fails; lock ensures only successful writes persist
        db = test_db
        results = {'success': 0, 'failed': 0}
        
        def worker(worker_id):
            try:
                @db_transaction_raises
                def append_rows():
                    rows = [
                        {
                            'barcode': f'{150 + worker_id * 10 + i}',
                            'name': f'W{worker_id}Item{i}',
                            'price': f'{1.00 + i}',
                            'category': f'Cat{worker_id}',
                            'current_stock': '1',
                            'initial_stock': '1'
                        }
                        for i in range(3)
                    ]
                    db._product_table.append(rows)
                    
                    # Worker 1 intentionally fails after append
                    if worker_id == 1:
                        raise RuntimeError("worker 1 intentional failure")
                
                append_rows()
                results['success'] += 1
            except RuntimeError:
                results['failed'] += 1
        
        # Act - spawn threads, one will fail
        threads = [Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Assert - 2 succeeded, 1 failed; only successful rows persisted
        assert results['success'] == 2, f"Expected 2 successful writes, got {results['success']}"
        assert results['failed'] == 1, f"Expected 1 failed write, got {results['failed']}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        db_count = cur.fetchone()[0]
        con.close()
        
        cache_count = len(db._product_table.get())
        # Only 2 workers' data persisted (6 rows); worker 1's write rolled back
        assert db_count == 6, f"Expected 6 rows in DB (2 workers × 3 rows), got {db_count}"
        assert cache_count == 6, f"Expected 6 rows in cache, got {cache_count}"
        assert db_count == cache_count, "DB and cache must match"
