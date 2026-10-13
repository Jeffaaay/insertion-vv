> Historical startup escalation. RESOLVED by the user’s subsequent delegation of routine design decisions; retained verbatim below as review history. See docs/REVIEW_PROTOCOL.md and docs/C1_DESIGN_DECISIONS.md.

# G startup escalation — decision requested before M0

Status: ESCALATE. No Phase C experiments or M0 registration have occurred.
G is partially prepared, not passed. No new commit, push, hosted CI, GPT review,
tag or completion blog is claimed. Baseline tracked files remain unchanged.

## External response retained

`claude.md` is the complete response copied from the existing Claude conversation.
Its text was compared against the browser clipboard: 6,560 UTF-16 characters,
FNV-1a 32-bit `c1e063e3`, excluding the archive file's final newline. This check
guards transcription; it is not the experimental SHA-256 sealing mechanism.
The verdict JSON says ESCALATE. The reviewer reports independently cloning and
reading baseline e8cb4ee; that is a reviewer claim, not a local tool execution.

## Local assessment of that response

Confirmed from local source: F5 belongs to physical plant motion; changing only
sensor values is a different experiment. The fixed 2–5 s ramp cannot also begin
at every prescribed injection time. Preview rejects fresh measurements younger
than 15 ms; duplicate sequence/sample metadata is rejected. The scoring window
is 3–8 s. Zero nominal noise/dropout makes relevant baseline ablations identities.

Do not adopt the reviewer's blanket claim that *all* no-delay cases necessarily
FAIL. If F3 jitter remains active, some frames can have age >=15 ms; F6 mailbox
handling can also change delivery age. No experiment has verified every verdict,
or that prediction 5 has the largest flip count. Report measured outcomes only.
The original response is preserved unchanged, with this qualification separate.

Do not silently reduce preview_c32 coverage as proposed in the response. The
decision proposal below retains both controllers across all six ablations.
Figure 4 must also use F5's sole fixed ramp, not a nonexistent 2.4 s F5 onset.

## Proposed decision for user approval — not yet registered

1. F5 changes real tissue motion through an additional plant implementation;
   frozen source/MJCF/controllers remain unchanged. Keep the 2.0–5.0 s frequency
   ramp, hold its target through 8 s, and exempt F5 from the injection-time axis.
   Integrate frequency into phase; keep respiration unchanged.
2. F1/F6 are single N-tick bursts at the selected onset. F2/F3 last 300 ms.
   F4/F7/F8 persist from onset through the end of the run.
3. F1 freezes surface measurement values while sample timestamps and frame
   sequence numbers continue normally. It models a stuck sensor rather than a
   retransmission of identical frame metadata.
4. Ablations remove the named sensor mechanism, including its injected effect:
   no-jitter disables F3; no-quantization disables F8; no-dropped-frame disables
   F2; no-noise is explicitly an identity under zero baseline noise. No-delay
   removes the 15 ms nominal delay while retaining F3 jitter around zero,
   clipped nonnegative. Keep controllers and verdict thresholds unchanged.
   Label disabled-fault/identity cases and avoid overstating causal evidence.
5. Keep all five predictions verbatim, but qualify interpretation of prediction 5:
   zero-delay nominal frames are rejected by the frozen preview age guard.
   Do not predeclare any cell FAIL or any prediction confirmed before running.
6. Retain preview_c32 across all six ablations, matching preview. With the F5
   exception and one nominal case per controller/ablation, that is 297 cases
   per matrix, 3,564 main cases; three additional figure-4 controllers add
   51 cases including their nominal references: 3,615 logical runs before each
   run's determinism replay and any separately documented validation checks.
7. Quantize only the tissue surface measurement for F8; preserve the needle
   encoder. Fix five random seeds to 42–46 and deterministic implementation
   conventions before experiments. F7 uses the corresponding controller and
   ablation's seed-42 nominal full-run maximum absolute force as its reference.
   Figure-4 severity uses a predeclared selection rule; F5 uses its fixed ramp.

This proposal changes the experiment definition, not just file formatting.
User approval is needed to resolve incompatible instructions before M0.
The handoff's section 10 explicitly says: “如果发现注册内容本身不合理：停下来报告，
不要自己放宽”; section 8 also names reviewer ESCALATE as a stopping condition.
The current user's direct browser-review instruction remains authoritative over
the handoff's obsolete CLI-only transport restriction.

## Resume

After the user's decision, finish G's actual gate implementation and exact-commit
CI/reviews. Then register the accepted design at M0 before any Phase C run.
Continue the user-requested pause/send/wait/copy loop at every milestone. Write
the short blog only after M4 is complete; release tagging remains separately
subject to user approval.
