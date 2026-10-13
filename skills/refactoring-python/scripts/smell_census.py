"""Census of refactoring signals in Python source, with no judgment attached.

    python scripts/smell_census.py src/billing src/reports [--json out.json] [--top 20]

Per module: size, long functions, functions with many parameters, deep nesting, large
classes, module-level mutable state, I/O libraries imported outside an adapter module,
in-package fan-in and fan-out, and function bodies duplicated across the scanned set.
The output is sorted by a rough score so the loudest modules come first; naming the smell
and choosing the transformation is the reader's job (see references/smells.md).

Standard library only.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

LONG_FUNCTION = 40
MANY_PARAMS = 5
DEEP_NESTING = 4
LARGE_CLASS_LINES = 300
LARGE_CLASS_METHODS = 15
DUPLICATE_MIN_STATEMENTS = 5

IO_MODULES = {
    "requests",
    "httpx",
    "urllib",
    "urllib3",
    "aiohttp",
    "http",
    "socket",
    "smtplib",
    "ftplib",
    "subprocess",
    "sqlalchemy",
    "psycopg2",
    "psycopg",
    "pymysql",
    "MySQLdb",
    "sqlite3",
    "pymongo",
    "redis",
    "boto3",
    "botocore",
    "google.cloud",
    "pika",
    "kombu",
    "celery",
    "confluent_kafka",
    "kafka",
    "prometheus_client",
    "statsd",
    "random",
}
IO_CALLS = {
    "datetime.now",
    "datetime.utcnow",
    "date.today",
    "time.time",
    "time.sleep",
    "os.getenv",
    "os.environ.get",
    "open",
}
ADAPTER_STEMS = {
    "adapters",
    "adapter",
    "infra",
    "infrastructure",
    "io",
    "gateway",
    "gateways",
    "cli",
    "main",
    "app",
    "wsgi",
    "asgi",
    "service",
    "services",
    "repositories",
    "repository",
    "clients",
    "client",
}


@dataclass
class ModuleReport:
    path: str
    lines: int
    functions: int
    classes: int
    long_functions: list[str] = field(default_factory=list)
    many_params: list[str] = field(default_factory=list)
    deep_nesting: list[str] = field(default_factory=list)
    large_classes: list[str] = field(default_factory=list)
    mutable_module_state: list[str] = field(default_factory=list)
    io_imports: list[str] = field(default_factory=list)
    io_calls: list[str] = field(default_factory=list)
    fan_out: int = 0
    fan_in: int = 0
    score: int = 0


def _dotted(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_dotted(node.value)}.{node.attr}"
    return ""


def _nesting(node: ast.AST, depth: int = 0) -> int:
    deepest = depth
    for child in ast.iter_child_nodes(node):
        nested = isinstance(
            child,
            ast.If
            | ast.For
            | ast.While
            | ast.With
            | ast.Try
            | ast.AsyncFor
            | ast.AsyncWith
            | ast.Match,
        )
        deepest = max(deepest, _nesting(child, depth + 1 if nested else depth))
    return deepest


def _length(node: ast.AST) -> int:
    end = getattr(node, "end_lineno", None) or node.lineno
    return end - node.lineno + 1


class _Normalize(ast.NodeTransformer):
    """Rename names positionally so two functions that differ only in naming compare equal."""

    def __init__(self) -> None:
        self.names: dict[str, str] = {}

    def visit_Name(self, node: ast.Name) -> ast.AST:
        node.id = self.names.setdefault(node.id, f"n{len(self.names)}")
        return node

    def visit_arg(self, node: ast.arg) -> ast.AST:
        node.arg = self.names.setdefault(node.arg, f"n{len(self.names)}")
        node.annotation = None
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return node


def _fingerprint(func: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    body = [
        s for s in func.body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
    ]
    if len(body) < DUPLICATE_MIN_STATEMENTS:
        return None
    normalized = _Normalize().visit(ast.Module(body=body, type_ignores=[]))
    return ast.dump(normalized, include_attributes=False)


def _module_name(path: Path) -> str:
    """Dotted name from the top of the package tree (the first ancestor without __init__.py)."""
    top = path.parent
    while (top.parent / "__init__.py").exists():
        top = top.parent
    rel = path.relative_to(top.parent).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def scan(paths: list[Path]) -> tuple[list[ModuleReport], list[dict[str, object]]]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += sorted(f for f in p.rglob("*.py") if "__pycache__" not in f.parts)
        elif p.suffix == ".py":
            files.append(p)
    known = {_module_name(f.resolve()) for f in files}
    imports: dict[str, set[str]] = defaultdict(set)
    reports: list[ModuleReport] = []
    fingerprints: dict[str, list[str]] = defaultdict(list)

    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError) as exc:
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        name = _module_name(path.resolve())
        lines = len(path.read_text(encoding="utf-8").splitlines())
        report = ModuleReport(path=str(path), lines=lines, functions=0, classes=0)
        is_adapter = path.stem in ADAPTER_STEMS or path.parent.name in ADAPTER_STEMS

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if alias.name in IO_MODULES or top in IO_MODULES:
                        if not is_adapter:
                            report.io_imports.append(alias.name)
                    if alias.name in known:
                        imports[name].add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                top = module.split(".")[0]
                if (module in IO_MODULES or top in IO_MODULES) and not is_adapter:
                    report.io_imports.append(module)
                for alias in node.names:
                    for candidate in (module, f"{module}.{alias.name}"):
                        if candidate in known and candidate != name:
                            imports[name].add(candidate)
            elif isinstance(node, ast.Call):
                called = _dotted(node.func)
                if called in IO_CALLS and not is_adapter:
                    report.io_calls.append(f"{called}:{node.lineno}")
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                report.functions += 1
                length = _length(node)
                params = (
                    len(node.args.args) + len(node.args.kwonlyargs) + len(node.args.posonlyargs)
                )
                if node.args.args and node.args.args[0].arg in ("self", "cls"):
                    params -= 1
                if length > LONG_FUNCTION:
                    report.long_functions.append(f"{node.name} ({length} lines)")
                if params > MANY_PARAMS:
                    report.many_params.append(f"{node.name} ({params} params)")
                depth = _nesting(node)
                if depth > DEEP_NESTING:
                    report.deep_nesting.append(f"{node.name} (depth {depth})")
                fp = _fingerprint(node)
                if fp:
                    fingerprints[fp].append(f"{path}:{node.name}")
            elif isinstance(node, ast.ClassDef):
                report.classes += 1
                methods = sum(
                    isinstance(i, ast.FunctionDef | ast.AsyncFunctionDef) for i in node.body
                )
                length = _length(node)
                if length > LARGE_CLASS_LINES or methods > LARGE_CLASS_METHODS:
                    report.large_classes.append(f"{node.name} ({length} lines, {methods} methods)")

        for node in tree.body:
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
            value = getattr(node, "value", None)
            if targets and isinstance(
                value, ast.List | ast.Dict | ast.Set | ast.ListComp | ast.DictComp
            ):
                for t in targets:
                    if isinstance(t, ast.Name) and not t.id.isupper():
                        report.mutable_module_state.append(t.id)
        reports.append(report)

    fan_in: Counter[str] = Counter()
    for targets in imports.values():
        for t in targets:
            fan_in[t] += 1
    by_name = {r.path: r for r in reports}
    for path in files:
        name = _module_name(path.resolve())
        r = by_name.get(str(path))
        if r is None:
            continue
        r.fan_out = len(imports.get(name, ()))
        r.fan_in = fan_in.get(name, 0)
        r.score = (
            3 * len(r.long_functions)
            + 2 * len(r.many_params)
            + 2 * len(r.deep_nesting)
            + 4 * len(r.large_classes)
            + len(r.mutable_module_state)
            + 3 * len(set(r.io_imports))
            + 2 * len(r.io_calls)
            + max(0, r.fan_out - 5)
            + r.lines // 400
        )

    duplicates = [{"sites": sites} for sites in fingerprints.values() if len(sites) > 1]
    for dup in duplicates:
        for site in dup["sites"]:
            r = by_name.get(site.split(":")[0])
            if r:
                r.score += 3
    reports.sort(key=lambda r: (-r.score, r.path))
    return reports, duplicates


def render(reports: list[ModuleReport], duplicates: list[dict[str, object]], top: int) -> str:
    out = [f"{'score':>5}  {'lines':>5}  {'fn':>3}  {'cls':>3}  {'out':>3}  {'in':>3}  module"]
    for r in reports[:top]:
        out.append(
            f"{r.score:>5}  {r.lines:>5}  {r.functions:>3}  {r.classes:>3}  "
            f"{r.fan_out:>3}  {r.fan_in:>3}  {r.path}"
        )
        for label, items in (
            ("long functions", r.long_functions),
            ("many params", r.many_params),
            ("deep nesting", r.deep_nesting),
            ("large classes", r.large_classes),
            ("mutable module state", r.mutable_module_state),
            ("I/O imports outside an adapter", sorted(set(r.io_imports))),
            ("I/O calls outside an adapter", r.io_calls),
        ):
            if items:
                out.append(f"{'':>34}{label}: {', '.join(items)}")
    if duplicates:
        out.append("")
        out.append("duplicated function bodies (same statements, names normalized):")
        for dup in duplicates:
            out.append("  " + "  ==  ".join(dup["sites"]))  # type: ignore[arg-type]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("paths", nargs="+", type=Path)
    p.add_argument("--json", type=Path, help="write the full census here")
    p.add_argument("--top", type=int, default=25, help="modules to print")
    args = p.parse_args(argv)
    reports, duplicates = scan(args.paths)
    print(render(reports, duplicates, args.top))
    if args.json:
        args.json.write_text(
            json.dumps(
                {"modules": [asdict(r) for r in reports], "duplicates": duplicates}, indent=2
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
