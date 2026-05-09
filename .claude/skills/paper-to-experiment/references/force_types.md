# Force-type registry

Authoritative source for which `force_type` strings are valid in `configs/plan_*.json` and what fields each requires. Skill must consult this BEFORE proposing any config field.

When adding a new force type, follow §4 below (8-step extension) — registry is the gatekeeper, schema and skill follow.

## Conventions table

Per-force-type conventions that are easy to mix up. **Read this before writing the campaign config.**

| force_type | `N` means | default IC | ndim | units_regime |
|------------|-----------|-----------|------|--------------|
| `hertzian_nonreciprocal` | **per-species** count (total = 2N — see §1) | from-file lattice | 3 | `reduced_lj` |
| `er_plasma` | total particle count | from-file lattice (`xyz_1000_3.in`) | 3 | `macro_dust` |
| `kalj`     | total particle count (split 80/20 A/B internally) | `simple_cubic_3d` from `tools/lattices/` | 3 | `reduced_lj` |

The `N` convention column is the most common footgun — `hertzian_nonreciprocal` is the only force_type where `N` is per-species. Future binary mixtures should document N as **total** unless there's a strong reason otherwise.

---

## 1. `hertzian_nonreciprocal`  (PRX 2015)

- **paper**: Ivlev et al. *Phys. Rev. X* 5, 011035 (2015), Eq. (1)
- **entry script**: `prx_nonreciprocal_run.py`
- **force class**: `forces.hertzian_nonreciprocal:HertzianNonreciprocal`
- **analyzer**: `toolClass.PRXAnalyzer` (in-process via `PRXAnalyzer.full_analysis`)
- **compat**: `ndim=3`, `units_regime=reduced_lj`
- **box**: derived from N and φ
- **integrator**: BAOAB (NVE if ν=0, Langevin else)

### Required fields per experiment

| field | type | range | meaning |
|-------|------|-------|---------|
| `tag` | str | `[A-Za-z0-9_]{2,32}` | unique run id |
| `phi` | float | (0, 1.0] | reduced number density |
| `T0`  | float | (0, 100] | initial temperature (reduced) |
| `steps` | int | [100, 5e7] | total integration steps |
| `stride` | int | [1, 1e5] | frames between HDF5 writes |

### Optional fields

| field | type | default | meaning |
|-------|------|---------|---------|
| `nu` | float | 0 | Langevin damping; 0 = pure NVE |
| `N` | int | 10000 | **per-species count**: `--N` arg sets `N_A = N_B = N`, **total particles = 2 × N**. Default 10000 → total 20000. Critical: setting `N=20000` yields total 40000, NOT 20000. |
| `dt` | float | 0.004 (PRX_PARAMS default in `prx_nonreciprocal_run.py`) | time step in τ |
| `chunk_size` | int | 200 | HDF5 chunk frames; cap 200 unless RAM allows |
| `write_stride` | int | 100 | frames per disk flush |
| `profiler` | bool | false | enable Taichi profiler (warning: OOM risk on long runs) |

### Critical pre-flight rules

- **`nu > 0` requires `nu ≤ ν_c = c/(2*T0^1.5)`** with `c ≈ 1.5e-4`. Skill MUST compute ν_c and warn if exceeded.
- **`steps × dt > 50000 τ`**: cap RAM via `chunk_size: 200` and `profiler: false`.
- **Damping experiments**: ALWAYS confirm corresponding NVE run at same (φ, T0) reached `slope_A ≥ 0.6` first (P3 invariant).

### Example (E14, sub-critical damping)

```json
{
  "force_type": "hertzian_nonreciprocal",
  "tag": "E14_nu1em5",
  "phi": 0.3,
  "T0": 0.3,
  "nu": 1e-5,
  "steps": 10000000,
  "stride": 1000
}
```

---

## 2. `er_plasma`  (PRL 2008)

- **paper**: Ivlev et al. *Phys. Rev. Lett.* 100, 095003 (2008)
- **entry script**: `er_plasma_run.py`
- **force class**: `forces.er_potential:ERPotential` (anisotropic Yukawa, Eq. (1))
- **analyzers**: `scripts/analyze_er.py` (CLI, accepts `--runs` glob), `tools.analyzers.er.ERAnalyzer` (registry-callable wrapper)
- **compat**: `ndim=3`, `units_regime=macro_dust` — required, ERPotential hard-codes 3D and the macro mm/ms/K scale
- **integrator**: BAOAB with Langevin damping (default `nu=0.1 /ms`)
- **lattice**: 1000-atom 10×10×10 lattice file expected at `dataFiles/<lattice>.xyz`

### Required fields per experiment

| field | type | range | meaning |
|-------|------|-------|---------|
| `tag` | str | `[A-Za-z0-9_]{2,32}` | unique run id |
| `MT` | float | [0, 1.2] | dimensionless ion-flow Mach number |
| `Z_eff` | float | [1, 1e5] | effective dust charge in units of e |
| `lambda_mm` | float | [0.001, 10] | Debye screening length in mm |
| `T0_K` | float | [1, 1e4] | initial temperature in Kelvin |
| `dt_ms` | float | [1e-4, 1] | time step in ms |
| `steps` | int | [100, 5e7] | total integration steps |
| `stride` | int | [1, 1e5] | frames between HDF5 writes |

### Optional fields

| field | type | default | meaning |
|-------|------|---------|---------|
| `nu` | float | 0.1 (1/ms) | Langevin damping; for ER plasmas always ≠ 0 |
| `N` | int | 1000 | particle count (must match lattice file) |
| `cho` | enum {1,2} | 2 | 1 = cell-list (N>3000), 2 = O(N²) (small N) |

### Critical pre-flight rules

- **N=1000 corresponds to `xyz_1000_3.in` lattice; box ≈ 1.07 mm cube**. Different N requires new lattice file.
- **cutoff = 12·λ_mm, cutoffNegh = 18·λ_mm** auto-set by entry script.
- **`MT > 1.0` is the sonic limit** — chains destabilize, expect early Q peak then collapse. Skill must flag this in design doc §6 pass criteria.
- **Run length**: 50k steps (=500 ms with dt=0.01) is INSUFFICIENT due to initial-lattice / chain-spacing coincidence. Use ≥100k steps for chain-phase reproduction.

### Example (ER4L, MT=0.8 main result)

```json
{
  "force_type": "er_plasma",
  "tag": "ER4L_MT08",
  "MT": 0.8,
  "Z_eff": 10000,
  "lambda_mm": 0.05,
  "N": 1000,
  "T0_K": 348,
  "dt_ms": 0.01,
  "steps": 100000,
  "stride": 200,
  "nu": 0.1,
  "cho": 2
}
```

---

## 3. `kalj`  (PRL 2018, Kob-Andersen binary LJ)

- **paper**: Pedersen, Schroder, Dyre, *Phys. Rev. Lett.* 120, 165501 (2018)
- **entry script**: `pedersen_kalj_run.py`
- **force class**: `forces.kalj:KobAndersenLJ`
- **analyzer**: `tools.analyzers.pedersen:PedersenAnalyzer` (partial RDFs g_AA / g_AB / g_BB + MSD)
- **plotter**:  `tools.plotters.pedersen:PedersenPlotter`
- **aggregator**: `tools.aggregators.pedersen:PedersenAggregator`
- **compat**: `ndim=3`, `units_regime=reduced_lj`
- **IC**: `simple_cubic_3d` lattice + random A/B species labels (deterministic seed)
- **integrator**: BAOAB (drag-only Langevin — engine has no Wiener noise yet)

### Required fields per experiment

| field | type | range | meaning |
|-------|------|-------|---------|
| `tag` | str | `[A-Za-z0-9_]{2,32}` | unique run id |
| `T0` | float | (0.05, 5.0] | initial temperature (reduced LJ units) |
| `rho` | float | (0.01, 5.0] | number density (paper Fig.4 covers 0.93–1.44) |
| `steps` | int | [100, 5e7] | total integration steps |
| `stride` | int | [1, 1e5] | frames between HDF5 writes |

### Optional fields

| field | type | default | meaning |
|-------|------|---------|---------|
| `nu` | float | 0.1 | Langevin damping (1/τ); drag-only, no Wiener noise (engine limitation) |
| `N` | int | 1000 | total particle count; split into round(fraction_B·N) B and (N − N_B) A |
| `dt` | float | 0.005 | LJ-reduced timestep |
| `fraction_B` | float | 0.20 | B-species fraction (paper KA standard 80:20) |
| `cho` | enum {1,2} | 2 | 1 = cell-list, 2 = O(N²) (use 2 for N<3000) |

### Critical pre-flight rules

- **Cutoff**: paper-defined truncate-and-shift at `2.5·σ_pq` per pair. Adapter sets `cutoff = 2.5·σ_AA = 2.5` (the largest). `cutoffNegh ≈ 1.15·cutoff`.
- **Engine limitations** (documented in design doc §11):
  - No NPT — paper's coexistence-line method (Fig.1, §III) is NOT reproducible. Use NVT-Langevin at fixed ρ and target qualitative observables (RDF structure, MSD trend).
  - With `integrator: baoab_drag`, the O step has no Wiener noise → MSD plateaus at low T (engine artifact). Use `integrator: baoab_langevin` (FD-balanced) for diffusion-relevant runs; the campaign config must then set `T_target` per state point (schema enforces).
- **Lattice-release temperature spike**: simple-cubic IC at the KA σ_AA spacing puts every atom near the steep wall of the LJ potential. On step 1 the lattice-PE → KE conversion produces `T_init ≈ 2.5·T_target` (observed, not theoretical). With `baoab_langevin` at nu=0.1, FD damping absorbs this in ~50 τ. Analyzers should measure `T_meas` over the LATE half of the trajectory, never from the first few frames.
- **Lattice equilibration window**: simple-cubic is far from KA equilibrium (the equilibrium is amorphous-supercooled or FCC depending on T). Use the LAST 1/3 of the trajectory for RDF measurement; the first 1/3 is dominated by lattice-melt transients.

### Example

```json
{
  "force_type": "kalj",
  "tag": "T10_rho12",
  "T0": 1.0,
  "T_target": 1.0,
  "integrator": "baoab_langevin",
  "rho": 1.2,
  "N": 1000,
  "fraction_B": 0.20,
  "steps": 100000,
  "stride": 200,
  "nu": 0.1,
  "cho": 2,
  "ndim": 3,
  "units_regime": "reduced_lj"
}
```

---

## 4. Engine integration notes (read before adding a new force type)

These platform behaviours are non-obvious and have caught autonomous extension agents. Worth reading once.

### Units handshake (3-way coupling)

Every force_type ties together three labels that MUST match:

1. The `units` keyword in the adapter-emitted `run.in` file (e.g. `units macro`)
2. The exact filename under `units/<name>.yaml` that constSet loads (e.g. `units/macro.yaml`)
3. The schema's `units_regime` enum value declared in the force_type's compat block (e.g. `macro_dust`)

Adding a new regime requires creating a new yaml under `units/`, then emitting that yaml's stem in `run.in:units` AND in the manifest's `units` field, while the schema-side `units_regime` is the human-readable enum label that maps to it.

### `ndim=2` requires `Lz ≥ cutoffNegh`

Even though z is force-zeroed every integrator step (every concrete integrator's `inteBegin` ends with `if ndim==2: zeroZ()`), the underlying searchBox neighbour pass still runs through the 3D MIC kernel. If the lattice file's z-extent is below `cutoffNegh`, `atomSystemClass.addNegh` asserts at startup. **2D adapters must set the lattice's `Lz ≥ cutoffNegh`** (a flat slab is fine — z stays zero throughout integration). Document `cutoffNegh` ≈ 1.3·`cutoff` ≈ 6·λ as a reasonable default, then size Lz accordingly.

### Full-list pattern

`requires_full_list = True` means the neighbour list visits both `(i, j)` AND `(j, i)` for every unordered pair. The kernel must:
- Write force ONLY to `force[i]` (never to `force[j]`) — the reverse visit handles `j` separately.
- Accumulate PE as `pe_per_atom[i] += 0.5 * U_pair` (the 0.5 factor compensates for the duplicate visit).

Read `lennardJones.updateOneF_reciprocal` (`forces/lennard_jones.py`) for the canonical reciprocal pattern. The template `force_class.py.template` documents this in detail.

### Initial state

`AtomSystem.initData(positions, masses, T0, boxList, groups=...)` calls `scaleVel` internally — velocities are randomized to T0. Tests that need zero initial velocity must call `A.vel.fill(0.0)` AFTER `initData`.

### Long-range repulsive IC caveat

For force types whose pair potential diverges (or stays large) as `r→0` — Coulomb, Yukawa, screened-dipole, anything with a hard core — random uniform initial positions inevitably contain small-r overlaps. On step 1 these get converted into kinetic energy:

- A few overlapping pairs at `r ~ 0.1·a` produce orders-of-magnitude force spikes.
- The integrator turns the spurious PE into spurious KE within a single step, leaving `T_init ≫ T0_target`.
- If the run is short (≤ a few `1/ω_p`) and Langevin damping is heavy (`ν > 0.05`), the damping over-cools relative to the fluctuation-dissipation balance and the steady-state `T_meas` ends up *below* `T0_target`. Observed shortfall in autonomous-Yukawa-OCP test: `T_meas ≈ T0/10` after 100·`1/ω_p`.

**Mitigation, in order of preference:**
1. **Lattice IC + brief NVE warmup**: use `tools/lattices/<lattice>_<dim>.py` (default `square_2d` / `simple_cubic_3d`; or `triangular_2d` for hexatic phases) followed by NVE for `~10·(1/ω_p)` to dissipate any residual lattice-mode energy.
2. **Random IC + soft repulsion ramp**: scale the potential by `λ(t)` ramping from 0 → 1 over `~5·(1/ω_p)` to avoid the step-1 overlap spike.
3. **Random IC + heavy short Langevin equilibration THEN swap to weak**: legitimate but parameter-sensitive.

Any new force class subclassing `forceField` whose potential diverges at the origin SHOULD declare its IC expectation in the design doc §3 `initial_state` field (not random). Adapter default for ndim=2 is `square_2d`, ndim=3 is `simple_cubic_3d`; override only when paper specifies otherwise.

### Integrator selection

Time-integration scheme is a registered platform extension just like force_type. Set `integrator` in the experiment dict (default `"baoab_drag"`) to pick:

| `integrator` | Scheme | Use when | Caveats |
|--------------|--------|----------|---------|
| `baoab_drag` | BAOAB step ordering, drag-only O step (`v *= exp(-ν·dt)`, no Wiener noise) | NVE (ν=0); structural-only NVT where small T drift is OK; legacy PRX/ER/KA-LJ runs | MSD plateaus over long Langevin runs; FD theorem violated; T_meas drifts away from T0 |
| `baoab_langevin` | BAOAB step ordering with Wiener-noise / FD-balanced O step (`v ← α·v + sqrt((1-α²)·k_B·T_target/m)·R`, `α = exp(-ν·dt)`, `R ~ N(0,I)`) | Diffusion / viscosity / glass dynamics; any observable that demands FD theorem balance; thermostatting at fixed `T_target`. Reduces to Velocity Verlet when `nu=0`. | REQUIRES `T_target` field. Reproducibility needs `ti.init(random_seed=...)` set before construction. Stability heuristic: `dt × ν < 0.1`. |

Schemes register in `integrators/__init__.py:INTEGRATOR_REGISTRY` AND `tools/registry.py:_REGISTRY` (integrators section). For the full extension flow when a paper genuinely requires Wiener-noise Langevin / Bussi / multi-time-step / etc., see "Adding a new integrator" below.

The integrator's `REQUIRED_KWARGS` / `OPTIONAL_KWARGS` class tuples drive what extra fields the campaign config must carry — e.g. `T_target` for FD-balanced Langevin. Adapter pulls those from the experiment dict and forwards via `inteParams`.

---

## 5. Adding a new force type

When a new paper requires a force class not listed above, walk these **8 steps** in order. **A reproduction that stops at step 6 has only proved the engine wires up — no `report.md`, no plots.** By SKILL.md Hard rule #9, that is incomplete. Flag the entire chain in design doc §2a as a status checklist.

1. **Force class implementation**
   - Write `forces/<your_force>.py` with class subclassing `forceField` (`forces/base.py`), declaring `requires_full_list` and `PREFLIGHT_FIELDS`.
   - Pattern: copy nearest existing class (`forces/hertzian_nonreciprocal.py` for non-reciprocal, `forces/er_potential.py` for anisotropic radial, `forces/lennard_jones.py` for simple radial).
   - **Register**: add the class to `forces/__init__.py:FORCE_REGISTRY` AND to `tools/registry.py:_REGISTRY`. Both, in sync.

2. **Tests** (mandatory before any production run)
   - `tests/test_<class>_<N>cases.py` covering: 2-particle force vs analytic; F symmetry/antisymmetry; cutoff boundary.
   - Run `pytest tests/test_<class>_*.py` until green.

3. **Entry script (adapter)**
   - Create `<topic>_run.py` at project root mirroring `prx_nonreciprocal_run.py` / `er_plasma_run.py`.
   - CLI flags must include all required fields from §1 above.
   - Use `tools.lattices.LATTICE_REGISTRY[design_doc.initial_state]` for the initial configuration. Default IC: `square_2d` for ndim=2, `simple_cubic_3d` for ndim=3.

4. **Dispatch in run_experiment + validator**
   - Edit `scripts/run_experiment.py:_invoke_md` — add a new branch for the new `force_type`.
   - Edit `scripts/run_experiment.py:EXP_DEFAULTS_BY_TYPE` — add per-force-type defaults so PRX-shaped values don't silently rewrite your campaign entries.
   - Update `EXP_REQUIRED_<TYPE>` constant with required fields.
   - Edit `scripts/validate_config.py:check_force_type_specific` — add the parallel `elif force_type == "<your_type>":` branch. (Forgetting this causes a silent `else: res.err("unknown force_type")` and the validator rejects every campaign with the new type.)

5. **Schema update**
   - Edit `templates/plan_config.schema.json`:
     - Add new value to `force_type` enum.
     - Add new `if/then` block in `allOf` mapping force_type → required-fields + `ndim` + `units_regime` constants.
     - If a brand-new units regime is needed, also extend the top-level `units_regime` enum.

6. **Registry section in this file**
   - Add a new section here (`## N. <new_type>`) with paper ref, fields, **compat block** (`ndim=...`, `units_regime=...`), examples, pre-flight rules.

7. **Analyzer (per-run)**
   - Write `tools/analyzers/<paper>.py` exposing `<Paper>Analyzer.full_analysis(run_dir, **params) -> dict`. The returned dict's fields drive the per-run `report.md` written in `<run_dir>/report.md`.
   - **Register**: add to `tools/registry.py:_REGISTRY` under the analyzers section. Without this step the run dir gets only `manifest.json + h5` — engine wires up but nothing is measured.
   - In your config, set `pipeline.analyze.class = "<Paper>Analyzer"`.

8. **Visualizer + aggregator**
   - Write `tools/plotters/<paper>.py` exposing `<Paper>Plotter.render(run_dir, **params) -> None` writing `figN_*.png` into the run dir.
   - Optional but recommended: write `tools/aggregators/<paper>.py:<Paper>Aggregator.aggregate(run_dirs, output, plots, title, **params)` for the cross-run master report.
   - **Register both** in `tools/registry.py:_REGISTRY`.
   - In your config, set `pipeline.visualize.class = "<Paper>Plotter"` AND `aggregation.class = "<Paper>Aggregator"`.

After all 8 steps:
- Each production run dir contains `manifest.json` + `report.md` + at least one `fig*.png`.
- The cross-run report (e.g. `docs/<paper>_campaign_report.md`) renders a coherent answer to the paper's question.
- `python scripts/validate_config.py --strict` passes.

### Anti-pattern: reuse-with-degenerate-parameter

There is a tempting third option to "reuse" vs "extend": pick an existing force class that algebraically reduces to the target physics under a parameter setting (e.g. `ERPotential` with `MT=0` is mathematically a pure isotropic Yukawa). This produces a strict-validating config in 5 minutes WITHOUT going through Steps 1-8.

**Do not do this for thesis-quality reproductions.** The manifest will lie about which physics ran (`force_class=ERPotential` instead of `YukawaIsotropic`), the dead anisotropy machinery is allocated and integrated even though it contributes zero, and downstream analyzers may misinterpret the data because they were written for the more general class. Surface this trade-off in design doc §10b as an `ASK USER:` decision, with the recommendation that thesis or published work should go through the full 8 steps.

---

## 5b. Adding a new integrator

When a paper requires a time-integration scheme that the existing integrators cannot faithfully reproduce, walk these **9 steps** in order. Most commonly triggered by:

- Diffusion / viscosity / glass-transition observables that demand FD-balanced Langevin (Wiener-noise BAOAB) — `baoab_drag` plateaus the MSD.
- Bussi / Nose-Hoover / DPD thermostats with paper-specific coupling.
- Multi-time-step / RESPA splittings.
- Symplectic schemes specific to a Hamiltonian (e.g., constrained dynamics, rigid-body integrators).

The flow mirrors the 8-step force extension but adds one extra step to wire the per-paper adapter:

1. **Integrator class** (`integrators/<your_scheme>.py`)
   - Subclass `IntegratorBase` from `integrators/base.py`.
   - Declare `REQUIRED_KWARGS` / `OPTIONAL_KWARGS` / `SCHEME_NAME` class tuples / strings.
   - Implement `__init__(self, timeStep, **kwargs)` and `inteBegin(self)`.
   - Pattern: copy `integrators/baoab_drag.py` as the closest template; add the missing physics in `step_O_full` (or wherever your scheme differs).
   - Use `templates/integrator.py.template` as a fresh scaffold if extending without a near-twin.

2. **Tests** (mandatory before any production run)
   - `tests/test_<scheme>_<N>cases.py` covering: NVE invariant preservation (energy drift over a long run), thermostat target hit (T_meas → T_target), and the kernel-level stochastic seed reproducibility if Wiener noise is used.

3. **Local registry**
   - Add to `integrators/__init__.py:INTEGRATOR_REGISTRY` and the `from ... import` block at the top.

4. **Forwarding station**
   - Mirror in `tools/registry.py:_REGISTRY` under the integrators section.

5. **Schema**
   - Add the scheme name to the `integrator` enum in `templates/plan_config.schema.json`.
   - If the scheme requires extra fields (e.g. `T_target`), declare them as schema properties (already partially done — see existing `T_target` field) and add a conditional `if/then` in `allOf` requiring the field when `integrator: <scheme>` is set.
   - **Important conditional shape**: a JSON-Schema `if` clause vacuously matches when the property is absent. To make the conditional fire only for entries that DO carry `integrator: <scheme>`, the `if` must require both the field's presence AND its value:
     ```json
     {
       "if": {
         "properties": {"integrator": {"const": "<scheme>"}},
         "required": ["integrator"]
       },
       "then": {"required": ["T_target"]}
     }
     ```
     Without `"required": ["integrator"]` the `if` matches every campaign entry that simply omits `integrator` entirely, and the `then` clause silently constrains entries that the author never intended.

6. **Validator (recommended; scaffold already wired)**
   - `scripts/validate_config.py:check_integrator_specific(cfg, res)` is the dedicated hook called from `main()` alongside `check_force_type_specific`. Add a new `if scheme == "<your_scheme>":` branch inside it for stability rules (e.g. `dt × ω_max < 0.1`, `T_target` vs `T0` sanity), notes about lattice-release temperature spikes, etc. The function exists; you only edit one branch.

7. **Adapter wiring**
   - Each per-paper adapter dispatches the integrator class by name from the campaign entry: `IntCls = INTEGRATOR_REGISTRY[exp.get("integrator", "baoab_drag")]`. Build `inteParams` from the integrator's `REQUIRED_KWARGS` class attribute — adapter is integrator-agnostic, no string-match magic. The dispatch pattern lives in `pedersen_kalj_run.py` for reference.
   - Local variable name: prefer `integrator_cls` (the class) and `integrator_inst` (the instance) over the legacy shadowing `from integrators import BAOABDrag as integrator`. The adapter template (`templates/adapter_run.py.template`) shows the new pattern.
   - Existing adapters that still import `BAOABDrag as integrator` work fine — the rename is opt-in until they want to dispatch by config.

8. **Registry doc**
   - Add a row to the **Integrator selection** table in §4 above with: scheme name, one-line description, "use when", "caveats".

9. **Regression test for sync**
   - The `tests/test_skill_regression.py:test_registry_local_init_sync` already covers the registry-vs-local-init invariant. Add the new integrator to the assertion in `tests/test_kalj_3cases.py`-style or a new `tests/test_<scheme>.py` so a missed registration is caught the next time `pytest -q` runs.

After all 9 steps, the integrator is a first-class platform extension and any future paper can pick it via `"integrator": "<scheme_name>"` in its campaign entry.

---

## 6. Legacy configs (pre-`force_type`)

Configs written before the `force_type` field was introduced (e.g., `plan_e_damping.json`, several Plan B/C configs) will fail strict validation because their experiments lack `force_type`. They were all `hertzian_nonreciprocal` by default — that was the only force the framework supported at the time.

**Migration**: add `"force_type": "hertzian_nonreciprocal"` to each campaign entry. No other changes needed; physics is unchanged.

Skill MUST NOT auto-rewrite legacy configs. If user is migrating, flag it explicitly and let user merge the change.

---

## 7. Cross-reference

- **Schema**: `templates/plan_config.schema.json`
- **Skill main**: `SKILL.md`
- **Force forwarding station**: `tools/registry.py:_REGISTRY` (single source of truth for forces / lattices / analyzers / plotters / aggregators / visualizers)
- **Force package**: `forces/__init__.py:FORCE_REGISTRY` (local registry, kept in sync with forwarding station)
- **Lattice package**: `tools/lattices/__init__.py:LATTICE_REGISTRY` + `DEFAULT_LATTICE_BY_NDIM`
- **Run dispatcher**: `scripts/run_experiment.py:_invoke_md`
- **Validator**: `scripts/validate_config.py:check_force_type_specific`
