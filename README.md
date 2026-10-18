# Agent Skills

Practical skills for AI coding agents — focused on performance, architecture, and engineering best practices.

These skills work with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Cursor](https://cursor.com), [GitHub Copilot](https://github.com/features/copilot), and other AI agents that support the [Agent Skills](https://skills.sh/) format.

## Available Skills

| Skill | Description |
|-------|-------------|
| [python-profiling](skills/python-profiling/) | Structured workflow for profiling and optimizing Python code — CPU hotspots, memory usage, and benchmark-driven validation. |
| [porting-py2-to-py3](skills/porting-py2-to-py3/) | Phased methodology for porting a Python 2.7 codebase to Python 3 while the team keeps shipping: target version, dependency strategy, CI gates, agent loops, staged rollout. |
| [removing-dead-code](skills/removing-dead-code/) | Language-neutral removal of dead code and unused dependencies, ordered by the proof each deletion needs, with production coverage across many services. Python reference included. |
| [python-typing](skills/python-typing/) | Static typing with mypy, pyright, basedpyright and ty: fixing checker errors, making checkers agree, typing dynamic code, suppressions, configuration and typed libraries. |
| [refactoring-python](skills/refactoring-python/) | Safe, incremental refactoring and modernization of Python code: characterization tests first, one named transformation per commit, ports only where a dependency is external, idiomatic Python as the definition of done. |
| [orchestrating-large-changes](skills/orchestrating-large-changes/) | One orchestrating agent delivers a large plan through parallel subagents: risk settled with the user once, after the plan, then an unattended run with rulings, integration, live acceptance in a sandbox and a report. |

## Installation

### Install all skills

```bash
npx skills add fgmacedo/agent-skills
```

### Install a specific skill

```bash
npx skills add fgmacedo/agent-skills --skill python-profiling
npx skills add fgmacedo/agent-skills --skill porting-py2-to-py3
npx skills add fgmacedo/agent-skills --skill removing-dead-code
npx skills add fgmacedo/agent-skills --skill refactoring-python
npx skills add fgmacedo/agent-skills --skill orchestrating-large-changes
```

### List available skills

```bash
npx skills add fgmacedo/agent-skills --list
```

> See the [skills CLI documentation](https://skills.sh/docs/cli) for more options, including global install (`-g`) and agent targeting (`-a claude-code`).

## Skill Details

### python-profiling

A measurement-driven workflow for making Python code faster and leaner. Guides the agent through:

1. **Understanding the project** — Python version, package manager, existing benchmarks
2. **Establishing a baseline** — pytest-benchmark snapshots or ad-hoc cProfile runs
3. **Identifying bottlenecks** — Decision tree for choosing the right profiling tool (cProfile, line_profiler, py-spy, memray, scalene, tracemalloc)
4. **Optimizing one change at a time** — Common patterns ranked by impact and safety
5. **Deep investigation** — Visual profiling with flamegraphs, memory leak detection

**Trigger phrases:** "make this faster", "profile this code", "reduce memory usage", "find bottlenecks", "this is slow", "optimize performance"

**Tools covered:** cProfile, line_profiler, py-spy, tracemalloc, memray, scalene, snakeviz, pytest-benchmark

### porting-py2-to-py3

A phased workflow for moving a Python 2.7 codebase to Python 3 without a long-lived branch. Guides the agent through:

1. **Safety net**: lockfile of what production really runs, coverage gate, golden tests for hashes, tokens and IDs, a one-day spike on the target interpreter
2. **Parseable first**: the syntax-only `futurize --stage1` fixers, so Python 3 tooling can read the code while it still runs on 2.7
3. **Shrink the surface**: hands off to `removing-dead-code`
4. **Modernize on 2.7**: `six` shims, dependency upgrades to the last py2-compatible versions, `python2 -3 -Werror` runs
5. **Ratchet**: a Python 3 CI job with a known-failures list that only moves forward, and a symptom-to-fix table for bytes/str, views, ordering and pickles
6. **Cutover and cleanup**: two images per commit, per-workload switch, cache namespacing, then `pyupgrade`/ruff `UP`

**Trigger phrases:** "port to Python 3", "Python 2.7", "futurize", "2to3", "six", "unicode_literals", "basestring", "which Python version should we target"

**References included:** catalog of every 2→3 change classified as mechanical or judgment, tooling and pin tables, per-version removal table, case studies (Instagram, Dropbox, Yelp, Mercurial), plus a py2-idiom census script, a compile gate script and an uncovered-risk-lines script that turns a coverage report into the manual review list.

### removing-dead-code

Deletion ordered by the proof it needs. Guides the agent through unused imports, unreachable code, unreferenced modules, routes and jobs with zero production hits, and unused dependencies, with one removal per commit carrying its evidence. The workflow is language-neutral: tool categories, the dynamic-reference checklist and the multi-service production coverage design. Each language gets a `references/<language>.md` with its tools and commands; Python ships today (vulture, pyflakes, ruff, deptry, coverage.py, py-spy, tombstones), other languages follow the same structure.

**Trigger phrases:** "remove dead code", "is this still used", "unused dependencies", "clean up before migration"

### python-typing

Makes an agent fix Python typing problems so that every configured checker (mypy, pyright,
basedpyright, ty) sees precise types at the call sites users write:

1. **Detect** how the project really runs its checkers (config, pre-commit, CI, target Python per checker)
2. **Baseline** diagnostics, then **classify** each error (bug, loose annotation, dynamic pattern, divergence, stub gap, config)
3. **Fix** with a ladder from plain annotations to `TYPE_CHECKING`-only declarations, stubs, a single `cast`, and narrow suppressions
4. **Prove** the result with `assert_type` probes under every checker, and finish with no unused suppressions

References cover per-checker behavior, a verified cross-checker suppression matrix and divergence catalog, recipes for
descriptors, metaclasses, decorators, ParamSpec, generic defaults, `dataclass_transform`, TypedDict and mixins, PEP
version gating, library authoring (`py.typed`, `--verifytypes`) and project setup. Every non-obvious fact is backed by an
executable probe in [`claims/python-typing/`](claims/python-typing/).

**Trigger phrases:** "reveal_type shows Any", "decorator loses the signature", `type: ignore`, `[attr-defined]`,
`reportAttributeAccessIssue`, `unresolved-attribute`, "make mypy strict", "adopt ty"

### refactoring-python

Refactoring as a sequence of reviewable commits. Guides the agent through:

1. **Map the target**: a smell census (long functions, parameter counts, nesting, god modules, I/O reached outside adapters, duplicated bodies) named with Fowler's and Kerievsky's catalog and the review lenses (cohesion, DRY, minimum shared context)
2. **Pin behavior first**: characterization tests of the entry point, including what it mutates, writes and raises; golden masters; an oracle comparison when replacing an algorithm
3. **Plan one transformation per commit**: Beck's tidyings, Fowler's moves, Kerievsky's patterns only with two real variants; a subject with "and" is two commits
4. **Execute the loop**: mechanics from the catalog, suite green at every commit, revert on red, stage by path so tests never ride in a `refactor:` commit
5. **Boundaries where they pay**: a port for I/O and proven variation, a parameter for the clock, nothing for "might vary someday"; the domain module importable with the dependency blocked; a boundary test
6. **Pythonic pass**: dataclasses, enums, pathlib, comprehensions, context managers, each with its "behavior changes when" note and a grep that proves the idiom covers the module
7. **Verify and report**: `check_commits.py` (every commit typed and green, no mixed commits, characterization before the first change), then a PR body that separates structure from behavior

**Trigger phrases:** "refactor this", "modernize", "make it testable", "make it pythonic", "split this module", "this is a god class", "copy-pasted logic", "extract into a service", "hexagonal", "ports and adapters", "characterization test", "tidy first"

**Claims:** the Python facts the skill states (patch targets after a move, dataclass hashability, enum string values, import cycles, set ordering) run as executable probes in [`claims/refactoring-python/`](claims/refactoring-python/).

### orchestrating-large-changes

A method for delivering a change too large for one context, with one agent as orchestrator and integrator. Guides the agent through:

1. **Plan for lanes**: success criteria an agent can check, a dependency graph, waves, a lane table where each task owns its files, contracts written in full, an integration check per wave
2. **Settle risk once, after the plan**: a checklist of the questions only the user can answer (blast radius, live tests, data, the user's own resources, safety mechanisms, reserved decisions), asked in one message with defaults, written into a handoff with binding rules and a definition of done
3. **Harden the plan**: an adversarial review against the code before the first delegation
4. **Run the waves**: an implementer per task in its own worktree, review and fix rounds, merges in task order, the gate after every wave, worktrees removed as soon as they merge
5. **Rule, do not ask**: `Ruling: what - why - cost if wrong` in a ledger that survives context compaction; reserved items are skipped and reported, never bypassed
6. **Rehearse and accept live**: a sandbox with scripted actors, run-prefixed resources, one variable per diagnosis, evidence per item
7. **Progress at a glance**: `scripts/progress.py` keeps one state file synced from the plan's dependency graph, prints a terminal board (bars per release, tasks by dependency level, what is held and next) at the end of every loop turn, and generates the report's Mermaid graph and task table linked to the plan
8. **Final review, cleanup and report**: what shipped, evidence, every ruling, gaps, the user's validation and rollback steps

When the result is pull requests in several repositories and Orca is present, the orchestrator delegates one sub-orchestrator per repository as an Orca supervised worker; each runs the same method on its slice and negotiates contract changes with the parent through Orca messages. In one repository, plain subagents and agent teams are enough.

Composes with the `superpowers` skills (writing-plans, subagent-driven-development, requesting-code-review, using-git-worktrees, finishing-a-development-branch) and works in a reduced form without them.

**Trigger phrases:** "run this while I'm away", "until Monday", "orchestrate", "delegate to subagents", "agent teams", "parallel lanes", "handoff", "integration branch", "live acceptance"

## Who This Is For

- **Developers** optimizing Python applications and services
- **Tech leads** establishing performance baselines and practices
- **Engineering managers** seeking structured approaches to performance work

## Contributing

Contributions are welcome. Each skill lives in its own directory under `skills/` and must include a `SKILL.md` file with valid frontmatter. See `AGENTS.md` for the full specification.

## License

[MIT](LICENSE)
