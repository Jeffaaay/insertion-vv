"""Blender offline renderer for sealed poses; run with blender -b --python ... -- ..."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from c1.analyze import load_sealed, subset  # noqa: E402
from c1.render_insertion_3d import read_states  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, default=300)
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Reuse completed PNGs in this folder")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])
    import bpy
    from bpy_extras.object_utils import world_to_camera_view
    from mathutils import Vector

    from c1.studio_scene import build, set_pose

    root = ROOT / "artifacts/c1"
    matrix, matrix_sha = load_sealed(root)
    record = subset(matrix["runs"], controller="preview", ablation="baseline", fault="none")[0]
    states = read_states(root, record)
    plant_sha = hashlib.sha256((ROOT / "sim/plant.xml").read_bytes()).hexdigest()
    if plant_sha != matrix["source_files"]["sim/plant.xml"]:
        raise ValueError("Original plant does not match sealed source")
    objects = build()
    scene, camera, *_ = objects
    if args.quick:
        scene.cycles.samples = 12
        scene.render.resolution_percentage = 67
    args.output.mkdir(parents=True, exist_ok=True)
    frames = list(range(0, 8000, 40)) + list(range(2000, 3000, 10))
    meta = []
    for index in range(args.start, args.end):
        tick = frames[index]
        row = states[tick]
        set_pose(objects, row, index)
        scene.render.filepath = str((args.output / f"{index:04d}.png").resolve())
        if not args.resume or not Path(scene.render.filepath).exists():
            bpy.ops.render.render(write_still=True)
        projected = {}
        for name, point in {
            "tip": (0, 0, row["needle_z_m"] * 1000),
            "surface": (0, 0, row["tissue_z_m"] * 1000),
            "target": (0, 0, row["tissue_z_m"] * 1000 - 0.3),
        }.items():
            p = world_to_camera_view(scene, camera, Vector(point))
            projected[name] = [p.x, 1 - p.y]
        meta.append({"frame": index, "tick": tick, "projected": projected})
        print(f"STUDIO_FRAME {index + 1}/300", flush=True)
    manifest = {
        "matrix_sha256": matrix_sha,
        "source_run_id": record["run_id"],
        "truth_sha256": record["truth_sha256"],
        "plant_sha256": plant_sha,
        "blender_version": bpy.app.version_string,
        "frames": meta,
    }
    (args.output / f"render-{args.start}-{args.end}.json").write_text(
        json.dumps(manifest, indent=2)
    )


if __name__ == "__main__":
    main()
