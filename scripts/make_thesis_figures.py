#!/usr/bin/env python3
"""Generate publication-quality figures for the thesis with unified E*
naming. Output goes to docs/images/.

Renaming convention (canonical for thesis):
    E1: (phi=0.3, T0=0.3, 20000 tau)   was E1v3   — paper Fig 1 anchor
    E2: (phi=0.3, T0=0.3, 50000 tau)   was E8     — long-time stability
    E3: (phi=0.1, T0=1.0)              was phi01_T1
    E4: (phi=0.3, T0=1.0)              was phi03_T1
    E5: (phi=0.5, T0=1.0)              was old E5
    E6: (phi=0.7, T0=1.0)              was old E6
    E7: (phi=0.9, T0=1.0)              was old E7
    E8: (phi=0.3, T0=0.1)              was phi03_T01
    E9: (phi=0.3, T0=10)               was phi03_T10

Order is grouped by physics: T0=0.3 reference, T0=1 phi-sweep, T0 sweep
at phi=0.3.
"""
import os
import sys
from pathlib import Path
import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from toolClass import PRXAnalyzer

OUT_DIR = ROOT / "outputFiles"
DOC_IMG = ROOT / "docs" / "images"
DOC_IMG.mkdir(parents=True, exist_ok=True)

# Mapping: thesis E# -> folder name
THESIS_MAP = [
    ("E1", "20260502_051425_E1v3",      0.3, 0.3, 20000, "ref"),
    ("E2", "20260505_010133_E8",        0.3, 0.3, 50000, "ref-long"),
    ("E3", "20260506_112106_phi01_T1",  0.1, 1.0, 20000, "phi-sweep"),
    ("E4", "20260506_033731_phi03_T1",  0.3, 1.0, 20000, "phi-sweep+T0-sweep anchor"),
    ("E5", "20260504_200903_E5",        0.5, 1.0, 20000, "phi-sweep"),
    ("E6", "20260505_010133_E6",        0.7, 1.0, 20000, "phi-sweep"),
    ("E7", "20260505_112813_E7",        0.9, 1.0, 20000, "phi-sweep"),
    ("E8", "20260506_033731_phi03_T01", 0.3, 0.1, 20000, "T0-sweep low"),
    ("E9", "20260506_101719_phi03_T10", 0.3, 10,  20000, "T0-sweep high"),
]


def load_run(folder):
    rd = OUT_DIR / folder
    return PRXAnalyzer.load_run(rd)


def latest_slope(rec):
    rows = PRXAnalyzer.rolling_slopes(rec["time"], rec["TA"], rec["TB"])
    if not rows:
        return None
    last = rows[-1]
    err_A = abs(last["slope_A"] - PRXAnalyzer.PAPER_SLOPE) / PRXAnalyzer.PAPER_SLOPE
    err_R = abs(last["ratio"] - PRXAnalyzer.PAPER_RATIO) / PRXAnalyzer.PAPER_RATIO
    return {
        "tmin": last["tmin"],
        "slope_A": last["slope_A"],
        "slope_B": last["slope_B"],
        "ratio":   last["ratio"],
        "err_A":   err_A,
        "err_R":   err_R,
    }


def plot_fig1_multiT0():
    """Paper Fig 1 reproduction — multi-T0 at phi=0.3 sweep."""
    # Use E8 (T0=0.1), E1 (T0=0.3, 20kτ), E2 (T0=0.3, 50kτ),
    # E4 (T0=1), E9 (T0=10)
    targets = ["E8", "E1", "E2", "E4", "E9"]
    cmap = plt.get_cmap("plasma")

    fig, axs = plt.subplots(1, 2, figsize=(13, 5.3))
    for i, label in enumerate(targets):
        meta = next(m for m in THESIS_MAP if m[0] == label)
        _, folder, phi, T0, _, _ = meta
        rec = load_run(folder)
        color = cmap(i / max(1, len(targets) - 1))
        legend = f"{label}: T₀={T0}"
        mask = rec["time"] > 1.0
        axs[0].loglog(rec["time"][mask], rec["TA"][mask], "-",
                       color=color, lw=1.4, label=legend)
        axs[1].loglog(rec["time"][mask], rec["TB"][mask], "-",
                       color=color, lw=1.4, label=legend)

    # Paper t^(2/3) reference
    rec_ref = load_run("20260505_010133_E8")  # E2 has longest range
    t_ref = np.geomspace(10, rec_ref["time"][-1], 60)
    base_idx = 100
    ref = (t_ref / t_ref[0]) ** PRXAnalyzer.PAPER_SLOPE * rec_ref["TA"][base_idx]
    axs[0].loglog(t_ref, ref, "k:", lw=1.6, alpha=0.7, label="t^(2/3) (paper)")
    axs[1].loglog(t_ref, ref, "k:", lw=1.6, alpha=0.7, label="t^(2/3) (paper)")

    for ax, sp in zip(axs, ("T_A", "T_B")):
        ax.set_xlabel("t (τ)", fontsize=12)
        ax.set_ylabel(f"{sp}", fontsize=12)
        ax.set_title(f"{sp} vs t — multi-T₀ sweep at φ=0.3", fontsize=13)
        ax.legend(fontsize=10, loc="best")
        ax.grid(which="both", alpha=0.3)

    plt.tight_layout()
    out = DOC_IMG / "fig1_multi_T0.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def plot_fig2_multi_phi():
    """Paper Fig 2 reproduction — multi-phi at T0=1 sweep with n^(2/3)
    collapse inset."""
    targets = ["E3", "E4", "E5", "E6", "E7"]  # phi = 0.1, 0.3, 0.5, 0.7, 0.9
    cmap = plt.get_cmap("viridis")

    fig, axs = plt.subplots(1, 2, figsize=(14, 5.3))
    for i, label in enumerate(targets):
        meta = next(m for m in THESIS_MAP if m[0] == label)
        _, folder, phi, T0, _, _ = meta
        rec = load_run(folder)
        color = cmap(i / max(1, len(targets) - 1))
        legend = f"{label}: φ={phi}"
        t = rec["time"]
        T_sum = rec["TA"] + rec["TB"]
        mask = t > 1.0
        axs[0].loglog(t[mask], T_sum[mask], "-", color=color, lw=1.4,
                       label=legend)
        # n^(2/3) collapse: scale T_A by phi^(2/3)
        n = phi / np.pi
        axs[1].loglog(t[mask], rec["TA"][mask] * n ** (2/3),
                       "-", color=color, lw=1.4, label=legend)

    # paper t^(2/3) reference
    ref_rec = load_run("20260504_200903_E5")
    t_ref = ref_rec["time"][ref_rec["time"] > 1.0]
    T0_ref = (ref_rec["TA"] + ref_rec["TB"])[ref_rec["time"] > 1.0][0]
    ref = (t_ref / t_ref[0]) ** PRXAnalyzer.PAPER_SLOPE * T0_ref
    axs[0].loglog(t_ref, ref, "k:", lw=1.6, alpha=0.7, label="t^(2/3) (paper)")

    axs[0].set_xlabel("t (τ)", fontsize=12)
    axs[0].set_ylabel("T_A + T_B", fontsize=12)
    axs[0].set_title("Multi-φ sweep at T₀=1 (paper Fig 2 main)", fontsize=13)
    axs[0].legend(fontsize=10); axs[0].grid(which="both", alpha=0.3)

    axs[1].set_xlabel("t (τ)", fontsize=12)
    axs[1].set_ylabel("T_A · n^(2/3)", fontsize=12)
    axs[1].set_title("n^(2/3) collapse test (paper Fig 2 right)", fontsize=13)
    axs[1].legend(fontsize=10); axs[1].grid(which="both", alpha=0.3)

    plt.tight_layout()
    out = DOC_IMG / "fig2_multi_phi.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def plot_ratio_overlay():
    """All 9 runs T_A/T_B vs log t (paper Fig 2 inset reproduction)."""
    fig, ax = plt.subplots(1, 1, figsize=(11, 5.5))
    cmap = plt.get_cmap("viridis")
    ordered = sorted(THESIS_MAP, key=lambda m: (m[3], m[2]))  # by T0 then phi
    for i, meta in enumerate(ordered):
        label, folder, phi, T0, _, _ = meta
        rec = load_run(folder)
        color = cmap(i / max(1, len(ordered) - 1))
        time = rec["time"]
        ratio = rec["TA"] / np.maximum(rec["TB"], 1e-30)
        mask = time > 1.0
        legend = f"{label}: φ={phi}, T₀={T0} (end={ratio[-1]:.2f})"
        ax.semilogx(time[mask], ratio[mask], "-", color=color, lw=1.2,
                     label=legend)

    ax.axhline(PRXAnalyzer.PAPER_RATIO, color="k", ls="--", lw=1.5,
                alpha=0.8, label=f"paper τ_∞ = {PRXAnalyzer.PAPER_RATIO}")
    ax.axhline(1.0, color="gray", ls=":", lw=1.0, alpha=0.5,
                label="initial ratio = 1")
    ax.set_xlabel("t (τ)", fontsize=12)
    ax.set_ylabel("T_A / T_B", fontsize=12)
    ax.set_title("Temperature ratio T_A/T_B vs t — all 9 runs (paper Fig 2 inset)",
                  fontsize=13)
    ax.legend(fontsize=8, loc="best", ncol=2)
    ax.grid(which="both", alpha=0.3)
    plt.tight_layout()
    out = DOC_IMG / "fig3_ratio_overlay.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def plot_stability_E1_vs_E2():
    """Stability test — same parameters, two run lengths (E1 vs E2)."""
    e1 = load_run("20260502_051425_E1v3")
    e2 = load_run("20260505_010133_E8")
    e1["tag"] = "E1"; e2["tag"] = "E2"

    fig, ax = plt.subplots(1, 2, figsize=(13, 5.3))

    for rec, color, lbl in ((e1, "C0", "E1"), (e2, "C3", "E2")):
        ax[0].loglog(rec["time"], rec["TA"], color=color, lw=1.5,
                      label=f"{lbl}: T_A (t_end={rec['time'][-1]:.0f}τ)")
        ax[0].loglog(rec["time"], rec["TB"], color=color, lw=1.0,
                      ls="--", label=f"{lbl}: T_B")
    t_ref = np.geomspace(10, e2["time"][-1], 60)
    ax[0].loglog(t_ref,
                  (t_ref / 10) ** PRXAnalyzer.PAPER_SLOPE * e1["TA"][50],
                  "k:", lw=1.6, alpha=0.7, label="t^(2/3) (paper)")
    ax[0].set_xlabel("t (τ)", fontsize=12)
    ax[0].set_ylabel("T*", fontsize=12)
    ax[0].set_title("E1 (20000 τ) vs E2 (50000 τ) — same physics", fontsize=13)
    ax[0].legend(fontsize=10); ax[0].grid(which="both", alpha=0.3)

    for rec, color, lbl in ((e1, "C0", "E1"), (e2, "C3", "E2")):
        tmins = np.geomspace(50, 0.7 * rec["time"][-1], 14)
        sAs = []
        for tm in tmins:
            rs = PRXAnalyzer.rolling_slopes(rec["time"], rec["TA"], rec["TB"],
                                              tmin_grid=[tm])
            sAs.append(rs[0]["slope_A"] if rs else float("nan"))
        ax[1].semilogx(tmins, sAs, "-o", color=color, lw=1.5, markersize=6,
                        label=lbl)
    ax[1].axhline(PRXAnalyzer.PAPER_SLOPE, color="k", ls="--", lw=1.5,
                   alpha=0.8, label="paper 2/3")
    ax[1].set_xlabel("tmin (τ)", fontsize=12)
    ax[1].set_ylabel("slope_A (rolling fit)", fontsize=12)
    ax[1].set_title("Asymptote stability across windows", fontsize=13)
    ax[1].set_ylim(0.4, 0.85)
    ax[1].legend(fontsize=11); ax[1].grid(alpha=0.3)
    plt.tight_layout()
    out = DOC_IMG / "fig4_stability_E1_vs_E2.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def plot_best_case_showcase():
    """Showcase plot for E2 (best long-time PASS): T_{A,B} vs t with rolling slope."""
    rec = load_run("20260505_010133_E8")
    rec["tag"] = "E2"
    rows = PRXAnalyzer.rolling_slopes(rec["time"], rec["TA"], rec["TB"])

    fig, axs = plt.subplots(1, 3, figsize=(16, 5.3))

    # Panel 1: T_A and T_B vs t
    last_A = rows[-1]["slope_A"]; last_B = rows[-1]["slope_B"]
    axs[0].loglog(rec["time"], rec["TA"], "C0-", lw=1.4,
                   label=f"T_A (slope_late={last_A:.4f})")
    axs[0].loglog(rec["time"], rec["TB"], "C1-", lw=1.4,
                   label=f"T_B (slope_late={last_B:.4f})")
    t_ref = np.geomspace(rec["time"][50], rec["time"][-1], 60)
    ref = (t_ref / t_ref[0]) ** PRXAnalyzer.PAPER_SLOPE * rec["TA"][50]
    axs[0].loglog(t_ref, ref, "k:", lw=1.6, alpha=0.7,
                   label="t^(2/3) paper")
    axs[0].set_xlabel("t (τ)", fontsize=12)
    axs[0].set_ylabel("T*", fontsize=12)
    axs[0].set_title("E2: T_A, T_B vs t at φ=0.3, T₀=0.3, 50000 τ",
                      fontsize=12)
    axs[0].legend(fontsize=10); axs[0].grid(which="both", alpha=0.3)

    # Panel 2: rolling slope sweep
    tmins = [r["tmin"] for r in rows]
    axs[1].semilogx(tmins, [r["slope_A"] for r in rows], "C0-o", lw=1.4,
                     markersize=6, label="slope_A")
    axs[1].semilogx(tmins, [r["slope_B"] for r in rows], "C1-s", lw=1.4,
                     markersize=6, label="slope_B")
    axs[1].axhline(PRXAnalyzer.PAPER_SLOPE, color="k", ls="--",
                    alpha=0.8, lw=1.5, label="paper 2/3")
    axs[1].set_xlabel("fit window start tmin (τ)", fontsize=12)
    axs[1].set_ylabel("d log T / d log t", fontsize=12)
    axs[1].set_title("E2: rolling slope — converges to 2/3", fontsize=12)
    axs[1].set_ylim(0, 0.85)
    axs[1].legend(fontsize=10); axs[1].grid(alpha=0.3)

    # Panel 3: T_A/T_B vs t
    ratio = rec["TA"] / np.maximum(rec["TB"], 1e-30)
    mask = rec["time"] > 1.0
    axs[2].semilogx(rec["time"][mask], ratio[mask], "C2-", lw=1.4,
                     label=f"T_A/T_B (final={ratio[-1]:.3f})")
    axs[2].axhline(PRXAnalyzer.PAPER_RATIO, color="k", ls="--",
                    alpha=0.8, lw=1.5,
                    label=f"paper τ_∞ = {PRXAnalyzer.PAPER_RATIO}")
    axs[2].set_xlabel("t (τ)", fontsize=12)
    axs[2].set_ylabel("T_A / T_B", fontsize=12)
    axs[2].set_title("E2: temperature ratio approach to τ_∞",
                      fontsize=12)
    axs[2].set_ylim(0.9, 3.5)
    axs[2].legend(fontsize=10); axs[2].grid(alpha=0.3)

    plt.tight_layout()
    out = DOC_IMG / "fig5_best_case_E2_showcase.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def plot_velocity_dist_E2():
    """E2 velocity distribution (paper Fig 1 lower panel reproduction)."""
    rec = load_run("20260505_010133_E8")
    rec["tag"] = "E2"
    # Use existing PRXPlotter velocity_distribution, copy to docs/images
    from toolClass import PRXPlotter
    out = DOC_IMG / "fig6_E2_velocity_dist.png"
    PRXPlotter.velocity_distribution(rec, 700.0, out)
    print(f"  → {out.name}")


def plot_engine_diagnostics():
    """Two-panel diagnostic plot: KE partition + |P| drift (smoking gun)."""
    rec = load_run("20260505_010133_E8")
    n_frames = rec["TA"].shape[0]
    diag_idx = np.linspace(0, n_frames - 1, 60, dtype=int)
    ke_A = np.zeros(len(diag_idx))
    ke_B = np.zeros(len(diag_idx))
    px = np.zeros(len(diag_idx))
    py = np.zeros(len(diag_idx))
    with h5py.File(rec["h5_path"], "r") as f:
        for i, idx in enumerate(diag_idx):
            v = f["vel"][idx]
            mA = rec["species"] == 1
            mB = rec["species"] == 2
            ke_A[i] = 0.5 * (v[mA, :2] ** 2).sum()
            ke_B[i] = 0.5 * (v[mB, :2] ** 2).sum()
            px[i] = v[:, 0].sum()
            py[i] = v[:, 1].sum()
    diag_t = rec["time"][diag_idx]

    fig, axs = plt.subplots(1, 2, figsize=(13, 5.3))
    # KE partition
    axs[0].loglog(diag_t[diag_t > 1], ke_A[diag_t > 1], "C0-o",
                   lw=1.4, markersize=4, label="KE_A (species A)")
    axs[0].loglog(diag_t[diag_t > 1], ke_B[diag_t > 1], "C1-s",
                   lw=1.4, markersize=4, label="KE_B (species B)")
    axs[0].loglog(diag_t[diag_t > 1], (ke_A + ke_B)[diag_t > 1],
                   "k--", lw=1.4, alpha=0.7, label="Total KE")
    axs[0].set_xlabel("t (τ)", fontsize=12)
    axs[0].set_ylabel("Kinetic Energy", fontsize=12)
    axs[0].set_title("E2: per-species KE — non-equipartition (paper signature)",
                      fontsize=12)
    axs[0].legend(fontsize=10); axs[0].grid(which="both", alpha=0.3)

    # Momentum drift
    p_total = np.sqrt(px ** 2 + py ** 2)
    axs[1].plot(diag_t, px, "C0-", lw=1.4, label=r"$P_x$")
    axs[1].plot(diag_t, py, "C1-", lw=1.4, label=r"$P_y$")
    axs[1].plot(diag_t, p_total, "k--", lw=1.5, alpha=0.7,
                 label=r"$|P_{\rm total}|$")
    axs[1].axhline(0, color="gray", ls=":", alpha=0.5)
    axs[1].set_xlabel("t (τ)", fontsize=12)
    axs[1].set_ylabel("Total momentum", fontsize=12)
    axs[1].set_title("E2: total momentum drift — Newton's 3rd law violation",
                      fontsize=12)
    axs[1].legend(fontsize=10); axs[1].grid(alpha=0.3)
    plt.tight_layout()
    out = DOC_IMG / "fig7_E2_engine_diagnostics.png"
    plt.savefig(out, dpi=160)
    plt.close(fig)
    print(f"  → {out.name}")


def write_mapping_table():
    """Write a mapping table linking thesis E# to folder + parameters."""
    table = ROOT / "docs" / "images" / "_mapping_table.md"
    lines = ["# Thesis E* ↔ folder ↔ parameters mapping", "",
             "Used by all figures in this directory.", "",
             "| Thesis ID | Folder (data) | Original tag | (φ, T₀) | τ_end | Role |",
             "| --- | --- | --- | --- | --- | --- |"]
    orig_tags = {
        "20260502_051425_E1v3":      "E1v3",
        "20260505_010133_E8":        "E8",
        "20260506_112106_phi01_T1":  "phi01_T1",
        "20260506_033731_phi03_T1":  "phi03_T1",
        "20260504_200903_E5":        "E5",
        "20260505_010133_E6":        "E6",
        "20260505_112813_E7":        "E7",
        "20260506_033731_phi03_T01": "phi03_T01",
        "20260506_101719_phi03_T10": "phi03_T10",
    }
    for label, folder, phi, T0, tau, role in THESIS_MAP:
        orig = orig_tags.get(folder, "?")
        lines.append(
            f"| **{label}** | `{folder}` | `{orig}` | "
            f"({phi}, {T0}) | {tau} τ | {role} |"
        )
    table.write_text("\n".join(lines), encoding="utf-8")
    print(f"  → {table.name}")


def main():
    print("[thesis-figures] Generating publication plots in docs/images/")
    write_mapping_table()
    plot_fig1_multiT0()
    plot_fig2_multi_phi()
    plot_ratio_overlay()
    plot_stability_E1_vs_E2()
    plot_best_case_showcase()
    plot_velocity_dist_E2()
    plot_engine_diagnostics()
    print("[thesis-figures] DONE")


if __name__ == "__main__":
    main()
