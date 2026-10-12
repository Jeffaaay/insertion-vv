# Run comparison and optional visualization

## Cross-platform comparison (CI; standard library only)

```text
python tools/compare_traces.py artifacts/linux artifacts/windows --matrix --output artifacts/cross-platform/comparison.json
python tools/compare_traces.py artifacts/linux/primary/delayed_feedback artifacts/windows/primary/delayed_feedback
```

Inputs can be run directories or their `trace.jsonl` paths; keep `config.json`,
`metrics.json`, `repeat_trace.jsonl` and `truth.jsonl` alongside each trace. Use
new runs containing `platform_fingerprint`. The tool verifies integrity and identical
source/config/experiment identity, exact timing/discrete values and verdicts, then
all trace/truth signals with strict position/velocity/force tolerances of
1e-12 m / 1e-9 m/s / 1e-12 N. Physical metric relative differences must be <1e-9;
both-zero metrics yield zero relative error, one-zero pairs yield one. Timing,
UUIDs and OS descriptions are excluded. With equal fingerprints, bitwise trace
and truth equality is still required. Exit codes: 0 agreement, 1 mismatch,
2 INVALID evidence. Full details and up to 20 first mismatches go into the JSON report.

## Optional visualization (never required by CI)

Use a separate Python environment. None of these packages is added to the test
requirements, and neither tool is imported or executed by the simulation or CI.
Use the downloaded **Linux** run artifacts for canonical reporting, even when
rendering locally on Windows. Rendering does not rerun the recorded experiment.

```powershell
python -m venv artifacts/viz-env
artifacts/viz-env/Scripts/python -m pip install -r tools/requirements-viz.txt
artifacts/viz-env/Scripts/python tools/render_video.py --run artifacts/primary/lab_frame_pd
artifacts/viz-env/Scripts/python tools/plot_run.py --run artifacts/primary/lab_frame_pd
```

Select an existing run directory containing `metrics.json`, `config.json`,
`truth.jsonl` and `trace.jsonl`. Both tools validate the saved hashes and read
measurements; neither reruns a controller. Default outputs are
`artifacts/viz/{controller}_{contact_profile}_seed{seed}.mp4` and `.png`.
Use `--output` to choose another path. JSON sidecars record the source run and hashes.

The video uses `mujoco.Renderer` in an offscreen OpenGL context, without a viewer.
It needs a working OpenGL backend on the machine where the manual command runs;
on Linux a supported EGL/OSMesa backend may be selected with `MUJOCO_GL`.
The default is exactly 160 frames at 20 fps (8 s, samples at 0 through 7.95 s).
The fixed camera shows physical millimetre-scale motion. Orange is the original
capsule needle; the cyan translucent box is a **display-only cutaway** of the tissue.
The moving yellow marker stays 300 µm below the measured tissue surface, including
during approach; it indicates the final target depth, not the time-varying approach
reference. HUD errors and forces are the original evaluator's recorded values.
The on-disk MJCF, states, controllers and metrics are never modified.

The PNG plots all 8,000 truth samples, with ±20 µm and ±2 mm/s reference bands and
the original evaluation windows. The error band is an instantaneous visual aid;
the task's placement acceptance uses **contact-window RMS**, not an all-ticks bound.

For a quick camera review without encoding the video:

```powershell
python tools/render_video.py --run artifacts/primary/lab_frame_pd --preview preview.png --preview-time 5.1
```
