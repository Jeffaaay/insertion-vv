"""Build the multimedia project journal from already sealed SIL evidence."""

import html
import json
from pathlib import Path

from .analyze import NAMES, load_sealed


def main():
    root = Path("artifacts/c1")
    _, digest = load_sealed(root)
    summary = json.loads((root / "summary.json").read_text())
    if summary["matrix_sha256"] != digest:
        raise ValueError("Journal summary does not belong to the sealed matrix")
    page = Path("c1/blog-template.html").read_text(encoding="utf-8")
    for fault, choice in summary["video_selection"].items():
        scenario = choice["scenario"]
        extent = (
            "首个观察到 FAIL 的档位"
            if choice["boundary_observed"]
            else "未观察到 FAIL，展示最强档位"
        )
        caption = (
            f"{fault} · {NAMES[fault]} · {extent} · 注入 {scenario['onset_ms'] / 1000:g} s"
            f" · seed {scenario['seed']} · 接触 RMS {choice['contact']['rms_e_um']:.3f} µm"
        )
        clip = (
            f'<figure class="clip"><video controls playsinline preload="none" '
            f'aria-label="{html.escape(caption)}" poster="videos/{fault}-preview.png" '
            f'src="videos/{fault}.mp4">浏览器无法播放时，'
            f'<a href="videos/{fault}.mp4">打开 MP4</a>。</video>'
            f"<figcaption>{html.escape(caption)}<br>"
            f"<small>run {choice['run_id']} · 8 s / 24 fps · "
            f'<a href="videos/{fault}.mp4">打开视频</a></small></figcaption></figure>'
        )
        page = page.replace(f"__VIDEO_{fault}__", clip)
    page = page.replace("__MATRIX_SHA__", digest)
    if "__VIDEO_" in page:
        raise ValueError("Unresolved journal media")
    (root / "blog.html").write_bytes(page.encode())
    print("Multimedia journal built from sealed evidence; 8 videos, no simulation")


if __name__ == "__main__":
    main()
