# Studio presentation review request

## User request

Improve the visual presentation toward the quality of an industrial robotics demonstration: apparatus context, materials, lighting, camera composition, and a clear insertion close-up. Keep the blog and GitHub record updated, and obtain external review.

## Change

The 3D introductory video is now a 1920×1080 Blender Cycles/OptiX render of the same sealed nominal poses. It starts with a conceptual one-axis stage and needle holder, moves into a locked contact close-up, and returns to the insertion interval in slow motion. Machined metal, soft studio light, a sample carrier, depth marker and a four-metric overlay replace the primitive diagnostic view.

The stage, carrier and slender pointed needle are illustrative geometry. Original physics still uses the unchanged capsule (0.25 mm radius) and soft-contact block. Source tip z and tissue-surface z are scaled uniformly by 1000 for Blender. There is no controller execution, integration, state interpolation, material deformation, tearing, fluid simulation, or hardware claim. Frame 48 hides the front sample half to reveal depth; this cutaway is labeled. The marker passes through the needle axis at source tissue_z − 300 µm and its overlay anchor is projected from that world point.

12 seconds / 25 fps / 300 frames: frames 0–199 sample ticks 0…7960 by 40; frames 200–299 sample ticks 2000…2990 by 10. The main sequence is 1× and the final sequence is 0.25×, with source time and speed displayed. The original matrix, original eight fault videos/posters and registered numerical code remain unchanged.

## Review focus

Check provenance and timing, the visual needle/physics distinction, cutaway and target projection, and whether the new apparatus, camera and typography make the process understandable. Inspect actual MP4 frames and both stills, not just code. Distinguish visual-quality comments from scientific validation. Do not request new physical experiments for this presentation-only change.
