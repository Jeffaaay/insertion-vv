# M4 审阅（Claude）

**核验范围：** 我读了 `25bfc23` 的一页报告、FINDINGS #5–#9、`blog.html`、`report.html`、`index.html`，并从 `matrix.json` 独立重算了文中出现的数字。

**数字全部吻合：**
- matrix 仍为 `cc833c35…98aa9`。
- 余量表 8 行全部一致，包括 F1 13.318 / 0.7699、F5 157.135 / 3.1302、F7 264.094 / 3.5382。
- F2/F3/F8 相对 nominal 的最大偏差：2.5177 / 8.2104 / 3.3151 nm。
- C32 有效配对最大 RMS 差 0.0022464752 µm，最大相对差 0.0733611%。
- F5 1.3 Hz 为 52.6838745 µm；F1 在 5 s 注入 13.3184649 µm，在 2.4 s 注入 4.7631422 µm。

**结论边界也守住了：** P5 写明是结构性成立；85% 只作为 HIL 假设；F7 早期静态偏差与晚期瞬态分开叙述；C32 F6 的 0/96 覆盖单独列出；明确写了没有硬件结论。blog 的事实与报告一致。

**M4 通过。** 两处小问题，不影响事实：

1. **`index.html` 里有两个公开链接打不开。** 它链接到 `evidence-runs.zip` 和 `evidence-runs.sha256`，但这两个文件不在 git 里，在 GitHub 上会 404。改法：`.sha256` 只有几十字节，直接提交进 git；zip 改成纯文本说明"本地交付，SHA-256 见 …"，不做成链接。
2. **仓库链接指向会移动的分支。** `index.html` 链接的是 `tree/phase-c-sil`，分支以后会继续变化。封存报告应该链接到固定的 commit（`25bfc23`）。

```json
{"verdict":"PASS","issues":[
{"severity":"minor","where":"artifacts/c1/index.html","what":"evidence-runs.zip 与 evidence-runs.sha256 不在 git 中，公开链接会 404；提交 .sha256，zip 改为不带链接的本地说明","touches_frozen_or_registered":false},
{"severity":"minor","where":"artifacts/c1/index.html","what":"仓库链接指向分支 tree/phase-c-sil，应改为固定 commit 25bfc23","touches_frozen_or_registered":false}]}
```
