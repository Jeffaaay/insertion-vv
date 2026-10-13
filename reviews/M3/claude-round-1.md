# M3 审阅（Claude）

**核验范围：** 我独立读了 `d0fd911` 的 `visualize.py`、`heatmap-template.html`、`verify_public.py` 和各份清单，并实际解码了视频、抽帧查看。

**核验结果：全部一致。**
- matrix 仍是 `cc833c35…98aa9`。
- 8 条视频全部解码为 h264、1280×720、24 fps、192 帧、8.000 s，文件 SHA 与清单一致。
- `derived-artifacts.json` 列出的 33 个文件，哈希全部吻合。
- `selected-traces.zip` 里 9 个 run 的 18 份 trace/truth 解压后，SHA 与 matrix 逐条一致。
- 我按注册规则独立重算了视频选档（取边界档，没有 FAIL 就取最强档 → 在该档选 RMS 最差的 onset → 平局取最小 seed），8/8 与清单一致。
- 抽帧检查：F7（0.2 s 注入，4.0 s 处）画面显示针停在约 −0.405 mm，nominal 是 −0.525 mm，深度差约 120 µm，与 RMS 120.48 µm 吻合；F1 的误差曲线在 5.0–5.2 s 出现与冻结窗口对应的鼓包，标注清楚。

你们两处更正我接受：F2/F3/F8 我只看了每个注入时刻的最大值，没有看全部 run 的绝对偏差，所以"均 <2 nm"不准确；F7 在 5 s 注入时 |ė| 达到 1.6–3.5 mm/s，确实有瞬态，不应该统称为静态偏差。

**没有阻塞问题，M3 通过。** 三处小问题：

1. **视频选档里的 onset 平局规则没有注册过。** F7 50% 档在 200 ms 和 1500 ms 两个注入时刻的 RMS 完全相同（都是 120.48480974445947），实际选了 200 ms，等于用了"取最早 onset"规则，但注册文件只写了 seed 平局怎么处理。在清单和 `C1_SIL_PREDICTIONS.md` 里注明这是事后的展示规则，不影响任何 verdict。
2. **`verify_public.py` 全部用 `assert` 做校验。** 在 `python -O` 下这些检查会被删掉，校验会静默通过。改成显式的 `if …: raise`。
3. **视频底部时间轴的 "8" 和单位 "s" 重叠了**，纯外观问题。

```json
{"verdict":"PASS","issues":[
{"severity":"minor","where":"visualization-manifest.json; docs/C1_SIL_PREDICTIONS.md","what":"F7 50% 档在 200/1500 ms 的 RMS 完全相同，实际按'最早 onset'选取；注明这是事后展示规则，不影响 verdict","touches_frozen_or_registered":false},
{"severity":"minor","where":"c1/verify_public.py","what":"assert 在 python -O 下会被移除，改为显式 if/raise","touches_frozen_or_registered":false},
{"severity":"minor","where":"c1/visualize.py 视频误差曲线 x 轴","what":"刻度 '8' 与单位 's' 重叠","touches_frozen_or_registered":false}]}
```
