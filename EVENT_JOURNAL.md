# SOFTSEC Group 22 — Event Journal

## 2026-10-17 — Server update and restart

- Built a combined release from local main and the PDF-validator correction,
  preserving the server's existing authentication logging, startup changes,
  RMAP development dependency, course keys and operational-security documents.
- Preserved the server's `niloy-phase2` branch and created no Git commits.
- Backed up the repository, working files, database, uploaded files and previous
  image under `/home/softsec/backups/deployment-20261017T150932Z` before updating.
- Combined-release tests: 56 passed and six applicability skips.
- Rebuilt and restarted only the application container. Database health passed;
  eight live API checks covered authentication, account creation/login, upload
  validation, ownership, watermarking, downloads and independent random links.
  Temporary test accounts and files were removed afterward.
- Verified the running source hash, RMAP source document/key availability and
  presence of the configured flag without recording secret values.
- API health passed through an SSH tunnel. Direct port 5000 access from this
  computer over the VPN timed out; the server listener and firewall allow it.
- With explicit user approval, rotated 20 legacy predictable links at 15:23 UTC.
  Verification found zero remaining; old URLs are invalidated and RMAP links
  retain their separate format. The migration ran transactionally.
- Release fingerprints and the preserved server-only source changes are recorded
  in `artifacts/common/deployments/2026-10-17/`.

## 2026-10-17 — Focused mutation testing of PDF uploads

- Restored four upload regression cases from the existing handoff; baseline mutmut
  run killed 30 of 35 selected PDF-validator mutants.
- Added boundary, parser-repair, metadata and cleanup assertions. On unchanged code,
  these killed 31 of the same 35 mutants.
- Found and reproduced a false-rejection defect: valid PDFs with long permitted
  trailing whitespace returned 400. Three tests failed before the fix.
- Changed validation to scan backward in bounded chunks and updated the API contract.
- Final suite has 18 upload cases; 46 of 55 corrected-code mutants killed and nine
  survivors retained with analysis. Full local suite: 47 passed, six applicability skips.
- Recorded raw evidence and a reproducible specialization-B report under
  `artifacts/tiago/mutation-testing/`. No VM deployment or offensive action.

## 2026-09-20 — Flag 2 capture incident

### Discovery
Professor Nicolas reported that Group 22's flag_2 had been captured by another group and that the flag file in the server container had not been initialized correctly.

### Investigation
- The expected flag file was found at `/app/flag` inside the server container.
- The flag was initialized from the configured `FLAG_2` environment value during container startup.
- The flag value itself was not recorded in this journal.
- Persistent application storage contained multiple files under `/app/storage/files/plugins/`.
- Several plugin files were inspected as raw bytes without executing or deserializing them.
- A malicious plugin payload was identified. It was disguised with a PDF header but contained a serialized Python object capable of invoking a system command to read `/app/flag` and send its contents to an external address.
- The application contained `/api/load-plugin`, which deserialized plugin files using `dill.load()`.
- This created a remote-code-execution vulnerability if an attacker could place a malicious serialized object in the plugin directory and cause the endpoint to load it.

### Root cause
The confirmed critical vulnerability was unsafe deserialization of untrusted plugin files using `dill`.

A separate path-handling weakness was also identified in `/api/upload-document`: the client-provided filename was originally used directly when constructing the storage path. This could allow path traversal through a crafted filename.

The exact mechanism by which the malicious plugin files were originally placed in the persistent `plugins` directory has not been conclusively established.

### Remediation
1. Uploaded filenames are now sanitized with Werkzeug `secure_filename()`.
2. Uploads whose sanitized filename is empty are rejected.
3. The `dill` dependency was removed from `server/pyproject.toml`.
4. The `/api/load-plugin` endpoint was disabled and now returns HTTP 410 after authentication.
5. The server image was rebuilt and the server container recreated.
6. The flag was reinitialized successfully during the rebuild.
7. The server health endpoint returned HTTP 200 with a successful database connection.
8. The deployed container was verified to have no `dill` installation and no `_pickle.load` usage under `/app/src`.
9. The persistent plugin files remain available as incident evidence; they were not executed during the investigation.

### Verification
- `python3 -m py_compile server/src/server.py` completed successfully.
- Docker image rebuilt successfully.
- Server container restarted successfully.
- `/healthz` returned HTTP 200.
- `/app/flag` exists and no longer contains the initialization placeholder.
- `dill` is not installed in the deployed server container.
- No `_pickle.load` call remains in the deployed application source.

### Security handling
Malicious serialized files were inspected only as raw bytes. They were not deserialized or executed.
Secrets, flag values, credentials, and private keys were not recorded in this journal.

