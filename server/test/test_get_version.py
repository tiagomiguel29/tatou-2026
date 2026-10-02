from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from server import create_app


def test_nonexistent_version_link_is_rejected(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()

    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-pytest-only")

    app = create_app()

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE Versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    documentid INTEGER,
                    link TEXT UNIQUE,
                    intended_for TEXT,
                    secret TEXT,
                    method TEXT,
                    position TEXT,
                    path TEXT
                )
                """
            )
        )

    app.config["_ENGINE"] = engine

    response = app.test_client().get(
        "/api/get-version/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}
