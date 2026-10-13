# M2 review packet

Implementation commit: `d0b86986c7677985ccae5d358b3a3c2ba7128672`

Exact-commit hosted CI green: True

Frozen checks: 104 PASS

```text
 artifacts/c1/evidence-audit.json                  |    7 +
 artifacts/c1/execution-manifest.json              |    1 +
 artifacts/c1/figs/fig1_fault_severity_heatmap.png |  Bin 0 -> 318398 bytes
 artifacts/c1/figs/fig1_fault_severity_heatmap.svg |  594 ++++++++++
 artifacts/c1/figs/fig2_rms_vs_inject_time.png     |  Bin 0 -> 230577 bytes
 artifacts/c1/figs/fig2_rms_vs_inject_time.svg     |  680 ++++++++++++
 artifacts/c1/figs/fig3_ablation_flips.png         |  Bin 0 -> 255241 bytes
 artifacts/c1/figs/fig3_ablation_flips.svg         |  687 ++++++++++++
 artifacts/c1/figs/fig4_controllers_vs_faults.png  |  Bin 0 -> 205325 bytes
 artifacts/c1/figs/fig4_controllers_vs_faults.svg  |  555 ++++++++++
 artifacts/c1/figs/fig5_hil_only.png               |  Bin 0 -> 277090 bytes
 artifacts/c1/figs/fig5_hil_only.svg               |   66 ++
 artifacts/c1/matrix.json                          |    1 +
 artifacts/c1/matrix.sha256                        |    1 +
 artifacts/c1/summary.json                         | 1206 +++++++++++++++++++++
 c1/analyze.py                                     |  460 ++++++++
 c1/faults.py                                      |    4 +
 c1/matrix.py                                      |  220 ++++
 c1/runner.py                                      |   18 +-
 c1/rust/.gitignore                                |    1 +
 c1/rust/src/lib.rs                                |    9 +
 c1/tests/test_injection.py                        |   60 +-
 c1/verify_evidence.py                             |   58 +
 docs/C1_SIL_PREDICTIONS.md                        |   68 ++
 reviews/M1/claude-round-1.md                      |   19 +
 reviews/M1/evidence.json                          |  556 ++++++++++
 reviews/M1/packet.md                              |   42 +
 reviews/M2/round-1.md                             |   24 +
 reviews/index.html                                |  655 ++++++++++-
 tools/render_reviews.py                           |    8 +-
 30 files changed, 5980 insertions(+), 20 deletions(-)
```

- Phase C integrity: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38346326523
- Phase A SIL: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38346326501
- Phase B C32: completed/success — https://github.com/Jeffaaay/insertion-vv/actions/runs/38346326496

See round notes for acceptance criteria, artifacts and limitations.
