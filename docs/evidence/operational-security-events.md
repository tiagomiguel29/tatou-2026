# Operational Security Evidence Record — Tatou

**Deployment:** SOFTSEC Group 22 Tatou
**Date:** 14 October 2026
**Purpose:** Record observed events from controlled validation of the operational-security changes.

## Event 1 — Application health check

- **Observed time (UTC):** 2026-10-14 18:30:54
- **Request:** `GET /healthz`
- **HTTP status:** `200 OK`
- **Observed result:** JSON response reported `db_connected: true`.
- **Access-log evidence:** Gunicorn recorded the request and status `200`.
- **Interpretation:** The application was responding and reported a working database connection after the server redeployment.
- **Limitations:** This does not establish that all application functions are secure or that no attack occurred.

## Event 2 — Controlled invalid-token test

- **Observed time (UTC):** 2026-10-14 18:32:07
- **Request:** `GET /api/list-documents`
- **Test input:** Deliberately invalid, non-secret test token. The token itself is intentionally not reproduced.
- **HTTP status:** `401 Unauthorized`
- **Security event:** `security_event=authentication_failed`
- **Reason:** `invalid_token`
- **Additional logged fields:** Endpoint, HTTP method, and remote address.
- **Access-log evidence:** Gunicorn recorded the request and status `401`.
- **Interpretation:** The tested request was rejected, and the application generated a security event. The security event did not contain the supplied token.
- **Limitations:** This was a controlled test of an unsuccessful authentication attempt, not evidence of a successful compromise or of an attack by an external actor.

## Event 3 — Startup logging validation

- **Observed time (UTC):** 2026-10-14 18:30:26
- **Change:** The startup message was changed to report that a configured value was used without printing the value itself.
- **Observed result:** The displayed startup message used the generic wording `Replacing placeholder in flag with [REDACTED]` in the reviewed evidence output. The deployed source now uses a generic configured-value message.
- **Interpretation:** The revised startup message avoids intentionally printing the configured flag value.
- **Limitations:** Historical container logs may still contain the previous startup message. This change does not erase historical logs.

## Deployment validation

The server image was rebuilt and the server container was recreated using `docker compose up -d --no-deps server`, without intentionally restarting the database. The health check subsequently returned HTTP 200 and `db_connected: true`.

## Evidence handling

This record summarizes terminal output and container logs observed during testing. It is not an unmodified raw-log export. The original relevant log entries were reviewed in the terminal; this document preserves their key fields while avoiding reproduction of credentials or secret values.

For a formal incident investigation, preserve original logs securely with timestamps and access controls. Record any redaction and avoid altering the original evidence.

## Overall assessment

The collected evidence demonstrates service-health validation, HTTP access logging, and detection/logging of a controlled invalid-token request. It does not demonstrate a successful attack, full incident containment, backup restoration, or recovery of compromised data.
