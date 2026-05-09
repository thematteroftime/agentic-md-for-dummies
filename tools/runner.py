"""ExperimentRunner — campaign-level orchestrator: preflight → smoke → production → analyze.

Depends on ResourceEstimator (resources.py), PRXAnalyzer (analyzers/prx.py),
PRXPlotter (plotters/prx.py).
"""
import json as _json
import datetime as _dt
from pathlib import Path as _Path
from tools.analyzers.prx import PRXAnalyzer
from tools.plotters.prx import PRXPlotter
from tools.resources import ResourceEstimator, PriorRunsDB

class ExperimentRunner:
    """Standard run lifecycle: preflight → smoke → run → analyze.

    Usage (single run):
        runner = ExperimentRunner({
            "tag": "E5", "N": 10000, "steps": 5_000_000,
            "phi": 0.5, "T0": 1.0, "stride": 600,
        })
        run_dir = runner.go()    # full pipeline

    Usage (campaign):
        ExperimentRunner.run_campaign([cfg1, cfg2, cfg3])
    """

    SCRIPT_DIR = _Path(__file__).resolve().parent
    DEFAULTS = {"N": 10000, "stride": 600, "cho": 1, "dt": 0.004}

    def __init__(self, config, python_path=None):
        import sys as _sys
        self.config = {**self.DEFAULTS, **config}
        # Default to the running interpreter; override with python_path= for
        # multi-env workflows (e.g. dispatch from base env into a CUDA env).
        self.python = python_path or _sys.executable
        self.tag = self.config["tag"]
        self.estimate = None

    def preflight(self):
        """Print resource estimate; return the dict so caller can store."""
        self.estimate = ResourceEstimator.print_preflight(self.config)
        return self.estimate

    def smoke(self, smoke_steps=2000):
        """Tiny run to verify init + first chunk write before committing
        to a multi-hour production run. Skipped if smoke_steps <= 0."""
        if smoke_steps <= 0:
            return True
        smoke_cfg = {**self.config, "tag": f"{self.tag}_smoke",
                      "steps": int(smoke_steps)}
        print(f"[ExperimentRunner] smoke run: {smoke_steps} steps")
        cmd = self._build_cmd(smoke_cfg)
        ret = _subprocess.run(cmd, cwd=str(self.SCRIPT_DIR))
        if ret.returncode != 0:
            print(f"[ExperimentRunner] SMOKE FAILED rc={ret.returncode}")
            return False
        # Find the smoke run dir and verify report.md (auto_analyze ran)
        smokes = sorted((self.SCRIPT_DIR / "outputFiles").glob(
            f"*_{self.tag}_smoke"))
        if not smokes:
            print("[ExperimentRunner] smoke produced no run dir")
            return False
        if not (smokes[-1] / "report.md").exists():
            print("[ExperimentRunner] smoke produced no report.md")
            return False
        print(f"[ExperimentRunner] smoke OK: {smokes[-1].name}")
        return True

    def run(self):
        """Production run. Returns the run dir on success, None on failure."""
        cmd = self._build_cmd(self.config)
        print(f"[ExperimentRunner] launching {self.tag}")
        ret = _subprocess.run(cmd, cwd=str(self.SCRIPT_DIR))
        if ret.returncode != 0:
            print(f"[ExperimentRunner] RUN FAILED rc={ret.returncode}")
            return None
        prods = sorted(
            d for d in (self.SCRIPT_DIR / "outputFiles").glob(f"*_{self.tag}")
            if "_smoke" not in d.name
        )
        if not prods:
            return None
        return prods[-1]

    def go(self, smoke_steps=2000):
        """preflight → smoke → run; analyze auto-runs inside the script."""
        self.preflight()
        if smoke_steps > 0:
            if not self.smoke(smoke_steps):
                return None
        return self.run()

    def _build_cmd(self, cfg):
        return [
            self.python, str(self.SCRIPT_DIR / "prx_nonreciprocal_run.py"),
            "--tag", str(cfg["tag"]),
            "--N", str(cfg["N"]),
            "--steps", str(cfg["steps"]),
            "--phi", str(cfg["phi"]),
            "--T0", str(cfg["T0"]),
            "--stride", str(cfg["stride"]),
            "--cho", str(cfg["cho"]),
        ]

    @staticmethod
    def run_campaign(configs, smoke_steps=2000, halt_on_fail=True):
        """Run multiple configs serially. Returns list of run dirs."""
        results = []
        for i, cfg in enumerate(configs):
            print(f"\n=== Campaign run {i+1}/{len(configs)}: {cfg['tag']} ===")
            runner = ExperimentRunner(cfg)
            rd = runner.go(smoke_steps=smoke_steps)
            results.append(rd)
            if rd is None and halt_on_fail:
                print(f"[campaign] {cfg['tag']} failed — halting chain")
                break
        return results



