"""TaichiTrajectoryViz — class wrapper around scripts/visualize_er_h5.py.

Phase E: makes the existing Taichi UI trajectory animator callable through
config-driven dispatch (tools.registry → run_experiment.stage_visualize).

Usage in plan config:

    "pipeline": {
      "visualize": {
        "enabled": true,
        "class":   "TaichiTrajectoryViz",
        "params":  {"color_mode": "chain", "record": null}
      }
    }

When `record` is non-null (path), renders to mp4 instead of opening a window.
"""
from __future__ import annotations
import sys
import argparse
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent.parent


class TaichiTrajectoryViz:
    """Wrap visualize_er_h5.run() for class-style dispatch."""

    def __init__(self, color_mode: str = "index", record: str | None = None,
                  fps: int = 60, **extra):
        # Reject typos like `colour_mode` instead of silently storing them.
        if extra:
            raise TypeError(
                f"TaichiTrajectoryViz got unexpected kwargs {sorted(extra)}; "
                f"accepted: color_mode, record, fps")
        self.color_mode = color_mode
        self.record = record
        self.fps = fps

    def render(self, run_dir):
        """Open interactive window (or write mp4 if self.record set)."""
        sys.path.insert(0, str(ROOT / "scripts"))
        import visualize_er_h5
        from visualize_er_h5 import find_h5, run as run_viz

        h5 = find_h5(str(run_dir))
        args = SimpleNamespace(record=self.record, fps=self.fps, compare=False)
        run_viz(h5, args)
        return None

    def show(self, run_dir):
        """Alias for render()."""
        return self.render(run_dir)
