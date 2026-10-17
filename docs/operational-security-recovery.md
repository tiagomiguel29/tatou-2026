# Operational Security Recovery Runbook — Tatou

## Purpose

This runbook describes a cautious response to suspected application-service failure or a security event in the Group 22 Tatou deployment. It prioritizes evidence preservation and protection of persistent data.

## Persistent data and dependencies

According to `docker-compose.yml`:

- `user-files` stores application files at `/app/storage`.
- `db-data` stores MariaDB data at `/var/lib/mysql`.
- `${HOME}/rmap-gnupg` is mounted into the server container at `/app/rmap-gnupg`.

These locations may contain important data or cryptographic material. Do not remove these volumes or delete the mounted directory during routine service recovery.

## Recovery procedure: application service

1. **Assess and preserve evidence.** Record the incident time, symptoms, relevant application and access logs, and the current container status. Redact credentials, tokens, flags, and other secrets before sharing evidence.
2. **Check service status.** Use `docker compose ps` and inspect recent server logs. Do not assume that a failed request proves the service is down.
3. **Validate the source.** Inspect the intended code changes and run relevant tests before rebuilding. Do not deploy unreviewed changes during an incident.
4. **Rebuild the server image.** From the repository root, run `docker compose build server`.
5. **Recreate only the server service.** Run `docker compose up -d --no-deps server`. Do not use `docker compose down -v` or remove persistent volumes.
6. **Verify recovery.** Check `docker compose ps`, request `/healthz`, and confirm HTTP 200 with `db_connected` set to `true`. Review recent logs for startup errors and expected access-log entries.
7. **Record the outcome.** Document the time, commands, observed status, remaining risks, and whether the service returned to normal operation.

These steps recover the application service only when the database and required persistent data remain usable. Recreating the server is not proof that a security compromise has been contained.

## Response to suspected unauthorized access

1. Preserve relevant timestamped logs before making changes.
2. Identify affected endpoints, time range, status codes, and security-event reasons.
3. Determine whether the evidence indicates rejected requests, successful access, or an unresolved possibility.
4. If justified and authorized, restrict network access or stop the affected service after considering operational impact and preserving evidence.
5. Investigate whether documents, application configuration, authentication material, or database records were affected.
6. If a secret is confirmed exposed, follow the course team's authorized secret-rotation procedure. Do not print the secret in logs or reports.
7. Restore a known-good application/configuration state and verify service health before returning to normal operation.

## Data recovery limitations

The Compose file defines persistent volumes but does not, by itself, establish that usable backups exist. This runbook does not claim that deleted files, corrupted database records, or compromised cryptographic material can currently be restored.

Before claiming full data recovery, establish and test a backup and restoration procedure for the document volume, database, and any required cryptographic/configuration material. Protect backups as sensitive data and verify their integrity before restoration.

## Validation record

On 14 October 2026, the server image was rebuilt and the server container was recreated without restarting the database. The `/healthz` endpoint then returned HTTP 200 and `db_connected: true`. A deliberately invalid test token was rejected with HTTP 401 and recorded as an authentication-failure event.

This validates application-service redeployment and authentication-failure observation in the tested scenario. It does not validate backup restoration or recovery from a successful compromise.
