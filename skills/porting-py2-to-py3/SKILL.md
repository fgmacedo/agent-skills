---
name: porting-py2-to-py3
description: >
  Methodology and tooling for porting a Python 2.7 codebase to Python 3 while the
  team keeps shipping: choosing the target version, dependency strategy, phased
  workflow with CI gates, agent loops for the mechanical and the judgment work,
  staged rollout and rollback. Use this skill whenever the user mentions Python 2,
  2.7, "port to Python 3", "py3 migration", "drop Python 2", futurize, 2to3,
  modernize, six, unicode_literals, basestring, print statements, bytes vs str
  errors after a port, or asks which Python version to target. Also trigger when
  a dependency has no Python 3 release and must be forked, or when a legacy
  service must move off an EOL interpreter.
license: MIT
---

# Porting Python 2 to Python 3

Core principle: **the port lands on the main branch as Python-2-compatible commits,
behind CI gates that only ratchet forward; the interpreter switch is the last,
smallest step.** Code changes are cheap. What is expensive is production risk,
calendar (soak windows, other teams' reviews) and the attention of the team that
keeps shipping on the same tree.

## Before you start

- Read `references/target-version.md` to choose the target. Default in late 2026: 3.13, with 3.14 as a go/no-go once the suite is green. Never pick an EOL version, and never assume a framework version "won't run" on a newer interpreter: measure it (Phase 0, step 5).
- Read `references/tooling.md` for the converter, the interpreter flags, the pins of the last py2-compatible versions, and which tools are dead (do not recommend `caniusepython3`, `pylint --py3k` on pylint 2.x, `futurize --stage2`, or the `future` runtime).
- Read `references/catalog.md` when fixing a specific idiom. It classifies every change as **M** (a tool rewrites it) or **J** (decide per site with the stated procedure).
- `references/case-studies.md` has the tactics behind this workflow (Instagram, Dropbox, Yelp, Mercurial).
- **OPTIONAL PRE-PHASE:** removing-dead-code (sibling skill). Every function, route, job and dependency removed is one fewer to port and verify.

## Phase 0: safety net and measurements (on main)

Done when: the environment is reproducible, CI publishes coverage and fails on regression, golden tests exist for every persisted invariant, and the spike has answered which interpreter the current framework chain runs on.

1. **Freeze what production really runs.** `pip freeze` inside the production image becomes a versioned lockfile. Base images maintained elsewhere often install unpinned packages that the repo never names (SQLAlchemy, DB drivers, memcache clients). Those are dependencies too. If the base image belongs to another team, build your own from `python:2.7.18-slim` plus the lockfile now: the py3 image needs the same layout, and the switch stops depending on their calendar.
2. **Pick the target version** with the decision rule in `references/target-version.md`. Write it into the project's README and agent instructions file in the same PR.
3. **Coverage as a gate.** Run the suite with `coverage` (5.5 on py2) in CI, publish the number, set `fail_under` to the current value. Start collecting coverage from production or staging now (see removing-dead-code for the multi-service design); the window must be long before Phase 2 needs it.
4. **Golden tests for cross-version invariants.** Record outputs under py2 as fixtures and assert byte-equality under both interpreters: IDs derived from hashes or `sys.maxint`, signed tokens, encrypted payloads, cache keys, serialized exports (JSON, CSV, XLSX, PDF), URLs built from user data, anything parsed by another system. These are the tests that catch `b'...'` leaks and rounding drift before a deploy does.
5. **One-day spike.** Build a py3 image on the target with the py2-compatible framework chain pinned (`references/tooling.md`, section 6) and import the chain in isolation, since the application still has py2 syntax at this point: `python3 -c "import flask, flask_sqlalchemy, sqlalchemy, <driver>, <rest layer>, <event loop lib>"` (Django: `django.setup()` plus `migrate` against sqlite) plus a minimal app factory smoke test. Expect the ceiling to differ by stack: the Flask 1.1 chain runs on 3.13, Django 1.11 stops at 3.9 (`references/tooling.md`, section 6). Check wheels for the target with `pip download --only-binary=:all: --python-version 3XY --platform manylinux2014_x86_64 -r requirements.txt` before building; a C extension without a wheel for the target either builds from source in the image or forces a split pin (step 6). If the chain imports on the target, the cutover changes only the interpreter. If it does not, cut over on the newest version it runs on and make the framework upgrade the next project. One variable at a time. The `-t tests` stage of the compile gate only becomes meaningful after Phase 1.
6. **Dependency inventory.** For every package: last version with 2.7, first without, whether the pinned version imports on the target, and whether a wheel exists for the target. Internal packages without py3 builds go to their owners now; they are the calendar risk. Archived upstreams get a fork (`references/tooling.md`, section 7). A package that cannot straddle both interpreters (its last py2 release has no build for the target: pandas 0.24, numpy 1.16, often psycopg2 2.8 and mysqlclient 1.4 without source builds) gets a **split pin** by environment marker, `pkg==old; python_version<"3"` and `pkg==new; python_version>="3"`, code restricted to the API subset both versions share, and golden tests for its outputs. From this point: no new package without py3 support.
7. **Baseline the census.** `python3 scripts/py2ism_census.py SRC --save py2ism-baseline.json` and add `--check` to CI. Teammates cannot add Python 2 idioms from now on.

## Phase 1: parseable on the target (on main, behaviour identical on 2.7)

Done when: `scripts/py3_compile_gate.sh -p python3.13 SRC` reports zero syntax errors, and the gate is required in CI.

Apply only the syntax fixers of `futurize --stage1`, under 2.7, one fixer per PR, per directory: `fix_print_with_import`, `fix_except`, `fix_numliterals`, `fix_repr`, `fix_ne`, `fix_raise`, `fix_tuple_params`, `fix_exec`. Then the `ur''` literals by hand (catalog A). The code still runs on 2.7 exactly as before, and now every Python-3-only tool (vulture 2.x, ruff, deptry, pyupgrade for diagnostics) can read it. Run the py2 suite after each PR.

## Phase 2: shrink the surface

Done when: the dead-code candidates with proof have been removed and soaked.

Use the removing-dead-code skill: unused imports, unreachable code, unreferenced modules, routes and jobs with zero production hits, unused dependencies. Do it after Phase 1 so the py3 tools work, with the production coverage started in Phase 0. Route, job and whole-module removal needs at least 30 days of production coverage (12 months or a calendar audit for seasonal jobs). If the deadline does not allow the window, bound this phase to the static proofs (imports, unreachable code, unreferenced private symbols, unused dependencies) and let the collector keep running; the dynamic removals come after the cutover.

## Phase 3: modernize while staying on 2.7 (on main, small PRs)

Done when: the census shows zero non-informational occurrences outside `six` shims, the py2 suite passes under `python2 -3 -Werror::DeprecationWarning -Qwarnall -R -tt`, and every dependency is at its last py2-compatible version.

1. Remaining `futurize --stage1` fixers: `fix_absolute_import`, `fix_has_key`, `fix_next_call`. Do not run `fix_dict` blindly; it wraps every `keys()`/`items()` in `list()` (see catalog E). Commit per fixer.
2. Census loop (below) for the J categories: `basestring`/`unicode`/`long` via `six`, `iteritems`, `__metaclass__`, `e.message`, `sys.maxint`, stdlib renames via `six.moves`, integer division, `StringIO` vs `BytesIO`.
3. Run the py2 suite with `-3 -Werror::DeprecationWarning -Qwarnall -R -tt`; it finds `cmp`, integer `/`, mixed indentation and order-dependent tests that grep cannot.
4. Upgrade dependencies to their last py2-compatible versions, one package per PR, each deployed to production before the next: test runner first (pytest 4.6.11, mock 3.0.5), then the framework chain, then drivers (MySQL-python to mysqlclient 1.4.6), then backports replaced by environment markers (`functools32; python_version<"3"`).
5. Keep the gates green: census `--check`, compile gate, optional `modernize --enforce`.

## Phase 4: the py3 job as a ratchet (still on main)

Done when: the py3 job is required and green, and golden tests produce identical values on both interpreters.

1. Add a CI job on the target with `continue-on-error: true`, running `python3 -bb -X warn_default_encoding -W error::DeprecationWarning -m pytest`, plus a known-failures list (`pytest-quarantine`, or an allowlist file with `xfail_strict = true`). A listed test that starts passing must leave the list; an unlisted test that fails breaks the job. Publish the pass count in the job summary.
2. Milestones, in order: parseable, importable (`pytest --collect-only` clean), functional parity (pass count rising to 100%), job required.
3. Work the list with the ratchet loop (below). Bytes/str discipline: decode at the input edge, text inside, encode at the output edge. Audit hashing, crypto, base64, ctypes, subprocess and Redis call sites against catalog B even if no test fails there.
4. Optional but effective: mypy or pyright on the modules with the most `.encode`/`.decode` calls; `bytes` vs `str` is a type error the checker sees.

## Phase 5: cutover (short-lived branch, days)

Done when: every workload runs the py3 image for the observation window (7 calendar days; it does not compress) with error rates and latency at baseline.

1. The branch changes only: base image to the target, the py3 lockfile, removal of py2-only markers. Merge main into it daily; it must not live longer than two weeks.
2. CI builds **both** images from the same commit. Deploy manifests select the image per workload.
3. Agree a merge freeze of 48 hours with the team for the switch of the API workload.
4. Shared serialized state: memcached and queue pickles do not round-trip between interpreters. Namespace cache keys per interpreter (`py3:` prefix) or flush at cutover; pin `pickle` protocol 2 while both run. A namespaced cache starts cold for every workload that switches, so pace the switches and watch database load; warm the hottest keys from the py3 side first when the cache protects a database. Signed tokens (itsdangerous, JWT) stay valid across interpreters when the secret bytes and the JSON serializer are unchanged; the golden tests prove it, and a mismatch is escalated, not patched.
5. Order: staging fully; then production by workload: idempotent CronJobs, then worker Deployments one replica at a time, then the API behind the existing router with a canary percentage per route. Tag errors with the interpreter version so the two populations are comparable.
6. Keep the py2 image buildable for several weeks. Rollback is an image change, never a data migration.

## Phase 6: after the cutover

1. `pyupgrade --py313-plus` and `ruff check --select UP,W605 --target-version py313 --fix` remove `six`, `from __future__`, `u''` prefixes, coding headers and unittest aliases. Delete the py2 CI leg and the census gate.
2. Keep `-W error::DeprecationWarning` on permanently; it announces the next version's removals.
3. Upgrade the framework chain (Flask 3, Werkzeug 3, SQLAlchemy 2, Flask-SQLAlchemy 3, forked REST layer with its framework patches) as a separate project with its own soak.

## Agent loops

Calendar, from the case studies and scaled by size: parseability takes days to two weeks; importability weeks; functional parity is the long tail (weeks for 100k lines, months for millions) and is where the ratchet loop lives; each production observation window is 7 days and does not compress; other teams' packages are the item most likely to slip. Separate effort from calendar in any estimate.

Each loop has a unit of work, a batch size and a stop condition. Run them until the stop condition holds, then move to the next phase. Judgment steps (J) are decided per site with the procedure in the catalog; escalate only the items under "Escalate".

### Census loop (Phases 1 and 3)

```
python3 scripts/py2ism_census.py SRC          # worklist by category
pick one category
for each file with hits:
    apply the catalog rule for that category (M: run the tool; J: decide per site)
    python2 -3 -Werror::DeprecationWarning -Qwarnall -R -tt -m pytest tests/ -x
commit "<category>: <directory>" (one category x one directory per commit)
python3 scripts/py2ism_census.py SRC --check py2ism-baseline.json
```

Batch: one category per PR, one directory per commit. Stop: the category reads zero outside `six` shims. Refresh the baseline file in the same PR.

### Ratchet loop (Phase 4)

```
take the next test from the known-failures list
run it on the target; read the first error
look up the symptom in the table below; find the producer of the offending value
fix at the boundary (where the value enters or leaves the process), not at the failing line
if the fix touches a persisted or shared value: add a golden test first
run the test on py2 and py3; run the module's tests on both
remove the test from the list; commit
```

Batch: one test file per PR. Stop: the list is empty. If the same boundary explains many failures, fix the boundary once and remove every test it unblocks in one commit.

### Dead-code loop (Phase 2)

Candidate, then the proof required for its category, then removal, suite, commit with the proof in the message, soak before the next batch. The procedure and the proof table are in the removing-dead-code skill.

## Symptom to cause to fix

| Symptom on py3 | Cause | Fix (see catalog) |
|---|---|---|
| `TypeError: can't concat str to bytes`, `a bytes-like object is required` | value crossed an I/O edge without decode/encode | decode at the input edge; `text=True` on subprocess; `decode_responses=True` on Redis |
| `b'...'` appears inside a URL, SQL string, cache key, log line or JSON | `str(bytes)` or `'{}'.format(bytes)` | decode the producer; add `-bb` to the test run to make comparisons fail loudly |
| `TypeError: Strings must be encoded before hashing` | `hashlib`/`hmac` given `str` | `.encode('utf-8')` at the call; golden test for the digest |
| `'dict_keys' object is not subscriptable`, `'map' object has no len()` | views and lazy iterators | `list(...)` only where indexed or measured; `next(iter(d))` for first key |
| iteration yields nothing the second time | exhausted `map`/`filter`/`zip` | materialize once with `list()` |
| `RuntimeError: dictionary changed size during iteration` | deleting while iterating a view | iterate over `list(d)` |
| `TypeError: '<' not supported between instances of 'NoneType' and 'int'` | mixed-type or `None` sort keys | `key=lambda x: (x is None, x)`; normalize types |
| `TypeError: unhashable type` | `__eq__` defined without `__hash__` | add `__hash__` or stop using instances as keys |
| `TypeError: 'float' object cannot be interpreted as an integer` | true division feeding an index or `range` | `//` |
| object always truthy; registry never populated | `__nonzero__`; `__metaclass__` attribute | `__bool__`; `six.add_metaclass` |
| `NameError: basestring/unicode/long/xrange/unichr/reduce` | removed builtins | `six.string_types`, `six.text_type`, `int`, `range`, `chr`, `functools.reduce` |
| `ImportError: No module named urllib2/urlparse/StringIO/cPickle/ConfigParser/Queue` | PEP 3108 renames | `six.moves` or new name; `StringIO` vs `BytesIO` by content |
| `UnboundLocalError` after an `except` block | exception variable deleted at block end | rebind to another name inside the block |
| `RuntimeError: generator raised StopIteration` | PEP 479 | `return` in the generator; guard `next()` |
| `UnicodeDecodeError` reading a file that worked on py2 | text mode with locale encoding | `open(..., encoding='utf-8')` or `'rb'`; `-X warn_default_encoding` finds the rest |
| test expectations differ by `u'`/`L` or by element order | `repr` and hash randomization | compare values, not reprs; sort before asserting |
| seeded random fixtures differ | `random` algorithms changed in 3.2 | regenerate fixtures; do not rely on `version=1` |
| `\d` matches digits that are not `[0-9]` | Unicode-aware `re` on `str` | `re.ASCII` or `[0-9]` |
| `SyntaxWarning: invalid escape sequence` | non-raw regex string | `r''` (ruff `W605`) |
| `except X, e:` compiles on 3.14 but `e` is a `NameError` at runtime | PEP 758 | gate syntax with ruff or 3.13 |

## Escalate (stop and ask, with the evidence)

- A contract with an external consumer changes (public endpoint, webhook payload, exported file format).
- A persisted value changes format or value: pickles in caches or queues, signed tokens, encrypted payloads, IDs derived from hashes, serialized exports.
- A dependency owned by another team has no py3 build.
- A numeric result visible to customers would change (rounding of money, pagination counts).
- Target version, cutover date, merge freeze, and which workloads go first.

Everything else is decided by the loop with the catalog procedure.

## Quick reference

| Phase | Tool | Gate |
|---|---|---|
| 0 safety net | `pip freeze` in prod image; coverage 5.5; golden tests; spike image | lockfile; `fail_under`; spike answered; census baseline |
| 1 parseable | `futurize --stage1 -f <fixer>` under 2.7 | `py3_compile_gate.sh` zero errors, required in CI |
| 2 shrink | removing-dead-code skill | candidates removed with proof, soaked |
| 3 modernize | remaining stage1 fixers; `six`; `python2 -3 -Werror::DeprecationWarning -Qwarnall -R -tt`; dep upgrades one per PR; split pins for packages that cannot straddle | census zero; py2 suite green under those flags; deps at last py2 versions |
| 4 ratchet | py3 job with `-bb -W error::DeprecationWarning`; known-failures list; ratchet loop | py3 job required and green; golden tests equal |
| 5 cutover | two images per commit; per-workload image switch; cache namespacing; canary by route | 7-day observation at baseline |
| 6 cleanup | `pyupgrade --py3XX-plus`; ruff `UP`; drop py2 leg | permanent `-W error::DeprecationWarning` |

## Common mistakes

- **A long-lived port branch.** With an active team it never merges. Everything py2-compatible goes to main; only the image switch needs a branch, for days.
- **Choosing the target by assumption.** "Flask 1.1 won't run on 3.13" is a measurement, not a belief (it does); "Django 1.11 runs on 3.10" is also a measurement (it does not). Use the decision rule and the spike.
- **`futurize --stage2` or the `future` runtime.** The project is finished and breaks on 3.13+. Use `six`, which `pyupgrade` removes later.
- **Global `unicode_literals`.** It changes the type of every literal on 2.7 and breaks `__slots__`, `struct`, WSGI and C-API calls. Explicit `u''`, and `unicode_literals` only in regex modules.
- **Porting code before dependencies.** Package work waits on other people; start it in Phase 0.
- **Wrapping every `map`/`keys()` in `list()`.** Only where indexed, measured or iterated twice. Blind wrapping hides the real boundary and costs memory.
- **Fixing at the failing line.** A `TypeError` deep in a helper means a value crossed an edge undecoded. Fix the edge; the helper then works for every caller.
- **Skipping golden tests.** `b'...'` inside a cache key or a token does not raise; it silently splits your cache in two and logs everyone out.
- **Cutting over without handling shared pickles.** py2 and py3 pods reading the same memcached keys will crash on each other's data. Namespace or flush.
- **Trusting `compileall` on 3.14.** `except X, e:` parses there. Gate with ruff or 3.13.
- **Reading `six.moves` as the end state.** It is a window shim; Phase 6 removes it.

## Checklist

- [ ] Lockfile reflects what the production image actually runs
- [ ] Target version chosen by the decision rule and written into the repo
- [ ] Coverage published in CI with `fail_under`; production coverage collection started
- [ ] Golden tests for every hash, token, ID, cache key and export
- [ ] Spike answered: does the py2-compatible chain import on the target, and do wheels exist for it?
- [ ] Own base image built from the lockfile (or the base image owner committed to a py3 variant on your dates)
- [ ] Dependency table: last with 2.7 / first without / imports on target; owners pinged for internal packages
- [ ] Census baseline saved and `--check` in CI
- [ ] Compile gate zero errors and required
- [ ] Dead code removed with proof (sibling skill)
- [ ] Census zero outside `six`; py2 suite green under `-3 -Werror::DeprecationWarning -Qwarnall -R -tt`
- [ ] Dependencies at their last py2-compatible versions, each deployed
- [ ] py3 job required and green with `-bb -W error::DeprecationWarning`
- [ ] Both images built from one commit; cache keys namespaced; rollback rehearsed in staging
- [ ] Every workload on py3 for 7 days at baseline error rate
- [ ] `pyupgrade`/ruff cleanup landed; py2 leg deleted; `-W error::DeprecationWarning` permanent
