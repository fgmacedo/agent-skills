# Dead-code and unused-dependency tools

Versions and compatibility verified against PyPI and upstream changelogs on
2026-10-12. Items marked [unverified] could not be confirmed.

Nearly every current tool parses with a Python 3 parser and cannot read py2-only
syntax (`print x`, `except E, e:`, backticks, `0777`, `ur''`, the `exec`
statement). For a Python 2.7 code base either pin the last py2-compatible
release and run it under 2.7, or apply the `futurize --stage1` syntax fixers
first so the source parses as Python 3 while still running on 2.7.

## Tool table

| Tool | What it finds | Runs on 2.7 source? | Notes |
|---|---|---|---|
| vulture 1.6 | unused defs, imports, unreachable code | Yes, under 2.7 | last 2.7 release; whitelist, `--ignore-decorators` |
| vulture 2.x (2.16) | same | No (py3 ast, requires >= 3.9) | after syntax modernization |
| pyflakes 2.4.0 | unused imports and locals | Yes, under 2.7 | 2.5.0 dropped 2.7 |
| autoflake 1.4 + pyflakes 2.4.0 | removes unused imports and locals | Yes, under 2.7 | 1.7.8+ requires >= 3.7; whether 1.5-1.7 ran on 2.7 is [unverified] |
| pylint 1.9.x | `unused-*`, `unreachable` (per module) | Yes, under 2.7 | 1.9.5 as the final 2.7 release is [unverified] |
| ruff F401/F811/F841 | unused imports and locals, autofix | No | after modernization |
| pycln / unimport | unused imports | No | |
| dead (asottile) | whole-repo unreferenced definitions | No | files from `git ls-files`; `--tests` |
| deadcode | rules DC01-DC13, `--fix` | No (requires >= 3.10) | |
| skylos | cross-file reference graph, `--trace` | No | aggressive; candidates only |
| mypy `--warn-unreachable` / pyright | unreachable branches | Partly (old mypy `--py2`) | after typing |
| jedi/parso <= 0.7.1 | find usages | Yes (py2 grammar) | parso 0.8.0 dropped py2; jedi 0.17.x as the matching line is [unverified] |
| coverage 5.5 | executed lines in production or staging | Yes, under 2.7 | 6.0 dropped 2.7; `parallel` + `combine` |
| py-spy | sampled live functions | Yes (2.3-2.7, out of process) | proves live only; prunes candidates, never confirms a deletion |
| `sys.setprofile` recorder, tombstones, probes | function hit, last hit | Yes (own code) | strongest proof for a single suspect |
| `flask routes` + access logs | unhit endpoints | Yes | map `$request_uri` to rule templates |
| pip-check-reqs 2.0.4 | extra and missing requirements | Yes, under 2.7 | 3.x requires >= 3.10 |
| deptry / FawltyDeps / creosote | unused, missing, transitive deps | No | run inside the venv, after modernization |
| pipdeptree / johnnydep / `pip list --not-required` | why is X installed | Metadata only, yes | |
| grep import inventory + `top_level.txt` | import vs requirement diff | Yes | add the string-import grep |

## Python 2.7 pins

```bash
pip install 'vulture==1.6' 'pyflakes==2.4.0' 'autoflake==1.4' 'pylint<2' \
    'pip-check-reqs==2.0.4' 'coverage==5.5'
```

Tested in this skill: `coverage==5.5` installs from sdist on Python 2.7.18 with pip 19.2.3.

## vulture

https://pypi.org/project/vulture/ (2.16, 2026-03-25, requires Python >= 3.9).
Changelog for 2.0: "The last Vulture release that supports Python 2.7 and
Python 3.5 is version 1.6." https://github.com/jendrikseipp/vulture/blob/main/CHANGELOG.md

Confidence levels:

| Confidence | Meaning |
|---|---|
| 100% | unused function arguments, unreachable code (after `return`/`raise`, `if False`) |
| 90% | unused imports |
| 60% | functions, classes, methods, attributes, properties, variables with no reference found in the analyzed files |

```bash
vulture src/ --min-confidence 100                       # proof-grade
vulture src/ --min-confidence 60 --sort-by-size         # candidates
vulture src/ --ignore-decorators "@app.route,@*.route,@celery.task,@shared_task,@pytest.fixture"
vulture src/ --ignore-names 'test_*,setUp*'
vulture src/ --make-whitelist > vulture_whitelist.py    # record false positives
vulture src/ vulture_whitelist.py                       # run with the whitelist
```

Exit code 3 means dead code was found. Prefer the whitelist over `--ignore-*`
flags and record names reached through `getattr` or string dispatch in it.
`[tool.vulture]` in `pyproject.toml` holds the same options.

Looks dead to vulture but is not, in Flask and SQLAlchemy apps: model columns
and attributes, `__tablename__`, `__repr__`, `before_request`, `errorhandler`,
`context_processor`, Jinja filters, Celery tasks, signal receivers, alembic
`upgrade`/`downgrade`, Marshmallow and WTForms fields.

`vulturecov` drops vulture findings that coverage data shows as executed:
https://pypi.org/project/vulturecov/

## pyflakes and autoflake

- pyflakes 2.5.0 (2022-07-30) dropped 2.7; last for 2.7 is 2.4.0 (2021-10-06).
  https://raw.githubusercontent.com/PyCQA/pyflakes/main/NEWS.rst
- autoflake 1.4 (2020-08-23) lists 2.7 in its classifiers; 1.7.8 requires >= 3.7;
  2.4.0 requires >= 3.10. https://pypi.org/project/autoflake/1.4/

```bash
pyflakes src/ | grep -E "imported but unused|assigned to but never used"
autoflake --check -r --remove-all-unused-imports --remove-unused-variables \
    --ignore-init-module-imports src/
autoflake --in-place -r --remove-all-unused-imports --remove-unused-variables \
    --ignore-init-module-imports src/
```

## ruff (py3-parsable source)

```bash
ruff check --select F401,F811,F841 src/
ruff check --select F401,F841 --fix src/
```

Add `# noqa: F401` with a reason on side-effect imports. Set
`ignore-init-module-imports = true` under `[tool.ruff.lint]` to keep
`__init__.py` re-exports.

## pylint 1.9.x (Python 2)

Docs: https://pylint.readthedocs.io/en/1.9/user_guide/index.html. The FAQ says
to use 1.8/1.9 under Python 2; 2.x analyzes py2 files only partially.

```bash
pylint --disable=all --enable=unused-import,unused-variable,unused-argument,unreachable src/
```

Per-module analysis: it cannot find project-wide uncalled functions.

## dead (asottile)

https://github.com/asottile/dead. Collects files via `git ls-files`, then does a
whole-repo definitions-versus-references pass with `ast`. `--tests` reports
names referenced only from tests separately. Suppress with `# dead: disable`.
The README lists false positives for interface implementations, enums and model
classes. Python 3 only.

```bash
dead --tests '(^|/)tests?/'
```

## deadcode

https://pypi.org/project/deadcode/ (2.4.1, requires >= 3.10). Rules DC01-DC13
cover unused variables, functions, classes, methods, attributes, imports,
properties, unreachable branches, code after `return` and commented-out code.

```bash
deadcode src/
deadcode src/ --fix --dry
deadcode src/ --ignore-names 'upgrade,downgrade' --ignore-definitions 'Base*'
```

## skylos

https://pypi.org/project/skylos/. Cross-file reference graph, optional
`--trace` runtime check, plus secret scanning. A third-party comparison found it
the most aggressive and slowest (626 findings against vulture's 22 on the same
code). Treat output as candidates only.

## Manual verification

```bash
git grep -n -w 'symbol_name' -- ':!*.pyc'           # code, templates, YAML, JSON, SQL
git grep -n 'pkg.module.symbol_name\|module:symbol_name'   # string and entry-point paths
git log -S 'symbol_name' --oneline | head           # when it was last touched
gh search code 'symbol_name' --owner <org>          # sibling repos
```

jedi and rope "find usages" need parso <= 0.7.1 for the py2 grammar
(https://raw.githubusercontent.com/davidhalter/parso/master/CHANGELOG.rst).

## Framework inventories

```bash
flask routes                                         # Flask 1.0+
python -c "from app import app; print(sorted(r.rule for r in app.url_map.iter_rules()))"
python -c "from tasks import celery; print(sorted(celery.tasks.keys()))"
kubectl get cronjobs -A -o custom-columns=NAME:.metadata.name,SCHEDULE:.spec.schedule
```

Join routes against nginx or load-balancer access logs by mapping each
`$request_uri` to its rule with `app.url_map.bind('').match(path)`. Join tasks
against beat schedules, CronJob YAML, crontabs and `send_task('name')` literals.

SQLAlchemy tables (`Base.metadata.tables`) can be joined against
`pg_stat_statements` and `pg_stat_user_tables` scan counts, but column and
table drops are out of scope for this skill.

## Unused dependencies

### deptry (py3-parsable source, inside the venv)

https://deptry.com/usage/. DEP001 missing, DEP002 unused, DEP003 transitive
import, DEP004 dev dependency used in production. Reads `requirements.txt`
(`requirements_files`), PEP 621, Poetry, PDM and uv `pyproject.toml`. Maps
distributions to modules through installed metadata, override with
`package_module_name_map`. Finds `importlib.import_module` only with literal
strings.

```bash
deptry src/
deptry src/ --requirements-files requirements.txt,requirements-dev.txt
```

### pip-check-reqs (2.0.4 for Python 2)

https://pypi.org/project/pip-check-reqs/ and
https://github.com/r1chardj0n3s/pip-check-reqs/blob/master/CHANGELOG.rst
("use version 2.0.4 for Python 2"; 3.1.0 requires >= 3.10).

```bash
pip-extra-reqs src/                      # declared but never imported
pip-missing-reqs --transitive src/       # imported but not declared
```

### FawltyDeps and creosote (py3)

- FawltyDeps (Tweag): undeclared and unused deps across requirements.txt,
  pyproject and setup.py. https://github.com/tweag/FawltyDeps
- creosote: unused deps against pyproject, Pipenv, PDM, requirements; misses
  importlib imports. https://pypi.org/project/creosote/

### Inventory that works on raw Python 2 source

```bash
git grep -hoE '^\s*(from|import)\s+[A-Za-z_][A-Za-z0-9_]*' -- '*.py' \
    | awk '{print $2}' | sort -u > imports.txt
SITE=$(python -c "import site; print(site.getsitepackages()[0])")
for f in "$SITE"/*.dist-info/top_level.txt "$SITE"/*.egg-info/top_level.txt; do
    [ -f "$f" ] && echo "$(basename "$(dirname "$f")" | sed 's/-.*//'): $(tr '\n' ' ' < "$f")"
done > modules_by_dist.txt
```

Join `imports.txt` against `modules_by_dist.txt`: a distribution none of whose
top-level modules appears in `imports.txt` is a candidate. Then grep the string references that no import inventory sees:

```bash
git grep -n 'import_module(\|__import__(\|:[a-z_]*$' -- '*.py' '*.cfg' '*.ini' '*.toml' '*.yaml'
git grep -n 'postgresql+\|mysql+\|redis://\|amqp://'
git grep -n -i 'handler\|backend\|worker.class\|worker_class' -- '*.ini' '*.cfg' '*.py' '*.yaml'
git grep -n 'console_scripts\|entry_points' setup.py setup.cfg pyproject.toml
grep -n 'pip install\|celery\|gunicorn\|uwsgi\|alembic' Dockerfile Procfile Makefile .github/workflows/*.yml
```

### Why is this installed

```bash
pipdeptree --reverse --packages psycopg2
pip list --not-required
johnnydep somepackage
```

### Removing one

```bash
pip uninstall -y somepackage
pytest                                    # full suite
pip-compile requirements.in               # or: uv pip compile requirements.in -o requirements.txt
git diff requirements.txt                 # packages that vanish were pulled in only by it
```

Commit the requirement removal, the lock regeneration and the orphaned
transitives together. Also trim unused extras (`pkg[extra]`) and tiny
libraries that 20 lines of stdlib replace.

## Dynamic detection, in brief

See `production-coverage.md` for the full design.

- coverage 5.5 is the last line that supports 2.7 (https://pypi.org/project/coverage/5.5/;
  6.0 dropped 2.7 and 3.5, https://pypi.org/project/coverage/6.0/). Modern cores
  (`sysmon`, `[run] patch = subprocess`) are 7.9+ and need Python 3.12+ for
  `sysmon`. https://coverage.readthedocs.io/en/latest/config.html
- py-spy supports "versions 2.3-2.7 and 3.3-3.14" out of process:
  `py-spy record --format raw --subprocesses --nonblocking`. Absence of samples
  does not prove dead. https://github.com/benfred/py-spy
- Tombstones and probes: David Schnepper, "Isn't That Code Dead?" (Velocity
  2014), via Andy Snell's Zombie Hunt (https://github.com/andysnell/zombie-hunt,
  https://nomadphp.com/video/277/zombie-hunt-find-and-safely-remove-undead-code);
  Bugsnag (https://www.bugsnag.com/?p=1862); Michael Feathers, "Scythe"
  (https://michaelfeathers.silvrback.com/scythe-using-coverage-in-production-to-find-dead-code).
- Cautionary case, 40k lines deleted on coverage evidence alone and checkout
  broke through `importlib` and reflection:
  https://dev.to/kollittle/i-deleted-40000-lines-of-dead-code-production-broke-in-3-minutes-12cc

## Methodology sources

- Fowler, Refactoring, "Remove Dead Code": https://refactoring.com/catalog/removeDeadCode.html
  and https://refactoring.guru/smells/dead-code
- Ned Batchelder, "Deleting code": https://nedbatchelder.com/blog/200212/deleting_code
- Jeff Atwood, "The Joy of Deletion": https://blog.codinghorror.com/the-joy-of-deletion/
- Software Engineering at Google, ch. 15 "Deprecation": https://abseil.io/resources/swe-book/html/ch15.html
- Feathers, Working Effectively with Legacy Code (characterization tests before touching code)
