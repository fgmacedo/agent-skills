# Tooling for a Python 2 to 3 port

Verified against PyPI, GitHub and docs on 2026-10-12. Each tool says whether it reads Python 2 syntax; most modern tools do not.

## 1. Running Python 2.7 in 2026

| Option | Status | Notes |
|---|---|---|
| Docker `python:2.7.18-slim` (also `-buster`, `-alpine3.11`) | Available, frozen since 2020-04-20, multi-arch incl. arm64 | No OS security updates; use only for the converter and the py2 CI leg. https://hub.docker.com/_/python |
| pyenv `2.7.18` | Builds, with friction | Needs OpenSSL 1.1 and manual `CFLAGS`/`LDFLAGS` on macOS arm64. https://github.com/pyenv/pyenv/wiki/Common-build-problems |
| uv | Refuses Python 2 | `uv python install 2.7` is not supported; uv skips 2.x during discovery. |

Last tool versions that run under 2.7 (pin them in the py2 environment):

| Package | Last with 2.7 | First without |
|---|---|---|
| pip | 20.3.4 | 21.0 |
| setuptools | 44.1.1 | 45.0 |
| virtualenv | runs on 2.7 until 20.15; creates 2.7 envs until 20.21 | 20.22 (2023-04) |
| tox | pin `requires = virtualenv<20.22`; some projects pin `tox<4` | |
| pytest | 4.6.11 | 5.0 |
| pytest-cov | 2.12.1 | 3.0 |
| pytest-xdist | 1.34.0 | 2.0 |
| coverage | 5.5 | 6.0 |
| mock | 3.0.5 | 4.0 |
| pyflakes | 2.4.0 | 2.5 |
| pylint | 1.9.5 | 2.0 |
| vulture | 1.6 | 2.0 |
| isort | 4.3.21 | 5.0 (runs on py3, still formats py2 code) |
| black | never ran on 2.7; formatted py2 code until 21.x | 22.x removed py2 formatting |

## 2. Converters

### `futurize` (python-future)

- Stage 1 (`futurize --stage1 -w -n --no-diffs PKG`) applies the safe fixers only and adds `from __future__ import absolute_import, division, print_function`. No runtime dependency. Output still runs on 2.7. This is the pass to use.
- Stage 2 (`--stage2`) adds `from builtins import ...`, `future.utils` and `standard_library.install_aliases()`, creating a runtime dependency on `future`. Do not use it: `future` 1.0.0 (2024-02) declares the project finished, its classifiers stop at 3.12, and `futurize` itself fails on 3.13+ with `No module named 'lib2to3'`.
- Run it under 2.7 (Docker) or under 3.12 at the latest.
- Useful flags: `-f FIXER` / `-x FIXER` to select or exclude fixers, `-l` to list them, `-j N` for parallel, `-u` for `unicode_literals` (do not use globally, see `catalog.md`).
- Run the fixers you want one at a time per directory and commit each separately, so review and revert stay cheap. Suggested order (all behaviour-preserving on 2.7): `fix_print_with_import`, `fix_except`, `fix_numliterals`, `fix_repr`, `fix_ne`, `fix_raise`, `fix_tuple_params`, `fix_exec`, `fix_has_key`, `fix_next_call`, `fix_absolute_import`.
- Docs: https://python-future.org/automatic_conversion.html and https://python-future.org/futurize_cheatsheet.html

### `modernize` (python-modernize)

- Emits `six`-based single-source code. Last release 0.8.0 (2020-09), runs on 3.6+ through `fissix` (a `lib2to3` fork, last release 2024-04, needs 3.8+). Unmaintained but functional; pin `fissix`.
- `modernize --enforce PKG` exits non-zero when any fixer would apply. Usable as a CI gate against new Python 2 idioms once the codebase is clean.
- `--no-six`, `--six-unicode`, `--future-unicode`, `-f`/`-x` as in futurize.
- https://github.com/PyCQA/modernize

### `2to3` / `lib2to3`

One-way conversion, unsuitable for a single-source window. Removed from the stdlib in 3.13. The de-facto replacement is `fissix`. Use only for throwaway diagnostics ("what would change").

### `six`

1.17.0 (2024-12), supports 2.7 and 3.x. The shim to use during the window: `six.string_types`, `six.text_type`, `six.binary_type`, `six.iteritems`, `six.moves.urllib`, `six.moves.cStringIO`, `six.add_metaclass`, `six.reraise`, `six.ensure_text`/`ensure_binary`/`ensure_str`. `pyupgrade` and ruff remove it after the cutover.

## 3. Post-cutover rewriters (Python 3 parser only)

These cannot read Python 2 syntax. Use them once the code parses as py3.

- `pyupgrade --py313-plus` (current 3.22, needs 3.11+ to run): rewrites `six` calls, `u''` prefixes, `from __future__` lines, `io.open`, `IOError` to `OSError`, `super()`, `%`-format and `.format` to f-strings where safe. https://github.com/asottile/pyupgrade
- `ruff check --select UP,W605 --target-version py313 --fix`: same family of rewrites plus invalid-escape fixes. Ruff's parser is py3-only at every target version. Default target is now 3.10, so set it explicitly.
- `vermin -t=2.7 -t=3 PKG` (1.8, 2025-11): reports the minimum interpreter each file needs. Runs on py3, reads py3-parseable code.
- LibCST (needs 3.9+, parses 3.0 to 3.15 only): for custom codemods after the port. Bowler is archived; its README points to LibCST.

## 4. Interpreter flags that find what grep cannot

Python 2.7 (https://docs.python.org/2.7/using/cmdline.html):

```bash
python2 -3 -Werror::DeprecationWarning -Qwarnall -R -tt -m pytest tests/
```

- `-3`: `DeprecationWarning` for Python 3 incompatibilities (`dict.has_key`, `cmp`, `sorted(cmp=)`, `__getslice__`, dict iteration order assumptions, ...). Warnings are hidden by default on 2.7, so pair with `-Werror` or `-Wd`.
- `-Qwarnall`: warns on every `/` with int operands. The only way to enumerate integer division sites.
- `-R`: hash randomization, exposes tests that depend on dict/set order.
- `-tt`: mixed tabs and spaces become errors.
- `-bb` on 2.7 only covers `unicode` vs `bytearray`; it does not catch `str` vs `unicode`.

Python 3:

```bash
python3 -bb -X dev -X warn_default_encoding -W error::DeprecationWarning -m pytest tests/
```

- `-bb`: `bytes == str` comparisons raise instead of silently returning `False`.
- `-X warn_default_encoding` (3.10+): warns on `open()` without `encoding=`.
- `-W error::DeprecationWarning`: surfaces the next version's removals now.
- `-X dev`: extra checks (unclosed files, `ResourceWarning`).
- `PYTHONHASHSEED=random` (default) plus `pytest-randomly` to shake out order dependence.

## 5. Regression gates during the window

| Gate | Tool | Fails when |
|---|---|---|
| New py2 idioms | `scripts/py2ism_census.py SRC --check baseline.json` | any non-informational category grows |
| Parseable on target | `scripts/py3_compile_gate.sh -p python3.13 SRC` | a file fails `compileall` (`-w` also fails on `SyntaxWarning`) |
| Importable on target | `scripts/py3_compile_gate.sh -p python3.13 -t tests SRC` | `pytest --collect-only` fails |
| py3 test ratchet | `pytest-quarantine` or an allowlist of known failures with `xfail_strict = true` | a known-passing test fails, or a listed test passes without being removed from the list |
| py2 runtime idioms | `python2 -3 -Werror` on the py2 CI leg | a `DeprecationWarning` fires |
| Single source (optional) | `modernize --enforce` | any fixer would change a file |

| Undefined names on target | `pyflakes SRC` or `ruff check --select F821 SRC` under the target interpreter | `unicode`, `basestring`, `xrange`, `long`, `unichr`, `reduce` on any line, covered or not |
| Uncovered risk lines | `python3 scripts/uncovered_risk_lines.py coverage.json` | printed list is the manual review list; the gate is that it is reviewed, not empty |
| Coverage floor per leg | `coverage report --fail-under=N` on both legs, `N` raised in every PR until 100 | a leg drops below its floor |

`pytest-quarantine` 2.0 (2019) supports 2.7 and pytest 4.6, so the same ratchet works on both legs. There is no plugin named "pytest-ratchet". GitHub Actions `continue-on-error: true` is how an allowed-to-fail job is declared; it renders poorly in the PR checks list, so publish the pass count as a job summary.

### Coverage to 100% on both legs

Single-source code has lines only one interpreter runs. coverage.py expands environment variables in `.coveragerc` (`${VAR-default}` syntax works on 5.5 and 7.x), so one file serves both legs:

```ini
[report]
fail_under = 100
show_missing = True
exclude_lines =
    pragma: no cover
    pragma: py${COVERAGE_EXCLUDE_PY-0} only
    raise NotImplementedError
    def __repr__
```

Tag the line `# pragma: py2 only` or `# pragma: py3 only`. The 2.7 job sets `COVERAGE_EXCLUDE_PY=3`, the target job sets `COVERAGE_EXCLUDE_PY=2`; unset expands to `py0 only` and excludes nothing. `coverage-conditional-plugin` does the same with less typing but is py3-only, so it cannot serve while the 2.7 leg exists. When diffing executed-line sets between legs, expect about fifty lines each way of tooling noise (coverage 5.5 and 7.x attribute `def` lines and docstrings differently); filter those before reading the diff.

### `-W error::DeprecationWarning` with the last-2.7 chain

The flag is unreachable on 3.12+ without filters: Werkzeug 1.0.1 uses `ast.Str` (most tests fail at routing), itsdangerous 1.1.0 calls `utcfromtimestamp`, SQLAlchemy 1.4 raises `RemovedIn20Warning` (a `DeprecationWarning` subclass) through its "uber warning", and Flask-SQLAlchemy 2.5.1 raises `FSADeprecationWarning` unless `SQLALCHEMY_TRACK_MODIFICATIONS` is set explicitly. pytest's `filterwarnings` ini entries take precedence over python's `-W` (verified on pytest 4.6.11 and 8.x), so keep the flag on the command line and scope each filter to the third-party line that raises it:

```ini
[pytest]
filterwarnings =
    ignore:ast\.Str is deprecated:DeprecationWarning:werkzeug\.routing
    ignore:Attribute s is deprecated:DeprecationWarning
    ignore:Constant\.__init__:DeprecationWarning
    ignore:datetime\.datetime\.utcfromtimestamp\(\) is deprecated:DeprecationWarning:itsdangerous\.timed
    ignore::sqlalchemy.exc.RemovedIn20Warning
```

Never `ignore::DeprecationWarning` unscoped: it hides the removals in your own code. Python 3.14 is out of reach for this chain because `ast.Str` is removed there; it becomes a go/no-go after the Phase 6 framework upgrade.

Dead or stale, do not recommend: `caniusepython3` (unmaintained since 2021), `pylint --py3k` (removed in pylint 2.11; only pylint 1.9.5 under 2.7 still has it), `unicode-nazi` (2011), `flake8-2020` (archived, only checks `sys.version` slicing), Bowler (archived 2025).

## 6. Framework chain that supports both interpreters

The single-source window must stay inside these pins. Upgrade to them on the py2 side first, one package per PR, each deployed, so the cutover changes only the interpreter. "Measured" rows were smoke-tested on 2026-10-12 with `uv run --python X.Y --with pkg==ver` (import, app setup, one request, one ORM query); everything else comes from PyPI metadata and may differ from what actually imports.

### Flask stack

| Package | Last with 2.7 | First without | Highest 3.x the last-2.7 release runs on |
|---|---|---|---|
| Flask | 1.1.4 (pins Werkzeug<2, Jinja2<3, itsdangerous<2, click<8) | 2.0 | 3.13, measured (with the pins below) |
| Werkzeug | 1.0.1 | 2.0 | 3.13, measured |
| Jinja2 | 2.11.3 | 3.0 | 3.13, measured |
| MarkupSafe | 1.1.1 (py2 side); pin 2.0.1 on the py3 side, 2.1 removed `soft_unicode` which Jinja2 2.11 imports | 2.0 | 3.13, measured |
| itsdangerous | 1.1.0 | 2.0 | 3.13, measured |
| click | 7.1.2 | 8.0 | 3.13, measured |
| Flask-SQLAlchemy | 2.5.1 | 3.0 | 3.13, measured. Two incompatibilities with SQLAlchemy 1.4.54: `scoped_session.get_bind` forwards a `bind` kwarg that `SignallingSession.get_bind` rejects (call `get_bind` on `session()`, not on the proxy); a secondary-table `DELETE` of a missing row raises `StaleDataError` because 1.4 checks rowcount where 1.3 did not, and the collection remove event fires before `list.remove` raises `ValueError`, so "remove then swallow `ValueError`" code still queues the delete (check membership first). Set `SQLALCHEMY_TRACK_MODIFICATIONS` explicitly or `FSADeprecationWarning` fires |
| Flask-Principal | 0.4.0 | none | needs `blinker==1.4`; newer blinker removed `_utilities.contextmanager` |
| blinker | 1.4 (with Flask-Principal); 1.9 otherwise | | |
| aniso8601 | 9.0.1 | 10.0 changed date parsing (a test-visible difference, pin it) | |
| Flask-RESTful | 0.3.10 | none yet (still declares 2.7) | classifiers to 3.8 |
| flask-restx | 0.5.1 | 1.0 | classifiers to 3.8 |
| Flask-Login | 0.5.0 | 0.6 | classifiers to 3.7 |
| Flask-WTF / WTForms | 0.14.3 / 2.3.3 | 1.0 / 3.0 | classifiers to 3.8 |
| Flask-Cors | 3.0.10 | 4.0 | classifiers to 3.7 |
| Flask-Migrate | 2.7.0 | 3.0 | follows alembic |
| Flask-Caching | none (1.x already requires >= 3.5); stay on Flask-Cache 0.13 or vendor | | |
| Flask-Admin | none with 2.7 after 1.5.x (not re-verified) | | |

### Django stack

| Package | Last with 2.7 | First without | Highest 3.x the last-2.7 release runs on |
|---|---|---|---|
| Django | 1.11.29 (LTS, 2020-03) | 2.0 | **3.9, measured.** 3.10 fails at import (`from collections import Iterator` in `db/models/sql/query.py`); 3.12+ fails earlier (`django.utils.six.moves`) |
| djangorestframework | 3.9.4 | 3.10 | 3.9, measured with Django 1.11.29 |
| django-filter | 1.1.0 | 2.0 | classifiers to 3.6 |
| drf-yasg | 1.17.1 | 1.20 | classifiers to 3.8 |
| django-cors-headers | 3.0.0 | 3.1 | classifiers to 3.7 |
| django-storages | 1.9.1 | 1.10 | classifiers to 3.8 |
| django-debug-toolbar | 1.11.1 | 2.0 | classifiers to 3.7 |
| pytest-django | 3.10.0 | 4.0 | classifiers to 3.8 |
| factory_boy | 2.12.0 | 3.0 | classifiers to 3.7 |
| django-redis | none (4.11 already requires >= 3.5); use `django.core.cache` with `redis` 3.5.3 or vendor 4.10 | | |
| channels | none (2.x is py3 only) | | |

The Django ceiling changes the plan. Django 1.11 cannot straddle 2.7 and anything newer than 3.9, and 3.9 is EOL. The route that keeps one variable per step: cut over on 3.9 with Django 1.11.29, then upgrade Django and Python alternately on the py3 side, each a deployed step with its own soak: Django 2.2 (3.5 to 3.9), Django 3.2 (3.6 to 3.10) then Python 3.10, Django 4.2 (3.8 to 3.12) then Python 3.12, Django 5.2 (3.10 to 3.13) then Python 3.13. Each Django LTS jump has its own deprecation list; `python -W error::RemovedInDjangoXXWarning` on the previous LTS is the gate, the same ratchet shape as the interpreter. Budget calendar for four soaks, not for the code.

### Servers, task queues, other frameworks

| Package | Last with 2.7 | First without | Notes |
|---|---|---|---|
| gunicorn | 19.10.0 | 20.0 | classifiers to 3.7; pure Python |
| uWSGI | 2.0.x (C, builds against either interpreter) | | build two images from the same version |
| celery / kombu / billiard | 4.4.7 / 4.6.11 / 3.6.4 | 5.0 | classifiers to 3.8 |
| tornado | 5.1.1 | 6.0 | classifiers to 3.7; 6.0 removed the `tornado.gen` Python 2 paths and is asyncio-only |
| Pyramid | 1.10.8 | 2.0 | classifiers to 3.9 |
| Twisted | 20.3.0 | 21.2 | classifiers to 3.7 |
| aiohttp, FastAPI, Starlette, channels | py3 only | | out of the window; adopt after the cutover |

### Shared libraries

| Package | Last with 2.7 | First without |
|---|---|---|
| SQLAlchemy | 1.4.54 | 2.0 |
| alembic | 1.4.3 | 1.5 (not re-verified) |
| psycopg2 | 2.8.6 | 2.9 |
| mysqlclient (replaces MySQL-python, same `MySQLdb` import) | 1.4.6 | 2.0 |
| PyMySQL | 0.10.1 (not re-verified) | 1.0 |
| pymongo | 3.13.0 (classifiers to 3.11) | 4.0 |
| mongoengine | 0.19.1 | 0.20 |
| requests | 2.27.1 | 2.28 |
| redis | 3.5.3 | 4.0 |
| gevent | 22.10.x (not verified on 3.12+) | 23 |
| eventlet | 0.30.2 (2021; not verified on 3.12+, confirm in the spike) | 0.31 |
| marshmallow | 2.21.0 | 3.0 |
| lxml | 4.9.4 (wheels to 3.12) | 5.1 |
| Pillow | 6.2.2 | 7.0 |
| sentry-sdk | 1.45.x | 2.0 |
| boto3/botocore | releases before 2021-07-15 | after |
| jaeger-client | 4.4.0 | 4.5 |
| Sphinx | 1.8.6 | 2.0 |
| pandas / numpy | 0.24.2 / 1.16.6 (no wheels for 3.12+; split pin by marker) | 0.25 / 1.17 |

Classifiers are an upper bound on what the maintainers tested, never on what imports. The Flask chain declares 3.8 at most and runs on 3.13; Django 1.11 declares 3.7 and runs on 3.9. Measure your own chain in the Phase 0 spike. Flask 1.1.4 and Django 1.11 both carry open CVEs, which argues for a short window.

Wheel check for the target before building the spike image:

```bash
pip download --only-binary=:all: --python-version 313 --platform manylinux2014_x86_64 \
    --no-deps -d /tmp/wheels -r requirements.txt
```

Packages that fail here need a source build in the image (compiler and headers, slower builds) or a split pin:

```
pandas==0.24.2; python_version < "3"
pandas==2.3.*; python_version >= "3"
```

With a split pin the code must use only the API subset both versions share, and the outputs of that code need golden tests (exports, aggregations), because the two versions can differ in defaults (dtype inference, `sort` behaviour, rounding).

## 7. Archived or dead dependencies

When a dependency's upstream is archived (typical case: a pure-Python REST or serialization layer whose last release predates 2020 and whose classifiers stop at 3.6):

1. Check whether the pinned release already imports on the target interpreter with the window chain. Pure-Python packages from the 2.7 era often do.
2. Search the fork network for recent commits (`https://github.com/<org>/<repo>/forks?sort_by=last_updated`). A fork may already carry the fix for the newer framework; these patches are usually a few lines against the framework's import paths.
3. Fork into your org, publish to your index with a `+yourorg.N` local version, pin it. Keep the fork single-source until the cutover, then apply the framework patches.
4. Replacement (another REST layer) is a separate project; count the call sites before proposing it.

## 8. Sources

- Python 3.8 porting HOWTO (the last full version): https://docs.python.org/3.8/howto/pyporting.html
- Current HOWTO (pointer page since 3.11): https://docs.python.org/3/howto/pyporting.html
- Conservative Python 3 Porting Guide (Red Hat): https://portingguide.readthedocs.io/en/latest/
- python-future cheat sheet: https://python-future.org/compatible_idioms.html
- pytest compatibility: https://docs.pytest.org/en/stable/backwards-compatibility.html
- coverage changelog: https://coverage.readthedocs.io/en/latest/changes.html
- virtualenv changelog: https://virtualenv.pypa.io/en/latest/changelog.html
- python-future on 3.13: https://aur.archlinux.org/packages/python-future
