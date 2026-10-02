from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from server import create_app


def _test_app(tmp_path, monkeypatch):
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
    return app, engine


def test_nonexistent_version_link_is_rejected(tmp_path, monkeypatch):
    app, _ = _test_app(tmp_path, monkeypatch)

    response = app.test_client().get(
        "/api/get-version/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}


def test_modified_version_link_is_rejected(tmp_path, monkeypatch):
    app, engine = _test_app(tmp_path, monkeypatch)

    valid_link = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaab"

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO Versions
                    (documentid, link, intended_for, secret, method, position, path)
                VALUES
                    (1, :link, 'Group_07', 'test-secret', 'test', 'center', '/tmp/test.pdf')
                """
            ),
            {"link": valid_link},
        )

    modified_link = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaac"

    assert modified_link != valid_link

    response = app.test_client().get(
        f"/api/get-version/{modified_link}"
    )

    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}
