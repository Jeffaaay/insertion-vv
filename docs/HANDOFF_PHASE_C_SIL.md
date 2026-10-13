你接手一个机器人验证项目。下面是从零开始的完整说明，以本文为准。

━━━━━━━━━━━━━━━━━━━━
一、这个项目是什么
━━━━━━━━━━━━━━━━━━━━
仓库：github.com/Jeffaaay/insertion-vv（公开）
当前 main：e8cb4ee；已有 tag：v0.1-phase-a

一句话：做一个缩小版的"手术机器人验证系统"。
- 场景：一根针沿一条轴插进组织。组织会跟着心跳（约 1.2 Hz）上下动。
- 控制器的任务：让针跟着组织一起动，针和组织之间的相对误差（contact RMS）越小越好。
- 物理世界用 MuJoCo 模拟。基线论文是 arXiv 2608.08860。

项目分三个阶段：
- Phase A（纯软件）：在 sim 里写控制器，看能不能达标。
- Phase B（软件 + 硬件）：控制器移植成 C，跑在 STM32 板子（NUCLEO-H723ZG）上，MuJoCo 继续当被控对象。外面用 Rust harness 管理。
- Phase C（故障注入）：在 sim 和真板子上故意制造同样的故障，看两边的 PASS/FAIL 是否一致，以及 sim 漏建模哪一项会让 bug 溜过去。

━━━━━━━━━━━━━━━━━━━━
二、已经做完的（全部冻结）
━━━━━━━━━━━━━━━━━━━━
- Phase A：4 个控制器的 contact RMS
  lab_frame_pd 256 µm / delayed_feedback 184 µm / offsetfree 20.6 µm / preview 1.12 µm（PASS，论文 MPC 是 1.9 µm）
- Phase B1：C 版 float32 控制器（preview_c32）+ Rust harness + 虚拟板子。
  float32 和 float64 的针位置最大差 0.017 µm。
- Phase B2：固件和烧录工具已写好，但还没烧。BIN 的 hash 开头是 cb7a11e3。
  事先定好的目标：compute p99 < 100 µs，overrun = 0，抖动 p99 < 5 µs，栈余量 ≥ 4 KiB。
- 确定性规则分两层：
  · 同一台机器、同一环境：结果逐 bit 相同
  · 不同机器：针位置差 < 1e-12 m，并且 PASS/FAIL 结论相同
- 已有发现 #1–#4：论文的刚度参数自相矛盾；不同平台 sin 差 1 ulp；BLAS 实现会影响结果；float32 有精度地板。
- 仓库里已有的文档（PROJECT_BRIEF.md、docs/FINDINGS.md 等）可以参考。

不许动的东西：
Phase A 数值代码、C 版控制器源码、MuJoCo 模型（MJCF）、PASS/FAIL 判定规则、容差、所有已记录的 trace/truth hash、固件。

━━━━━━━━━━━━━━━━━━━━
三、现在要做什么
━━━━━━━━━━━━━━━━━━━━
板子大约一周内用不了。这一周先做 Phase C 的 sim 半边：
在 sim 里对 8 种故障从轻到重各跑一遍，得出每种故障在什么程度会从 PASS 变成 FAIL，再把结果封存。
板子回来后，在真固件上做同样的故障，对答案。

最终交付：一份封存的预测 + 5 张图 + 8 条视频 + 1 个交互热图 + 1 页报告。

━━━━━━━━━━━━━━━━━━━━
四、几个词
━━━━━━━━━━━━━━━━━━━━
- tick：控制器每 1 ms 算一次。一次 run 是 8 s，也就是 8000 tick。
- 严重度梯度：同一种故障从轻到重的一组档位。
- flip point：从 PASS 变成 FAIL 的那一档，代表系统对这种故障的余量。
- 注入时刻：故障开始的时间。已知的脆弱时段：0–0.5 s（Kalman 还没锁住心跳相位）和 2.3–2.6 s（针刚接触组织）。
- 消融：关掉 sim 里的某一项建模再跑一遍，看结论变不变。
- 封存：对结果文件算 SHA-256 写进文档，之后不再修改。
- HIL-only：只在真板子上存在的故障，sim 不给结论。

━━━━━━━━━━━━━━━━━━━━
五、实验设计（M0 要原样写进文件）
━━━━━━━━━━━━━━━━━━━━
8 种故障 + 严重度档位：
F1 传感帧冻结（连续 N tick 读到同一个旧值）：1, 5, 15, 30, 60, 120 tick
F2 传感帧丢失（随机丢帧）：1, 5, 10, 25, 50 %
F3 延迟抖动（15 ms 延迟上叠加随机 σ）：0.5, 1, 2, 5, 10 ms
F4 采样率下降（组织位置的更新频率）：1000, 200, 100, 50, 25 Hz
F5 心率漂移（预测器固定按 1.2 Hz，实际心率在 2–5 s 内线性变成）：1.3, 1.4, 1.6, 1.8 Hz
F6 deadline miss（sim 模拟：跳过 tick，保持上一条指令）：连续 1, 5, 15, 50 tick
F7 执行器饱和（力指令限幅到标称峰值的）：100, 50, 25, 10 %
F8 量化（传感输入在 ±1 mm 范围内的位数）：24, 16, 12, 10 bit

注入点：F6 在控制器 tick，F7 在执行器输出，其余在传感器模型层。
注入时刻：每种故障都跑 0.2, 1.5, 2.4, 5.0 s。
持续时间：300 ms。F4、F5、F7、F8 是持续性故障，不适用。
随机种子：F2、F3 各跑 5 个 seed，只要有一个 FAIL 就算 FAIL。其他故障只用 seed 42。

消融（每一项都重跑全矩阵）：
baseline / no-delay / no-jitter-model / no-quantization / no-noise / no-dropped-frame-model

被测控制器：
- 主：preview（float64）
- 确认：preview_c32 跑一遍完整矩阵，结论应该和主控制器一致，不一致的地方要记录
- 图 4 用：四个控制器各跑每种故障的一个注册档位

预测（现在写下，之后只能对照，不能改）：
1. F4 降到 25 Hz → FAIL
2. F5 ≥ 1.6 Hz → FAIL
3. F1 ≥ 60 tick → FAIL
4. 瞬态类故障在 2.4 s 注入时最差
5. 消融中 no-delay 翻转的结论最多

HIL-only（sim 不给结论）：
F9 串口 CRC 错误、F10 板子和 PC 的时钟漂移。
F6 的 sim 结果要标注"模拟的 deadline miss，需在 HIL 复核"。

规模：约 600–1300 次 run，每次约 0.5 s；全部消融约 1–2 小时 CPU。CI 只跑子集，全矩阵在本地跑完后封存。

━━━━━━━━━━━━━━━━━━━━
六、整条线
━━━━━━━━━━━━━━━━━━━━
G → M0 → M1 → M2 → M3 → M4 → 停，等我
每个里程碑结束：commit → CI 绿 → 过 review gate → 进入下一个

G  搭建
   - 把本文存成 docs/HANDOFF_PHASE_C_SIL.md
   - 搭 review gate（见第七节）
M0 注册：写 docs/C1_PREREG.md，原样写入第五节全部内容。必须在任何 run 之前提交。
M1 注入器：故障定义放在 faults/*.yaml，Python 和 Rust 的 FaultInjector 读同一份。确定性规则不变，旧 hash 一个 bit 都不能变。
M2 矩阵：跑完全部网格和消融。产出 artifacts/c1/matrix.json（每条 run 记录：run id、故障、档位、注入时刻、seed、消融项、trace SHA、指标、结论）和图 1–5。最后把 matrix.json 的 SHA-256 和生成它的 commit 写进 docs/C1_SIL_PREDICTIONS.md。
M3 可视化：8 条视频 + 交互热图。只读 M2 的结果，不碰 sim 和控制器。
M4 报告：写 docs/PHASE_C_SIL_SUMMARY.md，内容包括：
   - 5 条预测哪些成立、哪些不成立（不成立的写在前面）
   - 每种故障的 flip point 表
   - 消融结论
   - preview_c32 和 preview 的差异
   - sim 能信到哪里，以及 HIL-only 清单
   再在 docs/FINDINGS.md 从 #5 起追加。

━━━━━━━━━━━━━━━━━━━━
七、review gate（每个里程碑后自动审查）
━━━━━━━━━━━━━━━━━━━━
1. 写 reviews/<M>/packet.md，只写事实：本里程碑的验收标准、commit、git diff --stat、CI 结果、冻结文件 hash 前后对比、主要产出的路径和一句话说明。
2. 调两个只读 reviewer，提示词放在 docs/REVIEWER_PROMPT.md：
   - Claude：claude -p，--output-format stream-json --verbose，--permission-mode dontAsk，只允许读文件和只读的 git/sha256 命令
   - GPT：新开一个只读的 codex exec 会话，不带你当前的上下文
   - 两个 reviewer 都必须自己读仓库核对，不能只信 packet
   - 回答必须以 JSON 结尾：{"verdict": "PASS"|"BLOCK"|"ESCALATE", "issues": [{"severity", "where", "what", "touches_frozen_or_registered"}]}
3. 记录全过程：
   - reviews/<M>/claude.stream.jsonl、gpt.stream.jsonl
   - sessions.md（会话编号和重新打开的命令）
   - round-<n>.md（每轮改了什么、为什么）
4. 用 tools/render_reviews.py 生成 reviews/index.html：聊天式时间线，工具调用默认折叠，结论用颜色区分。每次 gate 后更新并提交。
5. 判定：
   - 两个都 PASS → 继续
   - 有 BLOCK 且都是范围内的问题 → 修完重审，最多 2 轮
6. 缺 CLI 或没登录：停下告诉我。不许去爬任何聊天网页。

━━━━━━━━━━━━━━━━━━━━
八、停点
━━━━━━━━━━━━━━━━━━━━
- M4 过 gate 之后：停下报告，等我批准再打 tag v0.3-phase-c-sil
- 以下任一情况立刻停，写 reviews/<M>/ESCALATION.md，等我：
  · 任何 reviewer 返回 ESCALATE
  · reviewer 建议改冻结文件、已注册内容或容差
  · 同一里程碑修了 2 轮仍不过
- 其他情况一律不停

━━━━━━━━━━━━━━━━━━━━
九、要保存的图
━━━━━━━━━━━━━━━━━━━━
artifacts/c1/figs/（每张存 PNG 300 dpi + 同名 SVG）
1. fig1_fault_severity_heatmap：故障 × 档位热图，标出 flip point
2. fig2_rms_vs_inject_time：contact RMS vs 注入时刻，每种故障一条线
3. fig3_ablation_flips：消融 × 故障，标出结论是否翻转
4. fig4_controllers_vs_faults：四个控制器 × 故障
5. fig5_hil_only：HIL-only 清单

artifacts/c1/videos/
6. F1.mp4 … F8.mp4：每种故障一条，8 s，用该故障的 flip-point 档位。画面分三栏（正常 / 故障 / 差值 ×100），下方放实时误差曲线。

artifacts/c1/
7. heatmap.html：交互热图，点一个格子会弹出该 run 的三面板曲线

reviews/
8. index.html：全部 review 的聊天式时间线

━━━━━━━━━━━━━━━━━━━━
十、规矩
━━━━━━━━━━━━━━━━━━━━
- 先注册再跑；预测写下后只能对照，不能改
- 一次只改一个变量；不调控制器，不调容差
- 结果不可复现记为 INVALID，不是 FAIL
- 旧 hash 一个 bit 都不能变；每个里程碑一个 commit，CI 绿了才进下一步
- 如果发现注册内容本身不合理：停下来报告，不要自己放宽

从 G 开始。