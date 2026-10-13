# Safety net: pin behavior before the first move

A refactoring is only safe when a test would fail if behavior changed. For code that has
no tests, the first commit writes the tests that describe what it does today, bugs
included. That is a characterization test (Feathers): it pins, it does not judge.

## Characterization test recipe

1. **Pick the entry point** callers use (`generate_statement(customer, period)`), not the
   helpers you are about to extract. The test must survive the refactoring.
2. **Call it with realistic inputs** covering each branch the code has: every type code,
   empty collections, the boundary values the code compares against (`>= 12`, `> 250`),
   `None` where the code checks it.
3. **Record what it returns** by running it, and paste the result as the expected value.
   A golden string is fine; a derived expectation (`round(x, 2)`) is not: it would encode
   your guess, not the behavior.
4. **Record the side effects**: arguments mutated (`customer["last_statement_total"]`,
   a key popped), rows written, files touched, logs emitted, calls made to collaborators
   (capture with a fake that records). The mutation of an argument is the one most often
   missed and most often relied on by callers.
5. **Record the failure modes**: which exception type on bad input (`KeyError` vs
   `ValueError`), what happens on an empty list, what `None` produces.
6. **Commit** as `test(scope): characterize <entry point>`, before any structural commit.

```python
def test_statement_updates_the_customer_record():
    customer = {"name": "Acme", "plan": "pro", "items": [], "pending_credit": 5.0}
    generate_statement(customer, date(2024, 11, 1))
    assert "pending_credit" not in customer
    assert customer["last_statement_total"] == -5.0


def test_unknown_plan_raises_key_error():
    with pytest.raises(KeyError):
        generate_statement({"name": "x", "plan": "gold", "items": []}, date(2024, 1, 1))
```

### When the characterization test finds a bug

Pin it as a strict expected failure with the issue reference, and do not fix it in the
refactoring PR. Fixing it is a `fix:` commit with its own test, after the structure
work, or a separate PR.

```python
@pytest.mark.xfail(strict=True, reason="find_source_id answers 1 for every recorte, #123")
def test_source_id_follows_the_diario():
    ...
```

### When the test is flaky

The code has hidden nondeterminism: a `set` or dict-of-sets iterated into output
(order changes with `PYTHONHASHSEED`), `datetime.now()`, `random`, a cache that survives
between tests, thread timing. Pin the nondeterministic input (sort before asserting,
inject `today`, seed `random`), or the refactoring will "break" tests that were never
stable.

## Golden masters and approval tests

For large outputs (rendered reports, exported files, HTML), store the output in
`tests/golden/<case>.txt` and compare. The update path must be explicit
(`pytest --update-golden`), never automatic. Diff the golden on failure; a reviewer reads
the diff as the behavior change. Normalize what is not behavior (timestamps, run ids)
before comparing.

## Coverage as a gate on the touched surface

```bash
coverage run -m pytest tests/test_statement.py
coverage report --include='billing/statement.py' --show-missing
```

Every line you are about to move should be executed by the characterization test. A
missed branch is a branch you will change without noticing. Aim at the touched modules,
not at a repo-wide number.

## Import-on-its-own test

Splitting a module into a package creates cycles that only close in one import order; a
suite whose `conftest` imports the package first never sees them.

```python
def test_rules_import_on_their_own():
    proc = subprocess.run([sys.executable, "-c", "import app.billing.rules"],
                          capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr[-2000:]
```

Add one per module you create or move. `scripts/check_boundaries.py` has it built in.

## Equivalence during Parallel Change

When replacing an algorithm or a library, keep the old implementation beside the new one
and let `hypothesis` compare them on generated inputs; the old one is the oracle.

```python
from hypothesis import given, strategies as st

@given(st.lists(st.decimals(min_value=0, max_value=10_000, places=2)))
def test_new_total_matches_old(amounts):
    assert new_total(amounts) == old_total(amounts)
```

Delete the old one, and the property, in the contract step.

## What the suite must do between commits

- Run the subset that covers the touched modules after every step; run the full suite,
  lint, types and the boundary test after every batch of about five commits and before
  pushing.
- Red after a step: revert the step, take a smaller one. Debugging forward on top of a
  refactoring turns the next commit into a behavior change nobody can review.
- The tests you changed in a `refactor:` commit may only rename or move; added or
  removed assertions belong in a `test:` commit, before (characterization) or after
  (tests against the new seam) the structure change. `scripts/check_commits.py` checks
  this.

## Escalate instead of pinning

Some behavior is not yours to pin or to keep: persisted formats (pickles, cache keys,
queue payloads), external contracts (API responses, webhook payloads, CLI flags,
Kubernetes probes bound to a file name), customer-visible numbers. If a characterization
test shows the refactoring would touch one of those, stop and ask with the evidence.
