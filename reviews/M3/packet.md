# M3 review packet

Implementation commit: `d0fd911badbd7abf3bac4ffc47dac84701b885d0`

Exact-commit hosted CI green: True

Frozen checks: 104 PASS

```text
 .github/workflows/phase-c.yml                     |   1 +
 artifacts/c1/derived-artifacts.json               | 152 +++++
 artifacts/c1/figs/fig1_fault_severity_heatmap.png | Bin 318398 -> 410412 bytes
 artifacts/c1/figs/fig1_fault_severity_heatmap.svg | 281 +++++----
 artifacts/c1/figs/fig2_rms_vs_inject_time.png     | Bin 230577 -> 273649 bytes
 artifacts/c1/figs/fig2_rms_vs_inject_time.svg     | 235 +++----
 artifacts/c1/figs/fig3_ablation_flips.svg         | 114 ++--
 artifacts/c1/figs/fig4_controllers_vs_faults.svg  |  96 +--
 artifacts/c1/figs/fig5_hil_only.svg               |   2 +-
 artifacts/c1/heatmap.html                         |  23 +
 artifacts/c1/selected-traces.zip                  | Bin 0 -> 9493167 bytes
 artifacts/c1/summary.json                         | 118 +++-
 artifacts/c1/videos/F1-preview.png                | Bin 0 -> 54597 bytes
 artifacts/c1/videos/F1.mp4                        | Bin 0 -> 425085 bytes
 artifacts/c1/videos/F2-preview.png                | Bin 0 -> 53341 bytes
 artifacts/c1/videos/F2.mp4                        | Bin 0 -> 396381 bytes
 artifacts/c1/videos/F3-preview.png                | Bin 0 -> 52145 bytes
 artifacts/c1/videos/F3.mp4                        | Bin 0 -> 395939 bytes
 artifacts/c1/videos/F4-preview.png                | Bin 0 -> 55101 bytes
 artifacts/c1/videos/F4.mp4                        | Bin 0 -> 449238 bytes
 artifacts/c1/videos/F5-preview.png                | Bin 0 -> 53291 bytes
 artifacts/c1/videos/F5.mp4                        | Bin 0 -> 488885 bytes
 artifacts/c1/videos/F6-preview.png                | Bin 0 -> 57432 bytes
 artifacts/c1/videos/F6.mp4                        | Bin 0 -> 411880 bytes
 artifacts/c1/videos/F7-preview.png                | Bin 0 -> 54243 bytes
 artifacts/c1/videos/F7.mp4                        | Bin 0 -> 423462 bytes
 artifacts/c1/videos/F8-preview.png                | Bin 0 -> 54091 bytes
 artifacts/c1/videos/F8.mp4                        | Bin 0 -> 403318 bytes
 artifacts/c1/visualization-manifest.json          | 115 ++++
 c1/README.md                                      |  25 +
 c1/analyze.py                                     |  64 +-
 c1/heatmap-template.html                          |  23 +
 c1/seal_derived.py                                |  84 +++
 c1/verify_public.py                               |  39 ++
 c1/visualize.py                                   | 268 ++++++++
 docs/C1_SIL_PREDICTIONS.md                        |  23 +
 reviews/G/reply-integrity.json                    |   9 +
 reviews/M0/reply-integrity.json                   |   9 +
 reviews/M1/reply-integrity.json                   |   8 +
 reviews/M2/claude-round-1.md                      |  44 ++
 reviews/M2/evidence.json                          | 556 ++++++++++++++++
 reviews/M2/packet.md                              |  47 ++
 reviews/M2/reply-integrity.json                   |   6 +
 reviews/M2/response-actions.md                    |  27 +
 reviews/M3/round-1.md                             |  27 +
 reviews/index.html                                | 735 +++++++++++++++++++++-
 46 files changed, 2784 insertions(+), 347 deletions(-)
```

- Phase A SIL: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38347971450
- Phase C integrity: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38347971541
- Phase B C32: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38347971470

See round notes for acceptance criteria, artifacts and limitations.
