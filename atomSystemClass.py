# atomSystemClass.py
from constSet import *
import constSet as cs
from toolClass import fileOperator

TAICHI_BLOCK_SIZE = 128


@ti.data_oriented
class atomBase:
    def __init__(self, num_atoms, n=3, cutoff=9, ndim=3):
        self.num_atoms = num_atoms
        self.cutoff = cutoff
        self.n = n
        self.ndim = ndim

        # dense.dense SNode allows ti.block_local(pos) in force kernel.
        # block_size MUST equal force kernel's loop_config(block_dim=...).
        self.taichi_block_size = TAICHI_BLOCK_SIZE
        num_blocks = (num_atoms + TAICHI_BLOCK_SIZE - 1) // TAICHI_BLOCK_SIZE
        self.pos = ti.Vector.field(n, dtype=ti.f64)
        ti.root.dense(ti.i, num_blocks).dense(ti.i, TAICHI_BLOCK_SIZE).place(self.pos)
        self.pos_copy = ti.Vector.field(n, dtype=ti.f64, shape=num_atoms)

        self.vel = ti.Vector.field(n, dtype=ti.f64, shape=num_atoms)
        self.force = ti.Vector.field(n, dtype=ti.f64, shape=num_atoms)

        self.mass = ti.field(dtype=ti.f64, shape=num_atoms)
        self.pe = ti.field(dtype=ti.f64, shape=())
        self.pe_per_atom = ti.field(dtype=ti.f64, shape=num_atoms)

        self.group = ti.field(dtype=ti.i32, shape=num_atoms)
        self.T_per_particle = ti.field(dtype=ti.f64, shape=num_atoms)

        return

    @ti.func
    def KineticEnergy(self) -> ti.f64:
        energy = ti.f64(0.0)
        for i in range(self.num_atoms):
            energy += (self.vel[i] @ self.vel[i]) * self.mass[i]

        return energy * 0.5

    @ti.kernel
    def computeTemperaturePerParticle(self):
        """并行计算每个粒子的动力学温度 T_i = (m_i * v_i^2) / (k_B * d)。"""
        d = ti.i32(self.ndim)
        for i in range(self.num_atoms):
            v2 = ti.f64(0.0)
            for k in ti.static(range(3)):
                if k < d:
                    v2 += self.vel[i][k] * self.vel[i][k]
            self.T_per_particle[i] = (self.mass[i] * v2) / (cs.UNITS.K_B * ti.cast(d, ti.f64))

    @ti.kernel
    def reduce_pe(self):
        """Sum pe_per_atom into pe[None]. Called once after updateAllF."""
        self.pe[None] = 0.0
        for i in range(self.num_atoms):
            self.pe[None] += self.pe_per_atom[i]

    @ti.kernel
    def scaleVel(self, T0: ti.f64):
        d = ti.cast(self.ndim, ti.f64)
        temp = self.KineticEnergy() * 2 / (d * cs.UNITS.K_B * self.num_atoms)
        factor = ti.sqrt(T0 / temp)
        for i in range(self.num_atoms):
            self.vel[i] *= factor

        return

    @ti.kernel
    def copyField(self):
        for i in range(self.num_atoms):
            self.pos_copy[i] = self.pos[i]

        return

    def addNegh(self, mN, cutoffNegh):
        self.mN = mN
        self.numUpdates = 0
        self.cutoffNegh = cutoffNegh
        if self.ndim == 2:
            box_np = self.boxList.to_numpy()[0]    # row 0 = box matrix
            assert box_np[2, 2] >= cutoffNegh, (
                "ndim=2 requires Lz >= cutoffNegh; "
                f"got Lz={box_np[2, 2]}, cutoffNegh={cutoffNegh}"
            )
        self.nNum = ti.field(dtype=ti.i32, shape=self.num_atoms)
        self.nList = ti.field(dtype=ti.i32, shape=(self.num_atoms, mN))
        return

    @ti.func
    def fill0Negh(self):
        self.nNum.fill(0)
        self.nList.fill(0)
        return


@ti.data_oriented
class AtomSystem(atomBase):
    def initData(self, positions, masses, temperature, boxList, groups=None):
        self.pos.from_numpy(positions)
        self.pos_copy.fill(0)

        self.mass.from_numpy(masses)
        if groups is not None:
            self.group.from_numpy(groups.astype(np.int32))
        else:
            self.group.fill(1)
        self.invtotalM = 1.0 / sum(self.mass.to_numpy())

        self.boxList = ti.Matrix.field(n=3, m=3, dtype=ti.f64, shape=2)
        self.boxList[0] = np.array(boxList).reshape((3, 3))
        self.boxList[1] = np.linalg.inv(np.array(boxList).reshape((3, 3)))

        self.vel.fill(0.0)
        self.initVel()
        if self.ndim == 2:
            self.zeroZ()                # before scaleVel so KE drops z

        self.scaleVel(temperature)

        self.force.fill(0.0)

        self.pe[None] = 0.0

        return

    @ti.kernel
    def initVel(self):
        invMass = self.invtotalM
        # Taichi 1.7.4: ti.Vector inside @ti.kernel rejects `dtype=` (lowers to
        # make_matrix); inferred f64 from default_fp set in constSet._init_taichi.
        centerV = ti.Vector([0.0, 0.0, 0.0])

        for i in range(self.num_atoms):
            self.vel[i] = 2 * ti.Vector([ti.randn(), ti.randn(), ti.randn()]) - 1
            centerV += self.mass[i] * self.vel[i]

        centerV *= invMass

        for i in range(self.num_atoms):
            self.vel[i] -= centerV

        return

    @ti.kernel
    def getKEnergy(self) -> ti.f64:
        return self.KineticEnergy()

    @ti.kernel
    def zeroZ(self):
        for i in range(self.num_atoms):
            self.pos[i] = ti.Vector([self.pos[i][0], self.pos[i][1], 0.0])
            self.vel[i] = ti.Vector([self.vel[i][0], self.vel[i][1], 0.0])
