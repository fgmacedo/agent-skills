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

`pytest-quarantine` 2.0 (2019) supports 2.7 and pytest 4.6, so the same ratchet works on both legs. There is no plugin named "pytest-ratchet". GitHub Actions `continue-on-error: true` is how an allowed-to-fail job is declared; it renders poorly in the PR checks list, so publish the pass count as a job summary.

Dead or stale, do not recommend: `caniusepython3` (unmaintained since 2021), `pylint --py3k` (removed in pylint 2.11; only pylint 1.9.5 under 2.7 still has it), `unicode-nazi` (2011), `flake8-2020` (archived, only checks `sys.version` slicing), Bowler (archived 2025).

## 6. Framework chain that supports both interpreters

The single-source window must stay inside these pins. Upgrade to them on the py2 side first, one package per PR, each deployed, so the cutover changes only the interpreter.

| Package | Last with 2.7 | First without |
|---|---|---|
| Flask | 1.1.4 (pins Werkzeug<2, Jinja2<3, itsdangerous<2, click<8) | 2.0 |
| Werkzeug | 1.0.1 | 2.0 |
| Jinja2 | 2.11.3 | 3.0 |
| MarkupSafe | 1.1.1 (py2 side); pin 2.0.1 on the py3 side, 2.1 removed `soft_unicode` which Jinja2 2.11 imports | 2.0 |
| itsdangerous | 1.1.0 | 2.0 |
| click | 7.1.2 | 8.0 |
| SQLAlchemy | 1.4.54 | 2.0 |
| Flask-SQLAlchemy | 2.5.1 | 3.0 |
| alembic | 1.4.3 | 1.5 (not re-verified) |
| psycopg2 | 2.8.6 | 2.9 |
| mysqlclient (replaces MySQL-python, same `MySQLdb` import) | 1.4.6 | 2.0 |
| PyMySQL | 0.10.1 (not re-verified) | 1.0 |
| requests | 2.27.1 | 2.28 |
| redis | 3.5.3 | 4.0 |
| celery | 4.4.7 | 5.0 |
| gunicorn | 19.10.0 | 20.0 |
| gevent | 22.10.x | 23 |
| marshmallow | 2.21.0 | 3.0 |
| sentry-sdk | 1.45.x | 2.0 |
| boto3/botocore | releases before 2021-07-15 | after |
| jaeger-client | 4.4.0 | 4.5 |
| pandas / numpy | 0.24.2 / 1.16.6 | 0.25 / 1.17 |

Whether Flask 1.1.4 + Werkzeug 1.0.1 + Jinja2 2.11.3 import cleanly on 3.12+ is not documented anywhere. Measure it (spike in Phase 0). Flask 1.1.4 also carries open CVEs, which argues for a short window.

## 7. Archived or dead dependencies

When a dependency's upstream is archived (example: Flask-Potion, archived 2025-04, last release 0.16.0 in 2019, pure Python, classifiers 2.7 and 3.4 to 3.6):

1. Check whether the pinned release already imports on the target interpreter with the window chain. Pure-Python packages from the 2.7 era often do.
2. Search the fork network for recent commits (`https://github.com/<org>/<repo>/forks?sort_by=last_updated`). A fork may already carry the fix for the newer framework (for Potion: `Zenysis/potion`, a 12-line Werkzeug 3 / Flask 2.3 patch, based on 0.15).
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
