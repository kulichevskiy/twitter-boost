import os
import sys
from pathlib import Path

import pytest

_DB = Path(__file__).resolve().parent / ".test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"
os.environ["SOURCE_LISTS"] = "fake"
os.environ["SOURCE_TWEETS"] = "fake"
os.environ["SOURCE_PROFILES"] = "fake"
os.environ["MY_HANDLE"] = "me"
os.environ["CRM_API_TOKEN"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session", autouse=True)
def schema():
    for f in _DB.parent.glob(".test.db*"):
        f.unlink()
    from app.migrate import upgrade_database

    upgrade_database()
    yield


@pytest.fixture(autouse=True)
def fresh_db(schema):
    from sqlalchemy import text

    from app.db import engine
    from app.models import Base
    from app.sources import fake

    with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DELETE FROM "{table.name}"'))
    fake._state["epoch"] = 0
    yield
