# Security Requirements Register

This register links documented security requirements to their threat/objective
source, implementation, and executable verification.

## REQ-01 — Link confidentiality

| Field | Evidence |
|---|---|
| Requirement | Secret links to watermarked documents should not be guessable by unauthorized parties. |
| Threat | `T.LINK_GUESS` |
| Security objective | `O.LINK_CONFIDENTIALITY` |
| Specification | `Platform_specifications.md` |
| Implementation | `server/src/server.py` — RMAP link generation and `GET /api/get-version/<link>` exact-link retrieval |
| Verification | `test_nonexistent_version_link_is_rejected`; `test_modified_version_link_is_rejected`; `test_handshake_with_official_client_returns_watermarked_pdf`; `test_replayed_msg2_is_rejected`; `test_unknown_identity_is_rejected` |
| Verification matrix | `SECURITY_TEST_MATRIX.md` |

## REQ-02 — Watermark secret retrieval

| Field | Evidence |
|---|---|
| Requirement | Watermarks MUST allow secret retrieval by the owner of the document allowing the identification of the document's version. |
| Threat/objective source | Platform specification requirement for watermark-based secret retrieval |
| Specification | `Platform_specifications.md` |
| Implementation | `server/src/watermarking_method.py`, `server/src/watermarking_utils.py`, `server/src/metadata_hmac.py`, `server/src/tiago_invisible_text.py` |
| Verification | `test_roundtrip`; `test_wrong_key_rejected`; `test_missing_watermark`; `test_secret_is_not_stored_in_clear`; `test_unwatermarked_pdf_has_no_secret`; `test_rewatermarking_keeps_each_key_readable` |
| Verification matrix | `SECURITY_TEST_MATRIX.md` and executable tests in `server/test/` |

## REQ-03 — Document access control

| Field | Evidence |
|---|---|
| Requirement | Documents without watermarks must be accessible only to their owner and the platform. Documents should not be modifiable by third parties. |
| Specification | `Platform_specifications.md` |
| Implementation | Ownership and access-control logic in `server/src/server.py` |
| Related security history | Git history contains security fixes for watermark ownership and access-control behaviour. |
| Verification status | Partially traced in the current repository; additional dedicated requirement-specific tests would strengthen this requirement. |

## Verification process

The register is intended to keep security requirements connected to
implementation and verification.

The verification process is supported by:

- `SECURITY_TEST_MATRIX.md`
- executable tests under `server/test/`
- pytest coverage reporting
- `.github/workflows/security-tests.yml`

## Evidence limitation

The strongest complete traceability currently exists for REQ-01 and REQ-02.
REQ-03 is documented and implemented but has less complete dedicated test
traceability.

This register therefore records the evidence that exists rather than claiming
that every platform security requirement is fully traced.
