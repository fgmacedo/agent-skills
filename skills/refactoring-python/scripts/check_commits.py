"""Grade the commit history a refactoring left behind.

Run inside the repository. Every commit after the base is checked for the discipline a
reviewer wants from a refactoring: typed subjects, structure and behavior never mixed, the
suite green at every commit, a characterization test before the first change to an untested
module, no big-bang commit.

    grade-commits --min-commits 6 --max-behavior-commits 0 \\
        --carry tests/test_hidden_statement.py \\
        --require-characterization billing/statement.py=billing.statement,billing \\
        --test-cmd ".venv/bin/python -m pytest -q tests"

Checks tagged R are deterministic given git; checks tagged H are heuristics (they can be
fooled, and the hidden behavior tests are what catches what they miss).
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

STRUCTURE_TYPES = frozenset({"refactor", "tidy", "style", "chore", "build", "ci", "docs"})
BEHAVIOR_TYPES = frozenset({"feat", "fix", "perf"})
TEST_TYPES = frozenset({"test"})
SUBJECT_RE = re.compile(r"^(?P<type>[a-z]+)(\([\w./ -]+\))?!?: \S")
TEST_PATH_RE = re.compile(r"(^|/)(tests?|testing)/|(^|/)(test_[^/]*|[^/]*_test|conftest)\.pyi?$")
DOC_SUFFIXES = (".md", ".rst", ".txt")
ASSERTION_RE = re.compile(
    r"^\s*(assert\b|with pytest\.raises|pytest\.raises\(|self\.assert\w+\(|"
    r"\.assert_(called|not_called|awaited))"
)
TEST_DEF_RE = re.compile(r"^\s*(async\s+)?def test_")
TIME_BUDGET_S = 540
COUNT_CAP = 120


class GradeError(RuntimeError):
    pass


def git(*args: str, cwd: Path, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GradeError(f"git {' '.join(args)} failed: {proc.stderr.strip()[-500:]}")
    return proc.stdout


@dataclass
class Commit:
    sha: str
    subject: str
    type: str | None
    kind: str  # structure | behavior | tests | untyped
    files: dict[str, str] = field(default_factory=dict)  # path -> status (A M D R)
    renamed_from: dict[str, str] = field(default_factory=dict)  # new path -> old path
    added: int = 0
    removed: int = 0

    def touches(self, path: str) -> bool:
        return path in self.files or path in self.renamed_from.values()


@dataclass
class Check:
    id: str
    name: str
    ok: bool
    detail: str = ""

    @property
    def kind(self) -> str:
        return "robust" if self.id.startswith("R") else "heuristic"


def classify(subject: str) -> tuple[str | None, str]:
    match = SUBJECT_RE.match(subject)
    if not match:
        return None, "untyped"
    ctype = match.group("type")
    if ctype in STRUCTURE_TYPES:
        return ctype, "structure"
    if ctype in BEHAVIOR_TYPES:
        return ctype, "behavior"
    if ctype in TEST_TYPES:
        return ctype, "tests"
    return ctype, "untyped"


def is_test_path(path: str) -> bool:
    return bool(TEST_PATH_RE.search(path))


def root_commits(repo: Path) -> list[str]:
    return git("rev-list", "--max-parents=0", "HEAD", cwd=repo).split()


def load_commits(repo: Path, base: str) -> list[Commit]:
    shas = git("rev-list", "--reverse", f"{base}..HEAD", cwd=repo).split()
    commits: list[Commit] = []
    for sha in shas:
        subject = git("show", "-s", "--format=%s", sha, cwd=repo).strip()
        ctype, kind = classify(subject)
        commit = Commit(sha=sha, subject=subject, type=ctype, kind=kind)
        status = git("diff-tree", "--no-commit-id", "-r", "-M50%", "--name-status", sha, cwd=repo)
        for line in status.splitlines():
            parts = line.split("\t")
            code = parts[0][0]
            if code == "R":
                commit.files[parts[2]] = "R"
                commit.renamed_from[parts[2]] = parts[1]
            else:
                commit.files[parts[1]] = code
        numstat = git("show", "--numstat", "--format=", "-M50%", sha, cwd=repo)
        for line in numstat.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0] != "-" and parts[1] != "-":
                commit.added += int(parts[0])
                commit.removed += int(parts[1])
        commits.append(commit)
    return commits


def check_base(repo: Path, subject: str, author: str) -> tuple[Check, str | None]:
    roots = root_commits(repo)
    if len(roots) != 1:
        return Check("R1", "base intact", False, f"{len(roots)} root commits"), None
    base = roots[0]
    got_subject, got_author = git("show", "-s", "--format=%s%n%ae", base, cwd=repo).splitlines()[:2]
    ok = got_subject == subject and got_author == author
    detail = (
        "" if ok else f"root is {got_subject!r} by {got_author}, expected {subject!r} by {author}"
    )
    return Check("R1", "base intact", ok, detail), base


def check_linear(repo: Path, base: str) -> Check:
    merges = git("rev-list", "--merges", f"{base}..HEAD", cwd=repo).split()
    return Check(
        "R2", "linear history", not merges, f"{len(merges)} merge commits" if merges else ""
    )


def check_committed(repo: Path) -> Check:
    unstaged = subprocess.run(["git", "diff", "--quiet", "HEAD"], cwd=repo).returncode
    staged = subprocess.run(["git", "diff", "--cached", "--quiet", "HEAD"], cwd=repo).returncode
    ok = unstaged == 0 and staged == 0
    files = git("diff", "--name-only", "HEAD", cwd=repo).split() if not ok else []
    return Check("R3", "all work committed", ok, f"uncommitted: {', '.join(files[:8])}")


def check_count(commits: list[Commit], low: int, high: int) -> Check:
    n = len(commits)
    return Check("R4", "commit count", low <= n <= high, f"{n} commits, expected {low}..{high}")


def check_typed(commits: list[Commit]) -> Check:
    bad = [c.subject for c in commits if c.kind == "untyped"]
    return Check("R5", "typed subjects", not bad, "; ".join(bad[:5]))


def check_test_commits_scope(commits: list[Commit]) -> Check:
    bad: list[str] = []
    for c in commits:
        if c.kind != "tests":
            continue
        outside = [p for p in c.files if not is_test_path(p) and not p.endswith(DOC_SUFFIXES)]
        if outside:
            bad.append(f"{c.sha[:7]} touches {', '.join(outside[:4])}")
    return Check("R7", "test commits touch only tests", not bad, "; ".join(bad[:5]))


def check_behavior_budget(commits: list[Commit], limit: int) -> Check:
    behavior = [c for c in commits if c.kind == "behavior"]
    detail = "; ".join(f"{c.sha[:7]} {c.subject}" for c in behavior[:5])
    return Check("R8", "behavior commit budget", len(behavior) <= limit, detail)


def _count_lines(lines: list[str]) -> tuple[int, int]:
    return (
        sum(1 for line in lines if ASSERTION_RE.match(line)),
        sum(1 for line in lines if TEST_DEF_RE.match(line)),
    )


def check_structure_keeps_assertions(repo: Path, commits: list[Commit]) -> Check:
    bad: list[str] = []
    for c in commits:
        if c.kind != "structure":
            continue
        for path, status in c.files.items():
            if not is_test_path(path) or not path.endswith((".py", ".pyi")):
                continue
            if status == "A":
                bad.append(f"{c.sha[:7]} adds test file {path}")
                continue
            diff = git("show", "--format=", "-M50%", c.sha, "--", path, cwd=repo)
            if status == "R":
                diff += git(
                    "show", "--format=", "-M50%", c.sha, "--", c.renamed_from[path], cwd=repo
                )
            added = [
                line[1:]
                for line in diff.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            ]
            removed = [
                line[1:]
                for line in diff.splitlines()
                if line.startswith("-") and not line.startswith("---")
            ]
            a_assert, a_def = _count_lines(added)
            r_assert, r_def = _count_lines(removed)
            if a_assert != r_assert or a_def != r_def:
                bad.append(
                    f"{c.sha[:7]} changes {path}: assertions +{a_assert}/-{r_assert}, "
                    f"tests +{a_def}/-{r_def}"
                )
    return Check("H1", "structure commits keep test assertions", not bad, "; ".join(bad[:5]))


def _imports_any(source: str, names: tuple[str, ...]) -> bool:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if any(alias.name == n or alias.name.startswith(n + ".") for n in names):
                    return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if any(module == n or module.startswith(n + ".") for n in names):
                return True
            if any(f"{module}.{alias.name}" == n for alias in node.names for n in names):
                return True
    return False


def check_characterization_first(
    repo: Path, commits: list[Commit], rules: list[tuple[str, tuple[str, ...]]]
) -> Check:
    bad: list[str] = []
    for module_path, names in rules:
        first = next((c for c in commits if c.touches(module_path)), None)
        if first is None:
            continue
        earlier = commits[: commits.index(first)]
        pinned = False
        for c in earlier:
            if c.kind != "tests":
                continue
            for path, status in c.files.items():
                if status == "D" or not is_test_path(path) or not path.endswith(".py"):
                    continue
                if _imports_any(git("show", f"{c.sha}:{path}", cwd=repo), names):
                    pinned = True
                    break
            if pinned:
                break
        if not pinned:
            bad.append(
                f"{module_path} first changed in {first.sha[:7]} without an earlier test "
                f"commit importing {'/'.join(names)}"
            )
    return Check("H2", "characterization test before the first change", not bad, "; ".join(bad))


def check_no_big_bang(commits: list[Commit], max_share: float) -> Check:
    """Over structure and behavior commits only: a characterization commit may carry large
    golden files, and that is not the rewrite this check is after."""
    commits = [c for c in commits if c.kind != "tests"]
    if len(commits) < 3:
        return Check("H3", "no big-bang commit", True, "fewer than 3 code commits, not evaluated")
    total = sum(c.added + c.removed for c in commits) or 1
    biggest = max(commits, key=lambda c: c.added + c.removed)
    share = (biggest.added + biggest.removed) / total
    return Check(
        "H3",
        "no big-bang commit",
        share <= max_share,
        f"{biggest.sha[:7]} carries {share:.0%} of changed lines "
        f"({biggest.added + biggest.removed}/{total})",
    )


def run_suite_at_every_commit(
    repo: Path, commits: list[Commit], test_cmd: str, carry: list[str], timeout: int
) -> tuple[Check, list[dict[str, object]]]:
    cmd = shlex.split(test_cmd)
    venv = repo / ".venv"
    rows: list[dict[str, object]] = []
    failures: list[str] = []
    started = time.monotonic()
    tmp_root = Path(tempfile.mkdtemp(prefix="grade-commits-"))
    try:
        for index, c in enumerate(commits):
            if time.monotonic() - started > TIME_BUDGET_S:
                failures.append(f"time budget exceeded before {c.sha[:7]}")
                break
            wt = tmp_root / str(index)
            git("worktree", "add", "--detach", "--quiet", str(wt), c.sha, cwd=repo)
            try:
                if venv.exists():
                    os.symlink(venv.resolve(), wt / ".venv", target_is_directory=True)
                for rel in carry:
                    src = repo / rel
                    if not src.is_file():
                        raise GradeError(f"carry file missing in workspace: {rel}")
                    dest = wt / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dest)
                t0 = time.monotonic()
                try:
                    proc = subprocess.run(
                        cmd, cwd=wt, capture_output=True, text=True, timeout=timeout
                    )
                    ok, tail = proc.returncode == 0, (proc.stdout + proc.stderr)[-1500:]
                except subprocess.TimeoutExpired:
                    ok, tail = False, "timeout"
                rows.append(
                    {"sha": c.sha[:7], "ok": ok, "seconds": round(time.monotonic() - t0, 1)}
                )
                if not ok:
                    failures.append(f"{c.sha[:7]} {c.subject}: {tail.strip()[-400:]}")
            finally:
                git("worktree", "remove", "--force", str(wt), cwd=repo, check=False)
    finally:
        git("worktree", "prune", cwd=repo, check=False)
        shutil.rmtree(tmp_root, ignore_errors=True)
    return Check("R6", "suite green at every commit", not failures, "\n".join(failures[:3])), rows


def parse_rule(value: str) -> tuple[str, tuple[str, ...]]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expected MODULE_PATH=import.name[,import.name...]")
    path, names = value.split("=", 1)
    return path, tuple(n.strip() for n in names.split(",") if n.strip())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--repo", default=".", help="repository to grade (default: cwd)")
    p.add_argument("--min-commits", type=int, default=1)
    p.add_argument("--max-commits", type=int, default=80)
    p.add_argument("--max-behavior-commits", type=int, default=0)
    p.add_argument("--max-commit-share", type=float, default=0.6)
    p.add_argument("--test-cmd", default="", help="suite to run at every commit; empty skips R6")
    p.add_argument("--test-timeout", type=int, default=120)
    p.add_argument(
        "--carry",
        action="append",
        default=[],
        help="file copied from the workspace into every commit before running the suite",
    )
    p.add_argument(
        "--require-characterization",
        action="append",
        default=[],
        type=parse_rule,
        metavar="MODULE_PATH=import.name[,...]",
    )
    p.add_argument(
        "--base",
        help="commit the work starts from (default: the single root commit, which must match "
        "--base-subject and --base-author)",
    )
    p.add_argument("--base-subject", default="base")
    p.add_argument("--base-author", default="eval@local")
    p.add_argument(
        "--count-only", action="store_true", help="exit with the number of commits after the base"
    )
    p.add_argument("--json", type=Path, help="write the full result here")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = Path(args.repo).resolve()
    try:
        if args.base:
            base = git("rev-parse", "--verify", f"{args.base}^{{commit}}", cwd=repo).strip()
            base_check = Check("R1", "base intact", True, f"explicit base {base[:7]}")
        else:
            base_check, base = check_base(repo, args.base_subject, args.base_author)
            if base is None:
                base = root_commits(repo)[0]
        commits = load_commits(repo, base)
    except GradeError as exc:
        print(f"grade-commits: {exc}", file=sys.stderr)
        return 2

    if args.count_only:
        return min(len(commits), COUNT_CAP)

    checks = [
        base_check,
        check_linear(repo, base),
        check_committed(repo),
        check_count(commits, args.min_commits, args.max_commits),
        check_typed(commits),
    ]
    suite_rows: list[dict[str, object]] = []
    if args.test_cmd:
        suite_check, suite_rows = run_suite_at_every_commit(
            repo, commits, args.test_cmd, args.carry, args.test_timeout
        )
        checks.append(suite_check)
    checks += [
        check_test_commits_scope(commits),
        check_behavior_budget(commits, args.max_behavior_commits),
        check_structure_keeps_assertions(repo, commits),
        check_characterization_first(repo, commits, args.require_characterization),
        check_no_big_bang(commits, args.max_commit_share),
    ]

    for check in checks:
        mark = "ok  " if check.ok else "FAIL"
        line = f"[{check.id} {mark}] {check.name}"
        if check.detail and (not check.ok or args.verbose):
            line += f": {check.detail}"
        print(line)
    if args.verbose or any(not c.ok for c in checks):
        print("commits:")
        for c in commits:
            print(
                f"  {c.sha[:7]} {c.kind:9} +{c.added}/-{c.removed} {len(c.files):2}f  {c.subject}"
            )

    result = {
        "ok": all(c.ok for c in checks),
        "checks": [asdict(c) | {"kind": c.kind} for c in checks],
        "commits": [asdict(c) for c in commits],
        "suite": suite_rows,
    }
    if args.json:
        args.json.write_text(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
