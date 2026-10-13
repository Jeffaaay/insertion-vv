# Scene3D review correction

Claude reviewed commit `2f20f353d8dc53374781e75c15a6750e7348930e` and blocked one display issue: the target-depth marker was drawn on the front face, producing a perspective mismatch with the needle axis. The full reply is preserved in `claude-round-1.md`; its hash and the reviewed commit's CI are recorded separately.

The marker now passes through `(0, 0, tissue_z - 0.0003)` along `(sin(azimuth), -cos(azimuth), 0)`, horizontally across the camera view at constant camera depth. The video and poster were rendered again from the same sealed poses. No simulation, controller, registered threshold, original MJCF, matrix or original fault video was changed.

Local visual verification: at source 3.50 s (poster), the 299.0 µm needle tip aligns with the 300 µm marker; at playback 10.20 s / source 2.55 s (decoded frame 255), the 303.9 µm tip is also aligned within the expected subpixel projected error. Both the main and slow views were inspected. The 300 frames decode at 1280×720, 25 fps, 12 seconds; all 16 original fault media files are byte-identical and 116 local HTML links resolve. This records the local correction, not a fabricated external PASS. Claude's reply asks for this frame check and does not require a full re-review.
