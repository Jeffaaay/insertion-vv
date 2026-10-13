"""Render recorded review files as an escaped, static, local HTML timeline.

This tool does not invoke reviewers or infer a gate verdict. Browser captures
remain labeled browser captures, rather than fabricated CLI event streams.
"""

import argparse
import html
import re
from pathlib import Path


def render(root: Path, output: Path) -> None:
    blocks = []
    for milestone in ("G", "M0", "M1", "M2", "M3", "M4", "Journal", "Scene3D"):
        directory = root / milestone
        if not directory.is_dir():
            continue
        cards = []
        for path in sorted(directory.iterdir(), key=lambda p: p.name):
            if path.suffix not in (".md", ".txt", ".json", ".jsonl"):
                continue
            text = path.read_text(encoding="utf-8-sig")
            tone = "escalate" if path.name == "ESCALATION.md" else "record"
            explicit = re.findall(r'"verdict"\s*:\s*"(PASS|BLOCK|ESCALATE)"', text)
            if explicit:
                tone = explicit[-1].lower()
            # Data/tool records are collapsed; prose remains immediately visible.
            opened = "" if path.suffix in (".json", ".jsonl") else " open"
            cards.append(
                f'<details class="{tone}"{opened}><summary>'
                f"{html.escape(path.name)}</summary><pre>"
                f"{html.escape(text)}</pre></details>"
            )
        blocks.append(f"<section><h2>{milestone}</h2>{''.join(cards)}</section>")
    page = """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Phase C SIL — review evidence</title>
<style>body{max-width:1050px;margin:40px auto;padding:0 20px;background:#f5f6fa;
color:#172235;font:16px/1.65 system-ui}h1{font-size:28px}details{background:white;
padding:16px 20px;margin:16px 0;border-left:4px solid #4879ad;border-radius:8px}
details.escalate{border-color:#c56c20;background:#fff6e9}
details.pass{border-color:#2d8878;background:#f2faf6}
details.block{border-color:#c45343;background:#fff4f0}summary{cursor:pointer;
font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.6
ui-monospace,monospace}header p{color:#556477}</style><header>
<h1>Phase C SIL · 审阅记录</h1><p>事实、外部反馈和未决项。记录存在不代表里程碑通过。
工具与数据记录默认折叠；网页回复不冒充 CLI 日志。</p></header>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page + "".join(blocks) + "</html>", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("reviews"))
    parser.add_argument("--output", type=Path, default=Path("reviews/index.html"))
    args = parser.parse_args()
    render(args.root, args.output)
