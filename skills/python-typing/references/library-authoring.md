# Shipping a typed library

Verified with pyright 1.1.414, mypy 2.4.0 (October 2026). Normative source:
<https://typing.python.org/en/latest/guides/libraries.html> and PEP 561
(<https://peps.python.org/pep-0561/>).

## `py.typed` and stubs

- Inline types: add an empty `py.typed` file inside the top-level package and make sure the
  build includes it (hatchling and setuptools include package data by default only for files
  inside the package; check the wheel with `unzip -l dist/*.whl | grep py.typed`).
- Namespace packages need `py.typed` in each regular subpackage that ships types.
- Partial typing: a `py.typed` containing the line `partial\n` (stub packages only) tells checkers
  to fall back to the runtime package for modules the stubs do not cover.
- Separate stubs: a `<pkg>-stubs` distribution with `.pyi` files. Validate stubs against the
  runtime with `stubtest <pkg>` (ships with mypy); it imports the package and reports missing,
  extra and mismatched definitions. Use `--allowlist` for intentional differences.

## What counts as public (pyright and the typing guide agree)

In a `py.typed` package:

| Form | Public? |
|---|---|
| `_name`, `_module`, anything under a private module | no |
| `from m import x` in `__init__.py` | **no** (implicit re-export is private) |
| `from m import x as x`, `import m as m` | yes |
| name listed in `__all__` | yes, including a plain `from m import x` |
| `from m import *` | re-exports `m.__all__` |

<!-- claim: lib-verifytypes-exports --> mypy applies the same rule only with
`no_implicit_reexport` (part of `--strict`): users see `Module "pkg" does not explicitly export
attribute "x"`. Fix the library with `__all__` or `as x`, never with an ignore on the user side.

## Declared vs inferred types

Checkers infer differently, so a library's public surface should not depend on inference:

- **Return types**: an unannotated return is unknown to `--verifytypes` even when pyright infers
  it locally; mypy treats it as `Any` and ty as `Unknown`. Annotate every public return.
- **Instance attributes** assigned from calls (`self.n = len(pts)`, `self.pts = list(pts)`) are
  "ambiguous": `could be inferred differently by type checkers`. Declare them in the class body
  (`n: int`) or annotate the assignment.
- Literal and list-literal assignments (`kind = "shape"`, `NAMES = ["a"]`, `DEFAULT = 3.0`) are
  accepted as known. <!-- claim: lib-verifytypes-rules -->
- Do not use `ClassVar` to silence an ambiguous instance attribute: it forbids per-instance
  assignment. Annotate the attribute with its real type.

## `pyright --verifytypes`

```bash
PATH=.venv/bin:$PATH pyright --verifytypes mypkg --ignoreexternal           # human report
PATH=.venv/bin:$PATH pyright --verifytypes mypkg --ignoreexternal --outputjson \
  | python -c 'import json,sys; print(json.load(sys.stdin)["typeCompleteness"]["completenessScore"])'
```

- It resolves the package through the import path of the Python interpreter it finds (the
  `python` on `PATH`, or `PYTHONPATH`), not through `--pythonpath`. When resolution fails it does
  **not** say so: it prints `error: No py.typed file found` and `Type completeness score: 0%`.
  <!-- claim: lib-verifytypes-resolution --> Install the package into the venv (editable is
  fine) and put the venv first on `PATH`, or run from the source root with `PYTHONPATH=.`.
- `--ignoreexternal` skips unknown types that come from other packages.
- Exit code is 1 below 100%. In CI gate on `completenessScore` from `--outputjson` if 100% is not
  yet the target, and ratchet the threshold up.
- Each finding names the symbol (`pkg.Class.attr`) and the reason: `Return type annotation is
  missing`, `Type annotation for parameter "x" is missing`, `Type is missing type annotation and
  could be inferred differently by type checkers`, or `partially unknown`.

## Type tests in CI

Keep a `typing_tests/` (or `tests/typing/`) directory of files that are only type-checked, never
executed by pytest:

```python
from typing_extensions import assert_type  # typing.assert_type needs 3.11+

from mypkg import load

assert_type(load("x"), Config)
load(1)  # type: ignore[arg-type]
```

- Positive cases: `assert_type` on the public API. An `Any`/`Unknown` result fails the
  assertion; an unannotated return passes under pyright (it infers) but fails under mypy and ty.
  <!-- claim: lib-inferred-return -->
- Negative cases: a coded `# type: ignore[code]` plus mypy `warn_unused_ignores = true`. If the
  library stops rejecting the call, the ignore becomes unused and the test fails.
  <!-- claim: lib-type-tests-unused-ignore --> For pyright use
  `reportUnnecessaryTypeIgnoreComment = "error"`. ty ignores coded `type: ignore[...]` comments
  entirely (see `cross-checker.md`), so negative cases for ty need `# ty: ignore[rule]`.
- Functions holding `assert_type` must be annotated (`-> None`): mypy does not check the body of
  an unannotated function by default.
- Run every checker you claim to support on the directory; each has gaps the others do not.

## Runtime cost and dependencies

- Imports needed only for annotations go under `if TYPE_CHECKING:`; with
  `from __future__ import annotations` (or on 3.14+) the annotations can name them unquoted.
  ruff `TC001`-`TC003` move such imports, `TC004` flags ones used at runtime.
- `typing_extensions` is a runtime dependency if imported at module level. A library that wants
  zero dependencies imports newer constructs under `if TYPE_CHECKING:` and provides a runtime
  fallback (for example `TypeVar` without `default=`, or a no-op decorator), keeping the two
  branches signature-compatible.
- `@overload` and `Protocol` method bodies (`...`) are never executed; exclude them from coverage
  (`exclude_also = ["@overload", "\\.\\.\\.$"]` in coverage config, or `# pragma: no cover`).
