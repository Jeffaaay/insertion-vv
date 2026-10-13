# 文档扩写审阅（Claude）

**核验范围：** 我读了 `3444a51` 的 `blog.html` 全文、`PROJECT_JOURNAL.md`、README 新前言、`review_gate.py` 改动，并对照了 `HARDWARE_RUNBOOK.md` 和 `c1/rust/src/main.rs`。matrix 仍为 `cc833c35…`，视频文件和仿真代码都没有改动。

**这几项没有问题：**
- **没有夸大。** 数字与封存数据一致，P5、85%、F7 早晚期、0/96 覆盖这些边界都写清楚了。文中还特意说明 3615 不能当作 preview 的单一通过率，这句写得好。
- **视频解释到位。** F1/F5/F7 三段各有"看哪里"的提示，明确写了"轨迹回放，不是硬件录像"，F6 附录也注明不能替代 C32 覆盖。
- **README 例外仍然保护旧证据。** 检查要求标记恰好出现 1 次，标记之后的内容与基线逐字相同，其他 103 个文件的保护不变。用 `read_text` 读取会统一换行，所以在 Windows 的 CRLF checkout 上也能正确比对。

**需要改的一处（文档准确性）：硬件篇把"待开发"写成了"待执行"。**

blog 写的是"具体操作沿用仓库的 hardware runbook"，但 runbook 只覆盖 nominal 的 lockstep 和 replay，没有任何故障注入。表里列的 HIL 对照，有三块工具还不存在：

1. **F1/F5/F7 的 HIL 注入：** 需要把 `c1/rust` 注入器接进 board-link 的 lockstep 回路。board-link 是冻结文件，所以要写一个新的 binary。目前 Rust 注入器只做过离线的字节等价验证。
2. **真实 F6：** 需要固件变体（忙等或高优先级中断）或外部负载。这会是一个新的、单独记哈希的构建，不是冻结的 BIN `cb7a11e3`。
3. **F9/F10：** 需要链路层的帧损坏工具和时钟漂移记录工具。

另外建议写明一个预期：lockstep 不是实时运行，F1/F5/F7 在 lockstep 里主要检验 MCU 数值是否与 host C32 一致，而 host C32 已经与 Python 1686/1686 一致，所以大概率会吻合。真正有区分力的是 replay 计时、真实 F6 和 F9/F10。

**修法：** blog 和 journal 的硬件表各加一列"工具状态"（已有 / 待开发），并把那句改成"链路与计时沿用 runbook；故障注入 HIL 工具尚未实现"。只是改文字，改完不需要再审。

```json
{"verdict":"PASS","issues":[
{"severity":"major","where":"artifacts/c1/blog.html §06; docs/PROJECT_JOURNAL.md 硬件篇","what":"'具体操作沿用 hardware runbook' 不准确：runbook 只有 nominal lockstep/replay。F1/F5/F7 HIL 注入（新 binary 接 c1/rust）、真实 F6（新固件变体或外部负载）、F9/F10（链路工具）都尚未实现；硬件表加'工具状态'列，并说明 lockstep 下 F1/F5/F7 预计主要检验 MCU 数值一致性","touches_frozen_or_registered":false}]}
```
