# Phase 1 Status — Group 22 Tatou

## 1. Overview

This document records the status of Group 22's Phase 1 work on the Tatou project, including RMAP implementation, security improvements, testing, and deployment.

## 2. Git Branch and Version Control

- Phase 1 branch: `niloy-phase1`
- Current Phase 1 commit: `620a8f0` — Complete Phase 1 RMAP and security fixes
- Remote status: synchronized with `origin/niloy-phase1`
- SAMM/security-testing work is maintained separately on `niloy-samm-security-testing`.
- Changes on `main` are outside the scope of this Phase 1 documentation task.

## 3. RMAP Implementation

The project includes implementation work for the RMAP initiation and link-retrieval endpoints.

The initiation endpoint processes an encrypted request, validates the requesting identity against available public keys, and establishes a session using client and server nonces.

The link-retrieval endpoint processes the server nonce and returns an encrypted result containing a link derived from the two nonces.

**Known limitations requiring verification or further work:**

- Confirm compatibility with the prescribed RMAP library and protocol encoding.
- Verify that the assigned confidential PDF is used.
- Ensure each authorized recipient receives a distinct, individually watermarked PDF.
- Ensure the watermark and corresponding database record are created before returning the link.
- Verify identity formatting and protocol interoperability with the official client.

These limitations must not be treated as completed requirements until they have been tested.

## 4. Security Improvements

Security work includes:

- Disabling dynamic plugin loading to prevent unsafe deserialization.
- Removing the `dill` dependency used by the previous plugin-loading implementation.
- Sanitizing uploaded document filenames.
- Keeping the server's private key outside the Git repository.
- Recording the security incident and remediation in `EVENT_JOURNAL.md`.

## 5. Testing and Deployment

Previous verification included:

- Successful RMAP initiation and link-retrieval testing.
- A returned link with the expected 32-character hexadecimal format.
- Successful retrieval of a PDF through the generated link.
- Verification that the server health endpoint returned HTTP 200 with database connectivity.
- Watermarking tests for the `metadata-hmac` method.

Earlier test results included 13 passed and 3 skipped in one test run, and 6 passed in the dedicated metadata-HMAC tests. These are historical results, not a claim that all current tests pass.

## 6. Individual Watermarking Method

The `metadata-hmac` method was implemented in `server/src/metadata_hmac.py` and registered in `server/src/watermarking_utils.py`.

The method stores encoded watermark metadata and an HMAC-SHA256 value in PDF metadata. Tests covered round-trip behaviour, incorrect keys, missing watermarks, deterministic output, applicability, and empty secrets.

## 7. Outstanding Verification

Before considering Phase 1 fully complete, verify:

1. RMAP protocol compatibility and payload encoding.
2. Correct use of the assigned confidential PDF.
3. Recipient-specific watermark generation.
4. Creation and persistence of the matching database record before link delivery.
5. Authorization and identity validation using the official course keys.
6. Current test results and deployed behaviour.
7. Required incident follow-up and flag handling, where applicable.

## 8. Scope and Change Control

This document is a status record, not proof that every requirement is complete. Any outstanding item should be marked complete only after evidence has been collected.

The Phase 1 documentation change should remain on `niloy-phase1`. Do not merge into `main` or push additional changes without explicit approval.
