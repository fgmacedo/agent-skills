# Project setup: config, hooks, CI

Verified with mypy 2.4.0, pyright 1.1.414, basedpyright 1.40.2, ty 0.0.86, ruff 0.16 (October
2026). Config references: mypy <https://mypy.readthedocs.io/en/stable/config_file.html>, pyright
<https://github.com/microsoft/pyright/blob/main/docs/configuration.md>, ty
<https://docs.astral.sh/ty/reference/configuration/>.

## Which Python version each checker assumes

| Checker | Without explicit config |
|---|---|
| mypy | version of the interpreter running mypy |
| pyright | version of the Python environment it resolves (`python` on `PATH`, or `venvPath`/`venv`) |
| ty | **lower bound of `requires-python`**, else the environment |

With `requires-python = ">=3.10"` and no version setting, `from typing import Self` passes mypy
and pyright on a 3.14 interpreter and fails in ty. <!-- claim: setup-ty-requires-python --> Pin the
target explicitly in all three (`python_version`, `pythonVersion`, `python-version`) to the
oldest supported Python, so every checker rejects features the oldest runtime lacks.

## Config precedence and validation

- pyright: `pyrightconfig.json` wins over `[tool.pyright]`; the pyproject table is ignored
  entirely when the JSON file exists. <!-- claim: setup-pyrightconfig-wins -->
- ty: `ty.toml` wins over `[tool.ty]`. <!-- claim: setup-ty-toml-wins --> An unknown key is a hard failure (`ty failed ... is not a
  valid pyproject.toml`, exit 2); mypy and pyright only warn about unknown options and keep
  checking. <!-- claim: setup-unknown-keys --> Always run `ty check` once after editing its config.
- mypy: the first file found wins, no merging: `mypy.ini`, `.mypy.ini`, `pyproject.toml`
  (`[tool.mypy]`), `setup.cfg` (`[mypy]`). A stray `mypy.ini` silently disables the pyproject
  table. Set `warn_unused_configs = true` so override sections that match no module are
  reported.

## Side by side: gradual project with one strict package

<!-- claim: setup-sample-config -->
```toml
[project]
requires-python = ">=3.12"

[tool.mypy]
python_version = "3.12"
files = ["src", "tests"]
mypy_path = "src"
warn_unused_configs = true
warn_unused_ignores = true
warn_redundant_casts = true
enable_error_code = ["ignore-without-code", "redundant-expr", "truthy-bool", "possibly-undefined"]

[[tool.mypy.overrides]]          # strict for one package: list the flags (see mypy.md)
module = "app.core.*"
disallow_untyped_defs = true
disallow_incomplete_defs = true
disallow_any_generics = true
warn_return_any = true

[tool.pyright]
include = ["src", "tests"]
pythonVersion = "3.12"
typeCheckingMode = "standard"    # basic | standard (default) | strict
strict = ["src/app/core"]        # paths checked in strict mode
reportUnnecessaryTypeIgnoreComment = "error"
venvPath = "."
venv = ".venv"

[tool.ty.environment]
python-version = "3.12"
root = ["src"]

[tool.ty.src]
include = ["src", "tests"]

[tool.ty.rules]
possibly-unresolved-reference = "error"
unused-ignore-comment = "error"
unused-type-ignore-comment = "error"

[[tool.ty.overrides]]
include = ["tests/**"]
[tool.ty.overrides.rules]
unresolved-attribute = "ignore"
```

ty has no strict mode and no missing-annotation rules: an unannotated `def f(x)` passes ty with
every default rule, while pyright strict reports `reportMissingParameterType`.
<!-- claim: setup-ty-no-annotation-rules --> Enforce annotations with mypy
(`disallow_untyped_defs`), pyright strict, or ruff `ANN`.

## Running against the project environment

| Checker | Point it at `.venv` |
|---|---|
| mypy | run the venv's mypy, or `--python-executable .venv/bin/python` / `python_executable` |
| pyright | `venvPath = "."` + `venv = ".venv"`, `--pythonpath .venv/bin/python`, or run inside the activated venv |
| ty | finds `./.venv` or `VIRTUAL_ENV` automatically; `--python .venv` or `environment.python` |
| `pyright --verifytypes` | only the interpreter on `PATH` / `PYTHONPATH` (see `library-authoring.md`) |

With uv: `uv run mypy`, `uv run pyright`, `uv run ty check` (add them to a dev dependency group)
or `uvx ty check` for a tool not in the project. A global uv setting such as `exclude-newer` can
make `uv run` re-resolve and rewrite `uv.lock`; use `uv run --frozen` in hooks and CI.

## pre-commit hooks

| Checker | repo | hook id | Note |
|---|---|---|---|
| mypy | `https://github.com/pre-commit/mirrors-mypy` | `mypy` | isolated venv; default args `--ignore-missing-imports --scripts-are-modules` hide unresolved third-party imports; add typed deps to `additional_dependencies`; receives only changed filenames |
| pyright | `https://github.com/RobertCraigie/pyright-python` | `pyright` | isolated venv; set `venvPath`/`venv` so it sees project deps |
| basedpyright | `https://github.com/DetachHead/basedpyright-prek-mirror` | `basedpyright` | tags have no `v` prefix (`rev: 1.40.2`) |
| ty | `https://github.com/astral-sh/ty-pre-commit` | `ty` | runs `uv check --ty-version=<pinned>` on the whole project (`pass_filenames: false`); resolves deps from `pyproject.toml`, ignores `additional_dependencies`; may create `.venv` or update `uv.lock` unless `args: [--isolated]` |

Sources: each repo's README and `.pre-commit-hooks.yaml`. Because the mypy and pyright mirrors
run in their own environments, many projects prefer a `local` hook that runs the project's
pinned tool on the whole tree:

```yaml
- repo: local
  hooks:
    - id: mypy
      name: mypy
      entry: uv run --frozen mypy
      language: system
      types: [python]
      pass_filenames: false
```

`pass_filenames: false` matters for type checkers: a change in `a.py` can break `b.py`.

## GitHub Actions

```yaml
jobs:
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: astral-sh/setup-uv@1c37ad07a6a961277cf70c0d37d6f313000f5884  # v10.3.0
      - run: uv sync --frozen
      - run: uv run --frozen mypy
      - run: uv run --frozen pyright
      - run: uv run --frozen ty check --output-format github
```

`astral-sh/setup-uv` publishes full version tags only (no floating `v10`); its README pins by
commit SHA. pyright and ty print annotations natively (`pyright --outputjson` for tooling, ty
`--output-format github|gitlab|junit`); mypy has `-O json` for machine-readable output.

## ruff rule families that complement checkers

| Family | What it adds | Notable rules |
|---|---|---|
| `ANN` | missing annotations (ty has none) | ANN001 args, ANN201 public returns, ANN204 special methods, ANN401 `Any` in signatures |
| `UP` | modern syntax for the configured `target-version` | UP006/UP035 builtin generics, UP007/UP045 `X \| Y`, UP040 `type` aliases, UP046/UP047 PEP 695 generics, UP037 needless quotes |
| `TC` | imports used only in annotations go under `TYPE_CHECKING` | TC001-TC003 move, TC004 runtime use inside the block, TC006 quote `cast` types, TC008 quoted aliases |
| `FA` | `from __future__ import annotations` when needed | FA100, FA102 |
| `PYI` | stub and annotation hygiene | PYI016 duplicate union members, PYI019 use `Self`, PYI034 `__new__`/`__enter__` should return `Self` |

ruff's `target-version` should match the oldest supported Python, the same value given to the
checkers, or `UP` will rewrite to syntax the oldest runtime cannot evaluate.
