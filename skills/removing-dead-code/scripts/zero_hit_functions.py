"""List functions and classes with zero executed lines in coverage.py JSON data.

Usage:

    python zero_hit_functions.py --source src/mypkg \\
        --coverage-json api=cov/api.json \\
        --coverage-json worker-billing=cov/worker-billing.json \\
        --coverage-json cron-reports=cov/cron-reports.json

Each ``--coverage-json`` is a ``coverage json`` output file, optionally
prefixed with a service label. A function is reported when none of its body
lines executed in any of the files (the union). ``--per-service`` adds, for
every function, the list of services that did execute it, so partially dead
code is visible too.

Source files are parsed with ``ast`` by the interpreter running this script.
Run it under the interpreter whose syntax the source uses (Python 2.7 for a
Python 2 code base).
"""
from __future__ import print_function

import argparse
import ast
import json
import os
import sys


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", action="append", required=True,
                        help="directory to scan for .py files (repeatable)")
    parser.add_argument("--coverage-json", action="append", required=True,
                        metavar="[LABEL=]FILE",
                        help="coverage json output, optionally labelled (repeatable)")
    parser.add_argument("--per-service", action="store_true",
                        help="print every function with the services that hit it")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--min-lines", type=int, default=1,
                        help="ignore functions with fewer executable lines")
    parser.add_argument("--exclude", action="append", default=[],
                        help="path fragment to skip while scanning (repeatable)")
    return parser.parse_args(argv)


def norm_parts(path):
    path = os.path.normpath(path).replace("\\", "/")
    return tuple(part for part in path.split("/") if part not in ("", "."))


class ServiceCoverage(object):
    def __init__(self, label, path):
        self.label = label
        with open(path) as handle:
            report = json.load(handle)
        self.files = {}
        for name, entry in report.get("files", {}).items():
            executed = set(entry.get("executed_lines", []))
            missing = set(entry.get("missing_lines", []))
            self.files[norm_parts(name)] = (executed, executed | missing)

    def lookup(self, abs_parts):
        best = None
        for parts in self.files:
            if len(parts) <= len(abs_parts) and abs_parts[-len(parts):] == parts:
                if best is None or len(parts) > len(best):
                    best = parts
        return self.files.get(best) if best else None


def load_services(specs):
    services = []
    for spec in specs:
        if "=" in spec and not os.path.exists(spec):
            label, path = spec.split("=", 1)
        else:
            label, path = os.path.splitext(os.path.basename(spec))[0], spec
        services.append(ServiceCoverage(label, path))
    return services


def iter_source_files(roots, excludes):
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames
                                 if not any(x in os.path.join(dirpath, d) for x in excludes))
            for filename in sorted(filenames):
                path = os.path.join(dirpath, filename)
                if filename.endswith(".py") and not any(x in path for x in excludes):
                    yield path


def node_end(node):
    end = getattr(node, "end_lineno", None)
    if end:
        return end
    return max(getattr(child, "lineno", node.lineno) for child in ast.walk(node))


FUNCTION_TYPES = (ast.FunctionDef,) + tuple(
    getattr(ast, name) for name in ("AsyncFunctionDef",) if hasattr(ast, name))


class Definition(object):
    def __init__(self, kind, qualname, lineno, body_start, end):
        self.kind = kind
        self.qualname = qualname
        self.lineno = lineno
        self.body_start = body_start
        self.end = end
        self.children = []

    def body_lines(self):
        return range(self.body_start, self.end + 1)


def collect_definitions(tree):
    found = []

    def visit(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, FUNCTION_TYPES + (ast.ClassDef,)):
                kind = "class" if isinstance(child, ast.ClassDef) else "function"
                qualname = prefix + child.name
                definition = Definition(kind, qualname, child.lineno,
                                        child.body[0].lineno, node_end(child))
                found.append(definition)
                visit(child, qualname + ".")
            else:
                visit(child, prefix)

    visit(tree, "")
    return found


def analyze_file(path, services, min_lines):
    with open(path, "rb") as handle:
        source = handle.read()
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        print("skip %s: %s" % (path, exc), file=sys.stderr)
        return []

    abs_parts = norm_parts(os.path.abspath(path))
    per_service = [(svc.label, svc.lookup(abs_parts)) for svc in services]
    loaded_anywhere = any(data is not None for _, data in per_service)

    results = []
    class_lines = {}
    for definition in collect_definitions(tree):
        body = set(definition.body_lines())
        if definition.kind == "class":
            class_lines[definition.qualname] = definition.lineno
            continue
        statements = set()
        hit_by = []
        for label, data in per_service:
            if data is None:
                continue
            executed, known = data
            statements |= known & body
            if executed & body:
                hit_by.append(label)
        if loaded_anywhere and len(statements) < min_lines:
            continue
        results.append({
            "file": path,
            "kind": definition.kind,
            "name": definition.qualname,
            "line": definition.lineno,
            "executable_lines": len(statements),
            "hit_by": hit_by,
            "module_loaded": loaded_anywhere,
        })

    results.extend(class_rollups(results, class_lines))
    return results


def class_rollups(function_results, class_lines):
    by_class = {}
    for item in function_results:
        if item["kind"] != "function" or "." not in item["name"]:
            continue
        owner = item["name"].rsplit(".", 1)[0]
        by_class.setdefault(owner, []).append(item)
    rollups = []
    for owner, methods in sorted(by_class.items()):
        hit_by = sorted(set(label for m in methods for label in m["hit_by"]))
        rollups.append({
            "file": methods[0]["file"],
            "kind": "class",
            "name": owner,
            "line": class_lines.get(owner, min(m["line"] for m in methods)),
            "executable_lines": sum(m["executable_lines"] for m in methods),
            "hit_by": hit_by,
            "module_loaded": methods[0]["module_loaded"],
            "methods": len(methods),
        })
    return rollups


def main(argv=None):
    args = parse_args(argv)
    services = load_services(args.coverage_json)
    labels = [svc.label for svc in services]

    rows = []
    for path in iter_source_files(args.source, args.exclude):
        rows.extend(analyze_file(path, services, args.min_lines))

    zero = [row for row in rows if not row["hit_by"]]

    if args.format == "json":
        json.dump({"services": labels, "zero_hit": zero,
                   "all": rows if args.per_service else None},
                  sys.stdout, indent=2)
        print()
        return 0

    print("services: %s" % ", ".join(labels))
    print("zero hits across all services (%d):" % len(zero))
    for row in zero:
        note = "" if row["module_loaded"] else "  [module never loaded]"
        extra = "  (%d methods)" % row["methods"] if row["kind"] == "class" else ""
        print("  %s:%d  %s %s%s%s" % (row["file"], row["line"], row["kind"],
                                      row["name"], extra, note))
    if args.per_service:
        print()
        print("per-service breakdown:")
        for row in rows:
            if row["kind"] != "function":
                continue
            print("  %s:%d  %s  hit by: %s" % (
                row["file"], row["line"], row["name"],
                ", ".join(row["hit_by"]) or "-"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
