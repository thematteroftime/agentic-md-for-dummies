"""ERAnalyzer — class wrapper around scripts/analyze_er.py functions.

Exposes the three sub-analyses as methods so config-driven dispatch (via
tools/registry.py) can invoke them by class name. The underlying script
is preserved as a CLI entry point for ad-hoc use.

The class re-exports analyze_er.py functions; it does not duplicate logic.

Usage from config:

    "pipeline": {
      "analyzer_class": "ERAnalyzer",
      "analyzer_params": {"subcommand": "long"}
    }
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Re-export the three task functions and shared utilities
from analyze_er import (  # noqa: E402
    task_chain, task_long, task_length, runs_from_dirs,
    angular_pair_correlation, find_chains, Q_time_series,
    BOX_MM, LAMBDA_MM, R_MAX,
)


class ERAnalyzer:
    """Class-style wrapper for ER plasma analyses.

    Methods mirror `scripts/analyze_er.py` subcommands. All accept an optional
    `runs` argument (list of (label, dirname, MT) tuples). When omitted, falls
    back to module-level SHORT_RUNS / LONG_RUNS in analyze_er.py (empty by
    default in OSS distribution; populated by ERAggregator at dispatch time).

    Methods:
    - chain(runs=None):                fig11–13
    - long(short=None, long_=None):    fig14–16
    - length(runs=None):               fig17
    - full_analysis(run_dir, ...):     per-run hook for run_experiment.py
    """

    @staticmethod
    def chain(runs=None):
        return task_chain(runs=runs)

    @staticmethod
    def long(short=None, long_=None):
        return task_long(short=short, long_=long_)

    @staticmethod
    def length(runs=None):
        return task_length(runs=runs)

    @staticmethod
    def full_analysis(run_dir, subcommand: str = "long", run_dirs=None, **kw):
        """Pipeline hook called by run_experiment.stage_analyze.

        For across-run analyses (chain phase diagram), pass `run_dirs=[...]`
        explicitly through analyzer_params. The single `run_dir` is
        informational only.
        """
        runs = runs_from_dirs(run_dirs) if run_dirs else None
        if subcommand == "chain":
            return task_chain(runs=runs)
        if subcommand == "long":
            return task_long(long_=runs)
        if subcommand == "length":
            return task_length(runs=runs)
        if subcommand == "all":
            task_chain(runs=runs)
            task_long(long_=runs)
            task_length(runs=runs)
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
