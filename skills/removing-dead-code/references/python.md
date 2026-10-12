# Python

Everything Python-specific for the procedure in `SKILL.md`: the tool for each
category, exact commands, what to preserve, and the Python spellings of the
dynamic-reference checklist. Versions, confidence tiers and the full tool table
are in `python-tools.md`; production coverage, tombstones, the `sys.setprofile`
recorder and py-spy are in `python-production-coverage.md`.

## Python 2 code base: decide this first

Almost every current tool parses only Python 3 syntax (vulture 2.x, ruff,
pyflakes 2.5+, autoflake 2.x, deptry, dead, deadcode). Two ways to analyze a
Python 2.7 code base:

1. **Last py2-compatible releases, run under the 2.7 interpreter**: vulture 1.6,
   pyflakes 2.4.0, autoflake 1.4, pylint 1.9.x, pip-check-reqs 2.0.4, coverage 5.5.
   ```bash
   pip install 'vulture==1.6' 'pyflakes==2.4.0' 'autoflake==1.4' 'pylint<2' \
       'pip-check-reqs==2.0.4' 'coverage==5.5'
   ```
2. **Apply only the syntax fixers of `futurize --stage1` first** (print function,
   `except E as e`, octal literals, long literals, backticks, `<>`). The code
   keeps running on 2.7 and now parses as Python 3, so every modern tool works.

For a large code base take path 2 and keep path 1 for a first pass. Running
ruff or vulture 2.x on unconverted 2.7 source fails on `print x` and
`except E, e:` and reports nothing, or crashes.

## Baseline

```bash
python -m pytest -q 2>&1 | tail -1 > baseline-tests.txt   # -m adds the cwd; bare pytest needs the package installed or a conftest
pip freeze > baseline-freeze.txt
```

Start production coverage collection in the same PR with
`scripts/coverage_bootstrap.py` (env `DEADCODE_COVERAGE=1`; see
`python-production-coverage.md`, section 1).

## Tool per category

| Category | Tool | Command |
|---|---|---|
| 1. Unused imports, locals | pyflakes, autoflake (2.7 and 3); ruff (py3-parsable) | below |
| 2. Unreachable code | vulture at 100% | `vulture src/ --min-confidence 100` |
| 3. Private symbols | vulture at 60%, `dead` | `vulture src/ --min-confidence 60`, `dead --files 'src/.*'` |
| 4. Whole modules | `git grep` + combined production coverage | `scripts/zero_hit_functions.py` |
| 5. Endpoints, tasks, jobs | `flask routes`, `app.url_map.iter_rules()`, `celery inspect registered`, `app.tasks.keys()`, CronJob YAML | joined against access logs and task counters |
| 6. Dependencies | pip-check-reqs 2.0.4 (2.7), deptry (py3) | `pip-extra-reqs src/`, `deptry .` |
| Proof of life | py-spy | `py-spy dump --pid <pid>`, `py-spy record` |

### 1. Unused imports and locals

```bash
autoflake --check --remove-all-unused-imports --remove-unused-variables \
    --ignore-init-module-imports -r src/
ruff check --select F401,F841 src/          # py3-parsable source
```

Preserve: re-exports in `__init__.py`, names in `__all__`, side-effect imports
(SQLAlchemy model registration, blinker and Django signal hookup, monkeypatches,
Flask blueprint and plugin imports), `try/except ImportError` compatibility
shims. Mark a kept import `# noqa: F401` with a one-line reason.

### 2. Unreachable code

vulture 100% covers code after `return`/`raise`, `if False`, and unused
function arguments. Preserve unused arguments on callbacks, signal handlers and
overridden methods whose signature is fixed by the caller.

### 3. Unreferenced private symbols

```bash
vulture src/ --min-confidence 60 --ignore-decorators '@app.route,@task,@receiver'
git grep -n -w 'export_rows' -- ':!*.pyc'
gh search code 'export_rows' --owner <org>
git log -S 'export_rows' --oneline | head
```

60% means "no reference found in the analyzed files". Run it on the source
tree without `tests/`: a symbol that only tests reference is listed, and that
is correct, it is a candidate (code only tests call is dead code). Preserve anything a
decorator registers (`@app.route`, `@click.command`, `@shared_task`, Jinja
`@app.template_filter`, `@receiver`, pytest fixtures), ORM model attributes,
`__dunder__` methods, abstract-method implementations. Check the defining
module for `getattr(`, `globals()[`, `importlib.import_module(`, `__import__(`
before deleting.

### 4. Whole modules

```bash
git grep -n 'pkg.legacy_export\|legacy_export'
python scripts/zero_hit_functions.py --source src/mypkg \
    --coverage-json api=cov/api.json --coverage-json worker-billing=cov/worker-billing.json \
    --coverage-json cron-reports=cov/cron-reports.json --per-service
```

Not dead while listed in `setup.py`/`pyproject.toml` entry points, Celery
`include=`/`imports`, alembic `env.py`, `INSTALLED_APPS` or other settings
lists, Dockerfile or Procfile commands. Preserve modules only imported by
migrations, modules registered by name in config, and modules that exist only
to be pickled or unpickled.

### 5. Endpoints, tasks and cron jobs

```bash
flask routes
celery -A proj inspect registered
kubectl get cronjobs -A -o custom-columns=NAME:.metadata.name,SCHEDULE:.spec.schedule
```

Join routes against nginx or load-balancer access logs by mapping each
`$request_uri` to its rule template. Join tasks against beat schedules,
CronJob YAML, crontabs and `send_task('name')` literals. The tombstone and
410-flag helpers are in `python-production-coverage.md`.

### 6. Dependencies

```bash
pip-extra-reqs src/                        # 2.7, pip-check-reqs 2.0.4
deptry .                                   # py3, inside the venv
git grep -n 'import_module\|__import__\|postgresql+\|mysql+\|redis://\|amqp://'
grep -n 'pip install\|celery\|gunicorn\|uwsgi\|alembic' Dockerfile Procfile Makefile .github/workflows/*.yml
pipdeptree --reverse --packages <name>
```

Preserve drivers and backends loaded by URL or setting (`psycopg2`,
`mysqlclient`, `gevent`, `eventlet`), CLI tools run from Procfile, CI or
Makefile (`gunicorn`, `celery`, `alembic`). Regenerate the lock (`pip-compile`,
`uv lock`, `poetry lock`) in the same commit. The inventory that works on raw
2.7 source is in `python-tools.md`, "Inventory that works on raw Python 2
source".

## Dynamic-reference checklist, Python spellings

- `getattr(`, `globals()[`, `importlib.import_module(`, `__import__(` with a non-literal or config-driven string
- Celery: `@task(name=...)`, `send_task('...')`, `apply_async` by name, beat schedules
- `url_for('endpoint')`, Jinja helpers, filters, macros and context processors referenced from templates
- `__all__` and `__init__.py` re-exports
- `setup.py` / `pyproject.toml` entry points and plugin registries (`[project.entry-points]`, `pkg_resources`, `importlib.metadata`)
- alembic and Django migrations that import models or helpers
- Pickled class paths in memcached, Redis, Celery results and Flask or Django sessions
- blinker, SQLAlchemy event and Django signal listeners registered only by importing the module
- JSON-RPC, webhook, Flask CLI and Django management command names
- External consumers: other repos, SDKs, partners, mobile clients
- Jobs that run yearly, quarterly or at month end
- Code behind a feature flag that is currently off

## Commit messages, Python examples

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

## Scripts

- `scripts/coverage_bootstrap.py`: starts coverage.py post-fork when
  `DEADCODE_COVERAGE=1`, saves on `atexit`, SIGTERM and a timer, uploads.
  Runs on 2.7 with coverage 5.5 and on 3.x with coverage 7.
- `scripts/zero_hit_functions.py`: joins `coverage json` output with the AST
  of every `def` and prints functions with zero hits, per service and in
  total. Run it under the interpreter that parses the source.
