# Insertion Verification Stack — Project Brief

**Owner:** Jeff Young  
**Status:** Phase 0 (not started). This brief is the single source of truth for scope; update it before changing scope.  
**Audience:** 给人读，也给执行 agent（Codex 等）读。Agent 只做本文件明确授权的事。

---

## 0. 一句话

搭一个缩小版"手术机器人验证栈"：MuJoCo 里的 1 轴插入 + 脉动组织 → 控制器跑在 STM32 真固件上（sim 当 plant）→ 注入真实时序故障 → 回答一个问题：

> **在移动目标插入任务上，sim 给出的 PASS/FAIL 在哪些 fault 类别下能代表真固件？缺哪项建模就会漏 bug？**

这不是控制算法项目。控制器只需要"够用"，重点是 **可复现、fault injection、sim-vs-HIL 判定一致性、CI**。

---

## 1. 为什么做这个

**目标岗位的痛点（Neuralink HIL / Simulation JD 原文）：**
- "When a failure escapes sim or HIL, you reproduce it and close the coverage gap."
- "Reproduce hardware failures in sim to accelerate our test timelines."
- "Make runs deterministic, measurable, and cheap enough to run in CI."
- 技术栈：Rust（核心）、Python（工具）、Bazel（加分）、MuJoCo/Isaac/Gazebo 任一。

**为什么稀有故障是核心：** 一台手术 500 根线，每根异常率 0.1% → 至少一次异常 = 1 − 0.999^500 ≈ 39%。要把手术级异常率压到 1%，每根要 ≤ 1/50,000；用 rule of three，证明这个数字需要约 150,000 次零失败插入。人工做不到，只能 sim 每 commit 跑 + HIL 日夜跑。**难点是可靠性分母，不是单次精度。**

**Baseline 论文：** arXiv 2608.08860（Cao, 2026-08），"Preview-Based Relative-Motion Control of an Insertion Tool for Neural-Thread Placement in Pulsating Tissue"。MuJoCo 3.8，1 轴针 + 脉动表面，MPC 控制器。**Simulation-only**，作者明确写了真实时序、嵌入式实现、执行器动力学是未来工作。它回答"怎么控"，本项目回答"真固件上能不能信"。

---

## 2. 研究问题（精确版）

**主问题（Phase C 回答）：**  
对一组定义好的 fault（§7），sim-only 的判定 V_sim 和 HIL 的判定 V_hil 是否一致？不一致时，缺的是哪一项建模（延迟分布、jitter、deadline miss、量化、总线时序）？

**副问题：**
1. 论文的 1.9 µm 接触误差，在真实 1 kHz 固件 jitter 下变成多少？（论文的 1 ms 控制周期本身就贡献 ≈ 1.5 µm，见 §3）
2. 传感降到 25 Hz + 心率漂移时，预测器从什么条件开始"帮倒忙"？固件能否实时检测？

**明确不做：**
- 不改进 MPC / 控制理论本身
- 不做柔性线、组织切割、真实组织力学
- 不做 3 轴/机械臂（Phase D 可选）
- 不追求真实 µm 级物理测量（Phase 1–3 用 sim plant 当真值）

---

## 3. 单位与数量级（读论文必备）

| 量 | 值 | 来源 |
|---|---|---|
| 心跳频率 f_c | 1.2 Hz（72 bpm） | 论文 Table III |
| 心跳振幅 A_c | 200 µm（真实测量约 30–40 µm，论文故意放大） | 论文 Table III |
| 二次谐波 | 60 µm @ 2.4 Hz | 论文 |
| 呼吸 f_r / A_r | 0.25 Hz / 300 µm | 论文 |
| 组织峰值速度 | 2π·f·A ≈ 2π·1.2·200 µm ≈ **1.5 mm/s** | 推导 |
| 传感延迟 τ | 15 ms | 论文 |
| 控制周期 | 1 ms（1 kHz） | 论文 |
| 针尖等效质量 m | 1 g | 论文 |
| 组织刚度 K_env | ≈ 16 N/m | 论文 |
| 插入深度 | 0.3 mm；悬停高度 0.5 mm | 论文 |
| Spec | e < 20 µm，ė < 2 mm/s | 论文 |
| 论文结果（1-DOF） | lab-frame PD 286.1/275.5 µm；delayed-feedback 18.3/176.8 µm；preview MPC 12.0/1.9 µm（free/contact RMS） | 论文 Table IV |

**核心估算公式：误差 ≈ 组织速度 × 看不见的时间。** 1 ms → 1.5 µm；15 ms → 22 µm；40 ms（25 Hz 采样）→ 60 µm。

---

## 4. 架构

```
改一行控制/固件代码
  │
  ├─ Phase A  SIL：控制器 + MuJoCo 同一进程，lockstep，同平台 bitwise；跨平台容差比较
  │
  ├─ Phase B  HIL：控制器在 STM32（Nucleo-H723ZG），MuJoCo 在 PC 当 plant，
  │           UART/CAN lockstep；真实 jitter/延迟/量化，plant 真值仍免费
  │
  └─ Phase C  Fault injection 两边都做 → 判定一致性矩阵 → 一个真实 escape 的
              复现→补模型→关闭 案例
```

**Plant interface（Rust trait，所有 backend 实现同一接口）：**
```rust
trait Plant {
    fn reset(&mut self, seed: u64);
    fn step(&mut self, cmd: Command, dt_us: u32) -> Sensors; // sim: mj_step; hil: 通过串口和板子交换
    fn truth(&self) -> Truth;                                 // 仅评估用，控制器永远拿不到
}
```
控制器只看 `Sensors`（带延迟、降采样、噪声、可能缺帧），评估只看 `Truth`。两者在代码上硬隔离（参考 AIC 的 GT-blind 做法）。

---

## 5. Phase A 规格（SIL，Python 起步，harness 逐步换 Rust）

**Plant（MuJoCo MJCF）：**
- `needle`：1 个 slide joint（z），motor actuator，质量 1 g 等效
- `tissue`：1 个 slide joint（z），由高刚度位置伺服驱动到 d(t) = A_c·sin(2π f_c t) + A_2c·sin(2π·2f_c t + φ) + A_r·sin(2π f_r t)
- 接触：MuJoCo 软接触，调到 ≈ 16 N/m（记录 solref/solimp 和实测的准静态刚度）
- timestep 1 ms（或更小，由 harness 决定 control tick）

**Task timeline（照论文）：** 0–1 s 平滑接近；1–2 s 悬停 0.5 mm（free-space 窗口）；2–2.5 s ramp 到 0.3 mm penetration；2.5–8 s hold（3–8 s 为 contact 窗口）。

**Controllers（A 阶段只做前两个）：**
1. `lab_frame_pd`：固定 lab-frame setpoint，忽略 d(t)
2. `delayed_feedback`：跟踪延迟 15 ms 的测量表面，无预测
3. `preview`（Phase A 末或 B）：简化版预测（Kalman/exosystem + 简单 MPC 或 LQR）。**只要够用，不追求论文精度**

**Sensors 模型（控制器能看到的）：** 延迟 τ=15 ms，可配置采样率（1 kHz / 25 Hz），可配置高斯噪声，可配置缺帧。

**Metrics（每次 run 输出 JSON）：** free/contact RMS e、peak ė（用 plant 真实速度）、peak F_contact、每 tick 的 wall-time（后面给 HIL 对比用）。

**Verdict contract（PASS/FAIL 的定义，先定后跑）：**
- PASS：contact-window RMS e < 20 µm AND peak |ė| < 2 mm/s AND 无 safety stop
- FAIL：任一不满足
- INVALID：run 没跑完 / 数据缺失（不能当 FAIL 算）

**Acceptance criteria（Phase A 结束的硬门槛）：**
- [ ] `lab_frame_pd` 复现到论文量级（contact RMS ≈ 250–300 µm）
- [ ] `delayed_feedback` free-space RMS 在 20 µm 附近（15–25 µm），primary contact RMS 150–200 µm
- [ ] 同平台确定性：同 source/config/seed、OS/arch/Python/MuJoCo/NumPy 版本，trace 与 truth SHA-256 完全一致（CI 强制）；每个 run 记录平台指纹
- [ ] 跨平台确定性：Linux/Windows 的位置 |Δ| <1e-12 m、速度 <1e-9 m/s、力 <1e-12 N；时间/离散状态及 verdict 完全一致；物理指标相对差 <1e-9（CI 独立 job）
- [ ] 相对差定义为 |a-b|/max(|a|,|b|)，两者均零取零；不比较 wall-time/UUID。损坏、缺失、不完整的产物不能通过比较
- [ ] GitHub Actions：每 push 在 Linux 和 Windows 跑两个 controller × 两种 contact config，上传 metrics JSON、trace 及跨平台比较报告；报告数值以 Linux runner 为准
- [ ] 无 GUI 依赖，headless 可跑

---

## 6. Phase B 规格（HIL，摘要）

- 板子：STM32H723ZG（Nucleo）。控制环在板上 1 kHz（TIM 中断），接收 `Sensors` 帧，发送 `Command` 帧
- 链路：USART @ 460800（起步）或 CAN-FD；每帧带 tick 序号 + 板端时间戳（DWT cycle counter）
- Lockstep：PC 侧 harness 每 tick 发 sensors → 等板子 cmd → mj_step；板上另有"自由跑"模式用来量真实 jitter
- 记录：板端每 tick 的中断进入/退出时间、是否 deadline miss、收发延迟
- Acceptance：同一控制器、同一 seed，HIL 与 SIL 的 trace 在"无故障"下差异 < 定义的 ε；量出 jitter 分布（p50/p95/max）

---

## 7. Fault catalog（Phase C，现在先定好）

| ID | Fault | sim 注入方式 | HIL 注入方式 |
|---|---|---|---|
| F1 | 传感帧冻结（stale） | 重复上一帧 N tick | PC 重发旧帧 |
| F2 | 传感帧丢失 | 跳帧 | 不发帧 |
| F3 | 延迟抖动 | τ ~ 分布 | PC 侧延迟发送 |
| F4 | 采样率降到 25 Hz | 降采样 | 同 |
| F5 | 心率漂移 1.2→1.6 Hz | plant 参数 | 同 |
| F6 | 控制 tick 错过 deadline | 人为跳 tick | 板上插入忙等 / 高优先级中断 |
| F7 | 执行器饱和 | 限幅 | 同 |
| F8 | 量化/定点误差 | 模拟 | 板上真实发生 |
| F9 | 串口帧损坏（CRC fail） | N/A（sim 无总线） | 真实注入 |
| F10 | 时钟漂移（板子 vs PC） | N/A | 真实发生 |

F9/F10 在 sim 里"不存在"，这正是预期会出现判定不一致的地方。

**输出物：** 10 × 2 的矩阵（fault × {SIL, HIL}）→ 判定；再逐项关掉 sim 里的建模（延迟模型、jitter 模型、量化）看从哪一项开始漏判。

---

## 8. Repo 布局（建议）

```
insertion-vv/
  README.md             # 一页：问题、结果表、怎么跑
  PROJECT_BRIEF.md      # 本文件
  sim/                  # MJCF + Python 工具（Phase A 起步）
  harness/              # Rust：Plant trait、sim backend、serial backend、runner、metrics
  firmware/             # STM32 控制环（C 起步；时间允许再评估 Rust embedded）
  faults/               # fault 定义（YAML/JSON），sim 与 HIL 共用
  tests/                # 确定性测试、verdict 测试、regression
  .github/workflows/    # CI
  docs/                 # writeup、结果表、决策日志
```

---

## 9. 执行纪律（从 AIC 继承）

- 一次只改一个变量；不改代码跑最多 3 次；3 次失败做一次整体对比，不逐次打补丁
- 控制器 **永远** 拿不到 `Truth`；用自动化测试证明有/无 truth 文件输出 bitwise 相同
- 每个 run 有 run id、seed、git SHA、source/config hash，以及 OS、arch、Python、MuJoCo、NumPy 版本的平台指纹
- 同平台同 source/config/seed 必须 bitwise 可复现；否则 run = INVALID，不算任务 FAIL。历史 SHA 只约束相同平台指纹
- 跨平台按 §5 预注册的 SI 容差和相同 verdict 比较，不要求 SHA 相同；不可比或损坏的产物 = INVALID，超容差/verdict 不同则跨平台 CI 失败，保留原 run 的任务判定
- 不修改 sin()、不舍入 trace 来掩盖最后一位差异；Linux runner 是报告数值的标准平台
- Phase B 单精度约 1e-7 是相对精度量级而非固定米数或已测 HIL 误差；复用容差层，但 HIL 容差需按单位和误差预算预注册，不能直接放宽当前 SIL contract
- 不用 magic constant 修 PASS/FAIL；阈值在 verdict contract 里注册后才能用
- 先定 verdict，再跑实验

---

## 10. 时间线（目标 6–8 周）

| 周 | 内容 |
|---|---|
| 0 | 本 brief；Rust 基础（ownership / Result / trait / serial） |
| 1–2 | Phase A：MJCF、两个 baseline、metrics、确定性测试、CI |
| 2–3 | 简化 preview 控制器；Rust harness 替换 Python runner |
| 3–5 | Phase B：固件、串口协议、lockstep、jitter 测量 |
| 5–7 | Phase C：fault catalog 两边跑、一致性矩阵、一个 escape 案例 |
| 7–8 | writeup + README；可选 Phase D（flex 组织 / 3 轴 / Menagerie 臂） |

---

## 11. 决策日志

- 2026-10-12：选 MuJoCo 而非 Gazebo —— 需要"时钟在我手里"（mj_step 手动步进，同平台 bitwise 确定性，pip 可装进 CI）。Gazebo 经验保留为对比 backend 的候选。
- 2026-10-12：先不做真实机械轴；Phase 1–3 用 sim plant 当真值，重点是时序。
- 2026-10-12：不重做 AIC；AIC 只贡献方法论和简历故事。

---

## 12. Sources

- arXiv 2608.08860 — https://arxiv.org/html/2608.08860v1
- Neuralink JD, Software Engineer – HIL — https://job-boards.greenhouse.io/neuralink/jobs/8005730003
- Neuralink JD, Software Engineer – Simulation — https://job-boards.greenhouse.io/neuralink/jobs/8005762003
- MuJoCo Menagerie — https://github.com/google-deepmind/mujoco_menagerie
- rusty_mujoco — https://docs.rs/crate/rusty_mujoco
- mujoco_ros2_control (ros-controls) — https://github.com/ros-controls/mujoco_ros2_control

---

## 13. Local execution checkpoint (2026-10-12)

User-authorized scope for this checkpoint: Phase A plant and `lab_frame_pd` only.
Do not implement another controller until the same-seed trace SHA-256 determinism
test passes in hosted CI. Local verification runs the same commands as the written
GitHub Actions workflow; it is not represented as a hosted CI pass.

The user will create public `github.com/Jeffaaay/insertion-vv` and add the remote.
No GitHub repository creation or push is authorized in this checkpoint.
See `docs/model-and-evaluation.md` for explicit modeling choices and measured results.
The original brief above is preserved; Phase A overall acceptance is still pending.

## 14. Contact-profile decision (2026-10-12)

Phase A targets paper-magnitude baselines with documented deviations, not bit-exact
paper replication. Tissue servo gains are aligned to v1 Appendix B-B (8000/120),
and the needle tip is a capsule. The primary contact remains measured 16 N/m.
A `paper_effective` diagnostic targets measured 3.5 N/m by changing only the contact
stiffness term; no further parameter tuning is authorized after its result.

The prior 6.52 mN primary-force stop condition is resolved by this user decision.
The diagnostic's expected 2–4 mN peak force is a hypothesis to report, not a reason
to fit parameters or change the task verdict. Both profiles belong in local CI.
`docs/REPLICATION_NOTES.md` records the version-specific paper evidence and differences.
This checkpoint stops after reporting local CI; no delayed_feedback, GitHub repository
creation, remote addition, or push is authorized.

## 15. Hosted gate and delayed-feedback authorization (2026-10-12)

The user now authorizes public repository creation, remote setup, commit and push.
The public remote is https://github.com/Jeffaaay/insertion-vv, branch `main`.
Hosted run 38309462614 at commit 24e4dd4 passed all 43 tests. Downloaded trace files
reproduce both full local hashes (primary 66422ccb..., paper_effective cc7e3e7e...).
This satisfies the hosted determinism gate; it does not claim determinism on all CPUs.

Implement `delayed_feedback` only: delayed measured position plus a filtered measured
surface velocity, without prediction, integral action or contact-force compensation.
Before the first experiment, select finite impedance gains kp=10 N/m and
kd=0.2 N s/m (critical damping for the 1 g free axis), and a 5 ms backward-Euler
velocity-filter time constant. These are documented implementation choices, not
recovered author settings. Keep both plants and the lab-frame PD unchanged.
Define "near 20 um" as 15–25 um free-window RMS; primary contact RMS must be
150–200 um. Register these reproduction checks before running. They are distinct
from the unchanged task PASS contract (<20 um contact RMS and <2 mm/s velocity).
Run seed 42 for both controllers and contact profiles in local and hosted CI;
preserve the known lab-frame trace hashes as platform-scoped regression gates.

## 16. Two-tier determinism decision (2026-10-12; supersedes cross-OS SHA gate)

Linux run 38315698883 passed the original 43 tests and both same-seed repeats, but
its trace hashes differed from Windows by last-ulp floating-point differences.
The first received surface difference was at 0.351 s: 2.710505431213761e-20 m.
The user accepts this platform libm behavior; do not patch sin() or require cross-OS
bitwise equivalence. Apply the two-tier contract in §5 and §9, document both
findings, and use Linux as the canonical reporting platform. Run full CI on Linux
and Windows plus the cross-platform comparison. Commit/push are authorized.
After this gate, verify the existing delayed_feedback implementation on both contact
profiles with seed 42 and regenerate its optional plot/video from Linux artifacts.
Preview, firmware and Phase B implementation remain outside this authorization.
