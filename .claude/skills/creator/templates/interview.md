# Framework profile — 17 questions

Ask one at a time. Skip any whose answer you can read from the user's codebase — but say so.

## A. Project layout (5)

1. Language + main numerics library? (Python/Taichi, Python/PyTorch, Julia, C++/Kokkos, ...)
2. Config format? (JSON canonical / YAML / TOML / Python dict)
3. Path to the script that runs ONE simulation given a config? (e.g. `prx_run.py`)
4. Output directory convention? (per-run timestamp dir / single dump / something else)
5. What concept maps to "force_type" in your code? (force class / model class / experiment_type / kernel) List all current values.

## B. Workflow phases (4)

6. Which phases does your pipeline have? Pick all: preflight / smoke / production / analyze / aggregate / visualize / report
7. Entry command for each? (typically only "production"; others may be implicit)
8. Resource preflight mechanism — exists? (returns wall/RAM/VRAM estimate from config)
9. Single-run cost magnitudes? (seconds / minutes / hours; CPU cores / GPU memory)

## C. Schema & validation (3)

10. Existing config schema or validation? (path or "none")
11. Required vs optional fields per type — list per type from #5.
12. Cross-field dependencies? (e.g. `if force=ER then lambda required`)

## D. Resource constraints (2)

13. Hardware target? (GPU model + VRAM, CPU cores, cluster)
14. Hard budget per run? (wall hours, disk GB, RAM GB)

## E. Existing artifacts (2)

15. Two or three "successful" config files we can use as exemplars + post-test fixtures? Paths.
16. Where do experiment results / reports / figures live?

## F. Domain (1)

17. Field + one representative paper citation. (For grounding the generated skill's tone + analyzer naming.)
