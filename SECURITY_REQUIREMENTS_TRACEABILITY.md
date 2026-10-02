# Security Requirements Traceability

## Link Confidentiality

| Element | Evidence |
|---|---|
| Threat | T.LINK_GUESS: unauthorized party obtains a valid document link by guessing, modifying, predicting, or reconstructing it. |
| Objective | O.LINK_CONFIDENTIALITY: retrieval links should not be derivable or guessable by unauthorized parties. |
| Requirement | Platform_specifications.md requires secret links that should not be guessable by anyone other than the owner/platform. |
| Implementation | server/src/server.py generates/stores links and retrieves versions using an exact `WHERE link = :link` lookup. |
| Negative test | `test_nonexistent_version_link_is_rejected` expects HTTP 404. |
| Negative test | `test_modified_version_link_is_rejected` expects HTTP 404. |
| Positive test | `test_handshake_with_official_client_returns_watermarked_pdf` verifies valid-link retrieval. |
| RMAP replay test | `test_replayed_msg2_is_rejected` expects HTTP 400. |
| RMAP identity test | `test_unknown_identity_is_rejected` expects HTTP 400. |

## Traceability Chain

T.LINK_GUESS -> O.LINK_CONFIDENTIALITY -> Platform_specifications.md -> server/src/server.py -> server/test/ security tests

## Verification Process

Security verification is supported by SECURITY_TEST_MATRIX.md, pytest coverage reporting, and .github/workflows/security-tests.yml.

## Evidence Limitation

The complete threat-to-requirement-to-implementation-to-test chain is demonstrated most clearly for link confidentiality. This document does not claim that every platform requirement has complete traceability.
