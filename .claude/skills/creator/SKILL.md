---
name: creator
description: Use when a user wants to bootstrap an experiment-orchestration skill for their own simulation framework. Captures their framework profile via 17 questions, then emits a tailored paper-to-experiment skill (templates, schema, registry, validator) into their .claude/skills/.
---

# Creator — meta-skill that builds experiment-orchestration skills

You are generating a skill that lives inside another project. The output is a working clone of `paper-to-experiment` adapted to that project's simulation framework.

## Hard rules

1. **Inspect first, ask second.** Read the user's project root before any question. Files >> their description.
2. **Don't invent fields.** If a question's answer can't be inferred from the codebase, surface it; don't guess.
3. **Skill output is text-only.** No GPU, no simulations, no `--apply` to user files outside `.claude/skills/<generated>/`.
4. **Generated skill must validate.** Before handing off, dry-run the schema against one of the user's existing configs.
5. **Single source of class registry.** Generated skill must point at one runtime registry (e.g. `tools/registry.py`), never at scattered references.
6. **AI only produces config; never executes.** This contract is non-negotiable in every generated skill.

## Process

```
1. Inspect repo  →  2. Interview (17 Q) →  3. Fill profile
                                              ↓
       6. Hand off  ←  5. Self-test  ←  4. Generate skill
```

### Step 1 — Inspect repo

Read in order:
- `pyproject.toml` / `package.json` / `Cargo.toml` (language + deps)
- The user's main entry script (whatever runs a simulation)
- One existing config file (the kind of artifact the new skill will produce)
- `docs/` for any README / architecture notes

Catalog: language, config format (JSON/YAML/TOML/Python), entry-script signature, output dir convention, existing analyzer/plotter classes.

### Step 2 — Interview

Open `templates/interview.md`, ask the 17 questions in order. **One question per turn.** Multiple-choice when possible. Skip questions whose answers you already inferred — and say so ("from inspecting `<file>`, I'll assume X; correct?").

### Step 3 — Fill profile

Save user answers + inspections to `docs/specs/<TS>-<framework-name>-profile.md` using `templates/framework_profile.md` as scaffold. This file is the input contract for skill generation.

### Step 4 — Generate skill

For each placeholder in `templates/skill_scaffold/`, substitute from profile:

| Scaffold token | Source |
|---|---|
| `{{FRAMEWORK_NAME}}` | profile §A.1 |
| `{{CONFIG_FORMAT}}` | profile §A.2 |
| `{{ENTRY_SCRIPT}}` | profile §A.3 |
| `{{REGISTRY_PATH}}` | profile §C.1 |
| `{{REGISTERED_TYPES}}` | profile §A.5 |
| `{{ADAPTER_CONTRACT_FIELDS}}` | profile §C.2 |

Write the generated files to `<user_project>/.claude/skills/paper-to-experiment-<framework>/`. Never overwrite an existing skill of the same name without explicit confirmation.

### Step 5 — Self-test

Run `validate_config.py --strict` (the generated one) against one of the user's existing approved configs. Must exit 0. If it fails, fix the schema generation rule, regenerate, retry. Log failures into the profile §F (lessons captured for future iterations).

### Step 6 — Hand off

Tell the user: where the skill is, what registry entries to add, the smoke-test command, and the contract file (`SKILL.md`) they'll iterate on.

## Anti-patterns

| Thought | Reality |
|---|---|
| "Just clone paper-to-experiment as-is" | Their framework isn't ours. Profile-substitution is the whole point. |
| "Skip the interview, infer everything" | One wrong inference rots downstream. Ask when unsure. |
| "Don't bother self-testing" | Untested generation = handing the user a broken skill. |
| "AI runs simulations to verify" | Out of scope — `creator` produces files, never burns compute. |

## Files

```
.claude/skills/creator/
├── SKILL.md                   # this file
├── templates/
│   ├── interview.md           # 17 questions (framework profile)
│   ├── framework_profile.md   # filled by creator + user
│   └── skill_scaffold/        # placeholder skill, copied + substituted
│       ├── SKILL.md.tmpl
│       ├── design_template.md.tmpl
│       ├── schema.json.tmpl
│       ├── registry.md.tmpl
│       └── validator.py.tmpl
└── references/
    ├── distillation.md        # what's framework-agnostic vs specific
    └── md_test1/              # this project as exemplar
```

End of skill.
