# Planning for parallel lanes

A plan for one implementer lists tasks. A plan for parallel implementers also says who owns
which file, what each task codes against before its producer merges, and when the
orchestrator merges and checks. Add an "Execution shape" section to the plan with the four
parts below. With superpowers, write the plan with superpowers:writing-plans and add this
section; without it, the tasks still need exact files, interfaces, test commands and
acceptance per task.

## 1. Success criteria first

Before tasks, write the criteria the result must meet, each checkable by a command or a test
an agent can run (an architecture test, a grep that must be empty, a live scenario). Number
them (C1, C2, ...). They are the authority every ruling in the run cites. A criterion only a
person can judge is not one; rewrite it or move it to the report's "validate" list.

## 2. Dependency graph

One node per task, an edge from producer to consumer. Draw it (Mermaid in Markdown is fine)
and state the tasks nothing depends on. Order by value to the user; the graph only says what
cannot start yet.

## 3. Waves and the lane table

A wave is the set of tasks whose inputs are merged. One row per task:

| Task | Brief | Contract | May touch | Shared |
|---|---|---|---|---|
| T6 | one versioned API; every client on it | consumes `pr.Ref` (T2's first commit); produces `api.*`, `api/client` | `internal/api/`, `internal/daemon/`, `internal/cli/` (type references only) | `internal/cli/serve.go` with T27: T6 rewrites daemon types, T27 agent references |

- **May touch** is the complete list of paths the implementer may edit, plus tests beside
  them. Two tasks in one wave never share a path unless the Shared column splits it.
- **Shared** names the file and the part each task owns (functions, fields, lines). Prefer
  splitting ownership of a shared file over serializing the tasks.
- **Contract** names the exact types and signatures consumed and produced. Write the
  interfaces in full in the plan, so a consumer codes against them before the producer
  merges. A consumer in the same wave branches from the producer's first commit, which
  holds only the types.
- **Merge order** inside a wave is task order, producers first.
- A task whose inputs are all merged may start before its wave (an early start). Log it as
  a ruling with its cost (a rebase).

## 4. Integration check per wave

The commands the orchestrator runs on the integration branch after each wave's merges, all
must pass before the next wave starts:

1. the full gate (build, full test suite, lint);
2. the criteria tests that exist so far;
3. wave-specific checks: greps that prove an old path is gone, a package no longer imports
   another, a removed name has no references.

## Phases

A phase boundary exists only where an irreversible consequence must be verified before going
on (a data migration on the user's store, an install that changes the user's homes, the
first write to a remote). Refactors, contracts, adapters behind a switch and test scaffolding
are steps inside the delivery that uses them. Where a boundary exists, the plan names the
check that clears it, and the orchestrator runs it; no boundary waits on a person.

## Plan review before execution

Before the first delegation, one reviewer on the most capable model attacks the plan against
the code. Dispatch prompt:

~~~text
You are hardening an implementation plan before parallel subagents execute it, with no
person available until it is done. Work read-only in <worktree>; do not touch anything
outside it.

Read: <criteria-doc>, <spec>, <plan> (all of it), <handoff>, and the code as needed.

Attack the plan against the real code: names and signatures that do not exist or differ,
task boundaries that leave a file to two tasks without a split, waves whose tasks are not
independent, contracts a consumer cannot code against, steps whose test cannot fail, checks
that do not prove their criterion, safety rules a step would break, and behavior the spec
requires that no task delivers.

Write findings to <workspace>/plan-review.md as Critical / Important / Minor, each with the
plan line, the code location, and the fix. Reply with the counts and the path only.
~~~

The orchestrator applies what holds up to the plan in one commit and logs a ruling for each
finding it rejects.
