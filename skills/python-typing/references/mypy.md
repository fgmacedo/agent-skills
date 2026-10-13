# mypy

Verified with mypy 2.4.0 on Python 3.14, Oct 2026. Lines marked `<!-- claim: id -->` are
executable probes in the skill's eval suite. Docs: <https://mypy.readthedocs.io/en/stable/>.

## Running it

- Pass targets explicitly: `mypy pkg tests`. With no target and no `files` config, mypy exits
  with "Missing target module, package, files, or command".
- When mypy is not installed in the project's environment (global tool, `uvx`, CI image),
  add `--python-executable .venv/bin/python` so installed packages and their `py.typed`
  stubs resolve. Without it, third-party imports become `import-not-found` or `Any`.
- Machine-readable output: `mypy -O json ...` prints one JSON object per diagnostic, with
  `file`, `line`, `column`, `code`, `severity` (`error` or `note`). <!-- claim: mypy-output-json -->
- Throwaway probes: `mypy --no-incremental probe.py` avoids touching the project cache.
- Parallel checking: `-n N` / `-n auto` (auto caps at 8 workers), or `MYPY_NUM_WORKERS`.
  The default is a single process. Parallel mode requires `local_partial_types` (the 2.x
  default).
- `dmypy run -- pkg` keeps a daemon for fast re-checks in a watch loop; it needs the same
  flags every run.

## Defaults that changed in 2.x

Check these before trusting older answers or blog posts
(<https://mypy.readthedocs.io/en/stable/changelog.html>):

| setting | 2.x default | what it means |
|---|---|---|
| `strict_bytes` | on | `bytearray` and `memoryview` are no longer accepted where `bytes` is expected; opt out with `--no-strict-bytes` <!-- claim: mypy-strict-bytes-default --> <!-- claim: mypy-no-strict-bytes --> |
| `local_partial_types` | on | `x = None` at class or module scope is not completed by an assignment inside a function in another scope; annotate `x: int \| None = None` |
| `allow_redefinition` | off | new semantics when on: a local variable may take a new type on reassignment (`x = 1; x = "a"` makes `x: str`); the 1.x behavior is `--allow-redefinition-old` <!-- claim: mypy-redefinition-default --> <!-- claim: mypy-allow-redefinition --> |
| native parser | on | `--no-native-parser` falls back to the `ast`-based parser if a parse result looks wrong |
| cache | SQLite, fixed format | `.mypy_cache` is a database; delete the directory, do not edit it |

## What `--strict` turns on, and what it does not

`--strict` = `disallow_any_generics`, `disallow_subclassing_any`, `disallow_untyped_calls`,
`disallow_untyped_defs`, `disallow_incomplete_defs`, `check_untyped_defs`,
`disallow_untyped_decorators`, `warn_redundant_casts`, `warn_unused_ignores`,
`warn_return_any`, `no_implicit_reexport`, `strict_equality`, `extra_checks`
(`mypy --help`, "Miscellaneous strictness flags").

Not included, enable separately when wanted:

| check | how to enable | note |
|---|---|---|
| unreachable code | `warn_unreachable = true` | <!-- claim: mypy-strict-no-unreachable --> <!-- claim: mypy-warn-unreachable --> |
| `@override` required | `enable_error_code = ["explicit-override"]` | <!-- claim: mypy-explicit-override-not-strict --> <!-- claim: mypy-explicit-override-enabled --> |
| non-exhaustive `match` | `enable_error_code = ["exhaustive-match"]` | <!-- claim: mypy-exhaustive-match-opt-in --> <!-- claim: mypy-exhaustive-match-enabled --> |
| PEP 702 `@deprecated` usage | `enable_error_code = ["deprecated"]` | silent by default, even with the decorator present <!-- claim: mypy-deprecated-opt-in --> <!-- claim: mypy-deprecated-enabled --> |
| name bound in one branch only | `enable_error_code = ["possibly-undefined"]` | <!-- claim: mypy-possibly-undefined-opt-in --> <!-- claim: mypy-possibly-undefined-enabled --> |
| bare `# type: ignore` | `enable_error_code = ["ignore-without-code"]` | <!-- claim: mypy-unused-ignore-and-without-code --> |
| `None` in `strict_equality` | `strict_equality_for_none = true` | |
| explicit `Any` in annotations | `disallow_any_explicit = true` (code `explicit-any`) | |

The full list of off-by-default codes in 2.4: `possibly-undefined`, `redundant-expr`,
`truthy-bool`, `truthy-iterable`, `ignore-without-code`, `unused-awaitable`,
`redundant-self`, `unused-ignore`, `explicit-override`, `unimported-reveal`,
`mutable-override`, `exhaustive-match`, `deprecated`
(<https://mypy.readthedocs.io/en/stable/error_code_list2.html>). `unused-ignore` is what
`warn_unused_ignores` turns on.

`untyped-decorator` ("Untyped decorator makes function X untyped") comes from
`disallow_untyped_decorators`, which `--strict` includes and `disallow_untyped_defs` does
not. <!-- claim: mypy-untyped-decorator-strict --> <!-- claim: mypy-untyped-decorator-not-defs -->
Fix it by typing the decorator (ParamSpec), not by ignoring each decorated function.

## Strict for one package only

`strict` is not a per-module option:

- `strict = true` inside `[[tool.mypy.overrides]]` is applied to **every** module, with no
  warning, not even with `warn_unused_configs`. <!-- claim: mypy-strict-override-global -->
- `# mypy: strict` at the top of a file is an error: `Setting "strict" not supported in
  inline configuration`. <!-- claim: mypy-inline-strict-rejected -->

List the per-module flags instead. `module = "pkg.core.*"` also matches `pkg.core` itself
(its `__init__.py`), so one entry is enough. <!-- claim: mypy-per-module-strict-recipe -->

```toml
[tool.mypy]
warn_unused_configs = true
warn_redundant_casts = true          # global-only: cannot go in an override

[[tool.mypy.overrides]]
module = "pkg.core.*"
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_calls = true
disallow_untyped_decorators = true
disallow_any_generics = true
disallow_subclassing_any = true
warn_return_any = true
warn_unused_ignores = true
no_implicit_reexport = true
strict_equality = true
extra_checks = true
```

- Global-only flags placed in an override (`warn_redundant_casts`, `warn_unused_configs`,
  `strict`, `strict_bytes`, `python_version`, `plugins`, ...) print `Per-module sections
  should only specify per-module flags (...)`, are ignored, and mypy still exits 0. Read the
  first lines of output after editing config. <!-- claim: mypy-global-only-in-override -->
- `warn_unused_configs` reports an override that matches nothing as `note: unused
  section(s): module = [...]`, also with exit 0. <!-- claim: mypy-unused-config-section -->
- `no_implicit_reexport` on a package changes what its importers may import: names pulled in
  with `from x import y` are private unless re-exported with `from x import y as y` or listed
  in `__all__`. Add `__all__` in the same change.
- Inline per-file flags are allowed for everything except `strict`:
  `# mypy: disallow-untyped-defs, warn-return-any`
  (<https://mypy.readthedocs.io/en/stable/inline_config.html>).

## Unannotated code

- A function without a return annotation returns `Any`, even when its parameters are
  annotated. mypy never infers return types (pyright does; ty does not either). Annotate the
  return of every function whose result callers use. <!-- claim: mypy-unannotated-return-any -->
- The body of a function with no annotations at all is not checked unless
  `check_untyped_defs` is on. `assert_type` inside it fails with `"assert_type" expects
  everything to be "Any" in unchecked functions`, and wrong assignments there pass silently
  (note `[annotation-unchecked]`). Give every test or probe function `-> None`.
  <!-- claim: mypy-unchecked-body -->

## Suppressions

- Form: `# type: ignore[code]` or `# type: ignore[code1, code2]`. Copy the code from the
  bracket at the end of the error line; never guess it.
- A wrong code does not suppress, and mypy prints the right one:
  `note: Error code "assignment" not covered by "type: ignore[attr-defined]" comment`.
  <!-- claim: mypy-ignore-code-mismatch -->
- `warn_unused_ignores` reports `Unused "type: ignore" comment [unused-ignore]` on lines that
  no longer need it; `ignore-without-code` reports bare ignores and suggests the code.
  <!-- claim: mypy-unused-ignore-and-without-code -->
- `warn_unused_ignores` is off by default and in many projects. Before finishing, run once
  with `--warn-unused-ignores` (and grep the diff for `type: ignore`) so speculative ignores
  do not ship.
- Other checkers read `# type: ignore` too; see `cross-checker.md` before adding one to code
  that pyright or ty also check.

## Probing types

- `reveal_type(x)` needs no import in mypy (the `unimported-reveal` code can require one).
  Remove probes before finishing.
- `assert_type(value, T)` is exact, not a subtype check: `assert_type(1, int)` fails because
  the type is `Literal[1]`, and an `int` is not `object`. Assert on annotated names or call
  results, with the precise expected type. <!-- claim: mypy-assert-type-exact -->

## Plugins and stubs

- mypy plugins (`plugins = [...]`) only affect mypy; pyright and ty ignore them. Prefer
  portable typing (`@dataclass_transform`, overloads, `Protocol`, descriptors with typed
  `__get__`) when more than one checker must agree
  (<https://mypy.readthedocs.io/en/stable/extending_mypy.html>).
- `python -m mypy.stubtest pkg` compares `.pyi` stubs against the runtime module; run it in
  CI for hand-written stubs (<https://mypy.readthedocs.io/en/stable/stubtest.html>).
