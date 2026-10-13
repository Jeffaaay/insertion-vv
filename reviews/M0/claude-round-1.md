# G 复核 + M0 审阅（Claude，第 3 轮）

**核验范围：** 我独立读了 `dcd86f5` 的 `C1_PREREG.md`、`round-2.md`、`review_gate.py`、`phase-c.yml`，并核对了 `controller.c` 和 `h723/main.c`。我用 `random.Random(1000·fault+seed)` 独立重算了 `faults/random-v1.json`：F2 seed 42 的 300 个 uint32 完全一致，F3 五档 σ 在 base=15 下也完全一致（含 ties-even，σ=10 的范围是 0–47）。没有运行任何仿真。

**G：通过。** 104 个基线文件全部冻结、缺失文件会明确报错、死代码已删、CI 会检查 review 页是否最新，这几项都已落实。

你们的两处更正我接受：
- no-noise 应该对照**同一故障**的 baseline 结果，我上一轮写成"对照无故障"是错的。
- 我的 15 GB 是未压缩的估算。gzip 后约 3.6 GiB，完整保留在本地是可行的，M3 维持只读即可。

## M0 剩余缺陷

**1.【阻塞】F1 差一位（off-by-one）。**
现在写的是"在 onset 冻结当前捕获值"，窗口是 [onset, onset+N)。问题在于 onset 那一帧本来就等于它自己的值，所以：
- N=1 按构造就是恒等，第一档 F1 实际上没有注入任何故障；
- 其余每一档实际只有 N−1 帧是旧值。

P3 的判定（≥60 tick）正好依赖这个档位定义。

修法：冻结值改为 **onset 之前最后一次捕获的值**（即 onset−1 tick 的捕获），窗口 [onset, onset+N) 内 N 帧全部携带这个值。M1 的边界测试里加一条断言：N=1 不是恒等，且只有第 onset 帧的值被替换。这是在任何 run 之前的前瞻性修正，补一个 commit 即可，不需要重写注册。

**2.【次要】F6 那句解释和你们自己的规则矛盾。**
`C1_PREREG.md` 写着"F3/F6 can deliver older frames even at base=0"，但 `round-2.md` 已经说了"No F6 old-frame claim"。实际情况是：在注册的 1 kHz 调度下，无论 base=15（t ≥ 15 ms 后）还是 base=0，每个 tick 都有一帧新的 fresh 帧，所以 latest-wins mailbox 在整个矩阵里**从来不会被触发**。F6 的真实语义是"跳过期间的帧丢失，恢复时用当前帧"。

修法：把这句改成"F3 可以；F6 的 mailbox 在本矩阵的调度下不会被触发"。

**3.【次要】P5 的平局还没定义算不算成立。**
现在只写了"report ties"。

修法：写死规则，比如"no-delay 严格最大才算成立；并列最大记为'不成立（共享最大）'"。同时写明 no-fault 行是否计入翻转数。

**4.【次要，但关系到项目结论】C32 的 F6 会按构造产生 96 个 INVALID。**
16 个格子 × 6 种消融，全部会因为 `controller.c:150` 拒绝跳号而无效。你们的处理（照跑、记 INVALID、单独醒目报告）是对的。建议再注册一句预期：

> 在 replay 固件路径里，`tim6_body` 每个 UIF 处理一个连续 tick。overrun 表现为 ISR 晚执行，而 C 核心拒绝跳号，所以 HIL 上的 deadline miss 大概率是"晚执行、tick 号连续"，而不是 Python 模拟的"跳过并保持指令"。

这样 Python F6 和 HIL F6 预期就是两种不同的失效语义，是事先就能写下的一个 sim/HIL 分歧点。另外，c32 与 preview 的一致率统计要把 F6 从分母里拿出来单独报告。

**5.【次要，M1 规划】冻结全部 104 个文件后，Rust 侧无法在原 crate 里加模块。**
`harness/src/lib.rs` 和 `harness/Cargo.toml` 都被冻结，`mod fault;` 加不进去。M1 的 Rust FaultInjector 需要放在一个新 crate 里，通过 path 依赖 `../harness`，并配自己的 `Cargo.toml` 和 `Cargo.lock`。同理，Python 侧放新包。另外，冻结的 `faults/README.md` 里"没有 Phase C 实现"这句会过时，在新文档里注明即可，不要改它。

其余注册内容我逐条核过，没有发现影响正确性的问题：F5 相位积分公式正确且连续；F3 用 FIFO 加预生成表，绕开了跨语言 libm 差异；F4 的除数都是整数；F7 的 100% 档是恒等；F8 用有符号码加饱和；恒等格子是对同 seed 的 nominal 做对照；聚合规则和 P1–P4 的量词都已经定死。

```json
{
  "verdict": "BLOCK",
  "issues": [
    {"severity": "blocker", "where": "docs/C1_PREREG.md Injection semantics F1", "what": "冻结 onset 当前捕获值导致 N=1 恒等、各档实际只有 N−1 帧旧值；改为冻结 onset 之前最后一次捕获的值，[onset,onset+N) 内 N 帧全部携带该值，并在 M1 测试 N=1 不是恒等", "touches_frozen_or_registered": true},
    {"severity": "minor", "where": "docs/C1_PREREG.md Ablations and interpretation", "what": "'F3/F6 can deliver older frames at base=0' 中 F6 部分错误：1 kHz 下每个 tick 都有 fresh 帧，mailbox 在本矩阵中从不触发；与 round-2 的说法矛盾，需改正", "touches_frozen_or_registered": true},
    {"severity": "minor", "where": "docs/C1_PREREG.md P5", "what": "定义平局是否算成立（建议严格最大才算），并写明 no-fault 行是否计入翻转数", "touches_frozen_or_registered": true},
    {"severity": "minor", "where": "docs/C1_PREREG.md Frozen C32 tick-gap boundary; firmware/h723/main.c tim6_body; firmware/ctrl/controller.c:150", "what": "C32 F6 按构造产生 96 个 INVALID；注册预期：HIL 上的 miss 大概率是晚执行、tick 连续，与 Python 的跳过语义不同；c32/preview 一致率统计中 F6 单独报告", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "M1 规划: harness/src/lib.rs, harness/Cargo.toml（已冻结）", "what": "Rust FaultInjector 需放在新 crate 中，通过 path 依赖 harness；冻结的 faults/README.md 会过时，在新文档中说明，不要修改", "touches_frozen_or_registered": false}
  ]
}
```
