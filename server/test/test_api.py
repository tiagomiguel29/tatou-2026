from server import app

def test_healthz_route():
    client = app.test_client()
    resp = client.get("/healthz")

    assert resp.status_code == 200
    assert resp.is_json


def test_healthz_ignores_malformed_input():
    client = app.test_client()
    fuzz_cases = [
        ("null-byte-query", "?unexpected=%00", b"", 200),
        ("oversized-query", "?unexpected=" + "A" * 4096, b"", 200),
        ("malformed-json-rejection-demo", "", b"{malformed json", 200),
        ("nested-query-binary-body", "?nested[unexpected]=%7B%22x%22%3A1%7D", b"\x00\xff", 200),
    ]

    for case_name, query, body, expected_status in fuzz_cases:
        resp = client.get(
            f"/healthz{query}",
            data=body,
            content_type="application/json",
        )
        print(resp.get_data(as_text=True))

        try:
            assert resp.status_code == expected_status
            assert resp.is_json
            assert set(resp.json) == {"message", "db_connected"}
            assert isinstance(resp.json["db_connected"], bool)
        except AssertionError:
            print(f"FAIL: {case_name}")
            raise
        else:
            print(f"PASS: {case_name}")


def test_login_rejects_malformed_input():
    client = app.test_client()
    fuzz_cases = [
        ("empty-body", b""),
        ("malformed-json", b"{malformed json"),
        ("empty-json-object", b"{}"),
        ("empty-json-array", b"[]"),
        ("missing-email", b'{"password":"secret"}'),
        ("missing-password", b'{"email":"user@example.com"}'),
        ("empty-credentials", b'{"email":"","password":""}'),
    ]

    for case_name, body in fuzz_cases:
        resp = client.post(
            "/api/login",
            data=body,
            content_type="application/json",
        )
        print(f"{case_name}: {resp.get_data(as_text=True)}")

        try:
            assert resp.status_code == 400
            assert resp.is_json
            assert set(resp.json) == {"error"}
            assert isinstance(resp.json["error"], str) and resp.json["error"]
        except AssertionError:
            print(f"FAIL: {case_name}")
            raise
        else:
            print(f"PASS: {case_name}")


def test_protected_route_rejects_invalid_auth_headers():
    client = app.test_client()
    fuzz_cases = [
        ("missing-header", None),
        ("empty-header", ""),
        ("wrong-scheme", "Basic dXNlcjpwYXNz"),
        ("missing-bearer-token", "Bearer "),
        ("malformed-bearer-token", "Bearer not-a-valid-token"),
        ("oversized-bearer-token", "Bearer " + "A" * 4096),
    ]

    for case_name, auth_header in fuzz_cases:
        headers = {} if auth_header is None else {"Authorization": auth_header}
        resp = client.get("/api/list-documents", headers=headers)
        print(f"{case_name}: {resp.get_data(as_text=True)}")

        try:
            assert resp.status_code == 401
            assert resp.is_json
            assert set(resp.json) == {"error"}
            assert isinstance(resp.json["error"], str) and resp.json["error"]
        except AssertionError:
            print(f"FAIL: {case_name}")
            raise
        else:
            print(f"PASS: {case_name}")


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
