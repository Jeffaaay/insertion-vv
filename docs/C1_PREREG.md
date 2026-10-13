# C1 prospective registration

No Phase C simulations precede this registration commit.

## Original handoff section 5 (historical text, verbatim)

```text
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
```

## Operational specification (resolves the original ambiguities prospectively)

Authority: the user delegates ordinary design decisions to the implementation/review
loop. This section takes precedence over incompatible prose above. No controller,
plant MJCF, numerical Phase A source, verdict thresholds or stored hashes change.

### Population and schedule

Primary contact profile only; 8,000 ticks at 1 ms; scoring remains [3,8) seconds.
Preview and preview_c32 each run every fault/severity/onset/seed in all six ablations.
F5 onset is solely 2.0 s; others use 0.2,1.5,2.4,5.0 s. F2/F3 seeds=42,43,44,45,46;
all other cases use 42. Each controller/ablation also has a seed-42 no-fault case.
Total main inventory=297*2*6=3,564 logical runs, each executed twice. Figure 4 adds
three earlier controllers, one severity per fault and one onset, five F2/F3 seeds,
and a no-fault reference per controller: 51 runs. Total 3,615, excluding validation.
All logical runs retain trace/truth SHA and reproducibility status. Incomplete or
nonreproducible runs are INVALID and never aggregated into PASS. Aggregation: any
INVALID => INVALID; otherwise any FAIL => FAIL; otherwise PASS. This supplements,
without changing, the frozen per-run verdict. No invalid rows are silently omitted.

### Injection semantics

F1/F2/F3/F4/F8 act on tissue surface capture, never the needle encoder. Onset is
capture time (delivery can occur later). F6 acts at controller invocation and F7
at actuator command application; F5 acts on actual plant drive.

- F1: one N-tick capture window [onset,onset+N). Freeze the current captured surface
  value at onset; generate fresh, increasing sequence/sample metadata normally.
- F2: 300 captures from onset, independent Bernoulli drop probability p/100. Dropped
  captures still advance capture sequence; previous delivered value is held.
- F3: 300 captures from onset. Delay = max(0,round_ties_even(base_ms+sigma_ms*z))
  integer ticks, where base=15 normally or 0 for no-delay. Maintain FIFO scheduled
  arrival=max(capture+delay,previous_scheduled_arrival). Deliver all due frames at
  each tick, expose newest due frame, and mark fresh only when a frame is delivered.
  Preserve true sample time. Record early-frame rejection interpretation; do not
  change the preview estimator. The resulting effective jitter includes queuing.
- F4: after onset retain only captures whose absolute tick is a multiple of
  1000/rate. These divisors are integers. Keep nominal capture sequence indexing;
  discarded samples do not enter delivery queue. Continue to 8 s.
- F5: true cardiac frequency ramps from 1.2 to target during [2,5] seconds, then
  holds. For u=t-2 during ramp, phase/(2*pi)=1.2*t+0.5*(target-1.2)*u*u/3;
  after 5 use 1.2*5+1.5*(target-1.2)+target*(t-5). Harmonic uses twice the phase;
  respiration unchanged. Before t=2 call the frozen tissue_target directly.
  Implement in a separate plant subclass/module, leaving original files untouched.
- F6: one N-tick window [onset,onset+N). Do not call the controller; hold previous
  actuator command. Plant and sensor clock continue. Store newest fresh surface
  frame received while skipped; on resumption offer it once if no newer fresh frame
  is already available (latest-wins mailbox), retaining capture metadata. Do not
  compensate missed observer steps. This is simulated deadline miss, HIL unverified.
- F7: symmetric clip to p/100 times the same controller/ablation's seed-42 nominal
  maximum absolute applied command over 8 s. Calibrate by a registered no-fault run
  before F7, record reference run ID/hash/value. Continue to 8 s. 100%=identity.
- F8: surface-only quantizer, LSB=0.002/(2**bits); nearest ties-even integer code,
  signed codes [-2**(bits-1),2**(bits-1)-1], saturation at endpoints. Never quantize
  time, sequence, needle position/velocity or truth. Continue to 8 s.

Fault specs use JSON syntax within .yaml files (a valid YAML 1.2 subset); Python
and Rust parse the exact same files. Random tables are generated before simulations
and committed: independent Python random.Random(1000*fault_number+seed), F2 draws
300 getrandbits(32), drop iff word < floor(p*2**32/100); F3 draws 300 gauss(0,1)
values then stores the resulting integer delays for every sigma and base (15/0).
Both language injectors consume tables, avoiding cross-language Gaussian/libm drift.
No mutation of Phase A's RNG stream: its two original noise/dropout draws are still
consumed per capture in the same order, even when their nominal effects are zero.

### Ablations and interpretation

baseline: original 15 ms transport, zero noise/dropout, no quantization/jitter except
selected fault. no-delay: base transport delay=0, keep F3 around zero and clipping.
no-jitter-model: F3 becomes identity; no-quantization: F8 identity;
no-dropped-frame-model: F2 identity; no-noise: identity for all scenarios here.
Other mechanisms unchanged. Never introduce nuisance noise just to make ablations
interesting. Disabled-fault and identity cells must be labeled explicitly and match
corresponding nominal traces where their entire input/command behavior is identical.
No-delay guard rejection is a controller/model interface effect, not proof that
less physical latency is harmful. F3/F6 can deliver older frames even at base=0.

### Summary rules and unchanged predictions

All five original prediction sentences above are frozen; the following operational
interpretations are fixed before results. Main prediction tests use preview baseline.
P1: every onset at F4=25Hz must FAIL. P2: both F5 targets >=1.6 must FAIL.
P3: F1 levels >=60 must FAIL at every onset. Report partial support separately; do
not relabel an existential failure as universal support.
P4: for each transient fault F1/F2/F3/F6, take maximum contact RMS across severities
and seeds at each onset. 2.4 s must be among maxima for all four faults; exact ties
count as shared worst and are named. Invalid data makes the affected claim unresolved.
P5: count per-run verdict flips versus matched baseline across full preview grid;
no-delay must attain the largest count (report ties). INVALID is tracked separately,
never counted as a PASS/FAIL flip. Also report both directions of flips.

For each fault, order severity from mild to severe exactly as the original list.
Aggregate over onsets/seeds using the rule above. Report first FAIL as boundary,
whether the preceding level passed, pre-existing nominal FAIL, no observed FAIL,
and any nonmonotonic reversals; do not interpolate between registered levels.

Figure 4: choose preview baseline first FAIL level at onset 2.4 s (F5=2 s), aggregated
across five seeds for F2/F3. If none fail choose strongest; label no observed flip.
Run all four Phase A controllers at this same chosen severity/onset; preview rows
are reused, the other three are newly executed. No gain/threshold adjustments.
Figure 2: same selected severity per fault across its registered onsets, max RMS
across seeds; F5 is a single point, not a fabricated onset curve.
Videos: use the globally aggregated boundary level (or strongest if none), choose
onset with worst preview baseline contact RMS at that level and lowest seed on ties;
compare to corresponding nominal trace. Label missing boundary or nominal failure.
Each video is 8 s with normal/fault/difference-x100 and a time-dependent error plot.
M2 retains per-tick traces and truth for every logical run, compressed losslessly,
so M3 visualization requires no simulations. Quantitative plots derive from sealed
matrix; videos are schematic measured-position displays, not new MuJoCo renders.

### Provenance, validity and sealing

Run IDs are stable hashes of canonical scenario records, including controller,
profile, fault, severity, onset, seed and ablation. Each row includes implementation
commit, spec hashes, random-table hash, nominal calibration reference, trace/truth
hashes, repeat hashes, metrics and frozen verdict. A single matrix-level complete
platform fingerprint describes this local environment; no cross-platform equality
claim is made without corresponding runs. Local Windows results are labeled as
such rather than represented as historical canonical Linux numbers.

CI runs meaningful injection boundary tests, shared Python/Rust contract tests,
selected reproducibility checks and legacy workflows. Full matrix runs locally.
M2 seals matrix SHA-256, generating commit and trace inventory; hash integrity is
checked before M3/M4. F9 CRC corruption and F10 clock drift are HIL-only, no sim
PASS/FAIL. No hardware validation or clinical-performance claim is made.

### Frozen C32 tick-gap boundary

Source inspection before experiments shows firmware/ctrl/controller.c:150 requires
input tick == internal next_tick. F6 skips calls, so resumption is expected to be
rejected by the frozen C32 ABI. Do not relabel this rejection as task FAIL, mutate
private controller state, compress its time axis, or call hidden catch-up steps.
Record the attempted C32 F6 case as INVALID with its observed rejection/error and
partial trace. Preserve every registered case in the matrix. Python F6 remains a
simulated skipped-tick experiment; this interface coverage gap must be prominent
in C32 comparisons and the HIL follow-up, not hidden by aggregate agreement rates.

### Identity and cross-language acceptance checks

no-noise must match the SAME FAULT baseline case, not the no-fault case. Disabled
F2/F3/F8 and F4=1000Hz/F7=100% match their same-controller/ablation nominal case
(seed-specific nominal inputs where relevant; zero noise makes sensor RNG draws
inert). F8=24bit is NOT a bitwise identity. Both trace and truth hashes are checked;
an expected-identity mismatch makes the row INVALID with a diagnostic reason.
Python/Rust injector equivalence is checked for all eight faults and both nominal
transport delays, on identical prerecorded full-rate samples from one MuJoCo plant.
Compare binary packed sensor records (values, timestamps, sequence, fresh), skip
schedules and force-clipping outputs exactly. Plant physics is shared Python; F5
is validated by phase continuity/derivative and identical feeding of plant samples.

### Storage feasibility checked before runs

Existing (previous-project) nominal preview trace/truth files total 4,888,677 bytes;
gzip level 6 totals 1,075,237 bytes. 3,615 such runs would occupy about 3.62 GiB
compressed; actual matrix size will be reported. Available local space at startup
was about 699 GiB. Keep losslessly compressed full traces locally with hashes,
never commit their gigabytes to git. M3 can therefore remain read-only without
regenerating simulations. Publish compact curves and selected video evidence.
