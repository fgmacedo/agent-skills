# Choosing the delegation tool, and delivering across repositories

## Which tool for which delegate

| Situation | Tool | Why |
|---|---|---|
| The result fits in pull requests of one repository | Plain subagents, one per task, each in its own git worktree (`delegation.md`) | One-shot work: brief in, commit and short report out. Nothing to see in a UI, nothing to clean up but the worktree. |
| Same, and a delegate needs several turns of conversation with its context kept (a long fix loop, a planner revising with you) | An agent team member (named) | It keeps its context between your messages. It reports only through `SendMessage`; say so in the spawn prompt (`delegation.md`, "Named teammates"). |
| Orca is present and the result is pull requests in **more than one repository** | Orca supervised workers: one **sub-orchestrator per repository**, each in an Orca worktree of its repository | Each repository gets an owner with its own PR, worktree and ledger, visible to the user in Orca; parent and child talk through Orca's durable messages; the parent's context holds one line per repository. |
| Handing the whole run to a new session nobody supervises (launching the orchestrator from the planning session) | Orca's `worktree create --agent` through the orca-cli skill, or a new terminal session without Orca | Ownership moves; nothing waits on the result in this session. |
| Several repositories, no Orca | Plain subagents in worktrees of each repository; the orchestrator owns every PR | Same method, one level; the parent's context and ledger carry all repositories. |

Orca's command reference is served by the binary and changes between versions. Load it
before the first Orca command and use what it prints over anything below:
`orca skills get orchestration` (supervised workers, messages) and
`orca skills get orca-cli` (worktrees, terminals, unsupervised handoff).

## Multi-repository delivery with sub-orchestrators

The method is recursive. The parent runs this skill over the whole change; each child runs
this skill over its repository's slice, with a handoff the parent writes. The levels differ
only in scope and in who answers the child's questions: the parent, never the user.

### What the parent's plan adds

- **A slice per repository**: its tasks, its lane table, its integration check, its
  acceptance items.
- **Cross-repository contracts**, written in full, each with an owner repository: the
  schema, the API, the message format, the version or tag a consumer pins. A consumer codes
  against the contract before the producer's PR exists.
- **Order across repositories**: which PR must be green (or merged, or released) before
  another can pass its acceptance, and how a consumer points at the producer's branch while
  the producer is unmerged (a replace directive, a submodule ref, a package from a branch).
- **The joint acceptance**: the live check of all repositories together, run by the parent
  after every child settles.

### The child's handoff

Use `handoff.md` with these differences:

- **Scope**: one repository, its worktree and branch, its plan slice and the contracts it
  consumes and produces.
- **Rules**: the parent's safety rules that apply to this repository, verbatim. The child
  may narrow them, never widen them. The reserved list is inherited whole.
- **Done**: the PR opened as the handoff allows (draft or ready, never merged), its CI
  green, every task reviewed, the final review of the branch done, the slice's acceptance
  proven in the child's ledger, the child's delegate worktrees and branches removed, and a
  report file whose path goes in the completion message.
- **Negotiation**: what the child decides alone and what it must agree with the parent:

| The child rules alone, and logs | The child asks the parent, and waits on that item only |
|---|---|
| Anything inside its repository that leaves every contract as written | A change to a cross-repository contract (a field, a type, a version) |
| Task order, splits, early starts, its own delegates | Moving work into or out of its slice; a new dependency on another repository |
| Plan fixes inside its slice | Changing its definition of done or the order across repositories |
| | Anything the inherited reserved list names: the parent forwards it as a gap, it never decides it |

### Running it

1. Parent, after hardening the plan: create one Orca run for the change, and start one
   supervised worker per repository in a new top-level worktree of that repository, with a
   spec that points at the child's handoff file and says it is the orchestrator of that
   slice. Record each dispatch id, worktree and branch in the ledger.
2. Child: works as this skill says, with plain subagents inside its repository. It goes one
   Orca level down again only if its slice itself spans repositories.
3. A negotiation item: the child sends a blocking `ask` to the parent's run with the
   proposed change, the reason, the files on both sides and the cost of saying no. It keeps
   working on everything the item does not touch.
4. The parent answers from its own criteria, never from the user: if the change is
   accepted, it updates the plan's contract in one commit, tells every affected child with
   `send` to their dispatch, and logs a ruling; if refused, the reply says what to do
   instead. Each side records the outcome in its ledger.
5. The parent's loop waits on its run's inbox (`check --wait` for `worker_done`,
   `escalation`, `question`) and processes every message before acknowledging the batch.
   An empty wait is a checkpoint, not a failure.
6. A child settles with `worker_done`: outcome, PR URL, head SHA, report path. The parent
   verifies by itself (the PR's checks, the head it names, the report's evidence) before
   accepting, then releases the worker. A child that settles failed gets a ruling: retry
   with a new brief, or a gap in the report.
7. When every child settled, the parent runs the joint acceptance with the PR heads
   installed together, sends fixes back to the owning child (reuse its terminal or start a
   retry), and writes one report that links each repository's PR and report.

### What stays at the end

- One PR per repository, as the handoff allows, linked from the report.
- The children's Orca worktrees stay while their PRs are open: they hold the branches the
  user reviews. The report lists them, and says they can be removed after each merge.
- No delegate worktree or branch inside any repository, no run-prefixed resource, no
  unreleased Orca worker terminal.
