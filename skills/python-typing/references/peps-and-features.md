# Typing features by PEP and Python version

Verified with mypy 2.4.0, pyright 1.1.414, ty 0.0.86, typing_extensions 4.16, CPython 3.14/3.15
(October 2026). Spec: <https://typing.python.org/en/latest/spec/index.html>. Python's own table:
<https://docs.python.org/3/library/typing.html> (section "Deprecation Timeline of Major Features").

## Version gating

The import location decides whether a checker accepts the code for a target version. pyright
and ty read `pythonVersion` / `python-version` (ty falls back to the lower bound of
`requires-python`, see `setup.md`) and reject a `typing` import that does not exist there. Below
the floor, import the same name from `typing_extensions`, which every checker treats as the same
symbol. `typing_extensions>=4.15` provides everything in this table.

| PEP | Feature | `typing` / syntax since | mypy | pyright | ty |
|---|---|---|---|---|---|
| 604 | `X \| Y` in annotations | 3.10 at runtime | yes | yes | yes |
| 612 | `ParamSpec`, `Concatenate` | 3.10 | yes | yes | yes |
| 647 | `TypeGuard` | 3.10 | yes | yes | yes |
| 655 | `Required` / `NotRequired` | 3.11 | yes | yes | yes |
| 673 | `Self` | 3.11 | yes | yes | yes |
| 675 | `LiteralString` | 3.11 | **treated as `str`** | yes | yes |
| 646 | `TypeVarTuple`, `*Ts` | 3.11 | yes | yes | yes, keeps literals |
| 681 | `dataclass_transform` | 3.11 | yes | yes | yes |
| (none) | `assert_type`, `reveal_type`, `Never` | 3.11 | yes | yes | yes |
| 692 | `**kwargs: Unpack[TD]` | 3.12 | yes | yes | yes |
| 695 | `class C[T]`, `def f[T]`, `type X = ...` | 3.12 syntax | yes | yes | yes |
| 698 | `@override` | 3.12 | yes | yes | yes |
| 696 | type parameter defaults `[T = int]` | 3.13 | yes | yes | yes |
| 702 | `@warnings.deprecated` | 3.13 | off by default | off by default | warns |
| 705 | `ReadOnly` TypedDict items | 3.13 | yes | yes | yes |
| 742 | `TypeIs` | 3.13 | yes | yes | yes |
| 649/749 | deferred evaluation of annotations | 3.14 | n/a | yes | yes |
| 728 | `TypedDict(closed=True)` / `extra_items=` | 3.15 | **`closed` only** | yes | yes |
| 747 | `TypeForm` | 3.15 | yes | yes | yes |
| 800 | `@disjoint_base` | 3.15 | yes | yes | yes |
| 661 | `sentinel` builtin (`typing_extensions.Sentinel` before) | 3.15 | yes | yes | yes |
| 810 | `lazy import` statement | 3.15 | parses | parses | parses |

Import floors, checked by the checkers themselves:

- For a 3.10 target, `from typing import Self, assert_type, reveal_type` is an error in all
  three. <!-- claim: peps-import-floor-310 --> Probe files for projects that support 3.10 must use
  `from typing_extensions import assert_type`.
- `typing.override` needs 3.12; `typing.TypeIs`, `typing.ReadOnly` and `warnings.deprecated` need
  3.13. <!-- claim: peps-import-floor-312 -->
- PEP 696 defaults make the bare class mean the default: with `class Box[T = int]`, a parameter
  annotated `Box` is `Box[int]` in all three. <!-- claim: peps-696-defaults --> Below 3.13, declare
  the TypeVar with `typing_extensions.TypeVar("T", default=int)`; to avoid a runtime dependency,
  import it under `if TYPE_CHECKING:` and fall back to `typing.TypeVar` without the default at
  runtime.

## Semantics that differ from what the name suggests

- **`LiteralString`**: mypy accepts any `str` where `LiteralString` is expected; pyright and ty
  reject `"select " + user`. <!-- claim: peps-675-mypy-literalstring --> Do not rely on mypy alone
  to enforce it.
- **`TypeIs` vs `TypeGuard`**: `TypeIs[str]` narrows the `else` branch too (`int | str` becomes
  `int`); `TypeGuard[str]` leaves the `else` branch unchanged. <!-- claim: peps-742-typeis-negative -->
  `TypeIs` requires the narrowed type to be consistent with the parameter type; `TypeGuard` does
  not. Prefer `TypeIs` unless the narrowed type is not a subtype of the input.
- **`@deprecated`**: calling a deprecated function is silent in mypy (needs
  `--enable-error-code deprecated`) and in pyright `standard` (needs `reportDeprecated`); ty
  warns by default. <!-- claim: peps-702-deprecated-defaults -->
- **`@override`**: all three reject `@override` on a method that overrides nothing. None reports a
  missing `@override` by default; that needs mypy's `explicit-override` code or pyright's
  `reportImplicitOverride`. <!-- claim: peps-698-override -->
- **PEP 728**: mypy 2.4 accepts `closed=True` but rejects `extra_items=` as an unexpected keyword;
  pyright and ty check both. <!-- claim: peps-728-mypy-no-extra-items --> A plain (open) TypedDict
  still rejects unknown keys in a dict literal in every checker; `closed` matters for
  assignability and `**` unpacking.
- **`TypeVarTuple` solving**: ty keeps literal types (`pack(1, "a")` is
  `tuple[Literal[1], Literal["a"]]`), mypy and pyright widen to `tuple[int, str]`.
  <!-- claim: peps-646-ty-literals --> Assert with the widened type only under mypy/pyright, or
  annotate the arguments.
- **`TypeForm`**, **`@disjoint_base`** and **sentinels** are already implemented in all three
  checkers. <!-- claim: peps-747-typeform --> <!-- claim: peps-800-disjoint-base -->
  <!-- claim: peps-661-sentinel --> A sentinel is usable in a union (`int | MISSING`) and narrows
  with `is`.
- **`lazy import`** (3.15) parses in all three. <!-- claim: peps-810-lazy-import -->

## Forward references and `from __future__ import annotations`

Before 3.14, annotations are evaluated at definition time. A class referring to itself in its own
body (`def clone(self) -> Node`, `ClassVar[dict[str, Node]]`) or a function annotated with a class
defined later raises `NameError` at import. pyright and ty report this for a target below 3.14;
**mypy does not**, so a mypy-only project can ship code that fails to import on 3.13.
<!-- claim: peps-forward-ref-mypy-silent --> Fixes, in order of preference:

1. `Self` for "the same class" in methods (3.11+, or `typing_extensions`).
2. `from __future__ import annotations` at the top of the module (all annotations become strings;
   runtime consumers such as `dataclasses`, `pydantic`, `get_type_hints` then resolve them lazily).
3. Quote the name: `-> "Node"`.

From 3.14 (PEP 649/749) annotations are deferred and the unquoted form is valid in all three
checkers when the target is 3.14+. Expressions outside annotations are still evaluated eagerly:
`cast(Node, x)`, base classes, `TypeVar(bound=...)`, `type X = ...` right-hand sides used at
runtime, and `isinstance` all need the name defined (or a string where the API accepts one).

## Deprecated aliases and modernization

| Old | New | Removal | ruff rule |
|---|---|---|---|
| `typing.List`, `Dict`, `Set`, `Tuple`, `Type`, ... | `list`, `dict`, `set`, `tuple`, `type` | undecided | UP006, UP035 |
| `typing.Callable`, `Iterable`, `Mapping`, ... | `collections.abc` | undecided | UP035 |
| `Optional[X]`, `Union[X, Y]` | `X \| None`, `X \| Y` | not deprecated | UP045, UP007 |
| `typing.Text` | `str` | undecided | UP019 |
| `typing.ByteString` | `collections.abc.Buffer` or `bytes \| bytearray \| memoryview` | 3.17 | |
| `typing.AnyStr` | PEP 695 constrained parameter `[S: (str, bytes)]` | 3.18 | |
| `TypeAlias` annotation | `type X = ...` (3.12+) | undecided | UP040 |
| `T = TypeVar("T")` + `Generic[T]` | `class C[T]`, `def f[T]` (3.12+) | | UP046, UP047 |

Source for removal versions: the Python `typing` docs deprecation timeline. `type X = ...`
creates a `TypeAliasType`, which is not the aliased class at runtime: it cannot be used with
`isinstance` or called. Keep a plain assignment when the alias is also used at runtime.

PEP 695 type parameters are scoped to the class or function. Do not mix them with old-style
`TypeVar`s in the same signature, and remember the syntax is 3.12+: a library supporting 3.10
must keep `TypeVar`.

## Drafts (not final, do not use)

PEPs 718, 746, 764 (inline TypedDict, behind mypy `--enable-incomplete-feature=InlineTypedDict`),
767, 781, 821, 827, 835, 846, 849 are drafts or deferred as of this writing. Check
<https://peps.python.org/topic/typing/> before relying on anything not in the table above.
