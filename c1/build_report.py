"""Render the repository's one-page Markdown summary as a portable print page."""

import html
import json
import re
from pathlib import Path

from .analyze import NAMES


def inline(text):
    text = html.escape(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", text)


def main():
    text = Path("docs/PHASE_C_SIL_SUMMARY.md").read_text(encoding="utf-8")
    blocks = []
    for block in text.strip().split("\n\n"):
        if block.startswith("# "):
            blocks.append("<h1>" + inline(block[2:]) + "</h1>")
        elif block.startswith("|"):
            rows = block.splitlines()

            def cells(row):
                return [inline(x.strip()) for x in row.strip("|").split("|")]

            table = "<table><thead><tr>" + "".join("<th>" + x + "</th>" for x in cells(rows[0]))
            table += "</tr></thead><tbody>"
            for row in rows[2:]:
                table += "<tr>" + "".join("<td>" + x + "</td>" for x in cells(row)) + "</tr>"
            blocks.append(table + "</tbody></table>")
        else:
            blocks.append("<p>" + inline(block.replace("\n", " ")) + "</p>")
    style = """
*{box-sizing:border-box}body{margin:0;background:#e9ede8;color:#263c43;
font:13px/1.38 Georgia,'Times New Roman',serif}.paper{width:794px;min-height:1123px;
margin:25px auto;padding:36px 40px;background:#fffef9}h1{font:700 26px/1.2 Arial;
letter-spacing:-.7px;margin:0 0 17px}p{margin:12px 0}table{width:100%;border-collapse:
collapse;font:11.4px/1.3 Arial}th,td{padding:7px 5px;text-align:left;border-bottom:
1px solid #d9dfd8}th{background:#e5ede6;color:#244e4b}td:nth-child(n+3){white-space:
nowrap;text-align:right}strong{color:#173d3b}code{font-size:11px}.brand{font:10px Arial;
letter-spacing:2px;color:#5b7972;margin-bottom:11px}.links{font:12px Arial;margin-top:18px;
padding-top:10px;border-top:1px solid #ccc}a{color:#21696f}@page{size:A4;margin:0}
@media print{body{background:white}.paper{margin:0;width:210mm;min-height:297mm;
padding:10mm}.links{display:none}}@media screen and (max-width:820px){.paper{margin:0;width:100%;
min-height:0;padding:24px}table{font-size:10px}th,td{padding:5px 3px}}
"""
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><title>Phase C SIL report</title>'
    page += (
        '<meta name="viewport" content="width=device-width,initial-scale=1"><style>'
        + style
        + "</style>"
    )
    page += '<article class="paper"><div class="brand">INSERTION V&amp;V / SEALED EVIDENCE</div>'
    page += "".join(blocks)
    page += '<div class="links"><a href="index.html">Evidence hub</a> · '
    page += '<a href="heatmap.html">Interactive heatmap</a> · <a href="blog.html">Blog post</a>'
    page += "</div></article></html>"
    Path("artifacts/c1/report.html").write_bytes(page.encode())
    build_hub()


def build_hub():
    root = Path("artifacts/c1")
    summary = json.loads((root / "summary.json").read_text())
    template = Path("c1/hub-template.html").read_text(encoding="utf-8")
    titles = [
        "故障档位与误差余量",
        "注入时刻与接触 RMS",
        "哪些消融改变结论",
        "四个控制器的同档位对照",
        "留给 HIL 的问题",
    ]
    cards = []
    for title, path in zip(titles, sorted((root / "figs").glob("*.png"))):
        name = "figs/" + path.name
        cards.append(
            f'<figure><a href="{name}"><img src="{name}" alt="{title}"></a>'
            f'<figcaption>{title} · <a href="{name}">PNG</a> · '
            f'<a href="{name[:-4]}.svg">SVG</a></figcaption></figure>'
        )
    clips = []
    for fault, choice in summary["video_selection"].items():
        scenario = choice["scenario"]
        label = (
            "首个汇总 FAIL 档位" if choice["boundary_observed"] else "未观察到 FAIL；展示最强档位"
        )
        clips.append(
            f'<figure><video controls preload="metadata" poster="videos/{fault}-preview.png" '
            f'src="videos/{fault}.mp4"></video><figcaption><b>{fault} · {NAMES[fault]}</b><br>'
            f"{label} · 注入 {scenario['onset_ms'] / 1000:g} s · seed {scenario['seed']}"
            f"<br><small>run {choice['run_id']}</small></figcaption></figure>"
        )
    page = template.replace("__FIGURES__", "".join(cards)).replace("__VIDEOS__", "".join(clips))
    page = page.replace("__MATRIX_SHA__", summary["matrix_sha256"])
    (root / "index.html").write_bytes(page.encode())


if __name__ == "__main__":
    main()
