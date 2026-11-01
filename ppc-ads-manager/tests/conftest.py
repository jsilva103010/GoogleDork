import pytest

from app import config


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Every test gets its own throwaway JSON store instead of touching db/store.json."""
    monkeypatch.setattr(config, "DB_FILE", tmp_path / "test_store.json")
    yield
