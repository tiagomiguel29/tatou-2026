import hashlib
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, event, text
from sqlalchemy.pool import StaticPool
from werkzeug.security import check_password_hash, generate_password_hash

from server import create_app
from tiago_invisible_text import TiagoInvisibleText


PASSWORD = "route-tests-only-password"
PASSWORD_HASH = generate_password_hash(PASSWORD)
WATERMARK_KEY = "route-tests-only-watermark-key"


def pdf_bytes():
    with pymupdf.open() as document:
        document.new_page().insert_text((72, 72), "Route coverage document")
        return document.tobytes()


def auth_headers(app, uid=1, login="owner"):
    token = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth").dumps(
        {"uid": uid, "login": login, "email": f"{login}@example.test"}
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    app = create_app()
    app.config.update(TESTING=True)
    engine = create_engine(
        "sqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def sqlite_functions(connection, _record):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.create_function("UNHEX", 1, bytes.fromhex)
        connection.create_function("HEX", 1, lambda value: bytes(value).hex().upper())

    with engine.begin() as connection:
        for statement in [
            """CREATE TABLE Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE, hpassword TEXT NOT NULL,
                login TEXT NOT NULL)""",
            """CREATE TABLE Documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, path TEXT NOT NULL UNIQUE,
                ownerid INTEGER NOT NULL REFERENCES Users(id) ON DELETE CASCADE,
                creation TEXT DEFAULT CURRENT_TIMESTAMP,
                sha256 BLOB NOT NULL, size INTEGER NOT NULL)""",
            """CREATE TABLE Versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                documentid INTEGER NOT NULL REFERENCES Documents(id) ON DELETE CASCADE,
                link TEXT NOT NULL UNIQUE, intended_for TEXT, secret TEXT NOT NULL,
                method TEXT NOT NULL, position TEXT, path TEXT NOT NULL)""",
        ]:
            connection.execute(text(statement))
        connection.execute(text("""INSERT INTO Users (id, email, login, hpassword)
            VALUES (:id, :email, :login, :password)"""), [
                {"id": uid, "email": f"{name}@example.test", "login": name,
                 "password": PASSWORD_HASH}
                for uid, name in [(1, "owner"), (2, "other")]
            ])
        original = pdf_bytes()
        paths = {}
        for did, uid, name in [(1, 1, "owner.pdf"), (2, 2, "other.pdf"),
                               (3, 1, "marked-original.pdf")]:
            content = original if did != 3 else TiagoInvisibleText().add_watermark(
                original, "original-marker", WATERMARK_KEY
            )
            path = storage / "files" / str(uid) / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            paths[did] = path
            connection.execute(text("""INSERT INTO Documents
                (id, name, path, ownerid, sha256, size)
                VALUES (:id, :name, :path, :uid, :sha, :size)"""),
                {"id": did, "name": name, "path": str(path), "uid": uid,
                 "sha": hashlib.sha256(content).digest(), "size": len(content)})
    app.config["_ENGINE"] = engine
    with app.test_client() as client:
        yield SimpleNamespace(
            app=app, client=client, engine=engine, storage=storage,
            paths=paths, original=original, owner=auth_headers(app),
            other=auth_headers(app, 2, "other"),
        )
    engine.dispose()


def create_version(api, did=1):
    response = api.client.post(f"/api/create-watermark/{did}", headers=api.owner,
        json={"method": "tiago-invisible-text", "intended_for": "recipient",
              "secret": "version-marker", "key": WATERMARK_KEY})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


@pytest.mark.parametrize("url", ["/", "/index.html"])
def test_home_and_static_html(api, url):
    response = api.client.get(url)
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"<html" in response.data.lower()
    response.close()


@pytest.mark.parametrize("url", ["/style.css", "/static/style.css"])
def test_static_stylesheet_bytes(api, url):
    response = api.client.get(url)
    assert response.status_code == 200
    assert response.data == (Path(__file__).parents[1] / "src/static/style.css").read_bytes()
    response.close()


def test_missing_static_file_returns_404(api):
    assert api.client.get("/not-a-static-file.css").status_code == 404


def test_health_checks_database_connection(api):
    response = api.client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json()["db_connected"] is True


def test_create_user_stores_password_hash_and_returns_account(api):
    response = api.client.post("/api/create-user", json={
        "email": " NEW@EXAMPLE.TEST ", "login": "new-user", "password": PASSWORD})
    assert response.status_code == 201
    body = response.get_json()
    assert body == {"id": 3, "email": "new@example.test", "login": "new-user"}
    with api.engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM Users WHERE id = :id"),
                                 {"id": body["id"]}).one()
    assert row.hpassword != PASSWORD
    assert check_password_hash(row.hpassword, PASSWORD)


def test_duplicate_email_is_rejected_without_another_account(api):
    response = api.client.post("/api/create-user", json={
        "email": "owner@example.test", "login": "duplicate", "password": PASSWORD})
    assert response.status_code == 409
    with api.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM Users")).scalar_one() == 2


@pytest.mark.parametrize("body", [{}, {"email": "a@b.test"},
                                  {"email": "a@b.test", "login": "a"}])
def test_create_user_requires_all_account_fields(api, body):
    assert api.client.post("/api/create-user", json=body).status_code == 400


def test_login_issues_signed_token_usable_on_protected_route(api):
    response = api.client.post("/api/login", json={
        "email": "owner@example.test", "password": PASSWORD})
    assert response.status_code == 200
    body = response.get_json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == api.app.config["TOKEN_TTL_SECONDS"]
    payload = URLSafeTimedSerializer(api.app.config["SECRET_KEY"], salt="tatou-auth").loads(
        body["token"], max_age=body["expires_in"])
    assert payload == {"uid": 1, "login": "owner", "email": "owner@example.test"}
    documents = api.client.get("/api/list-documents", headers={
        "Authorization": f"Bearer {body['token']}"})
    assert documents.status_code == 200
    assert {d["id"] for d in documents.get_json()["documents"]} == {1, 3}


@pytest.mark.parametrize("email,password", [
    ("owner@example.test", "incorrect"), ("absent@example.test", PASSWORD)])
def test_login_wrong_password_and_unknown_account_are_indistinguishable(api, email, password):
    response = api.client.post("/api/login", json={"email": email, "password": password})
    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid credentials"}


def test_document_list_contains_only_owner_metadata(api):
    response = api.client.get("/api/list-documents", headers=api.owner)
    assert response.status_code == 200
    documents = response.get_json()["documents"]
    assert {d["id"] for d in documents} == {1, 3}
    document = next(d for d in documents if d["id"] == 1)
    assert document["size"] == len(api.original)
    assert document["sha256"].lower() == hashlib.sha256(api.original).hexdigest()
    assert "path" not in document and "ownerid" not in document


@pytest.mark.parametrize("url", ["/api/get-document/1", "/api/get-document?id=1",
                                  "/api/get-document?documentid=1"])
def test_original_download_preserves_bytes_and_private_cache_headers(api, url):
    response = api.client.get(url, headers=api.owner)
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data == api.original
    assert response.headers["ETag"].strip('"') == hashlib.sha256(api.original).hexdigest()
    assert "private" in response.headers["Cache-Control"]
    response.close()


@pytest.mark.parametrize("did", [2, 999])
def test_foreign_and_missing_originals_return_same_404(api, did):
    response = api.client.get(f"/api/get-document/{did}", headers=api.owner)
    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}


@pytest.mark.parametrize("url", ["/api/list-versions/1", "/api/list-versions?id=1",
                                  "/api/list-versions?documentid=1"])
def test_list_versions_returns_only_requested_owned_document(api, url):
    version = create_version(api)
    response = api.client.get(url, headers=api.owner)
    assert response.status_code == 200
    assert response.get_json()["versions"] == [{
        "id": version["id"], "documentid": 1, "link": version["link"],
        "intended_for": "recipient", "secret": "version-marker",
        "method": "tiago-invisible-text"}]
    assert api.client.get(url, headers=api.other).get_json() == {"versions": []}


def test_list_all_versions_filters_owner_and_omits_secret(api):
    version = create_version(api)
    response = api.client.get("/api/list-all-versions", headers=api.owner)
    assert response.status_code == 200
    assert response.get_json()["versions"] == [{
        "id": version["id"], "documentid": 1, "link": version["link"],
        "intended_for": "recipient", "method": "tiago-invisible-text"}]
    assert api.client.get("/api/list-all-versions", headers=api.other).get_json() == {"versions": []}


def test_public_version_download_contains_recipient_marker(api):
    version = create_version(api)
    response = api.client.get(f"/api/get-version/{version['link']}")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert TiagoInvisibleText().read_secret(response.data, WATERMARK_KEY) == "version-marker"
    assert api.paths[1].read_bytes() == api.original
    response.close()


@pytest.mark.parametrize("method,url,kwargs", [
    ("delete", "/api/delete-document/1", {}),
    ("delete", "/api/delete-document?id=1", {}),
    ("post", "/api/delete-document", {"json": {"id": 1}}),
])
def test_delete_removes_original_and_cascades_version_record(api, method, url, kwargs):
    create_version(api)
    response = getattr(api.client, method)(url, headers=api.owner, **kwargs)
    assert response.status_code == 200
    assert response.get_json()["deleted"] is True
    assert response.get_json()["file_deleted"] is True
    assert not api.paths[1].exists()
    assert api.paths[2].exists()
    with api.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM Documents WHERE id=1")).scalar_one() == 0
        assert connection.execute(text("SELECT COUNT(*) FROM Versions WHERE documentid=1")).scalar_one() == 0


@pytest.mark.parametrize("did", [2, 999])
def test_delete_cannot_remove_foreign_document(api, did):
    response = api.client.delete(f"/api/delete-document/{did}", headers=api.owner)
    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}
    assert api.paths[2].read_bytes() == api.original


def test_method_listing_preserves_registered_methods(api):
    response = api.client.get("/api/get-watermarking-methods")
    assert response.status_code == 200
    methods = response.get_json()
    assert methods["count"] == 4
    assert {m["name"] for m in methods["methods"]} == {
        "toy-eof", "tiago-invisible-text", "metadata-hmac", "secret-producer"}
    assert all(m["description"] for m in methods["methods"])


@pytest.mark.parametrize("url", ["/api/read-watermark/3", "/api/read-watermark?id=3"])
def test_read_watermark_recovers_owned_document_marker(api, url):
    response = api.client.post(url, headers=api.owner, json={
        "method": "tiago-invisible-text", "key": WATERMARK_KEY})
    assert response.status_code == 201
    assert response.get_json() == {"documentid": 3, "secret": "original-marker",
                                  "method": "tiago-invisible-text", "position": None}


@pytest.mark.parametrize("operation", ["create-watermark", "read-watermark"])
def test_watermark_operations_reject_foreign_owner_without_side_effects(api, operation):
    files_before = {p: p.read_bytes() for p in api.storage.rglob("*") if p.is_file()}
    response = api.client.post(f"/api/{operation}/2", headers=api.owner, json={
        "method": "tiago-invisible-text", "key": WATERMARK_KEY,
        "secret": "foreign-attempt", "intended_for": "recipient"})
    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}
    assert files_before == {p: p.read_bytes() for p in api.storage.rglob("*") if p.is_file()}
    with api.engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM Versions")).scalar_one() == 0


def test_wrong_watermark_key_does_not_return_secret(api):
    response = api.client.post("/api/read-watermark/3", headers=api.owner,
        json={"method": "tiago-invisible-text", "key": "wrong-key"})
    assert response.status_code == 400
    assert "secret" not in response.get_json()


@pytest.mark.parametrize("method,url", [
    ("get", "/api/list-documents"), ("get", "/api/list-versions/1"),
    ("get", "/api/list-all-versions"), ("get", "/api/get-document/1"),
    ("post", "/api/upload-document"), ("delete", "/api/delete-document/1"),
    ("post", "/api/create-watermark/1"), ("post", "/api/read-watermark/1"),
])
def test_private_routes_require_authentication(api, method, url):
    response = getattr(api.client, method)(url)
    assert response.status_code == 401
    assert response.get_json() == {"error": "Missing or invalid Authorization header"}


def test_expired_authentication_is_rejected_and_logged(api, caplog):
    api.app.config["TOKEN_TTL_SECONDS"] = -1
    with caplog.at_level("WARNING", logger="server"):
        response = api.client.get("/api/list-documents", headers=api.owner)
    assert response.status_code == 401
    assert response.get_json() == {"error": "Token expired"}
    assert "reason=expired_token" in caplog.text
    assert api.owner["Authorization"] not in caplog.text
