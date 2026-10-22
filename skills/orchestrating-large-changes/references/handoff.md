# Handoff template

The only thing the orchestrator is sure to read. Commit it next to the plan. Everything in it
comes from the plan and the user's answers to `risk-questions.md`.

~~~markdown
# <change>: run until done

You are the orchestrator and integrator of <change>: worktree <path>, branch <branch>. The
user is away until <when> and will only do a final validation; nobody answers questions.
Run as a loop whose exit is the final acceptance, all green. Follow the
orchestrating-large-changes skill.

Read: <plan-dir>/criteria.md (binding), <plan-dir>/core.md, the task files as you dispatch.
Run directory (outside every worktree): <run-dir>. Times in <zone>.

## How to work
- Harden the plan first, then run the lanes. Multi-agent orchestration is opted in: <tools>.
- Never stop to ask. Decide by the criteria and the user's decisions, log a ruling with its
  cost, fix and retry. Changing the plan is allowed; violating the criteria, the decisions
  <ids> or the rules below is not.
- Reserved: <list>. When one blocks a case: log a gap, skip the case, continue, report it.
- Remove every worktree and branch you or your delegates created, except yours, once merged.

## You may
- <install/uninstall/restart commands, as often as validation needs>
- <create and remove resources named prefix*>
- <sandbox: name, what may be written there, the commands that drive each fake actor>
- <the live scenarios the final acceptance must include>

## You must never
- <write outside allowed-resources>
- <close, rename, move or delete the user's things; compare against snapshot>
- <change config or homes except through installer, which backs up each file first>
- <kill processes you did not start>
- <write the backup at path; migrations read a copy; checksums compared at the end>
- <weaken a safety mechanism of the user's tools; detect and report it>

## Done
- every acceptance item proven by a command whose output is in the ledger;
- the integration branch holds all the work, merged and green; no delegate worktree or branch;
- <installed and running from the branch's build>;
- automation left <paused/resumed>, with the status saying how to change it;
- the report at <report-path>; <where the user looks first> says done and where it is.
~~~

Launch the orchestrator in a fresh session in its own worktree, the handoff as the whole
prompt, with a self-paced loop if the harness has one (`/loop Read <handoff> and follow it
until its definition of done holds.`). Confirm the first turn was accepted before leaving.
