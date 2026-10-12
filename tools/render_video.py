"""Offscreen MuJoCo replay of saved truth states: 20 fps, 8 s by default.

This manual visualization never steps physics or imports a controller. Visual
geometry/camera changes affect only an in-memory display copy of the MJCF.
"""

import argparse
import hashlib
import json
from pathlib import Path

from _run_artifact import REPO, default_output, load_run, provenance


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fps", type=int, default=20)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--preview", type=Path, help="Optional single-frame PNG for manual review")
    parser.add_argument("--preview-time", type=float, default=5.1)
    args = parser.parse_args()
    metrics, config, rows = load_run(args.run)
    if args.fps <= 0 or 1_000_000 % args.fps:
        parser.error("fps must divide one million microseconds")
    frame_us = 1_000_000 // args.fps
    if frame_us % metrics["control_dt_us"] or config["parameters"]["duration_us"] % frame_us:
        parser.error("frame times must coincide with recorded ticks and cover the whole run")
    if args.width % 2 or args.height % 2 or args.width < 640 or args.height < 360:
        parser.error("H.264 dimensions must be even and at least 640 x 360")

    import imageio.v2 as imageio
    import mujoco
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    output = (args.output or default_output(metrics, "mp4")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    model_path = REPO / "sim" / "plant.xml"
    if hashlib.sha256(model_path.read_bytes()).hexdigest() != config["mjcf_sha256"]:
        raise ValueError("Current plant.xml does not match this run's recorded MJCF")
    model = mujoco.MjModel.from_xml_path(str(model_path))
    model.pair_solref[0] = config["contact"]["solref"]
    model.pair_solimp[0] = config["contact"]["solimp"]
    model.vis.global_.offwidth = args.width
    model.vis.global_.offheight = args.height
    model.vis.global_.orthographic = 1
    model.vis.global_.ipd = 0
    model.vis.map.znear = 0.0001
    model.vis.map.zfar = 10
    model.vis.headlight.ambient[:] = (0.55, 0.55, 0.55)
    model.vis.headlight.diffuse[:] = (0.8, 0.8, 0.8)
    needle = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "needle_tip")
    tissue = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "tissue_surface")
    model.geom_rgba[needle] = (1.0, 0.40, 0.13, 1.0)
    model.geom_rgba[tissue] = (0.08, 0.68, 0.79, 0.35)
    # A visual cutaway through the original box; recorded tissue top is unchanged.
    model.geom_size[tissue] = (0.0012, 0.00012, 0.001)
    model.geom_pos[tissue] = (0, 0, -0.001)
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = (0, 0, 0.00010)
    camera.distance = 0.0032
    camera.azimuth = 90
    camera.elevation = 0
    camera.orthographic = 1
    model.vis.global_.fovy = 0.00265  # Orthographic vertical field of view, metres.
    target_depth = config["parameters"]["insertion_depth_m"]
    scale = args.width / 1280
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")

    def font(size):
        for candidate in (font_path, Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
            if candidate.exists():
                return ImageFont.truetype(str(candidate), round(size * scale))
        return ImageFont.load_default(size=round(size * scale))

    def connector(scene, start, end, rgba, width=3):
        geom = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(
            geom,
            mujoco.mjtGeom.mjGEOM_LINE,
            np.zeros(3),
            np.zeros(3),
            np.eye(3).ravel(),
            np.array(rgba),
        )
        mujoco.mjv_connector(
            geom, mujoco.mjtGeom.mjGEOM_LINE, width * scale, np.array(start), np.array(end)
        )
        scene.ngeom += 1

    def paint(renderer, row):
        data.qpos[:] = (row["needle_z_m"], row["tissue_z_m"])
        data.qvel[:] = (row["needle_v_m_s"], row["tissue_v_m_s"])
        data.time = row["time_us"] / 1e6
        mujoco.mj_forward(model, data)  # Refresh display state; no integration or controller.
        renderer.update_scene(data, camera)
        surface = row["tissue_z_m"]
        depth_z = surface - target_depth
        yellow = (1.0, 0.84, 0.25, 1.0)
        cyan = (0.20, 0.87, 0.92, 1.0)
        connector(renderer.scene, (-0.0011, -0.0002, surface), (0.0011, -0.0002, surface), cyan, 2)
        for x in np.arange(-0.0011, 0.0011, 0.00016):
            connector(
                renderer.scene, (x, -0.00025, depth_z), (x + 0.00009, -0.00025, depth_z), yellow, 3
            )
        connector(
            renderer.scene, (0.00070, -0.00025, surface), (0.00070, -0.00025, depth_z), yellow, 3
        )
        for z in (surface, depth_z):
            connector(renderer.scene, (0.00064, -0.00025, z), (0.00076, -0.00025, z), yellow, 3)
        frame = Image.fromarray(renderer.render())
        draw = ImageDraw.Draw(frame, "RGBA")

        def sx(n):
            return round(n * scale)

        draw.rounded_rectangle(
            (sx(22), sx(20), sx(360), sx(181)), radius=sx(12), fill=(13, 26, 44, 236)
        )
        draw.text(
            (sx(40), sx(33)),
            "LAB-FRAME PD"
            if metrics["controller"] == "lab_frame_pd"
            else metrics["controller"].upper(),
            font=font(18),
            fill=(180, 200, 218),
        )
        for i, text in enumerate(
            (
                f"t   {data.time:5.2f} s",
                f"e   {row['e_m'] * 1e6:+8.1f} µm",
                f"F   {row['contact_force_n'] * 1e3:8.3f} mN",
            )
        ):
            draw.text((sx(40), sx(65 + 33 * i)), text, font=font(25), fill="white")
        # Match the orthographic camera's world-to-pixel vertical mapping.
        mid_z = surface - target_depth / 2
        label_y = (
            args.height / 2 - (mid_z - camera.lookat[2]) / model.vis.global_.fovy * args.height
        )
        draw.text(
            (sx(840), int(label_y - sx(15))),
            f"{target_depth * 1e6:.0f} µm target depth",
            font=font(22),
            fill=(255, 219, 88),
            stroke_width=1,
            stroke_fill=(20, 25, 30),
        )
        phase = (
            "FREE-SPACE WINDOW"
            if 1 <= data.time < 2
            else "CONTACT WINDOW"
            if 3 <= data.time < 8
            else "APPROACH / TRANSITION"
        )
        draw.text((sx(820), sx(32)), phase, font=font(19), fill=(221, 231, 240))
        draw.rectangle((0, args.height - sx(76), args.width, args.height), fill=(13, 26, 44, 240))
        draw.text(
            (sx(28), args.height - sx(64)),
            "Orange: needle   Cyan: tissue   Yellow: 300 µm below moving surface",
            font=font(19),
            fill=(228, 236, 246),
        )
        draw.text(
            (sx(28), args.height - sx(33)),
            f"{metrics['contact_profile']}  •  seed {metrics['seed']}  •  "
            "recorded-state replay  •  visual cutaway",
            font=font(16),
            fill=(170, 190, 210),
        )
        # A physical 0.5 mm vertical scale, distinct from the target marker.
        bar_x = args.width - sx(52)
        bar_y = args.height - sx(160)
        bar_h = round(0.0005 / model.vis.global_.fovy * args.height)
        draw.line((bar_x, bar_y, bar_x, bar_y - bar_h), fill="white", width=sx(3))
        for y in (bar_y, bar_y - bar_h):
            draw.line((bar_x - sx(8), y, bar_x + sx(8), y), fill="white", width=sx(2))
        draw.text(
            (bar_x - sx(115), bar_y - bar_h // 2 - sx(10)), "500 µm", font=font(20), fill="white"
        )
        return np.array(frame)

    with mujoco.Renderer(model, height=args.height, width=args.width) as renderer:
        if args.preview:
            if not 0 <= args.preview_time < metrics["duration_s"]:
                parser.error("preview time must be inside the run")
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            tick = int(args.preview_time * 1e6 / metrics["control_dt_us"])
            Image.fromarray(paint(renderer, rows[tick])).save(args.preview)
            print(args.preview.resolve())
            return
        count = round(metrics["duration_s"] * args.fps)
        with imageio.get_writer(
            str(output),
            fps=args.fps,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
            macro_block_size=1,
            output_params=["-movflags", "+faststart"],
        ) as writer:
            for i in range(count):
                writer.append_data(paint(renderer, rows[i * frame_us // metrics["control_dt_us"]]))
    manifest = {
        **provenance(metrics, args.run),
        "renderer": "mujoco.Renderer",
        "fps": args.fps,
        "frames": count,
        "duration_s": count / args.fps,
        "width": args.width,
        "height": args.height,
        "target_depth_um": target_depth * 1e6,
        "display_only": "Contrasting colors, translucent tissue cutaway, fixed orthographic camera",
    }
    output.with_suffix(".video.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(output)


if __name__ == "__main__":
    main()
