# Choosing the target Python version

Facts as of 2026-10-12. Re-check release status at https://devguide.python.org/versions/ before deciding.

## The cost question

Porting 2.7 straight to the newest 3.x costs almost the same as porting to an old 3.x. The dominant work is identical for every target: bytes/str boundaries, true division, lazy iterators and dict views, ordering of mixed types, `__hash__`/`__bool__`/`__truediv__`, pickled data, and test snapshots that depend on `repr`, hash order or `random`. The extra cost of a newer target is a short, mechanical list of stdlib removals (below), all caught by `ruff --select UP` or a grep. Expect hours to days for that delta, not weeks.

What a newer target does change:
- Converter tooling (`futurize`, `modernize`, `2to3`) needs `lib2to3`, removed in 3.13. Run the converter under 2.7 or 3.12. This constrains the converter machine, never the target.
- The framework chain that still supports 2.7 may not run on the newest 3.x, and this is the one factor that can force an old target. Measured 2026-10-12: the Flask chain (Flask 1.1.4, Werkzeug 1.0.1, Jinja2 2.11.3, MarkupSafe 2.0.1, SQLAlchemy 1.4.54, Flask-SQLAlchemy 2.5.1) runs on 3.13; Django 1.11.29 with DRF 3.9.4 runs on 3.9 and fails to import on 3.10+. Measure your own chain with a one-day spike (build the py3 image with the py2-compatible chain pinned, import it, serve one request). If the chain fails on the target, cut over on the newest version it runs on and upgrade the framework as the next project. One variable at a time. `references/tooling.md`, section 6, has the per-stack ceilings and the Django ladder.
- On 3.14, `except X, e:` parses again (PEP 758) with the meaning `except (X, e):`. Unconverted handlers compile and fail only when an exception arrives. Gate syntax with ruff or a 3.13 interpreter, not with `compileall` on 3.14.

## Per-version table

| Version | Released | EOL | Status (Oct 2026) | Removals that bite a 2.7 port | Notable |
|---|---|---|---|---|---|
| 3.8 | 2019-10 | 2024-10 | EOL | `time.clock`, `cgi.escape`, `cgi.parse_qs`, `platform.linux_distribution` | macOS `spawn` default |
| 3.9 | 2020-10 | 2025-10 | EOL | `base64.encodestring/decodestring`, `array.tostring`, `ElementTree.getchildren`, `Thread.isAlive`, `json.loads(encoding=)` | `zoneinfo`, `str.removeprefix` |
| 3.10 | 2021-10 | 2026-10 | EOL | `collections.Mapping` and other ABC aliases, asyncio `loop=` | `match`, `-X warn_default_encoding` |
| 3.11 | 2022-10 | 2027-10 | security only | `asyncio.coroutine`, `binhex`, `inspect.getargspec`, `gettext.l*` | 10 to 60% faster than 3.10; `tomllib`, `ExceptionGroup` |
| 3.12 | 2023-10 | 2028-10 | security only | `distutils`, `imp`, `asyncore`/`asynchat`/`smtpd`, unittest aliases (`assertEquals`...), `configparser.SafeConfigParser`/`readfp`, `ssl.wrap_socket`; invalid escapes become `SyntaxWarning`; venvs no longer preinstall setuptools | comprehension inlining; PEP 695/701 |
| 3.13 | 2024-10 | 2029-10 | security only | PEP 594 modules (`cgi`, `cgitb`, `crypt`, `imghdr`, `pipes`, `telnetlib`, `uu`, `nntplib`, ...), `lib2to3`/`2to3`, `locale.resetlocale`, `typing.io`/`typing.re`, `unittest.makeSuite` | experimental free-threading and JIT |
| 3.14 | 2025-10 | 2030-10 | bugfix | `ast.Num`/`Str`/`Bytes`, `pkgutil.find_loader`/`get_loader`, `asyncio.get_event_loop()` raises without a loop, `urllib.request.URLopener`, `sqlite3.version` | `multiprocessing` default start method `forkserver` on Linux; `tarfile` default filter `data`; PEP 758; PEP 649 lazy annotations; `functools.partial` as method descriptor |
| 3.15 | 2026-10 | 2031-10 | just released | not surveyed | UTF-8 mode default (PEP 686) |

## Ecosystem floor (checked on PyPI, 2026-10-12)

- SQLAlchemy 2.1 requires >= 3.11. numpy 2.5 requires >= 3.12. Flask 3.1 and Werkzeug 3.1 require >= 3.9. Alembic 1.20, psycopg 3.3, mysqlclient 2.3, redis-py 8, gunicorn 26, pytest 9 all require >= 3.10.
- gunicorn and Celery classifiers stop at 3.13; they are pure Python and likely fine on 3.14, but verify with your suite.
- `python-future` 1.0.0 (2024-02) declares itself finished; `futurize` crashes on 3.13+. `six` 1.17 (2024-12) works everywhere.
- Docker images `python:3.12-slim`, `3.13-slim`, `3.14-slim` all exist.

## Decision rule

1. Exclude every version that is EOL or will be within a year of your cutover date.
2. Exclude versions below the floor of the dependencies you intend to run after the port (SQLAlchemy 2.1 means >= 3.11).
   Exception: when the py2-compatible framework chain has a ceiling below that floor (Django 1.11 stops at 3.9), the cutover target is the ceiling, even if EOL, and the framework ladder follows on the py3 side. Rule 1 then applies to the end of the ladder, not to the cutover.
3. Among the rest, prefer the newest with full wheel coverage for your dependency set and the longest support window. Treat the next version as a go/no-go once the suite is green: if CI passes on it, take it and skip an upgrade cycle.
4. Pin the choice everywhere at once: `requires-python`, ruff `target-version`, `pyupgrade --pyXY-plus`, Dockerfile base image, CI matrix, and the project's agent instructions file.
5. Run the py3 suite with `-W error::DeprecationWarning` so the next version's removals show up now.

In October 2026 the rule yields 3.13 for Flask and most non-framework code bases, with 3.14 as the go/no-go candidate; for Django 1.11 code bases it yields 3.9 at cutover and 3.13 at the end of the ladder.
