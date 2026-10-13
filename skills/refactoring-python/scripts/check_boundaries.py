"""Assert the dependency rule of a package: domain modules never import the I/O layer.

Copy this file into the project's ``tests/`` as ``test_package_boundaries.py`` and edit
RULES, or run it as a command while exploring:

    python scripts/check_boundaries.py --package app/billing \\
        --forbid db,app.models,requests,sqlalchemy --allow adapters.py,service.py

What it checks, with the standard library ``ast`` only:

1. No module under the package, except the ones in ``allow``, imports a forbidden root.
   ``from app.models import Invoice`` counts as reaching ``app.models``; reading only the
   imported name would let the rule be sidestepped by importing the class.
2. Optionally, modules listed in ``standalone`` import in a bare interpreter
   (``python -c "import pkg.mod"``), which catches cycles that only close in one import
   order and imports that only resolve because a test module ran first.
"""

from __future__ import annotations

import argparse
import ast
import subprocess
import sys
from pathlib import Path

RULES = {
    "package": "app/billing",
    "forbid": ["db", "app.models", "sqlalchemy", "requests", "prometheus_client"],
    "allow": ["adapters.py", "service.py"],
    "standalone": ["app.billing.rules"],
}


def imported_modules(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if base:
                yield base
            for alias in node.names:
                yield f"{base}.{alias.name}" if base else alias.name


def reaches(module: str, forbidden: str) -> bool:
    return module == forbidden or module.startswith(forbidden + ".")


def violations(package: Path, forbid: list[str], allow: list[str]) -> list[str]:
    found: list[str] = []
    for path in sorted(package.rglob("*.py")):
        rel = path.relative_to(package).as_posix()
        if rel in allow or "__pycache__" in path.parts:
            continue
        reached = sorted({f for m in imported_modules(path) for f in forbid if reaches(m, f)})
        if reached:
            found.append(
                f"{package / rel} imports {', '.join(reached)}; that belongs in an adapter"
            )
    return found


def standalone_failures(modules: list[str], cwd: Path) -> list[str]:
    failures: list[str] = []
    for module in modules:
        proc = subprocess.run(
            [sys.executable, "-c", f"import {module}"], cwd=cwd, capture_output=True, text=True
        )
        if proc.returncode != 0:
            failures.append(f"{module} does not import on its own:\n{proc.stderr[-1500:]}")
    return failures


def test_domain_does_not_reach_the_io_layer() -> None:
    assert violations(Path(RULES["package"]), RULES["forbid"], RULES["allow"]) == []


def test_modules_import_on_their_own() -> None:
    assert standalone_failures(RULES["standalone"], Path.cwd()) == []


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--package", type=Path, default=Path(RULES["package"]))
    p.add_argument(
        "--forbid", default=",".join(RULES["forbid"]), help="comma-separated module roots"
    )
    p.add_argument(
        "--allow",
        default=",".join(RULES["allow"]),
        help="comma-separated paths relative to the package",
    )
    p.add_argument(
        "--standalone",
        default="",
        help="comma-separated dotted modules to import in a bare interpreter",
    )
    args = p.parse_args(argv)
    split = lambda s: [x.strip() for x in s.split(",") if x.strip()]  # noqa: E731
    problems = violations(args.package, split(args.forbid), split(args.allow))
    problems += standalone_failures(split(args.standalone), Path.cwd())
    for line in problems:
        print(line)
    print(f"{len(problems)} violations" if problems else "ok: boundaries hold")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
