"""ERAnalyzer — class wrapper around scripts/analyze_er.py functions.

Exposes the three Plan G/G2/G3 analyses as methods so config-driven dispatch
(via tools/registry.py) can invoke them by class name. Preserves the
underlying script as a CLI entry point for ad-hoc use.

Phase E: registry-callable wrapper. Body still lives in scripts/analyze_er.py;
this module imports its functions to avoid duplication.

Usage from config:

    "pipeline": {
      "analyzer_class": "ERAnalyzer",
      "analyzer_params": {"subcommand": "all"}
    }
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Re-export the three task functions and shared utilities
from analyze_er import (  # noqa: E402
    task_chain, task_long, task_length,
    angular_pair_correlation, find_chains, Q_time_series,
    SHORT_RUNS, LONG_RUNS, BOX_MM, LAMBDA_MM, R_MAX,
)


class ERAnalyzer:
    """Class-style wrapper for ER plasma analyses.

    Methods mirror `scripts/analyze_er.py` subcommands:
    - chain():    Plan G snapshot, fig11–13
    - long():     Plan G2/G3 long-time, fig14–16
    - length():   chain length distribution, fig17
    - full_analysis(run_dir): per-run hook for run_experiment.py pipeline.
    """

    @staticmethod
    def chain():
        return task_chain()

    @staticmethod
    def long():
        return task_long()

    @staticmethod
    def length():
        return task_length()

    @staticmethod
    def full_analysis(run_dir, subcommand: str = "long", **kw):
        """Pipeline hook called by run_experiment.stage_analyze.

        For ER plasma campaigns, the analysis is across-runs (compares 6 long
        runs to extract phase diagram), so `run_dir` is informational only and
        the analysis runs over the registered LONG_RUNS list.
        """
        if subcommand == "chain":
            return task_chain()
        if subcommand == "long":
            return task_long()
        if subcommand == "length":
            return task_length()
        if subcommand == "all":
            task_chain(); task_long(); task_length()
            return None
        raise ValueError(
            f"unknown ERAnalyzer subcommand '{subcommand}'; "
            f"expected one of: chain, long, length, all"
        )

    @staticmethod
    def angular_pair_correlation(pos):
        return angular_pair_correlation(pos)

    @staticmethod
    def find_chains(pos, **kw):
        return find_chains(pos, **kw)

    @staticmethod
    def Q_time_series(run_dir, sample_every: int = 10):
        return Q_time_series(run_dir, sample_every)
