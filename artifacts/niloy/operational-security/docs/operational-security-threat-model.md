# Operational Security Threat Model — Tatou

## 1. Scope and purpose

Tatou is a web platform for PDF watermarking. The project README states that it is intended for pedagogical use, contains security vulnerabilities, and should not be deployed on an open network.

This threat model focuses on the Group 22 deployment and the operational-security changes made for Phase II. Its purpose is to identify assets, plausible attack scenarios, observation points, and response measures. It does not claim that every identified threat has been exploited or that the deployment is secure against all attacks.

## 2. System and trust boundaries

The deployment includes:
- A web/API server implemented in Python and Flask.
- Gunicorn serving the application on port 5000.
- A MariaDB database container.
- Docker Compose networking between the application and database.
- Environment-provided configuration and secrets.
- A host-mounted GPG home directory used by the application.
- Application, startup, error, and HTTP access logs.

The HTTP server port is published on the host. The database is configured as a separate Compose service. The host, containers, application, database, mounted GPG material, and incoming HTTP requests form relevant trust boundaries.

The application is not intended for unrestricted public exposure. Network reachability should therefore be restricted to the intended testing environment.

## 3. Assets to protect

| Asset | Security objective | Potential impact if compromised |
|---|---|---|
| Watermarked and uploaded PDF documents | Confidentiality and integrity | Disclosure, unauthorized modification, or deletion |
| Authentication tokens and signing/authentication material | Confidentiality and integrity | Unauthorized API access or misuse of protected operations |
| Environment variables and application secrets | Confidentiality | Impersonation, unauthorized access, or other compromise |
| Database records and credentials | Confidentiality, integrity, and availability | Data exposure, tampering, or service disruption |
| GPG key material | Confidentiality and integrity | Misuse of cryptographic operations |
| Application and security logs | Integrity, availability, and confidentiality | Loss of evidence, misleading investigations, or disclosure of sensitive data |
| Server and database availability | Availability | Interruption of watermarking and API operations |

## 4. Threat actors and assumptions

Potential threat actors include:
- An unauthenticated remote or local requester probing API endpoints.
- A user with an invalid, expired, or otherwise unacceptable authentication token.
- A malicious or compromised authenticated user attempting unauthorized document operations.
- A process or actor that obtains access to the host, container, mounted files, or deployment configuration.

These are threat scenarios, not claims that the corresponding actors have compromised the deployment.

The assessment assumes that the application may receive malformed or hostile requests. It does not assume that authentication alone prevents every application-level attack.

## 5. Threat scenarios and mitigations

| ID | Threat scenario | Existing or planned observation point | Mitigation or response |
|---|---|---|---|
| T1 | Repeated unauthenticated or invalid-token requests against protected endpoints | Authentication-failure security events and HTTP access logs | Investigate repeated failures; restrict the source or network access when justified and permitted |
| T2 | Expired tokens are used to access protected endpoints | Authentication-failure event with reason `expired_token` | Reject the request, retain a useful security event, and investigate suspicious repetition |
| T3 | Sensitive configuration or secrets are disclosed through logs | Review startup, application, and container logs | Do not log secret values; redact sensitive data and restrict access to logs |
| T4 | Malicious document requests or uploads exploit document-processing behavior | HTTP access logs and relevant application error/security logs | Preserve evidence, inspect the request and error context, restrict access if necessary, and investigate the affected documents |
| T5 | Unauthorized or destructive document operations affect stored documents | Relevant application events, error logs, and document/database state | Preserve available evidence, assess affected data, and restore from a verified backup where appropriate |
| T6 | Compromise of a privileged server container increases impact | Container configuration and Docker/runtime inspection | Evaluate least privilege, filesystem permissions, capabilities, and recovery options before changing deployment settings |
| T7 | Attack activity overwhelms the service or makes it unavailable | HTTP access logs, container status, health endpoint, and error logs | Restrict incoming traffic, preserve logs, restore service from a known-good state, and verify health |

The observation and response measures in this table are not all implemented or tested. Their completion status must be documented separately.

## 6. Verified findings and current controls

The following observations were verified during the Phase II work:

1. The server is deployed using Docker Compose and serves HTTP on port 5000.
2. The `/healthz` endpoint returned HTTP 200 and reported that the database was connected after the logging changes were deployed.
3. A request to `/api/list-documents` with a deliberately invalid test token returned HTTP 401.
4. The application recorded an authentication-failure event with reason `invalid_token`, the endpoint, method, and remote address.
5. The corresponding Gunicorn access log recorded the request and HTTP 401 response.
6. The authentication-failure event did not contain the deliberately invalid token value.
7. Gunicorn access logging was enabled by configuring its access and error logs to use standard output.
8. The startup message was changed so it no longer prints the configured flag value.
9. The repository test suite previously reported 26 passed and 7 skipped. The skipped tests and reasons must be retained when reporting this result; this is not equivalent to every test passing.
10. The deployment was inspected and the server process was observed running as root inside the container. This is a hardening concern that requires further assessment; no privilege reduction has yet been claimed.

## 7. Evidence limitations

- The invalid-token request demonstrates a rejected authentication attempt, not a successful compromise.
- A health-check request demonstrates service availability, not the absence of attacks.
- Logging provides evidence for investigation but does not itself block repeated attempts, recover deleted documents, or restore a compromised service.
- The presence of an event in a log does not independently establish the identity or intent of the requester.
- Earlier startup logs included a sensitive configured value. The startup message has been corrected, but changing the message does not erase historical log entries.
- No claim is made here that every attack scenario in Section 5 has been tested.

## 8. Incident response outline

For a suspected security incident:

1. **Detect:** identify relevant authentication events, HTTP status codes, application errors, and service-health changes.
2. **Preserve:** save relevant timestamped logs and record the test or incident context. Redact credentials and secret values.
3. **Assess:** determine which endpoint and assets may be affected, and distinguish observed evidence from hypotheses.
4. **Contain:** when justified and authorized, restrict access to the affected service or source. Avoid destructive changes before preserving evidence.
5. **Recover:** use a known-good application/configuration state and verified backups where necessary. Rotate affected credentials only when authorized and operationally safe.
6. **Verify:** check application health, database connectivity, authentication behavior, and relevant logs after recovery.
7. **Report:** document the timeline, evidence, impact, response, limitations, and follow-up actions.

This outline is a proposed response procedure. Individual recovery actions must be tested or explicitly described as recommendations rather than completed capabilities.

## 9. Follow-up work

- Preserve a redacted evidence collection containing the invalid-token event and access-log entry.
- Test and document the missing-authorization and expired-token cases where safe.
- Review log retention and access controls.
- Assess container privilege and filesystem hardening without disrupting the deployment.
- Define and test a recovery scenario appropriate to the available environment.
- Complete the Phase II report with actual test results, timestamps, and limitations.
