# C1 design decisions before registration

The current user delegates resolving design ambiguities to the working/review loop.
No Phase C simulations have run. The original handoff remains unchanged.

Accepted from the startup review, with independent corrections:
- F5 is real plant motion through a new isolated implementation, not sensor spoofing.
  It ramps 1.2 Hz to target during 2–5 s and holds until 8 s. F5 has one onset (2 s).
- F1 and F6 are single N-tick bursts. F2/F3 have 300 ms windows. F4/F7/F8 persist.
- F1 freezes surface value but advances capture timestamps/sequence normally.
- Ablations remove the named mechanism including its injected effect; no-noise is
  an identity with zero nominal noise. Identity cases are reported transparently.
- All five prediction sentences remain unchanged. No-delay can cause age-guard
  rejection; do not predeclare all cells FAIL or prediction 5 confirmed. F3/F6 can
  deliver older frames. The metric thresholds and controller code remain frozen.
- Both preview and preview_c32 cover all six ablations, retaining the original
  full comparison rather than reducing C32 to baseline as the reviewer suggested.
- F8 quantizes surface position only. F2/F3 seeds are 42–46. F7 references the same
  controller/ablation/seed-42 nominal full-run maximum absolute command.
- Figure 4 uses a preregistered severity selection rule; F5 uses its sole 2–5 s ramp.

Exact algorithm details and experiment inventory belong in C1_PREREG.md at M0.
These are prospective corrections, not post-result changes. No user confirmation
is pending. The reviewer's comments are advisory and retained as historical text.
