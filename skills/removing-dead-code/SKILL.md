---
name: removing-dead-code
description: >
  Proof-driven workflow for deleting dead Python code and unused dependencies
  without breaking production: unused imports, unreachable branches, unreferenced
  functions and classes, whole modules, unhit endpoints and jobs, unused
  requirements. Use this skill whenever the user wants to remove dead code, asks
  "is this still used" or "delete this module", wants to find unused code or
  unused dependencies, shrink the codebase, or clean up before migration or a
  Python 3 port. Also trigger on tool names and techniques: vulture, pyflakes, autoflake,
  ruff F401, deptry, pip-check-reqs, coverage in production, tombstones, probes.
  Casual requests like "nobody uses this anymore", "can we drop this",
  "legacy module" or "trim requirements.txt" should trigger it too.
license: MIT
---

# Removing Dead Code

Deleting code is cheap to do and cheap to revert only when each deletion is
**atomic and carries its proof**. Static tools produce candidates. What counts
as proof depends on the category, and the procedure below is ordered by how
much proof each category needs. Never skip ahead: a module that "looks dead" to
vulture is a candidate, and a candidate is not a deletion.

**RELATED:** porting-py2-to-py3 (when the cleanup prepares a Python 2 code base for the port).

## Before you start

1. Read `references/tools.md` for the tool table, exact commands, and which
   releases still run on Python 2.7.
2. Read `references/production-coverage.md` before any claim about endpoints,
   jobs, tasks or whole modules. Static analysis cannot prove those dead.
3. Run the full test suite and record the result. Freeze `pip freeze` output and
   the lockfile. Every later step compares against this.
4. **Start dynamic collection now**, even if today's PR only removes imports.
   Categories 4 and 5 need 30 to 90 days of production data, and the clock only
   starts when the collector is deployed. Use `scripts/coverage_bootstrap.py`.
5. Python 2 code base: pick one of the two paths in "Python 2 note" below before
   running any tool.

## The procedure, ordered by proof required

Work through the categories in order. Each category lists what to find, the
tool, the proof required before deleting, and what to preserve.

### 1. Unused imports and unused local variables

| | |
|---|---|
| Find | `pyflakes` or `autoflake --check` (2.7), `ruff check --select F401,F841` (py3-parsable source) |
| Proof | Tool report plus a green full test suite after the change |
| Preserve | Re-exports in `__init__.py`, names listed in `__all__`, side-effect imports (model registration, signal hookup, monkeypatches, blueprint and plugin imports), `try/except ImportError` compatibility shims |

```bash
autoflake --check --remove-all-unused-imports --remove-unused-variables \
    --ignore-init-module-imports -r src/
```

Read the list before applying `--in-place`. An import that only has effects on
import is not unused. Mark it `# noqa: F401` with a one-line reason.

### 2. Unreachable code

| | |
|---|---|
| Find | `vulture src/ --min-confidence 100` (code after `return`/`raise`, `if False`, unused arguments) |
| Proof | vulture 100% is proof on its own; green suite confirms |
| Preserve | Unused arguments on callbacks, signal handlers and overridden methods whose signature is fixed by the caller |

### 3. Unreferenced private functions, classes and methods

| | |
|---|---|
| Find | `vulture src/ --min-confidence 60`, or `dead` (whole-repo definitions vs references) |
| Proof | All three: (a) tool report, (b) whole-repo grep of the bare name across code, templates, YAML, JSON, SQL, docs and sibling repos finds nothing, (c) the defining module has no `getattr`, `globals()`, `import_module` or string dispatch that could reach it |
| Preserve | Anything a decorator registers (routes, CLI commands, tasks, filters, signal receivers, fixtures), ORM model attributes, `__dunder__` methods, interface implementations |

```bash
git grep -n -w 'export_rows' -- ':!*.pyc'
gh search code 'export_rows' --owner <org>
git log -S 'export_rows' --oneline | head
```

If a symbol is only called by another dead symbol, delete both in the same
commit. 60% confidence means "no reference found in the analyzed files". It is
a candidate, never a proof.

### 4. Whole modules

| | |
|---|---|
| Find | Modules every other tool lists as entirely unused, or whose file shows 0% in combined production coverage |
| Proof | All of: no dotted import or string path anywhere (`git grep -n 'pkg.legacy_export\|legacy_export'`), 0% executed lines in production coverage across **all** services over the window, not listed in `setup.py` entry points, Celery `include=`/`imports`, alembic `env.py`, settings lists or Dockerfile/Procfile commands |
| Preserve | Modules only imported by migrations, modules registered by name in config, modules that exist only to be pickled or unpickled |

Dynamic evidence is mandatory here. If collection has not run for the full
window yet, the module stays and the commit message of the collector PR says
when the window ends.

### 5. Public but unhit endpoints, tasks and cron jobs

| | |
|---|---|
| Find | `flask routes` (or `app.url_map.iter_rules()`), `app.tasks.keys()`, Kubernetes CronJob and beat schedules, joined against access logs and task counters |
| Proof | All of: 0 hits in access logs or task counters over the window (12 months, or a calendar audit for monthly, quarterly and yearly jobs); absent from every schedule (beat, CronJob YAML, crontab, `send_task` literals); not in API docs, contracts or SDKs; consumers and owners asked and the answer recorded; a tombstone or a 410 feature flag soaked for one more cycle without firing |
| Preserve | Anything behind a flag that is currently off, seasonal jobs whose season is outside the window, error and fallback paths |

The soak is not optional. A route with zero hits in 30 days and a quarterly
report job look identical in the logs.

### 6. Unused dependencies

| | |
|---|---|
| Find | Import inventory diffed against installed `top_level.txt`, `pip-check-reqs` (`pip-extra-reqs`), or `deptry` on py3-parsable source |
| Proof | All of: no static import, no string or config reference (`import_module`, `'pkg.module:attr'` entry points, SQLAlchemy dialect URLs, logging handler paths, gunicorn/uwsgi config, Dockerfile, Procfile, CI), `pip uninstall` followed by the full suite and a staging run |
| Preserve | Drivers and backends loaded by URL or setting (`psycopg2`, `gevent`), CLI tools run from Procfile, CI or Makefile (`gunicorn`, `celery`, `alembic`) |

Regenerate the lockfile in the same commit and delete the transitive packages
that vanish from it. A dependency removed from `requirements.in` but still
pinned in the lock is not removed. Also trim unused extras (`pkg[extra]`) and
tiny libraries that 20 lines of stdlib replace.

### 7. Database columns and tables

Out of scope for this skill. Removing a column is expand/contract: stop reading
it, deploy, confirm with `pg_stat_user_tables` or query logs, then drop in a
later release. Never bundle schema drops with code deletion.

## Commit rules

1. **One removal per commit**, with the proof in the message. A category with
   fourteen items is fourteen commits, or one commit per module when the items
   are mechanical and the tool output is attached.
2. **Delete, never comment out.** `git log -S name` finds it again.
3. **Tests that only exercise the deleted code go in the same commit.** A test
   that fails after the deletion is either proof the code was alive or a test
   to delete; decide, do not skip it.
4. **Full suite after every batch**, not only at the end of the PR.
5. **Soak between batches.** Deploy, watch error rates and 404/500 counts on the
   neighboring routes, then open the next batch.
6. **Rarely hit error paths are not dead.** Zero hits on an `except` branch is
   good news, not a deletion candidate.

Example messages:

```
Remove unused imports from billing/ (autoflake 1.4 + pyflakes 2.4.0)

Full suite green (2143 passed). Kept billing/__init__.py re-exports and
billing/signals.py side-effect import.
```

```
Remove legacy_export._format_row and _escape_cell

vulture 60%, no references: git grep -w across code, templates and infra
repos, gh search code in the org. legacy_export has no getattr/dispatch.
Deleted tests/test_legacy_export.py::test_format_row in the same commit.
```

```
Remove /v1/legacy/export route and legacy_export module

0 hits in nginx access logs 2025-10-01..2026-10-01. 0 executed lines in
production coverage across api, 50 workers and 90 cron jobs
(2026-07-01..2026-10-01). Absent from beat and CronJob schedules. Finance
confirmed the CSV export was retired in 2024. 410 flag soaked 2026-09-01..
2026-10-01 without a hit.
```

## Dynamic-reference risk checklist

Grep for each of these before deleting a name. Any hit moves the item up one
category in the proof ladder.

- `getattr(`, `globals()[`, `importlib.import_module(`, `__import__(` with a non-literal or a config-driven string
- Celery task names: `@task(name=...)`, `send_task('...')`, `apply_async` by name, beat schedules
- `url_for('endpoint')`, Jinja helpers, filters, macros and context processors referenced from templates
- `__all__` and `__init__.py` re-exports
- `setup.py` / `pyproject.toml` entry points and plugin registries
- alembic migrations that import models or helpers
- Pickled class paths in caches, queues and sessions: removing the class breaks unpickling of data already stored
- blinker, SQLAlchemy and Django signal listeners registered only by importing the module
- JSON-RPC, webhook, admin command and management command names
- External consumers: other repos, SDKs, partners, mobile clients
- Jobs that run yearly, quarterly or at month end
- Code behind a feature flag that is currently off

## Python 2 note

Almost every current tool parses only Python 3 syntax (vulture 2.x, ruff,
pyflakes 2.5+, autoflake 2.x, deptry, dead, deadcode). Two ways to analyze a
Python 2.7 code base:

1. **Last py2-compatible releases, run under the 2.7 interpreter**: vulture 1.6,
   pyflakes 2.4.0, autoflake 1.4, pylint 1.9.x, pip-check-reqs 2.0.4, coverage 5.5.
2. **Apply only the syntax fixers of `futurize --stage1` first** (print function,
   `except E as e`, octal literals, long literals, backticks, `<>`). The code
   keeps running on 2.7 and now parses as Python 3, so every modern tool works.

For a large code base take path 2 and keep path 1 for a first pass. Versions and
pins are in `references/tools.md`.

## Multi-service production coverage

When one code base ships as many services (one API plus dozens of worker
Deployments and CronJobs), only the **union** of coverage across all of them
proves a function dead. A function unhit by the API is routinely hit by a cron
job. `references/production-coverage.md` covers collection post-fork,
persistence, sampling, combination, the time window and the output format.

py-spy is the cheap complement: sampled from outside every pod, it proves a
function **alive** and removes it from the candidate list, but a function it
never saw is unknown, not dead. Prune with py-spy, prove with coverage or a
tombstone.

```bash
coverage combine --keep data/*/.coverage.*
coverage json -o combined.json
python scripts/zero_hit_functions.py --source src/mypkg \
    --coverage-json api=cov/api.json --coverage-json worker-billing=cov/worker-billing.json \
    --coverage-json cron-reports=cov/cron-reports.json --per-service
```

## Quick reference

| Category | Tool | Proof before deleting |
|---|---|---|
| Unused imports, locals | pyflakes / autoflake / ruff F401 F841 | tool report + green suite; keep re-exports and side-effect imports |
| Unreachable code | vulture 100% | tool report + green suite |
| Private functions, classes | vulture 60% or `dead` | tool + whole-repo grep of the bare name + no dynamic dispatch in the module |
| Whole modules | grep + production coverage | no import or string path + 0% across all services over the window + not in entry points or schedules |
| Endpoints, tasks, cron jobs | routes/tasks inventory + logs | 0 hits over 12 months or calendar audit + absent from schedules + consumers asked + tombstone or 410 flag soaked |
| Dependencies | import inventory, pip-check-reqs, deptry | no import, no string/config reference, uninstall + suite + staging; lock regenerated |
| DB columns, tables | out of scope | expand/contract |

## Common mistakes

- **Deleting on vulture 60% alone.** It reports "no reference found", which
  templates, strings and other repos routinely contradict.
- **Running ruff or vulture 2.x on Python 2 source.** They fail to parse
  `print x` and `except E, e:` and report nothing, or crash. Use the 2.7
  releases or run the stage-1 syntax fixers first.
- **One big commit per category.** Reverting a single wrong deletion then
  means reverting the whole PR.
- **Proof in the PR description only.** The description does not survive a
  squash merge or a cherry-pick. The commit message does.
- **Treating test coverage as production evidence.** `pytest --cov` shows what
  tests reach. Code that only tests call is still dead code, and code tests
  never reach may be hot in production.
- **Collecting production coverage from one service only.** The API is one of
  many entry points. Combine all services before concluding anything.
- **Starting the window too late.** Dynamic collection should start in the
  first PR, before any module or endpoint deletion is even proposed.
- **Removing a requirement without regenerating the lock.** Transitive
  packages stay pinned and the "removal" changes nothing in the image.
- **Deleting the flag and the code in one step.** Keep the 410 or raise
  behind a flag for one cycle first. Flipping the flag back is the rollback.
- **Deleting a class that is pickled somewhere.** Queues, caches and sessions
  hold instances; unpickling fails after the deletion.

## Checklist

Before declaring a removal batch done:

- [ ] Baseline suite result, `pip freeze` and lockfile recorded before any change
- [ ] Dynamic collection deployed and the window end date written down
- [ ] Each deletion is its own commit, with the proof in the message
- [ ] Every deleted name grepped across code, templates, config and sibling repos
- [ ] The dynamic-reference checklist walked for every deleted name
- [ ] Endpoints and jobs: logs, schedules, consumers and soak all documented
- [ ] Dependencies: lock regenerated, orphaned transitives removed, staging run green
- [ ] Tests that only exercised deleted code removed in the same commit
- [ ] Full suite green after the batch
- [ ] Soak period scheduled before the next batch
