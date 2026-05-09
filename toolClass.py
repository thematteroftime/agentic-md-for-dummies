"""Backward-compatibility re-export of the `tools/` package.

Old import paths still work:

    from toolClass import fileOperator     # → tools.file_io
    from toolClass import PRXAnalyzer       # → tools.analyzers.prx
    from toolClass import PRXPlotter        # → tools.plotters.prx
    from toolClass import ResourceEstimator # → tools.resources
    from toolClass import PriorRunsDB       # → tools.resources
    from toolClass import ExperimentRunner  # → tools.runner

New code should import from the package directly:

    from tools.analyzers.prx import PRXAnalyzer
"""
from tools import (  # noqa: F401  (re-exports)
    fileOperator,
    PRXAnalyzer,
    PRXPlotter,
    ResourceEstimator,
    PriorRunsDB,
    ExperimentRunner,
)

__all__ = [
    "fileOperator",
    "PRXAnalyzer",
    "PRXPlotter",
    "ResourceEstimator",
    "PriorRunsDB",
    "ExperimentRunner",
]
