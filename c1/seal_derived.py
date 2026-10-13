"""Canonicalize text, package public trace subset, and pin all derived artifact bytes."""

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from .analyze import load_sealed, subset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/c1"))
    parser.add_argument("--archive", type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    matrix, digest = load_sealed(root)
    summary = json.loads((root / "summary.json").read_text())
    ids = {r["run_id"] for r in summary["video_selection"].values()}
    ids.add(
        subset(matrix["runs"], controller="preview", ablation="baseline", fault="none")[0]["run_id"]
    )
    with zipfile.ZipFile(root / "selected-traces.zip", "w", compression=zipfile.ZIP_STORED) as z:
        for rid in sorted(ids):
            for name in ("trace.jsonl.gz", "truth.jsonl.gz", "metrics.json"):
                path = root / "runs" / rid / name
                z.write(path, path.relative_to(root))
    paths = [
        *root.glob("*.json"),
        *root.glob("*.html"),
        *root.glob("*.zip"),
        *root.glob("*.sha256"),
        *root.glob("figs/*"),
        *root.glob("videos/*"),
    ]
    paths = sorted(p for p in paths if p.is_file() and p.name != "derived-artifacts.json")
    for path in paths:
        if path.suffix in (".json", ".html", ".svg", ".sha256"):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    assert load_sealed(root)[1] == digest
    with args.archive.open("rb") as stream:
        archive_hash = hashlib.file_digest(stream, "sha256").hexdigest()
    sources = [
        Path("c1") / name
        for name in ("analyze.py", "visualize.py", "heatmap-template.html", "seal_derived.py")
    ]
    sources += [
        p
        for p in (
            Path("c1/build_report.py"),
            Path("c1/hub-template.html"),
            Path("docs/PHASE_C_SIL_SUMMARY.md"),
            Path("docs/FINDINGS.md"),
        )
        if p.is_file()
    ]
    manifest = {
        "matrix_sha256": digest,
        "analysis_introduced_commit": "d0b86986c7677985ccae5d358b3a3c2ba7128672",
        "annotation_analysis_base_commit": "ca5e99a8721c8eb721d0b321c64db99c1d7b1c07",
        "text_encoding": "UTF-8, LF; identical to Git blob bytes",
        "render_source_sha256_lf": {
            p.as_posix(): hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest()
            for p in sources
        },
        "files": {
            p.relative_to(root).as_posix(): {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "bytes": p.stat().st_size,
            }
            for p in paths
        },
        "full_evidence_archive": {
            "file": args.archive.name,
            "sha256": archive_hash,
            "bytes": args.archive.stat().st_size,
            "location": "local deliverables, not git",
        },
    }
    (root / "derived-artifacts.json").write_bytes((json.dumps(manifest, indent=2) + "\n").encode())
    document = Path("docs/C1_SIL_PREDICTIONS.md")
    text = document.read_text(encoding="utf-8")
    before, table = text.split("| Derived artifact | SHA-256 |", 1)
    _, after = table.split("\n\nReview interpretation:", 1)
    body = "| Derived artifact | SHA-256 |\n|---|---|\n"
    for name, value in manifest["files"].items():
        if name in ("summary.json", "selected-traces.zip") or name.startswith("figs/"):
            body += f"| `{name}` | `{value['sha256']}` |\n"
    document.write_bytes((before + body + "\nReview interpretation:" + after).encode())
    print(f"Canonical derived seal: {len(paths)} files; matrix unchanged")


if __name__ == "__main__":
    main()
