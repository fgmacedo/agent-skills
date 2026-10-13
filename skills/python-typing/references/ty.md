# ty

Verified against **ty 0.0.86** (with mypy 2.4.0 and pyright 1.1.414 for comparisons). ty is a
beta (0.0.x) and changes between releases: re-check rule names and defaults with
`ty explain rule <name>` and `ty check --help` for the installed version. Docs:
[CLI](https://docs.astral.sh/ty/reference/cli/),
[configuration](https://docs.astral.sh/ty/reference/configuration/),
[rules](https://docs.astral.sh/ty/rules/),
[suppression](https://docs.astral.sh/ty/suppression/),
[modules and environments](https://docs.astral.sh/ty/modules/),
[typing FAQ](https://docs.astral.sh/ty/reference/typing-faq/).

## Running it

```bash
ty check                                   # project root, honors [tool.ty] / ty.toml
ty check --output-format concise src tests # one line per diagnostic: file:line:col: level[rule] msg
ty check --python .venv                    # interpreter or venv dir used for third-party imports
ty check --python-version 3.12             # override the target version
ty check --error possibly-unresolved-reference --ignore unresolved-import
ty check -c 'analysis.respect-type-ignore-comments=false'   # one-off config override
ty explain rule invalid-method-override    # what a rule checks, default level, examples
ty check --add-ignore                      # write `# ty: ignore[rule]` on every diagnostic line
ty check --watch
```

- Use `--output-format concise` when reading output; the default `full` prints code frames.
  Other formats: `github`, `gitlab`, `junit`.
- Probes must live **inside the project** (or pass `--project`): ty discovers `pyproject.toml`
  and `.venv` by walking up from the project directory. A probe in `/tmp` sees `Unknown` for
  every project import.
- **Warnings fail the run**: with only warnings, ty exits 1. `--exit-zero-on-warning` exits 0
  when there are no errors, `--exit-zero` always exits 0. IO errors exit 2. <!-- claim: ty-exit-codes -->
- An unimported `reveal_type(...)` is an `undefined-reveal` **warning**, so it alone makes ty
  exit 1. Import it from `typing` (3.11+) or `typing_extensions`. <!-- claim: ty-undefined-reveal -->

## Target Python version

Resolution order: `--python-version` / `environment.python-version`, then the **lower bound of
`project.requires-python`**, then the active or discovered environment, then the newest stable
version. A project with `requires-python = ">=3.10"` is checked as 3.10 even when `.venv` is
3.12, so `from typing import Self` is `unresolved-import`. <!-- claim: ty-python-version-requires-python -->

Set `[tool.ty.environment] python-version` explicitly only when the project wants a different
target than its oldest supported version.

## Configuration

`[tool.ty]` in `pyproject.toml` or a top-level `ty.toml` (same keys without the `tool.ty`
prefix). When both exist, **`ty.toml` wins and the whole `[tool.ty]` section is ignored**, with a
WARN line. <!-- claim: ty-toml-precedence -->

```toml
[tool.ty.environment]
python-version = "3.12"
python = ".venv"                    # optional, auto-discovered
extra-paths = ["vendored"]

[tool.ty.src]
include = ["src", "tests"]
exclude = ["scripts/", "**/migrations/**"]

[tool.ty.rules]
possibly-unresolved-reference = "error"
deprecated = "error"
missing-type-argument = "error"

[tool.ty.analysis]
respect-type-ignore-comments = true  # default

[tool.ty.terminal]
output-format = "concise"
error-on-warning = false             # warnings alone then exit 0

[[tool.ty.overrides]]
include = ["tests/**"]
[tool.ty.overrides.rules]
unresolved-attribute = "ignore"
```

- `[[tool.ty.overrides]]` sets rule levels per glob (`include`, optional `exclude`). This is
  how per-directory policies (pyright `executionEnvironments`, mypy `[[overrides]]`) port to
  ty. <!-- claim: ty-overrides -->
- `--exclude GLOB` on the CLI **adds** to the configured excludes. Paths passed explicitly on
  the command line are checked even if excluded, unless `--force-exclude`. <!-- claim: ty-exclude-semantics -->
- An unknown rule name in config is only an `unknown-rule` **warning** (exit 1 unless
  `error-on-warning = false`); an invalid path such as a missing `extra-paths` directory
  aborts with exit 2. <!-- claim: ty-config-keys --> <!-- claim: ty-config-bad-path-exit-2 -->
- No strict mode and no missing-annotation rules exist: ty never reports unannotated
  parameters or returns. Enforce annotations with ruff `ANN` rules or mypy
  `disallow_untyped_defs`.

## Rule defaults that differ from intuition

| rule | default | mypy / pyright analogue |
|---|---|---|
| `possibly-unresolved-reference` | **ignore** | pyright `reportPossiblyUnboundVariable` (error in standard); mypy `possibly-undefined` (off) |
| `possibly-missing-attribute` | **ignore** | attribute missing on some members of a union |
| `missing-type-argument` | **ignore** | mypy `type-arg` under `disallow_any_generics`; pyright `reportMissingTypeArgument` (strict) |
| `missing-override-decorator` | **ignore** | mypy `explicit-override` (off) |
| `blanket-ignore-comment` | **ignore** | mypy `ignore-without-code` (off) |
| `deprecated` | warn | mypy `deprecated` (off), pyright `reportDeprecated` (strict) |
| `redundant-cast`, `unused-awaitable` | warn | mypy `redundant-cast` (strict), `unused-awaitable` (off) |
| `unused-ignore-comment`, `unused-type-ignore-comment` | warn | mypy `warn_unused_ignores` (strict); pyright `reportUnnecessaryTypeIgnoreComment` (off) |
| `invalid-method-override`, `invalid-attribute-override` | error | mypy `override` / `assignment`; pyright `reportIncompatibleMethodOverride` / `reportIncompatibleVariableOverride` |
<!-- claim: ty-default-levels -->

A loop variable used after the loop is silent by default and reported only with
`possibly-unresolved-reference` enabled. <!-- claim: ty-possibly-unbound-off -->

## Rule names across checkers

| situation | mypy | pyright | ty |
|---|---|---|---|
| missing attribute | `attr-defined` | `reportAttributeAccessIssue` | `unresolved-attribute` |
| wrong type assigned to attribute | `assignment` | `reportAttributeAccessIssue` | `invalid-assignment` |
| wrong type assigned to variable | `assignment` | `reportAssignmentType` | `invalid-assignment` |
| wrong argument type | `arg-type` | `reportArgumentType` | `invalid-argument-type` |
| no overload matches | `call-overload` | `reportCallIssue` | `no-matching-overload` |
| bad return value | `return-value` | `reportReturnType` | `invalid-return-type` |
| unresolvable import | `import-not-found` | `reportMissingImports` | `unresolved-import` |
| incompatible method override | `override` | `reportIncompatibleMethodOverride` | `invalid-method-override` |
| incompatible attribute override | `assignment` | `reportIncompatibleVariableOverride` | `invalid-attribute-override` |
<!-- claim: ty-rule-map --> <!-- claim: ty-override-rules -->

Copy the rule from the `error[...]` bracket of the output; never guess it. A misspelled rule
inside `# ty: ignore[...]` is an `ignore-comment-unknown-rule` warning and suppresses
nothing. <!-- claim: ty-blanket-ignore-rule -->

## Suppression

| comment | ty behavior |
|---|---|
| `# ty: ignore[rule-a, rule-b]` | suppresses those rules on the line (first or last line of a multi-line diagnostic) |
| `# ty: ignore` | suppresses everything; flagged by `blanket-ignore-comment` when enabled <!-- claim: ty-blanket-ignore-rule --> |
| `# type: ignore` (bare) | **honored**; unused ones are `unused-type-ignore-comment` <!-- claim: ty-bare-type-ignore --> |
| `# type: ignore[attr-defined]` (codes without `ty:`) | **ignored entirely**: does not suppress, never reported as unused <!-- claim: ty-coded-type-ignore-ignored --> |
| `# type: ignore[ty:unresolved-attribute]` | behaves like `# ty: ignore[unresolved-attribute]`; mixed lists work, e.g. `[attr-defined, ty:unresolved-attribute]` <!-- claim: ty-type-ignore-ty-prefix --> |
| `# pyright: ignore[...]` | **ignored**; append `# ty: ignore[rule]` on the same line <!-- claim: ty-pyright-ignore-ignored --> |
| `# ty: ignore[rule]` or `# type: ignore` on its own line before any code (docstrings count as code) | suppresses for the whole file <!-- claim: ty-file-level-ignore --> |
| `@no_type_check` on a function | skips its body (not supported on classes) <!-- claim: ty-no-type-check --> |

- `analysis.respect-type-ignore-comments = false` makes ty ignore every `# type: ignore`, so a
  line shared with mypy needs its own `# ty: ignore[...]`. <!-- claim: ty-respect-type-ignore-off -->
- An unused `# ty: ignore` is `unused-ignore-comment` (warning, so exit 1). <!-- claim: ty-unused-ty-ignore -->
- The suppression docs describe one `unused-ignore-comment` rule for both forms; 0.0.86 reports
  unused `type: ignore` under the separate `unused-type-ignore-comment`.
- `--add-ignore` writes `# ty: ignore[<rule>]` to every offending line. Use it only to baseline
  a legacy codebase, then remove entries as you fix them. <!-- claim: ty-add-ignore -->
- A coded `# type: ignore[ty:rule]` is read by mypy too; with `warn_unused_ignores` mypy reports
  the `ty:` code as unused. On lines that need both, prefer separate comments:
  `# type: ignore[code]  # ty: ignore[rule]`. <!-- claim: ty-mypy-sees-ty-code -->

## Inference differences that break probes

- **Unannotated functions return `Unknown`** at call sites, even for `return 1`. pyright
  infers the return type, mypy uses `Any`. Annotate every return that callers depend on.
  <!-- claim: ty-unannotated-return-unknown -->
- `Unknown` is ty's implicit `Any` (inferred, not written). It is as permissive as `Any`: an
  `Unknown` result silently accepts typos, so probe with a negative line (`obj.missing` must
  error).
- **`float*` / `complex*`**: ty marks a value it knows is a real `float` (not an `int`
  promoted to `float`). `assert_type(x, float)` **fails** on `float*`, even when `x` is
  declared `x: float = 1.5`, because assignment narrows the declared type. Assert on a
  function result annotated `-> float` instead. <!-- claim: ty-float-star -->
- `Callable[..., R]` has no `__name__` in ty ("not every callable is a function"). Use a
  `Protocol` that declares `__name__: str` and `__call__`. <!-- claim: ty-callable-no-name -->
- `hasattr(obj, "x")` narrows `obj.x` to `object`, not `Any`. Cast or use a `Protocol` plus
  `isinstance` with `@runtime_checkable`. <!-- claim: ty-hasattr-object -->
- A string assigned to a name is not a type alias: `Alias = "int | str"` is
  `invalid-type-form` when used in an annotation. Write `Alias: TypeAlias = "int | str"` or a
  `type Alias = int | str` statement (3.12+). <!-- claim: ty-string-alias -->
