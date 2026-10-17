# Upload validation test mapping

Tests are in `server/test/test_upload_validation.py` and the frozen final
mutation-testing snapshot.

| Requirement | Test |
|---|---|
| Valid PDF and correct metadata | `test_accepts_structurally_valid_pdf` |
| Invalid upload leaves no file or row | `test_rejects_non_pdf_and_removes_file` |
| Allowed whitespace and boundary handling | `test_accepts_pdf_eof_with_allowed_whitespace` |
| Parser repairs cannot bypass validation | `test_rejects_parser_tolerated_malformed_pdf` |
| Missing file fails closed | `test_validator_rejects_missing_file` |
| Database failure removes the saved file | `test_database_failure_removes_valid_upload` |
| Long allowed whitespace is accepted | `test_accepts_long_trailing_whitespace` |
| Other trailing bytes are rejected | `test_rejects_disallowed_trailing_bytes` |
