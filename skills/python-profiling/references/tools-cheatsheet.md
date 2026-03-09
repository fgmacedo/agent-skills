# Profiling Tools Cheatsheet

Quick reference for each profiling tool. All commands assume `uv` as the package
manager — adapt if the project uses pip/poetry/etc.

---

## cProfile (stdlib — no install needed)

**Best for:** Quick overview of function-level CPU time. Available everywhere,
zero setup.

### From the command line

```bash
# Profile a script, sort by cumulative time
uv run python -m cProfile -s cumtime script.py

# Save to .prof file for later analysis
uv run python -m cProfile -o /tmp/profile.prof script.py
```

### From code

```python
import cProfile
import pstats

# Quick one-liner
cProfile.run('my_function()', sort='cumulative')

# With more control
profiler = cProfile.Profile()
profiler.enable()
my_function()
profiler.disable()

stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # top 20 functions
```

### With pytest-benchmark

```bash
# Per-benchmark cProfile breakdown
uv run pytest <file>::<test> -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-cprofile=cumtime --benchmark-cprofile-top=20

# Dump .prof files for visualization
uv run pytest <file>::<test> -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-cprofile=cumtime \
    --benchmark-cprofile-dump=/tmp/bench
```

### Reading the output

| Column | Meaning |
|--------|---------|
| `ncalls` | Number of calls (two numbers = primitive/total for recursive) |
| `tottime` | Time spent in this function only (excluding subfunctions) |
| `percall` | `tottime / ncalls` |
| `cumtime` | Time spent in this function AND all subfunctions |
| `percall` | `cumtime / ncalls` |

**Look at `cumtime` first** to find the call trees that matter, then `tottime`
to find where time is actually spent (not just passed through).

---

## line_profiler

**Best for:** Per-line CPU time within a specific function. Use after cProfile
identifies the hot function.

**Install:** `uv pip install line_profiler`
**Python:** 3.8+

### Usage with decorator

```python
# Add @profile decorator to target functions (line_profiler injects it)
@profile
def hot_function():
    ...
```

```bash
uv run kernprof -l -v script.py
```

### Usage without modifying code

```python
from line_profiler import LineProfiler

lp = LineProfiler()
lp.add_function(target_function)
lp.enable()
target_function()
lp.disable()
lp.print_stats()
```

### Reading the output

```
Line #  Hits    Time    Per Hit  % Time  Line Contents
     5  1000    5000    5.0      50.0    result = expensive_call()
     6  1000    2000    2.0      20.0    data.append(result)
```

Focus on `% Time` — the lines with the highest percentage are your targets.

---

## py-spy

**Best for:** Sampling profiler that attaches to running processes. No code
changes, minimal overhead. Great for production profiling.

**Install:** `uv pip install py-spy`
**Python:** 3.7+ (CPython and PyPy)
**Note:** May need `sudo` on some systems (ptrace permissions).

### Commands

```bash
# Record a flamegraph (SVG)
uv run py-spy record -o /tmp/profile.svg -- python script.py

# Top-like live view
uv run py-spy top -- python script.py

# Attach to running process
uv run py-spy record -o /tmp/profile.svg --pid <PID>

# Sample rate (default 100 Hz)
uv run py-spy record -r 200 -o /tmp/profile.svg -- python script.py

# Include native (C) frames
uv run py-spy record --native -o /tmp/profile.svg -- python script.py
```

### Output formats

- `--format flamegraph` (default) — Interactive SVG flamegraph
- `--format speedscope` — Open in https://speedscope.app
- `--format raw` — Raw samples for custom analysis

---

## tracemalloc (stdlib — no install needed)

**Best for:** Quick memory allocation tracking. Shows where memory is allocated,
not just how much is used.

### Usage

```python
import tracemalloc

tracemalloc.start()

# ... run your code ...

snapshot = tracemalloc.take_snapshot()
stats = snapshot.statistics('lineno')  # or 'filename', 'traceback'

print("Top 10 memory allocations:")
for stat in stats[:10]:
    print(stat)
```

### Comparing snapshots (finding leaks)

```python
tracemalloc.start()

snapshot1 = tracemalloc.take_snapshot()
# ... run code that might leak ...
snapshot2 = tracemalloc.take_snapshot()

stats = snapshot2.compare_to(snapshot1, 'lineno')
print("Top 10 memory increases:")
for stat in stats[:10]:
    print(stat)
```

### Current/peak usage

```python
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024:.1f} KB, Peak: {peak / 1024:.1f} KB")
```

---

## memray

**Best for:** Detailed memory profiling with flamegraphs, allocation tracking,
and leak detection. The most comprehensive Python memory profiler.

**Install:** `uv pip install memray`
**Python:** 3.7+ (CPython only, Linux and macOS)

### Commands

```bash
# Record allocations
uv run memray run -o /tmp/mem.bin script.py

# Generate flamegraph
uv run memray flamegraph /tmp/mem.bin -o /tmp/mem.html

# Summary table
uv run memray summary /tmp/mem.bin

# Allocation stats
uv run memray stats /tmp/mem.bin

# Tree view (like a call tree for allocations)
uv run memray tree /tmp/mem.bin

# Track with pytest
uv pip install pytest-memray
uv run pytest --memray tests/
```

### Live mode

```bash
# Terminal-based live view (like top for memory)
uv run memray run --live script.py
```

### Tracking leaks

```bash
# Show allocations not freed by end of recording
uv run memray flamegraph --leaks /tmp/mem.bin -o /tmp/leaks.html
```

---

## scalene

**Best for:** Combined CPU + memory + GPU profiling in one tool. Shows CPU time,
memory allocations, and copy volume per line.

**Install:** `uv pip install scalene`
**Python:** 3.8+ (CPython)

### Commands

```bash
# Profile a script (opens browser report)
uv run scalene script.py

# CLI output only
uv run scalene --cli script.py

# Profile specific functions/files
uv run scalene --cpu-only script.py
uv run scalene --memory-only script.py

# Reduced overhead mode
uv run scalene --reduced-profile script.py
```

### With pytest

```bash
uv run scalene --- -m pytest tests/test_specific.py
```

---

## snakeviz

**Best for:** Visualizing `.prof` files from cProfile as interactive sunburst
diagrams in the browser.

**Install:** `uv pip install snakeviz`

### Usage

```bash
# Open interactive visualization
uv run snakeviz /tmp/profile.prof

# Specify port
uv run snakeviz -p 8080 /tmp/profile.prof

# Server mode (don't open browser)
uv run snakeviz -s /tmp/profile.prof
```

---

## pytest-benchmark

**Best for:** Structured, reproducible benchmarking integrated with pytest.
Compare before/after with statistical rigor.

**Install:** `uv add --group dev pytest-benchmark` (usually a project dependency)

### Key commands

```bash
# Run benchmarks and save snapshot
uv run pytest <file> -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-save=<label>

# Compare against a saved baseline
uv run pytest <file> -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-compare=<run-number>

# Compare two saved snapshots (no test run)
uv run pytest-benchmark compare \
    .benchmarks/<platform>/<run1>*.json \
    .benchmarks/<platform>/<run2>*.json \
    --columns=mean,stddev --sort=name --group-by=name

# Export JSON for scripted analysis
uv run pytest <file> -m slow \
    --benchmark-only --benchmark-disable-gc \
    --benchmark-json=/tmp/bench.json
```

### Writing good benchmarks

```python
import pytest

@pytest.mark.slow()
class TestPerformance:
    def test_operation(self, benchmark):
        # Setup OUTSIDE the benchmark
        obj = setup_object()

        # Only measure the operation itself
        benchmark.pedantic(
            obj.operation,
            args=(arg1, arg2),
            rounds=10,        # Number of measurement rounds
            iterations=1000,  # Calls per round
        )
```

**Why `pedantic()`?** The simpler `benchmark(fn)` auto-calibrates rounds and
iterations, which can produce inconsistent results across runs. `pedantic()`
gives explicit control, making comparisons more reliable.

### Reading comparison output

```
Name                    Min      Max      Mean     StdDev   Rounds
test_operation (0001)   1.2ms    1.5ms    1.3ms    0.1ms    10
test_operation (0002)   0.8ms    1.0ms    0.9ms    0.05ms   10
                                          ^^^^
                                    30% improvement
```

Focus on **Mean** and **StdDev**. An improvement smaller than 2x the StdDev is
likely noise. Compare against the baseline `Mean`, not `Min`.

---

## Tool compatibility matrix

| Tool | Python | OS | Install | Overhead | Modifies code? |
|------|--------|----|---------|----------|----------------|
| cProfile | 3.x | All | stdlib | Medium | Optional |
| line_profiler | 3.8+ | All | pip | High | Yes (decorator) or No (API) |
| py-spy | 3.7+ | All | pip | Very low | No |
| tracemalloc | 3.4+ | All | stdlib | Medium | Yes (start/stop) |
| memray | 3.7+ | Linux/macOS | pip | Low | No |
| scalene | 3.8+ | All | pip | Low | No |
| snakeviz | 3.x | All | pip | N/A | N/A (viewer) |
| pytest-benchmark | 3.8+ | All | pip | N/A | Yes (test code) |
