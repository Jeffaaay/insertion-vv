"""Verify the committed public evidence package, including normalized source hashes."""

import gzip
import hashlib
import json
import zipfile
from pathlib import Path

from .analyze import load_sealed


def main():
    root = Path("artifacts/c1")
    matrix, digest = load_sealed(root)
    manifest = json.loads((root / "derived-artifacts.json").read_text())
    if manifest["matrix_sha256"] != digest:
        raise ValueError("manifest/matrix seal mismatch")
    for name, record in manifest["files"].items():
        data = (root / name).read_bytes()
        if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError(f"artifact size/hash mismatch: {name}")
    for name, expected in manifest["render_source_sha256_lf"].items():
        data = Path(name).read_text(encoding="utf-8").encode()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"source hash mismatch: {name}")
    lookup = {r["run_id"]: r for r in matrix["runs"]}
    intro_path = root / "insertion-3d-manifest.json"
    if intro_path.exists():
        intro = json.loads(intro_path.read_text())
        source = lookup[intro["source_run_id"]]
        if (
            intro["matrix_sha256"] != digest
            or intro["truth_sha256"] != source["truth_sha256"]
            or intro["plant_sha256"] != matrix["source_files"]["sim/plant.xml"]
            or source["scenario"]["fault"] != "none"
            or source["scenario"]["controller"] != "preview"
            or source["scenario"]["ablation"] != "baseline"
        ):
            raise ValueError("3D introduction source mismatch")
        video_sha = hashlib.sha256((root / "videos/insertion-3d.mp4").read_bytes()).hexdigest()
        if video_sha != intro["video_sha256"]:
            raise ValueError("3D introduction video mismatch")
        frames = 0
        for segment in intro["segments"]:
            start, end = segment["source_tick_range"]
            count = (end - start) // segment["stride"] + 1
            duration = segment["playback_s"][1] - segment["playback_s"][0]
            if (
                start < 0
                or end >= 8000
                or (end - start) % segment["stride"]
                or count != duration * intro["fps"]
                or segment["stride"] * intro["fps"] / 1000 != segment["speed"]
            ):
                raise ValueError("3D introduction playback mapping mismatch")
            frames += count
        if frames != intro["frames"] or frames / intro["fps"] != intro["duration_s"]:
            raise ValueError("3D introduction duration mismatch")
    with zipfile.ZipFile(root / "selected-traces.zip") as archive:
        if len(archive.infolist()) != 27:
            raise ValueError("selected archive inventory mismatch")
        for item in archive.infolist():
            if item.filename.endswith(".jsonl.gz"):
                rid = item.filename.split("/")[1]
                stem = item.filename.split("/")[-1].split(".")[0]
                actual = hashlib.sha256(gzip.decompress(archive.read(item))).hexdigest()
                if actual != lookup[rid][stem + "_sha256"]:
                    raise ValueError(f"selected trace hash mismatch: {item.filename}")
    print(f"Public matrix, {len(manifest['files'])} artifacts, source hashes and 9-run subset PASS")


if __name__ == "__main__":
    main()
