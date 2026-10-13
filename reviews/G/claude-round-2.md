# G 审阅（Claude，第 2 轮）

**核验范围：** 我独立读了 `phase-c-sil @ 250ce20` 的源码和 diff，没有运行任何仿真。CI 结果我看不到实时状态，按你说的视为未确认。

## 一、先更正我上一轮的说法

你的纠正成立。no-delay 下 preview 并不是"所有格子必 FAIL"：F3 的抖动围绕 0，在 σ 较大时，四舍五入后的延迟可能 ≥ 15 ms，这些帧能通过 `sim/preview.py:69` 的 guard，而 preview 本来就是按稀疏传感设计的，所以 F3 在 no-delay 下可能 PASS。我上一轮的结论下错了，逐格实测是对的。

F6 那条理由要小心。如果 mailbox 是 latest-wins，在 1 kHz、零延迟的情况下，恢复时交付的是最新一帧，帧龄 0，仍然会被拒收。F6 能不能交付"旧帧"完全取决于 M0 里 mailbox 的精确定义。别依赖这个论证，把定义写死就行。

## 二、G 工具：两处必须修（影响完整性）

**1. 冻结范围漏了"产生基线证据的代码"。**
`review_gate.py` 只保护 `sim/`、`firmware/`、`tests/`、`harness/contract.json`、`requirements-lock.txt`。但 gate 的核心证据是"Phase A/B CI 绿"，而下面这些决定 CI 怎么判的文件没被冻结：

- `.github/workflows/phase-a.yml`
- `.github/workflows/phase-b.yml`
- `tools/compare_traces.py`（Phase A 跨平台比较）
- `harness/ci.py`
- `harness/compare.py`
- `harness/tests/data/protocol_v1.json`

这些文件只要被改动，CI 就可能在基线已经变了的情况下照样绿。修法：把它们加进 protected 列表。Phase C 的代码和 CI 一律放新文件、新 workflow。M1 需要扩展的 Rust runner 等共享模块可以改，但比较器和 CI 定义不能动。

**2. M3 "不重跑"规则和存储规模冲突。**
每个 run 的 trace 加 truth 是每 tick 两行 canonical JSON，粗估每 run 4–5 MB，3615 个 run 是 15 GB 量级（M1 实测后修正）。而交互热图要求点每个格子都能看曲线。建议规则：

- M2 为每个 run 保存降采样曲线（10 ms 一点：e、gap、needle/tissue、command、fresh），集中放进一个压缩文件，供热图使用。
- 完整 trace 只记录 SHA-256，不进 git。
- M3 需要完整 trace（视频）时，**允许重新生成，但生成结果的 SHA-256 必须等于封存值**，否则判 INVALID。这不是新结果，只是可证明相同的复现。
- `REVIEW_PROTOCOL.md` 里"no simulation reruns for art"改成这条。

## 三、M0 必须写进去的规则（否则预测没法判）

**3. 预测原文不改，但每条要注册判定方法。** 现在的写法跑完会有歧义：

| 预测 | 需要定义 |
|---|---|
| 1. F4 @ 25 Hz → FAIL | 4 个注入时刻是"全部 FAIL"还是"任一 FAIL"；只看 preview，还是 c32 也算 |
| 2. F5 ≥ 1.6 Hz → FAIL | 1.6 和 1.8 两档都要 FAIL 才算成立？ |
| 3. F1 ≥ 60 tick → FAIL | 同预测 1 的注入时刻规则 |
| 4. 瞬态故障在 2.4 s 最差 | "最差"按 contact RMS 还是 FAIL 数；F1/F2/F3/F6 是"全部"还是"多数"满足；平局怎么算 |
| 5. no-delay 翻转最多 | 计数单位（seed 聚合后的格子）；对照组（同控制器 baseline 消融）；preview 和 c32 分开算还是合算；平局 |

建议默认：
- 只按 preview 判，c32 单独报告一致性。
- 预测 1、3：4 个注入时刻全部 FAIL 才算成立。
- 预测 4：按 contact RMS，4 种瞬态故障里至少 3 种的最大值出现在 2.4 s。
- 预测 5：按 seed 聚合后格子的 verdict 翻转数，严格最多才算成立，平局算不成立。

具体规则你们定，关键是 M0 提交前写死。

**4. 恒等格子要做成自动检查，不只是"透明报告"。**
按构造等于无故障的格子必须满足：trace SHA 等于同控制器、同消融的无故障 run，不相等就判 INVALID（说明注入器有 bug）。这类格子包括：no-noise 全部、no-jitter-model × F3、no-quantization × F8、no-dropped-frame-model × F2、F7 100%，以及 F4 1000 Hz 和 F8 24 bit（如果按构造恒等的话；F8 24 bit 不一定逐 bit 相同，先算清楚再归类）。这是全矩阵里最便宜的正确性证据。

**5. 跨语言注入器等价测试放进 M1 验收。**
"Python 和 Rust 读同一份 YAML"不等于两边注入结果相同。每种故障至少取一档，在同一个 plant 上比较两边**注入后的传感帧序列逐字节相同**，而不是只比较 verdict。否则 c32 和 preview 的差异会把注入器差异和控制器差异混在一起。

## 四、次要

- `phase-c.yml` 跑了 `render_reviews.py`，但没检查提交的 `index.html` 是不是最新，建议在后面加 `git diff --exit-code reviews/index.html`。
- `review_gate.py` 里第一次给 `required` 赋的字面量是死代码，删掉。
- 冻结文件被删除时，`git hash-object` 会直接抛异常，建议改成报 `missing`，输出更清楚。

## 五、设计决定

其余全部接受：F5 走 plant、单次 2 s 起点；N-tick burst 和 300 ms 窗口分开；F1 值冻结、元数据递增；机制消融；c32 跑全部六种消融（3564 + 51 = 3615 我核对过）；F7 按同控制器、同消融的无故障峰值；F8 只量化 surface。这些都是正常的工程选择，不需要升级。

**结论：** BLOCK 只针对第 1、2 条，都是小改动，可以并进 M0 的提交里；M0 文档可以并行写。第 3–5 条必须进 M0 注册文件。

```json
{
  "verdict": "BLOCK",
  "issues": [
    {"severity": "blocker", "where": "tools/review_gate.py frozen_check()", "what": "冻结范围漏了产生基线证据的 CI 定义和比较器：phase-a.yml、phase-b.yml、tools/compare_traces.py、harness/ci.py、harness/compare.py、harness/tests/data/protocol_v1.json；CI 绿不能证明基线未变", "touches_frozen_or_registered": true},
    {"severity": "major", "where": "docs/REVIEW_PROTOCOL.md 'no simulation reruns for art'; M2/M3 产物设计", "what": "全量 trace 约 15 GB 量级；改为 M2 存降采样曲线 + 完整 trace 只存 SHA，M3 重生成必须 SHA 等于封存值，否则 INVALID", "touches_frozen_or_registered": false},
    {"severity": "blocker", "where": "M0 docs/C1_PREREG.md（HANDOFF §5.6）", "what": "5 条预测原文保留，但必须在 M0 注册判定方法：注入时刻全部/任一、判定控制器、'最差'和'翻转'的计数单位与平局规则", "touches_frozen_or_registered": true},
    {"severity": "major", "where": "M0/M2 恒等格子", "what": "按构造恒等的格子必须 trace SHA 等于对应无故障 run，不等则 INVALID，作为注入器正确性检查", "touches_frozen_or_registered": false},
    {"severity": "major", "where": "M1 验收", "what": "Python 与 Rust 注入器须做逐字节的注入后传感帧等价测试，不能只比较 verdict", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "M0 F6 定义", "what": "mailbox 语义要精确写死；latest-wins 在零延迟下不会交付 ≥15 ms 的旧帧，不要依赖该论证", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": ".github/workflows/phase-c.yml", "what": "渲染后加 git diff --exit-code reviews/index.html", "touches_frozen_or_registered": false},
    {"severity": "minor", "where": "tools/review_gate.py", "what": "删除 required 的死代码赋值；冻结文件缺失时报 missing 而不是抛异常", "touches_frozen_or_registered": false}
  ]
}
```
