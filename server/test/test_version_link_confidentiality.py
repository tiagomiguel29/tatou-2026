import hashlib
from pathlib import Path

import pymupdf
import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool

import server as server_module
from tiago_invisible_text import TiagoInvisibleText
from rotate_version_links import rotate_legacy_links


@pytest.fixture
def version_app(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    source = storage / "files/owner/source.pdf"
    source.parent.mkdir(parents=True)
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Confidential document")
        document.save(source)
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    app = server_module.create_app()
    app.config.update(TESTING=True)
    engine = create_engine("sqlite://", poolclass=StaticPool,
                           connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("""CREATE TABLE Documents (
            id INTEGER PRIMARY KEY, name TEXT, path TEXT, ownerid INTEGER)"""))
        connection.execute(text("""CREATE TABLE Versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, documentid INTEGER,
            link TEXT UNIQUE, intended_for TEXT, secret TEXT, method TEXT,
            position TEXT, path TEXT)"""))
        connection.execute(text("""INSERT INTO Documents VALUES
            (1, 'confidential.pdf', :path, 1)"""), {"path": str(source)})
    app.config["_ENGINE"] = engine
    yield app
    engine.dispose()


def create_version(app, secret="first-secret"):
    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps(
        {"uid": 1, "login": "owner", "email": "owner@example.test"})
    return app.test_client().post("/api/create-watermark/1", headers={
        "Authorization": f"Bearer {token}"}, json={
            "method": "tiago-invisible-text", "intended_for": "recipient",
            "secret": secret, "key": "test-watermark-key"})


def versions(app):
    with app.config["_ENGINE"].connect() as connection:
        return connection.execute(text("SELECT * FROM Versions ORDER BY id")).all()


def test_filename_prediction_no_longer_retrieves_pdf(version_app):
    prediction = hashlib.sha1(b"confidential__recipient.pdf").hexdigest()
    response = create_version(version_app)
    assert response.status_code == 201, response.get_json()
    link = response.get_json()["link"]
    assert link != prediction
    client = version_app.test_client()
    assert client.get(f"/api/get-version/{prediction}").status_code == 404
    download = client.get(f"/api/get-version/{link}")
    assert download.status_code == 200
    assert download.mimetype == "application/pdf"
    assert TiagoInvisibleText().read_secret(download.data, "test-watermark-key") == "first-secret"


def test_link_uses_256_bit_random_token(version_app, monkeypatch):
    requested_sizes = []
    expected = "a-random-token-independent-of-document-name"

    def random_token(size):
        requested_sizes.append(size)
        return expected

    monkeypatch.setattr(server_module.secrets, "token_urlsafe", random_token)
    response = create_version(version_app)
    assert response.status_code == 201, response.get_json()
    assert requested_sizes == [32]
    assert response.get_json()["link"] == expected
    assert versions(version_app)[0].link == expected


def test_repeated_recipient_has_unique_links_and_preserves_both_copies(version_app):
    first = create_version(version_app, "first-secret")
    second = create_version(version_app, "second-secret")
    assert first.status_code == second.status_code == 201
    links = [first.get_json()["link"], second.get_json()["link"]]
    assert links[0] != links[1]
    rows = versions(version_app)
    assert len(rows) == 2
    assert rows[0].path != rows[1].path
    for link, secret in zip(links, ["first-secret", "second-secret"]):
        response = version_app.test_client().get(f"/api/get-version/{link}")
        assert response.status_code == 200
        assert TiagoInvisibleText().read_secret(response.data, "test-watermark-key") == secret


def test_token_collision_does_not_overwrite_existing_copy(version_app, monkeypatch):
    monkeypatch.setattr(server_module.secrets, "token_urlsafe", lambda size: "same-token")
    first = create_version(version_app)
    assert first.status_code == 201
    download = version_app.test_client().get("/api/get-version/same-token")
    assert download.status_code == 200
    original = download.data
    second = create_version(version_app, "second-secret")
    assert second.status_code >= 400
    assert len(versions(version_app)) == 1
    assert version_app.test_client().get("/api/get-version/same-token").data == original


def test_database_failure_removes_only_the_new_copy(version_app):
    first = create_version(version_app)
    assert first.status_code == 201
    original = versions(version_app)[0]

    def fail_insert(connection, cursor, statement, parameters, context, executemany):
        if "INSERT INTO Versions" in statement:
            raise RuntimeError("simulated database failure")

    event.listen(version_app.config["_ENGINE"], "before_cursor_execute", fail_insert)
    response = create_version(version_app, "second-secret")
    assert response.status_code == 503
    assert len(versions(version_app)) == 1
    stored = list(Path(version_app.config["STORAGE_DIR"]).rglob("watermarks/*.pdf"))
    assert stored == [Path(original.path)]
    assert version_app.test_client().get(f"/api/get-version/{original.link}").status_code == 200


def test_legacy_rotation_revokes_old_url_and_preserves_other_links(version_app):
    assert create_version(version_app).status_code == 201
    issued = versions(version_app)[0]
    legacy = hashlib.sha1(b"confidential__recipient.pdf").hexdigest()
    rmap = "a" * 32
    with version_app.config["_ENGINE"].begin() as connection:
        connection.execute(text("""INSERT INTO Versions (documentid, link, path)
            VALUES (1, :legacy, :path), (1, :rmap, :path)"""),
                           {"legacy": legacy, "rmap": rmap, "path": issued.path})
        assert rotate_legacy_links(connection) == 1
        assert connection.execute(text("SELECT COUNT(*) FROM Versions WHERE link = :link"),
                                  {"link": legacy}).scalar_one() == 1
        assert rotate_legacy_links(connection, apply=True) == 1
        assert rotate_legacy_links(connection, apply=True) == 0
    rows = versions(version_app)
    assert rows[0].link == issued.link
    assert rows[2].link == rmap
    client = version_app.test_client()
    assert client.get(f"/api/get-version/{legacy}").status_code == 404
    assert client.get(f"/api/get-version/{rows[1].link}").status_code == 200
    assert client.get(f"/api/get-version/{rmap}").status_code == 200
    assert client.get(f"/api/get-version/{issued.link}").status_code == 200


def test_legacy_rotation_is_transactional(version_app):
    assert create_version(version_app).status_code == 201
    legacy = "b" * 40
    engine = version_app.config["_ENGINE"]
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO Versions (link) VALUES (:link)"), {"link": legacy})
    with pytest.raises(RuntimeError, match="abort"):
        with engine.begin() as connection:
            assert rotate_legacy_links(connection, apply=True) == 1
            raise RuntimeError("abort")
    assert versions(version_app)[1].link == legacy
