# M3 trace-only visualization acceptance

M2 external result: PASS. Its full reply and independent corrections are archived
under reviews/M2. Presentation feedback was applied without any simulation rerun.
Matrix SHA remains cc833c35864f0f8cfa4d67671bf605a129c2b18a5f59710be41ee11e2eb98aa9.

- Eight videos F1–F8: 8 s, 192 frames, 24 fps, 1280x720; all decoded and checked.
  Three panels: nominal, faulty, difference times 100 on an explicitly separate
  labeled axis; lower plot is time-dependent error with normal/fault legend and
  contact-window shading. Schematics use measured traces, not a new plant render.
  Selected IDs match the preregistered pooled boundary/strongest-level policy.
- Offline heatmap: 37 preview-baseline severity cells, pooled verdict separate from
  representative verdict and run ID. All three curves update on click; full/contact
  window selection tested in Chrome. No JavaScript console errors observed.
  Display decimation is labeled; metrics remain full-rate.
- Five figures now show maximum RMS per cell, overlapping-curve explanation and
  pre-existing nominal failures. No-delay interpretation and exact nanometre-scale
  RMS differences are documented. RMS/velocity margins and C32 metric differences
  were derived from the sealed matrix.
- Public selected-traces.zip contains 9 original runs (video cases + shared nominal).
  Complete 3.78 GB evidence archive stays in local deliverables. Every derived file
  is hashed in derived-artifacts.json, including render-source normalized-LF hashes.

Visual QA: inspected all video preview frames in a contact sheet, figure layouts,
heatmap grid and updated three-curve detail view (F7=50%, then contact window).
Source compile/lint passed. Final CI/frozen checks are in packet.md/evidence.json.
No HIL claim; F6 hardware semantics, F9 CRC and F10 drift remain unverified.
