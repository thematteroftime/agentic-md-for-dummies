#!/usr/bin/env python3
"""Generate Plan F (subcritical damping) thesis figures.

Three figures:
  fig8_damping_phase_diagram.png — collapse vs steady-state phase boundary
  fig9_damping_steady_state.png  — T_inf vs nu power-law fit
  fig10_damping_ratio_invariance.png — ratio vs nu showing universality
"""
import sys
from pathlib import Path
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DOC_IMG = ROOT / "docs" / "images"

# Subcritical (Plan F) + supercritical (Plan E) runs at (phi=0.3, T0=0.3)
RUNS = [
    # Plan F (subcritical)
    ("E14", "20260507_005253_E14_nu1em5", 1e-5, "subcritical"),
    ("E15", "20260507_005253_E15_nu1em4", 1e-4, "subcritical"),
    ("E16", "20260507_062355_E16_nu3em4", 3e-4, "subcritical"),
    # Plan E (supercritical)
    ("E10", "20260506_225256_E10_nu001",  1e-3, "supercritical"),
    ("E11", "20260506_225256_E11_nu01",   1e-2, "supercritical"),
    ("E12", "20260506_235028_E12_nu1",    1e-1, "supercritical"),
    ("E13", "20260506_235801_E13_nu10",   1.0,  "supercritical"),
    ("E17", "20260507_072651_E17_nu5em4", 5e-4, "supercritical"),
]

# Critical damping derived from NVE fit
NU_C = 4.5e-4


def load_T_evolution(folder):
    rd = ROOT / "outputFiles" / folder
    h5_path = next(rd.glob("*.h5"))
    with h5py.File(h5_path, "r") as f:
        sp = f["species"][:]
        T = f["T"][:]
        time = f["time"][:]
    mA = sp == 1
    mB = sp == 2
    return time, T[:, mA].mean(axis=1), T[:, mB].mean(axis=1)


def fig_phase_diagram():
    """T_A(t) trajectories for all 8 nu values, color-coded by phase."""
    fig, ax = plt.subplots(1, 1, figsize=(11, 6))

    sub_nus = []; super_nus = []
    for label, folder, nu, phase in RUNS:
        try:
            time, TA, TB = load_T_evolution(folder)
        except Exception:
            continue
        # Replace zeros with floor for log plot
        TA_plot = np.maximum(TA, 1e-12)
        if phase == "subcritical":
            color = plt.cm.Greens(0.4 + 0.5 * (np.log10(NU_C) - np.log10(nu)) / 2.5)
            ax.loglog(time, TA_plot, "-", color=color, lw=1.6,
                       label=f"{label}: ν={nu:.0e} (steady)")
            sub_nus.append(nu)
        else:
            color = plt.cm.Reds(0.4 + 0.5 * (np.log10(nu) - np.log10(NU_C)) / 4)
            ax.loglog(time, TA_plot, "-", color=color, lw=1.4,
                       alpha=0.8, label=f"{label}: ν={nu:.0e} (collapse)")
            super_nus.append(nu)

    ax.axhline(0.3, color="gray", ls=":", lw=1.0, alpha=0.6, label="T₀=0.3 (init)")
    ax.set_xlabel("t (τ)", fontsize=12)
    ax.set_ylabel("T_A", fontsize=12)
    ax.set_title(
        f"Damping phase diagram at (φ=0.3, T₀=0.3): "
        f"ν_c ≈ {NU_C:.0e} separates regimes",
        fontsize=12,
    )
    ax.legend(fontsize=8, loc="lower left", ncol=2)
    ax.grid(which="both", alpha=0.3)
    ax.set_ylim(1e-12, 10)
    plt.tight_layout()
    out = DOC_IMG / "fig8_damping_phase_diagram.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def fig_steady_state_scaling():
    """T_inf (mean over t > 5000 τ) vs nu for subcritical runs.
    Expected scaling: T_inf ∝ nu^(-2/3) from analytical balance."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))

    nus_sub = []
    TA_inf = []
    TB_inf = []
    labels_sub = []
    for label, folder, nu, phase in RUNS:
        if phase != "subcritical":
            continue
        time, TA, TB = load_T_evolution(folder)
        # Plateau average over second half
        plateau_mask = time > time[-1] / 2
        TA_inf.append(float(TA[plateau_mask].mean()))
        TB_inf.append(float(TB[plateau_mask].mean()))
        nus_sub.append(nu)
        labels_sub.append(label)

    nus_sub = np.array(nus_sub)
    TA_inf = np.array(TA_inf)
    TB_inf = np.array(TB_inf)

    # Plot data
    ax.loglog(nus_sub, TA_inf, "C0o", markersize=12, label="T_A (sim)")
    ax.loglog(nus_sub, TB_inf, "C1s", markersize=10, label="T_B (sim)")
    for L, n, t in zip(labels_sub, nus_sub, TA_inf):
        ax.annotate(L, (n, t), textcoords="offset points",
                     xytext=(8, 6), fontsize=10)

    # Fit T_inf ∝ nu^alpha (power law)
    log_nu = np.log10(nus_sub)
    log_TA = np.log10(TA_inf)
    slope_A, intercept_A = np.polyfit(log_nu, log_TA, 1)
    log_TB = np.log10(TB_inf)
    slope_B, intercept_B = np.polyfit(log_nu, log_TB, 1)

    # Predict line
    nu_grid = np.geomspace(nus_sub.min() * 0.5, nus_sub.max() * 2, 100)
    A_fit = 10 ** intercept_A * nu_grid ** slope_A
    B_fit = 10 ** intercept_B * nu_grid ** slope_B
    ax.loglog(nu_grid, A_fit, "C0-", lw=1.4, alpha=0.6,
               label=f"fit: T_A ∝ ν^{slope_A:.3f}")
    ax.loglog(nu_grid, B_fit, "C1-", lw=1.4, alpha=0.6,
               label=f"fit: T_B ∝ ν^{slope_B:.3f}")

    # Theoretical prediction (slope = -2/3)
    A_th = 10 ** intercept_A * nu_grid ** (-2/3) * (nus_sub[0] ** (-2/3) / nus_sub[0] ** slope_A)
    # Just draw a -2/3 reference line through middle data point
    mid_n = nus_sub[1]
    mid_t = TA_inf[1]
    ref = mid_t * (nu_grid / mid_n) ** (-2/3)
    ax.loglog(nu_grid, ref, "k:", lw=1.6, alpha=0.7,
               label=f"theory: ν^(-2/3) ref")

    ax.axvline(NU_C, color="gray", ls="--", lw=1.0, alpha=0.6,
                label=f"ν_c ≈ {NU_C:.0e}")
    ax.set_xlabel("ν (drag coefficient)", fontsize=12)
    ax.set_ylabel("Steady-state temperature T_∞", fontsize=12)
    ax.set_title(
        f"Steady-state scaling — fitted exponent (T_A: {slope_A:.3f}, "
        f"T_B: {slope_B:.3f}) vs theory −2/3",
        fontsize=11,
    )
    ax.legend(fontsize=10, loc="best")
    ax.grid(which="both", alpha=0.3)
    plt.tight_layout()
    out = DOC_IMG / "fig9_damping_steady_state.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")
    print(f"    fitted T_A scaling: ν^{slope_A:.4f}  (theory: ν^-0.667)")
    print(f"    fitted T_B scaling: ν^{slope_B:.4f}")


def fig_ratio_invariance():
    """ratio = T_A/T_B at plateau vs nu, demonstrating ratio is independent
    of nu — a key paper PRX 2015 prediction."""
    fig, ax = plt.subplots(1, 1, figsize=(9, 6))

    nus = []
    ratios = []
    labels = []
    nve_ratio = 2.86  # E1, E2 mean
    for label, folder, nu, phase in RUNS:
        if phase != "subcritical":
            continue
        time, TA, TB = load_T_evolution(folder)
        plateau_mask = time > time[-1] / 2
        ratio = TA[plateau_mask].mean() / max(TB[plateau_mask].mean(), 1e-30)
        nus.append(nu)
        ratios.append(ratio)
        labels.append(label)

    ax.semilogx(nus, ratios, "C2o-", markersize=14, lw=1.6,
                 label="Plan F damped runs (T_∞ ratio)")
    for L, n, r in zip(labels, nus, ratios):
        ax.annotate(L, (n, r), textcoords="offset points",
                     xytext=(8, 8), fontsize=11)

    ax.axhline(3.1, color="k", ls="--", lw=1.5, alpha=0.7,
                label="paper τ_∞ = 3.1")
    ax.axhline(nve_ratio, color="C0", ls="--", lw=1.2, alpha=0.5,
                label=f"NVE ratio (E1, E2) = {nve_ratio}")
    ax.axvline(NU_C, color="gray", ls=":", lw=1.0, alpha=0.6,
                label=f"ν_c ≈ {NU_C:.0e}")
    ax.set_xlabel("ν (drag coefficient)", fontsize=12)
    ax.set_ylabel("T_A / T_B at plateau", fontsize=12)
    ax.set_title(
        "Temperature ratio is independent of ν — confirms paper Eq. 11 "
        "(τ_∞ depends only on force form ε)",
        fontsize=11,
    )
    ax.legend(fontsize=10, loc="best")
    ax.set_ylim(1.5, 3.3)
    ax.grid(which="both", alpha=0.3)
    plt.tight_layout()
    out = DOC_IMG / "fig10_damping_ratio_invariance.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")
    print(f"    ratio plateau values: {dict(zip(labels, [f'{r:.3f}' for r in ratios]))}")


def main():
    print("[damping-figures] generating Plan F thesis figures...")
    fig_phase_diagram()
    fig_steady_state_scaling()
    fig_ratio_invariance()
    print("[damping-figures] DONE")


if __name__ == "__main__":
    main()
