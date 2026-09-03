import pytest


@pytest.fixture
def db_ready(db: None) -> None:
    """Alias for pytest-django's `db`; later phases extend this with seed data."""
