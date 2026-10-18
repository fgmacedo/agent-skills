# Live acceptance

Tests on fakes prove the logic. Only a live run proves the contracts with the real tools: the
remote API's actual responses, the installer on real homes, the service manager, the agent
sessions, the other actors. The orchestrator runs it, one step at a time, in a sandbox the
handoff allows.

## Before the run (prepared during the risk questions)

- **Backup.** Take it before launching, prove it (an integrity check, row counts), record
  checksums of every file. The run reads copies, never the backup.
- **Snapshot of the user's resources.** A listing of what exists now (workspaces, sessions,
  open PRs, branches, cards, config files) saved to the scratch directory. The final step
  compares against it: nothing missing, nothing extra but what the handoff allows.
- **Sandbox.** A private repository, project or account the run may write to freely. Script
  the other actors so the run can play them: one account cannot review its own pull request,
  so a CI workflow acting as a bot opens pull requests, requests reviews, pushes follow-ups,
  comments and fails checks on demand. Smoke-test each script before the run.
- **Run prefix.** Every resource the run creates carries it (`<project>-e2e-<timestamp>-<case>`),
  so cleanup removes exactly that and a listing proves nothing else changed.

## Rehearsal

Run the whole acceptance once on an intermediate integration head (after the wave that makes
the product installable), before the last waves finish. It finds the environment problems
(dialogs, permissions, contract surprises) while there is still time to plan fixes, and it
runs in parallel with the remaining implementation. Fix tasks found here go through the same
loop: brief, implementer, review, merge.

## Running a case

- One scenario per case, with a fresh resource each (a new workspace, session or terminal);
  never reuse one case's leftovers in the next.
- Record each command and the trimmed output that proves the item in the ledger, keyed by the
  acceptance item (`A5: ...`).
- When a case fails, diagnose by changing one variable at a time: a temporary home instead of
  the real one, a fresh workspace, a single setting toggled. Write the diagnosis in the
  ledger before the fix.
- A failure caused by a safety mechanism of the user's tools (folder trust, permission
  prompt, credential, signing) is not an obstacle to remove. Do not write the setting that
  disables it. Make the product detect and report it with the command the user can run, prove
  the detection live, and log the case as a gap for the user. This is reserved even when the
  bypass makes the test pass.

## Final acceptance

On the final integration head, installed from it:

1. every criterion and acceptance item proven by a command, its output in the ledger;
2. automation left in the state the handoff says (for example paused everywhere, with the
   health check saying how to resume);
3. cleanup: no run-prefixed resource left, the user's snapshot fully present, backup
   checksums unchanged, `git worktree list` showing only the user's checkouts and the
   integration worktree, no delegate branch left;
4. the report written.

A table in the ledger, one row per item: item, command, result.
