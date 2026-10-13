# Cross-checker reference: suppressions, divergences, probes

Verified with mypy 2.4.0, pyright 1.1.414, basedpyright 1.40.2 and ty 0.0.86 on Python 3.14.
Every row tagged `claim:` is an executable probe in the eval suite; re-run it after upgrading a
checker. Sources: [typing spec, directives](https://typing.python.org/en/latest/spec/directives.html),
[mypy error codes](https://mypy.readthedocs.io/en/stable/error_codes.html),
[pyright comments](https://github.com/microsoft/pyright/blob/main/docs/comments.md),
[ty suppression](https://docs.astral.sh/ty/suppression/).

## Suppression matrix

"Suppresses" = the comment hides that checker's error on the line. "Unused" = the checker
reports the comment when the line has no error, with its unused-ignore check on (mypy
`warn_unused_ignores`, pyright `reportUnnecessaryTypeIgnoreComment`, ty
`unused-ignore-comment` / `unused-type-ignore-comment`).

| comment on the line | mypy | pyright (default) | pyright `enableTypeIgnoreComments=false` | basedpyright (default) | ty |
|---|---|---|---|---|---|
| `# type: ignore` | suppresses, unused reported | suppresses, unused reported | ignored | ignored | suppresses, unused reported |
| `# type: ignore[mypy-code]` | suppresses that code, unused reported | suppresses **everything**, unused reported | ignored | ignored | **ignored, never reported** |
| `# type: ignore[ty:rule]` | treated as a mypy code: mypy error not covered | suppresses, unused reported | ignored | ignored | suppresses, unused reported |
| `# type: ignore[code, ty:rule]` | `ty:rule` part reported unused | suppresses, unused reported | ignored | ignored | suppresses, unused reported |
| `# pyright: ignore` | ignored | suppresses, unused reported | suppresses, unused reported | suppresses, warns "must specify a rule" | ignored |
| `# pyright: ignore[rule]` | ignored | suppresses rule, unused reported | same | same | ignored |
| `# ty: ignore[rule]` / `# ty: ignore` | ignored | ignored | ignored | ignored | suppresses (bare form: all rules), unused reported |

Claims: cross-mypy-only-reads-type-ignore, cross-mypy-ty-codes-break-unused-ignore,
cross-mypy-unused-ignore-any-code, cross-pyright-honors-type-ignore-with-any-code,
cross-pyright-flags-unneeded-type-ignore, cross-pyright-etic-false,
cross-basedpyright-default-ignores-type-ignore, cross-ty-type-ignore-codes,
cross-ty-unused-type-ignore, cross-mypy-only-error-conflicts-with-pyright.

More facts:

- mypy sees `# type: ignore` only as the **first** comment on the line: `# noqa  # type: ignore[x]` or `# pyright: ignore[r]  # type: ignore[x]` does nothing for mypy. pyright and ty find their comments anywhere on the line. <!-- claim: cross-mypy-type-ignore-must-come-first -->
- With default pyright settings, a `# pyright: ignore[rule]` next to a `# type: ignore[code]` is itself reported unnecessary, because pyright already honored the `type: ignore`. <!-- claim: cross-pyright-redundant-next-to-type-ignore -->
- ty's unused-ignore rules default to `warn`, and a warning alone makes `ty check` exit 1. <!-- claim: cross-ty-unused-default-warn-exit-1 -->
- `[tool.ty.analysis] respect-type-ignore-comments = false` makes ty ignore every `type: ignore`. <!-- claim: cross-ty-respect-type-ignore-false -->
- A `# type: ignore` line before any code (no docstring above it) silences the whole file in mypy, pyright and ty. After a docstring or an import it is a normal unused line comment. <!-- claim: cross-file-level-type-ignore -->
- `# mypy: ignore-errors` at the top silences the file for mypy only. <!-- claim: cross-file-level-mode-comments -->
- `# pyright: basic` / `standard` / `strict` changes pyright's rule set for the file; it is not a suppression (basic still reports type errors) and other checkers ignore it. <!-- claim: cross-file-level-mode-comments -->

### Recipe: one line, different checkers complain, every unused check on

Copy codes and rules from the checker output (mypy `[code]`, pyright trailing `(reportX)`,
ty `error[rule]`); never guess them. Then pick the row:

| errors on the line from | write (in this order) |
|---|---|
| mypy + pyright + ty | `# type: ignore[code]  # ty: ignore[rule]` |
| mypy + pyright | `# type: ignore[code]` |
| mypy + ty | `# type: ignore[code]  # ty: ignore[rule]` and set pyright `enableTypeIgnoreComments = false` |
| mypy only | `# type: ignore[code]` and set pyright `enableTypeIgnoreComments = false` |
| pyright only | `# pyright: ignore[rule]` |
| ty only | `# ty: ignore[rule]` |
| pyright + ty | `# pyright: ignore[rule]  # ty: ignore[rule]` |

With `enableTypeIgnoreComments = false` (the basedpyright default), any line where pyright also
errors needs `# type: ignore[code]  # pyright: ignore[rule]  # ty: ignore[rule]`.

Never use the combined `# type: ignore[code, ty:rule]`: mypy reports the `ty:` half unused.
<!-- claim: cross-mypy-ty-codes-break-unused-ignore -->
When the project cannot set `enableTypeIgnoreComments = false`, a mypy-only error cannot be
suppressed without pyright flagging it, so fix the code or restructure the line instead.
<!-- claim: cross-mypy-only-error-conflicts-with-pyright -->

Before finishing, list the suppressions you added and prove each one is needed:

```bash
git diff -U0 | grep -E '^\+.*#\s*(type|pyright|ty):\s*ignore'
```

Then run every checker with its unused-ignore check on and delete each comment it reports.

## Divergence catalog

| situation | mypy | pyright | ty |
|---|---|---|---|
| call to a function **without return annotation** | `Any` | inferred type | `Unknown` <!-- claim: cross-return-inference --> |
| body of an unannotated `def` | **not checked** (`annotation-unchecked` note) | checked | checked <!-- claim: cross-untyped-body --> |
| `Cls.method = f` | `method-assign` | silent | silent <!-- claim: cross-method-assign --> |
| `obj.method = f` | `method-assign` | silent | `invalid-assignment` <!-- claim: cross-method-assign --> |
| name bound only inside a `for` body, used after | silent | `reportPossiblyUnboundVariable` | silent <!-- claim: cross-possibly-unbound-loop --> |
| `hasattr(o, "name")` on `o: object`, then `o.name` | `Any` | error, `Unknown` | `object` <!-- claim: cross-hasattr-narrowing --> |
| metaclass `__call__` with a non-instance return | ignored, gives the class instance | honored | honored <!-- claim: cross-metaclass-call --> |
| overloaded call with an `Any` argument matching several overloads | `Any` | `Unknown` | `Unknown` <!-- claim: cross-overload-any-arg --> |
| extra key in a TypedDict literal | `typeddict-unknown-key` | `reportAssignmentType` | `invalid-key` <!-- claim: cross-typeddict-extra-key-codes --> |
| `[1, "a"]` | `list[object]` (join) | `list[Unknown]` | `list[int \| str]` <!-- claim: cross-joins-vs-unions --> |
| `1 if b else "s"` | `int \| str` | `Literal[1, 's']` | `Literal[1, "s"]` <!-- claim: cross-joins-vs-unions --> |
| un-awaited `async def` call | `Coroutine[Any, Any, T]` | `CoroutineType[Any, Any, T]` | `CoroutineType[Any, Any, T]` <!-- claim: cross-coroutine-type --> |
| read-only property overriding a writable attribute | error | error | error <!-- claim: cross-property-overrides-attribute --> |
| target Python version | interpreter, unless `python_version` | interpreter, unless `pythonVersion` | lower bound of `requires-python` <!-- claim: cross-version-source --> |

Consequences:

- **Annotate the return of every function whose result callers use.** "pyright is clean"
  says nothing about what mypy and ty users see: without the annotation they get `Any` /
  `Unknown`, and attribute typos on the result go unreported. <!-- claim: cross-return-inference -->
- **Descriptor leakage:** once a class defines `__get__`, every class attribute annotated with
  it is read through `__get__`, including `x: D | None = None` in unrelated classes. Constrain
  the overloads (owner-specific instance overload plus an `object` fallback returning `Self`)
  or annotate those attributes with a non-descriptor type.
  <!-- claim: cross-descriptor-leaks-to-annotated-classvars -->
- **Arbitrary metaclass `__call__` returns** work in pyright and ty only. For mypy, declare the
  produced type another way (a `TYPE_CHECKING` branch, a factory function).
  <!-- claim: cross-metaclass-call -->
- Annotate mixed literals (`items: list[int | str] = [1, "a"]`) instead of relying on
  inference that differs per checker. <!-- claim: cross-joins-vs-unions -->

## Probe protocol

Use a throwaway probe to prove what callers see; runtime tests do not prove static types.

1. Write `_probe.py` **inside the project root** and run every checker from the root. ty
   discovers the project root from the working directory; from elsewhere the package import
   fails (`unresolved-import`) and everything becomes `Unknown`. <!-- claim: cross-ty-project-root -->
2. Put assertions in functions annotated `-> None` (or at module level). mypy does not check an
   unannotated `def`, and `assert_type` there fails with "expects everything to be Any in
   unchecked functions". <!-- claim: cross-mypy-assert-type-unchecked -->
3. Import `assert_type` from `typing_extensions` when the target is below 3.11. ty reads the
   target from `requires-python`, mypy and pyright from their config or the interpreter, so a
   probe can pass in one and fail in another. <!-- claim: cross-version-source -->
4. Assert on **results**, never on callables or coroutines: `assert_type(fn, Callable[[int, str], float])`
   fails in all three checkers when `fn` has named or defaulted parameters, and un-awaited
   coroutine types differ. Assert `assert_type(fn(1, "x"), float)` and
   `assert_type(await co(), int)` instead. <!-- claim: cross-assert-type-def-vs-callable --> <!-- claim: cross-coroutine-type -->
5. Add one **negative line** per public result (`result.missing_attribute` must error). It
   proves the result is not `Any` without spelling its full type.
6. Run all target checkers against the project interpreter, then delete the probe:

```bash
mypy --python-executable .venv/bin/python _probe.py
pyright --pythonpath .venv/bin/python _probe.py
ty check --python .venv _probe.py
```
<!-- claim: cross-cli-interpreter-flags -->

## Conformance (spec coverage)

[Typing conformance results](https://github.com/python/typing/tree/main/conformance), results
page updated 2026-10-09 (Pass = 1, Partial = 0.5, 146 tests):

| checker (version tested there) | score | notable gaps |
|---|---|---|
| mypy 2.1.0 | 109.5 / 146, 75.0% | metaclass `__call__`, `LiteralString`, TypedDict `extra_items`, ParamSpec/TypeVarTuple variance, `infer_variance`, dataclass_transform `converter`, `__new__` returning a non-subclass |
| pyright 1.1.410 | 136 / 146, 93.2% | `TypeForm` (PEP 747), `disjoint_base` (PEP 800), ParamSpec variance, mixed variance inference |
| ty 0.0.83 | 139.5 / 146, 95.5% | constrained TypeVars solved to unions, recursive generic protocols, some implicit type aliases, descriptor `__get__` on dataclass fields |

Conformance measures spec coverage, not usefulness: ty 0.0.x is beta and misses checks the others
make (possibly-unbound after loops, above), so a high score does not make it a drop-in
replacement. <!-- claim: cross-possibly-unbound-loop -->
