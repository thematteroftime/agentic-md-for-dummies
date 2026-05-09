# constSet.py
"""Runtime-bound unit system + Taichi 1.7 init wrapper.

Backward compat: module-level `K_B`, `KE_E2`, `TIME_UNIT_CONVERSION` mirror
`UNITS.*` so legacy scripts using `from constSet import *` keep working.
Call `reconfigure(...)` BEFORE any AtomSystem / Taichi field is allocated.
Modules that bound `K_B` / `KE_E2` via `from constSet import *` BEFORE
calling `reconfigure(...)` will retain stale values — re-import or
read `cs.UNITS.K_B` / `cs.K_B` after the switch.
"""
import os
from dataclasses import dataclass
import yaml
import taichi as ti
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import time
import plotly.io as pio
import plotly.offline as py
import plotly.graph_objects as go
import h5py
import threading
import queue


@dataclass
class Units:
    name: str
    K_B: float
    KE_E2: float
    TIME_UNIT_CONVERSION: float
    length_label: str


# Runtime-bound globals — populated by reconfigure() / set_units().
UNITS: Units = None
LOG: bool = False
PROFILER: bool = False

# Module-level mirrors — kept in sync with UNITS for `from constSet import *`.
K_B: float = 0.0
KE_E2: float = 0.0
TIME_UNIT_CONVERSION: float = 1.0

_TAICHI_INITED = False
_DEBUG = False

_UNITS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "units")
_OFFLINE_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   ".ti_cache")


def set_units(name: str = "macro") -> None:
    """Load units/<name>.yaml into UNITS singleton + sync legacy mirrors."""
    global UNITS, K_B, KE_E2, TIME_UNIT_CONVERSION
    path = os.path.join(_UNITS_DIR, f"{name}.yaml")
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    UNITS = Units(**cfg)
    K_B = UNITS.K_B
    KE_E2 = UNITS.KE_E2
    TIME_UNIT_CONVERSION = UNITS.TIME_UNIT_CONVERSION


def _init_taichi(debug: bool, profiler: bool) -> None:
    """First-or-switch ti.init. MUST run before any field allocation."""
    global _TAICHI_INITED, _DEBUG
    if _TAICHI_INITED:
        ti.reset()
    try:
        ti.init(
            arch=ti.gpu,
            default_fp=ti.f64,
            debug=debug,
            kernel_profiler=profiler,
            advanced_optimization=True,
            fast_math=True,
            offline_cache=True,
            offline_cache_file_path=_OFFLINE_CACHE_PATH,
        )
        print("[Taichi] Initialized on GPU "
              f"(debug={debug}, profiler={profiler})")
    except Exception as e:
        print(f"[Taichi] GPU init failed: {e}; falling back to CPU")
        try:
            ti.init(arch=ti.cpu, default_fp=ti.f64,
                    debug=debug, kernel_profiler=profiler)
            print(f"[Taichi] Initialized on CPU "
                  f"(debug={debug}, profiler={profiler})")
        except Exception as cpu_err:
            print(f"[Taichi] CPU init also failed: {cpu_err}")
            raise
    _DEBUG = debug
    _TAICHI_INITED = True


def reconfigure(units: str = "macro",
                log: bool = False,
                debug: bool = False,
                profiler: bool = False) -> None:
    """Apply run.in flags. Call BEFORE AtomSystem instantiation."""
    global LOG, PROFILER
    set_units(units)
    LOG = log
    PROFILER = profiler
    _init_taichi(debug, profiler)


# Module-load defaults: macro units + production Taichi flags.
# `simpleMDClass.py` and other legacy entry points see these without changes.
set_units("macro")
_init_taichi(debug=False, profiler=False)
