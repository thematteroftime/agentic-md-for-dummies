"""PRXAggregator — cross-run aggregation for PRX 2015 campaigns.

Implements the aggregator contract from docs/ARCHITECTURE.md §3.5:
  static aggregate(run_dirs, output, plots, title, **params) -> None

Other papers add their own aggregator classes (e.g. ERAggregator) and
select via:

    "aggregation": {"enabled": true, "class": "PRXAggregator", "plots": [...]}
"""
from __future__ import annotations
import datetime as _dt
from collections import defaultdict
from pathlib import Path

def _lazy_imports():
    """Defer PRXAnalyzer/PRXPlotter import until aggregate() runs.
    Importing them eagerly triggers Taichi CUDA init (~3 s) at every
    `tools.registry.resolve('PRXAggregator')`, which is wasteful for
    aggregator-only use (no kernels needed)."""
    from tools.analyzers.prx import PRXAnalyzer  # noqa: F401
    from tools.plotters.prx import PRXPlotter    # noqa: F401
    return PRXAnalyzer, PRXPlotter


class PRXAggregator:
    """Cross-run aggregator for PRX 2015 NVE / damping campaigns."""

    KNOWN_PLOTS = ("fig1", "fig2", "ratio", "stability")

    @staticmethod
    def aggregate(run_dirs, output: str | Path, plots: list[str],
                   title: str, max_stability_pairs: int = 4,
                   **params) -> None:
        """REQUIRED contract method (§3.5).

        run_dirs: paths to individual run directories
        output:   path to master report .md to write
        plots:    list of plot short names (e.g. ["fig1", "fig2", "stability"])
        title:    master report title
        max_stability_pairs: cap on # stability plots (avoids quadratic blow-up
                             when many runs share (φ, T₀) — each pair becomes a fig)
        params:   forwarded from pipeline.aggregation extra fields
        """
        PRXAnalyzer, PRXPlotter = _lazy_imports()
        if not run_dirs:
            print("[aggregate/PRX] no run dirs — skip")
            return
        invalid = [p for p in plots if p not in PRXAggregator.KNOWN_PLOTS]
        if invalid:
            print(f"[aggregate/PRX] unknown plot keys {invalid}; "
                   f"valid: {PRXAggregator.KNOWN_PLOTS}")
        # Figures land alongside the master report.
        out_root = Path(output).resolve().parent
        out_root.mkdir(parents=True, exist_ok=True)
        records = []
        for rp in run_dirs:
            if str(rp).endswith("_smoke") or "_smoke" in str(rp):
                print(f"[aggregate/PRX] skip smoke: {rp}")
                continue
            try:
                rec = PRXAnalyzer.load_run(rp)
                rec["tag"] = rec["manifest"].get("tag", Path(rp).name)
                if len(rec["time"]) < 100:
                    print(f"[aggregate/PRX] skip {rec['tag']}: only "
                          f"{len(rec['time'])} frames")
                    continue
                records.append(rec)
            except Exception as e:
                print(f"[aggregate/PRX] skip {rp}: {e}")
        if not records:
            print("[aggregate/PRX] no loadable records")
            return

        plot_dir = out_root
        plot_dir.mkdir(parents=True, exist_ok=True)
        plot_paths = {}

        if "fig1" in plots:
            by_phi = defaultdict(list)
            for r in records:
                by_phi[r["manifest"].get("phi_target")].append(r)
            target_phi, recs = max(by_phi.items(), key=lambda kv: len(kv[1]))
            recs.sort(key=lambda r: r["manifest"].get("T0_star", 0))
            out_png = plot_dir / "campaign_fig1_multi_T0.png"
            PRXPlotter.fig1_multi_T0(recs, out_png)
            plot_paths[f"Fig 1 (multi-T₀, φ={target_phi})"] = out_png
            print(f"  → {out_png.name}")

        if "fig2" in plots:
            by_T0 = defaultdict(list)
            for r in records:
                by_T0[r["manifest"].get("T0_star")].append(r)
            target_T0, recs = max(by_T0.items(), key=lambda kv: len(kv[1]))
            recs.sort(key=lambda r: r["manifest"].get("phi_target", 0))
            out_png = plot_dir / "campaign_fig2_multi_phi.png"
            PRXPlotter.fig2_multi_phi(recs, out_png)
            plot_paths[f"Fig 2 (multi-φ + n^(2/3), T₀={target_T0})"] = out_png
            print(f"  → {out_png.name}")

        if "ratio" in plots:
            try:
                ratio_png = plot_dir / "campaign_ratio_overlay.png"
                ratio_recs = sorted(records,
                                    key=lambda r: (r["manifest"].get("phi_target", 0),
                                                    r["manifest"].get("T0_star", 0)))
                PRXPlotter.multi_run_ratio(
                    ratio_recs, ratio_png,
                    title="T_A/T_B vs t — all runs (paper Fig 2 inset)")
                plot_paths["Temperature ratio T_A/T_B vs t (all runs)"] = ratio_png
                print(f"  → {ratio_png.name}")
            except Exception as e:
                print(f"  ratio overlay skipped: {e}")

        if "stability" in plots:
            pairs = []
            for i, ri in enumerate(records):
                for rj in records[i+1:]:
                    if (abs(ri["manifest"].get("phi_target", -1)
                            - rj["manifest"].get("phi_target", -2)) < 1e-6
                        and abs(ri["manifest"].get("T0_star", -1)
                                - rj["manifest"].get("T0_star", -2)) < 1e-6):
                        short, long_ = ((ri, rj) if ri["time"][-1] < rj["time"][-1]
                                        else (rj, ri))
                        pairs.append((short, long_))
            if len(pairs) > max_stability_pairs:
                print(f"[aggregate/PRX] {len(pairs)} stability pairs found; "
                      f"capping at {max_stability_pairs} (override via "
                      f"aggregation.params.max_stability_pairs)")
                pairs = pairs[:max_stability_pairs]
            for k, (short, long_) in enumerate(pairs):
                out_png = plot_dir / f"campaign_stability_{k+1}.png"
                PRXPlotter.stability(short, long_, out_png)
                plot_paths[f"Stability {short['tag']} vs {long_['tag']}"] = out_png
                print(f"  → {out_png.name}")

        PRXAggregator._write_master_report(records, plot_paths, output, title)

    @staticmethod
    def _write_master_report(records, plot_paths, output, title):
        PRXAnalyzer, PRXPlotter = _lazy_imports()
        md = [f"# {title}", ""]
        md.append(f"_Generated {_dt.datetime.now().isoformat(timespec='seconds')}_  "
                  f"_From {len(records)} runs._")
        md.append("")
        md.append("## Per-run summary")
        md.append("")
        md.append("| Tag | φ | T₀ | τ_end | tmin | slope_A | err_A | T_A/T_B | err_R | Verdict | Wall (hr) |")
        md.append("| --- | -- | -- | ----- | ---- | ------- | ----- | ------- | ----- | ------- | --------- |")
        for r in records:
            m = r["manifest"]
            rows = PRXAnalyzer.rolling_slopes(r["time"], r["TA"], r["TB"])
            if not rows:
                continue
            last = rows[-1]
            v = PRXAnalyzer.paper_verdict(
                last["slope_A"], last["slope_B"], last["ratio"],
                ke_growing=r["TA"][-1] > r["TA"][0])
            wall = m.get("wall_seconds", 0) / 3600.0
            verdict = ("PASS" if v["all_pass"]
                       else "PARTIAL" if v["slope_A_verdict"] == "PASS"
                       else "FAIL")
            md.append(
                f"| {r['tag']} | {m.get('phi_target', '?'):.2f} "
                f"| {m.get('T0_star', '?'):.2f} | {r['time'][-1]:.0f} "
                f"| {last['tmin']} | {last['slope_A']:.4f} "
                f"| {v['slope_A_err']*100:.2f}% | {last['ratio']:.3f} "
                f"| {v['ratio_err']*100:.2f}% | {verdict} | {wall:.2f} |")
        md.append("")
        md.append("## Paper PRX 2015 anchors")
        md.append("")
        md.append(f"- slope_A = slope_B = 2/3 = {PRXAnalyzer.PAPER_SLOPE:.4f}")
        md.append(f"- T_A/T_B → τ_∞ = {PRXAnalyzer.PAPER_RATIO}")
        md.append("- n^(2/3) collapse: T·n^(2/3) universal in t at long time")
        md.append("- Δ_eff = 0.57, ϵ = 0.082 (analytical)")
        md.append(f"- Tolerance for PASS: {PRXAnalyzer.TOLERANCE*100:.0f}%")
        md.append("")
        if plot_paths:
            md.append("## Plots")
            md.append("")
            for label, path in plot_paths.items():
                md.append(f"### {label}")
                md.append(f"![{label}]({Path(path).name})")
                md.append("")
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(md), encoding="utf-8")
        print(f"[aggregate/PRX] wrote {out}")
