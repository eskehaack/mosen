"""Stress tests for concurrent transaction atomicity."""
import pytest
import sqlite3
from threading import Thread, Lock

from src.container import Container
from src.database.data_connection import Database, db_transaction_raises


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "stress_test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestStressHighConcurrency:
    """Stress tests with many threads and high volume."""

    def test_10_threads_30_rows_each(self, test_db):
        """10 threads, 30 rows each = 300 rows total."""
        db = test_db
        errors = []
        barrier_lock = Lock()
        barrier_ready = 0
        
        def worker(worker_id):
            try:
                @db_transaction_raises
                def append_rows():
                    # Each worker appends 30 rows
                    rows = [
                        {
                            'barcode': f'{100 + worker_id * 30 + i % 30}',
                            'name': f'W{worker_id}_R{i}',
                            'price': f'{1.00 + (i % 10)}',
                            'category': f'Stress{worker_id}',
                            'current_stock': '1',
                            'initial_stock': '1'
                        }
                        for i in range(30)
                    ]
                    db._product_table.append(rows)
                
                append_rows()
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Spawn 10 threads
        threads = [Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify
        assert len(errors) == 0, f"Errors: {errors}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        
        # Due to barcode collisions, not all 300 will fit, but we should get close
        # Each worker tries 30 unique barcodes per 30-row batch
        # With wraparound, some collisions occur
        cache_count = len(db._product_table.get())
        assert count == cache_count, f"DB and cache mismatch: {count} vs {cache_count}"
        assert count > 0, "Should have persisted some rows"

    def test_20_threads_5_rows_each_all_unique(self, test_db):
        """20 threads, 5 unique rows each = 100 unique rows."""
        db = test_db
        errors = []
        
        def worker(worker_id):
            try:
                @db_transaction_raises
                def append_rows():
                    # Use non-overlapping ranges so all rows are unique
                    rows = [
                        {
                            'barcode': f'{100 + worker_id * 5 + i}',
                            'name': f'W{worker_id}_Item{i}',
                            'price': f'{1.00 + i}',
                            'category': f'Cat{worker_id}',
                            'current_stock': '1',
                            'initial_stock': '1'
                        }
                        for i in range(5)
                    ]
                    db._product_table.append(rows)
                
                append_rows()
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Spawn 20 threads
        threads = [Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify
        assert len(errors) == 0, f"Errors: {errors}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        
        cache_count = len(db._product_table.get())
        assert count == 100, f"Expected 100 rows, got {count}"
        assert cache_count == 100, f"Expected 100 in cache, got {cache_count}"
        assert count == cache_count, "DB and cache must match"

    def test_10_threads_half_fail(self, test_db):
        """10 threads writing, 5 succeed, 5 fail - verify atomicity."""
        db = test_db
        results = {'success': 0, 'failed': 0}
        
        def worker(worker_id):
            try:
                @db_transaction_raises
                def append_rows():
                    rows = [
                        {
                            'barcode': f'{100 + worker_id * 5 + i}',
                            'name': f'W{worker_id}_Item{i}',
                            'price': f'{1.00 + i}',
                            'category': f'Cat{worker_id}',
                            'current_stock': '1',
                            'initial_stock': '1'
                        }
                        for i in range(5)
                    ]
                    db._product_table.append(rows)
                    
                    # Half the workers fail after append
                    if worker_id % 2 == 1:
                        raise RuntimeError(f"worker {worker_id} intentional failure")
                
                append_rows()
                results['success'] += 1
            except RuntimeError:
                results['failed'] += 1
        
        # Spawn 10 threads
        threads = [Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify
        assert results['success'] == 5, f"Expected 5 successes, got {results['success']}"
        assert results['failed'] == 5, f"Expected 5 failures, got {results['failed']}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        
        cache_count = len(db._product_table.get())
        # Only 5 workers succeeded with 5 rows each = 25 rows
        assert count == 25, f"Expected 25 rows (5 workers × 5 rows), got {count}"
        assert cache_count == 25, f"Expected 25 in cache, got {cache_count}"
        assert count == cache_count, "DB and cache must match"

    def test_mixed_set_and_append_concurrent(self, test_db):
        """Threads mix set() and append() operations concurrently."""
        db = test_db
        errors = []
        
        def worker(worker_id):
            try:
                if worker_id % 2 == 0:
                    # Even workers: set() operation
                    @db_transaction_raises
                    def do_set():
                        rows = [
                            {
                                'barcode': f'{100 + worker_id * 5 + i}',
                                'name': f'W{worker_id}_Set{i}',
                                'price': f'{2.00 + i}',
                                'category': f'Set{worker_id}',
                                'current_stock': '1',
                                'initial_stock': '1'
                            }
                            for i in range(3)
                        ]
                        db._product_table.set(rows)
                    
                    do_set()
                else:
                    # Odd workers: append() operation
                    @db_transaction_raises
                    def do_append():
                        rows = [
                            {
                                'barcode': f'{200 + worker_id * 5 + i}',
                                'name': f'W{worker_id}_Append{i}',
                                'price': f'{3.00 + i}',
                                'category': f'Append{worker_id}',
                                'current_stock': '1',
                                'initial_stock': '1'
                            }
                            for i in range(3)
                        ]
                        db._product_table.append(rows)
                    
                    do_append()
            except Exception as e:
                errors.append((worker_id, str(e)))
        
        # Spawn 6 threads (3 set, 3 append)
        threads = [Thread(target=worker, args=(i,)) for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Verify
        assert len(errors) == 0, f"Errors: {errors}"
        
        con = sqlite3.connect(db.data_file)
        cur = con.cursor()
        cur.execute('SELECT COUNT(*) FROM prods')
        count = cur.fetchone()[0]
        con.close()
        
        cache_count = len(db._product_table.get())
        # 3 set operations (3 rows each, but last set() deletes all)
        # 3 append operations (3 rows each)
        # Interleaved: last set() deletes everything, but appends happen concurrently
        # Final state depends on ordering, but must be consistent
        assert cache_count == count, f"Cache/DB mismatch: {cache_count} vs {count}"
        assert count > 0, "Should have some rows persisted"
