# Framework profile — `<FRAMEWORK_NAME>`

Filled by `creator` skill from inspection + user interview. Becomes input to skill generation.

## §A Project layout

- **A.1 framework_name**: `<...>`
- **A.2 language_stack**: `<e.g. Python 3.10 + Taichi 1.7.4 + CUDA>`
- **A.3 config_format**: `JSON | YAML | TOML | Python`
- **A.4 entry_script**: `<relative path>`
- **A.5 output_dir_convention**: `<e.g. outputFiles/<TS>_<tag>/>`
- **A.6 type_concept**: `<force_type | model_type | experiment_type | ...>`
- **A.7 known_types**: `[<type_1>, <type_2>, ...]`

## §B Workflow phases

- **B.1 phases_used**: `[preflight, smoke, production, analyze, aggregate, visualize]`
- **B.2 phase_commands**: `<table phase → command>`
- **B.3 has_preflight**: `true | false`
- **B.4 single_run_cost**: `<order of magnitude wall + RAM + VRAM>`

## §C Schema & validation

- **C.1 registry_path**: `<file that maps name → class, e.g. tools/registry.py>`
- **C.2 required_fields_per_type**: `<table>`
- **C.3 conditional_fields**: `<rules>`
- **C.4 existing_validator**: `<path or "none">`

## §D Resource constraints

- **D.1 hardware_target**: `<GPU model + VRAM, CPU cores>`
- **D.2 hard_budgets**: `wall=<hr>, disk=<GB>, RAM=<GB>, VRAM=<GB>`

## §E Existing artifacts

- **E.1 exemplar_configs**: `[<path1>, <path2>]`
- **E.2 results_dir**: `<path>`
- **E.3 figures_dir**: `<path>`

## §F Domain

- **F.1 field**: `<e.g. complex plasma MD; biomolecular MD; chemistry DFT>`
- **F.2 representative_paper**: `<citation>`
- **F.3 analyzer_naming_convention**: `<e.g. PRXAnalyzer for Phys. Rev. X paper>`

## §G Lessons captured (Step 5 self-test failures)

Append entries when self-test catches a generation bug — used to refine the
substitution table in `creator/SKILL.md` Step 4.

- ...
