"""Run every claim in *.toml against the pinned toolchain.

Each claim writes the files of its probe (the ``[probes."<id>"]`` table of the same file) to a
temporary dir, runs a command there with the toolchain first on PATH, and checks exit code and
output patterns.

    uv sync --project claims/refactoring-python/toolchain
    python3 claims/refactoring-python/verify.py [--only ID ...] [-v]
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

SUITE = Path(__file__).resolve().parent
TOOLCHAIN_BIN = SUITE / "toolchain" / ".venv" / "bin"


def child_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE", "ANTHROPIC"))}
    env["PATH"] = f"{TOOLCHAIN_BIN}{os.pathsep}{env.get('PATH', '')}"
    env.pop("VIRTUAL_ENV", None)
    env["NO_COLOR"] = "1"
    return env


def run_claim(claim: dict, verbose: bool) -> list[str]:
    failures: list[str] = []
    with tempfile.TemporaryDirectory(prefix="claim-") as tmp:
        work = Path(tmp) / "probe"
        for rel, text in claim["files"].items():
            path = work / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        proc = subprocess.run(
            claim["cmd"],
            cwd=work,
            env=child_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
    output = proc.stdout + proc.stderr
    if "expect_exit" in claim and proc.returncode != claim["expect_exit"]:
        failures.append(f"exit {proc.returncode} != {claim['expect_exit']}")
    for pattern in claim.get("expect_output", []):
        if not re.search(pattern, output, re.MULTILINE):
            failures.append(f"missing /{pattern}/")
    for pattern in claim.get("expect_no_output", []):
        if re.search(pattern, output, re.MULTILINE):
            failures.append(f"unexpected /{pattern}/")
    if verbose or failures:
        print(f"--- {claim['id']}: {' '.join(claim['cmd'])}\n{output.rstrip()}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", default=None)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    claims = []
    for path in sorted(SUITE.glob("*.toml")):
        data = tomllib.loads(path.read_text())
        claims += [{**claim, "files": data["probes"][claim["probe"]]} for claim in data["claim"]]
    ids = [c["id"] for c in claims]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        print(f"duplicate claim ids: {sorted(duplicates)}")
        return 2

    if args.only:
        unknown = set(args.only) - set(ids)
        if unknown:
            print(f"unknown claim ids: {sorted(unknown)}")
            return 2
        claims = [c for c in claims if c["id"] in args.only]

    failed = 0
    for claim in claims:
        failures = run_claim(claim, args.verbose)
        status = "FAIL" if failures else "ok"
        print(f"{status:4} {claim['id']}: {claim['statement']}")
        for failure in failures:
            print(f"     {failure}")
        failed += bool(failures)
    print(f"\n{len(claims) - failed}/{len(claims)} claims verified")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
