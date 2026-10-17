# tatou
A web platform for pdf watermarking. This project is intended for pedagogical use, and contain security vulnerabilities. Do not deploy on an open network.

## Instructions

The following instructions are meant for a bash terminal on a Linux machine. If you are using something else, you will need to adapt them.

To clone the repo, you can simply run:

```bash
git clone https://github.com/nharrand/tatou-2026.git
```

Note that you should probably fork the repo and clone your own repo.


### Run python unit tests

```bash
cd tatou/server

# Create a python virtual environement
python3 -m venv .venv

# Activate your virtual environement
. .venv/bin/activate

# Install the necessary dependencies
python -m pip install -e ".[dev]"

# Run the unit tests
python -m pytest
```

### Deploy

From the root of the directory:

```bash
# Create a file to set environement variables like passwords.
cp sample.env .env

# Edit .env and pick the passwords you want

# Rebuild the docker image and deploy the containers
docker compose up --build -d

# Monitor logs in realtime 
docker compose logs -f

# Test if the API is up
http -v :5000/healthz

# Open your browser at 127.0.0.1:5000 to check if the website is up.
```

### Phase II mutation-testing evidence

The short individual report is in
[`artifacts/tiago/mutation-testing/REPORT.md`](artifacts/tiago/mutation-testing/REPORT.md).
The folder also contains saved code/test snapshots, raw results, mutation diffs,
coverage, the validator fix patch and reproduction verification.

#### Reproduce the experiment

From the full repository root, with Python 3.12 and Git installed:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r artifacts/tiago/mutation-testing/requirements-lock.txt
.venv/bin/python artifacts/tiago/mutation-testing/reproduce.py --output /tmp/tatou-option-b-new-run
```

Use a new output directory. The script runs all three stages using frozen snapshots
in temporary workspaces. It requires macOS/Linux or WSL and does not modify the
project or contact the course VM.

#### Run API tests and coverage

From the repository root:

```sh
PYTHONPATH=server/src .venv/bin/python -m pytest server/test/test_upload_validation.py -v
PYTHONPATH=server/src .venv/bin/python -m pytest server/test -v --cov=server/src --cov-report=term-missing
```

The complete suite needs GnuPG and its local agent for temporary RMAP keys.
Production keys are not required. The isolated upload campaign does not need GnuPG.

#### Specification-to-test mapping

The following tests are in `server/test/test_upload_validation.py` and the frozen
final test snapshot.

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

`summary.json` records mutation counts and source/test fingerprints. A separate
reproduction matched all three recorded stages; see `reproduction-verification.json`.
`MANIFEST.sha256` covers the current evidence folder; `ARCHIVED_BUNDLE_MANIFEST.sha256`
belongs to the unchanged historical ZIP.
