# forceFieldClass.py
from constSet import *
import matplotlib.pyplot as plt


@ti.data_oriented
class forceField:
    requires_full_list: bool = False    # subclasses override

    def register(self, atomSystem, searchBox):
        self.cutoffSquare = atomSystem.cutoff * atomSystem.cutoff
        self.atomSystem = atomSystem
        self.searchBox = searchBox
        self.reciprocal = getattr(self, 'reciprocal', True)
        # Propagate requires_full_list to the searchBox so the neighbour builder
        # always uses the correct list type, regardless of registration order.
        searchBox.full_list = bool(self.requires_full_list)
        return

    @ti.func
    def calForce(self):
        pass

    @ti.func
    def calPotential(self):
        pass

    @ti.func
    def updateOneF_reciprocal(self, i: ti.i32, j: ti.i32):
        pass

    @ti.func
    def updateOneF_nonreciprocal(self, i: ti.i32, j: ti.i32):
        pass

    @ti.kernel
    def updateAllF_zero(self):
        for i in range(self.atomSystem.num_atoms):
            self.atomSystem.force[i] = ti.Vector([0.0, 0.0, 0.0])
            self.atomSystem.pe_per_atom[i] = 0.0

    @ti.kernel
    def updateAllF_compute(self):
        ti.loop_config(block_dim=128)
        for i in range(self.atomSystem.num_atoms):
            for jj in range(self.atomSystem.nNum[i]):
                j_idx = self.atomSystem.nList[i, jj]
                if j_idx >= 0 and j_idx < self.atomSystem.num_atoms:
                    if ti.static(self.reciprocal):
                        self.updateOneF_reciprocal(i, j_idx)
                    else:
                        self.updateOneF_nonreciprocal(i, j_idx)

    def updateAllF(self):
        self.updateAllF_zero()
        self.updateAllF_compute()
        return


@ti.data_oriented
class lennardJones(forceField):
    requires_full_list = True    # Task 11: full-list, eliminates force[j] atomic writes

    def __init__(self, sigma, eps):
        self.sigma6 = np.power(sigma, 6)
        self.sigma12 = self.sigma6 * self.sigma6
        self.sigma = sigma
        self.eps = eps
        self.reciprocal = True

        return

    @ti.func
    def updateOneF_reciprocal(self, i: ti.i32, j: ti.i32):
        rij = self.atomSystem.pos[j] - self.atomSystem.pos[i]
        rij = self.searchBox.applyMic(rij)
        rij_norm = rij.norm()
        rij_norm_sq = rij_norm * rij_norm

        if rij_norm_sq <= self.cutoffSquare:
            s6rij6 = self.sigma6 / ti.pow(rij_norm, 6)
            force_mag = self.calForce(rij_norm)
            rij_unit = rij / rij_norm
            fij = -force_mag * rij_unit

            # Full-list: write only force[i]; neighbour list has both (i,j) and (j,i).
            self.atomSystem.force[i] += fij

            # PE per-atom: 0.5*U on i side only; full-list visits each ordered pair once,
            # so sum over all (i,j) with 0.5 gives the unordered-pair sum.
            self.atomSystem.pe_per_atom[i] += 0.5 * self.calPotential(s6rij6)

        return

    @ti.func
    def calForce(self, r_norm: ti.f64) -> ti.f64:
        """
        wiki百科中的相对位置向量表示为：受力粒子r - 施力粒子r
        代码中为：施力粒子r - 受力粒子r
        LJ force magnitude: F = 24ε * [2(σ/r)^12 - (σ/r)^6] / r
        Optimized form: F = 24ε * [2σ^12/r^13 - σ^6/r^7]
        """
        r6 = ti.pow(r_norm, 6)
        r7 = r6 * r_norm
        r13 = ti.pow(r_norm, 13)
        return 24 * self.eps * (2 * self.sigma12 / r13 - self.sigma6 / r7)

    @ti.func
    def calPotential(self, s6rij6):
        """
        LJ pe
        """
        return 4 * self.eps * s6rij6 * (s6rij6 - 1)


@ti.data_oriented
class ERPotential(forceField):
    requires_full_list = True    # Task 11: full-list, eliminates force[j] atomic writes

    def __init__(self, Z_eff, lambda_screen, MT, E_dir=ti.Vector([0.0, 0.0, 1.0])):
        self.Z_eff = Z_eff
        self.lb = lambda_screen  # 屏蔽长度 λ
        self.MT2 = MT ** 2  # 马赫数平方
        self.E_dir = E_dir  # 电场方向矢量
        self.reciprocal = True

    def register(self, atomSystem, searchBox):
        # Resolve alpha at register-time so cs.UNITS reflects run.in choice.
        import constSet as cs
        self.alpha = cs.UNITS.KE_E2 * (self.Z_eff ** 2)
        super().register(atomSystem, searchBox)

    @ti.func
    def updateOneF_reciprocal(self, i: ti.i32, j: ti.i32):
        rij_vec = self.searchBox.applyMic(self.atomSystem.pos[j] - self.atomSystem.pos[i])
        r = rij_vec.norm()

        # 计算 cos(theta)
        cos_theta = rij_vec.dot(self.E_dir) / r
        cos2_theta = cos_theta ** 2

        # --- 势能公式分解 ---
        # W = alpha * [ exp(-r/lb)/r - 0.43 * MT^2 * lb^2 * (3*cos2_theta - 1)/r^3 ]

        # --- 力的计算 (F = -grad W) ---
        # 1. 径向力分量 (Radial Force)
        term1_r = (1 / r + 1 / self.lb) * ti.exp(-r / self.lb) / (r)  # 德拜项导数
        term2_r = -3.0 * 0.43 * self.MT2 * (self.lb ** 2) * (3 * cos2_theta - 1) / (r ** 4)  # 偶极项导数
        Fr = self.alpha * (term1_r + term2_r)

        # 2. 角度力分量 (Angular Force, 针对 cos_theta 求导)
        # 注意：这里需要根据电场方向分量合成
        F_angular_coeff = self.alpha * (0.43 * self.MT2 * self.lb ** 2 / r ** 3) * (6 * cos_theta)

        # 合力矢量 = Fr * (单位径向矢量) + F_angle * (修正矢量)
        # 简化计算：直接对分量求导更安全
        # 这里给出简化的分量力计算逻辑：
        f_vec = (Fr / r) * rij_vec
        # 加上电场诱导的非对称修正
        f_vec += (F_angular_coeff / r) * (self.E_dir - cos_theta * (rij_vec / r))

        # Full-list: write only force[i]; neighbour list has both (i,j) and (j,i).
        self.atomSystem.force[i] -= f_vec

        # PE per-atom: 0.5*U on i side only; full-list visits each ordered pair once,
        # so sum over all (i,j) with 0.5 gives the unordered-pair sum.
        cos2 = cos_theta ** 2
        U_pair = self.alpha * (
            ti.exp(-r / self.lb) / r
            - 0.43 * self.MT2 * (self.lb ** 2) * (3 * cos2 - 1) / (r ** 3)
        )
        self.atomSystem.pe_per_atom[i] += 0.5 * U_pair


@ti.data_oriented
class HertzianNonreciprocal(forceField):
    """非互易 Hertzian 力场，按 PRX 按组受力表实现。需 full_list 全邻接表。"""

    requires_full_list = True

    def __init__(self, r0, phi0, reciprocal=False):
        self.r0 = r0
        self.phi0 = phi0
        self.reciprocal = reciprocal
        return

    @ti.func
    def updateOneF_nonreciprocal(self, i: ti.i32, j: ti.i32):
        rij = self.searchBox.applyMic(self.atomSystem.pos[j] - self.atomSystem.pos[i])
        r = rij.norm()
        if r >= self.r0:
            pass
        else:
            r_hat = rij / r
            x = r / self.r0
            F_r = (self.phi0 / self.r0) * (1.0 - x)
            F_n = (self.phi0 / self.r0) * (1.0 - x) ** 2
            gi = self.atomSystem.group[i]
            gj = self.atomSystem.group[j]
            mag = F_r
            if gi != gj:                          # cross-species only
                sign = 1.0 if gi == 1 else -1.0   # A: +F_n, B: -F_n
                mag += sign * F_n
            self.atomSystem.force[i] += -mag * r_hat
            self.atomSystem.pe_per_atom[i] += 0.25 * self.phi0 * (1.0 - x) ** 2
        return