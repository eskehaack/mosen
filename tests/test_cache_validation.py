import pytest

from src.container import Container
from src.database.data_connection import Database
from src.cache_validation import on_cache_validation


@pytest.fixture
def test_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(db_file)
    Container.set(Database, db)
    yield db
    Container.reset()


class TestCacheValidationCallback:
    def test_on_cache_validation_reports_stale_cache(self, test_db):
        con, cur = test_db._connection.connect()
        cur.execute(
            "INSERT INTO prods (barcode, name, price, category, current_stock, initial_stock) VALUES (?, ?, ?, ?, ?, ?)",
            ["123", "Beer", "5.00", "Beverage", "10", "20"],
        )
        con.commit()
        con.close()

        result = on_cache_validation(1, [])

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["src"] == "cache"
        assert "Cache validation detected changes" in result[0]["msg"]
        assert "prods" in result[0]["msg"]
