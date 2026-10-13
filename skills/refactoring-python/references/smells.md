# Smells: what to look for, what it violates, what cures it

A smell is a signal, not a verdict. Name it, then pick the transformation in
`transformations.md` whose mechanics cure it. The lenses are the ones a reviewer applies:

- **Cohesion.** Things that change for the same reason live together; things that change
  for different reasons are apart. A concept split across modules, or one module mixing
  unrelated reasons to change, fails this lens.
- **DRY.** Duplicated *knowledge* (a rule, a mapping, a constant, a decision), not similar
  looking code. Two functions that look alike but encode different decisions are not
  duplication; unifying them changes behavior.
- **Minimum shared context.** An interface exposes the least a caller needs (ISP), a module
  depends on abstractions only where the concrete thing is external or varies (DIP), a
  function receives values, not the whole world (Law of Demeter).
- **One reason to change** (SRP) for a module or class; open for extension through data or
  polymorphism rather than through editing a conditional (OCP) only once the second variant
  exists.

Sources: Fowler, *Refactoring* (2nd ed.); Kerievsky, *Refactoring to Patterns*; Beck,
*Tidy First?*; Ramalho, *Fluent Python*.

## Catalog

| Smell | Python signal (census, grep, reading) | Lens | Cure |
|---|---|---|---|
| Long function | `smell_census.py` long functions (> 40 lines); comments that label sections; local variables reused for different things | cohesion | Extract Function per labeled section; Replace Temp with Query; Split Phase when the first half computes and the second half renders |
| Long parameter list | > 5 parameters; several callers pass the same group; booleans that select behavior | minimum context | Introduce Parameter Object (`@dataclass(frozen=True)`); Preserve Whole Object; Remove Flag Argument (two functions) |
| Data clumps | the same 3 names travel together (`user_id, company_id, period`); tuples indexed by position | cohesion, DRY | Extract Class as a frozen dataclass or `NamedTuple`; replace positional tuple access with attribute access |
| Primitive obsession | strings carrying a type code (`status == "ok"`), money as float, ids as bare ints, dicts used as records | minimum context | Replace Type Code with Class (an `Enum`); Replace Primitive with Object (`Decimal`, `Money` dataclass); Replace Data Value with Object |
| Conditional complexity / switch statements | `if plan == ...: elif plan == ...:` ladders repeated in several functions; `isinstance` chains; nesting depth > 4 | OCP, cohesion | Decompose Conditional; Replace Nested Conditional with Guard Clauses; Replace Conditional with Polymorphism only when the ladder appears in 2+ places over the same type code, otherwise a dict of callables or a lookup table |
| Duplicated code | census "duplicated function bodies"; copy-pasted helpers in sibling modules; drifted copies | DRY | Extract Function / Pull Up; when copies drifted, first pin both behaviors with tests, then parametrize the difference explicitly (a policy enum, a keyword argument) rather than picking one |
| Large class / god module | > 300 lines or > 15 methods; a module that every other module imports (high fan-in) and that imports everything (high fan-out); `api_*.py` files of 10k lines | SRP, cohesion | Extract Class; Move Function to the module that owns the data; Split Module by reason to change |
| Divergent change | one module edited for every feature (billing rules, HTTP parsing and email templates in one file) | SRP | Split Phase; Extract Class; Move Function |
| Shotgun surgery | one rule change edits five modules (a status string compared in each) | DRY, cohesion | Move Function / Inline the spread; Combine Functions into Class; one `Enum` or table owning the rule |
| Feature envy | a function reads 4 attributes of another object and 0 of its own; `obj.a.b.c` chains | Demeter | Move Function to the data; Extract Function then Move |
| Inappropriate intimacy | module A reaches `B._private`; subclasses that touch parent internals | minimum context | Move Function; Replace Subclass with Delegate; Hide Delegate |
| Message chains | `company.config.plan.limits.max_users` | Demeter | Hide Delegate; Extract Function with an intention-revealing name |
| Middle man | a class whose methods all delegate | cohesion | Remove Middle Man; Inline Function |
| Speculative generality | an ABC with one implementation; a `Base*` class with one subclass; hooks nobody calls; `**kwargs` passed through | YAGNI, minimum context | Collapse Hierarchy; Inline Class; Remove Dead Code; replace the ABC with a function parameter |
| Temporary field | attributes set in one method and read in another, `None` elsewhere | cohesion | Extract Class; Introduce Special Case |
| Refused bequest | subclass overrides a method to raise or no-op | LSP | Replace Subclass with Delegate; Push Down Method |
| Comments as deodorant | comments that explain *what* the next 10 lines do | cohesion | Extract Function named after the comment; Introduce Assertion; delete the comment |
| Mutable global state | module-level `dict`/`list` written by functions (`_CACHE = {}`); census "mutable module state" | testability | Encapsulate Variable; pass the state in; put caches behind a port when they hit I/O |
| Hidden dependency | `datetime.now()`, `time.time()`, `random`, `os.environ`, `requests.get`, ORM session reached from a function that computes a result | DIP, testability | Parameterize Function (`today: date`); Extract Function for the I/O; a port when the dependency is external (see `boundaries.md`) |
| Import-time work | queries, HTTP, registry mutation at module import; `from app import *` | testability | move the work into a function called by the composition root; import-on-its-own test |
| Alternative classes with different interfaces | two classes do the same job with different method names (`fetch`/`load`) | DRY | Rename Method; Unify Interfaces with Adapter; Extract Superclass only with 2+ real sharers |
| Combinatorial explosion | `render_md_with_totals`, `render_csv_with_totals`, ... | DRY | Replace Implicit Language with Interpreter is rarely worth it; usually Separate the axes: one function per axis composed |
| Oddball solution | one place solves a problem differently from the rest of the code base | DRY | Unify Interfaces; Substitute Algorithm with the house one |
| Solution sprawl | one feature implemented across many classes and modules | cohesion | Move Creation Knowledge to Factory only if there are several creators; otherwise Move Function and Inline |
| Indecent exposure | public helpers that only one module uses; everything `from x import *` exported | minimum context | leading underscore, explicit `__all__`; Encapsulate Classes with Factory only when construction varies |

## Python-specific signals the census does not print

- `getattr(obj, "x_" + kind)`, `globals()[name]`, string-built dispatch: open-ended lookup
  that hides callers from every static tool. Replace with an explicit dict before moving
  anything it can reach.
- `try: import x except ImportError:` compatibility shims and `six`: port leftovers, see
  the porting skill.
- A function that both returns a value and mutates its argument (`customer["total"] = ...`):
  callers may depend on the mutation. Pin it before extracting a pure builder.
- `@staticmethod` collections on a class with no state: a module of functions in disguise.
- `*args, **kwargs` pass-through layers: an interface that says nothing; the real signature
  lives two levels down.
- Boolean parameters named `force`, `strict`, `raw`: two functions.
- Tests that patch `module.requests.get` or `module.time.time`: the hidden dependency has
  no seam; the test is coupled to the import line.

## How to use the catalog

1. Run `python scripts/smell_census.py PATHS` and read the top modules.
2. For each signal, find the row and write down smell → lens → cure, one line each. That
   list is the plan of phase 2.
3. Order it: cures that unlock others first (guard clauses before extracting; naming
   constants before replacing the conditional; pinning behavior before any of it).
