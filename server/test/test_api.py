from server import app


def test_healthz_route():
    client = app.test_client()
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.is_json


def test_invalid_bearer_token_is_logged(caplog):
    client = app.test_client()

    with caplog.at_level("WARNING", logger="server"):
        resp = client.get(
            "/api/list-documents",
            headers={"Authorization": "Bearer deliberately-invalid-test-token"},
        )

    assert resp.status_code == 401
    assert "security_event=authentication_failed" in caplog.text
    assert "reason=invalid_token" in caplog.text
    assert "deliberately-invalid-test-token" not in caplog.text

def test_missing_authorization_is_logged(caplog):
    client = app.test_client()

    with caplog.at_level("WARNING", logger="server"):
        resp = client.get("/api/list-documents")

    assert resp.status_code == 401
    assert "security_event=authentication_failed" in caplog.text
    assert "reason=missing_or_invalid_authorization_header" in caplog.text
