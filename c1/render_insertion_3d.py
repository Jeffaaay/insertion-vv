"""Render measured nominal poses in 3D without physics integration or control."""

import argparse
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

from .analyze import load_sealed, subset


def read_states(root, record):
    raw = gzip.decompress((root / record["truth_path"]).read_bytes())
    if hashlib.sha256(raw).hexdigest() != record["truth_sha256"]:
        raise ValueError("Sealed truth hash mismatch")
    states = [json.loads(line) for line in raw.splitlines()]
    if len(states) != 8000 or any(
        r["tick"] != i or r["time_us"] != i * 1000 for i, r in enumerate(states)
    ):
        raise ValueError("Expected 8,000 consecutive measured 1 ms states")
    return states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/c1"))
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--preview-time", type=float, default=3.5)
    args = parser.parse_args()
    root = args.root
    matrix, matrix_sha = load_sealed(root)
    record = subset(matrix["runs"], controller="preview", ablation="baseline", fault="none")[0]
    if record["verdict"]["status"] != "PASS" or not record["reproducible"]:
        raise ValueError("Expected complete, reproducible nominal PASS")
    states = read_states(root, record)
    plant = Path("sim/plant.xml")
    source_bytes = plant.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != matrix["source_files"]["sim/plant.xml"]:
        raise ValueError("MJCF does not match the recorded source inventory")

    import imageio.v2 as imageio
    import mujoco
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    # Visual changes exist only in a display copy; the original MJCF is untouched.
    xml = ET.fromstring(source_bytes)
    asset = ET.SubElement(xml, "asset")
    ET.SubElement(
        asset,
        "texture",
        name="display_sky",
        type="skybox",
        builtin="gradient",
        rgb1="0.88 0.93 0.92",
        rgb2="0.98 0.98 0.95",
        width="512",
        height="512",
    )
    display_xml = ET.tostring(xml, encoding="unicode")
    model = mujoco.MjModel.from_xml_string(display_xml)
    model.vis.global_.offwidth = 960
    model.vis.global_.offheight = 560
    model.vis.global_.fovy = 0.0049
    model.vis.global_.orthographic = 1
    model.vis.map.znear = 0.0001
    model.vis.map.zfar = 10
    model.vis.headlight.ambient[:] = (0.6, 0.6, 0.6)
    model.vis.headlight.diffuse[:] = (0.75, 0.75, 0.75)
    needle = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "needle_tip")
    tissue = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "tissue_surface")
    model.geom_rgba[needle] = (0.92, 0.43, 0.15, 1.0)
    model.geom_rgba[tissue] = (0.08, 0.58, 0.57, 0.28)
    model.geom_size[tissue] = (0.001, 0.00065, 0.0007)
    model.geom_pos[tissue] = (0, 0, -0.0007)
    data = mujoco.MjData(model)
    camera = mujoco.MjvCamera()
    camera.type = mujoco.mjtCamera.mjCAMERA_FREE
    camera.lookat[:] = (0, 0, 0.00035)
    camera.distance = 0.005
    camera.azimuth = 130
    camera.elevation = -18
    camera.orthographic = 1
    fonts = {}

    def font(size, bold=False):
        key = size, bold
        if key not in fonts:
            path = Path("C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf")
            if not path.exists():
                path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
            fonts[key] = ImageFont.truetype(str(path), size)
        return fonts[key]

    def line(scene, a, b, rgba, width=2):
        geom = scene.geoms[scene.ngeom]
        mujoco.mjv_initGeom(
            geom,
            mujoco.mjtGeom.mjGEOM_LINE,
            np.zeros(3),
            np.zeros(3),
            np.eye(3).ravel(),
            np.array(rgba),
        )
        mujoco.mjv_connector(geom, mujoco.mjtGeom.mjGEOM_LINE, width, np.array(a), np.array(b))
        scene.ngeom += 1

    def paint(renderer, tick, slow=False):
        row = states[tick]
        data.qpos[:] = row["needle_z_m"], row["tissue_z_m"]
        data.qvel[:] = row["needle_v_m_s"], row["tissue_v_m_s"]
        data.time = row["time_us"] / 1e6
        # Geometry transforms only. No mj_step, mj_forward, controller or force recomputation.
        mujoco.mj_kinematics(model, data)
        mujoco.mj_camlight(model, data)
        camera.lookat[2] = -0.00005 if slow else 0.00035
        model.vis.global_.fovy = 0.0038 if slow else 0.0049
        renderer.update_scene(data, camera)
        top = row["tissue_z_m"]
        bottom = top - 0.0014
        outline = (0.10, 0.42, 0.43, 0.75)
        corners = [(-0.001, -0.00065), (0.001, -0.00065), (0.001, 0.00065), (-0.001, 0.00065)]
        for i, (x, y) in enumerate(corners):
            nx, ny = corners[(i + 1) % 4]
            for z in (top, bottom):
                line(renderer.scene, (x, y, z), (nx, ny, z), outline)
            line(renderer.scene, (x, y, bottom), (x, y, top), outline)
        target = top - 0.0003
        for x in np.arange(-0.00095, 0.00095, 0.00018):
            line(
                renderer.scene,
                (x, -0.00068, target),
                (x + 0.0001, -0.00068, target),
                (0.83, 0.55, 0.12, 1.0),
                3,
            )
        # A fixed 500 um vertical reference gives the 3D view a physical scale.
        for y in (-0.00065, 0.00065):
            line(renderer.scene, (-0.001, y, top), (0.001, y, top), (0.05, 0.55, 0.55, 1), 3)
        frame = Image.new("RGB", (1280, 720), "#f9f8f1")
        frame.paste(Image.fromarray(renderer.render()), (0, 88))
        draw = ImageDraw.Draw(frame, "RGBA")
        draw.rectangle((0, 0, 960, 87), fill=(244, 248, 243, 239))
        draw.text((28, 15), "NEEDLE / MOVING TISSUE", font=font(27, True), fill="#213d3e")
        title = "INSERTION CLOSE-UP  /  0.25x replay" if slow else "3D recorded-state replay  /  1x"
        draw.text((28, 53), title, font=font(18), fill="#536d69")
        draw.line((960, 0, 960, 720), fill="#cbd9ce", width=2)
        draw.text((986, 28), "PREVIEW / NOMINAL", font=font(19, True), fill="#226b59")
        phase = (
            "APPROACH"
            if data.time < 1
            else "TRACK ABOVE SURFACE"
            if data.time < 2
            else "INSERTION"
            if data.time < 3
            else "FOLLOWING TISSUE"
        )
        draw.text((986, 67), phase, font=font(17, True), fill="#4e6663")
        values = [
            ("SOURCE TIME", f"{data.time:.2f} s"),
            ("TIP DEPTH", f"{(top - row['needle_z_m']) * 1e6:+.1f} um"),
            ("CONTACT FORCE", f"{row['contact_force_n'] * 1e3:.2f} mN"),
            ("RELATIVE ERROR", f"{row['e_m'] * 1e6:+.2f} um"),
        ]
        for i, (label, value) in enumerate(values):
            y = 126 + i * 101
            draw.text((986, y), label, font=font(14, True), fill="#66807a")
            draw.text((986, y + 26), value, font=font(29), fill="#233f40")
        draw.text((986, 540), "Final depth target: 300 um", font=font(18), fill="#8a6429")
        draw.text((986, 574), "Negative depth = above surface", font=font(15), fill="#5a6f69")
        draw.text(
            (986, 617),
            f"Contact RMS: {record['contact']['rms_e_um']:.3f} um",
            font=font(18),
            fill="#226b59",
        )
        draw.text((986, 650), "Original nominal verdict: PASS", font=font(15), fill="#226b59")
        draw.rectangle((0, 649, 960, 720), fill=(244, 248, 243, 244))
        draw.text(
            (25, 659),
            "Orange: capsule needle   Teal: tissue cutaway   Dashed: final depth target",
            font=font(17),
            fill="#294a46",
        )
        draw.text(
            (25, 688),
            "Measured poses / display-only cutaway / soft contact, not fluid or tissue fracture",
            font=font(15),
            fill="#59726c",
        )
        # Orthographic scale refers to world vertical projected into this camera view.
        bar = round(0.0005 / model.vis.global_.fovy * 560 * np.cos(np.deg2rad(18)))
        draw.line((70, 600, 70, 600 - bar), fill="#234e46", width=3)
        for y in (600, 600 - bar):
            draw.line((63, y, 77, y), fill="#234e46", width=3)
        draw.text((85, 590 - bar // 2), "500 um (vertical)", font=font(15), fill="#234e46")
        return np.asarray(frame)

    folder = root / "videos"
    folder.mkdir(exist_ok=True)
    output = folder / "insertion-3d.mp4"
    with mujoco.Renderer(model, height=560, width=960) as renderer:
        if args.preview:
            if not 0 <= args.preview_time < 8:
                parser.error("preview time must lie in [0, 8)")
            args.preview.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(paint(renderer, round(args.preview_time * 1000))).save(args.preview)
            print(args.preview)
            return
        # 8 seconds at 1x, then replay measured 2.000–2.990 s insertion at 0.25x.
        frames = [(tick, False) for tick in range(0, 8000, 40)]
        frames += [(tick, True) for tick in range(2000, 3000, 10)]
        with imageio.get_writer(
            str(output),
            fps=25,
            codec="libx264",
            quality=8,
            pixelformat="yuv420p",
            macro_block_size=1,
            output_params=["-movflags", "+faststart"],
        ) as writer:
            for tick, slow in frames:
                writer.append_data(paint(renderer, tick, slow))
        Image.fromarray(paint(renderer, 3500)).save(folder / "insertion-3d-preview.png")
    manifest = {
        "matrix_sha256": matrix_sha,
        "source_run_id": record["run_id"],
        "truth_sha256": record["truth_sha256"],
        "plant_sha256": source_sha,
        "renderer": "mujoco.Renderer",
        "mujoco_version": mujoco.__version__,
        "physics_integration": False,
        "controller_execution": False,
        "state_updates": "mj_kinematics + mj_camlight from measured qpos/qvel",
        "display_only": (
            "tissue cutaway dimensions/alpha, capsule color, skybox, camera, annotations"
        ),
        "needle_geometry": "unchanged original capsule; not a sharp-tip puncture model",
        "target_depth_um": 300,
        "fps": 25,
        "frames": len(frames),
        "duration_s": len(frames) / 25,
        "width": 1280,
        "height": 720,
        "segments": [
            {"playback_s": [0, 8], "source_tick_range": [0, 7960], "stride": 40, "speed": 1},
            {"playback_s": [8, 12], "source_tick_range": [2000, 2990], "stride": 10, "speed": 0.25},
        ],
        "interpolation": False,
        "limitations": (
            "Soft-contact block; no fluid, material tearing, puncture or real hardware video"
        ),
        "video_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    (root / "insertion-3d-manifest.json").write_bytes(
        (json.dumps(manifest, indent=2) + "\n").encode()
    )
    print(output)


if __name__ == "__main__":
    main()
