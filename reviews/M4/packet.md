# M4 review packet

Implementation commit: `25bfc23e4b68b70d2a7aa7d02b4410d98934b3c9`

Exact-commit hosted CI green: True

Frozen checks: 104 PASS

```text
 artifacts/c1/blog.html                            |   16 +
 artifacts/c1/derived-artifacts.json               |  104 +-
 artifacts/c1/figs/fig1_fault_severity_heatmap.svg |   96 +-
 artifacts/c1/figs/fig2_rms_vs_inject_time.svg     |  204 +-
 artifacts/c1/figs/fig3_ablation_flips.svg         |  114 +-
 artifacts/c1/figs/fig4_controllers_vs_faults.svg  |   96 +-
 artifacts/c1/figs/fig5_hil_only.svg               |    2 +-
 artifacts/c1/index.html                           |   10 +
 artifacts/c1/report.html                          |   14 +
 artifacts/c1/reviews.html                         | 3725 +++++++++++++++++++++
 artifacts/c1/videos/F1-preview.png                |  Bin 54597 -> 54730 bytes
 artifacts/c1/videos/F1.mp4                        |  Bin 425085 -> 425196 bytes
 artifacts/c1/videos/F2-preview.png                |  Bin 53341 -> 53472 bytes
 artifacts/c1/videos/F2.mp4                        |  Bin 396381 -> 396493 bytes
 artifacts/c1/videos/F3-preview.png                |  Bin 52145 -> 52277 bytes
 artifacts/c1/videos/F3.mp4                        |  Bin 395939 -> 396050 bytes
 artifacts/c1/videos/F4-preview.png                |  Bin 55101 -> 55230 bytes
 artifacts/c1/videos/F4.mp4                        |  Bin 449238 -> 449347 bytes
 artifacts/c1/videos/F5-preview.png                |  Bin 53291 -> 53421 bytes
 artifacts/c1/videos/F5.mp4                        |  Bin 488885 -> 488990 bytes
 artifacts/c1/videos/F6-preview.png                |  Bin 57432 -> 57560 bytes
 artifacts/c1/videos/F6.mp4                        |  Bin 411880 -> 412014 bytes
 artifacts/c1/videos/F7-preview.png                |  Bin 54243 -> 54374 bytes
 artifacts/c1/videos/F7.mp4                        |  Bin 423462 -> 423569 bytes
 artifacts/c1/videos/F8-preview.png                |  Bin 54091 -> 54224 bytes
 artifacts/c1/videos/F8.mp4                        |  Bin 403318 -> 403429 bytes
 artifacts/c1/visualization-manifest.json          |   19 +-
 c1/analyze.py                                     |    3 +-
 c1/build_report.py                                |  102 +
 c1/hub-template.html                              |   10 +
 c1/seal_derived.py                                |   10 +
 c1/verify_public.py                               |   20 +-
 c1/visualize.py                                   |    7 +-
 docs/C1_SIL_PREDICTIONS.md                        |   16 +-
 docs/FINDINGS.md                                  |   59 +
 docs/PHASE_C_SIL_SUMMARY.md                       |   43 +
 reviews/M3/claude-round-1.md                      |   26 +
 reviews/M3/evidence.json                          |  556 +++
 reviews/M3/packet.md                              |   63 +
 reviews/M3/reply-integrity.json                   |    6 +
 reviews/M3/response-actions.md                    |   18 +
 reviews/M4/local-checks.json                      |    7 +
 reviews/M4/round-1.md                             |   22 +
 reviews/index.html                                |  700 +++-
 44 files changed, 5744 insertions(+), 324 deletions(-)
```

- Phase C integrity: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38349076776
- Phase B C32: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38349076797
- Phase A SIL: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38349076838

See round notes for acceptance criteria, artifacts and limitations.
