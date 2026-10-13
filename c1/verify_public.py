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
    assert manifest["matrix_sha256"] == digest
    for name, record in manifest["files"].items():
        data = (root / name).read_bytes()
        assert len(data) == record["bytes"]
        assert hashlib.sha256(data).hexdigest() == record["sha256"], name
    for name, expected in manifest["render_source_sha256_lf"].items():
        data = Path(name).read_text(encoding="utf-8").encode()
        assert hashlib.sha256(data).hexdigest() == expected, name
    lookup = {r["run_id"]: r for r in matrix["runs"]}
    with zipfile.ZipFile(root / "selected-traces.zip") as archive:
        assert len(archive.infolist()) == 27
        for item in archive.infolist():
            if item.filename.endswith(".jsonl.gz"):
                rid = item.filename.split("/")[1]
                stem = item.filename.split("/")[-1].split(".")[0]
                assert hashlib.sha256(gzip.decompress(archive.read(item))).hexdigest() == (
                    lookup[rid][stem + "_sha256"]
                )
    print(f"Public matrix, {len(manifest['files'])} artifacts, source hashes and 9-run subset PASS")


if __name__ == "__main__":
    main()
