# What's framework-agnostic vs framework-specific

The distillation rule for `creator`. When in doubt, prefer general — generated skills are easier to specialize than to generalize back.

## Framework-agnostic (hard-coded into every generated skill)

These survive verbatim across any simulation domain.

| | Why |
|---|---|
| 7-step process: read paper → fill design → user gate → emit config → validate → handoff | Workflow, not domain |
| "AI only emits config; never runs simulations" | Safety contract |
| "Smoke before production" hard rule | Cheap insurance, universally applicable |
| "Citations required for every observable" | Hallucination prevention |
| 12-section design doc structure (Metadata / Observables / Force / Setup / Sweep / Phases / Pass / Costs / Assets / Deliverables / Decisions / Validation / Output) | Generic R&D scaffold |
| Three-layer validation (schema + physics + budget) | Universal failure modes |
| Adapter contract: CLI in, manifest out, stdout, exit code | Subprocess interface, not domain |
| "Decision log split into auto-decisions vs ASK USER:" | Auto-mode safety |

## Framework-specific (substituted from `framework_profile.md`)

| | Substituted from |
|---|---|
| Config format (JSON/YAML/TOML/Python) | A.3 |
| Entry script path + CLI flags | A.4 + C.2 |
| Type-concept name (force_type, model_type, ...) | A.6 |
| Registered types enumeration | A.7 |
| Schema field ranges (N, dt, T, ...) | C.2 + D.2 |
| Step-rate calibration constants | E.1 + B.4 |
| Physics observables vocabulary (slope, g(r), loss, ...) | F.1 |
| Resource budgets (VRAM, wall, disk thresholds) | D.2 |
| Existing analyzers/visualizers/aggregators | inferred from project root |
| Lattice / IC preparation conventions | C.2 |
| Manifest §3.2 paper-specific fields | C.2 + F.2 |

## How to decide when in doubt

1. **Is the rule about safety or workflow?** → agnostic.
2. **Is it about a specific number / file / class name?** → specific.
3. **Could a chemist + a robotics researcher both want it?** → if yes, agnostic; if no, specific.
4. **Is it cargo-culted from one paper?** → specific. Reject if you can't justify it.

## Self-check before generating

Walk every line in the scaffold. For each, mark `[A]` (agnostic — keep) or `[S]` (specific — substitute). Any line you can't classify is a generation bug — go back to the profile and add a question.
