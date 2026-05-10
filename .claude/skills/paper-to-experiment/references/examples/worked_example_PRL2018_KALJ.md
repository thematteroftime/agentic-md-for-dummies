## Worked example: PRL 2018 Kob-Andersen binary LJ reproduction

This walkthrough mirrors the autonomous reproduction of Pedersen, Schrøder, Dyre PRL 120, 165501 (2018) that lives at `configs/plan_pedersen_kalj.json`. Read it when you are wiring a new binary-mixture paper or when you need a concrete template for the joint **8-step force extension + 9-step integrator extension** flow — KA-LJ exercises both in a single campaign and the artefacts here line up cleanly with the skill's checklist.

The reproduction is a smoke-scale qualitative match: structural observables (partial RDF peak ordering) hit paper-derived analytic targets within ~5%, and dynamic observables (per-species MSD, Einstein diffusivity ratio) follow the expected qualitative trends. The paper's central NPT coexistence-line method is out of scope for the framework, which is documented explicitly in §11 below — surface that limitation in any new binary-mixture design that inherits this template.

---

## §0 Metadata

```yaml
paper_title: Phase Diagram of Kob-Andersen-Type Binary Lennard-Jones Mixtures
citation:    Pedersen, Schrøder, Dyre, Phys. Rev. Lett. 120, 165501 (2018)
doi:         10.1103/PhysRevLett.120.165501
paper_pdf:   papers/pedersen_prl2018.pdf
key_equations: [pair-potential definition (top of p.2): per-pair LJ with σ_BB/σ_AA=0.88, σ_AB/σ_AA=0.8, ε_BB/ε_AA=0.5, ε_AB/ε_AA=1.5, truncated at 2.5σ_pair]
key_figures: [Fig.1 (T_m=1.028 at ρ=1.2 for χ_B=0.20), Fig.3 (T-χ_B phase diagram)]
legacy_data: none — KA model first appears in this framework with this campaign
```

### Open-questions early checklist

Every entry resolves before any §1 content is written. Fail this gate and stop.

- Paper PDF on disk at the cited path — yes
- All paper parameters cited from explicit passages — yes (KA σ/ε matrix and 2.5σ cutoff are stated verbatim on p.2)
- Force type decision: **extend** — `forces.lennardJones` is single-(σ,ε), so degenerate reuse is impossible. New `KobAndersenLJ` class required.
- Integrator decision: **extend** — drag-only `baoab_drag` plateaus MSD below the cage timescale, which masks the paper's central dynamic signal. New Wiener-noise `BAOABLangevin` required.
- Cost budget: < 24 hr/run, < 8 GB VRAM — yes (N=1000, 1e5 steps, ≈4 min/run on RTX 5060 Laptop)
- Open ASK USER count: 0

## §1 Physics observables

| ID | Observable | Paper ref | Quantitative target | Tolerance | Analyzer |
|----|------------|-----------|---------------------|-----------|----------|
| O1 | Partial RDF g_AA first peak | KA standard | r_AA ≈ σ_AA·2^{1/6} ≈ 1.122 σ_AA | ±10% | PedersenAnalyzer |
| O2 | Partial RDF g_AB first peak | KA standard | r_AB ≈ σ_AB·2^{1/6} ≈ 0.898 σ_AA | ±10% | PedersenAnalyzer |
| O3 | Partial RDF g_BB first peak | KA standard | r_BB ≈ σ_BB·2^{1/6} ≈ 0.988 σ_AA | ±10% | PedersenAnalyzer |
| O4* | Peak ordering r_AB < r_AA | analytic from σ matrix | r_AB / r_AA < 1 | strict | PedersenAnalyzer |
| O5* | Per-species MSD trend | Fig.3 isodiffusional | linear growth past cage time at all 3 T; D_B > D_A | qualitative | PedersenAnalyzer |
| O6* | Thermostat fidelity T_meas vs T_target | from FD theorem | |T_meas − T_target| / T_target < 5% on the late half of the trajectory | strict | PedersenAnalyzer |

`*` derived observable (not directly stated in the paper but implied by the physics).

## §1.5 Analyzer / plotter / aggregator contract

```yaml
analyzer:
  class_path: tools.analyzers.pedersen:PedersenAnalyzer
  method:     full_analysis(run_dir, **params) -> dict
  writes:     report.md (per run dir), rdf.npz, msd.npz
  returns:    verdict, r_peak_AA/AB/BB, msd_A_final, msd_B_final, T_meas, params

plotter:
  class_path: tools.plotters.pedersen:PedersenPlotter
  method:     render(run_dir, **params) -> None
  writes:     fig1_rdf.png (3-panel partial RDFs), fig2_msd.png (per-species MSD)
  cross_run:  fig_rdf_overlay, fig_msd_overlay (called by aggregator)

aggregator:
  class_path: tools.aggregators.pedersen:PedersenAggregator
  method:     aggregate(run_dirs, output, plots, title, **params) -> None
  writes:     docs/pedersen_kalj_campaign_report.md, docs/images/pedersen_kalj_*.png
```

## §2 Force field

```yaml
name:                   KobAndersenLJ            # NEW
class_path:             forces.kalj:KobAndersenLJ
registered_force_type:  kalj                     # NEW
units:                  reduced_lj               # σ_AA = ε_AA = m = k_B = 1
new_class_required:     true
paper_eq_for_force:     v(r) = 4ε_pq·[(σ_pq/r)^12 − (σ_pq/r)^6], truncated and shifted at 2.5σ_pq
```

The 8-step force extension landed in commit `b6169c4`. Each row maps onto a real file in main; copy this table verbatim when extending into a new force_type.

| Step | Action | File |
|------|--------|------|
| 1 | Force class | `forces/kalj.py`; registered in `forces/__init__.py:FORCE_REGISTRY` and `tools/registry.py:_REGISTRY` |
| 2 | Tests | `tests/test_kalj_3cases.py` (analytic 2-particle force; AB cross-species selection; cutoff boundary) |
| 3 | Adapter | `pedersen_kalj_run.py` |
| 4 | Dispatch + validator | `scripts/run_experiment.py:_invoke_md` (kalj branch); `scripts/validate_config.py:check_force_type_specific` (kalj branch) |
| 5 | Schema | `templates/plan_config.schema.json` (force_type enum + if/then for `["T0", "rho"]`) |
| 6 | Registry doc | `references/force_types.md §3 kalj` |
| 7 | Analyzer | `tools/analyzers/pedersen.py:PedersenAnalyzer` |
| 8 | Plotter + aggregator | `tools/plotters/pedersen.py`, `tools/aggregators/pedersen.py` |

## §3 Simulation setup

```yaml
N:                  1000        # total; split 800 A + 200 B by assign_species_random
box:                derived from rho via box = (N/rho)^(1/3); cubic
dt:                 0.005       # LJ-reduced
T0:                 sweep [0.7, 1.0, 1.3]
T_target:           equal to T0 in this campaign (FD setpoint)
density (rho):      1.20        # paper's canonical isochore
boundary_conditions: periodic
thermostat:         FD-balanced Langevin via baoab_langevin (Wiener-noise)
integrator:         baoab_langevin
integrator_kwargs:  {nu: 0.1, T_target: <T0>}
initial_state:      simple_cubic_3d with deterministic-seed species permutation
equilibration_steps: implicit — analyzer measures over the late half of the trajectory
write_stride:       200
chunk_size:         200
cho:                2           # O(N²), N=1000 ≪ cell-list crossover
steps_per_run:      100000
t_total:            500 LJ τ
```

## §4 Sweep dimensions

| Dim | Variable | Values | Count | Rationale |
|-----|----------|--------|-------|-----------|
| D1 | T0 = T_target | [0.7, 1.0, 1.3] | 3 | brackets paper Tm = 1.028: supercooled / coexistence / equilibrium liquid |

Total runs: 3.

## §5 Run phases

| Phase | Enabled | Steps | Purpose |
|-------|---------|-------|---------|
| preflight | yes | — | resource estimate |
| smoke | yes | 100 | catch crash before launching production |
| production | yes | 100000 | main |
| analyze (3.4) | yes | — | dispatched to PedersenAnalyzer |
| visualize (3.5) | yes | — | PedersenPlotter renders fig1_rdf + fig2_msd per run dir |
| aggregate | yes | — | PedersenAggregator writes the cross-run report and overlay figures |

`halt_on_fail: true`, `max_parallel: 1`.

## §6 Pass criteria

| Obs | Metric | PASS | NEAR | FAIL |
|-----|--------|------|------|------|
| O1 | r_peak_AA | within ±10% of 1.122 σ_AA | ±20% | otherwise |
| O2 | r_peak_AB | within ±10% of 0.898 σ_AA | ±20% | otherwise |
| O3 | r_peak_BB | within ±10% of 0.988 σ_AA | ±20% | otherwise |
| O4 | r_peak_AB < r_peak_AA | strict ordering | — | not ordered |
| O5 | MSD_A(t_end) | ≥ 0.5 σ_AA² (mobile) | 0.1–0.5 | < 0.1 |
| O6 | |T_meas − T_target| / T_target | ≤ 5% | 5–15% | > 15% |

## §7 Expected costs (per run, RTX 5060 Laptop)

- wall: ~3.5 min at N=1000 cho=2 (measured ≈480 step/s)
- RAM peak: ~1.5 GB
- VRAM peak: ~0.36 GB (well under 8 GB budget)
- disk (HDF5 LZF): ~30 MB per run
- total runs: 3
- campaign wall: ~10 min serial
- campaign disk: ~100 MB

All within the validator's hard budget gates.

## §8 Existing assets reused

| Asset | Path | Status |
|-------|------|--------|
| simulator | `systemClass.systemRun` | reused (Layer 1) |
| atom system | `atomSystemClass.AtomSystem` | reused (Layer 1) |
| neighbor list | `searchBox.searchBox` | reused (Layer 1, cho=2 O(N²)) |
| HDF5 writer | `tools/file_io.py` (via systemClass) | reused |
| Lattice IC | `tools.lattices.simple_cubic_3d:SimpleCubicLattice3D` | reused |
| Species tagging | `tools.lattices._template:assign_species_random` | reused |
| Resource estimator | `tools.resources.ResourceEstimator` | reused |

## §9 Deliverables

- per-run figures: `outputFiles/<TS>_kalj_<T>/{fig1_rdf,fig2_msd}.png`
- per-run report: `outputFiles/<TS>_kalj_<T>/report.md`
- cross-run figures: `docs/images/pedersen_kalj_{rdf,msd}_overlay.png`
- cross-run report: `docs/pedersen_kalj_campaign_report.md`
- new code: forces/kalj.py, integrators/baoab_langevin.py, pedersen_kalj_run.py, tools/{analyzers,plotters,aggregators}/pedersen.py, tests/test_kalj_3cases.py, tests/test_baoab_langevin_3cases.py
- thesis chapter: out of scope (autonomous reproduction smoke campaign)

## §10 Decision log

### §10a Auto-decisions

1. **Particle count** — N=1000 vs paper's 8000. Paper is converged at large N; smoke-scale N=1000 still resolves r_AA / r_AB peaks cleanly because they sit at single-σ separation. Trade-off accepted: g_BB peak detection is the noisiest because N_B is only 200 atoms.
2. **Lattice IC** — simple-cubic at the KA σ_AA spacing. Equilibrium would be amorphous-supercooled at low T or FCC at high T; the simple-cubic release puts every atom near the steep wall of the LJ potential. The FD-balanced thermostat absorbs the resulting T_init ≈ 2.5·T_target spike in roughly 50 τ at ν=0.1 — analyzer therefore measures over the late half of each trajectory, which is documented in `force_types.md §3 kalj` Critical pre-flight rules.
3. **Integrator** — `baoab_langevin` over `baoab_drag` so MSD escapes the cage and T_meas tracks T_target. Drag-only would have given the wrong dynamic signal at all three T.
4. **Cutoff** — single global cutoff = 2.5·σ_AA = 2.5 (the largest pair cutoff); per-pair masking inside the kernel keeps each (σ_pq, ε_pq) pair within its own 2.5·σ_pq window.

### §10b Open questions for human

`N/A — no open questions`

## §11 Validation plan

| Paper claim | Reproducibility in this framework | What we measure instead |
|-------------|------------------------------------|-------------------------|
| Tm = 1.028 at ρ=1.2 (Fig.1) | not reproducible — engine has no NPT, no Frenkel-Ladd free-energy integration | structural g_pq peaks + dynamic MSD trend across the bracketing T points |
| Coexistence-line method (§III) | not reproducible (same reason) | NVT at fixed (ρ, T) state points |
| Per-species partial RDFs (Fig.2 implicit) | reproducible | quantitative match within ±10% on the analytic σ_pq·2^{1/6} target for AA and AB; ±20% NEAR on BB due to small-N statistics |
| Per-species diffusion D_p | reproducible (with `baoab_langevin`) | D_B > D_A across all 3 T as expected from σ_BB < σ_AA |

## §12 Output config

`configs/plan_pedersen_kalj.json` carries the full 3-temperature campaign with `integrator: baoab_langevin` and `T_target` per state point. The smoke version `configs/examples/plan_pedersen_kalj_smoke.json` is a single-temperature N=200 quick-launch suitable for the README Quickstart guide. After approval, validate via:

```
python scripts/validate_config.py configs/plan_pedersen_kalj.json --strict
```

Then launch via:

```
python scripts/run_experiment.py configs/plan_pedersen_kalj.json
```

---

End of worked example.
