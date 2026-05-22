#!/usr/bin/env python3
"""
generate_note.py — 讀取 analysis.json + info.json → 輸出 Obsidian 投資筆記
用法：python3 generate_note.py <work_dir>
輸出：依 note_type 決定格式，寫入 note_path.txt 記錄路徑
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path


SKILL_DIR = Path(__file__).parent.parent
CONFIG_PATH = SKILL_DIR / "config" / "podcasts.json"


def load_config(podcast_id: str) -> dict:
    cfg = json.loads(CONFIG_PATH.read_text())
    pod = next((p for p in cfg["podcasts"] if p["id"] == podcast_id), None)
    if not pod:
        raise ValueError(f"Podcast '{podcast_id}' 不在 config/podcasts.json")
    return pod


def yq(x: str) -> str:
    return json.dumps(str(x), ensure_ascii=False)


def generate_investment_note(data: dict, info: dict, pod_cfg: dict, today: str) -> str:
    """投資 Podcast 筆記格式（依 note-investment.md 規範）"""
    title_zh     = data.get("title_zh", info.get("title", "Unknown"))
    topic        = data.get("topic", "")
    tags         = data.get("tags", [])
    stocks       = data.get("stocks", [])
    tldr         = data.get("tldr", {})
    sections     = data.get("sections", [])
    key_insights = data.get("key_insights", [])
    data_table   = data.get("data_table", [])
    frameworks   = data.get("investment_framework", {})
    source_url   = info.get("rss", pod_cfg.get("rss", ""))

    # Frontmatter
    tag_lines = [f"  - {t}" for t in (["台股", "Podcast", pod_cfg["name"]] + tags)]
    stock_lines = [f"  - {s}" for s in stocks]

    lines = [
        "---",
        f"title: {yq(title_zh)}",
        f"date: {yq(today)}",
        f"source: {yq(pod_cfg['name'])}",
        f"topic: {yq(topic)}",
        "tags:",
    ] + tag_lines

    if stocks:
        lines += ["stocks:"] + stock_lines

    lines += [
        f"url: {yq(source_url)}",
        "---",
        "",
    ]

    # TL;DR
    lines += ["## TL;DR", ""]
    for label, key in [
        ("核心主張", "核心主張"),
        ("關鍵機制", "關鍵機制_問題"),
        ("重要數字", "重要數字"),
        ("風險 / 限制", "風險_限制"),
        ("操作建議", "操作建議"),
    ]:
        val = tldr.get(key, "")
        if val:
            if isinstance(val, list):
                lines.append(f"- **{label}**：")
                for item in val:
                    lines.append(f"    - {item}")
            else:
                lines.append(f"- **{label}**：{val}")
    lines.append("")

    # 節目資訊
    lines += [
        "## 節目資訊", "",
        "| 欄位 | 內容 |", "| ---- | ---- |",
        f"| 頻道 | {pod_cfg['name']} |",
        f"| 集數 | {info.get('episode', '')} |",
        f"| 時長 | {info.get('duration', '')} |",
        f"| 發布 | {info.get('upload_date', '')} |",
        "",
    ]

    # 章節筆記
    lines += ["## 章節筆記", ""]
    for i, sec in enumerate(sections):
        start  = sec.get("start_time", "")
        title_s = sec.get("title", f"段落 {i+1}")
        points  = sec.get("content_points", [])
        header = f"### {i+1}."
        if start:
            header += f" [{start}]"
        header += f" {title_s}"
        lines.append(header)
        lines.append("")
        for pt in points:
            lines.append(pt)
        lines.append("")

    # 關鍵洞見
    if key_insights:
        lines += ["## 關鍵洞見", ""]
        for ins in key_insights:
            lines.append(f"- {ins}")
        lines.append("")

    # 投資框架
    if frameworks:
        lines += ["## 投資框架", ""]
        for horizon, content in frameworks.items():
            lines.append(f"### {horizon}")
            lines.append("")
            lines.append("```")
            if isinstance(content, dict):
                for k, v in content.items():
                    lines.append(f"{k}：{v}")
            else:
                lines.append(str(content))
            lines.append("```")
            lines.append("")

        risks = data.get("risks", [])
        if risks:
            lines.append("> [!warning]")
            lines.append("> **核心風險**")
            lines.append("> ")
            for r in risks:
                lines.append(f"> - {r}")
            lines.append("")

    # 數據速查
    lines += ["## 附：關鍵數據速查", ""]
    if data_table:
        lines += ["| 指標 | 數值 | 備註 |", "| ---- | ---- | ---- |"]
        for row in data_table:
            lines.append(f"| {row.get('指標','')} | {row.get('數值','')} | {row.get('備註','')} |")
    else:
        lines += ["| 指標 | 數值 | 備註 |", "| ---- | ---- | ---- |",
                  "| （本集無具體數字） | — | — |"]
    lines.append("")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("用法：generate_note.py <work_dir>", file=sys.stderr)
        sys.exit(1)

    work_dir = Path(sys.argv[1])
    analysis_path = work_dir / "analysis.json"
    info_path     = work_dir / "info.json"

    if not analysis_path.exists():
        print(f"ERROR: 找不到 {analysis_path}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(analysis_path.read_text())
    info = json.loads(info_path.read_text()) if info_path.exists() else {}

    podcast_id = os.environ.get("PODCAST_ID", "gooaye")
    pod_cfg    = load_config(podcast_id)

    today      = date.today().isoformat()
    title_zh   = data.get("title_zh", info.get("title", "Unknown"))
    note_type  = data.get("note_type", "investment")
    note_dir   = Path(pod_cfg.get("note_dir", "/home/trx50/Documents/arthurwang_DB/投資"))

    if note_type == "investment":
        content = generate_investment_note(data, info, pod_cfg, today)
    else:
        # 預留：其他格式（tech note 等）
        content = generate_investment_note(data, info, pod_cfg, today)

    safe_title = re.sub(r'[/\\:*?"<>|]', ' ', title_zh).strip()
    safe_title = re.sub(r'\s+', ' ', safe_title)[:120]
    note_path  = note_dir / f"{safe_title}.md"

    # 避免覆蓋已存在的筆記
    if note_path.exists():
        ep = info.get("episode", "ep")
        note_path = note_dir / f"{safe_title} - {ep}.md"

    note_path.write_text(content, encoding="utf-8")
    (work_dir / "note_path.txt").write_text(str(note_path), encoding="utf-8")
    print(f"筆記已寫入：{note_path}")


if __name__ == "__main__":
    main()
