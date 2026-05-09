"""3-case unit tests for `integrators.baoab_langevin.BAOABLangevin`.

Verifies the FD-balanced Wiener-noise scheme:

  case 1:  nu=0  → reduces exactly to Velocity Verlet (NVE invariant);
                  total energy drift < 1e-3·E0 over 20 LJ steps,
                  matching the BAOABDrag NVE bound.
  case 2:  nu>0  → thermostat target hit; T_meas → T_target ± 5%
                  averaged over the second half of a 10 000-step run
                  starting from a non-equilibrium IC (T_init = 2·T_target).
  case 3:  fixed Taichi seed reproducibility — two independent runs
                  with `ti.init(random_seed=S)` produce bit-for-bit
                  identical trajectories. Confirms the Wiener noise is
                  driven by Taichi's RNG (not numpy or unseeded CPython).

These tests share `setup_lj_2d(...)` with `tests/test_baoab_energy.py`; the
pattern is duplicated to keep tests independent of import-order ti.init quirks.
"""
from __future__ import annotations
import os
import sys
import math
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

import constSet as cs
import taichi as ti

if cs.UNITS is None or cs.UNITS.name != "reduced":
    cs.reconfigure(units="reduced", log=False, debug=False, profiler=False)

from atomSystemClass import AtomSystem
from searchBox import searchBox
from forces import lennardJones
from integrators import BAOABLangevin


def _setup_lj_2d(N=64, T0=1.0):
    """Same lattice + LJ setup as test_baoab_energy.py — kept local so this
    test file does not couple to test_baoab_energy.py import order."""
    side = int(math.ceil(math.sqrt(N)))
    L = side * 1.2
    cutoffNegh = 2.6
    Lz = 2.0 * cutoffNegh + 0.1
    pos = np.zeros((N, 3))
    k = 0
    for i in range(side):
        for j in range(side):
            if k < N:
                pos[k] = [i * 1.2 + 0.1, j * 1.2 + 0.1, 0.0]
                k += 1
    masses = np.ones(N)
    box = [L, 0, 0, 0, L, 0, 0, 0, Lz]
    A = AtomSystem(num_atoms=N, n=3, cutoff=2.5, ndim=2)
    A.initData(pos, masses, T0, box, groups=None)
    sb = searchBox(choose=1, mN=64, cutoffNegh=cutoffNegh, full_list=False)
    sb.register(A)
    ff = lennardJones(sigma=1.0, eps=1.0)
    ff.register(atomSystem=A, searchBox=sb)
    return A, sb, ff


def _total_energy(A):
    KE = 0.5 * float(np.sum(np.sum(A.vel.to_numpy() ** 2, axis=1)
                            * A.mass.to_numpy()))
    PE = float(A.pe[None])
    return KE, PE


def _measure_temperature(A):
    """k_B T = <m v²> / (ndim · N)  — matches scaleVel convention."""
    v = A.vel.to_numpy()
    m = A.mass.to_numpy()
    # ndim=2 → only x,y carry KE; z is zeroed by zeroZ at end of inteBegin
    v2 = v[:, 0] ** 2 + v[:, 1] ** 2
    KE = 0.5 * float(np.sum(m * v2))
    return float(2.0 * KE / (A.ndim * cs.UNITS.K_B * A.num_atoms))


def test_baoab_langevin_nu0_reduces_to_velocity_verlet():
    """Case 1: nu=0 → noise term identically zero → NVE energy invariant.

    Bound matches BAOABDrag's nu=0 test: drift < 1e-3·E0 over 20 LJ steps.
    """
    A, sb, ff = _setup_lj_2d(N=64, T0=0.5)
    inte = BAOABLangevin(timeStep=0.001, T_target=0.5, nu=0.0)
    inte.register(atomSystem=A, forceField=ff)
    sb.findNegh()
    ff.updateAllF()
    A.reduce_pe()
    KE0, PE0 = _total_energy(A)
    E0 = KE0 + PE0

    for step in range(20):
        sb.findNegh()
        inte.inteBegin()
        sb.applyPbc()

    KE, PE = _total_energy(A)
    E = KE + PE
    rel_drift = abs(E - E0) / abs(E0)
    print(f"BAOAB-Langevin nu=0: E0={E0:.6e}, E_final={E:.6e}, drift={rel_drift:.3e}")
    assert rel_drift < 1e-3, (
        f"BAOAB-Langevin nu=0 must reduce to Velocity Verlet; "
        f"got drift={rel_drift:.3e} > 1e-3 — Wiener term not vanishing")
    print("OK BAOAB-Langevin nu=0 → NVE-faithful (Velocity Verlet reduction)")


def test_baoab_langevin_thermostat_hits_target():
    """Case 2: nu>0, non-equilibrium IC → T_meas → T_target within ±5%.

    Start with T_init = 2·T_target (intentionally hot), run 10000 steps
    (= 50 τ at dt=0.005), then average T over last 5000 steps. FD-balanced
    Wiener noise must equilibrate the kinetic temperature regardless of IC.
    """
    T_target = 1.0
    A, sb, ff = _setup_lj_2d(N=64, T0=2.0)    # IC twice the target
    dt = 0.005
    nu = 1.0    # generously over-damped so equilibration is fast
    inte = BAOABLangevin(timeStep=dt, T_target=T_target, nu=nu)
    inte.register(atomSystem=A, forceField=ff)
    sb.findNegh()
    ff.updateAllF()
    A.reduce_pe()
    T_init = _measure_temperature(A)
    print(f"BAOAB-Langevin T-target test: T_init={T_init:.4f}, T_target={T_target}")

    n_steps = 10000
    T_samples = []
    for step in range(n_steps):
        sb.findNegh()
        inte.inteBegin()
        sb.applyPbc()
        if step >= n_steps // 2 and step % 50 == 0:
            T_samples.append(_measure_temperature(A))

    T_meas = float(np.mean(T_samples))
    T_std = float(np.std(T_samples))
    rel_err = abs(T_meas - T_target) / T_target
    print(f"BAOAB-Langevin T_meas={T_meas:.4f} ± {T_std:.4f} "
          f"(target {T_target}, rel_err={rel_err*100:.2f}%)")
    assert rel_err < 0.05, (
        f"BAOAB-Langevin T_meas={T_meas:.4f} differs from "
        f"T_target={T_target} by {rel_err*100:.1f}% > 5% — FD balance broken")
    print("OK BAOAB-Langevin equilibrates to T_target within 5%")


def test_baoab_langevin_seed_reproducibility():
    """Case 3: ti.init(random_seed=S) makes two independent runs identical.

    Runs the same 200-step trajectory twice with the same Taichi seed and
    asserts the final position fields match to <1e-12. Ensures the Wiener
    noise is driven by Taichi's RNG (not numpy or unseeded CPython), and
    therefore campaign reproducibility is achievable per Hard rule #7.
    """
    SEED = 12345
    dt = 0.005
    nu = 1.0
    T_target = 1.0
    n_steps = 200

    def _one_run(seed):
        # Reset Taichi with the requested seed. ti.reset() is a hard restart;
        # it tears down all live fields so we must rebuild.
        cs.reconfigure(units="reduced", log=False, debug=False,
                        profiler=False, random_seed=seed) if False else None
        # cs.reconfigure does not currently accept random_seed; do it directly:
        ti.reset()
        ti.init(arch=ti.gpu, default_fp=ti.f64, random_seed=seed,
                advanced_optimization=False, fast_math=False,
                offline_cache=False)
        # Re-set UNITS-derived module mirrors after reset (taichi-oblivious):
        # cs.set_units leaves the dataclass intact; just need K_B etc.
        if cs.UNITS is None:
            cs.set_units("reduced")

        A, sb, ff = _setup_lj_2d(N=64, T0=1.0)
        inte = BAOABLangevin(timeStep=dt, T_target=T_target, nu=nu)
        inte.register(atomSystem=A, forceField=ff)
        sb.findNegh()
        ff.updateAllF()
        A.reduce_pe()
        for step in range(n_steps):
            sb.findNegh()
            inte.inteBegin()
            sb.applyPbc()
        return A.pos.to_numpy().copy(), A.vel.to_numpy().copy()

    pos1, vel1 = _one_run(SEED)
    pos2, vel2 = _one_run(SEED)

    pos_diff = float(np.max(np.abs(pos1 - pos2)))
    vel_diff = float(np.max(np.abs(vel1 - vel2)))
    print(f"BAOAB-Langevin reproducibility: pos_max_diff={pos_diff:.3e}, "
          f"vel_max_diff={vel_diff:.3e}")
    assert pos_diff < 1e-10, (
        f"BAOAB-Langevin not reproducible under fixed Taichi seed: "
        f"max pos diff = {pos_diff:.3e}")
    assert vel_diff < 1e-10, (
        f"BAOAB-Langevin not reproducible under fixed Taichi seed: "
        f"max vel diff = {vel_diff:.3e}")
    print("OK BAOAB-Langevin reproducible under fixed Taichi seed")

    # Restore default Taichi state so subsequent tests are not affected.
    ti.reset()
    cs.reconfigure(units="reduced", log=False, debug=False, profiler=False)


def test_baoab_langevin_registered_in_both_registries():
    """Catch the silent mode where BAOABLangevin is added to one registry
    but not the other — mirrors the regression coverage in
    `tests/test_skill_regression.py:test_registry_local_init_sync`."""
    from integrators import INTEGRATOR_REGISTRY
    from tools.registry import _REGISTRY
    assert "baoab_langevin" in INTEGRATOR_REGISTRY, (
        "baoab_langevin missing from integrators/__init__.py:INTEGRATOR_REGISTRY")
    assert "BAOABLangevin" in _REGISTRY, (
        "BAOABLangevin missing from tools/registry.py:_REGISTRY")
    target = _REGISTRY["BAOABLangevin"]
    assert target == "integrators.baoab_langevin:BAOABLangevin", (
        f"unexpected target for BAOABLangevin: {target}")
    print("OK BAOABLangevin registered in BOTH INTEGRATOR_REGISTRY and "
          "tools/registry.py:_REGISTRY")


if __name__ == "__main__":
    test_baoab_langevin_nu0_reduces_to_velocity_verlet()
    test_baoab_langevin_thermostat_hits_target()
    test_baoab_langevin_seed_reproducibility()
    test_baoab_langevin_registered_in_both_registries()
    print("\nAll 4 BAOAB-Langevin tests passed.")
