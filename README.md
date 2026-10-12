# Agent Skills

Practical skills for AI coding agents — focused on performance, architecture, and engineering best practices.

These skills work with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Cursor](https://cursor.com), [GitHub Copilot](https://github.com/features/copilot), and other AI agents that support the [Agent Skills](https://skills.sh/) format.

## Available Skills

| Skill | Description |
|-------|-------------|
| [python-profiling](skills/python-profiling/) | Structured workflow for profiling and optimizing Python code — CPU hotspots, memory usage, and benchmark-driven validation. |
| [porting-py2-to-py3](skills/porting-py2-to-py3/) | Phased methodology for porting a Python 2.7 codebase to Python 3 while the team keeps shipping: target version, dependency strategy, CI gates, agent loops, staged rollout. |
| [removing-dead-code](skills/removing-dead-code/) | Language-neutral removal of dead code and unused dependencies, ordered by the proof each deletion needs, with production coverage across many services. Python reference included. |

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

**References included:** catalog of every 2→3 change classified as mechanical or judgment, tooling and pin tables, per-version removal table, case studies (Instagram, Dropbox, Yelp, Mercurial), plus a py2-idiom census script and a compile gate script.

### removing-dead-code

Deletion ordered by the proof it needs. Guides the agent through unused imports, unreachable code, unreferenced modules, routes and jobs with zero production hits, and unused dependencies, with one removal per commit carrying its evidence. The workflow is language-neutral: tool categories, the dynamic-reference checklist and the multi-service production coverage design. Each language gets a `references/<language>.md` with its tools and commands; Python ships today (vulture, pyflakes, ruff, deptry, coverage.py, py-spy, tombstones), other languages follow the same structure.

**Trigger phrases:** "remove dead code", "is this still used", "unused dependencies", "clean up before migration"

## Who This Is For

- **Developers** optimizing Python applications and services
- **Tech leads** establishing performance baselines and practices
- **Engineering managers** seeking structured approaches to performance work

## Contributing

Contributions are welcome. Each skill lives in its own directory under `skills/` and must include a `SKILL.md` file with valid frontmatter. See `AGENTS.md` for the full specification.

## License

[MIT](LICENSE)
