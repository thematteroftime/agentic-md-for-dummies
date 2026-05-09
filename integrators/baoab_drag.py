"""BAOAB integrator with drag-only Langevin (no Wiener noise).

This is the ORIGINAL integrator preserved through the integrators/ refactor.
It satisfies the BAOAB step ordering but the O step is `v *= exp(-ν·dt)`
without the fluctuation-dissipation noise term — so it is **deterministic
damping**, not a thermodynamically-faithful Langevin thermostat.

Step sequence:  B - A - O - A - F - B
  B: v += (F/m) * dt/2
  A: x += v * dt/2
  O: v *= exp(-ν·dt)                    ← drag-only; no noise
  F: forceField.updateAllF()
  B: v += (F/m) * dt/2

Use this integrator when:
- Pure NVE is wanted (set `nu=0`, the O step becomes a no-op)
- A paper's question is purely structural (RDFs, snapshot images) and
  small temperature drift over the run is acceptable
- The legacy PRX 2015 + PRL 2008 reproductions, both of which were
  designed against this integrator (changing it would be a regression)

DO NOT use for:
- Diffusion / viscosity / glassy dynamics — `step_O_full` removes too much
  velocity over a short window and MSD plateaus instead of growing
  linearly. See `tools/analyzers/pedersen.py` MSD output for an example
  artifact.
- Any paper whose central observable is a transport coefficient or a
  fluctuation-dissipation quantity.

For those cases, use a Wiener-noise BAOAB instead (`integrators/baoab_langevin.py`
when implemented — see `references/force_types.md` "Adding a new integrator"
for the extension flow).
"""
import math
from constSet import *
from integrators.base import IntegratorBase


@ti.data_oriented
class BAOABDrag(IntegratorBase):
    """BAOAB step ordering, drag-only O step (no Wiener noise)."""

    REQUIRED_KWARGS = ("timeStep",)
    OPTIONAL_KWARGS = ("nu",)
    SCHEME_NAME = "baoab_drag"

    def __init__(self, timeStep, nu=0.0):
        self.delta_t = float(timeStep)
        self.delta_tHalf = self.delta_t / 2.0
        self.nu = float(nu)
        self.damp_factor = math.exp(-self.nu * self.delta_t)
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
        damp = ti.f64(self.damp_factor)
        for i in range(self.atomSystem.num_atoms):
            self.atomSystem.vel[i] *= damp

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
