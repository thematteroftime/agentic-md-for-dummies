# searchBox.py
from constSet import *
import numpy as np
from atomSystemClass import AtomSystem

@ti.data_oriented
class searchBox:
    def __init__(self, choose=1, mN=10000, cutoffNegh=10, full_list=False):
        """
        algorithm Complexity:
        Linear : 1
        square : 2
        full_list: False=半邻接表(默认)，True=全邻接表(非互易力场需)
        """
        self.mN = mN
        self.cho = choose
        self.cutoffNegh = cutoffNegh
        self.full_list = full_list

        self.needed = ti.field(ti.i32, shape=())
        self.overflow_flag = ti.field(ti.i32, shape=())

        return

    def register(self, atomSystem, forceField=None):
        atomSystem.addNegh(mN=self.mN, cutoffNegh=self.cutoffNegh)
        self.atomSystem = atomSystem
        # Driver attribute supersedes constructor arg; if forceField is given,
        # its requires_full_list always wins.
        if forceField is not None:
            self.full_list = bool(forceField.requires_full_list)

        self.cutoffNeghSquare = self.cutoffNegh * self.cutoffNegh
        if self.atomSystem.cutoff > self.cutoffNegh:
            raise ValueError(
                f"cutoffNegh ({self.cutoffNegh}) must be >= cutoff "
                f"({self.atomSystem.cutoff})")
        self.checkDis = (self.cutoffNegh - self.atomSystem.cutoff)/2
        self.checkDisSqu = self.checkDis * self.checkDis

        if (self.cho == 1):
            self.thickNess = self.getThickness()
            self.cutoffNeghInv = 1 / self.cutoffNegh

            self.numCells = ti.Vector([
                int(ti.max(1,ti.floor(self.thickNess[0] * self.cutoffNeghInv))) ,
                int(ti.max(1,ti.floor(self.thickNess[1] * self.cutoffNeghInv))) ,
                int(ti.max(1,ti.floor(self.thickNess[2] * self.cutoffNeghInv))) ,
                0
            ])
            self.numCells[3] = self.numCells[0] * self.numCells[1] * self.numCells[2]

            self.list_idx = ti.Vector.field(n=4, dtype=ti.i32, shape=self.atomSystem.num_atoms)
            self.cellCount = ti.field(dtype=ti.i32, shape=self.numCells[3])
            self.cellCount_sum = ti.field(dtype=ti.i32, shape=self.numCells[3])
            self.cellContents = ti.field(dtype=ti.i32, shape=self.atomSystem.num_atoms)

            # MIC check is per-active-dim. For ndim=2 the z-axis is forced to 0
            # every step (zeroZ), so Lz/2 < cutoffNegh on z is harmless: no two
            # particles ever have a non-zero z-image distance.
            n_active_dims = (self.atomSystem.ndim
                             if hasattr(self.atomSystem, "ndim") else 3)
            for d in range(n_active_dims):
                if self.cutoffNegh > self.thickNess[d] * 0.5:
                    raise ValueError(
                        f"cutoffNegh ({self.cutoffNegh}) > L[{d}]/2 "
                        f"({self.thickNess[d] * 0.5}) — violates MIC")

        return

    @ti.kernel
    def _fill0Negh_kernel(self):
        self.atomSystem.nNum.fill(0)
        self.atomSystem.nList.fill(0)

    @ti.kernel
    def _fill0Cell_kernel(self):
        self.cellCount.fill(0)
        self.cellCount_sum.fill(0)
        self.cellContents.fill(0)
        self.list_idx.fill(0)

    @ti.kernel
    def _count_cells_kernel(self):
        """Phase 1: each atom computes its cell idx and atomic_adds to cellCount."""
        for i in range(self.atomSystem.num_atoms):
            cell_vec = self.findCell(self.atomSystem.pos[i])
            self.list_idx[i] = cell_vec
            ti.atomic_add(self.cellCount[cell_vec[3]], 1)

    @ti.kernel
    def _build_contents_kernel(self):
        """Phase 3: each atom places itself at cellCount_sum[cell] + local_idx.

        Reuses cellCount as a per-cell write counter (zeroed by Python coordinator
        before calling).
        """
        for i in range(self.atomSystem.num_atoms):
            cell_id = self.list_idx[i][3]
            local_idx = ti.atomic_add(self.cellCount[cell_id], 1)
            global_idx = self.cellCount_sum[cell_id] + local_idx
            if global_idx < self.atomSystem.num_atoms:
                self.cellContents[global_idx] = i

    def findNegh(self):
        if self.checkUpdate():
            self.atomSystem.numUpdates += 1
            self.applyPbc()  # 将分数坐标限制在 [0，1) 中
            self.overflow_flag[None] = 0
            if self.cho == 1:
                self._fill0Negh_kernel()
                self._fill0Cell_kernel()
                self._count_cells_kernel()
                # exclusive prefix sum on CPU (numpy)
                cnt = self.cellCount.to_numpy()
                csum = np.empty_like(cnt)
                csum[0] = 0
                csum[1:] = np.cumsum(cnt[:-1])
                self.cellCount_sum.from_numpy(csum)
                # zero cellCount before _build_contents_kernel uses it as write counter
                self.cellCount.fill(0)
                self._build_contents_kernel()
                self.findNeghO1_1()
            elif self.cho == 2:
                self.findNeghO2_1()
            self.atomSystem.copyField()
            if self.overflow_flag[None] == 1:
                raise RuntimeError(
                    f"neighbor list overflow: increase mN "
                    f"(current mN={self.mN})")
        return

    @ti.kernel
    def findNeghO1_1(self):
        for n1 in range(self.atomSystem.num_atoms):
            cell_vec = self.list_idx[n1]

            # 记录上一个处理过的 neighborCell，避免在小 Box 下重复处理
            # 在 Taichi 中，我们可以通过简单的逻辑判断来跳过

            # 针对 N=1, N=2, N>=3 的全兼容逻辑
            for i in ti.static(range(-1, 2)):
                if ti.static(self.numCells[0] == 1 and i != 0): continue
                if ti.static(self.numCells[0] == 2 and i == -1): continue  # 2个Cell时只扫 0和1，不扫-1
                for j in ti.static(range(-1, 2)):
                    if ti.static(self.numCells[1] == 1 and j != 0): continue
                    if ti.static(self.numCells[1] == 2 and j == -1): continue
                    for k in ti.static(range(-1, 2)):
                        if ti.static(self.numCells[2] == 1 and k != 0): continue
                        if ti.static(self.numCells[2] == 2 and k == -1): continue
                        # 此时剩下的循环组合在任何 N 下都不会重复索引同一个 Cell

                        neighborCell = self.computeCellNegh(i, j, k, cell_vec)

                        # 开始处理邻居原子
                        for m in range(self.cellCount[neighborCell]):
                            n2 = self.cellContents[self.cellCount_sum[neighborCell] + m]

                            # 半邻接表：n1<n2；全邻接表：双向存储
                            if n1 < n2:
                                rij = self.atomSystem.pos[n2] - self.atomSystem.pos[n1]
                                rij = self.applyMic(rij)
                                if rij.norm_sqr() < self.cutoffNeghSquare:
                                    idx1 = ti.atomic_add(self.atomSystem.nNum[n1], 1)
                                    if idx1 < self.mN:
                                        self.atomSystem.nList[n1, idx1] = n2
                                    else:
                                        self.overflow_flag[None] = 1
                                    if ti.static(self.full_list):
                                        idx2 = ti.atomic_add(self.atomSystem.nNum[n2], 1)
                                        if idx2 < self.mN:
                                            self.atomSystem.nList[n2, idx2] = n1
                                        else:
                                            self.overflow_flag[None] = 1

    @ti.func
    def computeCellNegh(self, i_off, j_off, k_off, cell_vec) -> ti.i32:
        # 1. 计算邻居 Cell 的原始 xyz 坐标
        nx = cell_vec[0] + i_off
        ny = cell_vec[1] + j_off
        nz = cell_vec[2] + k_off

        # 2. 分别处理三个维度的 PBC
        if nx < 0:
            nx += self.numCells[0]
        elif nx >= self.numCells[0]:
            nx -= self.numCells[0]

        if ny < 0:
            ny += self.numCells[1]
        elif ny >= self.numCells[1]:
            ny -= self.numCells[1]

        if nz < 0:
            nz += self.numCells[2]
        elif nz >= self.numCells[2]:
            nz -= self.numCells[2]

        # 3. 返回正确的线性索引
        return nx + self.numCells[0] * (ny + self.numCells[1] * nz)

    @ti.kernel
    def findNeghO2_1(self):
        self.atomSystem.fill0Negh()

        ti.block_local(self.atomSystem.pos)
        for i, j in ti.ndrange(self.atomSystem.num_atoms, self.atomSystem.num_atoms):
            if i < j:
                self.findNeghO2_2(i, j)
        return

    @ti.func
    def findNeghO2_2(self, i: ti.i32, j: ti.i32):
        rij = self.atomSystem.pos[j] - self.atomSystem.pos[i]
        rij_new = self.applyMic(rij)
        dis = rij_new @ rij_new

        if dis < self.cutoffNeghSquare:
            idx_i = ti.atomic_add(self.atomSystem.nNum[i], 1)
            if idx_i < self.atomSystem.mN:
                self.atomSystem.nList[i, idx_i] = j
            else:
                self.overflow_flag[None] = 1
            if ti.static(self.full_list):
                idx_j = ti.atomic_add(self.atomSystem.nNum[j], 1)
                if idx_j < self.atomSystem.mN:
                    self.atomSystem.nList[j, idx_j] = i
                else:
                    self.overflow_flag[None] = 1
        return

    @ti.kernel
    def checkUpdate(self) -> ti.i32:
        self.needed[None] = 0

        for i in range(self.atomSystem.num_atoms):
            rij = self.atomSystem.pos[i] - self.atomSystem.pos_copy[i]
            if (rij @ rij > self.checkDisSqu):
                self.needed[None] = 1

        return self.needed[None]

    @staticmethod
    @ti.func
    def applyPbcOne(sx):
        if (sx < 0.0):
            sx += 1.0
        elif (sx > 1.0):
            sx -= 1.0

        return sx

    @ti.kernel
    def applyPbc(self):
        for i in range(self.atomSystem.num_atoms):
            sV = self.atomSystem.boxList[1] @ self.atomSystem.pos[i]
            sV[0] = self.applyPbcOne(sV[0])
            sV[1] = self.applyPbcOne(sV[1])
            sV[2] = self.applyPbcOne(sV[2])
            self.atomSystem.pos[i] = self.atomSystem.boxList[0] @ sV

        return

    @ti.func
    def applyMic(self, rij):
        sij = self.atomSystem.boxList[1] @ rij
        for i in ti.static(range(self.atomSystem.n)):
            sij[i] = self.applyMicOne(sij[i])

        return self.atomSystem.boxList[0] @ sij

    @staticmethod
    @ti.func
    def applyMicOne(x12):
        if (x12 < -0.5):
            x12 += 1.0
        elif (x12 > +0.5):
            x12 -= 1.0

        return x12

    @ti.kernel
    def getThickness(self) -> ti.types.vector(3, ti.f32):
        box_T = self.atomSystem.boxList[0].transpose()

        return ti.abs(self.atomSystem.boxList[0].determinant()) / ti.Vector(
            [self.getArea(box_T[1, :], box_T[2, :]), self.getArea(box_T[2, :], box_T[0, :]),
             self.getArea(box_T[0, :], box_T[1, :])], dt=ti.f32)

    @staticmethod
    @ti.func
    def getArea(a, b):
        return a.cross(b).norm()

    @ti.func
    def findCell(self, r):
        s = self.atomSystem.boxList[1] @ r

        s_scaled = s * self.thickNess * self.cutoffNeghInv
        cell = ti.cast(ti.floor(s_scaled), ti.i32)
        for d in ti.static(range(3)):
            if cell[d] < 0:
                cell[d] += self.numCells[d]
            if cell[d] >= self.numCells[d]:
                cell[d] -= self.numCells[d]

            cell[d] = ti.min(ti.max(cell[d], 0), self.numCells[d] - 1)

        return ti.Vector(
            [cell[0], cell[1], cell[2],
             cell[0] + self.numCells[0] * (cell[1] + self.numCells[1] * cell[2])], dt=ti.i32)

