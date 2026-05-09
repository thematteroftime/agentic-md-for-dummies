"""Regression test for stale K_B bug in atomSystemClass.

After cs.reconfigure(units='reduced'), scaleVel must use K_B=1.0 not 1.38e-20.
Failure mode: initial velocities are essentially zero because the scale factor
is sqrt(T0 * 1.38e-20 / KE).
"""
import os
import sys
import subprocess
import json

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))


def measure_kinetic_energy(units, T0):
    code = f"""
import os, sys
sys.path.insert(0, r'{ROOT}'); os.chdir(r'{ROOT}')
import constSet as cs
cs.reconfigure(units='{units}', log=False, debug=False, profiler=False)
from atomSystemClass import AtomSystem
import numpy as np

N = 100
pos = np.zeros((N, 3))
pos[:, 0] = np.linspace(0.1, 9.9, N)
A = AtomSystem(num_atoms=N, n=3, cutoff=1.0, ndim=2)
A.initData(pos, np.ones(N), {T0}, [10.0, 0, 0, 0, 10.0, 0, 0, 0, 1.0], None)

vel = A.vel.to_numpy()
KE = 0.5 * float(np.sum(np.sum(vel ** 2, axis=1)))  # mass=1
# Expected: KE = (d/2) * N * k_B * T = 1 * N * k_B * T0 (d=2)
expected_KE = N * cs.UNITS.K_B * {T0}
ratio = KE / expected_KE if expected_KE > 0 else 0.0
import json
print('RESULT_JSON', json.dumps({{"KE": KE, "expected_KE": expected_KE, "ratio": ratio}}))
"""
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=60)
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT_JSON")]
    if not line:
        print("STDOUT:", r.stdout[-500:])
        print("STDERR:", r.stderr[-500:])
        raise RuntimeError("no result")
    return json.loads(line[0].split(" ", 1)[1])


def test_reduced_units_scaleVel():
    """In reduced units (K_B=1.0), KE after scaleVel must equal N*k_B*T0."""
    r = measure_kinetic_energy("reduced", 1.0)
    print(f"reduced units: KE={r['KE']:.4f}, expected={r['expected_KE']:.4f}, ratio={r['ratio']:.4f}")
    assert abs(r['ratio'] - 1.0) < 1e-3, (
        f"reduced-units scaleVel ratio {r['ratio']:.4e} != 1.0 -- "
        "bug: stale K_B in atomSystemClass freezes macro value")


def test_macro_units_scaleVel():
    """In macro units (K_B=1.38e-20), KE after scaleVel must equal N*k_B*T0."""
    r = measure_kinetic_energy("macro", 348.0)
    print(f"macro units: KE={r['KE']:.4e}, expected={r['expected_KE']:.4e}, ratio={r['ratio']:.4f}")
    assert abs(r['ratio'] - 1.0) < 1e-3, (
        f"macro-units scaleVel ratio {r['ratio']:.4e} != 1.0")


if __name__ == "__main__":
    test_reduced_units_scaleVel()
    test_macro_units_scaleVel()
    print("OK: scaleVel respects current units")
