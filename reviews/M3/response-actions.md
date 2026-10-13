# M3 PASS follow-up

Claude independently decoded all videos, checked all 33 public file hashes,
decompressed the 9-run subset, reproduced all video selections and inspected frames.
The full reply is copied verbatim in claude-round-1.md.

All three minor issues are addressed with the final report commit:
1. Earliest-onset choice after equal RMS and equal lowest seed is explicitly a
   post-hoc display convention, not a preregistration amendment. F7 50% is tied at
   200/1500 ms and shows 200 ms. No case or verdict is removed or changed.
2. Public checks and matrix-seal loading now use explicit exceptions, including
   under python -O. A tampered copied artifact is rejected in optimized mode.
3. Move the video x-axis unit right of the last tick; re-render from original traces.

An interim M3 CI run caught formatting in the new public verifier; it was fixed
before the reviewed d0fd911 commit, whose three workflows all passed. Public text
artifacts were canonicalized to LF to keep local and Git bytes identical. No old
source, tolerance, prediction or sealed matrix bytes changed.
