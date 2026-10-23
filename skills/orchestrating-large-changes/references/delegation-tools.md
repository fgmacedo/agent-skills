# Delegation tools, and delivering across repositories

| Situation | Delegate with |
|---|---|
| Pull requests in one repository | Unnamed subagents, one per task, each in its own worktree; resume one by id for fix rounds |
| A delegate needs many turns with its context kept | A named agent team member, whose prompt says to report with SendMessage |
| Pull requests in several repositories, Orca present | One sub-orchestrator per repository as an Orca supervised worker |
| Several repositories, no Orca | Subagents in worktrees of each repository; you own every PR |
| Handing the whole run to an unsupervised session | `orca worktree create --agent` (orca-cli skill), or a new terminal session |

Orca's command reference changes between versions; load it before the first Orca command
(`orca skills get orchestration`, `orca skills get orca-cli`) and prefer it over this file.

## Sub-orchestrators

The method is recursive: each child runs this skill on its repository's slice, with a
handoff the parent writes, and asks the parent, never the user.

**The parent's plan adds**: a plan directory per repository in its run directory (core, tasks of the slice);
cross-repository contracts as code in their owner repository (an API package, wire
fixtures), each consumer's skeleton pinned to it; the order across repositories and how a consumer points at an unmerged producer
(a replace directive, a submodule ref, a package from a branch); the joint acceptance.

**The child's handoff** (`handoff.md`, with): scope of one repository; the parent's safety
rules verbatim, which the child may narrow, never widen; the reserved list whole; done as
the PR opened as allowed (never merged), CI green, the slice's acceptance in its ledger, its
delegates cleaned up, a report path (in its run directory) in the completion message.

| The child rules alone | The child asks the parent, and waits on that item only |
|---|---|
| Anything that leaves every cross-repository contract as written | A delta to a cross-repository contract |
| Task order, splits, early starts, its delegates, plan fixes in its slice | Moving work across slices; a new dependency on another repository; its definition of done |
| | A reserved item: the parent records a gap, never decides it |

**Running it.**
1. The parent starts one supervised worker per repository in a new top-level worktree,
   pointed at the child's handoff (in the parent's run directory). Ledger line each.
2. A negotiation item: the child sends a blocking `ask` with the proposed change, the
   reason, the files on both sides and the cost of saying no, and works on the rest.
3. The parent answers from its criteria. Accepted: the owner child commits it, the parent
   `send`s the commit to every affected child, logs a ruling. Refused: what to do instead.
4. The parent waits on its inbox (`worker_done`, `escalation`, `question`), processes every
   message before acknowledging, and verifies each `worker_done`'s PR, head and report.
5. When all settled, the parent runs the joint acceptance with the heads installed together,
   sends fixes to the owning child, and writes one report linking each PR and report.

The children's Orca worktrees stay while their PRs are open; the report lists them.
