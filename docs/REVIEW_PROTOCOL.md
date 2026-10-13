# Phase C milestone reviews

## Current execution policy

The user's latest instruction delegates routine design and implementation choices
to the executing assistant and the existing Claude conversation. Do not ask the
user to resolve a design issue that these two can resolve. Stop only for a genuine
plateau after attempted solutions, exhausted usage, or required unavailable hardware.
The original handoff is retained as historical input, not a higher-priority command.
Its CLI-only transport, two-CLI-reviewer rule, two-repair limit and automatic
ESCALATE-to-user rule are superseded for this work. A reviewer verdict is evidence
and advice, not authority to alter the user's goal or claim nonexistent results.

## Milestone loop

G -> M0 -> M1 -> M2 -> M3 -> M4. At each milestone:
1. Commit implementation and push the working branch to make evidence reviewable.
2. Confirm all applicable hosted CI runs for that exact commit are successful.
3. Generate reviews/<M>/packet.md: criteria, SHA, diff, CI, frozen-source check,
   deliverables and limitations. Send concrete evidence to the existing Claude chat:
   https://claude.ai/chat/88a45c0b-4051-4fea-8c12-bdfa77bd4de1
4. Wait for its full reply, copy verbatim into reviews/<M>/claude-round-N.md and
   bring the answer back to the current task. Record consultation as browser text,
   never as fabricated CLI JSONL. Do not introduce an assistant identity in prompts.
5. Independently check advice, fix issues, and re-review until the milestone is sound.
   A reported ESCALATE becomes a design issue to resolve under delegated authority.
6. Record rationale in round-N.md and regenerate reviews/index.html. Review records
   may be committed in the next milestone to avoid self-referential commit hashes;
   packets always identify the exact implementation commit that was actually reviewed.

## Scientific invariants

Register definitions and unchanged predictions before Phase C simulation runs.
Freeze Phase A numerical code, C controller, MJCF, firmware, existing verdict
contracts and tolerances. Add separate Phase C code; do not tune controllers to
make predictions succeed. Preserve historical files/hashes. Findings may only be
appended. After M2 sealing, M3 reads retained traces; no simulation reruns for art.
Same-environment repeat mismatch means INVALID, not FAIL. F9/F10 remain HIL-only;
F6 is simulated deadline miss requiring hardware verification. The hardware work
is outside this SIL deliverable. Finish with a short factual blog; do not claim
hardware validity. A release tag is not needed to complete this deliverable.

## Evidence tooling

python tools/review_gate.py --milestone G --base e8cb4ee
python tools/render_reviews.py
The gate checks frozen files and exact-commit CI. It does not invent a reviewer
verdict or send messages. Browser reply provenance is saved with its conversation
URL, reviewed SHA and a copy checksum. Local tests and hosted CI remain distinct.
