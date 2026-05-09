"""PRXPlotter — figure builders. Depends on PRXAnalyzer constants/methods.

Phase C split: extracted from toolClass.py:774-1131.
"""
import numpy as _np
import h5py as _h5py
import matplotlib as _mpl
import matplotlib.pyplot as _plt
from pathlib import Path as _Path
from tools.analyzers.prx import PRXAnalyzer

class PRXPlotter:
    """Plotting primitives for PRX 2015 reproduction.

    All methods accept matplotlib Axes (None to create new) and return the
    figure path (or None if drawing into existing axes). Save as PNG at 140
    DPI by default.
    """

    @staticmethod
    def _ensure_axes(ax, figsize=(13, 5.2)):
        if ax is not None:
            return None, ax
        fig, ax = _plt.subplots(1, 1, figsize=figsize)
        return fig, ax

    @staticmethod
    def slope_overlay(time, TA, TB, rows, save_path, title=""):
        """Twin panel: T_A/T_B vs t (left) + slope sweep vs window (right)."""

        fig, ax = _plt.subplots(1, 2, figsize=(13, 5.2))

        last_A = rows[-1]["slope_A"] if rows else float("nan")
        last_B = rows[-1]["slope_B"] if rows else float("nan")
        ax[0].loglog(time, TA, "C0-", lw=1.0,
                      label=f"T_A (slope_late={last_A:.3f})")
        ax[0].loglog(time, TB, "C1-", lw=1.0,
                      label=f"T_B (slope_late={last_B:.3f})")
        if len(time) > 100:
            idx = max(10, int(0.001 * len(time)))
            t_ref = _np.geomspace(time[idx], time[-1], 60)
            ref = (t_ref / t_ref[0]) ** PRXAnalyzer.PAPER_SLOPE * TA[idx]
            ax[0].loglog(t_ref, ref, "k:", lw=1.2, alpha=0.7,
                         label="paper t^(2/3)")
        ax[0].set_xlabel("t (τ)")
        ax[0].set_ylabel("T*")
        ax[0].set_title(title)
        ax[0].legend(loc="best", fontsize=9)
        ax[0].grid(which="both", alpha=0.3)

        if rows:
            tmins = [r["tmin"] for r in rows]
            ax[1].semilogx(tmins, [r["slope_A"] for r in rows],
                            "C0-o", label="slope_A")
            ax[1].semilogx(tmins, [r["slope_B"] for r in rows],
                            "C1-s", label="slope_B")
            ax[1].axhline(PRXAnalyzer.PAPER_SLOPE, color="k", ls="--",
                          alpha=0.7,
                          label=f"paper 2/3={PRXAnalyzer.PAPER_SLOPE:.3f}")
            ax[1].set_xlabel("fit window start tmin (τ)")
            ax[1].set_ylabel("slope = d log T / d log t")
            ax[1].set_title("Rolling slope sweep — does run cross 2/3?")
            ax[1].set_ylim(0, 0.85)
            ax[1].legend(loc="best", fontsize=9)
            ax[1].grid(alpha=0.3)

        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path

    @staticmethod
    def ratio_vs_time(rec, save_path, title=""):
        """Per-run T_A/T_B vs log(t) — paper Fig 2 inset analog.

        Shows asymmetry development over time, with paper τ_∞=3.1
        dashed reference. The latest-window mean ratio is annotated.
        """

        time = rec["time"]
        TA = rec["TA"]
        TB = rec["TB"]
        ratio = TA / _np.maximum(TB, 1e-30)

        fig, ax = _plt.subplots(1, 1, figsize=(9, 5))
        mask = time > 1.0
        ax.semilogx(time[mask], ratio[mask], "C0-", lw=1.0,
                     label=f"T_A / T_B  (final={ratio[-1]:.3f})")
        ax.axhline(PRXAnalyzer.PAPER_RATIO, color="k", ls="--",
                    alpha=0.7,
                    label=f"paper τ_∞ = {PRXAnalyzer.PAPER_RATIO}")
        ax.axhline(1.0, color="gray", ls=":", alpha=0.5, label="ratio = 1")
        ax.set_xlabel("t (τ, log)")
        ax.set_ylabel("T_A / T_B")
        ax.set_title(title or "Temperature ratio T_A/T_B over time")
        ax.legend(loc="best")
        ax.grid(which="both", alpha=0.3)
        # y range: from just below 1 to ~1.2× paper ratio
        max_ratio = max(float(ratio.max()), PRXAnalyzer.PAPER_RATIO)
        ax.set_ylim(0.5, max_ratio * 1.15)
        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path

    @staticmethod
    def multi_run_ratio(records, save_path, title=""):
        """Multi-run T_A/T_B vs log(t) — paper Fig 2 inset, all runs overlaid.

        Useful for comparing how φ and T₀ affect ratio convergence speed.
        """

        fig, ax = _plt.subplots(1, 1, figsize=(11, 5.5))
        cmap = _plt.get_cmap("viridis")
        for i, rec in enumerate(records):
            m = rec["manifest"]
            phi = m.get("phi_target", float("nan"))
            T0 = m.get("T0_star", float("nan"))
            color = cmap(i / max(1, len(records) - 1))
            time = rec["time"]
            mask = time > 1.0
            ratio = rec["TA"] / _np.maximum(rec["TB"], 1e-30)
            label = (f"{rec.get('tag', '?')} "
                     f"φ={phi:.2f} T₀={T0:.2f} "
                     f"(end={ratio[-1]:.2f})")
            ax.semilogx(time[mask], ratio[mask], "-", color=color,
                        lw=1.0, label=label)

        ax.axhline(PRXAnalyzer.PAPER_RATIO, color="k", ls="--",
                    alpha=0.7,
                    label=f"paper τ_∞ = {PRXAnalyzer.PAPER_RATIO}")
        ax.axhline(1.0, color="gray", ls=":", alpha=0.5, label="ratio = 1")
        ax.set_xlabel("t (τ, log)")
        ax.set_ylabel("T_A / T_B")
        ax.set_title(title or "Temperature ratio overlay (paper Fig 2 inset)")
        ax.legend(loc="best", fontsize=8)
        ax.grid(which="both", alpha=0.3)
        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path

    @staticmethod
    def fig1_multi_T0(records, save_path):
        """Paper Fig 1 — T_A and T_B vs t for several T₀ at fixed φ."""

        fig, axs = _plt.subplots(1, 2, figsize=(13, 5.5))
        cmap = _plt.get_cmap("plasma")

        for i, rec in enumerate(records):
            color = cmap(i / max(1, len(records) - 1))
            label = (f"T₀={rec['manifest'].get('T0_star', '?')} "
                     f"({rec.get('tag', rec['manifest'].get('tag', '?'))})")
            mask = rec["time"] > 1.0
            axs[0].loglog(rec["time"][mask], rec["TA"][mask], "-",
                          color=color, label=f"T_A {label}")
            axs[1].loglog(rec["time"][mask], rec["TB"][mask], "-",
                          color=color, label=f"T_B {label}")

        if records:
            t = records[0]["time"]
            mask = t > 1.0
            t_ref = t[mask]
            ref = ((t_ref / t_ref[0]) ** PRXAnalyzer.PAPER_SLOPE
                   * records[0]["TA"][mask][0])
            axs[0].loglog(t_ref, ref, "k:", alpha=0.5,
                          label="paper t^(2/3)")
            axs[1].loglog(t_ref, ref, "k:", alpha=0.5,
                          label="paper t^(2/3)")

        for ax, sp in zip(axs, ("T_A", "T_B")):
            ax.set_xlabel("t (τ, log)")
            ax.set_ylabel(f"{sp} (log)")
            ax.set_title(f"{sp} vs t — multi-T₀")
            ax.legend(fontsize=8)
            ax.grid(which="both", alpha=0.3)

        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path

    @staticmethod
    def fig2_multi_phi(records, save_path):
        """Paper Fig 2 — T_A+T_B vs t for several φ at fixed T₀, plus
        n^(2/3) collapse inset."""

        fig, axs = _plt.subplots(1, 2, figsize=(14, 5.5))
        cmap = _plt.get_cmap("viridis")

        for i, rec in enumerate(records):
            phi = rec["manifest"].get("phi_target", float("nan"))
            color = cmap(i / max(1, len(records) - 1))
            label = (f"φ={phi:.2f} "
                     f"({rec.get('tag', rec['manifest'].get('tag', '?'))})")
            t = rec["time"]
            T_sum = rec["TA"] + rec["TB"]
            mask = t > 1.0
            axs[0].loglog(t[mask], T_sum[mask], "-", color=color, label=label)

            # n^(2/3) collapse: scale T_A by phi^(2/3) (n ∝ φ in reduced units)
            n = phi / _np.pi  # area density in r0^-2
            axs[1].loglog(t[mask],
                          rec["TA"][mask] * n ** (2.0 / 3.0),
                          "-", color=color, label=label)

        if records:
            t = records[0]["time"]
            mask = t > 1.0
            t_ref = t[mask]
            T_sum0 = records[0]["TA"][mask][0] + records[0]["TB"][mask][0]
            ref = (t_ref / t_ref[0]) ** PRXAnalyzer.PAPER_SLOPE * T_sum0
            axs[0].loglog(t_ref, ref, "k:", alpha=0.5,
                          label="paper t^(2/3)")

        axs[0].set_xlabel("t (τ, log)")
        axs[0].set_ylabel("T_A + T_B (log)")
        axs[0].set_title("Fig 2 — multi-φ at fixed T₀")
        axs[0].legend(fontsize=8); axs[0].grid(which="both", alpha=0.3)

        axs[1].set_xlabel("t (τ, log)")
        axs[1].set_ylabel("T_A · n^(2/3) (log)")
        axs[1].set_title("n^(2/3) collapse — paper Eq. 9")
        axs[1].legend(fontsize=8); axs[1].grid(which="both", alpha=0.3)

        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path

    @staticmethod
    def stability(record_short, record_long, save_path):
        """E1v3 vs E8 style — same params, different t_end. Tests whether
        slope stays at 2/3 across the longer time window."""

        fig, ax = _plt.subplots(1, 2, figsize=(14, 5.2))
        for rec, color, lbl in (
                (record_short, "C0", "short"),
                (record_long,  "C3", "long"),
        ):
            tag = rec.get("tag", rec["manifest"].get("tag", lbl))
            ax[0].loglog(rec["time"], rec["TA"], color=color, lw=1.0,
                          label=f"{tag} T_A (t_end={rec['time'][-1]:.0f}τ)")
            ax[0].loglog(rec["time"], rec["TB"], color=color, lw=0.8,
                          ls="--", label=f"{tag} T_B")
        t_max = max(record_short["time"][-1], record_long["time"][-1])
        t_ref = _np.geomspace(10, t_max, 60)
        # Reference amplitude: pick a frame ~1% into the short run, but
        # safely within bounds for any input length (smoke runs may have
        # very few frames).
        ref_idx = min(max(10, len(record_short["TA"]) // 100),
                       len(record_short["TA"]) - 1)
        ax[0].loglog(t_ref,
                     (t_ref / 10) ** PRXAnalyzer.PAPER_SLOPE
                     * record_short["TA"][ref_idx],
                     "k:", lw=1.2, alpha=0.7, label="paper t^(2/3)")
        ax[0].set_xlabel("t (τ)"); ax[0].set_ylabel("T*")
        ax[0].set_title("Stability: short vs long at same params")
        ax[0].legend(fontsize=8); ax[0].grid(which="both", alpha=0.3)

        for rec, color in ((record_short, "C0"), (record_long, "C3")):
            tag = rec.get("tag", rec["manifest"].get("tag", ""))
            tmins = _np.geomspace(50, 0.7 * rec["time"][-1], 12)
            sAs = []
            for tm in tmins:
                rs = PRXAnalyzer.rolling_slopes(rec["time"], rec["TA"],
                                                  rec["TB"], tmin_grid=[tm])
                sAs.append(rs[0]["slope_A"] if rs else float("nan"))
            ax[1].semilogx(tmins, sAs, "-o", color=color, label=tag)
        ax[1].axhline(PRXAnalyzer.PAPER_SLOPE, color="k", ls="--", alpha=0.7,
                      label="2/3")
        ax[1].set_xlabel("tmin (τ)"); ax[1].set_ylabel("slope_A")
        ax[1].set_title("Does slope stay at 2/3 across long windows?")
        ax[1].set_ylim(0.4, 0.85)
        ax[1].legend(); ax[1].grid(alpha=0.3)
        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path

    @staticmethod
    def velocity_distribution(rec, t_target, save_path, bins=40):
        """Paper PRX 2015 Fig 1 lower-panel reproduction.

        Two-panel side-by-side comparison:
          Left  — f(|v|) histogram for species A and B overlaid, with
                  2D Maxwell-Boltzmann fit curves drawn as solid lines.
                  Direct comparison: do A and B both look Maxwellian?
          Right — log10[f(|v|) / |v|] vs |v|^2.  The 2D MB distribution
                  f(v) = (m/T)·v·exp(-mv^2/(2T)) becomes a STRAIGHT LINE
                  in this representation, slope = -m/(2T)·log10(e).
                  Deviation from the line = non-Maxwellian behaviour.
                  This is exactly the diagnostic the paper uses (Fig 1
                  lower-right inset) to visually flag the A-species
                  high-|v| tail that fails to thermalize.
        """

        # Load vel for the closest-to-t_target frame from HDF5.
        with _h5py.File(rec["h5_path"], "r") as f:
            time = f["time"][:]
            idx = int(_np.argmin(_np.abs(time - t_target)))
            vel = f["vel"][idx]
            species = f["species"][:]

        speed = _np.linalg.norm(vel[:, :2], axis=1)
        mA = species == 1
        mB = species == 2
        spA = speed[mA]
        spB = speed[mB]

        # 2D MB effective T: <v^2> = 2T/m, m=1 in reduced units
        T_A = float((spA ** 2).mean() / 2)
        T_B = float((spB ** 2).mean() / 2)

        fig, axs = _plt.subplots(1, 2, figsize=(13, 5.2))

        # ---- Left panel: combined f(|v|) histogram with MB fits ----
        v_max = float(max(spA.max(), spB.max())) * 1.1
        v_grid = _np.linspace(0, v_max, 400)
        mb_A = (1.0 / T_A) * v_grid * _np.exp(-(v_grid ** 2) / (2 * T_A))
        mb_B = (1.0 / T_B) * v_grid * _np.exp(-(v_grid ** 2) / (2 * T_B))
        common_bins = _np.linspace(0, v_max, bins + 1)
        axs[0].hist(spA, bins=common_bins, density=True, alpha=0.45,
                    color="C0", label=f"sim A (T={T_A:.3f})")
        axs[0].hist(spB, bins=common_bins, density=True, alpha=0.45,
                    color="C1", label=f"sim B (T={T_B:.3f})")
        axs[0].plot(v_grid, mb_A, "C0-", lw=1.5,
                    label=f"MB A fit T={T_A:.3f}")
        axs[0].plot(v_grid, mb_B, "C1-", lw=1.5,
                    label=f"MB B fit T={T_B:.3f}")
        axs[0].set_xlabel("|v|")
        axs[0].set_ylabel("f(|v|)")
        axs[0].set_title(f"f(|v|) at t={time[idx]:.1f} τ — A and B compared")
        axs[0].legend(fontsize=9, loc="upper right")
        axs[0].grid(alpha=0.3)

        # ---- Right panel: linearized log10[f(v)/v] vs v^2 (paper Fig 1) ----
        # Compute density-normalized histogram for f(v); convert to f/v;
        # take log10. Plot vs bin-center squared.
        for sp, color, lbl, T_eff in (
                (spA, "C0", "A", T_A),
                (spB, "C1", "B", T_B),
        ):
            counts, edges = _np.histogram(sp, bins=common_bins, density=True)
            centers = 0.5 * (edges[:-1] + edges[1:])
            # f(v)/v with safe log
            fov = counts / _np.maximum(centers, 1e-30)
            mask = (counts > 0) & (centers > 1e-3)
            x = centers[mask] ** 2
            y = _np.log10(fov[mask])
            axs[1].plot(x, y, "o", color=color, markersize=4, alpha=0.7,
                         label=f"sim {lbl}")
            # Theoretical straight line: log10[f/v] = log10(1/T) - v^2/(2T) * log10(e)
            x_line = _np.linspace(0, x.max() if len(x) else 1.0, 100)
            y_line = _np.log10(1.0 / T_eff) - x_line / (2 * T_eff) * _np.log10(_np.e)
            axs[1].plot(x_line, y_line, "-", color=color, lw=1.5,
                         alpha=0.6, label=f"MB line T={T_eff:.3f}")
        axs[1].set_xlabel(r"$|v|^2$")
        axs[1].set_ylabel(r"$\log_{10}\,[f(|v|)/|v|]$")
        axs[1].set_title("Linearized MB diagnostic (paper Fig 1 lower right)")
        axs[1].legend(fontsize=9, loc="best")
        axs[1].grid(alpha=0.3)

        _plt.tight_layout()
        _plt.savefig(save_path, dpi=140)
        _plt.close(fig)
        return save_path



