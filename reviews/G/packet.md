# G startup design review — not a completed milestone

Baseline: `e8cb4ee7ac1420c945dbcb2ba86adfe1afa63338`.
Local branch: `phase-c-sil`. No Phase C simulation has run. M0 is not registered.

## Acceptance still pending

Save the original handoff, implement review evidence capture and rendering,
commit, obtain CI for that new commit, and pass review before M0.
The original handoff is copied without alteration into
`docs/HANDOFF_PHASE_C_SIL.md`. `baseline-files.json` records existing file hashes.

## Verified baseline CI

- Phase A: https://github.com/Jeffaaay/insertion-vv/actions/runs/38330849073 — success.
- Phase B: https://github.com/Jeffaaay/insertion-vv/actions/runs/38330849102 — success.

These apply only to the baseline, not to G. Machine-readable evidence:
`baseline-ci.json`. No new milestone commit or hosted CI is claimed.

## User-requested review channel

The current user explicitly requests sending milestone evidence to the existing
Claude chat, waiting for its answer and copying the answer back to the Codex task.
This supersedes the handoff's Claude-CLI-only/no-chat-webpage transport rule.
Destination: https://claude.ai/chat/88a45c0b-4051-4fea-8c12-bdfa77bd4de1
The reviewer response is advisory, never user approval to change scope.
Browser transcript records must not be represented as CLI stream-json output.

## Design conflicts submitted before registration

1. F5 changes actual cardiac motion but handoff groups it under sensor injection.
   `PROJECT_BRIEF.md` section 7 calls F5 a plant parameter;
   `sim/config.py:tissue_target` and `sim/plant.py:step` confirm the distinction.
2. F5's fixed 2–5 s ramp conflicts with onset values 0.2, 1.5, 2.4, 5.0 s.
3. F1/F6 N-tick bursts versus the common 300 ms duration are underspecified.
4. Five F2/F3 seed values, F7 nominal-force reference and figure-4 levels are
   unspecified and must be fixed before seeing experimental results.
5. Existing sensor noise/dropout are zero; jitter and quantization baseline
   models are absent. Identity ablations must be reported honestly.
6. The stated grid is 308 runs per controller per ablation, hence 1,848 for six
   ablations or 3,696 for both controllers, before repeats/figure-4 controls.

The cloud reviewer was asked to inspect public source independently, disclose
access failures, classify decisions and propose minimal corrections if needed.
The reviewer was explicitly told not to claim G passed or experiments ran.

## Work state

Frozen tracked source files have not been modified. Only new handoff and review
records are being added. Any ESCALATE decision will be saved and brought to the
user before dependent implementation or registration proceeds.
