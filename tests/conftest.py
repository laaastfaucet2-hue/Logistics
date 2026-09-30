"""All tests use pytest's temporary directories. Real database/ is never touched."""
import pytest
from app import create_app
from core import paths
from data_access import storage, database, dataguard
from services.bootstrap import bootstrap_year_files


@pytest.fixture
def app(tmp_path, monkeypatch):
    data = tmp_path / "database"
    monkeypatch.setenv("LOGISTICS_DATA_DIR", str(data))
    monkeypatch.delenv("LOGISTICS_PREVIEW", raising=False)
    monkeypatch.delenv("LOGISTICS_DESKTOP", raising=False)
    for module in (paths, storage, database, dataguard):
        monkeypatch.setattr(module, "DATA_DIR", data)
    monkeypatch.setattr(database, "DB_PATH", data / "system.db")
    monkeypatch.setattr(dataguard, "BACKUP_DIR", data / "backups")
    application = create_app()
    application.config["TESTING"] = True
    if storage.create_year(2031):
        bootstrap_year_files(2031)
    database.set_user_context(1, 2031, 9)
    yield application


@pytest.fixture
def client(app):
    client = app.test_client()
    response = client.post("/login", data={"username": "mostafa", "password": "779"})
    assert response.status_code == 302
    return client
