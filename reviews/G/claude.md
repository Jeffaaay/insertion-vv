我先自己克隆仓库核对这 5 个问题，再给启动审阅。

# G 启动审阅（Claude）

**核验范围：** 我独立克隆了公开仓库，HEAD = `e8cb4ee7ac1420c945dbcb2ba86adfe1afa63338`，只读了源码，没有运行任何仿真。下面的结论都基于我自己读到的代码，不依赖你的摘要。

## 一、你的 5 条：全部核实成立

1. **F5 注入层错了。** `PROJECT_BRIEF.md` §7 明确 F5 是 plant 参数。真实组织运动由 `sim/config.py:104 tissue_target()` 生成，`sim/plant.py:85` 每个 physics tick 都调用它。只改传感器，测到的就是"传感器欺骗"，不是心率漂移。交接里"其余在传感器模型层"这句是我写交接时加的，写错了，以 brief 为准。
2. **F5 和注入时刻有冲突。** 固定 2–5 s 的 ramp 与 {0.2, 1.5, 2.4, 5.0} s 注入在语义上冲突。
3. **几处定义缺失。**
   - F1/F6 的"连续 N tick"与 300 ms 持续时间冲突。
   - seed 没有给具体值。
   - F7 的"标称峰值力"在全仓库都没有定义（grep 不到任何力限幅）。
   - 图 4 用哪个档位没有指定。
4. **多数消融是空操作。** `sim/config.py:29-30` 中噪声和丢帧默认都是 0，`sim/sensors.py` 只有采样、固定延迟、噪声、丢帧四项，没有 jitter 和量化。所以 no-noise 和 no-dropped-frame-model 在基线上是恒等变换，no-jitter-model 和 no-quantization 在基线里没有对应项。
5. **规模计算正确。** 单控制器、单消融 308 run 的算法没错。

## 二、我额外发现的（按严重度）

**N1【阻塞】no-delay 消融对 preview 是退化的。**
`sim/preview.py:69` 要求 `sampled + self.delay_us <= sensors.time_us`，而估计器的 `delay_us` 被 `Config.validate` 固定为 15 ms。把传感延迟设成 0 后，每帧到达时 `sampled == time_us`，全部被拒收，estimator 一直返回 (0, 0)，preview 等于瞎了。结果是所有格子结构性 FAIL，预测 5 会因为这个 guard 而"成立"，不能作为"延迟建模必要"的证据。

**N2【解释】F3 下早到的帧会被 preview 永久丢弃。**
原因同上：延迟不足 15 ms 的帧在到达那个 tick 被拒收，之后 `fresh` 不再为真。所以对 preview 来说，F3 实际上是"抖动 + 部分丢帧"。这是冻结控制器的真实行为，不需要改设计，但报告解释 F3 时必须写出来。

**N3【阻塞】F1 的语义必须先定。**
`sim/controllers.py:49` 和 `sim/preview.py:71` 都会拒收序号不递增的帧：
- 如果"原样重发旧帧"，控制器会直接忽略，等价于短时丢帧。
- 如果"值冻结、序号和采样时间照常递增"，才是欺骗控制器。

两种结果会完全不同。

**N4【信息】计分窗口是 3.0–8.0 s**（`sim/verdict_contract.json:6`）。
在 0.2、1.5、2.4 s 注入的 300 ms 内瞬态故障，都在计分开始前就结束了，只能通过残留影响导致 FAIL。不需要改预测，但报告必须说明。

**其他代码事实（用于定实现约定）：**
- `sim/config.py:63` 只允许采样率 ∈ {25, 1000}，所以 F4 必须在注入层做降采样，不能改 cfg。
- `tissue_target` 用的是 `sin(2πft)` 加绝对时间。直接把 f 换成 f(t)，瞬时频率会变成 f + t·f′，所以 F5 必须对相位积分。
- `sim/controllers.py:90` 的观测器每次调用固定按 1 ms 推进。F6 跳 tick 会让它的预测落后，这是 F6 要测的真实行为。
- `sim/run.py` 每个 run 都会跑两遍做复现校验（verdict 要求 `require_verified_reproducibility`），所以确定性复跑已经内置了。

## 三、M0 前可直接补充的实现约定

这些写进 `C1_PREREG.md` 的"实现约定"一节，不改任何预测和阈值。

- **Seed：** F2/F3 用 {42, 43, 44, 45, 46}。注入器用独立的 RNG（`SeedSequence([seed, fault_index])`），不消耗 Phase A 传感器的 RNG，保证无故障 run 的 trace 逐 bit 不变。
- **F3：** 延迟 = 15 ms + N(0, σ)，四舍五入到整 tick，截到 ≥ 0。按 FIFO 投递（投递时间不递减），按采样时间判断是否落在窗口内。σ = 0.5 ms 时受 tick 量化影响很大，报告里要注明。
- **F4：** 从注入时刻起只保留采样时间是周期整数倍的帧，其余不投递。M1 加一项对照：从 t=0 开始注入 F4@25 Hz，与现有 Phase A 25 Hz 路径对比，除序号编号外应一致。
- **F5：** 在新模块里写 plant 子类实现，不改冻结文件。
  - φ(t) = 2π∫f dt，二次谐波用 2φ，呼吸分量不变。
  - ramp 开始前直接调用原来的 `tissue_target`，保证前缀逐 bit 一致。
  - Rust 路径的 plant 来自 `harness/plant_server.py`（`MujocoPlant`），所以只需实现一次，两条路径共用。
- **F6：** 跳过的 tick 不调用 `controller.command`，保持上一条指令。跳过期间到达的帧采用 latest-wins mailbox：恢复的那个 tick，如果期间有帧到达，就交付最新一帧并标记 `fresh`。
- **F7：** 限幅 = p% × 同一控制器、同一消融、seed 42 的无故障 run 在全 8 s 内的 max|force|，对称限幅。这个峰值在 M2 里、跑 F7 之前算出。100% 档必须与无故障 run 逐 bit 相同。
- **F8：** q(x) = clamp(round(x/LSB)·LSB)，LSB = 2 mm / 2^bits：

  | 位数 | LSB |
  |---|---|
  | 10 bit | 1.953 µm |
  | 12 bit | 0.488 µm |
  | 16 bit | 30.5 nm |
  | 24 bit | 0.119 nm |

- **图 4 档位规则：** 每种故障取 preview 在 baseline 消融、2.4 s 注入下的 flip-point 档位；没有翻转就取最重档。
- **精确矩阵（按第四节批准的版本）：**
  - 每个控制器 × 每个消融：F1 24 + F2 100 + F3 100 + F4 20 + F5 4 + F6 16 + F7 16 + F8 16 + 无故障 1 = **297**
  - preview × 6 个消融 = 1782
  - c32 = 297
  - 图 4 另外 3 个控制器共 51
  - 合计 **2130 run**，每个 run 内部跑两遍
- **记录方式：** `REVIEW_PROTOCOL.md` 写明，当前的审阅传递方式是用户指定的"聊天中转"，CLI 方案作废。我每次的回复原文存到 `reviews/<M>/claude.md`。

## 四、必须由用户决定：最小修正文案（可直接批准）

```
【C1 注册修正 v1 — 用户批准后写入 C1_PREREG.md】
1. F5 注入层 = plant（组织运动），与 PROJECT_BRIEF §7 一致。F5 固定为 2.0–5.0 s 线性 ramp，之后保持目标频率到 8 s；注入时刻轴对 F5 不适用（每档 1 个 run）。
2. 时间定义：F1、F6 = 从注入时刻起的单次连续 N tick；F2、F3 = 从注入时刻起的 300 ms 窗口；F4、F7、F8 从注入时刻起持续到 8 s。
3. F1 = 传感器卡死：帧照常到达、序号和采样时间照常递增，但 surface 值冻结在起点的值。
4. 消融 = 关掉 sim 对该机制的建模，包括标称项和对应的注入故障：no-delay → 标称延迟 0（F3 抖动围绕 0，截到 ≥0）；no-jitter-model → F3 无效；no-quantization → F8 无效；no-dropped-frame-model → F2 无效；no-noise → 无变化。被测控制器不变。按构造应与无故障相同的格子，必须逐 bit 相同。
5. 预测 5 原文不改，加注：preview 拒收采样后不满 15 ms 到达的帧（sim/preview.py:69），因此 no-delay 下 preview 收不到任何测量、结构性全部 FAIL；本条结果不作为"延迟建模必要"的证据。
6. preview_c32 只跑 baseline 消融的完整矩阵（297 run）。
7. F8 只量化 surface 测量，不量化 needle encoder。
```

可选（不在最小修正里，默认不做）：如果想让 no-delay 消融有信息量，可以额外把 `delayed_feedback_offsetfree` 作为第二个消融对象。它的 guard 是 `sampled <= time_us`，不会因为延迟为 0 而变瞎。

## 五、对 G 的结论

这些问题只阻塞 M0，不阻塞 G。G 可以照常做：保存原始 handoff、搭记录机制。**用户批准第四节之前，不要提交 `C1_PREREG.md`。** 这份审阅只是咨询意见，不等于用户批准。

```json
{
  "verdict": "ESCALATE",
  "issues": [
    {"severity": "blocker", "where": "HANDOFF §5.1-5.2 注入点表; PROJECT_BRIEF.md §7; sim/config.py:104; sim/plant.py:85", "what": "F5 必须在 plant 层注入（交接里的注入点表写错了）；固定 2–5 s ramp 与注入时刻轴冲突", "touches_frozen_or_registered": true},
    {"severity": "blocker", "where": "sim/preview.py:69; HANDOFF §5.4, §5.6", "what": "no-delay 下 preview 拒收全部帧、结构性 FAIL；预测 5 因 guard 而成立，不能作为证据", "touches_frozen_or_registered": true},
    {"severity": "blocker", "where": "sim/config.py:29-30; sim/sensors.py; HANDOFF §5.4", "what": "消融语义未定义；基线没有噪声/丢帧/抖动/量化项，4 个消融在当前定义下是恒等变换", "touches_frozen_or_registered": true},
    {"severity": "blocker", "where": "sim/controllers.py:49; sim/preview.py:71; HANDOFF §5.1 F1", "what": "F1 是'原样重发'还是'值冻结、元数据递增'：前者被序号 guard 拒收，等价于丢帧", "touches_frozen_or_registered": true},
    {"severity": "blocker", "where": "HANDOFF §5.2", "what": "F1/F6 的 N tick 与 300 ms 持续时间冲突；持续性故障的起止时间未定义", "touches_frozen_or_registered": true},
    {"severity": "minor", "where": "HANDOFF §5.5", "what": "preview_c32 '完整矩阵'的范围不明确，建议只跑 baseline 消融（297 run）", "touches_frozen_or_registered": true},
    {"severity": "minor", "where": "HANDOFF §5.1 F8", "what": "量化对象不明确，建议只量化 surface 测量", "touches_frozen_or_registered": true},
    {"severity": "minor", "where": "全仓库无力限幅定义; HANDOFF §5.1 F7", "what": "标称峰值力未定义，按程序化规则定义：同控制器、同消融、无故障 run 的 max|force|", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "HANDOFF §5.3, §5.5", "what": "seed 具体值和图 4 档位未指定，按实现约定补充", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "sim/config.py:63", "what": "Config 只允许 25/1000 Hz，F4 必须在注入层降采样，并与 Phase A 25 Hz 路径对照", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "sim/preview.py:69", "what": "F3 下早到的帧被 preview 永久丢弃（真实行为），报告必须解释", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "sim/verdict_contract.json:6", "what": "计分窗口 3.0–8.0 s，0.2/1.5/2.4 s 的瞬态注入在计分前结束，只能通过残留影响 FAIL", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "HANDOFF §10", "what": "按修正后的精确矩阵为 2130 run（每个 run 内部双跑），替换原来 600–1300 的估计", "touches_frozen_or_registered": false}
  ]
}
```
