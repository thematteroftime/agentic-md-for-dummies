"""Validate ndim=2 init temperature is exactly T0 (not 1.5*T0).

Reproduces §6.1 验收 5: ndim=2 N=1000 LJ, T0=1 ⇒ <KE> = K_B*N*T0.
The current bug runs scaleVel BEFORE zeroZ → dropping z component
makes T_final = (2/3) * T0.
"""
import os
import sys
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import constSet as cs
from atomSystemClass import AtomSystem


def test_2d_init_temperature_matches_T0():
    N = 1000
    T0 = 1.0
    box = np.array([[20.0, 0, 0], [0, 20.0, 0], [0, 0, 1.0]]).flatten().tolist()
    pos = np.zeros((N, 3))
    pos[:, 0] = np.linspace(0.1, 19.9, N)
    pos[:, 1] = np.linspace(0.1, 19.9, N)
    masses = np.ones(N)

    A = AtomSystem(num_atoms=N, n=3, cutoff=1.0, ndim=2)
    A.initData(pos, masses, T0, box, groups=None)

    vel = A.vel.to_numpy()
    z_max = float(np.max(np.abs(vel[:, 2])))
    KE = 0.5 * np.sum(masses * np.sum(vel ** 2, axis=1))
    T_meas = KE * 2.0 / (2 * cs.UNITS.K_B * N)  # d=2

    assert z_max < 1e-12, f"vel.z must be 0 after zeroZ, got max={z_max}"
    rel_err = abs(T_meas - T0) / T0
    assert rel_err < 5e-2, f"|T_meas - T0|/T0 = {rel_err:.3e}, expected <5%"
    print(f"OK: T_meas={T_meas:.4f}, T0={T0}, rel_err={rel_err:.2e}")


if __name__ == "__main__":
    test_2d_init_temperature_matches_T0()
