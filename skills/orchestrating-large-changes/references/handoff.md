# Handoff template

The handoff is the only thing the orchestrator is sure to read. It binds the run. Commit it
next to the plan. Keep it short: what to read, how to work, what is allowed, what is never
allowed, what done is. Everything here comes from the plan and from the user's answers to
`risk-questions.md`.

~~~markdown
# <change>: run until done

You are the orchestrator and integrator of <change>. You own the worktree <path> and the
branch <integration-branch>. The user is away until <when> and will only do a final
validation; nobody answers questions in between. Run as a loop whose exit is the plan's
final acceptance, all green.

## Read first

1. <success-criteria-doc>: the binding authority.
2. <spec>.
3. <plan>: tasks, lanes, waves, acceptance, Global Constraints.

## How to work

- **Harden the plan first.** Before delegating anything, have one reviewer on the most
  capable model attack the plan against the code (names, signatures, task boundaries, lane
  parallelism, behavior, safety). Fix what holds up, in the plan, committed.
- **Delegate, integrate, verify.** Each wave's tasks go to subagents in their own worktrees
  and branches, with the task's brief, contract and the files it may touch. Merge their
  branches into yours, run <gate-command> after each wave, release the next wave only on
  green. Every task gets a review before it merges; the whole branch gets a final review
  before the final acceptance. Multi-agent orchestration is opted in: <tools allowed>.
- **Never stop to ask.** When something fails or the plan is wrong, decide by the success
  criteria and the user's decisions, record it in the ledger as
  `Ruling: <what> - <why> - <cost if wrong>`, fix it and try again. Changing the plan is
  allowed; violating the success criteria, the decisions <ids> or the rules below is not.
- **Reserved.** <reserved-list>. When one of these blocks progress, do not work around it:
  record the gap, skip that case, continue everything else, and name it in the report.
- **Clean up.** Remove every worktree and branch you or your delegates created, except
  yours, once merged.
- **Keep the ledger current** so a resumed session picks up at the first unfinished step
  from the ledger and `git log`, never from memory.

## What you may do in this window

- <install/uninstall/restart commands, as often as validation needs>
- <create and remove resources named <prefix>*>
- <sandbox: name, what may be written there, the commands that drive each fake actor>
- <the live scenarios the final acceptance must include>

## What you must never do

- <no writes outside <allowed-resources>>
- <never close, rename, move or delete the user's <things>; compare against <snapshot>>
- <config and homes change only through <installer>, which backs up each file first>
- <kill only processes you started, by PID>
- <the backup at <path> is read only; migrations read a copy; checksums compared at the end>
- <never weaken a safety mechanism of the user's tools (<examples>); detect and report it>

## Done

- every final acceptance item proven by a command whose output is in the ledger;
- the integration branch holds all the work, merged and green, no leftover worktrees or
  branches from delegates;
- <installed and running from the branch's build, health check clean but the deliberate lines>;
- automation left <paused/resumed> as <rule>, with the status saying how to change it;
- the report at <report-path> (see the report template);
- <architecture docs updated to what shipped>;
- <where the user looks first> says: done, and where the report is.
~~~

## Launching it

Start the orchestrator in a fresh session in its own worktree, with the handoff as the whole
prompt and a self-paced loop if the harness has one, for example
`/loop Read <handoff> and follow it until its definition of done holds. You are the
orchestrator and integrator; the user is away and will not answer questions.`
Confirm the first turn was accepted before you leave.
