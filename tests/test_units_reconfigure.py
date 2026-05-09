"""Validate constSet.reconfigure() switches UNITS atomically and exposes runtime flags."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import constSet as cs


def test_default_macro_loaded():
    assert cs.UNITS is not None, "UNITS must be set on import (default macro)"
    assert cs.UNITS.name == "macro"
    assert abs(cs.UNITS.K_B - 1.380649e-20) < 1e-30
    assert abs(cs.UNITS.KE_E2 - 2.307e-22) < 1e-30
    assert cs.UNITS.TIME_UNIT_CONVERSION == 1.0


def test_legacy_module_constants_preserved():
    # simpleMDClass uses `from constSet import *` and reads K_B, KE_E2, TIME_UNIT_CONVERSION
    assert hasattr(cs, "K_B") and cs.K_B == cs.UNITS.K_B
    assert hasattr(cs, "KE_E2") and cs.KE_E2 == cs.UNITS.KE_E2
    assert hasattr(cs, "TIME_UNIT_CONVERSION")


def test_reconfigure_to_reduced():
    cs.reconfigure(units="reduced", log=True, debug=False, profiler=False)
    assert cs.UNITS.name == "reduced"
    assert cs.UNITS.K_B == 1.0
    assert cs.UNITS.KE_E2 == 1.0
    assert cs.LOG is True
    assert cs.PROFILER is False


def test_reconfigure_back_to_macro():
    cs.reconfigure(units="macro", log=False, debug=False, profiler=False)
    assert cs.UNITS.name == "macro"
    assert cs.LOG is False


if __name__ == "__main__":
    test_default_macro_loaded()
    test_legacy_module_constants_preserved()
    test_reconfigure_to_reduced()
    test_reconfigure_back_to_macro()
    print("OK: all tests passed")
