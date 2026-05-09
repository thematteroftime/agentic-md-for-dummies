#!/usr/bin/env python3
"""Extension analyses — compute structural/dynamical observables from
existing run dirs that go BEYOND the paper's main figures.

Adds three new diagnostics:
  1. Pair correlation g_AA(r), g_BB(r), g_AB(r) — spatial structure
  2. Per-species kinetic-energy partition over time — non-equipartition
  3. Total momentum and total KE drift — sanity check on integrator

Run:
    python scripts/extension_analysis.py outputFiles/<TS>_<tag>
"""
import os
import sys
import json
from pathlib import Path

import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent


def pair_correlation(positions, species, box_size, r_max=8.0, n_bins=120):
    """g_AB(r) for a 2D PBC box, single frame.

    Returns dict with keys 'r', 'g_AA', 'g_BB', 'g_AB'.
    """
    pos2d = positions[:, :2]
    Lx = box_size[0]
    Ly = box_size[1]

    mA = species == 1
    mB = species == 2
    pA = pos2d[mA]
    pB = pos2d[mB]
    nA = len(pA)
    nB = len(pB)
    n_total = nA + nB
    area = Lx * Ly

    bin_edges = np.linspace(0, r_max, n_bins + 1)
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])
    bin_areas = np.pi * (bin_edges[1:] ** 2 - bin_edges[:-1] ** 2)

    def mic_distances(P, Q):
        # Minimum image convention pairwise distances, P x Q
        # For memory, do batched
        d = P[:, None, :] - Q[None, :, :]
        d[..., 0] -= Lx * np.round(d[..., 0] / Lx)
        d[..., 1] -= Ly * np.round(d[..., 1] / Ly)
        return np.linalg.norm(d, axis=-1)

    # AA self-pairs (exclude self): use upper-triangular distances
    if nA > 1:
        dAA = mic_distances(pA, pA)
        dAA = dAA[np.triu_indices(nA, k=1)]
        hist_AA, _ = np.histogram(dAA, bins=bin_edges)
        # Normalise: rho_A = nA/area, expected pairs in shell = rho_A * area_shell
        rho_A = nA / area
        norm_AA = rho_A * bin_areas * (nA / 2.0)  # 2 because we counted only upper tri
        g_AA = hist_AA / np.maximum(norm_AA, 1)
    else:
        g_AA = np.zeros(n_bins)

    if nB > 1:
        dBB = mic_distances(pB, pB)
        dBB = dBB[np.triu_indices(nB, k=1)]
        hist_BB, _ = np.histogram(dBB, bins=bin_edges)
        rho_B = nB / area
        norm_BB = rho_B * bin_areas * (nB / 2.0)
        g_BB = hist_BB / np.maximum(norm_BB, 1)
    else:
        g_BB = np.zeros(n_bins)

    dAB = mic_distances(pA, pB)
    hist_AB, _ = np.histogram(dAB.ravel(), bins=bin_edges)
    # AB normalisation: rho_B from A's perspective
    rho_B = nB / area
    norm_AB = rho_B * bin_areas * nA
    g_AB = hist_AB / np.maximum(norm_AB, 1)

    return {
        "r": bin_centers,
        "g_AA": g_AA,
        "g_BB": g_BB,
        "g_AB": g_AB,
    }


def main(run_dir):
    run_dir = Path(run_dir)
    h5s = sorted(run_dir.glob("*.h5"), key=lambda p: p.stat().st_size)
    h5_path = h5s[-1]
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    tag = manifest.get("tag", run_dir.name)

    with h5py.File(h5_path, "r") as f:
        species = f["species"][:]
        time = f["time"][:]
        T_all = f["T"][:]
        box = f["box"][:]
        # Pick three time points: early, mid, late
        n_frames = T_all.shape[0]
        idx_early = int(n_frames * 0.05)
        idx_mid = int(n_frames * 0.50)
        idx_late = int(n_frames * 0.95)

        # g(r) at three time snapshots
        gr_results = {}
        for label, idx in [("early", idx_early), ("mid", idx_mid), ("late", idx_late)]:
            pos = f["pos"][idx]
            gr_results[label] = pair_correlation(pos, species, [box[0,0], box[1,1]],
                                                  r_max=6.0, n_bins=100)
            gr_results[label]["t"] = float(time[idx])

        # Read vel at all sampled frames (for KE and momentum diagnostics)
        # That's 8333 frames × 20000 × 3 × 8 bytes = ~4 GB. Too big to load all.
        # Instead just sample 50 evenly-spaced frames for diagnostics.
        diag_indices = np.linspace(0, n_frames - 1, 50, dtype=int)
        ke_A = np.zeros(len(diag_indices))
        ke_B = np.zeros(len(diag_indices))
        px = np.zeros(len(diag_indices))
        py = np.zeros(len(diag_indices))
        for i, idx in enumerate(diag_indices):
            v = f["vel"][idx]  # (n_atoms, 3)
            mA = species == 1
            mB = species == 2
            # m=1 reduced units
            ke_A[i] = 0.5 * (v[mA, :2] ** 2).sum()
            ke_B[i] = 0.5 * (v[mB, :2] ** 2).sum()
            px[i] = v[:, 0].sum()
            py[i] = v[:, 1].sum()
        diag_t = time[diag_indices]

    # Figure 1: g(r) at three time snapshots
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.8))
    for ax, label in zip(axs, ["early", "mid", "late"]):
        gr = gr_results[label]
        ax.plot(gr["r"], gr["g_AA"], "C0-", label="g_AA(r)", lw=1.5)
        ax.plot(gr["r"], gr["g_BB"], "C1-", label="g_BB(r)", lw=1.5)
        ax.plot(gr["r"], gr["g_AB"], "C2-", label="g_AB(r)", lw=1.5)
        ax.axhline(1.0, color="gray", ls=":", alpha=0.5, label="ideal gas")
        ax.axvline(1.0, color="black", ls=":", alpha=0.3, label="r₀ contact")
        ax.set_xlabel("r")
        ax.set_ylabel("g(r)")
        ax.set_title(f"{label}-time, t={gr['t']:.0f} τ")
        ax.legend(fontsize=8, loc="upper right")
        ax.grid(alpha=0.3)
        ax.set_xlim(0, 6)
    plt.tight_layout()
    pair_png = run_dir / "extension_pair_correlation.png"
    plt.savefig(pair_png, dpi=140)
    plt.close(fig)
    print(f"  → {pair_png.name}")

    # Figure 2: per-species KE vs time + total momentum drift
    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8))
    axs[0].loglog(diag_t[diag_t > 1], ke_A[diag_t > 1], "C0-o", lw=1.0,
                   markersize=3, label="KE_A (sum over species A)")
    axs[0].loglog(diag_t[diag_t > 1], ke_B[diag_t > 1], "C1-s", lw=1.0,
                   markersize=3, label="KE_B (sum over species B)")
    axs[0].loglog(diag_t[diag_t > 1], (ke_A + ke_B)[diag_t > 1], "k--",
                   alpha=0.6, label="total KE")
    axs[0].set_xlabel("t (τ)")
    axs[0].set_ylabel("KE")
    axs[0].set_title(f"{tag}: per-species kinetic energy")
    axs[0].legend(fontsize=9)
    axs[0].grid(which="both", alpha=0.3)

    # Total momentum drift: should be ~zero (NVE integrator + initial COM = 0)
    # but non-reciprocal force doesn't conserve p! So drift is EXPECTED.
    p_total = np.sqrt(px ** 2 + py ** 2)
    axs[1].plot(diag_t, px, "C0-", lw=1.0, label="P_x")
    axs[1].plot(diag_t, py, "C1-", lw=1.0, label="P_y")
    axs[1].plot(diag_t, p_total, "k--", lw=1.0, alpha=0.6,
                 label="|P| total")
    axs[1].axhline(0, color="gray", ls=":", alpha=0.5)
    axs[1].set_xlabel("t (τ)")
    axs[1].set_ylabel("P (per particle units)")
    axs[1].set_title(f"{tag}: total momentum drift (non-reciprocal NOT conserved)")
    axs[1].legend(fontsize=9)
    axs[1].grid(alpha=0.3)
    plt.tight_layout()
    energy_png = run_dir / "extension_energy_momentum.png"
    plt.savefig(energy_png, dpi=140)
    plt.close(fig)
    print(f"  → {energy_png.name}")

    # Save numerical summary
    summary = {
        "tag": tag,
        "g_late_AA_first_peak": float(gr_results["late"]["g_AA"][
            np.argmax(gr_results["late"]["g_AA"][5:50]) + 5]),
        "g_late_BB_first_peak": float(gr_results["late"]["g_BB"][
            np.argmax(gr_results["late"]["g_BB"][5:50]) + 5]),
        "g_late_AB_first_peak": float(gr_results["late"]["g_AB"][
            np.argmax(gr_results["late"]["g_AB"][5:50]) + 5]),
        "ke_A_initial": float(ke_A[0]),
        "ke_A_final":   float(ke_A[-1]),
        "ke_B_initial": float(ke_B[0]),
        "ke_B_final":   float(ke_B[-1]),
        "ke_ratio_late": float(ke_A[-1] / max(ke_B[-1], 1e-30)),
        "P_total_max":  float(np.max(p_total)),
        "P_total_final": float(p_total[-1]),
    }
    summary_path = run_dir / "extension_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"  → {summary_path.name}")
    print(f"  KE_A/KE_B (late) = {summary['ke_ratio_late']:.3f}  (paper τ_∞ = 3.1)")
    print(f"  |P_total| max    = {summary['P_total_max']:.3e}  (drift signature of non-reciprocity)")
    return summary


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: extension_analysis.py <run_dir>")
        sys.exit(1)
    main(sys.argv[1])
