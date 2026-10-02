# Security Test Matrix — Link Confidentiality

## Threat

**T.LINK_GUESS:** An unauthorized party obtains a valid Tatou document link by guessing, predicting, modifying, or reconstructing the link and uses it to retrieve the document.

## Security objective

**O.LINK_CONFIDENTIALITY:** A document cannot be retrieved through the public retrieval endpoint without the exact valid link issued for that document.

## Security test coverage

| Security property | Test | Expected result | Status |
|---|---|---|---|
| Nonexistent link cannot retrieve a document | `test_nonexistent_version_link_is_rejected` | HTTP 404 | Passing |
| Modified existing link cannot retrieve document | `test_modified_version_link_is_rejected` | HTTP 404 | Passing |
| Valid RMAP link retrieves watermarked PDF | `test_handshake_with_official_client_returns_watermarked_pdf` | HTTP 200 + expected watermark | Existing RMAP test; skipped in the current local test environment |
| Repeated retrievals use distinct links/copies | `test_each_retrieval_gets_a_distinct_watermarked_copy` | Distinct links and PDF copies | Existing RMAP test; skipped in the current local test environment |
| Replayed RMAP message is rejected | `test_replayed_msg2_is_rejected` | HTTP 400 | Existing RMAP test; skipped in the current local test environment |
| Unknown RMAP identity is rejected | `test_unknown_identity_is_rejected` | HTTP 400 | Existing RMAP test; skipped in the current local test environment |

## Coverage tracking

`pytest-cov` is configured in `server/pyproject.toml`:

`--cov=server --cov-report=term-missing`

The focused retrieval test run currently reports:

- `test_get_version.py`: 100% statement coverage
- `server.py`: 22% statement coverage
- Overall measured coverage: 48% in the latest full-suite run.

Coverage is used as a measurement of tested code paths, not as proof that the security objective is fully verified.

## Current limitation

The RMAP test module uses `pytest.importorskip("rmap")`. In the current Python 3.13 environment, the RMAP dependency cannot be imported because the installed dependency currently cannot import under Python 3.13 due to the removed standard-library `imghdr` module.

Therefore the end-to-end RMAP tests are skipped rather than passing.

The standalone retrieval tests remain executable and directly verify that unknown and modified links are rejected by the public retrieval endpoint.

## Security requirement traceability

| Element | Evidence |
|---|---|
| Threat | `T.LINK_GUESS` |
| Objective | `O.LINK_CONFIDENTIALITY` |
| Requirement | `Platform_specifications.md`: secret link should not be guessable |
| Implementation | `server/src/server.py`: exact `WHERE link = :link` retrieval |
| Positive test | `test_handshake_with_official_client_returns_watermarked_pdf` |
| Negative tests | `test_nonexistent_version_link_is_rejected`; `test_modified_version_link_is_rejected` |
| Protocol tests | `test_replayed_msg2_is_rejected`; `test_unknown_identity_is_rejected` |

Traceability:

`T.LINK_GUESS -> O.LINK_CONFIDENTIALITY -> Platform_specifications.md -> server/src/server.py -> server/test/`

The latest full-suite run reports 26 passed, 7 skipped, and 48% measured
coverage. RMAP tests are skipped in the current Python 3.13 environment
because the dependency cannot import the removed `imghdr` module.
