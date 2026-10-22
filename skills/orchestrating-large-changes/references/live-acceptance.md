# Live acceptance

Tests on fakes prove the logic; only a live run proves the contracts with the real tools.
The orchestrator runs it, one step at a time, in a sandbox the handoff allows.

## Prepared before the run

- **Backup**, proven (integrity check, row counts), with checksums of every file. The run
  reads copies.
- **Snapshot** of the user's resources (workspaces, sessions, PRs, branches, cards, config
  files) in the run directory. The final step compares against it.
- **Sandbox** the run may write to freely, with the other actors scripted (one account
  cannot review its own PR, so a CI workflow acting as a bot opens PRs, requests reviews,
  comments and fails checks on demand). Smoke-test each script before the run.
- **Run prefix** on everything the run creates (`<project>-e2e-<timestamp>-<case>`).

## Rehearsal

The whole acceptance once on an intermediate head (after the product is installable),
while the last tasks run. It finds the environment problems while there is time. Fixes go
through the same loop.

## A case

- One scenario, one fresh resource; never reuse a case's leftovers.
- Ledger line per item: `A/<item>: <command> -> <the output that proves it>`.
- On failure, change one variable at a time (temporary home, fresh workspace, one setting)
  and log the diagnosis before the fix.
- A safety mechanism of the user's tools is not an obstacle: never write the setting that
  disables it. Make the product detect and report it with the command the user runs, prove
  the detection live, log a gap.

## Final acceptance

On the final head, installed from it: every item proven; automation in the state the
handoff says; no run-prefixed resource left, the snapshot fully present, backup checksums
unchanged, `git worktree list` showing only the user's checkouts and the integration
worktree; the report written.
