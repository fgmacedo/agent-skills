# Agent Guidelines

This repository contains skills for AI coding agents, published to the [skills.sh](https://skills.sh/) marketplace. Follow these guidelines when working with or contributing to this repository.

## Repository Structure

```
agent-skills/
├── skills/                     # All skills live here
│   └── <skill-name>/          # One directory per skill
│       ├── SKILL.md           # Required — skill definition with frontmatter
│       ├── references/        # Optional — supporting documentation
│       └── scripts/           # Optional — executable scripts
├── claims/                    # Executable checks for factual claims in skill references (not installed)
├── AGENTS.md                  # This file — guidance for AI agents
├── README.md                  # Repository overview and install instructions
└── LICENSE                    # MIT
```

## Skill Format (skills.sh specification)

Each skill directory must contain a `SKILL.md` with YAML frontmatter:

```yaml
---
name: skill-name          # Required. Lowercase, hyphens only. Must match directory name.
description: >            # Required. Max 1024 chars. Describe what it does AND when to trigger.
  Description here.
license: MIT              # Optional. License identifier.
---
```

### Naming rules for `name`

- Max 64 characters
- Lowercase letters, numbers, and hyphens only
- Must not start or end with a hyphen
- No consecutive hyphens
- Must match the parent directory name exactly

### Description guidelines

The `description` field serves dual purposes:
1. **What the skill does** — clear, concise summary
2. **When to trigger** — keywords and phrases that help agents recognize when to activate the skill

Include natural-language trigger phrases (e.g., "this is slow", "make it faster") alongside technical terms.

## Content Guidelines

### Size and structure

- Keep `SKILL.md` under 500 lines — move detailed content to `references/` files
- Use progressive disclosure: the main file provides the workflow, reference files provide tool-specific details
- Reference files are loaded on demand when the agent needs them

### Writing style

- Be direct and actionable — agents follow instructions, not suggestions
- Use numbered steps for sequential workflows
- Use decision trees or tables for choosing between alternatives
- Include concrete code examples with realistic patterns
- Specify exact commands with all necessary flags

### Focus areas

This repository focuses on skills useful for:
- **Coding** — performance optimization, debugging, testing
- **Design** — system architecture, API design, code organization
- **Best practices** — engineering standards, code review, technical documentation
- **Leadership** — technical decision-making, team practices, incident response

## Contributing a New Skill

1. Create a directory under `skills/` with a kebab-case name
2. Add a `SKILL.md` with valid frontmatter (name must match directory)
3. Add supporting files under `references/` or `scripts/` as needed
4. Update the skills table in `README.md`
5. Test the skill by installing it locally: `npx skills add . --skill <name>`

## Verifying Claims

Every non-obvious factual claim in a skill's references (checker behavior, defaults, flags) must be backed by an
executable claim in `claims/<skill>/` that passes against the pinned toolchain. Each claim file holds the claims and
the probe files they run. Re-run the claims when bumping a tool version, and update the reference with what the probe
shows:

```bash
uv sync --project claims/python-typing/toolchain
python3 claims/python-typing/verify.py
```

## Quality Checklist

- [ ] `name` in frontmatter matches directory name
- [ ] `description` includes both purpose and trigger phrases
- [ ] `SKILL.md` is under 500 lines
- [ ] All referenced files exist
- [ ] Instructions are concrete and actionable (not vague advice)
- [ ] Code examples are realistic and use current best practices
