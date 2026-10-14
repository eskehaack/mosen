import os
import pytest
from src.database.data_connection import Database
from src.container import Container


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test.db")
    db = Database(data_file=db_file)
    Container.set(Database, db)
    yield db
    # Teardown: reset container and remove file
    Container.reset()
    try:
        os.remove(db_file)
    except OSError:
        pass
