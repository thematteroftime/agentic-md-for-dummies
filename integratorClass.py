# integratorClass.py
import math
from constSet import *


@ti.data_oriented
class integratorBase:
    def register(self, atomSystem, forceField):
        self.atomSystem = atomSystem
        self.forceField = forceField
        return


@ti.data_oriented
class integrator(integratorBase):
    """BAOAB Langevin integrator (deterministic drag, no noise yet).

    Step sequence:  B - A - O - A - F - B
        B: v += (F/m) * dt/2
        A: x += v * dt/2
        O: v *= exp(-nu * dt)
        F: forceField.updateAllF()
        B: v += (F/m) * dt/2

    With nu=0, damp_factor=1 ⇒ sequence reduces to B-A-A-F-B = standard
    kick-drift-kick Velocity Verlet.

    Note: damp_factor = exp(-nu*dt) is computed once in __init__; changing
    nu after construction has no effect.
    """

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
        self.atomSystem.reduce_pe()           # NEW
        self.step_B_half()
        if self.atomSystem.ndim == 2:
            self.atomSystem.zeroZ()
        return
