"""M3: trace-only interactive explorer and 8-second schematic evidence videos."""

import argparse
import gzip
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

from .analyze import NAMES, UNITS, aggregate, load_sealed, specs, subset, worst


def trace(root, row, stem):
    raw = gzip.decompress((root / row[f"{stem}_path"]).read_bytes())
    assert hashlib.sha256(raw).hexdigest() == row[f"{stem}_sha256"]
    return [json.loads(line) for line in raw.splitlines()]


def explorer(matrix, summary, root):
    """One representative for each baseline severity: maximum RMS, seed tie break."""
    base = subset(matrix["runs"], controller="preview", ablation="baseline")
    cells = []
    for fault, spec in specs().items():
        for level in spec["levels"]:
            pooled = subset(base, fault=fault, level=level)
            row = worst(pooled)
            truth = trace(root, row, "truth")
            commands = trace(root, row, "trace")
            stride = 10
            # Metrics are always full-rate; curves explicitly decimated to 100 Hz.
            curves = [
                [
                    r["time_us"] / 1e6,
                    r["needle_z_m"] * 1e3,
                    r["tissue_z_m"] * 1e3,
                    r["e_m"] * 1e6,
                    commands[i]["command"]["force_n"],
                ]
                for i, r in enumerate(truth)
                if i % stride == 0 or i == len(truth) - 1
            ]
            cells.append(
                {
                    "fault": fault,
                    "name": NAMES[fault],
                    "level": level,
                    "unit": UNITS[fault],
                    "pooled_status": aggregate(pooled),
                    "pool_size": len(pooled),
                    "row": row,
                    "curves": curves,
                    "boundary": summary["boundaries"][fault]["first_fail"] == level,
                }
            )
    payload = json.dumps({"cells": cells, "sha": summary["matrix_sha256"]}, separators=(",", ":"))
    template = (Path(__file__).with_name("heatmap-template.html")).read_text(encoding="utf-8")
    (root / "heatmap.html").write_bytes(template.replace("__DATA__", payload).encode())
    return len(cells)


def videos(matrix, summary, root):
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    folder = root / "videos"
    folder.mkdir(exist_ok=True)
    font_path = "C:/Windows/Fonts/arial.ttf"
    font = ImageFont.truetype(font_path, 20)
    small = ImageFont.truetype(font_path, 16)
    title_font = ImageFont.truetype(font_path, 30)
    nominal = subset(matrix["runs"], controller="preview", ablation="baseline", fault="none")[0]
    normal = trace(root, nominal, "truth")
    lookup = {r["run_id"]: r for r in matrix["runs"]}
    manifest = []
    for fault, choice in summary["video_selection"].items():
        row = lookup[choice["run_id"]]
        faulty = trace(root, row, "truth")
        assert len(normal) == len(faulty) == 8000
        c = row["scenario"]
        needle = np.array([r["needle_z_m"] for r in faulty])
        tissue = np.array([r["tissue_z_m"] for r in faulty])
        nn = np.array([r["needle_z_m"] for r in normal])
        nt = np.array([r["tissue_z_m"] for r in normal])
        err = np.array([r["e_m"] * 1e6 for r in faulty])
        ne = np.array([r["e_m"] * 1e6 for r in normal])
        bottom = float(min(needle.min(), tissue.min(), nn.min(), nt.min()))
        top = float(max(needle.max(), tissue.max(), nn.max(), nt.max()))
        span = max(top - bottom, 0.001)
        bottom -= 0.08 * span
        top += 0.08 * span
        delta_n, delta_t = (needle - nn) * 1e6 * 100, (tissue - nt) * 1e6 * 100
        dmax = max(float(np.max(np.abs(delta_n))), float(np.max(np.abs(delta_t))), 1)
        emin, emax = min(float(err.min()), float(ne.min())), max(float(err.max()), float(ne.max()))
        espan = max(emax - emin, 1)
        emin -= 0.07 * espan
        emax += 0.07 * espan

        def pos(z):
            return round(385 - (z - bottom) / (top - bottom) * 205)

        def dy(z):
            return round(282 - z / dmax * 92)

        def ey(z):
            return round(627 - (z - emin) / (emax - emin) * 130)

        def ex(t):
            return round(105 + t / 8 * 1065)

        base = Image.new("RGB", (1280, 720), "#f6f7f3")
        d = ImageDraw.Draw(base)
        d.text((40, 22), f"{fault} / {NAMES[fault]}", font=title_font, fill="#183747")
        note = (
            "first pooled FAIL"
            if choice["boundary_observed"]
            else "no FAIL observed; strongest level"
        )
        d.text(
            (40, 64),
            f"{c['level']:g} {UNITS[fault]}  |  onset {c['onset_ms'] / 1000:g} s"
            f"  |  seed {c['seed']}  |  {note}",
            font=font,
            fill="#414d57",
        )
        for x, label in ((40, "NORMAL"), (450, "FAULT"), (860, "DELTA x100 / own axis")):
            d.rounded_rectangle(
                (x, 113, x + 380, 429), radius=12, fill="white", outline="#d6ddd9", width=2
            )
            d.text((x + 16, 128), label, font=font, fill="#183747")
        for x in (40, 450):
            d.text((x + 12, 164), f"{top * 1000:.2f} mm", font=small, fill="#606c71")
            d.text((x + 12, 369), f"{bottom * 1000:.2f} mm", font=small, fill="#606c71")
            d.line((x + 84, 183, x + 84, 385), fill="#dae0dc", width=2)
        d.text((873, 164), f"+/- {dmax:.1f} um after x100", font=small, fill="#606c71")
        d.line((950, dy(0), 1210, dy(0)), fill="#c9d1cf", width=2)
        d.text(
            (45, 446),
            "Instantaneous relative-position error (um) | full trace, not an RMS threshold",
            font=font,
            fill="#183747",
        )
        d.text(
            (45, 474),
            "Gray: normal | Orange: fault | Shaded: contact scoring window",
            font=small,
            fill="#526169",
        )
        d.rectangle((ex(3), 490, ex(8), 633), fill="#e7efeb")
        for t in range(9):
            d.line((ex(t), 490, ex(t), 633), fill="#d7ded9")
            d.text((ex(t) - 4, 639), str(t), font=small, fill="#525e62")
        for val in (emin, (emin + emax) / 2, emax):
            d.text((10, ey(val) - 8), f"{val:.1f}", font=small, fill="#525e62")
        d.text((1165, 640), "s", font=small, fill="#525e62")
        d.text(
            (40, 680),
            "Schematic from sealed measured traces • Windows SIL • "
            + summary["matrix_sha256"][:12],
            font=small,
            fill="#526169",
        )
        if fault == "F6":
            d.text((780, 680), "SIMULATED deadline miss; HIL required", font=small, fill="#a94f3b")
        fps = 24
        path = folder / f"{fault}.mp4"
        with imageio.get_writer(
            path, fps=fps, codec="libx264", quality=8, macro_block_size=16
        ) as writer:
            for frame in range(8 * fps):
                tick = min(round(frame / (8 * fps - 1) * 7999), 7999)
                im = base.copy()
                draw = ImageDraw.Draw(im)
                for x, n, t in ((40, nn[tick], nt[tick]), (450, needle[tick], tissue[tick])):
                    py, sy = pos(float(n)), pos(float(t))
                    draw.line((x + 230, 182, x + 230, py), fill="#ce7653", width=7)
                    draw.ellipse((x + 224, py - 6, x + 236, py + 6), fill="#bf573c")
                    draw.line((x + 100, sy, x + 344, sy), fill="#248e9b", width=4)
                    draw.text(
                        (x + 14, 397),
                        f"needle {n * 1000:.4f} / tissue {t * 1000:.4f} mm",
                        font=small,
                        fill="#526169",
                    )
                for x, val, color, label in (
                    (1000, delta_n[tick], "#bf573c", "needle"),
                    (1150, delta_t[tick], "#248e9b", "tissue"),
                ):
                    draw.line((x, dy(0), x, dy(float(val))), fill=color, width=5)
                    draw.ellipse((x - 6, dy(float(val)) - 6, x + 6, dy(float(val)) + 6), fill=color)
                    draw.text((x - 32, 393), label, font=small, fill=color)
                draw.text(
                    (920, 355),
                    f"actual delta e: {err[tick] - ne[tick]:+.3f} um",
                    font=small,
                    fill="#526169",
                )
                indices = list(range(0, tick + 1, 8))
                if indices[-1] != tick:
                    indices.append(tick)
                for values, color in ((ne, "#7c8d92"), (err, "#bf573c")):
                    points = [(ex(i / 1000), ey(float(values[i]))) for i in indices]
                    if len(points) > 1:
                        draw.line(points, fill=color, width=2)
                draw.line((ex(tick / 1000), 490, ex(tick / 1000), 633), fill="#233c52", width=2)
                draw.text(
                    (870, 450),
                    f"t={tick / 1000:.3f}s  e={err[tick]:+.2f} um",
                    font=small,
                    fill="#8b3f2c",
                )
                writer.append_data(np.asarray(im))
                if frame == 132:
                    im.save(folder / f"{fault}-preview.png")
        record = {
            "fault": fault,
            "run_id": row["run_id"],
            "normal_run_id": nominal["run_id"],
            "truth_sha256": row["truth_sha256"],
            "normal_truth_sha256": nominal["truth_sha256"],
            "frames": 192,
            "fps": 24,
            "duration_s": 8,
            "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        with imageio.get_reader(path) as reader:
            metadata = reader.get_meta_data()
            assert reader.count_frames() == 192
            assert metadata["fps"] == 24 and metadata["size"] == (1280, 720)
            assert abs(metadata["duration"] - 8) < 0.001
        record["decoded_verification"] = "192 frames / 24 fps / 1280x720 / 8 seconds"
        manifest.append(record)
        print(json.dumps(record), flush=True)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/c1"))
    args = parser.parse_args()
    matrix, digest = load_sealed(args.root)
    summary = json.loads((args.root / "summary.json").read_text())
    assert summary["matrix_sha256"] == digest
    cells = explorer(matrix, summary, args.root)
    video_records = videos(matrix, summary, args.root)
    assert load_sealed(args.root)[1] == digest
    record = {
        "matrix_sha256": digest,
        "simulations_executed": 0,
        "heatmap_cells": cells,
        "videos": video_records,
        "display_sampling": {"heatmap_ms": 10, "video_curve_ms": 8, "metrics_ms": 1},
        "visualization_environment": {
            "python": platform.python_version(),
            **{name: version(name) for name in ("pillow", "imageio", "imageio-ffmpeg")},
        },
        "visualize_source_sha256_lf": hashlib.sha256(
            Path(__file__).read_text(encoding="utf-8").encode()
        ).hexdigest(),
    }
    (args.root / "visualization-manifest.json").write_bytes(
        (json.dumps(record, indent=2) + "\n").encode()
    )


if __name__ == "__main__":
    main()
