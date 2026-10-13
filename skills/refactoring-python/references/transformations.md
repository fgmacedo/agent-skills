# Transformations: mechanics in Python

One transformation per commit, named in the subject exactly as below so a reviewer knows
what to check. The mechanics are the small steps; run the suite after each step, commit
after the last. If a step goes red, revert the step (`git checkout -- .`), do not debug on
top of a refactoring.

Three families, in the order they usually apply:

1. **Tidyings** (Beck, *Tidy First?*): minutes each, no design intent, make the next
   change easy to read.
2. **Refactorings** (Fowler): change the structure, keep behavior; the named moves below.
3. **To patterns** (Kerievsky): a refactoring that lands on a known pattern, only when the
   smell it cures is present and there are at least two real variants.

Python facts that bite during moves are collected at the end.

## 1. Tidyings

| Tidying | Do | Commit subject |
|---|---|---|
| Guard clauses | `if not x: return ...` first, then the happy path unindented | `tidy: guard clauses in <fn>` |
| Dead code | delete what nothing reaches (see the dead-code skill for proof levels; inside one function, the suite is proof) | `tidy: remove unreachable branch in <fn>` |
| Normalize symmetries | the same thing done two ways (`d.get(k, 0) + 1` and `if k in d`) becomes one way | `tidy: normalize <thing>` |
| New interface, old implementation | write the call you wish you had, implement it by calling the old one | `tidy: add <new fn> over <old fn>` |
| Reading order | reorder definitions so the file reads top-down | `tidy: reading order in <module>` |
| Cohesion order | move the things that change together next to each other | `tidy: group <concept> in <module>` |
| Move declaration and initialization together | `x = compute()` at first use, not at the top | `tidy: declare <var> where it is used` |
| Explaining variable | name a subexpression | `tidy: name <expr> in <fn>` |
| Explaining constant | `TAX_RATE = Decimal("0.19")` instead of the literal | `tidy: name the <concept> constants` |
| Explicit parameters | replace `**kwargs` or a config dict read inside with named parameters | `tidy: explicit parameters for <fn>` |
| Chunk statements | blank lines between the phases of a function (the step before Extract Function) | `tidy: chunk <fn>` |
| Extract helper | a chunk with one job becomes a function; the next commit usually moves it | `refactor: extract <helper> from <fn>` |
| One pile | inline the pieces of something over-split so you can see it, then re-split along the real seams | `tidy: inline <pieces> into one pile` |
| Explaining comments | only for what the code cannot say (why, external constraint) | `tidy: explain <constraint>` |
| Delete redundant comments | comments that say what the next line says | `tidy: drop comments that restate the code` |

Beck's rule for the ratio: tidyings go in their own PR when they are many, before the
behavior change; a reviewer reads "tidy" commits in seconds.

## 2. Refactorings

Each entry: mechanics, the Python-specific step, and the test it needs.

### Extract Function

1. Chunk the statements. 2. Create the function next to the caller with a name that says
what it does, not how. 3. Copy the chunk in; pass every local it reads as a parameter;
return every local the caller reads afterwards (if more than two, extract a dataclass or
extract a smaller chunk). 4. Replace the chunk with the call. 5. Suite. Mutation of a
parameter inside the chunk is still visible to the caller for lists and dicts, invisible
for ints and strings: check what the chunk rebinds versus what it mutates.

### Inline Function / Inline Variable

Reverse of extract, used to undo bad splits before resplitting (One pile). Check the
function has no other callers (`git grep -w name`) and no decorator with side effects.

### Replace Temp with Query, Extract Variable

Repeated expression → function (query) when it needs the object's state, → local when it
is used in one function. In a class, a query that is cheap and pure may become a
`@property`; that changes every call site that used parentheses (see Facts).

### Split Phase

A function that computes and then renders (or parses and then decides): 1. Extract the
second half into a function taking an intermediate value. 2. Introduce a frozen dataclass
for the intermediate value. 3. Extract the first half returning it. 4. The original becomes
two calls. Each step is a commit. Rendering and computing now change for different reasons.

### Move Function / Move Module

1. In the new home, define the function. 2. In the old home, replace the body with a call to
the new one (or `from new import fn` re-export). 3. Suite: `mock.patch` targets, pickles and
logger names may break here (Facts). 4. Move callers one by one, or in one commit when they
are mechanical. 5. Remove the re-export last, in its own commit, after grepping the dotted
and the bare name across code, templates, config and sibling repos.

### Extract Class

1. `@dataclass` holding the clump of fields that travel together (frozen when nothing
mutates them). 2. Move the functions that only read those fields onto it one at a time.
3. The old class holds an instance and delegates. 4. Callers switch to the new class.

### Introduce Parameter Object

The same 3+ arguments in several signatures → one frozen dataclass. Add it as a new
parameter with a default built from the old ones, switch callers, remove the old ones.

### Replace Type Code with Class

`status == "ok"` scattered → `class Status(StrEnum)`. Keep the string values identical;
`str(member)` of a plain `Enum` or a `(str, Enum)` mixin prints `Status.OK` on 3.12, so
serialization must use `.value` or the class must be `StrEnum` (Facts).

### Decompose Conditional, Replace Nested Conditional with Guard Clauses

Extract the condition and each branch into named functions first; then flatten.

### Replace Conditional with Polymorphism

Only when the same ladder over the same type code appears in two or more places. Steps:
Replace Type Code with Class → for each branch, a method on the variant (or an entry in a
`dict[Status, Callable]`) → the ladder becomes one dispatch. One ladder in one place is a
lookup table, not a hierarchy.

### Replace Primitive with Object

Money as `float` → `Decimal` with an explicit rounding policy. This changes numbers
(`round(2.675, 2)` versus `Decimal("2.675").quantize(...)`): pin the current outputs first and
keep the old policy until a behavior commit changes it on purpose.

### Parameterize Function

`def report(invoices)` reaching `date.today()` → `def report(invoices, today: date)`; the
old default stays wired in the caller or as `today: date | None = None` resolved at the top.
Same for `now`, `sleep`, `random`, env reads. One implementation, no interface.

### Separate Query from Modifier

A function that returns a value and also writes: split into a pure query and a command,
unless callers depend on the combination, which the characterization test shows.

### Remove Flag Argument

`send(email, force=True)` → `send(email)` and `force_send(email)`.

### Encapsulate Variable / Encapsulate Collection

Module-level mutable state → accessed through functions, then injected. A returned list the
caller mutates → return a tuple or a copy, once the characterization test shows nobody
relies on the mutation.

### Collapse Hierarchy, Replace Subclass with Delegate, Replace Superclass with Delegate

A base class with one subclass, or subclasses that override to refuse: fold or delegate.

### Substitute Algorithm

Replace the body with a clearer one only when the characterization test covers the edges
the old one had (empty input, ties in rounding, ordering).

### Change Function Declaration (rename, add or remove parameter)

Migration mechanics: add the new signature as a new function, forward the old one to it,
move callers, delete the old one. Each step compiles and tests.

### Parallel Change (expand / migrate / contract)

For anything with external callers or persisted data: add the new path next to the old,
run both and compare (`hypothesis` with the old implementation as oracle), switch callers,
remove the old. Three PRs when callers are outside the repo.

## 3. Refactoring to patterns

Use only when the smell is present; the pattern is the destination, not the goal.

| Smell | Refactoring (Kerievsky) | Python shape |
|---|---|---|
| Conditional dispatcher: a big `if action == ...` choosing what to run | Replace Conditional Dispatcher with Command | `dict[str, Callable]`; a class only if commands carry state |
| Duplicated algorithm skeleton in sibling classes | Form Template Method | base method calling abstract steps, only with 2+ real subclasses; often a function taking the varying steps as callables |
| Nested `if`/`for` building a tree by hand | Replace Implicit Tree with Composite | nested dataclasses with a `render()`/`accept()` |
| Many constructors / factory functions scattered | Encapsulate Classes with Factory, Move Creation Knowledge to Factory | a `@classmethod` constructor, or one `build_*` function in the composition root |
| Type code with behavior | Replace Type Code with Class, Replace State-Altering Conditionals with State | `Enum` with methods; a state machine only when transitions are the domain |
| Two classes with the same job, different interfaces | Unify Interfaces with Adapter | a small adapter class or a `Protocol` the callers depend on |
| Optional behavior bolted on with flags | Move Embellishment to Decorator | a wrapping function or class; `functools.wraps` |
| Hard-coded collaborator construction | Extract Parameter, Inject the collaborator | constructor parameter; a port only when external (see `boundaries.md`) |
| Accumulating results across methods | Move Accumulation to Collecting Parameter / Visitor | pass the list in; `yield` from a generator is usually simpler |
| `isinstance` chains over a closed set of types | Replace Conditional with Polymorphism | `match` on the dataclass types when the set is closed and the chain lives in one place |
| Primitive obsession in strings with structure | Replace Implicit Language with Interpreter | rarely worth it; a parser function and a dataclass first |

## Python facts that change behavior during a move

Each one is backed by an executable probe in `claims/refactoring-python/` of this repository.

- **`mock.patch` targets the name where it is looked up.** A test that patches
  `pkg.clock.now` does nothing for `pkg.report`, which did `from pkg.clock import now`.
  Moving a function silently un-mocks every test that patched its old home. Grep for
  `patch("` and `patch.object(` on the names you move.
- **Pickles store the class path.** Caches, queues and sessions holding instances of a
  class break on load after the class moves. Keep a re-export at the old path for one
  release, or escalate.
- **`logging.getLogger(__name__)` follows the module.** Handlers, filters and log-based
  alerts configured for the old name stop seeing records after a move.
- **Star re-exports hide callers.** `from .core import *` in `__init__` means a grep for
  `pkg.core` finds no caller of `pkg.render`. Grep the bare name too.
- **A cycle can bite in one import order only.** `import pkg.b` works, `import pkg.a`
  fails with "partially initialized module"; a suite whose conftest imports the package
  first never sees it. Add an import-on-its-own subprocess test when splitting modules.
- **`@dataclass` adds `__eq__` and removes hashing** unless `frozen=True`. Instances used
  as dict keys or in sets stop working; instances compared by identity start comparing by
  value.
- **`lru_cache` on a method caches `self`.** Instances are never collected and the cache
  is shared across instances by key. Cache on a module function or use `cached_property`.
- **Method → `@property`** turns every `obj.total()` into `TypeError: 'int' object is not
  callable`. Change all call sites in the same commit.
- **`str()` of an `Enum` member is `Status.OK`**, also for `(str, Enum)` on 3.12. Only
  `StrEnum` or `.value` serializes to `"ok"`.
- **Set iteration order changes with the hash seed**; dict order does not. Output built
  from a set is not reproducible across runs; pin it only after sorting.
- Others to check by hand: `is` comparisons on small ints and interned strings; mutable
  default arguments shared across calls; `functools.partial` and bound methods captured
  at import; `__slots__` on a class that gains a dataclass; `__init_subclass__` and
  metaclass registration that runs at import; relative imports when a module moves
  packages; `typing.TYPE_CHECKING` imports that hide a runtime cycle.
