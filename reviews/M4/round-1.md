# M4 report and blog acceptance

Artifacts: docs/PHASE_C_SIL_SUMMARY.md; artifacts/c1/report.html (one-page print
layout), blog.html (short Chinese blog), index.html (all deliverables). Append-only
findings #5–#9 preserve the original #1–#4 exactly. M3 minor review issues are fixed.

The report lists unsupported P1/P3/P4 first, then supported P2/P5 with the structural
no-delay caveat. All eight sampled boundaries, independent RMS/velocity extrema and
margins, mechanism ablations, valid-pair C32 agreement/differences, 96 invalid F6
pairs and the HIL-only list are present. F7 steady bias versus late transients is
explicit. No hardware, universal precision or interpolated-threshold claim is made.

Visual QA: report table/content fit within one A4 page of content, no horizontal
overflow; blog and hub inspected in Chrome. All eight videos decode in the browser
at 8 s / 1280x720 with no media errors. Heatmap interactions tested in M3.
Public artifact/source checks run in normal and optimized Python; a corrupted
copied figure is rejected in optimized mode. Local archive and Git blob hashes
are checked separately. Full-matrix seal remains unchanged.

The current milestone commit and exact hosted CI are in packet.md/evidence.json.
External final review will be copied back verbatim. The deliverable needs no release
tag; no tag or hardware action is being taken as part of this software completion.
