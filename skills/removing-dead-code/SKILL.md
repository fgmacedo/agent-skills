---
name: removing-dead-code
description: >
  Proof-driven workflow for deleting dead code and unused dependencies in any
  language without breaking production: unused imports, unreachable branches,
  unreferenced functions and classes, whole modules, unhit endpoints and jobs,
  unused packages. Use this skill whenever the user wants to remove dead code,
  asks "is this still used" or "delete this module", wants to find unused code
  or unused dependencies, shrink the codebase, or clean up before a migration or
  a language-version port. Also trigger on techniques and tool names: dead-code
  analyzers, unused-import linters, dependency checkers, coverage in production,
  tombstones, probes, vulture, pyflakes, ruff F401, deptry, knip, ts-prune,
  deadcode, staticcheck U1000. Casual requests like "nobody uses this anymore",
  "can we drop this", "legacy module" or "trim the requirements" should trigger
  it too. Language-specific tools and commands live in references/<language>.md;
  Python is covered today.
license: MIT
---

# Removing Dead Code

Deleting code is cheap to do and cheap to revert only when each deletion is
**atomic and carries its proof**. Static tools produce candidates. What counts
as proof depends on the category, and the procedure below is ordered by how
much proof each category needs. Never skip ahead: a module that "looks dead" to
an analyzer is a candidate, and a candidate is not a deletion.

This file is language-neutral. Tools, exact commands, version pins and the
language's own dynamic-reference traps live in one reference per language:

| Language | Reference |
|---|---|
| Python | `references/python.md` (tool table in `references/python-tools.md`, production coverage in `references/python-production-coverage.md`, scripts in `scripts/`) |
| Other | No reference yet. Follow this file, choose the language's equivalent of each tool category in the "Tool categories" section, and record the tool and version in every commit message. |

**RELATED:** porting-py2-to-py3 (when the cleanup prepares a Python 2 code base for the port).

## Before you start

1. Read `references/<language>.md` for the code base's language. If it does
   not exist, say so and proceed with the tool categories below.
2. Run the full test suite and record the result. Freeze the installed
   dependency set and the lockfile. A project without a lockfile records the
   installed set and the fact that no lock exists; that is a baseline, not a
   missing step. Every later step compares against this.
3. **Start dynamic collection now**, even if today's PR only removes imports.
   Categories 4 and 5 need 30 to 90 days of production data, and the clock only
   starts when the collector is deployed. When the collector cannot be wired
   (no common entry point in this repo, no deploy path), the minimum is a
   tombstone in each suspect with the window end date in the commit message.
4. Deploy manifests often live in another repository (container files,
   process-manager files, CronJob YAML, CI). Search them there
   (`gh search code`), or name the check as a merge gate in the commit
   message. Never assume they are empty because this checkout has none.
5. Static analysis cannot prove an endpoint, a job, a task or a whole module
   dead. Read the "Dynamic evidence" section before any claim about those.

## Tool categories

Every language has an equivalent of each row. Pick the one for the code base
and write its name and version in the commit messages.

| Category | What it is | Python example |
|---|---|---|
| Unused-import and unused-local linter | compiler or linter rule, usually with autofix | pyflakes, autoflake, ruff F401/F841 |
| Dead-code analyzer | whole-repo definitions versus references, with a confidence tier | vulture, dead |
| Reference search | plain-text search across code, templates, config, docs and sibling repositories | `git grep -w`, `gh search code` |
| Route, task and job inventory | the framework's own listing of registered endpoints, tasks and schedules | `flask routes`, Celery `app.tasks`, CronJob YAML |
| Dependency checker | declared packages versus imported packages | pip-check-reqs, deptry |
| Production coverage | executed lines or functions per service, combined across services | coverage.py |
| Proof of life | sampling profiler or APM that shows a function on a live stack | py-spy |
| Tombstone or probe | a marker in one suspect function that logs when it fires | own code |

## The procedure, ordered by proof required

Work through the categories in order. Each category lists what to find, the
tool category, the proof required before deleting, and what to preserve.

### 1. Unused imports and unused local variables

| | |
|---|---|
| Find | Unused-import and unused-local linter |
| Proof | Tool report plus a green full test suite after the change |
| Preserve | Re-exports from package index files, names listed in a public export list, side-effect imports (model registration, signal hookup, monkeypatches, blueprint and plugin imports), compatibility shims that import under try/catch |

Read the list before applying the autofix. An import that only has effects on
import is not unused. Suppress the rule on that line with a one-line reason.
In languages where an unused import is a compile error, this category is "it
builds" and needs no linter.

### 2. Unreachable code

| | |
|---|---|
| Find | Dead-code analyzer at its highest confidence tier (code after `return`/`raise`/`throw`, constant-false branches, unused arguments) |
| Proof | The highest tier is proof on its own; green suite confirms |
| Preserve | Unused arguments on callbacks, signal handlers and overridden methods whose signature is fixed by the caller |

### 3. Unreferenced private functions, classes and methods

| | |
|---|---|
| Find | Dead-code analyzer at its lowest confidence tier ("no reference found") |
| Proof | All three: (a) tool report, (b) whole-repo search of the bare name across code, templates, YAML, JSON, SQL, docs and sibling repos finds nothing, (c) the defining module has no open-ended lookup that could reach it: reflection, name-based lookup, dynamic import, or dispatch built from strings or config. A literal registration table of function values is closed and static; the analyzer already accounts for it |
| Preserve | Anything a decorator or annotation registers (routes, CLI commands, tasks, filters, signal receivers, fixtures), ORM model attributes, operator-overload and lifecycle methods, interface implementations |

```bash
git grep -n -w 'export_rows'
gh search code 'export_rows' --owner <org>
git log -S 'export_rows' --oneline | head
```

If a symbol is only called by another dead symbol, delete both in the same
commit. "No reference found in the analyzed files" is a candidate, never a
proof. The exception is a compiled language with no name-based function
lookup and a whole-program reachability analyzer: for unexported symbols its
report is proof on its own, once build tags, linker directives, FFI exports
and plugin lookups have been checked.

### 4. Whole modules

| | |
|---|---|
| Find | Modules every other tool lists as entirely unused, or whose file shows 0% in combined production coverage |
| Proof | All of: no import or string path anywhere (search the dotted and the bare name), 0% executed lines in production coverage across **all** services over the window, not listed in entry points, task-queue include lists, migration environments, settings lists or container and process-manager commands |
| Preserve | Modules only imported by migrations, modules registered by name in config, modules that exist only to be serialized or deserialized |

Dynamic evidence is mandatory here. If collection has not run for the full
window yet, the module stays and the commit message of the collector PR says
when the window ends.

### 5. Public but unhit endpoints, tasks and cron jobs

| | |
|---|---|
| Find | Route, task and job inventory joined against access logs and task counters |
| Proof | All of: 0 hits in access logs or task counters over the window (12 months, or a calendar audit for monthly, quarterly and yearly jobs); absent from every schedule (beat, CronJob YAML, crontab, task-name literals); not in API docs, contracts or SDKs; consumers and owners asked and the answer recorded; a tombstone or a 410 feature flag soaked for one more cycle without firing |
| Preserve | Anything behind a flag that is currently off, seasonal jobs whose season is outside the window, error and fallback paths |

The soak is not optional. A route with zero hits in 30 days and a quarterly
report job look identical in the logs.

### 6. Unused dependencies

| | |
|---|---|
| Find | Dependency checker, plus an import inventory diffed against the declared packages |
| Proof | All of: no static import, no string or config reference (dynamic import, `module:attr` entry points, driver URLs, logging handler paths, server config, container file, process-manager file, CI), uninstall followed by the full suite and a staging run |
| Preserve | Drivers and backends loaded by URL or setting, CLI tools run from the process-manager file, CI or Makefile |

Regenerate the lockfile in the same commit and delete the transitive packages
that vanish from it. A dependency removed from the manifest but still pinned in
the lock is not removed. Without a lockfile, list the orphaned transitives by
name in the commit message (from the dependency tree tool). The staging run is
a merge gate, not a pre-commit gate: the commit carries the uninstall and the
suite result and names the staging run as the condition for merging. Also
trim unused extras and tiny libraries that 20 lines of the standard library
replace.

### 7. Database columns and tables

Out of scope for this skill. Removing a column is expand/contract: stop reading
it, deploy, confirm with the database's table statistics or query logs, then
drop in a later release. Never bundle schema drops with code deletion.

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
6. **Rarely hit error paths are not dead.** Zero hits on an error handler is
   good news, not a deletion candidate.

Message shape, one per category. The names are illustrative; in your repo
the same names may be alive through a string path, so run the ladder before
copying the shape:

```
Remove unused imports from billing/ (<linter> <version>)

Full suite green (2143 passed). Kept billing package re-exports and the
billing.signals side-effect import.
```

```
Remove legacy_export._format_row and _escape_cell

<analyzer> lowest tier, no references: git grep -w across code, templates and
infra repos, gh search code in the org. legacy_export has no reflection or
string dispatch. Deleted the test that only covered _format_row in the same
commit.
```

```
Remove /v1/legacy/export route and legacy_export module

0 hits in access logs 2025-10-01..2026-10-01. 0 executed lines in production
coverage across api, 50 workers and 90 cron jobs (2026-07-01..2026-10-01).
Absent from every schedule. Finance confirmed the CSV export was retired in
2024. 410 flag soaked 2026-09-01..2026-10-01 without a hit.
```

## Dynamic-reference risk checklist

Search for each of these before deleting a name. Any hit moves the item up one
category in the proof ladder. The language reference lists the concrete
spellings.

- Reflection and name-based lookup: attribute access by string, global or
  module lookup by name, dynamic import with a non-literal or config-driven
  string
- Task-queue names: tasks registered or dispatched by string, beat and cron
  schedules
- Template references: route names, helpers, filters, macros and context
  processors called from templates
- Public export lists and package index re-exports
- Entry points and plugin registries declared in the package manifest
- Migrations that import models or helpers
- Serialized class paths in caches, queues and sessions: removing the class
  breaks deserialization of data already stored
- Signal and event listeners registered only by importing the module
- RPC, webhook, admin command and management command names
- External consumers: other repos, SDKs, partners, mobile clients
- Jobs that run yearly, quarterly or at month end
- Code behind a feature flag that is currently off

A hit is an entry point, schedule or lookup that can select the name. A
suggestive name alone ("monthly", "legacy", "v1") is a prompt to check the
schedules, not a hit; a schedule entry or an open-ended dispatch is.

## Dynamic evidence

Four techniques, from cheapest to strongest, and what each proves:

| Technique | Proves | Cost |
|---|---|---|
| Access logs, APM, task counters | hits per route and per task | already collected |
| Proof of life (sampling profiler) | a function is **alive**; a function never seen is unknown, never dead | zero in the target process |
| Tombstone or probe | one suspect was or was not called in the window, with a timestamp | near zero; one deploy |
| Production coverage | every executed line or function, per service | tracer overhead on the sampled replica |

Prune the candidate list with proof of life, prove the deletion with coverage
or a tombstone. Cost depends on the runtime: interpreted languages pay a
tracer, compiled languages often ship binary coverage at near-zero overhead;
the language reference says which.

### Multi-service production coverage

When one code base ships as many services (one API plus dozens of worker
Deployments and CronJobs), only the **union** of coverage across all of them
proves a function dead. A function unhit by the API is routinely hit by a cron
job. The design is the same in every language:

1. **Collection in process**, started at the common entry point after the
   process has forked, writing one data file per process with a unique suffix.
2. **Persistence** on exit, on SIGTERM and on a periodic timer for long-running
   workers, then upload to a bucket keyed by service and pod.
3. **Sampling**: one replica per Deployment, every CronJob run, since short
   jobs have no steady state.
4. **Combination** by a daily job that merges every file, then joins executed
   lines against the list of function definitions to emit zero-hit functions
   per service and in total.
5. **Window and seasonality**: cross the window with every schedule; a job
   that did not run in the window leaves its code "unknown", not "dead".
6. **Output**: a candidate list with the proof attached (services, window,
   hits = 0) that becomes the commit message of the removal.

## Quick reference

| Category | Tool category | Proof before deleting |
|---|---|---|
| Unused imports, locals | unused-import linter | tool report + green suite; keep re-exports and side-effect imports |
| Unreachable code | dead-code analyzer, highest tier | tool report + green suite |
| Private functions, classes | dead-code analyzer, lowest tier | tool + whole-repo search of the bare name + no dynamic dispatch in the module |
| Whole modules | search + production coverage | no import or string path + 0% across all services over the window + not in entry points or schedules |
| Endpoints, tasks, cron jobs | inventory + logs | 0 hits over 12 months or calendar audit + absent from schedules + consumers asked + tombstone or 410 flag soaked |
| Dependencies | dependency checker + import inventory | no import, no string/config reference, uninstall + suite + staging; lock regenerated |
| DB columns, tables | out of scope | expand/contract |

## Common mistakes

- **Deleting on the analyzer's lowest tier alone.** It reports "no reference
  found", which templates, strings and other repos routinely contradict.
- **Running a tool on syntax it cannot parse.** It reports nothing, or
  crashes, and "nothing found" reads as "nothing unused". Check the language
  reference for parser limits (Python 2 source is the common case).
- **One big commit per category.** Reverting a single wrong deletion then
  means reverting the whole PR.
- **Proof in the PR description only.** The description does not survive a
  squash merge or a cherry-pick. The commit message does.
- **Treating test coverage as production evidence.** Test coverage shows what
  tests reach. Code that only tests call is still dead code, and code tests
  never reach may be hot in production.
- **Collecting production coverage from one service only.** The API is one of
  many entry points. Combine all services before concluding anything.
- **Starting the window too late.** Dynamic collection should start in the
  first PR, before any module or endpoint deletion is even proposed.
- **Removing a dependency without regenerating the lock.** Transitive
  packages stay pinned and the "removal" changes nothing in the image.
- **Deleting the flag and the code in one step.** Keep the 410 or raise
  behind a flag for one cycle first. Flipping the flag back is the rollback.
- **Deleting a class that is serialized somewhere.** Queues, caches and
  sessions hold instances; deserialization fails after the deletion.

## Checklist

Before declaring a removal batch done:

- [ ] Language reference read, or its absence stated and the chosen tools named
- [ ] Baseline suite result, installed set and lockfile recorded before any change
- [ ] Dynamic collection deployed and the window end date written down
- [ ] Each deletion is its own commit, with the proof and the tool version in the message
- [ ] Every deleted name searched across code, templates, config and sibling repos
- [ ] The dynamic-reference checklist walked for every deleted name
- [ ] Endpoints and jobs: logs, schedules, consumers and soak all documented
- [ ] Dependencies: lock regenerated, orphaned transitives removed, staging run green
- [ ] Tests that only exercised deleted code removed in the same commit
- [ ] Full suite green after the batch
- [ ] Soak period scheduled before the next batch
