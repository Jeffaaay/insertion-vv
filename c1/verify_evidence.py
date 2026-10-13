"""Verify all retained evidence against the sealed matrix without simulation."""

import argparse
import gzip
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .analyze import load_sealed, specs


def check_run(args):
    root, row = args
    size = 0
    for stem in ("trace", "truth"):
        path = root / row[f"{stem}_path"]
        size += path.stat().st_size
        data = gzip.decompress(path.read_bytes())
        assert hashlib.sha256(data).hexdigest() == row[f"{stem}_sha256"], path
        assert data.count(b"\n") == row["completed_ticks"], path
    return size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/c1"))
    args = parser.parse_args()
    matrix, digest = load_sealed(args.root)
    rows = matrix["runs"]
    assert len(rows) == len({r["run_id"] for r in rows}) == 3615
    main_rows = [r for r in rows if r["scenario"]["controller"] in ("preview", "preview_c32")]
    assert len(main_rows) == 3564
    registered = specs()
    for row in main_rows:
        c = row["scenario"]
        if c["fault"] != "none":
            spec = registered[c["fault"]]
            assert (
                c["level"] in spec["levels"]
                and c["onset_ms"] in spec["onsets_ms"]
                and c["seed"] in spec["seeds"]
            )
    with ThreadPoolExecutor(max_workers=8) as pool:
        size = sum(pool.map(check_run, [(args.root, r) for r in rows]))
    report = {
        "matrix_sha256": digest,
        "run_count": len(rows),
        "verified_gzip_files": len(rows) * 2,
        "verified_compressed_bytes": size,
        "hash_and_linecount": "PASS",
    }
    (args.root / "evidence-audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
