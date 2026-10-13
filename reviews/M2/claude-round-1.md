# M2 审阅（Claude）

**核验范围：** 我独立读了 `d0b8698` 的 `C1_SIL_PREDICTIONS.md`、`matrix.json`、`summary.json` 和五张图，并直接从 `matrix.json` 重算了关键数字。本地 trace 包（3.78 GB）我访问不到，trace 级哈希无法独立核验。

**重算结果：全部与你们一致。**
- matrix SHA-256 = `cc833c35…98aa9` ✓
- 2730 PASS / 789 FAIL / 96 INVALID，96 个全是 C32 F6 ✓
- 重复 run 哈希不一致：0 ✓
- 3615 个 run_id 唯一 ✓
- 1106 个 identity 全部通过，我按参考 run 的 trace/truth SHA 逐条复核一致 ✓
- F7 的 nominal 引用全部正确 ✓
- 1782 对中 1686 有效且全部一致 ✓
- P1–P5 判定与图 4 选档规则 ✓
- 生成 commit 之后只新增了 `analyze.py` 和 `verify_evidence.py`，注入和运行代码没有变动 ✓

**没有阻塞问题，M2 通过。** 以下几条请在 M4 报告里写清楚，否则结论会被读歪：

1. **P5 的"成立"不提供信息。** no-delay 的 297 个 preview run 全部 FAIL（包括 nominal，RMS 在 200 µm 以上），280 次翻转完全来自估计器的 15 ms 帧龄 guard。另外四个消融翻转数为 0，是因为它们关掉的 F2/F3/F8 在 baseline 下本来就没有 FAIL，没有东西可翻。正确的说法是：在注册范围内，jitter、量化、丢帧的建模细节不改变任何 verdict。这本身就是一个发现，但不能作为"延迟建模必要"的证据。

2. **要报告余量，而不只是 PASS/FAIL。** 图 1 一片绿，会让人误读成"故障没有影响"。实际的 contact RMS 最大值：
   - F1：13.3 µm（达到阈值的 67%，120 tick、5 s 注入）
   - F4：1.44 µm
   - F6：1.23 µm
   - F2、F3、F8：与 nominal（1.1226 µm）相差不到 2 nm

   建议在图 1 每个格子里加上最大 RMS 数值。所有数据都来自已封存的矩阵，不需要新的 run。这也决定了 HIL 对照该看哪里：F2/F3/F8 上 sim 和 HIL 都 PASS 几乎不说明问题，有区分力的是 F1、F5、F7 和 F6 的语义。

3. **P4 的判定只靠 F1。** F2/F3 的"5 s 最差"是由纳米级差异决定的，应写成"基本平坦"。P4 不成立实际上由 F1 一项决定：5 s 注入 13.3 µm，2.4 s 注入 4.76 µm。

4. **F7 失败的本质是静态力不够，不是动态跟踪失效。** 在 0.2、1.5、2.4 s 注入时，RMS 完全相同（264 / 210 / 120 µm），峰值 |ė| 只有 0.009 mm/s，说明针稳定停在了插入深度不足的位置。nominal 的峰值接触力 4.85 mN 约等于指令峰值 5.74 mN 的 85%，所以作为 HIL 假设可以写：限幅低于约 85% 就保持不住深度。不要把它写成插值得出的 flip point。

5. **图 2 有线被盖住了。** F2、F3、F8 三条线重叠，F2 的橙线完全看不见。加直接标注，或者加一句"F2/F3/F8 与 nominal 相差不到 2 nm"。

6. **补充溯源记录。** 在 `C1_SIL_PREDICTIONS.md` 里补上 `summary.json`、五张图、3.78 GB 证据包的 SHA-256，以及 `analyze.py` 所在的 commit，让 M3/M4 能核验派生产物。另外建议公开一小部分可复核的 trace：8 条视频对应的 run 加上它们的 nominal 参考，约十几 MB。

```json
{"verdict":"PASS","issues":[
{"severity":"major","where":"M4 报告; fig3","what":"P5 成立是结构性的：no-delay 全部 FAIL 来自帧龄 guard，其余消融因目标故障在 baseline 下无 FAIL 而无可翻转；应表述为'注册范围内 jitter/量化/丢帧建模不改变 verdict'","touches_frozen_or_registered":false},
{"severity":"major","where":"fig1; M4 报告","what":"报告每种故障的最大 RMS 与 |ė| 余量（F1 13.3 µm；F2/F3/F8 相差不到 2 nm），并说明 HIL 对照的区分力集中在 F1/F5/F7/F6","touches_frozen_or_registered":false},
{"severity":"minor","where":"C1_SIL_PREDICTIONS.md P4","what":"F2/F3 的最差时刻由纳米级差异决定，应写为基本平坦；P4 不成立由 F1 决定","touches_frozen_or_registered":false},
{"severity":"minor","where":"M4 报告 F7","what":"F7 失败是静态保持力不足（RMS 恒定、ė 约 0.009 mm/s；接触力约为指令峰值的 85%），作为 HIL 假设表述，不当作插值得出的 flip point","touches_frozen_or_registered":false},
{"severity":"minor","where":"fig2","what":"F2/F3/F8 曲线重叠导致 F2 不可见；加直接标注或说明","touches_frozen_or_registered":false},
{"severity":"minor","where":"docs/C1_SIL_PREDICTIONS.md","what":"补充 summary.json、各图、本地证据包的 SHA-256 和 analyze.py 的 commit；建议公开视频对应 run 的 trace 子集","touches_frozen_or_registered":false}]}
```
