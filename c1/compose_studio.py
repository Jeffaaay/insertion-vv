"""Overlay recorded metrics on Blender frames and encode the presentation video."""

import argparse
import hashlib
import json
from pathlib import Path

from .analyze import load_sealed, subset
from .render_insertion_3d import read_states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=Path, required=True)
    parser.add_argument("--preview", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    import imageio.v2 as imageio
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    root = Path("artifacts/c1")
    matrix, matrix_sha = load_sealed(root)
    record = subset(matrix["runs"], controller="preview", ablation="baseline", fault="none")[0]
    states = read_states(root, record)
    meta = {}
    blender_version = None
    for path in args.frames.glob("render-*.json"):
        chunk = json.loads(path.read_text())
        if (
            chunk["matrix_sha256"] != matrix_sha
            or chunk["truth_sha256"] != record["truth_sha256"]
            or chunk["source_run_id"] != record["run_id"]
            or chunk["plant_sha256"] != matrix["source_files"]["sim/plant.xml"]
        ):
            raise ValueError("Rendered source does not match sealed nominal run")
        blender_version = chunk["blender_version"]
        for frame in chunk["frames"]:
            meta[frame["frame"]] = frame
    fonts = {}

    def font(size, bold=False):
        key = size, bold
        if key not in fonts:
            name = "segoeuib.ttf" if bold else "segoeui.ttf"
            path = Path("C:/Windows/Fonts") / name
            if not path.exists():
                path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            fonts[key] = ImageFont.truetype(str(path), size)
        return fonts[key]

    white, muted, teal, amber = "#eff7f5", "#a2b9bd", "#66e2c9", "#ffc178"

    def paint(index):
        info = meta[index]
        tick = index * 40 if index < 200 else 2000 + (index - 200) * 10
        if info["tick"] != tick:
            raise ValueError("Frame/source tick mismatch")
        row = states[tick]
        frame = Image.open(args.frames / f"{index:04d}.png").convert("RGB")
        if args.preview is None and frame.size != (1920, 1080):
            raise ValueError("Final video requires native 1920x1080 rendered frames")
        frame = frame.resize((1920, 1080), Image.Resampling.LANCZOS)
        overlay = Image.new("RGBA", frame.size)
        draw = ImageDraw.Draw(overlay)
        # Restrained edge gradients keep the apparatus visible and type readable.
        for y in range(150):
            draw.line((0, y, 1919, y), fill=(5, 14, 21, round(190 * (1 - y / 150))))
        draw.rounded_rectangle(
            (48, 881, 1872, 1010),
            radius=15,
            fill=(7, 20, 27, 236),
            outline=(99, 135, 143, 70),
            width=1,
        )
        draw.text((66, 41), "INSERTION / V&V", font=font(24, True), fill=white)
        draw.text(
            (66, 77), "RECORDED MUJOCO STATES  /  STUDIO VISUALIZATION", font=font(15), fill=muted
        )
        draw.rounded_rectangle((1537, 38, 1853, 83), radius=22, fill=(15, 47, 46, 230))
        draw.ellipse((1559, 54, 1569, 64), fill=teal)
        draw.text((1584, 47), "NOMINAL  ·  SEALED REPLAY", font=font(17, True), fill=teal)
        slow = index >= 200
        phase = (
            "APPROACH"
            if tick < 1000
            else "SURFACE TRACKING"
            if tick < 2000
            else "INSERTION"
            if tick < 3000
            else "MOTION FOLLOWING"
        )
        if index < 26:
            draw.text(
                (66, 202), "Precision\nin motion.", font=font(76, True), fill=white, spacing=2
            )
            draw.text((69, 404), "A one-axis control experiment.", font=font(25), fill=muted)
            draw.text((69, 444), "Approach. Insert. Follow.", font=font(25), fill=muted)
        elif index >= 48:
            draw.text(
                (66, 170),
                "02 / INSERTION DETAIL" if slow else "01 / RECORDED MOTION",
                font=font(18, True),
                fill=teal,
            )
            draw.text(
                (64, 210), "Stay with\nthe surface.", font=font(52, True), fill=white, spacing=0
            )
            draw.text((66, 350), "CUTAWAY VIEW", font=font(18, True), fill=muted)
            draw.text(
                (66, 384),
                "The front half is hidden\nto reveal tip depth.",
                font=font(21),
                fill=muted,
                spacing=7,
            )
            p = info["projected"]["target"]
            x, y = p[0] * 1920, p[1] * 1080
            draw.ellipse((x - 5, y - 5, x + 5, y + 5), outline=amber, width=2)
            draw.line((x + 12, y, x + 80, y, x + 105, y - 32), fill=amber, width=2)
            draw.rounded_rectangle(
                (x + 105, y - 55, x + 366, y - 13), radius=6, fill=(9, 24, 29, 230)
            )
            draw.text((x + 118, y - 49), "TARGET DEPTH  300 µm", font=font(20, True), fill=amber)
        draw.rounded_rectangle((48, 810, 423, 858), radius=9, fill=(7, 20, 27, 210))
        draw.rounded_rectangle((1473, 810, 1854, 858), radius=9, fill=(7, 20, 27, 210))
        draw.rectangle((0, 1021, 1920, 1080), fill=(7, 20, 27, 230))
        draw.text((66, 818), phase, font=font(24, True), fill=white)
        draw.text(
            (1495, 818),
            "0.25×  /  SLOW REPLAY" if slow else "1×  /  ORIGINAL TIMING",
            font=font(20, True),
            fill=teal,
        )
        values = [
            ("SOURCE TIME", f"{tick / 1000:.2f}", "s"),
            ("TIP DEPTH", f"{(row['tissue_z_m'] - row['needle_z_m']) * 1e6:+.1f}", "µm"),
            ("CONTACT FORCE", f"{row['contact_force_n'] * 1000:.2f}", "mN"),
            ("RELATIVE ERROR", f"{row['e_m'] * 1e6:+.2f}", "µm"),
        ]
        for i, (name, value, unit) in enumerate(values):
            x = 80 + i * 455
            if i:
                draw.line((x - 31, 908, x - 31, 980), fill=(108, 144, 151, 70), width=1)
            draw.text((x, 900), name, font=font(16, True), fill=muted)
            draw.text((x, 929), value, font=font(39), fill=white)
            width = draw.textlength(value, font=font(39))
            draw.text((x + width + 14, 945), unit, font=font(22), fill=teal)
        draw.text(
            (66, 1031),
            "Illustrative apparatus & needle silhouette  ·  "
            "Source physics: capsule / soft-contact block  ·  No hardware or puncture claim",
            font=font(18),
            fill=muted,
        )
        # Timeline is source time; the slow replay deliberately returns to 2 s.
        draw.line((66, 865, 1853, 865), fill=(121, 153, 158, 60), width=3)
        draw.line((66, 865, 66 + 1787 * tick / 8000, 865), fill=teal, width=3)
        return np.asarray(Image.alpha_composite(frame.convert("RGBA"), overlay).convert("RGB"))

    if args.preview is not None:
        if args.output is None:
            parser.error("--preview requires --output")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(paint(args.preview)).save(args.output)
        print(args.output)
        return
    if set(meta) != set(range(300)):
        raise ValueError("Expected exactly 300 rendered source frames")
    output = root / "videos/insertion-3d.mp4"
    with imageio.get_writer(
        output,
        fps=25,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
        output_params=["-movflags", "+faststart"],
    ) as writer:
        for index in range(300):
            writer.append_data(paint(index))
    Image.fromarray(paint(90)).save(root / "videos/insertion-3d-preview.png")
    Image.fromarray(paint(0)).save(root / "videos/insertion-3d-overview.png")
    manifest = {
        "matrix_sha256": matrix_sha,
        "source_run_id": record["run_id"],
        "truth_sha256": record["truth_sha256"],
        "plant_sha256": matrix["source_files"]["sim/plant.xml"],
        "renderer": "Blender Cycles / OptiX + Pillow metric overlay",
        "blender_version": blender_version,
        "physics_integration": False,
        "controller_execution": False,
        "state_updates": (
            "measured needle_z and tissue_z; meters to millimeters with uniform factor 1000"
        ),
        "display_only": (
            "conceptual stage, collet, carrier, needle silhouette, sample crop, "
            "materials, lights, cutaway and camera"
        ),
        "needle_geometry": (
            "illustrative sharp silhouette; original sealed physics uses a 0.25 mm radius "
            "capsule, not puncture physics"
        ),
        "target_depth_um": 300,
        "target_marker": (
            "3D line passes through needle axis at tissue_z - 300 um; "
            "overlay anchor projected from that same point"
        ),
        "fps": 25,
        "frames": 300,
        "duration_s": 12,
        "width": 1920,
        "height": 1080,
        "segments": [
            {"playback_s": [0, 8], "source_tick_range": [0, 7960], "stride": 40, "speed": 1},
            {"playback_s": [8, 12], "source_tick_range": [2000, 2990], "stride": 10, "speed": 0.25},
        ],
        "interpolation": False,
        "camera_animation": (
            "smoothstep apparatus-to-macro transition during frames 25-48; fixed macro thereafter"
        ),
        "cutaway": "front sample half hidden from frame 48 onward; surface z is unchanged",
        "limitations": (
            "No measured hardware design, material deformation, fluid, tearing, "
            "puncture or new simulation results"
        ),
        "video_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    (root / "insertion-3d-manifest.json").write_bytes(
        (json.dumps(manifest, indent=2) + "\n").encode()
    )
    print(output)


if __name__ == "__main__":
    main()
