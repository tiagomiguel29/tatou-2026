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



### Additional testing and mutation reproduction

Use Python 3.12 for the virtual environment above. RMAP tests also require GnuPG.
Run the following commands from the repository root, using `server/.venv`.

API tests:

```sh
PYTHONPATH=server/src server/.venv/bin/python -m pytest server/test/test_api.py server/test/test_upload_validation.py server/test/test_rmap.py
```

Coverage for all unit and API tests:

```sh
server/.venv/bin/python -m pip install pytest-cov
PYTHONPATH=server/src server/.venv/bin/python -m pytest server/test --cov=server/src --cov-report=term-missing
```

See the [upload test mapping](artifacts/common/upload-validation-test-mapping.md)
and [mutation-testing report](artifacts/tiago/mutation-testing/REPORT.md).
Reproduce the mutation experiment on macOS, Linux or WSL:

```sh
server/.venv/bin/python -m pip install -r artifacts/tiago/mutation-testing/requirements-lock.txt
server/.venv/bin/python artifacts/tiago/mutation-testing/reproduce.py --output /tmp/tatou-mutation-run
```

Use a new output directory for each run.
