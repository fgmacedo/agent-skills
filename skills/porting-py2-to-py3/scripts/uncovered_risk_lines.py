#!/usr/bin/env python3
"""List uncovered lines that carry an idiom whose behaviour differs between 2.7 and 3.x.

Usage:
    coverage json -o coverage.json
    python3 uncovered_risk_lines.py coverage.json [coverage-other-leg.json ...]
    python3 uncovered_risk_lines.py coverage.json --root src/ --pattern 'MyType\\('

A line is reported when it is missing from every coverage file given and matches
the risk regex. Each report file is one leg (interpreter); passing both legs
lists lines no test runs anywhere. Paths are read as coverage wrote them,
relative to --root (default: current directory). The output is a review list
for a person or an agent, not a pass/fail gate.
"""
from __future__ import print_function

import argparse
import io
import json
import os
import re
import sys

RISK = (
    r"\bstr\(|\bsorted\(|\bmax\(|\bmin\(|\bhash\(|\.encode\(|\.decode\(|\bsix\."
    r"|hasattr\([^)]*__iter__|isinstance\([^)]*\bstr\b|\bdict\(|\bbytes\(|\bunicode\b"
    r"|\bround\(|(?<![/*=!<>])\s/\s(?!/)|\.keys\(\)|\.values\(\)|\.items\(\)|\bmap\(|\bfilter\(|\bzip\("
    r"|\.message\b|\.warn\(|re\.escape\(|\bcmp\b|__nonzero__|__cmp__|\bis not \"|\bis \""
)


def missing_by_file(paths):
    common = None
    for path in paths:
        with io.open(path, "r", encoding="utf-8") as fh:
            files = json.load(fh)["files"]
        current = {name: set(entry.get("missing_lines", [])) for name, entry in files.items()}
        if common is None:
            common = current
        else:
            common = {name: lines & current.get(name, set()) for name, lines in common.items()}
    return common or {}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("coverage_json", nargs="+")
    parser.add_argument("--root", default=".", help="directory the coverage paths are relative to")
    parser.add_argument("--pattern", default=RISK, help="regex that marks a line as risky")
    args = parser.parse_args(argv)

    rx = re.compile(args.pattern)
    total_missing = 0
    hits = []
    for name, lines in sorted(missing_by_file(args.coverage_json).items()):
        if not lines:
            continue
        full = os.path.join(args.root, name)
        if not os.path.exists(full):
            print("missing source: %s" % full, file=sys.stderr)
            continue
        with io.open(full, "r", encoding="utf-8", errors="replace") as fh:
            source = fh.read().splitlines()
        total_missing += len(lines)
        for number in sorted(lines):
            if number <= len(source) and rx.search(source[number - 1]):
                hits.append((name, number, source[number - 1].strip()))

    for name, number, text in hits:
        print("%s:%d: %s" % (name, number, text))
    print("risk lines: %d of %d uncovered" % (len(hits), total_missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
