<h1 align="center">Agentic MD-for-Dummies</h1>

<p align="center">
  <strong>一个小而完整的分子动力学复现框架——由 AI skill 驱动，把一篇物理论文转成可直接运行的实验配置。</strong>
</p>

<p align="center">
  <a href="#这个项目是什么">项目简介</a> •
  <a href="#工作原理">工作原理</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#ai-skill-工作流">AI Skill 工作流</a> •
  <a href="#添加自己的论文">添加论文</a> •
  <a href="#参考文献">参考文献</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Taichi-1.7.4-orange" alt="Taichi"/>
  <img src="https://img.shields.io/badge/Claude%20Skill-paper--to--experiment-7b53d6" alt="Claude Skill"/>
</p>

<p align="center">
  <a href="README.md">English</a> · <strong>简体中文</strong>
</p>

---

## 这个项目是什么

大部分 MD 论文配套的只有截图、一段方法描述，然后挥手再见。**复现往往要花几周时间**——读论文、解码参数、搭运行脚本、拼力场、写分析、画图，最后发现把 `T₀=0.3` 看成了 `T=0.3`。

`agentic-md-for-dummies` 是一个**论文驱动的工作流**，建立在一个极简的 Taichi MD 内核之上。它的定位是:

> **不是**又一个高性能 MD 引擎。已经有很优秀的（LAMMPS、GROMACS、GPUMD）。
>
> **是**一个教学性框架，展示完整路径：*论文 → 参数 → 仿真 → 分析 → 图*，让你换一篇论文只需写一份配置文件，必要时再加一个 adapter。

仓库内置三篇论文的**端到端复现**作为参考样例：

- Ivlev 等，*Phys. Rev. X* **5**, 011035 (2015) —— 非互易 Hertzian 力，二温度稳态
- Ivlev 等，*Phys. Rev. Lett.* **100**, 095003 (2008) —— 各向异性 Yukawa，链式相
- Pedersen 等，*Phys. Rev. Lett.* **120**, 165501 (2018) —— Kob-Andersen 二元 LJ，结构与动力学验证

### 内含什么

| | |
|---|---|
| 🧱 **四层架构** | Config → Adapter → Platform → Infrastructure，每层只与下一层通信 |
| 🤖 **AI skill** | Claude Code 的 `paper-to-experiment` skill，七步把论文变成被验证的配置；遇到要新加力 / 分析器 / 绘图器 / 聚合器走八步扩展流程，新积分器走九步 |
| 📋 **Schema 校验配置** | JSON Schema + 物理规则 + 资源预算检查，配置不合格在 GPU 启动前就拒掉 |
| 🔌 **类名分发** | 加新分析器 / 可视化 / 聚合器只需一个文件 + 注册表一行，没有中央 if-else |
| 🧪 **分层测试** | Schema 门禁、Manifest 门禁、Registry 门禁、运行时门禁，每条契约都有强制点 |
| 📐 **三篇参考论文** | PRX 2015（slope_A=2/3 误差 1% 内）、PRL 2008（链相，⟨L⟩=5.15 @ MT=0.8）、PRL 2018 KA 二元 LJ（三个温度下 g_AB 峰均 < g_AA 峰）|

---

## 为什么叫 "for-Dummies"

因为复现一篇物理论文不应该需要：

- ❌ 每篇论文写一个 5000 行的定制 C++ runner
- ❌ 30 步手册式的 "把 φ 转成 N，再转成盒子边长"
- ❌ 猜 `dt` 的单位是 fs 还是 τ
- ❌ 每次重建分析流水线

理想的样子是：

```bash
# 告诉 AI 要复现哪篇论文
$ /paper-to-experiment Ivlev_PRX_2015.pdf

# Skill 走 design 模板，遇到不确定的字段标 ASK USER:，
# 然后吐出一份验证通过的配置：
configs/plan_prx_t0sweep.json    ✓ schema valid
                                  ✓ physics rules pass
                                  ✓ within budget (4 hr/run)

# 你启动它
$ python scripts/run_experiment.py configs/plan_prx_t0sweep.json
```

就这样。不必写新力类（PRX 2015 的力已经在仓库里），不必接分析器，不必复制粘贴绘图代码。

---

## 工作原理

整个框架**严格四层**。每层只和下面一层通信。混层是 bug 的头号来源。

```
╔══════════════════════════════════════════════════════════════════════╗
║  Layer 4 — CONFIG     (纯数据，无代码)                                ║   ← 用户每篇论文
║  configs/plan_*.json  —— campaign 列表 / pipeline / 类名注册          ║     都要写这个
╠══════════════════════════════════════════════════════════════════════╣
║  Layer 3 — ADAPTER     (按论文写，遵循 TEMPLATE)                      ║   ← 加新论文时
║  prx_nonreciprocal_run.py, er_plasma_run.py, pedersen_kalj_run.py    ║     用户写
╠══════════════════════════════════════════════════════════════════════╣
║  Layer 2 — PLATFORM    (论文无关，除非有 bug 否则冻结)                 ║   ← 框架
║  scripts/run_experiment.py —— 编排器                                  ║     维护
║  tools/ —— analyzers / plotters / aggregators / visualizers / registry║
╠══════════════════════════════════════════════════════════════════════╣
║  Layer 1 — INFRASTRUCTURE  (Taichi MD 内核；数学冻结，                 ║
║  forces/ 与 integrators/ 包接受按规范注册的新类)                       ║
║  systemClass, atomSystemClass, searchBox, forces/, integrators/, ...   ║
╚══════════════════════════════════════════════════════════════════════╝
```

一次 run 走六个编号阶段：

```
0. 配置校验     (JSON Schema + 物理规则 + 预算)        —— 不动 GPU
1. preflight    (每条 run 的资源估计)                  —— 不动 GPU
2. smoke        (默认 100 步，捕获崩溃)
3. production   (真实 run，支持并行)
4. visualize    (可选，按 registry 分发)               —— Taichi UI / mp4
5. aggregate    (可选，跨 run 出图 + 报告)
```

完整架构规范见 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)。

---

## 快速开始

### 安装

```bash
git clone https://github.com/thematteroftime/agentic-md-for-dummies
cd agentic-md-for-dummies
pip install -r requirements.txt
```

> **GPU 提示**：项目使用 Taichi 1.7.4 + CUDA。CPU-only Taichi 可以跑 smoke 测试但 production 规模太慢。开发测试硬件：RTX 5060 Laptop（8 GB VRAM）。

### 校验一份示例配置（不开 GPU）

每份配置在启动前都要过三道前置校验，先体验一下：

```bash
# Schema + 物理 + 预算校验，exit 0 = 可启动
python scripts/validate_config.py configs/examples/plan_g_er_chains.json --strict
```

校验器会输出资源估计（每 run 墙钟 + 总 VRAM）。加 `--strict` 会让任何 warning 都失败。

### 跑一个小例子

PRL 2008 短 ER 等离子体 campaign（5 runs × 50k steps，RTX 5060 上约 20 分钟）：

```bash
python scripts/run_experiment.py configs/examples/plan_g_er_chains.json
```

输出每 run 落在 `outputFiles/<TS>_<tag>/`（HDF5 轨迹 + manifest.json + 每 run 的 report.md），跨 run 的图在 Phase 4（aggregate）跑完后写到 `docs/images/`。

> **更重的例子**（多小时，例如 `plan_e_damping.json`、`plan_g2_er_long.json`）也在 `configs/examples/`，但请先校验，确认你预算得起再启动。

### 跑测试套件

```bash
pytest tests/ -q
```

数秒内验证 schema、registry、validators、契约一致性。

### 独立工具

`scripts/` 下不属于主流水线但常用的几个 CLI：

| 脚本 | 用途 |
|--------|---------|
| `scripts/bench_neighbor.py` | 在多个 N 下基准 cell-list（`cho=1`）vs O(N²)（`cho=2`），帮你为硬件选 `cho` |
| `scripts/compute_delta_eff.py` | 数值积分 PRX 2015 力核的 `Δ_eff` 和 `ε` 指纹，启动 Hertzian 非互易 campaign 前自检 |
| `scripts/two_particle_calibration.py` | Hertzian 非互易力的双粒子受控碰撞测试，对照论文 Eq. (5) 验证单对能量注入 |
| `scripts/visualize_er_h5.py` | 任意 HDF5 轨迹的实时 Taichi-UI 动画；在 `tools/visualizers/` 中也封装为 `TaichiTrajectoryViz` 供配置驱动调用 |

---

## 用本仓库的两条路径

Skill 是头牌特性，但底下的框架是纯 Python，没有 AI 也跑得很好。按你的身份选一条路：

### 🤖 如果你是 AI agent

你的契约是 `.claude/skills/paper-to-experiment/` 下的 skill。先读 `SKILL.md`；其余（templates、registry、worked examples）都从那里被引用过去。最短的合法触发是 Claude Code 对话里一句话：

> *"Reproduce `papers/pedersen_prl2018.pdf` in this framework. Smoke-scale, NVT, three temperatures along the rho=1.2 isochore."*

接下来发生的就是 skill 的七步配置流程，skill 自己会描述清楚。两条扩展流程（八步力扩展、九步积分器扩展）只在论文真的需要框架尚未提供的类时才触发；那种情况下 skill 会停在 design doc 的 §2a 或 §3，把决策抛给你确认后再写代码。

下面三段 prompt 模板在产出本版本的五轮自主 sub-agent 测试中证明可靠：

<details>
<summary>复现 prompt —— 论文用的力类已经在框架里</summary>

```
Reproduce <paper title and citation> using paper-to-experiment.

Inputs:
  paper PDF: papers/<slug>.pdf
  scope:     <smoke | small production | full>; bound runs at <N>, steps at <M>;
             3 state points on the (T, rho) isochore unless paper indicates more.

Constraints:
  - Use the existing force_type if the paper's potential is already covered;
    otherwise stop at design doc §2a and ask before extending.
  - Default integrator is baoab_drag for NVE / structural runs and
    baoab_langevin for diffusion-sensitive runs (paper observable decides).
  - Do NOT commit. Hand back the design doc + config + first run dir.
```

</details>

<details>
<summary>扩展 prompt —— 论文引入新力类或新积分器</summary>

```
The paper at papers/<slug>.pdf needs a new <force class | integrator>
that the framework does not currently ship. Walk the
references/force_types.md §<4 | 5b> extension flow end-to-end:

  1. Implement the new class under forces/<name>.py or integrators/<name>.py
  2. Tests in tests/test_<name>_<N>cases.py
  3. Register in tools/registry.py + the matching package's __init__.py
  4. Schema enum + conditional in templates/plan_config.schema.json
  5. Validator branch (per-force-type or per-integrator)
  6. Adapter wiring; analyzer / plotter / aggregator if step 7-8 of force flow

Then re-run the campaign and verify Hard rule #9 holds (manifest + report
+ at least one fig per run dir). Critique to docs/specs/<date>-<topic>-critique.md.
```

</details>

<details>
<summary>审查 prompt —— 发布前一致性检查</summary>

```
Cross-validate that:
  1. tools/registry.py:_REGISTRY entries are mirrored in each package's
     local __init__.py (forces/, integrators/, tools/{analyzers,plotters,aggregators}/)
  2. schema enum values for force_type and integrator both have working adapters
     and are documented in references/force_types.md
  3. SKILL.md hard rules + force_types.md §3 conventions table + worked examples
     are mutually consistent
  4. README and ARCHITECTURE describe the same code that is on main
  5. pytest -q passes (one pre-existing flaky failure in test_units_reconfigure
     is acceptable; everything else must pass)

Report confirmed bugs separately from open questions; ask before fixing
anything ambiguous.
```

</details>

Skill 假设论文 PDF 在 `papers/` 目录里。仅凭 abstract 复现被 SKILL Hard rule #2 禁止——历史上这种做法产生过质量很差的复现——遇到 PDF 缺失，skill 会停下并把缺口报给你，而不是猜。

### 👤 如果你是人类开发者

框架的每一部分都可以手写驱动。Skill 只是包在同一份 Python 之上的便利层；你愿意的话完全可以直接写。最小的端到端添加（不动 AI）只需三步：

**1. 定义一个新力类。** `forces/` 下放一个文件，继承 `forceField`，声明 `requires_full_list` 和 `PREFLIGHT_FIELDS`，实现 `updateOneF_reciprocal`（或 `updateOneF_nonreciprocal`）：

```python
# forces/my_potential.py
from constSet import *
from forces.base import forceField


@ti.data_oriented
class MyPotential(forceField):
    requires_full_list = True
    PREFLIGHT_FIELDS = ("T0", "rho", "N", "steps")

    def __init__(self, sigma, eps):
        self.sigma = float(sigma)
        self.eps = float(eps)
        self.reciprocal = True

    @ti.func
    def updateOneF_reciprocal(self, i: ti.i32, j: ti.i32):
        rij = self.searchBox.applyMic(self.atomSystem.pos[j] - self.atomSystem.pos[i])
        r = rij.norm()
        if r * r <= self.cutoffSquare:
            # f_mag = -dV/dr; example here is a soft-core 1/r^4 well.
            f_mag = self.eps * self.sigma**4 / r**5
            self.atomSystem.force[i] += -f_mag * (rij / r)
            U_pair = self.eps * self.sigma**4 / (3.0 * r**3)
            self.atomSystem.pe_per_atom[i] += 0.5 * U_pair
```

**2. 把这个类注册到两处** —— 一处本地，一处全局：

```python
# forces/__init__.py —— 本地 registry，直接 import 时使用
from forces.my_potential import MyPotential

FORCE_REGISTRY: dict[str, type] = {
    "lennard_jones":          lennardJones,
    "er_plasma":              ERPotential,
    "hertzian_nonreciprocal": HertzianNonreciprocal,
    "kalj":                   KobAndersenLJ,
    "my_potential":           MyPotential,    # ← 新增行
}

# tools/registry.py —— 单一转发站
_REGISTRY: dict[str, str] = {
    # ... 已有条目 ...
    "MyPotential": "forces.my_potential:MyPotential",
}
```

如果两边失同步，`tests/test_skill_regression.py:test_registry_local_init_sync` 会在下一次 `pytest -q` 里大声报错。

**3. 写一份 campaign 配置**，引用新的 force_type，启动前先校验：

```bash
cat > configs/plan_my_potential.json << 'EOF'
{
  "_comment": "Smoke run for MyPotential — verify the kernel compiles and ships.",
  "_force_type_doc": "references/force_types.md (pending §N for my_potential)",
  "_units_doc": "reduced_lj",
  "campaign": [{
    "force_type": "my_potential",
    "tag": "mp_smoke",
    "T0": 1.0,
    "N": 200,
    "steps": 5000,
    "stride": 50,
    "ndim": 3,
    "units_regime": "reduced_lj"
  }],
  "pipeline": {"preflight": true, "smoke": true, "smoke_steps": 100,
               "production": true, "halt_on_fail": true, "max_parallel": 1}
}
EOF
python scripts/validate_config.py configs/plan_my_potential.json --strict
python scripts/run_experiment.py configs/plan_my_potential.json
```

校验器会拒掉这份配置，直到你也扩展了 schema 的 enum、`scripts/run_experiment.py:_invoke_md` 的分发分支、以及 `scripts/validate_config.py:check_force_type_specific` 的对应分支——这些都是 AI skill 自动走的步骤，手动模式下你逐步做即可。完整每一步的 recipe 在 `references/force_types.md §4 "Adding a new force type"`，文件号和注册点和上面 AI 工作流完全对齐。

积分器扩展是平行路径：在 `integrators/` 下继承 `IntegratorBase`，声明 `REQUIRED_KWARGS` 与 `OPTIONAL_KWARGS`，实现 `inteBegin`，注册到 `INTEGRATOR_REGISTRY` 与 `_REGISTRY`，扩 schema 的 `integrator` enum，可选地往 `check_integrator_specific` 加一条稳定性规则。`integrators/baoab_drag.py` 是最简参考，`integrators/baoab_langevin.py` 展示了带 Wiener 噪声的 FD 平衡变体（含 `(1 − α²)·k_B·T/m` 噪声前因子）。完整九步 recipe 在 `references/force_types.md §5b`。

无论哪条路径——AI 还是手写——一样的回归测试守一样的契约，一样的 registry 装一样的类，一样的 `pytest -q` 给出一样的判决。

---

## AI Skill 工作流

本仓库的独特价值在 `.claude/skills/paper-to-experiment/`——一个 [Claude Code skill](https://docs.claude.com/en/docs/claude-code/skills)，让你从 PDF 走到可运行配置，每个参数只输入一次。

### AI 怎么用这个 skill

```
1. 你在对话里抛一篇论文：
   "复现 Ivlev PRX 2015 Fig 1 —— 在固定 φ=0.3 下扫 T₀，NVE。"

2. Claude 触发 paper-to-experiment skill，它会：
   a. 读 .claude/skills/paper-to-experiment/SKILL.md（契约）
   b. 读 references/force_types.md（仓库支持的 force_type）
   c. 读 references/examples/（已有论文的样例 design）
   d. 读你提供的论文 PDF

3. Claude 填 templates/physics_design.md（12 节）：
   §1 物理观测量（带论文 Eq. 引用）
   §2 力场选择
   §3 仿真参数
   §4 扫描维度
   §5-§7 阶段、通过准则、成本
   §10b ASK USER: 它独自决策不了的项

4. 你审核 design 文档。§10b 为空（auto-mode 安全），
   Claude 继续；非空则停下来问你。

5. Claude 从 design 文档生成 configs/plan_<topic>.json。

6. Claude 跑 `validate_config.py --strict`，exit ≠ 0 就修后重跑。

7. 把启动命令交还给你。GPU 何时开你定。
```

Skill 强制几条规则：

- **引用必须有**。每个观测量都要引用论文的 Eq. 或 Fig. 编号。
- **不许凭空补**。缺参数 → `ASK USER:`，绝不猜。
- **production 前必 smoke**。永远不跳。
- **预算守门**。单 run 墙钟 > 24 hr 或 VRAM > 8 GB → 拒绝，建议改小。
- **复用先于扩展**。新力类只在没有现成的能匹配论文 Eq. 时才提出。

### 论文需要一种还没有的 force_type 怎么办

Skill 会带你走 `force_types.md §4` 文档化的八步扩展流程：

1. 在 `forces/<your_force>.py` 加新力类（提供模板）+ 注册到 `forces/__init__.py:FORCE_REGISTRY` 和 `tools/registry.py:_REGISTRY`
2. 写测试
3. 创建入口脚本（Layer 3 adapter，提供模板）
4. 更新 `scripts/run_experiment.py:_invoke_md` 分发器与 `scripts/validate_config.py:check_force_type_specific`
5. 更新 schema enum
6. 在 registry 文档里登记
7. 加分析器（`tools/analyzers/<paper>.py`）输出 `report.md`
8. 加绘图器（`tools/plotters/<paper>.py`）输出 `fig*.png`

每一步都有对应的模板文件在 `.claude/skills/paper-to-experiment/templates/`。

---

## 人类开发者保姆教程 —— 逐步走完

这一节是 `.claude/skills/paper-to-experiment/SKILL.md` 的人类版镜像。**刻意写得很详细**：每个 checkpoint、每个动到的文件、每条要敲的命令都明列；`configs/plan_pedersen_kalj.json` 这一份 Kob-Andersen 二元 LJ 复现是贯穿全程的范例。如果你已经读过上面的 *AI Skill 工作流* 一节并想自己做同一件事，本节就是同等详细的人类版地图。

三种场景覆盖几乎所有情况：

- **场景 A —— 论文使用框架已有的 force_type 和积分器**。直接跳到 *七步复现流程*。LJ / Hertzian / 各向异性 Yukawa / Kob-Andersen LJ 系列论文都在这条路。
- **场景 B —— 论文要新加一个力类**。先走 *八步力类扩展*，再回到七步复现。
- **场景 C —— 论文要新加（或必须用）一种时间积分方案**。先走 *九步积分器扩展*，再回到七步复现。

框架的硬规则（必须引用论文 / production 前必 smoke / 不许凭空猜参数 / 校验器先 green / registry 两边对齐 / 没产出 `report.md` + `fig*.png` 就算没复现完）AI 和人类一视同仁——这些规则由 schema 校验器、registry 回归测试、pipeline 阶段强制执行，不依赖任何 agent。

---

### 七步复现流程

#### 第 1 步 —— 把论文 PDF 放到磁盘上

框架的契约是"没 PDF 不写 design"：每次复现都从一份可被 design 文档引用的真实论文开始。把文件放到 `papers/` 下，按 `<author>_<journal><year>.pdf` 小写下划线规范命名，目录始终好 grep：

```bash
cp /path/to/your/paper.pdf papers/pedersen_prl2018.pdf
ls papers/*.pdf
```

如果论文付费墙拦着、你只有摘要，**停下**。Skill 的 Hard rule #2 禁止仅凭摘要复现，因为历史上这种做法产出过错误物理。要么拿到 PDF（preprint server / arXiv / ResearchGate / 学校订阅），要么换论文。`papers/` 下已有 4 篇候选 PDF（Bernard 2011、Engel 2013、Pedersen 2018、Prestipino 2005）都开源——见 `papers/CANDIDATES.md`。

**继续前的验证**：`ls papers/<your_slug>.pdf` 显示你的文件且大小非零。

#### 第 2 步 —— 审 registry，决定复用还是扩展

两份产物合起来描述了"框架已经知道的事"：

```bash
# 哪些 force_type / integrator / units_regime 字符串合法：
sed -n '1,180p' .claude/skills/paper-to-experiment/references/force_types.md

# 单一转发站 —— 哪些类被接进来了：
cat tools/registry.py
```

先读 `force_types.md` 顶部的 **Conventions table**（一张表里列出每个 force_type 的 N 含义、默认 IC、ndim、units_regime）；再读各 force_type 节（`## 1. hertzian_nonreciprocal`、`## 2. er_plasma`、`## 3. kalj`），逐行判断论文的势能是否和某一项严格匹配——同样的 Hamiltonian、同样的单位、同样的 ndim。

三种结果：

1. **复用**：论文力和某条已有项严格匹配 → design 文档 §2 写 `force_type=<name>`，跳到本场景的第 3 步。多数和 PRX 2015 / PRL 2008 / PRL 2018 同物理范畴的论文都属于这一类。
2. **扩展**：论文力确实是新的 → 切到下面的 *八步力类扩展*，做完再回。
3. **退化复用**（例如挑 `ERPotential` 然后令 `MT=0` 当各向同性 Yukawa 用）：thesis 级工作**禁止**这么做。manifest 会撒谎说跑的是 `ERPotential`，下游分析器可能误读。如果你被这条捷径诱惑到，至少在 design §10b 用 `ASK USER:` 标出来。

积分器同样过一遍：读 `force_types.md §4` 的 *Integrator selection* 表。如果论文核心观测量是扩散 / 黏度 / 玻璃动力学，默认的 `baoab_drag` 会把 MSD 卡在平台（缺 Wiener noise），你应该计划用 `baoab_langevin` 或者再扩展一种。结构分析或 NVE 跑用 `baoab_drag` 没问题。

**验证**：在纸上写四行 —— `force_type = <name>`、`integrator = <name>`、`units_regime = <name>`、`ndim = 2 或 3`。任一行写"需新类"就立刻翻到对应的扩展节。

#### 第 3 步 —— 写 design 文档

复制模板，按日期 + 主题命名新文件，逐节填：

```bash
cp .claude/skills/paper-to-experiment/templates/physics_design.md \
   docs/specs/$(date +%Y-%m-%d)-<your_topic>-design.md
```

把**每一处** `<...>` 占位符都替换掉。真的不适用的小节写 `N/A —— <理由>`，不要删——好让后来人看到你考虑过。§0 的 *Open-questions early checklist* 在写正文**之前**就要填——任何一行勾"no"或计数 ≥ 1，就停下解决再继续。

§1（观测量）是文档的脊梁。每行引用论文 Eq. 或 Fig. 编号，给定量化目标和容差。论文里没有但你推导出的衍生量打 `*` 号并在 §11 解释。`.claude/skills/paper-to-experiment/references/examples/worked_example_PRL2018_KALJ.md` 是 KA-LJ 完整 design 范例；你可以照抄它的 §1 表格形状。

§2（力场）从 registry 复制——直接把 `force_types.md` 对应条目的 required fields 抄过来。如果你在场景 B，把 §2a（八步扩展状态表）填完，然后**停**在这里给自己 greenlight 后再走扩展。

§3（仿真设置）覆盖 `N`、`box`、`dt`、`T0`、`density`、`boundary_conditions`、`thermostat`、`integrator`、`initial_state`、`equilibration_steps`、`write_stride`、`chunk_size`、`cho`、`steps_per_run`、`t_total`。`initial_state` 默认 ndim=2 用 `square_2d`，ndim=3 用 `simple_cubic_3d`；只在论文明示时覆盖。长程斥力（库仑 / Yukawa / 硬核近似）随机 IC 被 `force_types.md §4` 的 *Long-range repulsive IC caveat* **禁止**。

§4（扫描维度）默认上限 12 runs。真要更多就拆 Plan A / Plan B 并出两份配置。每个扫描值都要引用一段论文动机。

§6（pass criteria）把 §1 每条观测量翻译成 PASS / NEAR / FAIL 数值规则。KA-LJ design 的 §6 是干净参照。

§7（成本估计）估每 run 墙钟、RAM peak、VRAM peak、每 run 磁盘、campaign 总成本。硬上限：每 run 24 小时、VRAM 8 GB、磁盘 50 GB。

§10 把决策分两子表。§10a Auto-decisions 是你从 registry / examples 自定的默认——写明理由。§10b Open questions 是只有读者能定的事，前缀 `ASK USER:`。**§10b 为空才是进第 4 步的门**；非空意味着你有未解决问题，停。

**验证**：打开 design 文档，grep 任何不在代码块里的 `<` 字符（``grep -n '<' docs/specs/<your_design>.md | grep -v '\`' ``）——每个残留的字面 `<...>` 占位符都是 bug。

#### 第 4 步 —— 自审 design

§0 的 early checklist 已经守过第 3 步入口；这一步守第 5 步入口。换一双新眼睛再走一遍：

- 论文 PDF 在 §0 写的位置吗？（`ls papers/<slug>.pdf`）
- §1 每条观测量都引用了 paper Eq./Fig.，或者带 `*` 号说明是衍生？
- §2 的 `force_type` 真的在 `tools/registry.py:_REGISTRY` 和 `forces/__init__.py:FORCE_REGISTRY` 里？
- §3 的 `initial_state` 在 `tools/lattices/__init__.py:LATTICE_REGISTRY` 里（`square_2d`、`triangular_2d`、`octagonal_2d`、`simple_cubic_3d` 之一，或论文要求的扩展）？
- §4 总 runs ≤ 12，或者你已经拆成 Plan A/B？
- §7 成本估计落在硬上限以内？
- §10b 为空或全部列出？还有未解项就回去解决再继续。

任一"no"把你打回第 3 步。

#### 第 5 步 —— 生成 `configs/plan_<topic>.json`

campaign 配置是 design 文档的纯数据翻译。它带元数据、§4 cross-product 出来的每 run 参数、pipeline 阶段、以及驱动 Phase 3.4 ANALYZE / Phase 3.5 VISUALIZE / Phase 4 AGGREGATE 的注册类名。

最小必要字段（来自 `templates/plan_config.schema.json`）：

```json
{
  "_comment": "<合成自 design §0 + §1 的一段>",
  "_paper_ref": "<§0 引用>",
  "_paper_pdf": "papers/<slug>.pdf",
  "_design_doc": "docs/specs/YYYY-MM-DD-<topic>-design.md",
  "_force_type_doc": "references/force_types.md §N",
  "_units_doc": "<reduced_lj | macro_dust | reduced_yukawa>",
  "campaign": [
    {
      "force_type": "<name>",
      "tag": "<unique_run_id>",
      "ndim": 3,
      "units_regime": "reduced_lj",
      "integrator": "baoab_drag",
      "<force-required-fields>": "<from force_types.md>",
      "steps": 100000,
      "stride": 200,
      "notes": "<一行 rationale 链回 design §>"
    }
  ],
  "pipeline": {
    "preflight": true,
    "smoke": true,
    "smoke_steps": 100,
    "production": true,
    "analyze": true,
    "analyzer_class": "<Paper>Analyzer",
    "halt_on_fail": true,
    "max_parallel": 1,
    "visualize": {"enabled": true, "class": "<Paper>Plotter"}
  },
  "aggregation": {
    "enabled": true,
    "class": "<Paper>Aggregator",
    "output": "docs/<paper>_campaign_report.md",
    "plots": ["overview"]
  }
}
```

如果想看带三个状态点 + FD-balanced 热浴 + 完整 aggregator 接线的真实例子，复制 `configs/plan_pedersen_kalj.json` 来改——它是场景 A + 积分器 override 的标准范例。如果要 30 秒级 sanity check 的单温度 smoke 启动，`configs/examples/plan_pedersen_kalj_smoke.json` 是同一份 campaign 的最小版本。

`pipeline.analyzer_class`、`pipeline.visualize.class`、`aggregation.class` 引用的类**必须**已经在 `tools/registry.py:_REGISTRY` 里。如果它们不在（场景 B 的分析器 / 绘图器 / 聚合器），先回到八步扩展把那几步做完，这份配置才能通过校验。

#### 第 6 步 —— `--strict` 校验

每份配置在烧 GPU 之前先过三道前置校验：

```bash
python scripts/validate_config.py configs/plan_<your_topic>.json --strict
```

退出码：
- `0` —— schema、物理规则、预算全部通过。进第 7 步。
- `1` —— schema 或物理校验失败。读 `ERR` 行，改 JSON，重跑。
- `2` —— 仅有 warning（非严格模式 pass，严格模式 fail）。读 `warn` 行决定：要么改配置，要么在 `_comment` 里记录 override 并跑非 `--strict` 模式（前提是你清楚自己在权衡什么）。

校验器还会打成本估计（每 run 墙钟、总 VRAM、磁盘）。和 design §7 交叉核对。两边偏离超过 2× 时，校验器的 step-rate 模型相对你的硬件已陈旧——开 issue 报告，并相信更近的那一份。

校验通过后，再跑一次**不带** `--strict` 的，看看严格模式藏起来的 warning——这些都是后续要修但不阻塞 campaign 的事。

#### 第 7 步 —— 启动

框架只有一个入口：

```bash
python scripts/run_experiment.py configs/plan_<your_topic>.json
```

Pipeline 按序跑：**preflight → smoke → production → analyze (3.4) → visualize (3.5) → aggregate**。Smoke 用 100 步小爆破抓崩溃；任何 smoke 失败 + `halt_on_fail=true` 就阻断 production。每条 production 落到 `outputFiles/<TS>_<tag>/`，含 `manifest.json` + `<base>_<step>.h5` + `run.in` + `lattice.xyz`。Phase 3.4 给每个 dir 写 `report.md`，Phase 3.5 写 `figN_*.png`，Phase 4 写 `docs/<paper>_campaign_report.md` + `docs/images/<paper>_*.png` 跨 run 汇总。

**没看到答案就不算复现完。** 每个 production run dir 至少要有：

```
outputFiles/<TS>_<tag>/
├── manifest.json     ← 引擎接通
├── report.md         ← 分析器跑了（Phase 3.4）
└── fig*.png          ← 绘图器跑了（Phase 3.5）
```

如果 run dir 缺 `report.md` 或 `fig*.png`，分析器 / 绘图器没正确注册——回到八步扩展的 Step 7 / Step 8 修。

GPU 何时烧由你决定。框架不会从 design 阶段自动启动 production。

---

### 八步力类扩展

第 2 步告诉你论文势能不在 `forces/` 时走这条。参考实现是 commits `0f0593a` → `b6169c4` → `32f15bb` 中的 Kob-Andersen 扩展；下面提到的每个文件在 main 上都有真实实例。

#### 第 1 步 —— 写力类

复制模板，存到 `forces/`：

```bash
cp .claude/skills/paper-to-experiment/templates/force_class.py.template \
   forces/<your_force>.py
```

继承 `forces.base` 的 `forceField`，声明两个类级属性（`requires_full_list` 和 `PREFLIGHT_FIELDS`），实现 `updateOneF_reciprocal` 或 `updateOneF_nonreciprocal`。`forces/kalj.py` 是最干净的扩展参考——覆盖了二元混合需要的 per-pair (σ, ε) 选择；`forces/lennard_jones.py` 是单一物种最简参考。

模板形状：

```python
# forces/<your_force>.py
from constSet import *
from forces.base import forceField


@ti.data_oriented
class <YourForce>(forceField):
    requires_full_list = True              # full 邻居表对每对粒子访问 (i,j) 和 (j,i) 两次
    PREFLIGHT_FIELDS = ("<paper-specific kwargs>",)

    def __init__(self, <paper params>):
        ...
        self.reciprocal = True             # 多数力是；非互易力设 False

    @ti.func
    def updateOneF_reciprocal(self, i: ti.i32, j: ti.i32):
        rij = self.searchBox.applyMic(self.atomSystem.pos[j] - self.atomSystem.pos[i])
        r = rij.norm()
        if r * r <= self.cutoffSquare:
            f_mag = ...                                    # -dV/dr at r
            self.atomSystem.force[i] += -f_mag * (rij / r)
            U_pair = ...                                    # r 处的完整 pair 势能
            self.atomSystem.pe_per_atom[i] += 0.5 * U_pair  # 0.5 是因为 full-list 每对访问两次
```

新类要注册到**两处** registry —— 一处包内本地，一处全局：

```python
# forces/__init__.py —— 本地 registry，直接 import 时使用
from forces.<your_force> import <YourForce>

FORCE_REGISTRY: dict[str, type] = {
    # ... 已有条目原样保留 ...
    "<your_force_type>": <YourForce>,
}

__all__ = [..., "<YourForce>", "FORCE_REGISTRY"]
```

```python
# tools/registry.py —— 单一转发站，由 config 驱动的分发查这里
_REGISTRY: dict[str, str] = {
    # ... 已有条目原样保留 ...
    "<YourForce>": "forces.<your_force>:<YourForce>",
}
```

回归测试 `tests/test_skill_regression.py:test_registry_local_init_sync` 守这两边的同步。任何一边漏改下一次 `pytest -q` 就大声报错。

**验证**：`python -c "from forces import <YourForce>, FORCE_REGISTRY; print(FORCE_REGISTRY)"` 列出你的新条目。

#### 第 2 步 —— 写测试

Pair tests 用解析双粒子计算核对力大小，核对力的对称（或非互易力的反对称），核对 cutoff 边界行为。

```bash
cp tests/test_kalj_3cases.py tests/test_<your_class>_<N>cases.py
# 把解析目标换成你的势能
```

跑到 green：

```bash
pytest tests/test_<your_class>_*.py -x -v
```

production 前测试是必须的；这是 `f_mag` 符号错误或 PE 累加器漏 `0.5 *` 这类问题在污染数小时 GPU 时间之前被抓出来的地方。

#### 第 3 步 —— Adapter（论文专属入口脚本）

Adapter 是项目根的脚本，把你的力类包装成平台 CLI 契约。复制模板：

```bash
cp .claude/skills/paper-to-experiment/templates/adapter_run.py.template <topic>_run.py
```

镜像 `pedersen_kalj_run.py` 改造。结构是：

1. 顶部 `PARAMS` dict：论文默认值，含 `force_type`、`integrator`、晶格选择、论文专属 kwargs。
2. `_prepare_lattice(p, suffix)`：用 `tools.lattices.LATTICE_REGISTRY[p["initial_state"]]` 生成初始位置，把晶格文件写到 `dataFiles/`。
3. `_write_run_in(p, suffix)`：把运行参数写成 `dataFiles/` 下的 `run.in` 文本文件。
4. `main()`：解析 CLI，构造 `systemRun(...)`，调用 `runWithData()`，写 `manifest.json` 到 run dir。

Adapter **绝不能**在进程内调用分析器、绘图器、可视化——这是 `docs/ARCHITECTURE.md §3.1` 的 *FORBIDDEN*。Pipeline Phase 3.4 / 3.5 / 4 按 registry 名分发它们。

**验证**：跑一次绕过 pipeline 的 CLI smoke：

```bash
python <topic>_run.py --tag smoke --steps 100 --N 200 --T0 1.0
ls outputFiles/<TS>_smoke/
# 应有：manifest.json + .h5 + run.in + lattice.xyz
```

#### 第 4 步 —— Dispatcher 接线 + validator 分支

`scripts/run_experiment.py` 要知道怎么启动你的 adapter：

```python
# scripts/run_experiment.py
MD_SCRIPT_<TOPIC> = _ROOT / "<topic>_run.py"        # 加在已有 MD_SCRIPT_* 行附近

EXP_DEFAULTS_BY_TYPE = {
    # ... 已有条目 ...
    "<your_force_type>": {                          # 加你的默认值
        "N": 1000, "stride": 200, "nu": 0.1,
        # ... 其他默认 ...
    },
}

EXP_REQUIRED_<TYPE> = ("tag", "<paper-required-1>", "<paper-required-2>", "steps")

# 在 _normalize_config 里：
if force_type == "<your_force_type>":
    required = EXP_REQUIRED_<TYPE>

# 在 _invoke_md 里：
elif force_type == "<your_force_type>":
    cmd = [PYTHON, str(MD_SCRIPT_<TOPIC>),
           "--tag", str(exp["tag"]),
           # ... exp 字典键映射成 CLI flag ...]
```

`scripts/validate_config.py:check_force_type_specific` 也要加平行分支：

```python
elif ft == "<your_force_type>":
    # 论文专属物理 warning（亚临界阻尼、晶格不匹配等）
    ...
```

漏 validator 分支会让 `else: res.err("unknown force_type")` 静默触发，你的配置永远过不了校验。

**验证**：一份带 `"force_type": "<your_force_type>"` 的 dummy 配置过 `validate_config.py` 时不再抱怨 unknown force_type。

#### 第 5 步 —— Schema enum + 条件

`templates/plan_config.schema.json` 是框架接受何种配置的唯一权威：

```json
{
  "properties": {
    "force_type": {
      "enum": ["hertzian_nonreciprocal", "er_plasma", "kalj", "<your_force_type>"]
    }
  },
  "allOf": [
    {
      "if":   { "properties": { "force_type": { "const": "<your_force_type>" } } },
      "then": {
        "required": ["<paper-required-fields>"],
        "properties": {
          "ndim":         { "const": 3 },
          "units_regime": { "const": "reduced_lj" }
        }
      }
    }
  ]
}
```

如果论文引入全新的 units regime（`units/` 下要新加一个 yaml），同样在这里扩 `units_regime` 顶层 enum。

**验证**：`python scripts/validate_config.py configs/<your_test>.json --strict` 退 0。

#### 第 6 步 —— 在 registry 文档登记

`references/force_types.md` 是 schema enum 的人类可读对应。新加一节（下面外层用 4 个反引号，让嵌套的 `json` 块能正常渲染）：

````markdown
## N. `<your_force_type>`  (<论文 Citation>)

- **paper**: <citation>
- **entry script**: `<topic>_run.py`
- **force class**: `forces.<your_force>:<YourForce>`
- **analyzer**: `tools.analyzers.<paper>:<Paper>Analyzer`
- **plotter**: `tools.plotters.<paper>:<Paper>Plotter`
- **aggregator**: `tools.aggregators.<paper>:<Paper>Aggregator`
- **compat**: `ndim=<2|3>`, `units_regime=<reduced_lj|...>`
- **integrator**: <baoab_drag | baoab_langevin | ...>
- **IC**: <initial_state 选择 + 物种标签规则>

### Required fields per experiment
| field | type | range | meaning |
|-------|------|-------|---------|
| ... |

### Optional fields
| field | type | default | meaning |
|-------|------|---------|---------|
| ... |

### Critical pre-flight rules
- ...

### Example
```json
{ ... 标准配置块 ... }
```
````

同时在 `force_types.md` 顶部的 **Conventions table** 加一行写明你的 N 含义和默认 IC。

#### 第 7 步 —— Analyzer

按 run 分析的类，读轨迹、写 `report.md`，并可选写 `*.npz` 给绘图器消费：

```bash
cp .claude/skills/paper-to-experiment/templates/analyzer.py.template \
   tools/analyzers/<paper>.py
```

把模板里的 `MyAnalyzer` 改名为 `<Paper>Analyzer`，实现 `full_analysis(run_dir, **params) -> dict`，让该方法把 `<run_dir>/report.md` 作为副作用写出。完整契约在 `templates/physics_design.md §1.5`，`tools/analyzers/pedersen.py` 是最干净的 KA-LJ 范例。

再注册到**两处**：

```python
# tools/analyzers/__init__.py
from tools.analyzers.<paper> import <Paper>Analyzer
__all__ = [..., "<Paper>Analyzer"]

# tools/registry.py:_REGISTRY
"<Paper>Analyzer": "tools.analyzers.<paper>:<Paper>Analyzer",
```

在你的 campaign 配置里设 `pipeline.analyze=true` 和 `pipeline.analyzer_class="<Paper>Analyzer"`——Phase 3.4 必须两者都在才触发。

**验证**：重跑第 4 步那次单 production，run dir 现在含 `report.md`。

#### 第 8 步 —— Plotter 和 Aggregator

按 run 出图，跨 run 出报告：

```bash
cp .claude/skills/paper-to-experiment/templates/plotter.py.template \
   tools/plotters/<paper>.py
cp .claude/skills/paper-to-experiment/templates/aggregator.py.template \
   tools/aggregators/<paper>.py
```

`<Paper>Plotter.render(run_dir, **params)` 给每个 run dir 写 ≥1 张 `<run_dir>/figN_*.png`；`<Paper>Aggregator.aggregate(run_dirs, output, plots, title, **params)` 写主报告 `docs/<paper>_campaign_report.md`，并通过调用绘图器可选的 `fig_<name>` static 方法 render 跨 run 图。

两个类都注册到 `tools/registry.py:_REGISTRY`，并镜像到 `tools/plotters/__init__.py` 和 `tools/aggregators/__init__.py`。

在 campaign 配置里设 `pipeline.visualize.enabled=true`、`pipeline.visualize.class="<Paper>Plotter"`、`aggregation.enabled=true`、`aggregation.class="<Paper>Aggregator"`。

**验证（也是八步扩展的最终门）**：重跑一次完整 pipeline；每个 production run dir 现在含 `manifest.json + report.md + fig*.png`，`docs/<paper>_campaign_report.md` 加跨 run 图也存在。这满足 SKILL Hard rule #9，扩展完成。你现在可以从七步复现的第 5 步继续。

---

### 九步积分器扩展

论文核心观测量是扩散 / 黏度 / 玻璃动力学或任何要靠 fluctuation-dissipation 平衡热浴才能复现的传输 / 涨落量时走这条。默认 `baoab_drag` 是 drag-only Langevin —— 噪声项缺，所以 MSD 平台、`T_meas` 漂。`f65f5d3` commit 中的 `BAOABLangevin` 扩展是标准范例，下面提到的每个文件在 main 上都有真实实例。

#### 第 1 步 —— 写积分器类

复制模板，存到 `integrators/`：

```bash
cp .claude/skills/paper-to-experiment/templates/integrator.py.template \
   integrators/<your_scheme>.py
```

继承 `integrators.base` 的 `IntegratorBase`，声明三个类级属性：

```python
# integrators/<your_scheme>.py
import math
from constSet import *
import constSet as cs
from integrators.base import IntegratorBase


@ti.data_oriented
class <YourScheme>(IntegratorBase):
    REQUIRED_KWARGS = ("timeStep", "<paper-required>")
    OPTIONAL_KWARGS = ("nu",)
    SCHEME_NAME = "<your_scheme>"

    def __init__(self, timeStep, <paper-required>, nu=0.0):
        self.delta_t = float(timeStep)
        self.delta_tHalf = self.delta_t / 2.0
        # ... 缓存方案专属常量 ...

    @ti.kernel
    def step_<...>_<...>(self):
        ...

    def inteBegin(self):
        # 你方案的一整步 splitting；ndim=2 时末尾别忘了 atomSystem.zeroZ
        ...
```

`integrators/baoab_langevin.py` 是短（~60 行）且清晰的 FD-平衡 Wiener-noise 范例，含 `(1 − α²)·k_B·T_target/m` 前因子和 `@ti.kernel` 内 `ti.randn()` recipe。扩展其他随机方案时直接抄它的骨架。

#### 第 2 步 —— 测试

最小测试集：

- **ν=0 时退化为 NVE**：噪声项关掉时方案应该退化为 Velocity Verlet，长时间能量漂移有界。
- **热浴目标命中**：从非平衡 IC 出发，`T_meas` 在容差内（默认 5%；不 pin Taichi RNG seed 时容差小一点是合理的）收敛到 `T_target`。
- **Wiener 噪声可复现**：固定 `cs.reconfigure(random_seed=S)` 时两次跑产生一致轨迹。

`tests/test_baoab_langevin_3cases.py` 是标准范例。

#### 第 3 步 —— 本地 registry

```python
# integrators/__init__.py
from integrators.<your_scheme> import <YourScheme>

INTEGRATOR_REGISTRY: dict[str, type] = {
    "baoab_drag":     BAOABDrag,
    "baoab_langevin": BAOABLangevin,
    "<your_scheme>":  <YourScheme>,
}

__all__ = [..., "<YourScheme>"]
```

#### 第 4 步 —— 转发站

```python
# tools/registry.py:_REGISTRY
"<YourScheme>": "integrators.<your_scheme>:<YourScheme>",
```

#### 第 5 步 —— Schema enum + 条件

```json
{
  "properties": {
    "integrator": {
      "enum": ["baoab_drag", "baoab_langevin", "<your_scheme>"]
    }
  },
  "allOf": [
    {
      "if":   { "properties": { "integrator": { "const": "<your_scheme>" } }, "required": ["integrator"] },
      "then": { "required": ["<scheme-required-fields>"] }
    }
  ]
}
```

`if` 子句里那条 `"required": ["integrator"]` 是必须的——少了它，条件就匹配每条没设 `integrator` 的 campaign，悄悄强制约束作者本来不打算约束的项。

#### 第 6 步 —— Validator 稳定性规则

`scripts/validate_config.py:check_integrator_specific` 是专门给积分器的钩子，由 `main()` 在 `check_force_type_specific` 旁边调：

```python
def check_integrator_specific(cfg, res: Result):
    for exp in cfg.get("campaign", []):
        scheme = exp.get("integrator", "baoab_drag")
        tag = exp.get("tag", "<no-tag>")

        if scheme == "<your_scheme>":
            # 论文专属稳定性规则，例如 dt × nu < 0.1
            ...
```

`baoab_langevin` 今天的 `dt × ν < 0.1` 就是这么强制的。给你的方案加新分支。

#### 第 7 步 —— Adapter 接线

每个想用新积分器的 adapter 按名字分发：

```python
# 你的 <topic>_run.py main() 里
integrator_name = p.get("integrator", DEFAULT_INTEGRATOR)
integrator_cls = INTEGRATOR_REGISTRY[integrator_name]
inte_kwargs = {"timeStep": p["dt"], "nu": p["nu"]}
if "<paper-required>" in integrator_cls.REQUIRED_KWARGS:
    inte_kwargs["<paper-required>"] = p["<paper-required>"]

system = systemRun(..., integrator=integrator_cls, ..., inteParams=inte_kwargs)
```

`pedersen_kalj_run.py` 第 175-195 行是这种分发模式最干净的参考。

#### 第 8 步 —— Registry 文档表行

在 `references/force_types.md §4` 的 *Integrator selection* 表加一行：

| `integrator` | 方案 | 何时用 | 注意 |
|--------------|------|--------|------|
| `<your_scheme>` | <一行说明> | <要求该方案的观测量> | <稳定性 / 适用范围> |

如果你的方案除了 `nu` 和 `T_target` 还要别的字段，在 §3 / §5b 加一段示例配置块展示标准用法。

#### 第 9 步 —— 同步回归测试

`tests/test_skill_regression.py` 中的 `test_integrator_schema_enum_synced_with_registry` 已经断言每个 `INTEGRATOR_REGISTRY` 键都出现在 schema 的 `integrator` enum 里、反之亦然。把你的方案加到双 registry（第 3 + 4 步）和 schema（第 5 步）后这个测试自动通过。如果加方案但漏 schema enum，下一次 `pytest -q` 就 fail。也可考虑加一个对应于 `test_registry_local_init_sync` 的 sibling 测试断言新积分器在 `tools/registry.py:_REGISTRY` 中存在。

**验证（也是九步扩展的最终门）**：`pytest -q` 报告基线 pass 数 + 你的新测试，且一份带 `"integrator": "<your_scheme>"` 的 campaign 配置 `--strict` 校验退 0。

你现在可以从七步复现的第 3 步（或 design 已写过则第 5 步）继续。

---

## 添加自己的论文

最快的情况是论文复用框架已经支持的 force_type。挑一个最贴近你物理的起点——`configs/examples/plan_g_er_chains.json` 适合各向异性 Yukawa 系列，`configs/examples/plan_pedersen_kalj_smoke.json` 适合二元混合或对扩散敏感、需要 FD 平衡热浴的论文——然后本地迭代：

```
1.  cp configs/examples/plan_pedersen_kalj_smoke.json configs/plan_<your_topic>.json
2.  按论文调 campaign[0] 参数。在 `notes` 里引用 Eq./Fig.
3.  python scripts/validate_config.py configs/plan_<your_topic>.json --strict
4.  python scripts/run_experiment.py  configs/plan_<your_topic>.json
```

更大的情况是论文引入新力、新积分方案、论文专属分析器或绘图器 / 聚合器。Skill 为每个扩展点都备了模板，`references/force_types.md §4`（力类）和 `§5b`（积分器）记录了对应的八步与九步扩展流程。把每个模板放进对应的包，再分别往 `tools/registry.py` 和包内本地 registry 加一行——任何一边漏改回归测试都会大声报警。

| 目标 | 复制模板 | 保存为 |
|------|---------------|---------|
| 新 force_type | `templates/force_class.py.template` | `forces/<your_force>.py` |
| 新积分器方案 | `templates/integrator.py.template` | `integrators/<your_scheme>.py` |
| 新论文 adapter | `templates/adapter_run.py.template` | `<topic>_run.py` |
| 新分析器 | `templates/analyzer.py.template` | `tools/analyzers/<topic>.py` |
| 新绘图器 | `templates/plotter.py.template` | `tools/plotters/<topic>.py` |
| 新聚合器 | `templates/aggregator.py.template` | `tools/aggregators/<topic>.py` |
| 新可视化 | `templates/visualizer.py.template` | `tools/visualizers/<topic>.py` |

---

## 参考复现

仓库端到端复现了三篇论文，每篇都是 skill 的完整一遍走法：`configs/` 下一份 JSON 配置、`tools/` 下论文专属的 analyzer / plotter / aggregator，以及 `docs/images/` 中已经 commit 的复现图（PRX 2015、PRL 2008）或按需 render 到 `docs/` 的跨 run 报告（PRL 2018）。前两篇是物理引擎的原始验证，第三篇在 `v0.2.0` cycle 中加入，用同一篇论文同时演练二元混合的力扩展和 FD 平衡 Langevin 积分器扩展。

### Ivlev 等，*Phys. Rev. X* 5, 011035 (2015)

**非互易 Hertzian 二元混合，二温度 NVE 渐近态。**

| 观测量 | 论文 | 复现 | 误差 |
|------------|-------|------------|-------|
| slope_A (T_A ∝ t^α) | 2/3 ≈ 0.667 | 0.6617 | 0.74% |
| τ_∞ = T_A/T_B | 3.10 | 2.86 | 7.9% |
| Δ_eff（解析指纹）| 0.57 | 0.5714 | 0.25% |
| ε（解析指纹）| 0.082 | 0.0822 | 0.19% |

<p align="center">
  <img src="docs/images/fig5_best_case_E2_showcase.png" width="600px" alt="PRX 2015 best-case showcase"/>
  <br><em>图 5 —— 最佳样例：slope=2/3 + τ 渐近 + KE 单调增长。</em>
</p>

<details>
<summary>更多 PRX 图（点开展开）</summary>

- `docs/images/fig1_multi_T0.png` —— 多 T₀ 轨迹
- `docs/images/fig2_multi_phi.png` —— 多 φ + n^(2/3) collapse
- `docs/images/fig7_E2_engine_diagnostics.png` —— 动量漂移 √t（牛顿第三破缺）
- `docs/images/fig8_damping_phase_diagram.png` —— 临界阻尼 ν_c 两侧的相变
- `docs/images/fig10_damping_ratio_invariance.png` —— T_A/T_B 与 ν 无关

</details>

### Ivlev 等，*Phys. Rev. Lett.* 100, 095003 (2008)

**各向异性 Yukawa 势，电流变复杂等离子体的链式形成。**

| 观测量 | 论文 | 复现 |
|------------|-------|------------|
| 链峰处 g_∥/g_⊥ 比值（MT=0.8）| > 2× | **5.33×** |
| 链距 r* | ≈ 4λ | 3.6 λ |
| 最佳 MT 区间 | [0.6, 0.9] | [0.7, 0.9]（Q-peak 单调）|
| ⟨L⟩ at MT=0.8（论文定性表述）| "形成链" | **5.15 个粒子，占系统 84%** |
| 声速极限失稳（MT→1）| 定性 | **MT=1.0 时 0 条链** |

<p align="center">
  <img src="docs/images/fig15_er_long_g_at_chain_peak.png" width="700px" alt="PRL 2008 chain signature"/>
  <br><em>图 15 —— 链峰时刻的 g_∥(r) 与 g_⊥(r)。ER4L (MT=0.8) 呈现教科书式链信号：r ≈ 3.6λ 处轴向主峰，横向相关被压制。</em>
</p>

<p align="center">
  <img src="docs/images/fig17_er_chain_length_dist.png" width="700px" alt="PRL 2008 chain length stats"/>
  <br><em>图 17 —— 链长分布。⟨L⟩ 在 MT=0.8 达峰，到声速极限 MT=1 崩溃。</em>
</p>

### Pedersen, Schrøder, Dyre，*Phys. Rev. Lett.* 120, 165501 (2018)

**Kob-Andersen 二元 Lennard-Jones 混合，结构与动力学验证。** 这次复现按设计是定性的：引擎没有 NPT，也没有 Frenkel-Ladd 自由能积分，所以论文的 NPT 共存线主结论（T_m = 1.028 @ ρ = 1.2）作为 out-of-scope 明文记录，campaign 转而瞄准 (T = {0.7, 1.0, 1.3}, ρ = 1.2) 等容线上的偏径向分布函数和分种类扩散系数。

| 观测量 | 论文 / 解析目标 | 复现 (T = 1.0, ρ = 1.2) |
|------------|--------------------------|-------------------------------|
| g_AA 第一峰 | σ_AA · 2^{1/6} ≈ 1.122 σ_AA | 1.094 σ_AA（偏低 2.5%）|
| g_AB 第一峰 | σ_AB · 2^{1/6} ≈ 0.898 σ_AA | 0.906 σ_AA（偏高 0.9%）|
| g_AB 峰位 < g_AA 峰位 | σ_AB < σ_AA 的严格序 | 三个温度均满足 |
| T_meas vs T_target（FD setpoint）| 后半轨迹 5% 内 | T = 1.3 时 0.27%、T = 1.0 时 0.78%、T = 0.7 时 0.80% |
| 扩散系数排序 D_B > D_A | σ_BB < σ_AA 的隐含结论 | 三个温度下 D_B / D_A ≈ 1.4 |

这次 campaign 是**八步力扩展**（`forces/kalj.py:KobAndersenLJ` + 分析器 / 绘图器 / 聚合器）与**九步积分器扩展**（`integrators/baoab_langevin.py:BAOABLangevin`）联合演练的标准范例。完整 design 走法在 `.claude/skills/paper-to-experiment/references/examples/worked_example_PRL2018_KALJ.md`。生成上面这些数字的配置在 `configs/plan_pedersen_kalj.json`；想要分钟级 smoke 试跑，看 `configs/examples/plan_pedersen_kalj_smoke.json`。

---

## 项目布局

```
agentic-md-for-dummies/
├── README.md / README_zh.md         本文件（英 / 中）
├── LICENSE                          MIT
├── requirements.txt
│
├── docs/
│   ├── ARCHITECTURE.md              四层 + 六阶段规范（约 400 行）
│   └── images/                      复现图（精选 8 张）
│
├── .claude/skills/
│   ├── paper-to-experiment/         驱动整个工作流的 AI skill
│   │   ├── SKILL.md                 七步配置流 + 八步扩展 + 硬规则
│   │   ├── templates/               physics_design.md / plan_config.schema.json
│   │   └── references/              force_types 注册表 + 已有论文 worked examples
│   └── creator/                     meta-skill（为另一个框架生成 paper-to-experiment
│                                     skill —— WIP）
│
├── configs/examples/                示例配置（PRX 历史版、ER、KA-LJ smoke）
│
├── tools/                           平台包（注册表分发）
│   ├── analyzers/{prx,er,pedersen}.py
│   ├── plotters/{prx,pedersen}.py
│   ├── aggregators/{prx,er,pedersen}.py
│   ├── lattices/{square_2d,triangular_2d,octagonal_2d,simple_cubic_3d}.py
│   ├── visualizers/taichi_traj.py
│   ├── registry.py                  名字 → 类 的全局查找
│   ├── runner.py / resources.py / file_io.py
│   ├── validate_manifest.py         运行后 §3.2 契约校验
│   └── migrate_manifests.py         为旧 manifest 回填规范字段
│
├── scripts/
│   ├── run_experiment.py            唯一入口
│   ├── validate_config.py           schema + 物理 + 预算门禁
│   └── analyze_er.py                ER 分析 CLI（chain / long / length）
│
├── prx_nonreciprocal_run.py         Layer 3 adapter —— PRX 2015
├── er_plasma_run.py                 Layer 3 adapter —— PRL 2008
├── pedersen_kalj_run.py             Layer 3 adapter —— PRL 2018
│
├── forces/                          Layer 1 —— 一文件一力类（HertzianNonreciprocal、ERPotential、LJ、KobAndersenLJ）
├── integrators/                     Layer 1 —— 一文件一积分方案（BAOABDrag、BAOABLangevin）
├── systemClass.py                   Layer 1 —— MD 编排
├── atomSystemClass.py               Layer 1 —— 粒子状态
├── searchBox.py                     Layer 1 —— cell-list / O(N²) 邻居表
├── constSet.py                      Layer 1 —— 单位（reduced / macro）
├── toolClass.py                     tools/ 拆分后的向后兼容 shim
│
└── tests/                           pytest 契约 + 回归测试
```

---

## 贡献

这是一个教学性框架——目标是**清晰胜过性能、可复现胜过特性数量**。欢迎 PR，特别是：

- 新论文复现（带配套示例配置 + adapter + 分析器）
- 新分析器 / 可视化 / 聚合器
- `ARCHITECTURE.md` 中的解释性图与文档

不太欢迎：

- 替代积分器 / 加速器（Layer 1 内核刻意冻结）
- 巨大的抽象层 —— 简洁本身就是特性

为新论文开 PR 时：

1. 把配置加到 `configs/examples/`
2. 论文若需要新力，遵循 `force_types.md §4` 的八步扩展流程
3. 在 `tests/` 下加测试
4. 在 `docs/images/` 下加 1-2 张复现图，并在示例配置的 `_design_doc` 字段中引用它们

---

## 参考文献

- Ivlev, A. V. *et al.* "Statistical mechanics where Newton's third law is broken." *Phys. Rev. X* **5**, 011035 (2015). [DOI:10.1103/PhysRevX.5.011035](https://doi.org/10.1103/PhysRevX.5.011035)
- Ivlev, A. V. *et al.* "First Observation of Electrorheological Plasmas." *Phys. Rev. Lett.* **100**, 095003 (2008). [DOI:10.1103/PhysRevLett.100.095003](https://doi.org/10.1103/PhysRevLett.100.095003)
- Pedersen, U. R., Schrøder, T. B., Dyre, J. C. "Phase Diagram of Kob-Andersen-Type Binary Lennard-Jones Mixtures." *Phys. Rev. Lett.* **120**, 165501 (2018). [DOI:10.1103/PhysRevLett.120.165501](https://doi.org/10.1103/PhysRevLett.120.165501)
- Hu, Y. *et al.* "Taichi: a Language for High-Performance Computation on Spatially Sparse Data Structures." *ACM Trans. Graph.* **38**, 6 (2019). 驱动 Layer 1 的 Taichi 编译器。

---

## License

MIT —— 见 [`LICENSE`](LICENSE)。

如果你在已发表的工作里用了这个框架，欢迎引用本框架但非必需；引用上面列出的物理原文是必需的。
