# Pythonic: what the result should read like

"Modern Python" is the data model and the standard library doing the work the code used to
do by hand (Ramalho, *Fluent Python*). The checklist pairs the Java-flavored shape with the
idiomatic one and names what changes in behavior when you switch, because every row is a
structure change that can quietly become a behavior change. Pin first (`safety-net.md`),
switch in its own commit, keep the old behavior unless a behavior commit changes it on
purpose.

## Checklist

| Java-flavored | Idiomatic | Behavior changes when |
|---|---|---|
| Class with an N-argument `__init__` that only stores fields, plus `to_dict` | `@dataclass` (`frozen=True` when nothing mutates it; `slots=True` when there are many instances) | `__eq__` becomes value-based and `__hash__` disappears unless frozen; `repr` now prints every field (secrets in logs); field order is the constructor order |
| `get_x()` / `set_x(v)` | plain attributes; `@property` only when reading computes or writing validates | every `obj.get_x()` call site changes; a property removes the parentheses everywhere |
| `STATUS_OK = "ok"` constants compared with `==` | `class Status(StrEnum)` with the same values | `str(member)` and f-strings print `Status.OK` for a plain `Enum` or `(str, Enum)` on 3.12; `StrEnum` or `.value` keeps `"ok"`; `Status("x")` raises `ValueError` where the string code just passed through |
| `for i in range(len(xs)): xs[i]` | `for x in xs`, `enumerate(xs)`, `zip(a, b)` | none, unless the body mutates `xs` or reads `xs[i+1]` |
| Accumulator loops building a list or dict | comprehension, generator expression, `dict(zip(...))`, `collections.Counter` | `Counter.most_common()` reorders; a comprehension evaluates eagerly where a loop may have stopped early; `sum(genexpr)` of nothing is `0`, not `0.0` |
| `if k in d: d[k] += 1 else: d[k] = 1` | `d[k] = d.get(k, 0) + 1`, `defaultdict(int)`, `Counter` | `defaultdict` creates keys on read; a `Counter` prints differently and `==` ignores zero counts |
| `f = open(p); try: ... finally: f.close()` | `with open(p, encoding="utf-8") as f:` (always pass `encoding`) | adding `encoding=` where it was missing changes decoding on non-UTF-8 locales |
| `os.path.join(a, "b" + os.sep + c)` | `Path(a) / "b" / c`; `Path.read_text`, `.exists()`, `.glob()` | `str(path)` normalizes `./` and trailing slashes; functions that received `str` now get `Path` unless you convert at the boundary |
| `"%s - %s" % (a, b)`, `"{}".format(a)` | f-strings, except inside `logging` calls (`log.info("x=%s", x)` defers formatting) | `%-30s` and `%10.2f` have f-string equivalents (`{a:<30}`, `{b:>10.2f}`); `%s` of `None` and f-string of `None` agree; `%d` truncates floats, `{x:d}` raises |
| `if isinstance(x, A): ... elif isinstance(x, B):` over a closed set | `match x: case A(): ...` (3.10+) or a method on each class | `match` with class patterns uses `isinstance` too; guard order still matters |
| Dispatch by `if name == "a": do_a() elif ...` | `HANDLERS: dict[str, Callable[..., T]]` and one lookup | unknown key raises `KeyError` where the ladder fell through silently |
| Manual iterator class with `has_next()`/`next()` | a generator function (`yield`), `itertools` | a generator is single-pass; callers that iterate twice see an empty second pass |
| Returning a list that the caller filters again | return an iterator or a generator, or pass the predicate | laziness changes when exceptions surface |
| `try: v = d[k] except KeyError: v = default` | `d.get(k, default)`, `d.setdefault`, `dict.pop(k, None)` | `get` does not distinguish a missing key from a stored `None` |
| Checking `len(xs) == 0`, `xs == []` | `if not xs:` | `if not xs` also treats `0`, `""`, `None` as empty: `if not amount` makes `0` "missing"; use `is None` when zero is a value |
| Flags that select behavior (`render(rows, as_csv=True)`) | two functions, or a table of renderers | none |
| Abstract base class with one subclass | a function parameter or a `Protocol` the caller declares | none |
| Static-method holders (`class Utils:` with `@staticmethod`s) | module-level functions | import paths change for callers (`Utils.f` → `module.f`) |
| `__init__` doing I/O (opening files, querying) | construct with values; an `@classmethod` `from_file(...)` does the I/O | none if every caller used the same path |
| `global counter` | pass the state in; a small class when it has invariants | none |
| Nested functions reaching outer mutable state | explicit parameters | none |
| Timestamps with `datetime.now()` (naive) | `datetime.now(tz=timezone.utc)` and `date` parameters passed in | naive and aware datetimes do not compare; formatting adds `+00:00` |
| Money in `float` | `Decimal` with one explicit rounding policy | numbers change (`round(2.675, 2)` is `2.67`; `int(x*100+0.5)/100` truncates negatives toward zero); never switch in a structure commit |
| Mutable default argument (`def f(xs=[])`) | `xs: list | None = None` and `xs = [] if xs is None else xs` | the shared list was state; something may have depended on it |
| Bare `except:` | `except Exception:` and the narrowest type the handler can handle | bare `except` also swallows `KeyboardInterrupt` and `SystemExit`; a narrower clause lets errors through that were silenced: a behavior change, pin it |
| `type(x) == T` | `isinstance(x, T)` | subclasses now match |
| Sorting with `cmp` or key chains by hand | `sorted(xs, key=attrgetter("a", "b"))`, `functools.cmp_to_key` | stability and ties |
| String building with `+=` in loops | `"".join(parts)`, `io.StringIO` | none |
| `dict` as a record with string keys | `TypedDict` (typing only) or a dataclass | a dataclass rejects unknown keys and missing fields at construction |
| `__eq__` without `__hash__` | `@dataclass(frozen=True)` or define both | see dataclass row |

## Data model: let objects behave like the built-ins

A class that wraps a sequence should implement `__len__`, `__getitem__`, `__iter__`,
`__contains__` so `len`, slicing, `for` and `in` work; one that wraps a number implements
`__add__`, `__eq__`, `__hash__`, `__format__`; one that owns a resource implements
`__enter__`/`__exit__` (or uses `contextlib.contextmanager`). `__repr__` for debugging,
`__str__` only when there is a user-facing rendering. `functools.total_ordering` for
comparisons, `functools.cached_property` for expensive attributes.

## Functions and typing

- Keyword-only parameters (`*,`) for booleans and policies; positional-only (`/`) rarely.
- Type hints on every public function; `Protocol` for "anything with `get_rate`"; `Callable`
  for strategies; `TypeAlias`/`type` for repeated shapes.
- `functools.partial` to fix arguments, not a wrapper class.
- Decorators with `functools.wraps`; `contextlib` over hand-rolled context managers.
- Prefer returning a new object over mutating an argument; when the old code mutated and
  callers relied on it, the characterization test says so and the mutation stays until a
  behavior commit removes it.

## What is not a modernization

- `black`/`ruff format` runs: formatting, one commit, no review value beyond "it ran".
- Type-hint-only passes: separate skill, separate PR.
- Replacing a working loop with `itertools` gymnastics nobody can read.
- `__slots__`, `lru_cache`, `asyncio` without a measured reason.
- Swapping the exception type, the rounding, the ordering, the float formatting or the
  mutation of an argument: these are behavior changes; they need a `fix:`/`feat:` commit
  with a test that fails before it.
