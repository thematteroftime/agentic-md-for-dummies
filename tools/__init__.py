"""tools/ — themed sub-modules of the MD framework.

Direct submodule imports are preferred:

    from tools.analyzers.prx import PRXAnalyzer
    from tools.plotters.prx  import PRXPlotter
    from tools.resources     import ResourceEstimator, PriorRunsDB
    from tools.runner        import ExperimentRunner
    from tools.file_io       import fileOperator

The package-level `from tools import X` form is kept for backward
compatibility and uses lazy `__getattr__` so that paths which only need
e.g. an aggregator class don't eagerly drag in Taichi/CUDA at import.
"""
import importlib

# name → fully-qualified submodule path (no eager import at package load)
_LAZY_REEXPORTS = {
    "fileOperator":       "tools.file_io",
    "PRXAnalyzer":        "tools.analyzers.prx",
    "PRXPlotter":         "tools.plotters.prx",
    "ResourceEstimator":  "tools.resources",
    "PriorRunsDB":        "tools.resources",
    "ExperimentRunner":   "tools.runner",
}


def __getattr__(name):
    """Lazy re-export: pulled only when first accessed."""
    target = _LAZY_REEXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module 'tools' has no attribute {name!r}")
    mod = importlib.import_module(target)
    return getattr(mod, name)


__all__ = list(_LAZY_REEXPORTS.keys())
