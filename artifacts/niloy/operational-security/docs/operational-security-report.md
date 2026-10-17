# Phase II Specialization D — Operational Security

## 1. Objective

The objective was to build operational-security capabilities around the Group 22 Tatou deployment by defining a threat model, adding observation points, monitoring security-relevant activity, and documenting an attempted attack and the response. Tatou is a pedagogical PDF-watermarking platform whose README warns against deployment on an open network.

## 2. Threat modelling

The threat model is documented in `docs/operational-security-threat-model.md`. It identifies the documents, authentication material, environment secrets, database, GPG material, logs, and service availability as assets requiring protection.

The principal scenarios considered were invalid authentication attempts, disclosure of secrets through logs, hostile document requests, unauthorized document operations, container privilege, and service disruption. These are threat scenarios, not claims that each attack occurred.

## 3. Implemented observation points

### 3.1 Authentication-failure events

The server's authentication guard was updated to log security-relevant failures, including missing or invalid authorization headers, expired tokens, and invalid tokens. The events include a reason, endpoint, HTTP method, and remote address. Token values are not intentionally included in these event messages.

The tests in `server/test/test_api.py` cover missing authorization and invalid-token logging. The expired-token branch is implemented but has not been separately demonstrated in the live deployment during this validation.

### 3.2 HTTP access logging

Gunicorn was configured in `server/entrypoint.sh` to send access and error logs to standard output. This makes HTTP request records available through Docker Compose logs. The observed access records included the requested path, HTTP method, status code, and user-agent information.

### 3.3 Safer startup logging

The startup message in `server/entrypoint.sh` was changed so it no longer prints the configured flag value. This addresses the observed risk of disclosing sensitive configuration in startup logs. The change does not remove historical log entries that may contain the previous message.

## 4. Validation and observed results

The following checks were performed on 14 October 2026:

1. **Shell syntax:** `bash -n server/entrypoint.sh` completed successfully.
2. **Deployment:** The server image was rebuilt and only the server service was recreated using `docker compose up -d --no-deps server`.
3. **Health check:** `GET /healthz` returned HTTP 200, with `db_connected: true`.
4. **Controlled invalid-token request:** A request to `GET /api/list-documents` using a deliberately invalid test token returned HTTP 401.
5. **Security-event observation:** The application log recorded `security_event=authentication_failed` with `reason=invalid_token`, along with endpoint, method, and remote address.
6. **Access-log observation:** Gunicorn recorded the invalid-token request and its HTTP 401 response.
7. **Secret handling:** The reviewed authentication-failure event did not contain the supplied test token. The revised startup message no longer intentionally prints the configured flag value.
8. **Earlier test-suite result:** The server test suite reported 26 passed and 7 skipped. The skipped tests and their reasons must be considered; this result does not establish that every test path passed.

These results demonstrate that the tested invalid authentication attempt was rejected and recorded. They do not demonstrate a successful compromise or prove that all possible attacks are detected.

## 5. Incident analysis and response

The event used for the incident-analysis exercise was a controlled invalid-token attempt against `/api/list-documents` at 18:32:07 UTC on 14 October 2026.

The server returned HTTP 401 and recorded an authentication-failure event with reason `invalid_token`. The access log independently recorded the request and its response status. The supplied test token was not included in the reviewed security-event message.

The response was to preserve the observed event details, verify that the log exposed the failure reason without recording the token, and document the result. The request was rejected, so the evidence supports an unsuccessful authentication attempt rather than a successful attack. The remote address in the log identifies the observed network peer for that request; it does not establish the identity or intent of a person.

The event summary is stored in `docs/evidence/operational-security-events.md`. It is a redacted summary of observed terminal output and container logs, not an unmodified raw-log export.

## 6. Recovery procedure

The recovery runbook is documented in `docs/operational-security-recovery.md`. It prioritizes preserving logs, inspecting service status, validating changes, rebuilding the server image, recreating only the server container, and verifying application health and database connectivity.

The deployment exercise demonstrated that the server could be rebuilt and recreated without intentionally restarting the database, after which the health check succeeded. The Compose configuration defines persistent volumes for uploaded documents and database data; the runbook warns against deleting these volumes during routine recovery.

This exercise validates application-service redeployment in the tested scenario. It does not validate restoration from backups, recovery of deleted documents, database repair, or recovery from a confirmed compromise. Those capabilities require a separate, verified backup-and-restore procedure.

## 7. Limitations and follow-up work

- Authentication-failure logging was demonstrated for an invalid token; the expired-token branch has not been separately validated in the live deployment.
- The controlled test was not a successful compromise and should not be described as one.
- Logging supports detection and investigation but does not itself prevent repeated requests or restore data.
- The previous startup message may remain in historical container logs; changing the message does not erase those records.
- The server container was observed running as root. This remains a hardening concern requiring further assessment.
- Backup restoration and data recovery have not been tested.
- The evidence record is a summary. For stronger forensic handling, preserve original timestamped logs securely and record any redactions.
- The unrelated change to `server/pyproject.toml` is not part of this Operational Security specialization and should be reviewed separately.

## 8. Conclusion

The work added authentication-failure logging, enabled HTTP access logging, and corrected a startup message that previously exposed a configured value. The deployed service was validated with a successful health check and a controlled invalid-token test. The resulting evidence demonstrates detection and recording of an unsuccessful authentication attempt.

The threat model, recovery runbook, and evidence record document the reasoning and observed results. Full data recovery and response to a successful compromise remain unverified and are explicitly identified as limitations rather than claimed capabilities.
