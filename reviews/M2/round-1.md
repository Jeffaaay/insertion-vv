# M2 acceptance and evidence

Acceptance: registered full matrix and ablations, C32 coverage accounting, five
PNG-300dpi/SVG figures, sealed matrix SHA and generating commit. M1 feedback was
implemented before this matrix: atomic run directories, validated F7 calibration,
registered onset/seed rejection, all-severity/all-seed Python/Rust equivalence.
Local acceptance: 13 tests passed; generating commit has all three hosted workflows
green. Milestone commit CI and frozen-source evidence are recorded in packet.md.

Outputs: artifacts/c1/{matrix.json,matrix.sha256,execution-manifest.json,summary.json,
evidence-audit.json,figs/*}. Seal and result interpretation: docs/C1_SIL_PREDICTIONS.md.
All 7,230 compressed evidence files were decompressed and their hashes/line counts
verified. Identity checks: 1,106/1,106. Five figures were visually inspected.

3,615 rows; 2,730 PASS, 789 FAIL, 96 INVALID. Repeat hashes match for every row;
96 incomplete rows remain INVALID, not reproducible successes. All are expected
C32 F6 ABI rejections. Valid pairs 1,686/1,782; 1,686 agree and none disagree.
P1/P3/P4 unsupported; P2/P5 supported under unchanged registered operational rules.

No Phase A/controller/firmware/verdict changes. All baseline files remain frozen.
Large lossless traces stay local (3.78 GB compressed), while matrix and scientific
figures are committed. M3 visualization source is drafted but its artifacts have
not been generated and it has not run any simulation. External reply will be
copied verbatim from the user-selected Claude conversation.
