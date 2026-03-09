# Agent Skills

Practical skills for AI coding agents — focused on performance, architecture, and engineering best practices.

These skills work with [Claude Code](https://docs.anthropic.com/en/docs/claude-code), [Cursor](https://cursor.com), [GitHub Copilot](https://github.com/features/copilot), and other AI agents that support the [Agent Skills](https://skills.sh/) format.

## Available Skills

| Skill | Description |
|-------|-------------|
| [python-profiling](skills/python-profiling/) | Structured workflow for profiling and optimizing Python code — CPU hotspots, memory usage, and benchmark-driven validation. |

## Installation

### Install all skills

```bash
npx skills add fgmacedo/agent-skills
```

### Install a specific skill

```bash
npx skills add fgmacedo/agent-skills --skill python-profiling
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

## Who This Is For

- **Developers** optimizing Python applications and services
- **Tech leads** establishing performance baselines and practices
- **Engineering managers** seeking structured approaches to performance work

## Contributing

Contributions are welcome. Each skill lives in its own directory under `skills/` and must include a `SKILL.md` file with valid frontmatter. See `AGENTS.md` for the full specification.

## License

[MIT](LICENSE)
