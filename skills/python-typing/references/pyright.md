# pyright and basedpyright

Verified with pyright 1.1.414 and basedpyright 1.40.2 (based on pyright 1.1.414). Docs:
[configuration](https://github.com/microsoft/pyright/blob/main/docs/configuration.md),
[comments](https://github.com/microsoft/pyright/blob/main/docs/comments.md),
[command line](https://github.com/microsoft/pyright/blob/main/docs/command-line.md),
[type inference](https://github.com/microsoft/pyright/blob/main/docs/type-inference.md),
[mypy comparison](https://github.com/microsoft/pyright/blob/main/docs/mypy-comparison.md),
[typed libraries](https://github.com/microsoft/pyright/blob/main/docs/typed-libraries.md),
[basedpyright](https://docs.basedpyright.com/).

## Modes

| mode | how to select | what it adds |
|---|---|---|
| `basic` | `typeCheckingMode = "basic"` | baseline error set |
| `standard` | **default** when nothing is set | `reportIncompatibleMethodOverride`, `reportIncompatibleVariableOverride`, `reportFunctionMemberAccess`, `reportOverlappingOverload`, `reportPossiblyUnbound` as errors <!-- claim: pyright-default-mode-is-standard --> |
| `strict` | `typeCheckingMode = "strict"`, `strict = ["path"]`, or `# pyright: strict` | `reportUnknown*`, `reportMissingParameterType`, `reportMissingTypeArgument`, `reportPrivateUsage`, `reportUnusedImport`, `reportUnnecessaryIsInstance`, `reportUnnecessaryCast`, `reportMatchNotExhaustive`, `reportDeprecated` <!-- claim: pyright-strict-only-rules --> (full list in the [configuration table](https://github.com/microsoft/pyright/blob/main/docs/configuration.md#diagnostic-settings-defaults)) |

- `basic` does not downgrade the standard-only rules to warnings: it drops them. <!-- claim: pyright-basic-drops-standard-rules -->
- Explicit `Any` is never reported, even in strict. Only inferred `Unknown` is (`reportUnknown*`). <!-- claim: pyright-strict-only-rules -->
- `@deprecated` usage is invisible on the CLI unless `reportDeprecated` is set (strict or explicit). <!-- claim: pyright-deprecated-off-in-standard --> <!-- claim: pyright-deprecated-enabled -->
- A file comment overrides the project mode for that file in both directions: `# pyright: basic`, `# pyright: standard`, `# pyright: strict`. <!-- claim: pyright-file-comment-standard -->
- `# pyright: reportFoo=false` (or `=error`) on its own line sets one rule for the file ([comments](https://github.com/microsoft/pyright/blob/main/docs/comments.md)).

## Config location

- `pyrightconfig.json` beats `[tool.pyright]`. If both exist, the pyproject table is silently ignored, even when `pyrightconfig.json` is `{}`. Check for both before editing either. <!-- claim: pyright-config-precedence -->
- `executionEnvironments` entries take `root`, `pythonVersion`, `extraPaths` and per-root rule overrides, so a `scripts/` root can turn `reportMissingImports` off while `src/` keeps it. <!-- claim: pyright-execution-environments-rules -->
- `--pythonpath <python>` (CLI) or `venvPath` + `venv` (config) select the environment. Without them, pyright uses the `python` found on `PATH`.
- `pythonVersion` changes which stdlib names exist: with `3.10`, `from typing import assert_type, reveal_type` is `reportAttributeAccessIssue` ("unknown import symbol"). Import them from `typing_extensions` in probes for projects that support 3.10. <!-- claim: pyright-python-version-typing-imports -->

## Message to rule name

Copy the rule from the trailing `(reportX)` of the message, or from `"rule"` in `--outputjson`. Never write a rule name from memory. <!-- claim: pyright-rule-map -->

| message starts with | rule |
|---|---|
| `Cannot access attribute "x" for class "C"` | `reportAttributeAccessIssue` |
| `"x" is not a known attribute of module "m"` | `reportAttributeAccessIssue` |
| `"x" is unknown import symbol` | `reportAttributeAccessIssue` |
| `Cannot access/assign attribute "x" for class "FunctionType"` | `reportFunctionMemberAccess` (standard+) |
| `"x" is not a known attribute of "None"` | `reportOptionalMemberAccess` |
| `Object of type "None" is not subscriptable` | `reportOptionalSubscript` |
| `Argument of type ... cannot be assigned to parameter` | `reportArgumentType` |
| `Type ... is not assignable to declared type` | `reportAssignmentType` |
| `Type ... is not assignable to return type` | `reportReturnType` |
| `Expected N positional arguments`, `Object of type ... is not callable` | `reportCallIssue` |
| `"__getitem__" method not defined on type` | `reportIndexIssue` |
| `Operator "+" not supported for types` | `reportOperatorIssue` |
| `Function declaration "f" is obscured by a declaration of the same name` | `reportRedeclaration` |
| `Import "m" could not be resolved` | `reportMissingImports` |
| `Instance methods should take a "self" parameter` | `reportSelfClsParameterName` |
| `Type of parameter "cls" must be a supertype of its class` | `reportGeneralTypeIssues` |
| `"int" is not iterable` | `reportGeneralTypeIssues` |

The last two show that `reportGeneralTypeIssues` still exists for messages without a dedicated rule. <!-- claim: pyright-generaltypeissues-remaining -->

## Suppression comments

| comment | effect in pyright |
|---|---|
| `# pyright: ignore[ruleA, ruleB]` | suppresses only those rules on the line |
| `# pyright: ignore` | suppresses everything on the line (basedpyright warns: `reportIgnoreCommentWithoutRule`) |
| `# type: ignore[any-text]` | **blanket ignore for the whole line**: pyright ignores the bracket contents, so a mypy-only `type: ignore[code]` also hides every pyright error on that line <!-- claim: pyright-honors-type-ignore-any-code --> |
| `# type: ignore` at the top of a file | suppresses the whole file |

- `enableTypeIgnoreComments` (default `true`) controls the `type: ignore` handling. Set it to `false` and pyright neither honors nor reports `type: ignore` comments, which is how to keep mypy-only suppressions from hiding pyright errors. <!-- claim: pyright-enable-type-ignore-false -->
- `reportUnnecessaryTypeIgnoreComment` (off by default) reports both unneeded `type: ignore` and unneeded `pyright: ignore` rules. <!-- claim: pyright-honors-type-ignore-any-code -->
- A misspelled rule (`reportPossiblyUnbound` instead of `reportPossiblyUnboundVariable`) does not suppress the error, and with the setting on it is reported as `Unnecessary "# pyright: ignore" rule`. <!-- claim: pyright-wrong-rule-name-not-suppressed -->
- Consequence for multi-checker code: when `enableTypeIgnoreComments` is on and `reportUnnecessaryTypeIgnoreComment` is on, a `# type: ignore[code]` that only mypy needs makes pyright report it as unnecessary. Either turn `enableTypeIgnoreComments` off or accept that pyright treats every `type: ignore` as its own. See `cross-checker.md`.

## Inference differences that change results

| behavior | pyright | mypy | ty |
|---|---|---|---|
| unannotated function return | inferred from the body | `Any` | `Unknown` |
| unannotated parameter at a call site | call-site return inference (`ident(n)` with `n: int` gives `int`) | `Any` | `Unknown` |
| body of an unannotated `def` | checked | skipped (`annotation-unchecked` note) | checked |

<!-- claim: pyright-infers-unannotated-returns --> <!-- claim: pyright-return-inference-mypy-any --> <!-- claim: pyright-return-inference-ty-unknown --> <!-- claim: pyright-checks-untyped-bodies --> <!-- claim: pyright-untyped-body-pyright-errors -->

- "pyright is clean" therefore says nothing about what mypy or ty users see. Annotate every return that callers consume, then `assert_type` it under all checkers.
- `assert_type(1, int)` fails in pyright: the expression is `Literal[1]`. Assert on values whose declared type is what you check (a parameter `n: int`, a call result). <!-- claim: pyright-assert-type-literal -->
- `Unknown` is pyright's name for an implicit `Any` (missing annotation, unresolved import). It behaves like `Any` but only `Unknown` feeds `reportUnknown*`.

## CLI

| need | command |
|---|---|
| machine-readable output | `pyright --outputjson ...`; `generalDiagnostics[].range.start.line` is **0-based**, `summary.errorCount` <!-- claim: pyright-outputjson-zero-based --> |
| specific files only | `pyright path/a.py path/b.py` (CLI paths override `include`) |
| fail on warnings | `--warnings` (warnings alone exit 0 otherwise) <!-- claim: pyright-exit-warnings-only --> <!-- claim: pyright-exit-warnings-flag --> |
| a different config | `-p other.json` |

Exit codes: 0 no errors, 1 errors, 2 fatal error ([command line](https://github.com/microsoft/pyright/blob/main/docs/command-line.md)), 3 config file missing or unparsable, 4 invalid command line. <!-- claim: pyright-exit-bad-config --> <!-- claim: pyright-exit-bad-flag -->

## `--verifytypes` (library completeness)

```bash
PATH="$PWD/.venv/bin:$PATH" pyright --verifytypes mypkg --ignoreexternal
```

- The package must be importable by the `python` on `PATH` (installed, editable install, or `PYTHONPATH`). A package that only sits in the current directory is not found. <!-- claim: pyright-verifytypes-needs-import-path -->
- `--verifytypes` ignores `--pythonpath`: with `--pythonpath .venv/bin/python` it still reports "No py.typed file found" and 0%, while putting the venv first on `PATH` works. "No py.typed file found" plus 0 symbols means a resolution failure, not a missing marker. <!-- claim: pyright-verifytypes-ignores-pythonpath -->
- Public attributes assigned a non-literal value without an annotation (`self.points = list(points)`, `self.scale = float(n)`) are "ambiguous" ("could be inferred differently by type checkers") and count as not known. Literal assignments (`self.count = 0`, `sides = 4`) pass. Annotate the first assignment (`self.points: list[float] = ...`). <!-- claim: pyright-verifytypes-ambiguous-attrs -->
- An `__init__` import without `as` that is not in `__all__` (`from ._impl import helper`) is private and not checked; `from ._impl import area as area` is exported even when `__all__` omits it. <!-- claim: pyright-verifytypes-ambiguous-attrs -->
- Score = known / exported symbols; ambiguous counts against it. Exit 0 only at 100%. `--outputjson` exposes `typeCompleteness.completenessScore` (0 to 1) and `exportedSymbolCounts`. <!-- claim: pyright-verifytypes-complete-json -->
- `--ignoreexternal` stops unknown types from third-party packages lowering the score.

## basedpyright

A pyright fork with stricter defaults; same CLI and config keys plus extras ([docs](https://docs.basedpyright.com/latest/configuration/config-files/)).

| difference | basedpyright default |
|---|---|
| default mode | `recommended` (between strict and `all`); `all` enables every rule |
| `reportAny`, `reportExplicitAny`, `reportUnknown*` | on, as warnings <!-- claim: basedpyright-recommended-defaults --> |
| `failOnWarnings` | on: warnings alone exit 1 <!-- claim: basedpyright-fails-on-warnings --> |
| `enableTypeIgnoreComments` | **false**: `# type: ignore[...]` suppresses nothing <!-- claim: basedpyright-recommended-defaults --> |
| `# pyright: ignore` without a rule | warning `reportIgnoreCommentWithoutRule` <!-- claim: basedpyright-recommended-defaults --> |

- `typeCheckingMode = "standard"` restores pyright behavior: the Any warnings disappear and the run exits 0. <!-- claim: basedpyright-standard-mode-quiet -->
- Baseline for adopting it on an existing codebase: `basedpyright --writebaseline` writes `.basedpyright/baseline.json`; later runs report only new diagnostics. Commit the file and rerun `--writebaseline` after fixing old ones. <!-- claim: basedpyright-baseline -->
- Rule names and comment forms are pyright's, so the message map above applies.
