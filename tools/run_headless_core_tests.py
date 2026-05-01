#!/usr/bin/env python
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


def read_manifest(manifest_path: Path) -> list[str]:
    tests: list[str] = []
    for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            tests.append(line)
    return tests


def main() -> int:
    repo_root = Path(
        os.environ.get("GITHUB_WORKSPACE", Path(__file__).resolve().parents[1])
    ).resolve()
    manifest_path = repo_root / "tests" / "headless_core_tests.txt"
    relative_tests = read_manifest(manifest_path)
    absolute_tests = [(repo_root / test_path).resolve() for test_path in relative_tests]

    missing = [str(test_path) for test_path in absolute_tests if not test_path.exists()]
    if missing:
        print("Missing test files listed in tests/headless_core_tests.txt:")
        for test_path in missing:
            print(f"  {test_path}")
        return 2

    run_dir = Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())).resolve()
    os.chdir(run_dir)
    print(
        f"Running {len(absolute_tests)} headless core pytest files from {run_dir}",
        flush=True,
    )

    return subprocess.call(
        [sys.executable, "-m", "pytest", "-q", "-rs", *map(str, absolute_tests)]
    )


if __name__ == "__main__":
    raise SystemExit(main())
