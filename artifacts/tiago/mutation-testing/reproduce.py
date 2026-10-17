from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TARGET = "server.x__is_valid_pdf__mutmut_"


def run(command, workspace, environment, log):
    with log.open("w") as output:
        result = subprocess.run(command, cwd=workspace, env=environment,
                                stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f"Command failed ({result.returncode}); see {log}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stage", choices=["all", "baseline", "strengthened", "final"],
                        default="all")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    stages = ["baseline", "strengthened", "final"] if args.stage == "all" else [args.stage]
    summary = {}
    with tempfile.TemporaryDirectory(prefix="tatou-mutation-") as directory:
        workspace = Path(directory)
        (workspace / "src").mkdir()
        (workspace / "test").mkdir()
        for source in (ROOT / "server/src").glob("*.py"):
            shutil.copy2(source, workspace / "src" / source.name)
        shutil.copy2(ROOT / "server/pyproject.toml", workspace / "pyproject.toml")
        shutil.copy2(ROOT / "server/test/conftest.py", workspace / "test/conftest.py")
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment.update(SECRET_KEY="mutation-reproduction-test-only",
                           STORAGE_DIR=str(workspace / "storage"))
        for stage in stages:
            source = HERE / ("baseline-server.py" if stage != "final" else "final-server.py")
            tests = HERE / f"{stage}_test_upload_validation.py"
            if (workspace / "src/server.py").read_bytes() != source.read_bytes():
                shutil.rmtree(workspace / "mutants", ignore_errors=True)
            shutil.copy2(source, workspace / "src/server.py")
            shutil.copy2(tests, workspace / "test/test_upload_validation.py")
            print(f"Running {stage} in an isolated workspace...", flush=True)
            run([sys.executable, "-m", "pytest", "test/test_upload_validation.py",
                 "-o", "pythonpath=src", "-v"], workspace, environment,
                output / f"{stage}-tests.log")
            run([sys.executable, "-m", "mutmut", "run", TARGET + "*", "--max-children", "2"],
                workspace, environment, output / f"{stage}-run.log")
            metadata = json.loads((workspace / "mutants/src/server.py.meta").read_text())
            results = {k: v for k, v in metadata["exit_code_by_key"].items() if k.startswith(TARGET)}
            if not results or any(v not in (0, 1) for v in results.values()):
                raise RuntimeError(f"Incomplete or abnormal mutation results: {results}")
            (output / f"{stage}-results.json").write_text(json.dumps(results, indent=2) + "\n")
            for mutant, status in results.items():
                if status == 0:
                    number = mutant.rsplit("_", 1)[1]
                    run([sys.executable, "-m", "mutmut", "show", mutant], workspace,
                        environment, output / f"{stage}-mutant-{number}.diff")
            summary[stage] = {
                "tested": len(results), "killed": sum(v == 1 for v in results.values()),
                "survived": sum(v == 0 for v in results.values()),
                "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "tests_sha256": hashlib.sha256(tests.read_bytes()).hexdigest(),
            }
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
