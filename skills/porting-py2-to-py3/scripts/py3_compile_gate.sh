#!/usr/bin/env bash
# Milestone gate for a Python 2 -> 3 port.
#   parseable:  every file compiles under the target interpreter (SyntaxWarning counted separately)
#   importable: pytest can collect every test module under the target interpreter
#
# Usage: py3_compile_gate.sh [-p python3.13] [-t tests_dir] [-w] SRC_DIR [SRC_DIR...]
#   -w  also fail on SyntaxWarning (invalid escape sequences are SyntaxWarning since 3.12)
#   -t  run `pytest --collect-only` on tests_dir after the compile stage
set -u

PYTHON=python3
TESTS=""
STRICT=0
usage() { echo "usage: $0 [-p python] [-t tests_dir] [-w] SRC_DIR..." >&2; exit 2; }
while getopts "p:t:w" opt; do
  case "$opt" in
    p) PYTHON="$OPTARG" ;;
    t) TESTS="$OPTARG" ;;
    w) STRICT=1 ;;
    *) usage ;;
  esac
done
shift $((OPTIND - 1))
[ $# -ge 1 ] || usage

list_failures() {
  "$PYTHON" "$@" -m compileall -q -f "${ROOTS[@]}" 2>&1 \
    | grep -E "^\*\*\* Error compiling" \
    | sed -E "s/^\*\*\* Error compiling '([^']+)'.*/\1/" | sort -u
}
ROOTS=("$@")

echo "== parseable under $("$PYTHON" -V 2>&1)"
ERRORS=$(list_failures)
WARNINGS=$(list_failures -W error::SyntaxWarning | grep -vxF -f <(printf '%s\n' "$ERRORS") || true)
N_ERR=$(printf '%s' "$ERRORS" | grep -c . || true)
N_WARN=$(printf '%s' "$WARNINGS" | grep -c . || true)
echo "syntax errors:   $N_ERR file(s)"
echo "syntax warnings: $N_WARN file(s)"
if [ "$N_ERR" -gt 0 ]; then
  printf '%s\n' "$ERRORS" | head -40
  [ "$N_ERR" -gt 40 ] && echo "... ($N_ERR total)"
  exit 1
fi
if [ "$STRICT" -eq 1 ] && [ "$N_WARN" -gt 0 ]; then
  printf '%s\n' "$WARNINGS" | head -40
  exit 1
fi
echo "ok: parseable"

if [ -n "$TESTS" ]; then
  echo "== importable: pytest --collect-only $TESTS"
  "$PYTHON" -m pytest --collect-only -q "$TESTS" 2>&1 | tail -15
  exit "${PIPESTATUS[0]}"
fi
