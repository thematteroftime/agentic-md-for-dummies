# Paper-to-Experiment Design — `<TOPIC_SLUG>`

> Template version: 1.0  ·  Save as: `docs/specs/YYYY-MM-DD-<topic>-design.md`
>
> ALL fields are required unless marked `(optional)`. Replace every `<...>` placeholder.
> Don't delete unused sections — write `N/A — reason` so reviewers see you considered them.

---

## §0 Metadata

- **paper_title**: `<full title>`
- **citation**: `Author et al., Journal Vol, page (Year)`
- **doi**: `10.XXXX/...`
- **paper_pdf**: `papers/<file>.pdf`  *(path relative to project root)*
- **rendered_pages**: `papers/rendered/page_*.png`  *(optional, leave blank if not rendered)*
- **key_equations**: `Eq.(1), Eq.(10), ...`  *(comma-separated paper equation labels)*
- **key_figures**: `Fig.1, Fig.2, ...`  *(comma-separated paper figure labels)*
- **legacy_data**: `<file path or "none">`  *(prior simulation outputs to cross-validate against)*
- **thesis_chapter**: `§<N>`  *(毕设章节号)*

---

## §1 Physics observables

Every observable MUST cite a specific paper Eq. or Fig. number. AI MUST NOT invent observables not in the paper. If the paper just says "particles form chains", quantify it as e.g. `Q = max g_∥ - max g_⊥ > 4`.

| ID | Observable | Paper ref | Type | Quantitative target | Unit | Tolerance | Analyzer |
|----|------------|-----------|------|---------------------|------|-----------|----------|
| O1 | `<name>` | `Eq.(N)` | scalar / curve / map | `<value or shape>` | `<unit>` | `±X%` or qualitative | `<script or function>` |

Add as many rows as needed. If observable is **derived** (not directly in paper), mark with `*` and explain in §11.

---

## §2 Force field

- **name**: `<HertzianNonreciprocal | ERPotential | NEW>`
- **class_path**: `forceFieldClass.<ClassName>`  *(only if existing)*
- **registered_force_type**: `<hertzian_nonreciprocal | er_plasma | NEW_TYPE>`  *(see `references/force_types.md`)*
- **units**: `reduced` *(σ, ε, m=1, k_B=1)* or `macro` *(mm, ms, K)*
- **new_class_required**: `true | false`
- **paper_eq_for_force**: `Eq.(<N>)`

### §2a New force class  *(fill only if new_class_required=true; else delete)*

- **rationale**: `<why existing classes don't fit>`
- **python_skeleton** (10–30 lines, key kernel only):
  ```python
  @ti.data_oriented
  class <NewClass>:
      requires_full_list = True
      def __init__(self, ...): ...
      @ti.kernel
      def updateAllF(self, atomSystem, searchBox):
          # implement paper Eq.(<N>) here
          ...
  ```
- **test_plan**: `tests/test_<class>_<N>cases.py` covering at minimum:
  - 2-particle force magnitude vs analytic prediction
  - F_ij + F_ji symmetry (or asymmetry, if non-reciprocal)
  - Boundary cases (r→0, r→cutoff)
- **analytical_fingerprints**: `<dimensionless numbers from paper appendix that we can compute and verify before running, e.g. Δ_eff=0.57, ε=0.082>`

---

## §3 Simulation setup (single-run defaults)

- **N**: `<int or "sweep">`
- **box**: `<derived from N and density | explicit>`
- **dt**: `<value>`
- **T0**: `<value or "sweep">`
- **density (φ or n)**: `<value or "sweep">`
- **boundary_conditions**: `periodic | wall | mixed`
- **thermostat**: `NVE | Langevin(ν=<value>) | Bussi`
- **integrator**: `BAOAB | Verlet | (other)`
- **write_stride**: `<int>` *(frames between HDF5 writes)*
- **chunk_size**: `<int>` *(per-chunk frames in HDF5; cap at 200 unless RAM allows more)*
- **cho**: `1` *(cell-list, default for N>3000)* or `2` *(O(N²), small N)*
- **steps_per_run**: `<int>`  *(total integration steps)*
- **t_total**: `<computed: steps × dt>` `<unit>`

---

## §4 Sweep dimensions

### §4a Fixed parameters (held constant across all runs)

| Parameter | Value | Source (paper § or registry default) |
|-----------|-------|---------------------------------------|
| `<name>` | `<value>` | `<paper §X / registry default>` |

### §4b Swept dimensions (cross-product = total runs)

| Dim | Variable | Values | Count | Rationale (paper §) |
|-----|----------|--------|-------|---------------------|
| D1 | `<name>` | `[v1, v2, ...]` | N | paper §X requires sweep over Y |

**Total runs**: `<product of counts>`

If runs > 12, justify (or split into Plan A / Plan B). Skill should warn if total > 16 runs.

---

## §5 Run phases

| Phase | Enabled | Steps | Purpose |
|-------|---------|-------|---------|
| preflight | `yes` | — | print VRAM/RAM/wall estimates |
| smoke | `yes` *(default)* | `100` | catch crash before launching production |
| production | `yes` | `<from §3>` | main simulation |
| analyze | `yes / no` | — | per-run + aggregate (set `no` if analyzer is paper-specific and we'll run separately) |

`halt_on_fail`: `true` *(stop campaign on first failure; safer for cost)*
`max_parallel`: `<2 default; bump to 3-4 only if VRAM headroom exists>`

---

## §6 Pass criteria

For each observable from §1, define decision rule.

| Observable ID | Analyzer output | PASS | NEAR | FAIL |
|---------------|-----------------|------|------|------|
| O1 | `<metric>` | `<rule>` | `<rule>` | `<rule>` |

Example:
- `slope_A in [0.60, 0.74]` → PASS (10% of paper 0.667)
- `slope_A in [0.50, 0.85]` → NEAR
- `else` → FAIL

---

## §7 Expected costs (campaign-level)

Fill from `ResourceEstimator.print_preflight()` after a smoke run, OR estimate from prior runs.

- **per-run wall** (typical): `<hr>`
- **per-run RAM peak**: `<GB>`
- **per-run VRAM peak**: `<GB>` *(must fit in RTX 5060 Laptop 8 GB)*
- **per-run disk (HDF5)**: `<GB>`
- **total runs**: `<from §4>`
- **wall (with parallelism)**: `total_runs × per_run / max_parallel = <hr>`
- **disk total**: `<GB>`

**Hard budget gates** (skill must fail if exceeded):
- single-run wall > 24 hr → split or reduce N/steps
- VRAM > 8 GB → use cho=1 cell-list or reduce N
- disk total > 50 GB → reduce stride or runs

---

## §8 Existing assets reused

| Asset | Path | Reused / new |
|-------|------|--------------|
| force class | `forceFieldClass.<X>` | reused |
| entry script | `<X>_run.py` | reused / new |
| analyzer | `<scripts/analyze_X.py>` | reused / new |
| legacy ground truth | `<path>` | for cross-validation |

If `new` for any of these, link to the test/spec that proves it works before campaign launch.

---

## §9 Deliverables

- **figures**: `fig<N>_<topic>.png` × `<count>` in `docs/images/`
- **results doc**: `docs/<TOPIC>_results.md`
- **code**: `<list new files>`
- **mapping_table.md update**: yes / no  *(usually yes, must add fig descriptions)*
- **thesis chapter §**: `<N>`

---

## §10 Decision log

Two sub-lists. Be honest in both — empty `Open questions for human` is what unblocks auto-mode, not an empty `Auto-decisions taken`.

### §10a Auto-decisions taken (no human input needed)

Defaults picked from registry, granularity choices justified by paper context.

1. `<decision>`  →  `<rationale grounded in paper § or registry>`
2. ...

If empty, write `N/A — every parameter directly cited in paper`.

### §10b Open questions for human (`ASK USER:` prefix required)

Items only the user can resolve (paper omits a parameter, two reasonable budget tradeoffs, etc.). Each line MUST start with literal `ASK USER:` so auto-mode can detect.

1. `ASK USER: <question>`  →  `<options>`
2. ...

If empty, write `N/A — no open questions`.

**Auto-mode rule**: `§10b` empty → proceed to Step 5. Non-empty → stop and surface.

---

## §11 Validation plan

For each paper figure we expect to reproduce:

| Paper fig | Our fig | Visual criterion |
|-----------|---------|------------------|
| Fig.X | `figN_<name>.png` | qualitative shape match (peak position, scaling) |

If applicable, list quantitative targets:
- `<our_metric> within X% of paper_value`

---

## §12 Output config

After this design is approved, emit:

- `configs/<plan_topic>.json`  *(matches `plan_config.schema.json`)*
- Reference this design doc via `_design_doc` field in the JSON

End of template.
