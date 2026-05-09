"""BAOAB Langevin integrator — Wiener-noise (FD-balanced) version.

Implements the canonical BAOAB splitting (Leimkuhler & Matthews 2013) with
fluctuation-dissipation-balanced Ornstein-Uhlenbeck step. This is the
thermodynamically faithful counterpart of `BAOABDrag`: the noise term is
sized so the steady-state velocity distribution is Maxwell-Boltzmann at
`T_target` for any `nu > 0`.

Step sequence:  B - A - O' - A - F - B
  B : v += (F/m) * dt/2
  A : x += v * dt/2
  O': v ← α·v + sqrt((1 - α²)·k_B·T_target/m)·R,  R ~ N(0, I)
  F : forceField.updateAllF()
  B : v += (F/m) * dt/2

with α = exp(-ν·dt). The σ²(T) = (1 - α²)·k_B·T/m form solves the discrete
Ornstein-Uhlenbeck equation exactly so the velocity variance is preserved
even at large `ν·dt`.

When `nu = 0`:
  α = 1, σ² = 0 → O' is identity → scheme reduces to Velocity Verlet
  (B-A-A-F-B). NVE energy conservation invariant holds.

Use this integrator when:
- The paper's central observable is diffusion / viscosity / glass dynamics
  (FD theorem must hold). `BAOABDrag` plateaus the MSD because particles
  cannot escape their cage without thermal kicks.
- A target T must be hit and held (Langevin thermostat at T_target).

Caveats:
- `T_target` is REQUIRED and is the FD setpoint, NOT necessarily the same
  as the initial-velocity temperature `T0`. (Adapter typically passes
  T_target == T0 unless explicitly cooling.)
- In ndim=2, the @ti.kernel adds noise to all 3 velocity components; the
  outer `inteBegin()` calls `atomSystem.zeroZ()` at the end, which wipes
  the spurious z-noise. Do not pre-mask in the kernel.
- Reproducibility under fixed seed: callers must `ti.init(random_seed=S)`
  before constructing the integrator. Seed is a Taichi-runtime concern,
  not an integrator-internal one.
"""
import math
from constSet import *
import constSet as cs
from integrators.base import IntegratorBase


@ti.data_oriented
class BAOABLangevin(IntegratorBase):
    """BAOAB step ordering with Wiener-noise (FD-balanced) O step."""

    REQUIRED_KWARGS = ("timeStep", "T_target")
    OPTIONAL_KWARGS = ("nu",)
    SCHEME_NAME = "baoab_langevin"

    def __init__(self, timeStep, T_target, nu=0.0):
        self.delta_t = float(timeStep)
        self.delta_tHalf = self.delta_t / 2.0
        self.nu = float(nu)
        self.T_target = float(T_target)
        # α = exp(-ν·dt); σ² coefficient = (1 - α²)·k_B·T_target / m_i
        # (per-atom factor applied per particle in the kernel using mass[i]).
        self.damp_factor = math.exp(-self.nu * self.delta_t)
        # Pre-compute the variance prefactor that multiplies (k_B·T_target/m).
        # When nu=0 this is exactly 0 → O step becomes identity (Velocity
        # Verlet reduction, NVE-faithful).
        self.sigma2_prefactor = 1.0 - self.damp_factor ** 2
        # Cache k_B at construction time so the kernel does not need to read
        # cs.UNITS from the @ti.kernel scope.
        self.k_B = float(cs.UNITS.K_B) if cs.UNITS is not None else 1.0
        return

    @ti.kernel
    def step_B_half(self):
        for i in range(self.atomSystem.num_atoms):
            self.atomSystem.vel[i] += (
                self.atomSystem.force[i] / self.atomSystem.mass[i]
                * self.delta_tHalf)

    @ti.kernel
    def step_A_half(self):
        for i in range(self.atomSystem.num_atoms):
            self.atomSystem.pos[i] += self.atomSystem.vel[i] * self.delta_tHalf

    @ti.kernel
    def step_O_full(self):
        """Ornstein-Uhlenbeck step:  v ← α·v + σ_i·R,  σ_i² = pref·k_B·T/m_i

        The factor pref = (1 - α²) is precomputed in __init__.
        When nu=0: pref=0, sigma=0 → exact Velocity-Verlet reduction.
        """
        damp = ti.f64(self.damp_factor)
        pref = ti.f64(self.sigma2_prefactor)
        kBT = ti.f64(self.k_B * self.T_target)
        for i in range(self.atomSystem.num_atoms):
            sigma_i = ti.sqrt(pref * kBT / self.atomSystem.mass[i])
            # Generate 3-vector noise; ndim=2 zeroZ at end of inteBegin
            # wipes z-component. Do not branch inside the kernel.
            R = ti.Vector([ti.randn(), ti.randn(), ti.randn()])
            self.atomSystem.vel[i] = damp * self.atomSystem.vel[i] + sigma_i * R

    def inteBegin(self):
        self.step_B_half()
        self.step_A_half()
        self.step_O_full()
        self.step_A_half()
        self.forceField.updateAllF()
        self.atomSystem.reduce_pe()
        self.step_B_half()
        if self.atomSystem.ndim == 2:
            self.atomSystem.zeroZ()
        return
