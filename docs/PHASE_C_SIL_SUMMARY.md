# Phase C SIL — one-page result

**3,615 registered cases, each attempted twice:** 2,730 PASS, 789 FAIL, 96 INVALID.
Windows SIL; frozen controller, plant baseline and verdict. All repeat trace/truth
hashes match; 3,519 cases complete. Matrix seal: `cc833c35…98aa9` (full seal in
C1_SIL_PREDICTIONS.md). This completes the software half; no hardware claim.

**Unsupported first.** P1: 25 Hz stays PASS at all four onsets. P3: 60/120-tick
freezes stay PASS (8/8). P4: F1 is worse at 5 s than 2.4 s (13.318 versus 4.763 µm);
F2/F3 also have exact maxima at 5 s, but timing effects are tiny. Only F6 is worst
at 2.4 s. **Supported:** P2 (1.6/1.8 Hz drift FAIL); P5 (no-delay uniquely yields
280 PASS→FAIL flips). P5 is structural: zero-delay nominal already FAILS under the
frozen 15 ms frame-age guard. It does not establish that delay modeling is necessary.

| Fault | First tested FAIL / tested extent | Max RMS / margin (µm) | Peak error speed / margin (mm/s) |
|---|---|---:|---:|
| F1 freeze | None through 120 ticks | 13.318 / +6.682 | 0.7699 / +1.2301 |
| F2 loss | None through 50% | 1.123 / +18.877 | 0.0728 / +1.9272 |
| F3 jitter | None through σ=10 ms | 1.124 / +18.876 | 0.0731 / +1.9269 |
| F4 rate | None down to 25 Hz | 1.441 / +18.559 | 0.0943 / +1.9057 |
| F5 drift | 1.3 Hz; mildest tested already FAIL | 157.135 / −137.135 | 3.1302 / −1.1302 |
| F6 skipped calls | None through 50 ticks (Python) | 1.226 / +18.774 | 0.0728 / +1.9272 |
| F7 clipping | 50%; preceding 100% PASS | 264.094 / −244.094 | 3.5382 / −1.5382 |
| F8 quantization | None down to 10 bits | 1.126 / +18.874 | 0.0729 / +1.9271 |

Extrema above independently span all preview-baseline levels/onsets/seeds; margins
are 20−RMS and 2−peak |ė|. No interpolated boundary or nonmonotonic verdict reversal.
F1 reaches 67% of the RMS limit despite PASS. Nominal RMS is 1.122564 µm.

**Ablations and precision.** Removing jitter, quantization or dropout changes no
verdict here; no-noise is an intentional identity. F2/F3/F8 maximum absolute changes
in contact RMS from nominal are 2.52/8.21/3.32 nm, not instantaneous error bounds.
Of 1,782 Python/C32 pairs, 1,686 are valid and agree; zero valid disagreements.
The other 96 are F6 tick-gap rejections: C32 F6 coverage is 0/96. Maximum valid-pair
RMS difference is 0.002246 µm (largest relative difference 0.07336%, a different case).

**Interpretation and HIL.** Early F7 clipping leaves steady depth bias with peak
|ė|≈0.0091 mm/s; late clipping also causes transients. Insufficient holding force is
a HIL hypothesis, not an inferred 85% flip point. Prioritize F1/F5/F7 and actual F6
timing for discriminating hardware comparisons. F9 CRC and F10 board/PC clock drift
remain HIL-only. Both matrix controllers use the Python injector; Rust has separate
byte-equivalence checks. Older Figure 4 controllers already FAIL nominally. Five
figures, eight trace-only videos, the heatmap and hashed evidence support this scope.
