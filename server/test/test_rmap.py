from __future__ import annotations

import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path

import pymupdf
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

rmap = pytest.importorskip("rmap")
if shutil.which("gpg") is None:
    pytest.skip("gpg is not installed", allow_module_level=True)

from rmap import RMAPClient  # noqa: E402
from rmap.keygen import generate_keypair  # noqa: E402

from server import create_app  # noqa: E402
from tiago_invisible_text import TiagoInvisibleText  # noqa: E402

WATERMARK_KEY = secrets.token_urlsafe(32)


@pytest.fixture(scope="module")
def keys(tmp_path_factory):
    base = tmp_path_factory.mktemp("keys")
    gpg_home = Path(tempfile.mkdtemp(prefix="gpg"))
    gpg_home.chmod(0o700)
    keys_dir = base / "clients"
    keys_dir.mkdir()

    (gpg_home / "passphrase").write_text(secrets.token_urlsafe(16))
    gpg = [
        "gpg", "--batch", "--quiet", "--homedir", str(gpg_home),
        "--pinentry-mode", "loopback", "--passphrase-file", str(gpg_home / "passphrase"),
    ]
    subprocess.run(
        [*gpg, "--quick-gen-key", "Tatou Server <server@example.com>", "rsa2048", "cert,sign", "never"],
        check=True, capture_output=True,
    )
    listing = subprocess.run(
        ["gpg", "--homedir", str(gpg_home), "--with-colons", "--list-keys"],
        check=True, capture_output=True, text=True,
    ).stdout
    fingerprint = next(line.split(":")[9] for line in listing.splitlines() if line.startswith("fpr"))
    subprocess.run([*gpg, "--quick-add-key", fingerprint, "rsa2048", "encr", "never"], check=True, capture_output=True)
    server_pub = subprocess.run(
        ["gpg", "--homedir", str(gpg_home), "--armor", "--export"], check=True, capture_output=True
    ).stdout
    (base / "server_pub.asc").write_bytes(server_pub)

    clients = {}
    for identity in ("Group_07", "Group_08", "Group_99"):
        key = generate_keypair(identity, f"{identity.lower()}@example.com")
        priv = base / f"{identity}_priv.asc"
        priv.write_text(str(key))
        clients[identity] = priv
        if identity != "Group_99":
            (keys_dir / f"{identity}.asc").write_text(str(key.pubkey))

    yield {"base": base, "gpg_home": gpg_home, "keys_dir": keys_dir, "clients": clients}
    subprocess.run(["gpgconf", "--homedir", str(gpg_home), "--kill", "gpg-agent"], check=False)
    shutil.rmtree(gpg_home, ignore_errors=True)


@pytest.fixture
def app(keys, tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    source = storage / "files" / "owner" / "confidential.pdf"
    source.parent.mkdir(parents=True)
    with pymupdf.open() as doc:
        doc.new_page().insert_text((72, 72), "Confidential")
        doc.save(source)

    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("RMAP_GPG_HOME", str(keys["gpg_home"]))
    monkeypatch.setenv("RMAP_KEYS_DIR", str(keys["keys_dir"]))
    monkeypatch.setenv("RMAP_DOCUMENT_ID", "1")
    monkeypatch.setenv("RMAP_WATERMARK_KEY", WATERMARK_KEY)
    app = create_app()

    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE Documents (id INTEGER PRIMARY KEY, name TEXT, path TEXT, ownerid INTEGER)"))
        conn.execute(text("""
            CREATE TABLE Versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, documentid INTEGER, link TEXT UNIQUE,
                intended_for TEXT, secret TEXT, method TEXT, position TEXT, path TEXT
            )
        """))
        conn.execute(
            text("INSERT INTO Documents (id, name, path, ownerid) VALUES (1, 'confidential', :path, 1)"),
            {"path": str(source)},
        )
    app.config["_ENGINE"] = engine
    return app


def _client(keys, identity: str) -> RMAPClient:
    return RMAPClient(identity, keys["clients"][identity], keys["base"] / "server_pub.asc")


def _handshake(http, rmap_client: RMAPClient) -> str:
    resp1 = http.post("/api/rmap-initiate", json=rmap_client.build_msg1())
    assert resp1.status_code == 200, resp1.get_json()
    rmap_client.process_resp1(resp1.get_json())
    resp2 = http.post("/api/rmap-get-link", json=rmap_client.build_msg2())
    assert resp2.status_code == 200, resp2.get_json()
    return rmap_client.process_resp2(resp2.get_json())


def _versions(app):
    with app.config["_ENGINE"].connect() as conn:
        return conn.execute(text("SELECT link, intended_for, secret, method, path FROM Versions")).all()


def test_handshake_with_official_client_returns_watermarked_pdf(app, keys):
    http = app.test_client()
    rmap_client = _client(keys, "Group_07")

    link = _handshake(http, rmap_client)

    assert link == rmap_client.expected_link
    assert len(link) == 32
    [version] = _versions(app)
    assert version.link == link
    assert version.intended_for == "Group_07"

    pdf = http.get(f"/api/get-version/{link}")
    assert pdf.status_code == 200
    assert TiagoInvisibleText().read_secret(pdf.data, WATERMARK_KEY) == f"Group_07:{link}"


def test_each_retrieval_gets_a_distinct_watermarked_copy(app, keys):
    http = app.test_client()
    first = _handshake(http, _client(keys, "Group_07"))
    second = _handshake(http, _client(keys, "Group_07"))
    other = _handshake(http, _client(keys, "Group_08"))

    versions = {v.link: v for v in _versions(app)}
    assert len({first, second, other}) == 3
    assert len({Path(v.path).read_bytes() for v in versions.values()}) == 3
    assert versions[other].intended_for == "Group_08"

def test_modified_version_link_is_rejected(app, keys):
    http = app.test_client()
    link = _handshake(http, _client(keys, "Group_07"))

    modified = ("b" if link[0] != "b" else "c") + link[1:]

    response = http.get(f"/api/get-version/{modified}")

    assert modified != link
    assert response.status_code == 404
    assert response.get_json() == {"error": "document not found"}

def test_replayed_msg2_is_rejected(app, keys):
    http = app.test_client()
    rmap_client = _client(keys, "Group_07")
    rmap_client.process_resp1(http.post("/api/rmap-initiate", json=rmap_client.build_msg1()).get_json())
    msg2 = rmap_client.build_msg2()

    assert http.post("/api/rmap-get-link", json=msg2).status_code == 200
    assert http.post("/api/rmap-get-link", json=msg2).status_code == 400
    assert len(_versions(app)) == 1


@pytest.mark.parametrize("identity", ["Group_99", "Group_0"])
def test_unknown_identity_is_rejected(app, keys, identity):
    rmap_client = RMAPClient(identity, keys["clients"]["Group_99"], keys["base"] / "server_pub.asc")
    resp = app.test_client().post("/api/rmap-initiate", json=rmap_client.build_msg1())
    assert resp.status_code == 400
