# Patterns for dynamic code

Copy-ready recipes for patterns that checkers cannot follow by default. Every recipe was
checked with `assert_type` plus negative lines under mypy 2.4 `--strict`, pyright 1.1.414
(standard) and ty 0.0.86, targeting Python 3.10 (`typing_extensions` imports) unless noted.
Prove your adaptation the same way: a scratch probe inside the project, `assert_type` on
every public result, at least one line that must error, all three checkers.

Contents: descriptors · class statement replaced by an instance · `@deco` / `@deco(...)` ·
decorator that is also callable · callables with attributes · cached class-level factory ·
generic defaults · `dataclass_transform` · TypedDict · `TypeIs` · overloads · mixins ·
`@deprecated` · variance · portability · small rules.

## Descriptors: class access vs instance access

Overload `__get__` on `instance`: `None` is class access, the owner type is instance access,
and an `object` fallback keeps the descriptor type everywhere else. <!-- claim: patterns-descriptor-get-overloads -->

```python
from typing import overload
from typing_extensions import Self

class Column:
    @overload
    def __get__(self, instance: None, owner: type[Table]) -> Self: ...
    @overload
    def __get__(self, instance: Table, owner: object) -> int: ...
    @overload
    def __get__(self, instance: object, owner: object) -> Self: ...
    def __get__(self, instance: object, owner: object) -> Self | int:
        return 1 if isinstance(instance, Table) else self

class Table:
    size = Column()        # Table.size: Column, Table().size: int
```

- **The fallback overload is required.** Once a type has `__get__`, every class attribute
  annotated with that type, in any class, goes through it: `default: Column | None = None` on
  an unrelated class becomes `int | None` without the fallback. <!-- claim: patterns-descriptor-leakage -->
- Type unused `instance`/`owner` parameters as `object` (or `type[Owner]` when it selects the
  overload), never `Any`.
- **Objects replaced at class creation** (a metaclass or `__set_name__` swaps the class-body
  value for something else on instances): put the overloaded `__get__` inside
  `if TYPE_CHECKING:` in the class-body object's class. Runtime is untouched; checkers see
  `Owner.attr` as the declared object and `Owner().attr` as the bound value. <!-- claim: patterns-descriptor-type-checking-only -->

## Class statement that produces an instance

When a metaclass `__new__` returns an instance of another class (`class Group(metaclass=NodeFactory)`
evaluates to a `Node`), checkers still see a class. Declare only the members users need as
properties on the metaclass, under `TYPE_CHECKING`. <!-- claim: patterns-metaclass-returns-instance -->

```python
class NodeFactory(type):
    def __new__(mcs, name: str, bases: tuple[type, ...], ns: dict[str, Any]) -> Any:
        return Node(name)

    if TYPE_CHECKING:
        @property
        def name(cls) -> str: ...
        @property
        def connect(cls) -> Callable[[Node], Link]: ...   # Group.connect(leaf) -> Link
```

Mirror the few members the request names, not the whole instance API. Passing the class
object where a `Node` is expected still fails; that needs a real instance or an overload on
the receiving function.

## Decorator usable as `@deco` and `@deco(...)`, sync and async

Two overloads (positional-only function, keyword-only options), a typed implementation,
a separate async helper over `Callable[P, Awaitable[R]]`, and one cast at the
`iscoroutinefunction` dispatch. <!-- claim: patterns-paramspec-dual-decorator -->

```python
P = ParamSpec("P")
R = TypeVar("R")

@overload
def retry(func: Callable[P, R], /) -> Callable[P, R]: ...
@overload
def retry(*, times: int = 3) -> Callable[[Callable[P, R]], Callable[P, R]]: ...
def retry(
    func: Callable[P, R] | None = None, /, *, times: int = 3
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    def decorate(fn: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(fn):
            return cast("Callable[P, R]", _retry_async(fn, times))
        return _retry_sync(fn, times)
    return decorate if func is None else decorate(func)

def _retry_sync(fn: Callable[P, R], times: int) -> Callable[P, R]:
    @functools.wraps(fn)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R: ...
    return wrapper

def _retry_async(
    fn: Callable[P, Awaitable[R]], times: int
) -> Callable[P, Coroutine[Any, Any, R]]:
    @functools.wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        return await fn(*args, **kwargs)
    return wrapper
```

Do not leave the implementation as `Callable[..., Any] -> Any`: overloads alone type the
callers but leave the body unchecked. Probe `await fetch(...)` results, not the un-awaited
coroutine (mypy says `Coroutine`, pyright and ty say `CoroutineType`).

## Object that is both a decorator and a callable

An object registered with `@hook` and also invoked as `hook()` / `hook(10, currency="BRL")`:
overload `__call__` with a positional-only callable that is returned unchanged, then the call
form. Decorator methods are `(f: F) -> F`. <!-- claim: patterns-decorator-and-callable -->

```python
F = TypeVar("F", bound=Callable[..., Any])

class Hook:
    def before(self, f: F) -> F: ...

    @overload
    def __call__(self, f: F, /) -> F: ...
    @overload
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
    def __call__(self, *args: Any, **kwargs: Any) -> Any: ...
```

- The `/` makes zero-argument calls resolve to the second overload instead of failing with
  "argument missing for parameter f".
- Keep the call-form return compatible with `F` (here `Any`); a concrete return such as
  `list[Any]` makes the overloads overlap with incompatible returns (see Overloads).
- A subclass that overrides `__call__` does not inherit the overloads. Check whether the
  requested usages reach the override before typing it.

## Callables that carry attributes

Setting attributes on functions (`fn.key = ...`) is `attr-defined` / `unresolved-attribute`.
Declare a `Protocol` with `__call__`, `__name__` and the attributes, and build it in one
helper with a single cast. <!-- claim: patterns-callable-with-attributes -->

```python
R_co = TypeVar("R_co", covariant=True)

class Tagged(Protocol[P, R_co]):
    __name__: str
    key: str
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R_co: ...

def tag(fn: Callable[P, R_co], key: str) -> Tagged[P, R_co]:
    tagged = cast("Tagged[P, R_co]", fn)
    tagged.key = key
    return tagged
```

Declare `__name__` explicitly: ty rejects `fn.__name__` on a plain `Callable` because not
every callable is a function; mypy and pyright accept it. <!-- claim: patterns-callable-name-on-callable -->
Declare callable attributes as attributes (`clear: Callable[[], None]`), not methods, so the
helper can assign them.

## Cached class-level factory (function-wrapping descriptor)

A caching decorator stacked under `@classmethod` hides both the attributes it adds and the
return type. Move the implementation to module level with `cls: type[C]`, and make the cache
a descriptor whose `__get__` returns a bound object. <!-- claim: patterns-descriptor-wrapping-function -->

```python
class BoundFactory(Generic[C]):
    def __call__(self, key: str) -> C: ...
    def clear_cache(self) -> None: ...

class cached_factory(Generic[C]):
    def __init__(self, impl: Callable[[type[C], str], C]) -> None: ...
    def __get__(self, instance: object, owner: type[C]) -> BoundFactory[C]: ...

def _adapter_for(cls: type[Adapter], key: str) -> Adapter:
    return cls(key)

class Adapter:
    for_key = cached_factory(_adapter_for)  # Adapter.for_key("a"): Adapter
```

Keeping the implementation as a plain `def` in the class body with `cls: type[Adapter]`
fails: without `@classmethod` the first parameter is bound as `self`, and mypy and pyright
reject the annotation (ty 0.0.86 accepts it). <!-- claim: patterns-classmethod-cls-annotation -->

## Generic base with a default (PEP 696), no runtime dependency

To make `Flow[Order]` work while bare `Flow` keeps type checking (including under
`--disallow-any-generics`) on Python < 3.13 without depending on `typing_extensions` at
runtime: <!-- claim: patterns-generic-default-no-runtime-dep -->

```python
if TYPE_CHECKING:
    from typing_extensions import TypeVar
    M = TypeVar("M", default=Any)
else:
    from typing import TypeVar
    M = TypeVar("M")

class Base(Generic[M]): ...
class Flow(Base[M]): ...        # was `class Flow(Base)`: now Flow[Order] works
class Light(Flow): ...          # bare: M = Any, no type-arg error
```

Pick the default deliberately. A bounded TypeVar should default to its bound
(`TypeVar("M", bound=Machine, default=Machine)`): bare uses then see `Machine`, checked, and a
typo on them errors. <!-- claim: patterns-generic-default-to-bound --> Use `default=Any` only
when bare uses must stay unchecked because existing callers rely on it. With `typing_extensions` already a runtime
dependency, import `TypeVar` from it unconditionally.

## `dataclass_transform` for metaclass or base-class models

Use an overloaded field-specifier function, declared only for checkers, and keep the runtime
class behind it. <!-- claim: patterns-dataclass-transform-field-function -->

```python
if TYPE_CHECKING:
    @overload
    def Field(*, default: T, max_length: int | None = None) -> T: ...
    @overload
    def Field(*, max_length: int | None = None) -> Any: ...
    def Field(*, default: Any = None, max_length: int | None = None) -> Any: ...
else:
    Field = FieldInfo

@dataclass_transform(kw_only_default=True, field_specifiers=(Field,))
class ModelMeta(type): ...

class Model(metaclass=ModelMeta):
    def __init__(self, **values: Any) -> None: ...

class User(Model):
    name: str = Field(max_length=10)   # required, keyword-only
    age: int = Field(default=0)        # optional
```

Checkers then report unknown keywords, missing required fields, positional calls, wrong
value types and wrong attribute assignments.

- Do not use the runtime field class as the specifier when its `default` parameter has a
  default value: `name: str = FieldInfo(...)` is an assignment error (the call returns a
  `FieldInfo`, not `str`) and ty treats every field as optional. <!-- claim: patterns-dataclass-transform-class-specifier -->
- Do not annotate a metaclass `__call__` as returning `Any`: pyright and ty use it instead
  of the synthesized `__init__`, so instances become `Any` and keyword checks vanish (mypy
  ignores metaclass `__call__`). Drop the override or return the instance type. <!-- claim: patterns-dataclass-transform-metaclass-call -->

## TypedDict

- Narrow unions on a `Literal` discriminator key; read `NotRequired` keys with `.get`;
  mark immutable keys `ReadOnly` (assignment is an error); indexing a key that only some
  members have is an error. <!-- claim: patterns-typeddict-discriminated-union -->
- `closed=True` (PEP 728, `typing_extensions`, standard in 3.15) rejects unknown keys in all
  three. `extra_items=` works in pyright and ty; mypy 2.4 rejects the keyword and treats the
  class as closed. <!-- claim: patterns-typeddict-closed -->
- A string-valued alias needs `TypeAlias` (or a `type` statement on 3.12+):
  `Spec: TypeAlias = "int | Handler"`. Without the annotation it is a `str` variable and
  using it as a type is an error. <!-- claim: patterns-typealias-string-forward-ref -->
- To fix casts between TypedDicts, build the target dict key by key or widen the source type
  to a union of the real shapes; a `cast` hides missing keys.

## `TypeIs` vs `TypeGuard`

`TypeIs[T]` narrows both branches (the `else` branch becomes the input minus `T`) and errors
when `T` is not consistent with the parameter type. `TypeGuard[T]` narrows only the positive
branch. Prefer `TypeIs` for `isinstance`-like predicates; it is in `typing` from 3.13 and in
`typing_extensions` before. <!-- claim: patterns-typeis-vs-typeguard -->

## Overloads

- The implementation must accept every overload's arguments: all three checkers report it
  (ty on the overload, mypy and pyright on the implementation). <!-- claim: patterns-overload-pitfalls -->
- Order from narrow to broad. A broader earlier overload hides later ones, and overloads that
  overlap with incompatible returns are errors; mypy and pyright report both, ty 0.0.86
  reports neither, so one clean checker proves nothing here.
- Make the dispatching argument positional-only (`/`) when keyword use would make an
  overload ambiguous.

## Mixins that inject attributes at runtime

Make the mixin generic and declare the attribute it injects; subclasses pick the concrete
type, and typos still error. <!-- claim: patterns-mixin-injected-attribute -->

```python
M = TypeVar("M", bound=Tracker)

class TrackerMixin(Generic[M]):
    tracker_class: ClassVar[type[Tracker]]
    tracker: M                                # set in __init__ via setattr

class Order(TrackerMixin[OrderTracker]):
    tracker_class = OrderTracker              # Order().tracker: OrderTracker
```

A configurable attribute name (set with `setattr`) cannot be typed; declare the default name
and document that renamed attributes are untyped.

## `@deprecated` (PEP 702)

Usage of a `@deprecated` symbol is silent by default in mypy (even `--strict`) and in pyright
standard; ty warns. <!-- claim: patterns-deprecated-defaults --> Turn it on with mypy
`enable_error_code = ["deprecated"]`, pyright `reportDeprecated = "error"`, ty
`[tool.ty.rules] deprecated = "error"`. <!-- claim: patterns-deprecated-enabled --> Prefer
`@deprecated` over a runtime-only `warnings.warn` so callers see it in the editor.

## Variance

PEP 695 parameters (`class Box[T]`, 3.12+) infer variance: read-only use is covariant,
parameter-only use contravariant, a mutable attribute invariant. A `Cell[int]` is not a
`Cell[object]`; expose a read-only property to get covariance. <!-- claim: patterns-variance-pep695 -->
Old-style `TypeVar`s in a `Protocol` must declare the variance the protocol uses
(`R_co = TypeVar("R_co", covariant=True)` for return-only use).

## Portable over plugin-specific

mypy plugins (Django, SQLAlchemy and similar) have no counterpart in pyright or ty. For code
you own, express the behavior with portable constructs: `dataclass_transform`, overloads,
descriptors with `__get__`, `Protocol`s, `TYPE_CHECKING` declarations.

## Small rules

- Fix `no-any-return` from an untyped call (`json.loads`) with an annotated local
  (`data: dict[str, str] = json.loads(raw)`), not with new runtime validation. <!-- claim: patterns-annotated-local-no-any-return -->
- Use `object` for parameters whose type does not matter: it accepts anything and keeps the
  body checked; `Any` silences every use. <!-- claim: patterns-object-vs-any-param -->
- `@overload` stubs and `Protocol` bodies count as uncovered lines under coverage.py. Add
  `exclude_also = ["@overload", "if TYPE_CHECKING:", "\\.\\.\\.$"]` to
  `[tool.coverage.report]`, or `# pragma: no cover` when the coverage config is frozen.

## Sources

- Typing spec: [descriptors in the data model](https://docs.python.org/3/howto/descriptor.html),
  [overloads](https://typing.python.org/en/latest/spec/overload.html),
  [callables and ParamSpec](https://typing.python.org/en/latest/spec/generics.html#paramspec),
  [protocols](https://typing.python.org/en/latest/spec/protocol.html),
  [constructors and metaclass `__call__`](https://typing.python.org/en/latest/spec/constructors.html),
  [dataclass_transform](https://typing.python.org/en/latest/spec/dataclasses.html),
  [TypedDict](https://typing.python.org/en/latest/spec/typeddict.html),
  [type narrowing](https://typing.python.org/en/latest/spec/narrowing.html).
- PEPs: [612](https://peps.python.org/pep-0612/), [681](https://peps.python.org/pep-0681/),
  [695](https://peps.python.org/pep-0695/), [696](https://peps.python.org/pep-0696/),
  [702](https://peps.python.org/pep-0702/), [705](https://peps.python.org/pep-0705/),
  [728](https://peps.python.org/pep-0728/), [742](https://peps.python.org/pep-0742/).
- [coverage.py: excluding code](https://coverage.readthedocs.io/en/latest/excluding.html).
