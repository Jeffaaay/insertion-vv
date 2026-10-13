# A physical scene as the visual entry point

The user clarified that the missing video is a three-dimensional simulation view
of the needle entering material, not a real-hardware recording.

The new introductory clip uses the already sealed nominal preview run and original
capsule needle geometry. It checks the MJCF source hash and decompressed truth hash.
Only measured poses are replayed with mj_kinematics/mj_camlight. No physics integration,
controller invocation, fluid simulation, puncture mechanics or hardware experiment
is introduced. Tissue cutaway dimensions/color, camera and annotations are display-only.

The 12-second, 25 fps clip first covers 8 seconds at 1x, then source ticks 2000–2990
at 0.25x. All frames use actual 1 ms samples without interpolation. The slow segment
is visibly labeled, including the original source time. The blog and evidence hub
feature it before results; GitHub README and journal link the MP4 and poster.
