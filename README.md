<h1 align="center">Agentic MD-for-Dummies</h1>

<p align="center">
  <strong>A small but complete molecular-dynamics framework for reproducing physics papers — driven by an AI skill that turns a paper into a runnable experiment config.</strong>
</p>

<p align="center">
  <a href="#what-this-is">What this is</a> •
  <a href="#how-it-works">How it works</a> •
  <a href="#quickstart">Quickstart</a> •
  <a href="#the-ai-skill-workflow">AI Skill Workflow</a> •
  <a href="#adding-your-own-paper">Add Your Paper</a> •
  <a href="#references">References</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Taichi-1.7.4-orange" alt="Taichi"/>
  <img src="https://img.shields.io/badge/Claude%20Skill-paper--to--experiment-7b53d6" alt="Claude Skill"/>
</p>

---

## What this is

Most MD papers come with screenshots, a methods section, and a wave goodbye. **Reproducing them takes weeks.** You read the paper, decode the parameters, build a runner, glue together force fields, write analysis, plot figures, then realize you misread `T₀=0.3` as `T=0.3`.

`agentic-md-for-dummies` is a **paper-driven workflow** built on a minimal Taichi MD core. It is:

> **Not** another high-performance MD engine. There are excellent ones (LAMMPS, GROMACS, GPUMD).
>
> **Yes** a teaching framework that shows the full path: *paper → parameters → simulation → analysis → figure*, and lets you swap papers by writing one config file plus (when needed) one adapter.

It ships with two **end-to-end reproductions** of recent complex-plasma papers as worked examples:

- Ivlev et al., *Phys. Rev. X* **5**, 011035 (2015) — non-reciprocal Hertzian, two-temperature steady state
- Ivlev et al., *Phys. Rev. Lett.* **100**, 095003 (2008) — anisotropic Yukawa, chain formation

### What's inside

| | |
|---|---|
| 🧱 **4-layer architecture** | Config → Adapter → Platform → Infrastructure. Each layer talks only to the one below it. |
| 🤖 **AI skill** | A Claude Code skill (`paper-to-experiment`) that walks a paper into a validated config in 7 steps, with an 8-step extension flow for new force / analyzer / plotter / aggregator and a 9-step flow for a new time integrator. |
| 📋 **Schema-validated configs** | JSON Schema + physics rules + budget guards. Bad configs fail before any GPU is touched. |
| 🔌 **Class-name dispatch** | Add a new analyzer / visualizer / aggregator? One file + one registry line. No central if-else. |
| 🧪 **Layered testing** | Schema gate, manifest gate, registry gate, runtime gate. Every contract has an enforcement point. |
| 📐 **Three reference papers** | PRX 2015 (slope_A=2/3 to within 1%), PRL 2008 (chain phase, ⟨L⟩=5.15 at MT=0.8), and PRL 2018 KA binary LJ (g_AB peak < g_AA peak across 3 temperatures). |

---

## Why "for-Dummies"?

Because reproducing a physics paper shouldn't require:

- ❌ a custom 5000-line C++ runner per paper
- ❌ a 30-step manual lab notebook of "convert φ to N then to box length"
- ❌ guessing whether `dt` is in fs or τ
- ❌ rebuilding the analysis pipeline every time

It should look like:

```bash
# Tell the AI which paper to reproduce
$ /paper-to-experiment Ivlev_PRX_2015.pdf

# Skill walks the design template, asks ASK USER: questions if any,
# then emits a validated config file:
configs/plan_prx_t0sweep.json    ✓ schema valid
                                  ✓ physics rules pass
                                  ✓ within budget (4 hr/run)

# You launch it
$ python scripts/run_experiment.py configs/plan_prx_t0sweep.json
```

That's it. No new force class to write (PRX 2015's force already exists), no analyzer to plumb, no figure code to copy-paste.

---

## How it works

The framework is **strictly four-layered**. Each layer talks only to the one below. Mixing layers is the #1 source of bugs.

```
╔══════════════════════════════════════════════════════════════════════╗
║  Layer 4 — CONFIG     (data, no code)                                 ║   ← USER WRITES
║  configs/plan_*.json — campaign list, phases, class names             ║     this every paper
╠══════════════════════════════════════════════════════════════════════╣
║  Layer 3 — ADAPTER     (per-paper, follows TEMPLATE)                  ║   ← USER WRITES
║  prx_nonreciprocal_run.py, er_plasma_run.py                           ║     this for new papers
╠══════════════════════════════════════════════════════════════════════╣
║  Layer 2 — PLATFORM    (paper-agnostic, frozen unless bug)            ║   ← FRAMEWORK
║  scripts/run_experiment.py — orchestrator                              ║     OWNS this
║  tools/ — analyzers, plotters, aggregators, visualizers, registry      ║
╠══════════════════════════════════════════════════════════════════════╣
║  Layer 1 — INFRASTRUCTURE  (Taichi MD core; math frozen,              ║
║  structural extensions OK via forces/ + integrators/ packages)         ║
║  systemClass, atomSystemClass, searchBox, forces/, integrators/, ...   ║
╚══════════════════════════════════════════════════════════════════════╝
```

A single run goes through six numbered phases:

```
0. validate config   (JSON Schema + physics + budget)        — no GPU touched
1. preflight         (resource estimate per run)             — no GPU touched
2. smoke             (default 100 steps, catches crashes)
3. production        (the real run, parallel-safe)
4. visualize         (optional, registry-dispatched)         — Taichi UI / mp4
5. aggregate         (optional, cross-run figures + report)
```

Full architecture spec: [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Quickstart

### Install

```bash
git clone https://github.com/thematteroftime/agentic-md-for-dummies
cd agentic-md-for-dummies
pip install -r requirements.txt
```

> **GPU note**: this project uses Taichi 1.7.4 with CUDA. CPU-only Taichi works for the smoke tests but is slow for production-scale runs. Tested on RTX 5060 Laptop (8 GB VRAM).

### Validate an example config (no compute)

Every config goes through three pre-launch gates before any GPU is touched. Try them:

```bash
# Schema + physics + budget validation. Exits 0 = ready to launch.
python scripts/validate_config.py configs/examples/plan_g_er_chains.json --strict
```

The validator prints a cost estimate (per-run wall + total VRAM). Re-run with `--strict` to fail on warnings.

### Run a small example

The PRL 2008 short ER plasma campaign (5 runs × 50k steps ≈ 20 min on RTX 5060):

```bash
python scripts/run_experiment.py configs/examples/plan_g_er_chains.json
```

Outputs go to `outputFiles/<TS>_<tag>/` per run (HDF5 trajectory + manifest.json + per-run report.md). Cross-run figures land in `docs/images/` once Phase 4 (aggregate) runs.

> **Heavier examples** (multi-hour, e.g. `plan_e_damping.json`, `plan_g2_er_long.json`) are listed in `configs/examples/` for reference. Validate them first; launch only when you've budgeted the wall time.

### Run the test suite

```bash
pytest tests/ -q
```

This exercises the schema, registry, validators, and contract conformance in seconds.

### Standalone utilities

Three CLI helpers under `scripts/` that don't fit in the main pipeline:

| Script | Purpose |
|--------|---------|
| `scripts/bench_neighbor.py` | Benchmark cell-list (`cho=1`) vs O(N²) (`cho=2`) at several N — picks the right `cho` for your hardware. |
| `scripts/compute_delta_eff.py` | Numerically integrate the PRX 2015 `Δ_eff` and `ε` fingerprints from the force kernel — sanity-check before launching a Hertzian non-reciprocal campaign. |
| `scripts/two_particle_calibration.py` | Two-particle controlled-collision test for the Hertzian non-reciprocal force — verifies single-pair energy injection against paper Eq. (5). |
| `scripts/visualize_er_h5.py` | Real-time Taichi-UI animation of any HDF5 trajectory; also wrapped as `TaichiTrajectoryViz` in `tools/visualizers/` for config-driven dispatch. |

---

## Two ways to use this repo

The skill is the headline feature, but the framework underneath it is plain Python and runs perfectly well without any AI in the loop. Pick the path that matches who you are.

### 🤖 If you are an AI agent

Your contract is the skill at `.claude/skills/paper-to-experiment/`. Read `SKILL.md` first; everything else (templates, registry, worked examples) is referenced from it. The shortest valid invocation is a single sentence in a Claude Code conversation:

> *"Reproduce `papers/pedersen_prl2018.pdf` in this framework. Smoke-scale, NVT, three temperatures along the rho=1.2 isochore."*

What happens next is the skill's 7-step config flow, which the skill itself describes. The two extension flows (8-step force, 9-step integrator) only fire when the paper actually requires a class the framework does not yet ship; in that case the skill stops at design-doc §2a or §3 and surfaces the choice for human greenlight before any code lands.

A few prompt patterns that have proven robust across the five autonomous sub-agent rounds that produced this version:

<details>
<summary>Reproduction prompt — paper already covered by an existing force class</summary>

```
Reproduce <paper title and citation> using paper-to-experiment.

Inputs:
  paper PDF: papers/<slug>.pdf
  scope:     <smoke | small production | full>; bound runs at <N>, steps at <M>;
             3 state points on the (T, rho) isochore unless paper indicates more.

Constraints:
  - Use the existing force_type if the paper's potential is already covered;
    otherwise stop at design doc §2a and ask before extending.
  - Default integrator is baoab_drag for NVE / structural runs and
    baoab_langevin for diffusion-sensitive runs (paper observable decides).
  - Do NOT commit. Hand back the design doc + config + first run dir.
```

</details>

<details>
<summary>Extension prompt — paper introduces a new force class or integrator</summary>

```
The paper at papers/<slug>.pdf needs a new <force class | integrator>
that the framework does not currently ship. Walk the
references/force_types.md §<4 | 5b> extension flow end-to-end:

  1. Implement the new class under forces/<name>.py or integrators/<name>.py
  2. Tests in tests/test_<name>_<N>cases.py
  3. Register in tools/registry.py + the matching package's __init__.py
  4. Schema enum + conditional in templates/plan_config.schema.json
  5. Validator branch (per-force-type or per-integrator)
  6. Adapter wiring; analyzer / plotter / aggregator if step 7-8 of force flow

Then re-run the campaign and verify Hard rule #9 holds (manifest + report
+ at least one fig per run dir). Critique to docs/specs/<date>-<topic>-critique.md.
```

</details>

<details>
<summary>Audit prompt — release readiness</summary>

```
Cross-validate that:
  1. tools/registry.py:_REGISTRY entries are mirrored in each package's
     local __init__.py (forces/, integrators/, tools/{analyzers,plotters,aggregators}/)
  2. schema enum values for force_type and integrator both have working adapters
     and are documented in references/force_types.md
  3. SKILL.md hard rules + force_types.md §3 conventions table + worked examples
     are mutually consistent
  4. README and ARCHITECTURE describe the same code that is on main
  5. pytest -q passes (one pre-existing flaky failure in test_units_reconfigure
     is acceptable; everything else must pass)

Report confirmed bugs separately from open questions; ask before fixing
anything ambiguous.
```

</details>

The skill assumes the paper PDF is on disk under `papers/`. Abstract-only reproductions are unsupported by SKILL Hard rule #2 — they have produced bad reproductions in the past — and the skill will stop and surface the gap rather than guess.

### 👤 If you are a human developer

You can drive every part of the framework by hand. The skill is a convenience layer on top of the same Python that you write directly when you choose to. The smallest end-to-end addition without any AI involvement is:

**1. Define a new force class.** One file in `forces/`, subclass `forceField`, declare `requires_full_list` and `PREFLIGHT_FIELDS`, implement `updateOneF_reciprocal` (or `updateOneF_nonreciprocal`):

```python
# forces/my_potential.py
from constSet import *
from forces.base import forceField


@ti.data_oriented
class MyPotential(forceField):
    requires_full_list = True
    PREFLIGHT_FIELDS = ("T0", "rho", "N", "steps")

    def __init__(self, sigma, eps):
        self.sigma = float(sigma)
        self.eps = float(eps)
        self.reciprocal = True

    @ti.func
    def updateOneF_reciprocal(self, i: ti.i32, j: ti.i32):
        rij = self.searchBox.applyMic(self.atomSystem.pos[j] - self.atomSystem.pos[i])
        r = rij.norm()
        if r * r <= self.cutoffSquare:
            # f_mag = -dV/dr; example here is a soft-core 1/r^4 well.
            f_mag = self.eps * self.sigma**4 / r**5
            self.atomSystem.force[i] += -f_mag * (rij / r)
            U_pair = self.eps * self.sigma**4 / (3.0 * r**3)
            self.atomSystem.pe_per_atom[i] += 0.5 * U_pair
```

**2. Register the class** in two places — one local, one global:

```python
# forces/__init__.py — local registry, used by direct imports
from forces.my_potential import MyPotential

FORCE_REGISTRY: dict[str, type] = {
    "lennard_jones":          lennardJones,
    "er_plasma":              ERPotential,
    "hertzian_nonreciprocal": HertzianNonreciprocal,
    "kalj":                   KobAndersenLJ,
    "my_potential":           MyPotential,    # ← new line
}

# tools/registry.py — single forwarding station
_REGISTRY: dict[str, str] = {
    # ... existing entries ...
    "MyPotential": "forces.my_potential:MyPotential",
}
```

The regression test `tests/test_skill_regression.py:test_registry_local_init_sync` will fail loudly the next time `pytest -q` runs if either side drifts.

**3. Write a campaign config** that references the new force_type and validate it before launching anything:

```bash
cat > configs/plan_my_potential.json << 'EOF'
{
  "_comment": "Smoke run for MyPotential — verify the kernel compiles and ships.",
  "_force_type_doc": "references/force_types.md (pending §N for my_potential)",
  "_units_doc": "reduced_lj",
  "campaign": [{
    "force_type": "my_potential",
    "tag": "mp_smoke",
    "T0": 1.0,
    "N": 200,
    "steps": 5000,
    "stride": 50,
    "ndim": 3,
    "units_regime": "reduced_lj"
  }],
  "pipeline": {"preflight": true, "smoke": true, "smoke_steps": 100,
               "production": true, "halt_on_fail": true, "max_parallel": 1}
}
EOF
python scripts/validate_config.py configs/plan_my_potential.json --strict
python scripts/run_experiment.py configs/plan_my_potential.json
```

The validator will reject the config until you have also extended the schema enum, the dispatcher branch in `scripts/run_experiment.py:_invoke_md`, and the `check_force_type_specific` branch in `scripts/validate_config.py` — these are the steps that the AI skill walks through automatically and that you would do by hand here. The full per-step recipe is in `references/force_types.md §4 "Adding a new force type"`; the file numbers and registration points line up exactly with the AI workflow above.

For an integrator extension the path is parallel: subclass `IntegratorBase` in `integrators/`, declare `REQUIRED_KWARGS` and `OPTIONAL_KWARGS`, implement `inteBegin`, register in `INTEGRATOR_REGISTRY` + `_REGISTRY`, extend the schema's `integrator` enum, and (optionally) add a stability rule to `check_integrator_specific`. `integrators/baoab_drag.py` is the simplest reference; `integrators/baoab_langevin.py` shows the Wiener-noise variant including the `(1 − α²)·k_B·T/m` FD prefactor. The full 9-step recipe is in `references/force_types.md §5b`.

Either way — AI or human — the same regression tests gate the same contracts, the same registry holds the same classes, and the same `pytest -q` says yes or no.

---

## The AI Skill Workflow

The unique value of this repo is in `.claude/skills/paper-to-experiment/` — a [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills) that takes you from a PDF to a runnable config without you typing a single param twice.

### How AI uses the skill

```
1. You drop a paper in the conversation:
   "Reproduce Ivlev PRX 2015 Fig 1 — sweep T₀ at fixed φ=0.3, NVE."

2. Claude invokes paper-to-experiment skill, which:
   a. Reads .claude/skills/paper-to-experiment/SKILL.md (the contract)
   b. Reads references/force_types.md (which force types this repo knows)
   c. Reads references/examples/ (worked examples from existing papers)
   d. Reads the actual paper PDF you provided

3. Claude fills templates/physics_design.md (12 sections):
   §1 observables (with paper Eq. citations)
   §2 force field choice
   §3 simulation params
   §4 sweep dimensions
   §5-§7 phases, pass criteria, costs
   §10b ASK USER: items it can't decide alone

4. You review the design doc. If §10b is empty (auto-mode safe),
   Claude proceeds; otherwise it stops and asks.

5. Claude emits configs/plan_<topic>.json from the design doc.

6. Claude runs `validate_config.py --strict`. If exit ≠ 0, fix and retry.

7. Hands off the launch command. You decide when to spend GPU.
```

The skill enforces:

- **Citations are mandatory.** Every observable cites a paper Eq. or Fig. number.
- **No silent invention.** Missing param → `ASK USER:`, never a guess.
- **Smoke before production.** Always. No skipping.
- **Budget guards.** Single-run wall > 24 hr or VRAM > 8 GB → reject, propose smaller.
- **Reuse before extending.** New force class only when no existing one matches the paper's Eq.

### What if the paper needs a force type that doesn't exist yet?

The skill walks you through the 8-step extension process documented in `force_types.md` §4:

1. Add the force class to `forces/<your_force>.py` (template provided) + register in `forces/__init__.py:FORCE_REGISTRY` and `tools/registry.py:_REGISTRY`
2. Write tests
3. Create an entry script (Layer 3 adapter, template provided)
4. Update `scripts/run_experiment.py:_invoke_md` dispatcher AND `scripts/validate_config.py:check_force_type_specific`
5. Update the schema enum
6. Document in the registry
7. Add an analyzer (`tools/analyzers/<paper>.py`) producing `report.md`
8. Add a plotter (`tools/plotters/<paper>.py`) producing `fig*.png`

Each step has a template file under `.claude/skills/paper-to-experiment/templates/`.

---

## Adding your own paper

The fastest case is when the paper reuses a force type that the framework already ships. Pick a starter that is closest to your physics — `configs/examples/plan_g_er_chains.json` for an anisotropic-Yukawa-flavoured paper, or `configs/examples/plan_pedersen_kalj_smoke.json` for a binary-mixture or diffusion-sensitive paper that needs the FD-balanced thermostat — then iterate locally:

```
1.  cp configs/examples/plan_pedersen_kalj_smoke.json configs/plan_<your_topic>.json
2.  Edit campaign[0] params per the paper. Cite Eq./Fig. in `notes`.
3.  python scripts/validate_config.py configs/plan_<your_topic>.json --strict
4.  python scripts/run_experiment.py  configs/plan_<your_topic>.json
```

The bigger case applies when the paper introduces a new force, a new integration scheme, a paper-specific analyzer, or a paper-specific plotter / aggregator. The skill ships templates for each extension point, and `references/force_types.md §4` (force class) plus `§5b` (integrator) document the corresponding 8-step and 9-step extension flows. Drop each template into the correct package, then add one row each to `tools/registry.py` and to the matching package's local registry — the regression tests will fail loudly if either side drifts.

| Goal | Copy template | Save as |
|------|---------------|---------|
| New force type | `templates/force_class.py.template` | `forces/<your_force>.py` |
| New integrator scheme | `templates/integrator.py.template` | `integrators/<your_scheme>.py` |
| New paper adapter | `templates/adapter_run.py.template` | `<topic>_run.py` |
| New analyzer | `templates/analyzer.py.template` | `tools/analyzers/<topic>.py` |
| New plotter | `templates/plotter.py.template` | `tools/plotters/<topic>.py` |
| New aggregator | `templates/aggregator.py.template` | `tools/aggregators/<topic>.py` |
| New visualizer | `templates/visualizer.py.template` | `tools/visualizers/<topic>.py` |

---

## Reference reproductions

Three papers are reproduced end-to-end and shipped as worked examples in this repository. Each is a complete walk through the skill: a JSON config under `configs/`, a per-paper analyzer / plotter / aggregator under `tools/`, and either reproduction figures committed to `docs/images/` (PRX 2015, PRL 2008) or a cross-run report rendered into `docs/` on demand (PRL 2018). The first two cover the original physics-engine validation; the third was added during the `v0.2.0` cycle to exercise the binary-mixture force extension and the FD-balanced Langevin integrator extension on the same paper.

### Ivlev et al., *Phys. Rev. X* 5, 011035 (2015)

**Non-reciprocal Hertzian binary mixture, two-temperature NVE asymptote.**

| Observable | Paper | Reproduced | Error |
|------------|-------|------------|-------|
| slope_A (T_A ∝ t^α) | 2/3 ≈ 0.667 | 0.6617 | 0.74% |
| τ_∞ = T_A/T_B | 3.10 | 2.86 | 7.9% |
| Δ_eff (analytical fingerprint) | 0.57 | 0.5714 | 0.25% |
| ε (analytical fingerprint) | 0.082 | 0.0822 | 0.19% |

<p align="center">
  <img src="docs/images/fig5_best_case_E2_showcase.png" width="600px" alt="PRX 2015 best-case showcase"/>
  <br><em>Figure 5 — Best-case showcase: slope=2/3 + τ asymptote + KE growing.</em>
</p>

<details>
<summary>More PRX figures (click to expand)</summary>

- `docs/images/fig1_multi_T0.png` — multi-T₀ trajectories
- `docs/images/fig2_multi_phi.png` — multi-φ + n^(2/3) collapse
- `docs/images/fig7_E2_engine_diagnostics.png` — momentum drift √t (Newton 3rd violation)
- `docs/images/fig8_damping_phase_diagram.png` — bifurcation across critical damping ν_c
- `docs/images/fig10_damping_ratio_invariance.png` — T_A/T_B independent of ν

</details>

### Ivlev et al., *Phys. Rev. Lett.* 100, 095003 (2008)

**Anisotropic Yukawa potential, chain formation in electrorheological complex plasmas.**

| Observable | Paper | Reproduced |
|------------|-------|------------|
| g_∥/g_⊥ ratio at chain peak (MT=0.8) | > 2× | **5.33×** |
| chain spacing r* | ≈ 4λ | 3.6 λ |
| optimal MT regime | [0.6, 0.9] | [0.7, 0.9] (Q-peak monotonic) |
| ⟨L⟩ at MT=0.8 (paper qualitative) | "chains form" | **5.15 particles, 84% of system** |
| Sonic instability (MT→1) | qualitative | **0 chains @ MT=1.0** |

<p align="center">
  <img src="docs/images/fig15_er_long_g_at_chain_peak.png" width="700px" alt="PRL 2008 chain signature"/>
  <br><em>Figure 15 — g_∥(r) vs g_⊥(r) at peak chain time. ER4L (MT=0.8) shows the textbook chain signature: dominant axial peak at r ≈ 3.6λ, suppressed transverse correlation.</em>
</p>

<p align="center">
  <img src="docs/images/fig17_er_chain_length_dist.png" width="700px" alt="PRL 2008 chain length stats"/>
  <br><em>Figure 17 — Chain length distribution. ⟨L⟩ peaks at MT=0.8; collapses at sonic limit MT=1.</em>
</p>

### Pedersen, Schrøder, Dyre, *Phys. Rev. Lett.* 120, 165501 (2018)

**Kob-Andersen binary Lennard-Jones mixture, structural and dynamic verification.** This reproduction is qualitative by design: the engine has no NPT and no Frenkel-Ladd free-energy integration, so the paper's central coexistence-line claim (T_m = 1.028 at ρ = 1.2) is documented as out of scope and the campaign instead targets the partial radial distribution functions and per-species diffusivity along the (T = {0.7, 1.0, 1.3}, ρ = 1.2) isochore.

| Observable | Paper / analytic target | Reproduced (T = 1.0, ρ = 1.2) |
|------------|--------------------------|-------------------------------|
| g_AA first peak | σ_AA · 2^{1/6} ≈ 1.122 σ_AA | 1.094 σ_AA (2.5% under) |
| g_AB first peak | σ_AB · 2^{1/6} ≈ 0.898 σ_AA | 0.906 σ_AA (0.9% over) |
| g_AB peak < g_AA peak | strict ordering from σ_AB < σ_AA | satisfied at all three temperatures |
| T_meas vs T_target (FD setpoint) | within 5% on the late half of the trajectory | 0.27% at T = 1.3, 0.78% at T = 1.0, 0.80% at T = 0.7 |
| Diffusivity ordering D_B > D_A | implied by σ_BB < σ_AA | D_B / D_A ≈ 1.4 at all three temperatures |

The campaign is the canonical example of the joint **8-step force extension** (`forces/kalj.py:KobAndersenLJ` + analyzer / plotter / aggregator) and **9-step integrator extension** (`integrators/baoab_langevin.py:BAOABLangevin`) flow. The full design walkthrough lives at `.claude/skills/paper-to-experiment/references/examples/worked_example_PRL2018_KALJ.md`. The campaign config that produced the numbers above is `configs/plan_pedersen_kalj.json`; for a sub-minute smoke run, see `configs/examples/plan_pedersen_kalj_smoke.json`.

---

## Project layout

```
agentic-md-for-dummies/
├── README.md                       this file
├── ARCHITECTURE.md                 the 4-layer + 6-phase spec (~400 lines)
├── LICENSE                         MIT
├── requirements.txt
│
├── .claude/skills/
│   ├── paper-to-experiment/        the AI skill that drives the workflow
│   │   ├── SKILL.md                7-step config flow + 8-step extension + hard rules
│   │   ├── templates/              physics_design.md, plan_config.schema.json
│   │   └── references/             force_types registry + worked examples
│   └── creator/                    meta-skill (generate a paper-to-experiment
│                                    skill for a different framework — WIP)
│
├── configs/examples/               worked example configs (PRX-era, ER, and a KA-LJ smoke)
│
├── tools/                          platform package (registry-dispatched)
│   ├── analyzers/{prx,er,pedersen}.py
│   ├── plotters/{prx,pedersen}.py
│   ├── aggregators/{prx,er,pedersen}.py
│   ├── lattices/{square_2d,triangular_2d,octagonal_2d,simple_cubic_3d}.py
│   ├── visualizers/taichi_traj.py
│   ├── registry.py                 name → class lookup
│   ├── runner.py / resources.py / file_io.py
│   ├── validate_manifest.py        post-run §3.2 contract gate
│   └── migrate_manifests.py        backfill canonical fields in old manifests
│
├── scripts/
│   ├── run_experiment.py           the SOLE entry point
│   ├── validate_config.py          schema + physics + budget gate
│   └── analyze_er.py               ER analysis CLI (chain / long / length)
│
├── prx_nonreciprocal_run.py        Layer 3 adapter — PRX 2015
├── er_plasma_run.py                Layer 3 adapter — PRL 2008
│
├── forces/                         Layer 1 — one file per force class (HertzianNonreciprocal, ERPotential, LJ, KobAndersenLJ)
├── integrators/                    Layer 1 — one file per integrator scheme (BAOABDrag, BAOABLangevin)
├── systemClass.py                  Layer 1 — MD orchestrator
├── atomSystemClass.py              Layer 1 — particle state
├── searchBox.py                    Layer 1 — cell-list / O(N²) neighbor table
├── constSet.py                     Layer 1 — units (reduced / macro)
├── toolClass.py                    backward-compat shim for the tools/ split
│
├── tests/                          pytest contract + regression tests
└── docs/images/                    reproduction figures (8 selected)
```

---

## Contributing

This is a teaching framework — the goal is **clarity over performance, reproducibility over feature count**. Pull requests welcome, especially:

- new paper reproductions (with worked example config + adapter + analyzer)
- new analyzers / visualizers / aggregators
- documentation / explanatory diagrams in `ARCHITECTURE.md`

Less welcome:

- alternative integrators / accelerators (the Layer 1 core is intentionally frozen)
- giant abstraction layers — the simplicity is a feature

When opening a PR for a new paper:

1. Add a config under `configs/examples/`
2. If the paper needs a new force, follow `force_types.md` §4 (the 8-step extension process)
3. Add tests under `tests/`
4. Add 1-2 reproduction figures to `docs/images/` and reference them in your example config's `_design_doc`

---

## References

- Ivlev, A. V. *et al.* "Statistical mechanics where Newton's third law is broken." *Phys. Rev. X* **5**, 011035 (2015). [DOI:10.1103/PhysRevX.5.011035](https://doi.org/10.1103/PhysRevX.5.011035)
- Ivlev, A. V. *et al.* "First Observation of Electrorheological Plasmas." *Phys. Rev. Lett.* **100**, 095003 (2008). [DOI:10.1103/PhysRevLett.100.095003](https://doi.org/10.1103/PhysRevLett.100.095003)
- Pedersen, U. R., Schrøder, T. B., Dyre, J. C. "Phase Diagram of Kob-Andersen-Type Binary Lennard-Jones Mixtures." *Phys. Rev. Lett.* **120**, 165501 (2018). [DOI:10.1103/PhysRevLett.120.165501](https://doi.org/10.1103/PhysRevLett.120.165501)
- Hu, Y. *et al.* "Taichi: a Language for High-Performance Computation on Spatially Sparse Data Structures." *ACM Trans. Graph.* **38**, 6 (2019). The Taichi compiler powering Layer 1.

---

## License

MIT — see [`LICENSE`](LICENSE).

If you use this framework in published work, citing the framework is appreciated but not required. Citing the original physics papers (above) is required.
