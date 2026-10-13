# Boundaries: ports and adapters only where they pay

A port is an interface the domain owns and the outside world implements. It earns its
place when it isolates something **external** (the domain cannot run without faking it) or
something with **proven variation** (two implementations selected at runtime today). A
port over one pure implementation is an indirection: more files, same coupling.

## Does this deserve a port?

| The dependency is | Decision | Shape |
|---|---|---|
| I/O: database or ORM session, HTTP client, queue or broker, filesystem, email, metrics registry, env/config service | port | abstract class or `Protocol` in `ports.py`; implementation in `adapters.py`; built in the composition root |
| Two or more real implementations chosen at runtime (env var, config, feature flag) | port | same, one adapter per implementation |
| Clock, randomness, sleep | parameter | `today: date`, `now: Callable[[], datetime]`, `sleep: Callable[[float], None]` with the real one as default in the composition root; no `Clock` ABC |
| A pure helper with one implementation (formatter, `strip_html`, a parser) | parameter or direct call | pass the function when the caller needs to swap it in tests; otherwise just call it |
| A framework object the whole process shares (Flask `app`, SQLAlchemy `Session`, Django settings) | adapters only | the domain receives values and dataclasses, never the session or the request |
| "Might vary someday" | none | write in the PR what would trigger adding it |

The `rf-fx-ports` rule of thumb: the one HTTP rates provider gets a `RatesSource`
protocol because the domain cannot run without faking it; the date is a parameter because
one `date` needs no interface; nothing gets a factory because nothing is constructed in
more than one place.

## Package shape

```
app/billing/
  __init__.py      public API: the use-case functions and the value types callers need
  ports.py         interfaces + value types; imports nothing from the app or from I/O libraries
  domain.py        pure rules (or several modules: rules.py, rendering.py, ...)
  adapters.py      the ONLY module that imports db, models, requests, the ORM session
  service.py       composition root: builds adapters, calls the domain, used by cli/web/workers
```

What the next implementation (a new service, a different database) has to rewrite is the
list of imports in `adapters.py`. Nothing else knows the world exists.

### A port, with its contract in the docstring

```python
# ports.py
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Protocol


@dataclass(frozen=True)
class Publication:
    proc_id: int
    source_url: str
    published_on: date


class PublicationRepository(Protocol):
    """Where publications are written.

    Every method commits on its own. A failed write returns False, never raises: the
    worker answers False with a nack, and the redelivery lands on rows an earlier attempt
    already stored, so writes must tolerate an existing row for the same (proc_id,
    source_url).
    """

    def exists(self, proc_id: int, source_url: str) -> bool: ...

    def add(self, publication: Publication) -> bool: ...


class RatesSource(Protocol):
    def get_rate(self, base: str, quote: str, on: date) -> Decimal: ...
```

The docstring carries what the type cannot: transaction scope, what failure looks like,
idempotency, atomicity ("compare-and-append in the database, not read-modify-write").
Those are the lines the next adapter must honor.

### The adapter

```python
# adapters.py
from app import db
from app.models import ProcPublication

from .ports import Publication


class SqlPublicationRepository:
    def exists(self, proc_id: int, source_url: str) -> bool:
        return db.session.query(ProcPublication.id).filter_by(
            proc_id=proc_id, source_url=source_url
        ).first() is not None

    def add(self, publication: Publication) -> bool:
        try:
            db.session.add(ProcPublication(**publication.__dict__))
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False
```

### The composition root

```python
# service.py
from datetime import date

from . import adapters, domain


def run_partes(today: date | None = None) -> None:
    repo = adapters.SqlPublicationRepository()
    rates = adapters.EcbRates()
    domain.process(repo=repo, rates=rates, today=today or date.today())
```

`date.today()` lives here and in `cli.py`, nowhere in `domain.py`. Tests call
`domain.process(repo=FakeRepo(), rates=FakeRates(...), today=date(2026, 3, 1))`.

### Fakes live in tests

A fake is a plain class in the test module with the same method names; a `Protocol`
accepts it structurally, an ABC needs the fake to subclass it. Fakes record calls
(`self.calls.append(...)`) so a test can assert *which* dates were asked, not only the
output.

## Guard the boundary with a test

Copy `scripts/check_boundaries.py` into `tests/test_package_boundaries.py` and edit
`RULES`:

```python
RULES = {
    "package": "app/billing",
    "forbid": ["db", "app.models", "sqlalchemy", "requests", "prometheus_client"],
    "allow": ["adapters.py", "service.py"],
    "standalone": ["app.billing.domain", "app.billing.ports"],
}
```

It walks the AST (so `from app.models import X` counts as reaching `app.models`) and
imports each `standalone` module in a bare interpreter, which catches cycles that only
close in one import order. When adding a dev dependency is acceptable, `import-linter`
does the same with declarative contracts:

```ini
[importlinter]
root_package = app

[importlinter:contract:billing-domain-is-pure]
name = billing domain does not reach the data layer
type = forbidden
source_modules = app.billing.domain, app.billing.ports
forbidden_modules = app.db, app.models, sqlalchemy, requests
```

## Sequencing the extraction (one commit each)

1. `test:` characterize the use case through its current entry point (outputs and side
   effects, including what it writes and what it mutates).
2. `refactor:` extract the pure parts into functions that take values (Split Phase).
3. `refactor:` introduce `ports.py` with the interface the pure part needs, written from
   the pure part's point of view (what it needs, not what the ORM offers).
4. `refactor:` move the I/O code into `adapters.py` implementing the port; the old module
   keeps re-exports so callers and `mock.patch` targets survive this commit.
5. `refactor:` inject the port and the clock into the use case (expand: keyword arguments
   with defaults built lazily).
6. `test:` rewrite the tests against the seam with fakes; delete the monkeypatches.
7. `refactor:` require the dependencies at the boundary (contract: remove the defaults
   from the domain; the composition root provides them).
8. `refactor:` remove the re-exports; add the boundary test.

## Pure core, imperative shell

The domain returns decisions (`Publication` to write, `Event` to emit, `Nack`), the shell
performs them. A function that returns "what to do" is testable with equality on
dataclasses; one that does it needs fakes. Push I/O to the edges until the middle is
plain functions over plain data.

## Signs you went too far

- An ABC with one implementation and nothing external behind it.
- `ports.py` importing from `adapters.py` or from the ORM.
- A factory that builds one thing in one place.
- Tests that import the adapter to test the domain.
- A `Clock` class with a single method `now()` and one implementation.
- More modules than functions.
