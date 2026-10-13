---
name: python-typing
description: >
  Python static typing with mypy, pyright, basedpyright and ty: fixing type-checker errors,
  making several checkers agree, typing dynamic code (descriptors, metaclasses, decorators,
  ParamSpec, overloads, generic defaults, dataclass_transform, TypedDict, Protocols, mixins),
  which suppression comment to write when several checkers run, TypeIs/TypeGuard narrowing,
  checker configuration (per-module strict, porting pyright config to ty, CI and pre-commit)
  and typed libraries (py.typed, pyright --verifytypes). Use whenever a
  Python task touches type annotations or type-checker output, for example "reveal_type shows
  Any", "decorator loses the signature", `# type: ignore`, `[attr-defined]`, `[type-arg]`,
  `[no-untyped-def]`, `reportAttributeAccessIssue`, "Cannot access attribute",
  `unresolved-attribute`, `invalid-argument-type`, "Unused \"type: ignore\" comment",
  `warn_unused_ignores`, `reportUnnecessaryTypeIgnoreComment`, or a
  request to add type hints, enable strict mode, or adopt ty.
license: MIT
---

# Python typing: mypy, pyright, ty

A typing fix is done when **every checker the project targets sees the precise type at the
call sites users write**, proven with `assert_type` probes. "The reported errors are gone" is
not done: mypy and ty silently turn many unfinished fixes into `Any` / `Unknown`, which reports
nothing.

**Do not report done until all four hold:**

1. Every public module-level function and public method in the modules you edited that
   callers reach through the requested API has a return annotation; a missing one is `Any` in
   mypy and `Unknown` in ty. Check mechanically, not by eye. Annotate those precisely.
   Leave private helpers and nested closures alone; an `Any` annotation added only to silence
   a coverage check is not a fix.
2. A probe asserts the result type of each API the request names, plus one line that must
   error, and is clean under every target checker (step 4).
3. Each suppression you added was reported as needed by a checker, and none is unused.
4. The project's own checker invocations and tests pass.

Verified with mypy 2.4.0, pyright 1.1.414, basedpyright 1.40.2, ty 0.0.86 (beta), Python 3.14,
Oct 2026. Every non-obvious fact in `references/` is backed by an executable probe.

## Workflow

### 0. Detect how the project checks types

Find the checkers, their config, the target Python of each checker and the exact commands
pre-commit and CI run. Use those commands, with the project's interpreter, for every check.

- Config precedence: `pyrightconfig.json` silently replaces `[tool.pyright]`; `ty.toml`
  replaces `[tool.ty]`; an unknown `[tool.ty]` key makes ty exit 2.
- Target version: mypy and pyright use `python_version` / `pythonVersion`, else the
  interpreter; **ty uses the lower bound of `requires-python`**. The same import can pass two
  checkers and fail the third.
- Point checkers at the project venv: `mypy --python-executable .venv/bin/python`,
  `pyright --pythonpath .venv/bin/python`, `ty check --python .venv`.

### 1. Baseline

Run every target checker as the project does and record counts by rule before editing.

### 2. Classify each error

| class | signal | action |
|---|---|---|
| real bug | runtime would fail or misbehave | fix the code |
| loose annotation | missing return type, `Any`, bare `Callable`, `dict` without params | tighten the annotation |
| dynamic pattern | descriptor, metaclass, decorator, injected attribute, function attribute | `references/patterns.md` recipe |
| checker divergence | one checker disagrees on correct code | `references/cross-checker.md` |
| stub gap | third-party module untyped or wrong | stub package, local `.pyi`, narrow override |
| config | wrong target version, interpreter, include paths, mode | fix config, not code |

### 3. Fix with the first rung that works

1. Fix the code or the annotation. **Annotate the return type of every function you touch
   whose result callers use**: mypy gives `Any` and ty gives `Unknown` for unannotated returns;
   only pyright infers.
2. A precise construct: `@overload`, `Protocol`, `TypeVar` / `ParamSpec`, `Self`, `TypeIs`,
   generics with defaults, descriptor `__get__` overloads.
3. Declarations under `if TYPE_CHECKING:` for members created at runtime (metaclass
   properties, a type-only `__get__`, a stricter `TypeVar`). Runtime stays unchanged.
4. A `.pyi` stub next to the module.
5. One `cast` inside one helper, never at call sites.
6. A narrow, coded suppression on the exact line (see Suppressions).

Keep the change typing-only: no new runtime validation, no behavior changes, no overloads on
code paths the request does not reach. Fix `no-any-return` from `json.loads` with an annotated
local (`data: dict[str, str] = json.loads(raw)`).

### 4. Prove it with a probe

Write a throwaway `_probe.py` **inside the project root** and check it with every target
checker:

```python
from __future__ import annotations
from typing_extensions import assert_type   # typing.assert_type needs 3.11+ in pyright and ty

from pkg import Widget, make_widget


def probe() -> None:                         # annotated: mypy skips unannotated bodies
    w = make_widget("a")
    assert_type(w, Widget)                   # assert results, not callables or coroutines
    assert_type(w.size(), int)
    w.missing_attribute                      # must error: proves w is not Any
```

- `assert_type` is exact: `assert_type(1, int)` fails (`Literal[1]`); ty narrows
  `x: float = 1.5` to a literal-ish `float*`. Assert on calls to annotated functions.
- Assert `await coro()` results; un-awaited coroutines are `Coroutine` in mypy and
  `CoroutineType` in pyright and ty.
- Runtime tests do not prove static types. Keep the probe out of the commit unless the
  project has type tests (`references/library-authoring.md`).

### 5. Finish

1. Re-run every target checker with the project's own invocation, plus the tests, and walk the
   four "done" conditions at the top.
2. List the suppressions you added and prove each one: run with unused-ignore checks on
   (mypy `--warn-unused-ignores`, pyright `reportUnnecessaryTypeIgnoreComment`, ty reports by
   default) and delete what they flag.
   `git diff -U0 | grep -E '^\+.*#\s*(type|pyright|ty):\s*ignore'`
3. Check `git diff` for `Any` you introduced; replace with `object`, `type[C]`,
   `Callable[..., R]` or a `TypeVar` where possible.
4. Make edits with the editor tool and confirm them in `git diff`; BSD `sed -i` (macOS)
   needs `''` and fails otherwise.

## Suppressions

Copy the code from the output: mypy `[code]`, pyright trailing `(reportRule)`, ty
`error[rule]`. Never guess names (`reportPossiblyUnbound` is wrong; it is
`reportPossiblyUnboundVariable`, and pyright reports the wrong name as unnecessary).

| comment | mypy | pyright (default) | ty |
|---|---|---|---|
| `# type: ignore[code]` | suppresses `code` | suppresses **everything** on the line | **ignored, never reported unused** |
| `# type: ignore` (bare) | suppresses all | suppresses all | suppresses all |
| `# pyright: ignore[rule]` | ignored | suppresses `rule` | ignored |
| `# ty: ignore[rule]` | ignored | ignored | suppresses `rule` |

- mypy reads `# type: ignore` only as the **first** comment on the line.
- Never write the combined `# type: ignore[code, ty:rule]`: mypy reports the `ty:` part unused.
  Write separate comments: `# type: ignore[code]  # ty: ignore[rule]`.
- With default pyright, a `# type: ignore[code]` for a mypy-only error is reported
  unnecessary by pyright; the per-checker recipe is in `references/cross-checker.md`.
- Never add a suppression before running the checker that needs it.

## Facts that differ from intuition

| fact | where |
|---|---|
| mypy does not check bodies of unannotated `def`s (`check_untyped_defs` off); `assert_type` there fails with "expects everything to be Any" | mypy.md |
| `strict = true` inside `[[tool.mypy.overrides]]` applies to the **whole project**, silently; inline `# mypy: strict` is rejected. List the per-module flags instead | mypy.md |
| `--strict` does not enable `warn_unreachable`, `deprecated`, `exhaustive-match`, `explicit-override`, `possibly-undefined` | mypy.md |
| `pyright --verifytypes` ignores `--pythonpath`; it resolves the package through `python` on `PATH`. "No py.typed file found" with 0% means a resolution failure | pyright.md |
| ty: warnings alone exit 1; no strict mode and no missing-annotation rules (use ruff `ANN` or mypy) | ty.md |
| ty: a bare `Callable` has no `__name__`; `hasattr` narrows to `object` | ty.md |
| Adding `__get__` to a class makes every class attribute annotated with it a descriptor, including `x: D \| None = None` in unrelated classes | cross-checker.md |
| A metaclass `__call__` returning a non-instance is honored by pyright and ty, ignored by mypy | cross-checker.md |
| `@deprecated` is silent by default in mypy (even `--strict`) and pyright standard; ty warns | patterns.md |
| A class's own name inside its body needs quotes or `from __future__ import annotations` below 3.14; mypy does not report it, the code fails at runtime | peps-and-features.md |

## Pattern index (`references/patterns.md`)

| symptom | recipe |
|---|---|
| class access and instance access of an attribute need different types | descriptor `__get__` overloads with `object` fallback |
| a class statement produces an instance (metaclass `__new__` returns another type) | metaclass properties under `TYPE_CHECKING` |
| decorator loses the signature; must work as `@deco` and `@deco(opt=...)`, sync and async | `ParamSpec` overloads, async helper |
| object used both as a decorator and called to trigger something | `__call__(self, f: F, /) -> F` overload plus the call form |
| attributes set on functions (`fn.cache = ...`, `[attr-defined]`) | `Protocol` with `__call__` and the attributes |
| cached factory stacked with `@classmethod` loses its attributes | function-wrapping descriptor |
| `Base[T]` must keep working as bare `Base`, no runtime dependency | PEP 696 default under `TYPE_CHECKING` |
| models with `Field(...)` defaults and synthesized `__init__` | `dataclass_transform` with field specifiers |
| dict schemas with optional or variant keys, casts between TypedDicts | `NotRequired`, `ReadOnly`, discriminated unions |
| attributes injected by a mixin or framework | generic mixin with a declared attribute |
| user-defined narrowing function | `TypeIs` vs `TypeGuard` |

## References

| file | read when |
|---|---|
| `references/cross-checker.md` | several checkers disagree, suppression on a shared line, divergence catalog, probe protocol |
| `references/patterns.md` | typing a dynamic pattern (index above) |
| `references/mypy.md` | mypy config, `--strict` composition, per-module strict, error codes, plugins |
| `references/pyright.md` | message to rule map, modes, `--verifytypes`, basedpyright differences |
| `references/ty.md` | ty CLI, config, rule names and defaults, suppression, gaps in 0.0.x |
| `references/peps-and-features.md` | which `typing` feature exists for the target version, `typing_extensions` fallbacks |
| `references/library-authoring.md` | `py.typed`, public API rules, verifytypes workflow, type tests in CI |
| `references/setup.md` | pyproject configs side by side, pre-commit hooks, GitHub Actions, ruff rules |
