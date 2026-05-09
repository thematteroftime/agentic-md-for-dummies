"""ERAggregator — cross-run aggregation for PRL 2008 ER plasma campaigns.

Implements the aggregator contract from docs/ARCHITECTURE.md §3.5.
Wraps `scripts/analyze_er.py` task functions (chain / long / length) as
class methods so config-driven dispatch works:

    "aggregation": {
      "enabled": true, "class": "ERAggregator",
      "plots": ["chain", "long", "length"]
    }

Outputs go to docs/images/fig11-17 + docs/PRL2008_*.md (paths fixed by
the underlying analyze_er.py functions; matches §1 layered architecture
where ER plotting is a paper-specific package).
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))


class ERAggregator:
    """Cross-run aggregator for PRL 2008 ER plasma."""

    KNOWN_PLOTS = ("chain", "long", "length", "all")

    @staticmethod
    def aggregate(run_dirs, output: str | Path, plots: list[str],
                   title: str, **params) -> None:
        """REQUIRED contract method (§3.5).

        ⚠ CONTRACT NOTE — `run_dirs` is IGNORED by this aggregator.
        ER plasma analysis pulls from hardcoded SHORT_RUNS / LONG_RUNS lists
        in scripts/analyze_er.py because per-paper-Plan campaigns (G / G2 / G3)
        define the cross-run scope, not the platform's `completed` list.
        New ER campaigns extend SHORT_RUNS / LONG_RUNS in scripts/analyze_er.py.

        plots: subset of {"chain", "long", "length"}; "all" runs the trio.
        """
        from analyze_er import task_chain, task_long, task_length

        if run_dirs:
            print(f"[aggregate/ER] WARNING: {len(run_dirs)} run_dirs passed "
                   f"but ER aggregator ignores them (uses hardcoded lists in "
                   f"scripts/analyze_er.py:SHORT_RUNS/LONG_RUNS). To extend, "
                   f"edit those constants directly.")

        invalid = [p for p in plots if p not in ERAggregator.KNOWN_PLOTS]
        if invalid:
            print(f"[aggregate/ER] unknown plot keys {invalid}; "
                  f"valid: {ERAggregator.KNOWN_PLOTS}")

        if "chain" in plots or "all" in plots:
            print("[aggregate/ER] running 'chain' (Plan G short snapshot, fig11-13)...")
            task_chain()
        if "long" in plots or "all" in plots:
            print("[aggregate/ER] running 'long' (Plan G2/G3 long-time, fig14-16)...")
            task_long()
        if "length" in plots or "all" in plots:
            print("[aggregate/ER] running 'length' (chain length stats, fig17)...")
            task_length()

        ERAggregator._write_master_summary(output, title, plots)

    @staticmethod
    def _write_master_summary(output, title, plots):
        """Stitch existing PRL2008_*.md outputs into a master report."""
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"# {title}", ""]
        lines.append(f"_ERAggregator output for plots={plots}_")
        lines.append("")
        lines.append("## Sub-reports")
        lines.append("")
        for sub in ("PRL2008_extended_results.md", "PRL2008_chain_length.md"):
            sp = ROOT / "docs" / sub
            if sp.exists():
                lines.append(f"- [{sub}](./{sub})")
        lines.append("")
        lines.append("## Figures")
        lines.append("")
        for f in ("fig11_er_chain_phase_transition.png",
                  "fig12_er_chain_3d_snapshots.png",
                  "fig13_er_chain_order_parameter.png",
                  "fig14_er_long_Q_evolution.png",
                  "fig15_er_long_g_at_chain_peak.png",
                  "fig16_er_phase_transition.png",
                  "fig17_er_chain_length_dist.png"):
            fp = ROOT / "docs" / "images" / f
            if fp.exists():
                lines.append(f"- ![{f}](images/{f})")
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"[aggregate/ER] wrote {out}")
