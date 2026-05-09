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
                   title: str, short_run_dirs=None, **params) -> None:
        """REQUIRED contract method (§3.5).

        run_dirs:       long-time runs (used for 'long' and 'length' plots)
        short_run_dirs: optional short-window runs (used for 'chain' plots and
                        for the side-by-side short/long comparison in 'long')
        plots:          subset of {"chain", "long", "length", "all"}

        Each dir must contain a manifest.json with `tag` and `MT` fields.
        The aggregator translates run_dirs → analyze_er's expected
        (label, dirname, MT) tuple format via runs_from_dirs().
        """
        from analyze_er import (task_chain, task_long, task_length,
                                  runs_from_dirs)

        invalid = [p for p in plots if p not in ERAggregator.KNOWN_PLOTS]
        if invalid:
            print(f"[aggregate/ER] unknown plot keys {invalid}; "
                  f"valid: {ERAggregator.KNOWN_PLOTS}")

        long_runs = runs_from_dirs(run_dirs) if run_dirs else []
        short_runs = runs_from_dirs(short_run_dirs) if short_run_dirs else []

        if "chain" in plots or "all" in plots:
            print(f"[aggregate/ER] running 'chain' on {len(short_runs)} runs (fig11-13)...")
            task_chain(runs=short_runs or long_runs)
        if "long" in plots or "all" in plots:
            print(f"[aggregate/ER] running 'long' on "
                   f"{len(short_runs)} short + {len(long_runs)} long (fig14-16)...")
            task_long(short=short_runs, long_=long_runs)
        if "length" in plots or "all" in plots:
            print(f"[aggregate/ER] running 'length' on {len(long_runs)} long runs (fig17)...")
            task_length(runs=long_runs)

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
