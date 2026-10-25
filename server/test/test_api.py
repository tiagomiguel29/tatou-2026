import io

from itsdangerous import URLSafeTimedSerializer

from server import app


def _test_auth_headers():
    serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="tatou-auth")
    token = serializer.dumps({"uid": 1, "login": "fuzz-user", "email": "fuzz@example.com"})
    return {"Authorization": f"Bearer {token}"}


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


def test_create_user_rejects_malformed_input():
    client = app.test_client()
    fuzz_cases = [
        ("empty-body", b""),
        ("malformed-json", b"{malformed json"),
        ("null-json", b"null"),
        ("empty-object", b"{}"),
        ("missing-email", b'{"login":"user","password":"secret"}'),
        ("missing-login", b'{"email":"user@example.com","password":"secret"}'),
        ("missing-password", b'{"email":"user@example.com","login":"user"}'),
        ("non-object-json-array", b'["unexpected"]'),
    ]

    for case_name, body in fuzz_cases:
        resp = client.post(
            "/api/create-user",
            data=body,
            content_type="application/json",
        )
        print(f"{case_name}: {resp.get_data(as_text=True)}")

        try:
            assert resp.status_code == 400, (
                f"{case_name}: expected HTTP 400, got {resp.status_code}"
            )
            assert resp.is_json
            assert set(resp.json) == {"error"}
            assert isinstance(resp.json["error"], str) and resp.json["error"]
        except AssertionError:
            print(f"FAIL: {case_name}")
            raise
        else:
            print(f"PASS: {case_name}")


def test_get_watermarking_methods_ignores_unusual_query():
    client = app.test_client()
    fuzz_queries = [
        ("null-byte-query", "?unexpected=%00"),
        ("oversized-query", "?unexpected=" + "A" * 4096),
        ("repeated-query-keys", "?method=one&method=two"),
        ("nested-json-query", "?filter=%7B%22method%22%3A%22unknown%22%7D"),
    ]

    for case_name, query in fuzz_queries:
        resp = client.get(f"/api/get-watermarking-methods{query}")
        print(f"{case_name}: {resp.get_data(as_text=True)}")

        try:
            assert resp.status_code == 200
            assert resp.is_json
            assert isinstance(resp.json["methods"], list)
            assert isinstance(resp.json["count"], int)
            assert resp.json["count"] == len(resp.json["methods"])
            assert all(
                set(method) == {"name", "description"}
                for method in resp.json["methods"]
            )
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


def test_upload_document_rejects_missing_or_invalid_file():
    client = app.test_client()
    fuzz_cases = [
        ("missing-file", None),
        ("json-instead-of-file", b'{"file":null}'),
        ("plain-text-instead-of-file", b"not a multipart upload"),
    ]

    for case_name, body in fuzz_cases:
        request_args = {"headers": _test_auth_headers()}
        if body is not None:
            request_args.update(data=body, content_type="application/json")
        resp = client.post("/api/upload-document", **request_args)
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



def test_get_document_rejects_invalid_ids():
    client = app.test_client()
    fuzz_queries = [
        ("missing-id", ""),
        ("non-numeric-id", "?id=not-a-number"),
        ("oversized-id", "?id=" + "9" * 5000),
    ]

    for case_name, query in fuzz_queries:
        resp = client.get(f"/api/get-document{query}", headers=_test_auth_headers())
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


def test_create_watermark_rejects_invalid_input():
    client = app.test_client()
    fuzz_cases = [
        ("empty-body", b"", ""),
        ("malformed-json", b"{malformed json", ""),
        ("missing-fields", b'{"id":1}', ""),
        ("non-numeric-query-id", b"{}", "?id=not-a-number"),
    ]

    for case_name, body, query in fuzz_cases:
        resp = client.post(
            f"/api/create-watermark{query}",
            data=body,
            content_type="application/json",
            headers=_test_auth_headers(),
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


def test_read_watermark_rejects_invalid_input():
    client = app.test_client()
    fuzz_cases = [
        ("empty-body", b"", ""),
        ("malformed-json", b"{malformed json", ""),
        ("missing-fields", b'{"id":1}', ""),
        ("non-numeric-query-id", b"{}", "?id=not-a-number"),
    ]

    for case_name, body, query in fuzz_cases:
        resp = client.post(
            f"/api/read-watermark{query}",
            data=body,
            content_type="application/json",
            headers=_test_auth_headers(),
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
    
