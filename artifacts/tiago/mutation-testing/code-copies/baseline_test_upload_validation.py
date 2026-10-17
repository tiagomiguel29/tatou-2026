import io
from pathlib import Path

import pymupdf
import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

from server import create_app


@pytest.fixture
def upload_app(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    app = create_app()
    app.config.update(TESTING=True)

    engine = create_engine(
        "sqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def add_sqlite_functions(connection, _record):
        connection.create_function(
            "UNHEX", 1, lambda value: bytes.fromhex(value) if value else None
        )
        connection.create_function(
            "HEX", 1, lambda value: bytes(value).hex().upper() if value else None
        )

    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE Documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                path TEXT NOT NULL,
                ownerid INTEGER NOT NULL,
                sha256 BLOB NOT NULL,
                size INTEGER NOT NULL,
                creation TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """))

    app.config["_ENGINE"] = engine
    return app


def _auth_header(app):
    token = URLSafeTimedSerializer(
        app.config["SECRET_KEY"], salt="tatou-auth"
    ).dumps({"uid": 1, "login": "owner", "email": "owner@example.test"})
    return {"Authorization": f"Bearer {token}"}


def _pdf_bytes():
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Valid upload")
        return document.tobytes()


def _upload(app, data, filename="document.pdf"):
    return app.test_client().post(
        "/api/upload-document",
        data={"file": (io.BytesIO(data), filename)},
        headers=_auth_header(app),
        content_type="multipart/form-data",
    )


def _stored_files(app):
    return [path for path in Path(app.config["STORAGE_DIR"]).rglob("*") if path.is_file()]


def test_accepts_structurally_valid_pdf(upload_app):
    response = _upload(upload_app, _pdf_bytes())

    assert response.status_code == 201, response.get_json()
    assert response.get_json()["size"] > 0
    assert len(_stored_files(upload_app)) == 1


@pytest.mark.parametrize(
    "data",
    [
        b"plain text pretending to be a PDF",
        b"%PDF-1.7\nnot actually a PDF\n%%EOF\n",
        _pdf_bytes() + b"malicious trailing payload",
    ],
    ids=["wrong-magic", "fake-pdf-header", "trailing-payload"],
)
def test_rejects_non_pdf_and_removes_file(upload_app, data):
    response = _upload(upload_app, data)

    assert response.status_code == 400
    assert response.get_json() == {"error": "only valid PDF files are accepted"}
    assert _stored_files(upload_app) == []
    with upload_app.config["_ENGINE"].connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM Documents")).scalar_one() == 0
