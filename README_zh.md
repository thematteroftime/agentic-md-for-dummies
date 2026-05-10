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

完整架构规范见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

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
├── ARCHITECTURE.md                  四层 + 六阶段规范（约 400 行）
├── LICENSE                          MIT
├── requirements.txt
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
├── tests/                           pytest 契约 + 回归测试
└── docs/images/                     复现图（精选 8 张）
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
