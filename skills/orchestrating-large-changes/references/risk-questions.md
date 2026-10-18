# Risk questions: asked once, after the plan

The user owns every decision about risk. Ask all of them in one batch, after the plan exists
and before the run starts, so the run never waits on a person. Each answer becomes a line of
the handoff (`handoff.md`): an allowed action, a forbidden action, or a resource the run may
create.

## How to ask

1. Read the plan and list every task that touches something outside the repository: an
   installed binary, a service, a config or home directory, a database, a remote API, a
   shared repository, another tool's state. Those tasks are where the questions come from.
2. Write one message with every question, each with the default you propose and why. The
   user answers by exception ("all defaults, except 4"). Use your harness's question tool
   for the two or three with real alternatives; the rest go as a list.
3. Replace every human stop point the plan has ("the user installs", "after a day of use",
   "the user checks") with a criterion an agent can evaluate and an explicit permission to
   act. If a step truly needs the person (their account, their judgment on taste, a legal
   sign-off), it is reserved and the run works around it; it is never a gate the run waits on.
4. Prepare before launching what the user's answers make possible and the run would hesitate
   to do: the backup with its checksums, the sandbox repository with its fake actors, the
   snapshot of the user's resources. An agent unsure whether it may create a repository
   or write to a production service either stalls or guesses; settle it now.
5. Write the answers into the handoff verbatim enough that a fresh agent can apply them
   without this conversation.

## The checklist

Ask only the rows the plan touches; a row with nothing behind it is noise the user has to
read.

| # | Ask | Typical default | Becomes in the handoff |
|---|---|---|---|
| 1 | **Window.** Until when is the run alone? Will the user use this machine meanwhile? | Until the stated return; machine unused | "The user is away until <when>; nobody answers questions" |
| 2 | **Definition of done.** What must be true for the user to only do a final check: merged where, installed or not, which live proofs, which report? | Merged on the integration branch, gate green, installed from that branch, every acceptance item proven by a recorded command, report written | The Done section |
| 3 | **Blast radius: remote writes.** Which repositories, projects, accounts, queues or services may the run write to? Everything else is read-only. | Writes only to a sandbox the run controls; reads anywhere | Allowed-resources rule, with the exact names |
| 3b | **Pull requests.** On which repositories may the run push branches and open pull requests, draft or ready? Who merges? | Push and open draft PRs on the repositories the plan changes; never merge | PR rule naming each repository; "never merge" in the never list |
| 4 | **Live tests.** Is a live end-to-end test worth a sandbox? Who plays the other actors (a second account, a bot, a workflow)? | Yes, a private sandbox with scripted actors, created before the run | Sandbox section with the exact commands that drive each actor |
| 5 | **Automation that acts on its own.** Which schedulers, sweeps or bots may run during the window, and on what scope? | Paused everywhere but the sandbox; paused everywhere at the end | Pause rule, with the command that resumes and where the status shows it |
| 6 | **Install and restart.** May the run install, uninstall, stop and start the product on this machine, as often as validation needs? Through what (installer, service manager labels)? | Yes, only through the product's own installer and service labels | Install rule naming the commands |
| 7 | **The user's data.** What data must survive? Where is the backup, who takes it, how is it proven unchanged? | Backup taken now, read-only for the run, checksums compared at the end; migrations read a copy | Backup rule with path and checksum file |
| 8 | **The user's own things.** Which of the user's resources may never be touched (workspaces, sessions, cards, branches, PRs, files)? | Never close, rename, move or delete anything the run did not create | "Never" list, plus the snapshot the run compares against at the end |
| 9 | **Run-owned resources.** What prefix marks what the run creates, so cleanup can find it and nothing else? | `<project>-e2e-*` for workspaces, branches, PRs, processes | Prefix rule; cleanup removes exactly that |
| 10 | **Config and home directories.** Which files outside the repository may change, and only through what? | Only through the product's installer, which backs up each file before its first change; no hand edits | Config rule naming each file and the allowed key |
| 11 | **Security mechanisms.** Does the plan or a live test hit a safety mechanism of the user's tools (folder trust, permission prompts, credential stores, signing, branch protection)? | Never bypassed or written by the run; detected and reported, the fix offered as a command the user runs | Reserved list |
| 12 | **Processes.** What may the run kill? | Only processes it started, by recorded PID; services only through their manager | Process rule |
| 13 | **Compatibility.** Must old behavior, old data formats or old clients keep working? | Ask; the answer reshapes the plan | Constraint in the plan, repeated in the handoff |
| 14 | **Spend.** Model tiers, paid API calls, CI minutes, cloud resources: any ceiling? | Most capable model for plan review and final review, cheaper tiers for mechanical tasks and scoped re-reviews | Delegation rule |
| 15 | **Multi-agent opt-in.** May the run use subagents, agent teams, workflow tools? | Yes | Explicit opt-in sentence (some harnesses require it) |
| 16 | **Reserved decisions.** What must the run never decide alone, even when stuck? | Items 3, 8, 11 and anything irreversible outside the sandbox | Reserved list: the run skips the case, records a gap and continues |
| 17 | **Hand-back.** Where does the report go, and how does the user learn the run ended (a comment, a notification, a file)? | Report file in the repository plus one line where the user looks first | Done section |

## Questions that do not belong here

Design questions the plan already settled, and anything a measurement in the run can settle
(which approach is faster, whether a test passes). Those are rulings the run makes and logs.
