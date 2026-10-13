---
name: refactoring-python
description: >
  Use when refactoring or modernizing existing Python code without changing behavior:
  splitting a long function or module, removing drifted duplication, isolating I/O behind
  a port to make code testable, replacing Java-style classes with idiomatic Python, or
  judging whether an interface is over-engineering. Triggers: refactor, modernize, tidy,
  decouple, "make it testable", "make it pythonic", "god class", hexagonal, ports and
  adapters, characterization test. Not for profiling, Python 2 to 3 porting, dead-code
  removal or type hints.
license: MIT
---

# Refactoring Python

A refactoring is done when behavior is provably unchanged, the structure is better by a
named measure, and each step is a commit a reviewer can verify alone. Tidy first, then
change behavior, never both in one commit (Beck). The moves are Fowler's, the patterns
Kerievsky's, the idioms Ramalho's.

**Do not report done until all five hold:**

1. **Every commit is one named transformation** and the suite is green at each one:
   `python scripts/check_commits.py --base <sha> --test-cmd "<suite>"` passes.
2. **No commit mixes structure and behavior.** `refactor:`/`tidy:` commits change no
   assertion and add no test file; `test:` commits touch only tests; `fix:`/`feat:`
   commits carry a test that fails without them.
3. **Every function you changed was pinned first.** A `test:` commit with a
   characterization test precedes the first structural commit on an untested module.
4. **Every seam is real.** A dependency the domain cannot run without faking (I/O,
   clock, randomness) is a parameter or a port; the domain imports no I/O module;
   nothing abstract has fewer than two implementations unless it wraps I/O.
5. **Every idiom the user asked for covers the whole module**, verified by grep or AST,
   and no modernization changed an exception type, an ordering, a rounding, a string
   format or a mutation callers rely on.

## Workflow

### 0. Map the target

Scope (modules, callers, entry points), the test command, the baseline suite result, and
the lint and type checks that must stay green. Then:

```bash
python scripts/smell_census.py PATHS            # long functions, params, nesting, god modules, I/O outside adapters, duplicates
git grep -n "patch(\|patch.object(" tests/        # mock targets that break when names move
```

Name what the census found with `references/smells.md`. Order by value to the user (the
extraction, the testability, the readability they asked for); risk decides where you stop
to verify, not what you do first.

### 1. Pin behavior before the first move

Read `references/safety-net.md`. For each entry point you will touch that lacks tests,
write a characterization test: inputs covering every branch, record what it returns
**and** what it mutates, writes, logs and raises, paste the recorded values as expected.
Commit as `test(scope): characterize <entry point>`.

- A failing characterization test is a bug found: `xfail(strict=True)` with the issue,
  never fixed inside the refactoring.
- A flaky one is hidden nondeterminism (sets, `now()`, hash seeds): pin the input.
- When replacing an algorithm, keep the old one as an oracle and compare on generated
  inputs (`hypothesis`, or random inputs against a copy of the original module); delete
  the oracle in the last commit.

### 2. Plan the sequence, one row per commit

Write the table before editing. Each row is one transformation from
`references/transformations.md`, with the subject it will get:

| # | Type | Transformation | Target | Subject |
|---|---|---|---|---|
| 1 | test | Characterize | `generate_statement` | `test: characterize generate_statement` |
| 2 | tidy | Explaining constants | plan tuples | `tidy: name the plan constants` |
| 3 | refactor | Extract Function | rounding hack ×4 | `refactor: extract round_money` |
| 4 | refactor | Replace Conditional with lookup | plan ladder | `refactor: replace the plan conditional with a PLANS lookup` |
| 5 | refactor | Split Phase | compute vs render | `refactor: separate Statement from render_statement` |

- **A subject with "and" is two rows.** "Share the tax rule and name the rounding modes"
  is Move Function, then Replace Type Code with Class.
- **Tidyings first, then moves, then patterns.** Guard clauses, named constants, dead
  code and reading order make the moves small; a pattern (Command, Template Method,
  Composite, Adapter) only when its smell is present and there are two real variants.
- **Extract into the same module first.** A new module needs a second reason: another
  module will import it, or it changes for a different reason (a catalog of plans, money
  rounding). One module per extracted function is sprawl.
- **Behavior changes get their own row** typed `fix:`/`feat:`, after the structure that
  made them easy, with a test that fails without them.

### 3. Execute the loop

For each row: apply the mechanics (the small steps in `references/transformations.md`,
not the destination), run the suite, commit with the subject from the table.

- **Red after a step?** `git checkout -- .` and take a smaller step. Debugging forward
  turns the next commit into a behavior change nobody can review.
- **Stage by path, never `git commit -a`** in a `refactor:` commit: `-a` sweeps new test
  files into the structure commit. Added or removed assertions are a `test:` commit
  before (characterization) or after (`test: cover pricing.money directly`).
- **Every five commits:** full suite, lint, types, the boundary test, `check_commits.py`.
- **Stop and ask** before any step in the Escalate list.

### 4. Boundaries, only where they pay

Read `references/boundaries.md` before introducing any interface.

| The dependency is | Decision |
|---|---|
| I/O: DB or ORM session, HTTP client, queue, filesystem, email, metrics, env | port: `Protocol` or ABC in `ports.py`, implementation in `adapters.py`, built in the composition root |
| ≥ 2 real implementations selected at runtime | port |
| Clock, randomness, sleep | a parameter (`today: date`, `sleep: Callable[[float], None]`) defaulting to the real one in the composition root; no `Clock` class |
| One pure implementation (a formatter, a parser) | a parameter when tests need to swap it, else a direct call |
| A framework object the process shares (`app`, `Session`) | adapters import it; the domain receives values |
| "Might vary someday" | nothing; write in the PR what would trigger it |

**A seam is an object with the method, never the module.** `build_report(rates=converter)`
satisfies the signature and leaves `fx.report` importing `fx.converter`, hence `requests`.
Prove the seam in the tests:

```bash
python -c "import fx.report"            # with the dependency uninstalled or blocked
python scripts/check_boundaries.py --package fx --forbid requests,sqlalchemy,db --allow adapters.py,cli.py
```

Package shape: `ports.py` (interfaces and value types), pure domain modules,
`adapters.py` (the only importer of the ORM, `requests`, the broker), `service.py` or
`cli.py` (composition root, where `date.today()` and the adapters are built). The
contract the type cannot express (transaction scope, what failure returns, idempotency)
goes in the port's docstring. Copy `scripts/check_boundaries.py` into `tests/`.

### 5. Pythonic pass

Read `references/pythonic.md`. Each idiom is its own `refactor:` commit over the
**whole module**, and each has a "behavior changes when": `@dataclass` adds value
equality and removes hashing (`eq=False` or `frozen=True` keeps the old semantics);
`str(Status.OK)` prints `Status.OK` unless `StrEnum`; `if not amount` makes `0` missing;
a bare `except:` narrowed to `Exception` lets `KeyboardInterrupt` through; `@property`
breaks every `obj.total()` call site. Before committing:

```bash
git grep -n "os\.path\|range(len(\|\.get_[a-z_]*(\|%s" -- pkg/reader.py    # must print nothing for the idioms you replaced
```

### 6. Verify and report

```bash
python scripts/check_commits.py --base <sha> --test-cmd "<suite>" --require-characterization pkg/mod.py=pkg.mod,pkg
```

Then the full suite, lint, types, the boundary test. PR body: what changes and what does
not; the boundary and what guarantees it; behavior changes with their tests; findings
while pinning (xfail bugs, drift between copies); next step; out of scope.

## Escalate (stop and ask, with the evidence)

Persisted formats (pickles, cache keys, queue payloads of classes you move); external
contracts (API responses, webhook payloads, CLI flags, manifest entrypoints, liveness
probes bound to a file name); customer-visible numbers or ordering; `mock.patch` targets
in other teams' tests; migrations; hot paths with a measured budget; anything whose
deletion needs production evidence (hand off to `removing-dead-code`).

## Python facts that differ from intuition

Each is backed by a probe in `claims/refactoring-python/`.

- `mock.patch("pkg.clock.now")` does nothing for `pkg.report`, which did
  `from pkg.clock import now`: patch where the name is looked up; moved functions
  un-mock tests that patched their old home.
- Pickles, caches and queues store the class path; moving a class breaks loading what
  is already stored.
- `logging.getLogger(__name__)` renames the logger when the function moves.
- `from .core import *` in `__init__` hides callers from a grep of the module path.
- An import cycle can work in one order and fail in the other; a suite whose conftest
  imports the package first never sees it. Import each new module alone in a subprocess.
- `@dataclass` makes instances unhashable and equal by value unless `frozen=True`.
- `lru_cache` on a method keeps every instance alive.
- Set iteration order changes with `PYTHONHASHSEED`; dict order does not.
- `str()` of a plain `Enum` or a `(str, Enum)` member is `Status.OK` on 3.12; only
  `StrEnum` or `.value` serializes as `"ok"`.

## Quick reference

| Smell | Transformation | Reference |
|---|---|---|
| Long function, compute interleaved with render | Extract Function, Split Phase | transformations.md |
| `if plan ==` ladders, magic numbers | Explaining constants, Guard Clauses, lookup table | transformations.md |
| Copy-pasted helpers that drifted | Pin both, move the identical ones, name the difference as a policy | smells.md |
| `requests`/ORM/`now()` reached from logic | Parameterize Function, port + adapter, composition root | boundaries.md |
| Getters/setters, `range(len)`, `os.path`, string type codes | dataclass, iteration, pathlib, `StrEnum` | pythonic.md |
| ABC with one subclass, factory for one thing | Collapse Hierarchy, Inline Class, pass a function | smells.md |
| Untested entry point | characterization test, golden master, oracle comparison | safety-net.md |
