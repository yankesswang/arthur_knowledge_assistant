#!/usr/bin/env python3
"""
check_reading_list.py

功能一（預設）：掃描 待閱讀清單.md 的所有 [[wikilink]]，
  檢查 vault 內是否有對應 .md 檔案，輸出斷連報告。

功能二（--check-urls）：對斷連項目進行二次比對，
  用 grep 一次掃描 vault 所有 source URL，
  找出「檔名不同但 URL 有對應」的筆記。

功能三（--url <URL>）：直接查某個 URL 在 vault 是否已有筆記。

用法：
  python3 check_reading_list.py                        # 快速掃描（只比檔名）
  python3 check_reading_list.py --check-urls           # 含 URL 二次比對（較慢）
  python3 check_reading_list.py --dry-run              # 只印終端，不寫檔
  python3 check_reading_list.py --url <URL>            # 查單一 URL
"""

import re
import argparse
from pathlib import Path
from datetime import date

VAULT_ROOT   = Path("/Users/yankesswang/Documents/arthurwang_DB")
READING_LIST = VAULT_ROOT / "待閱讀清單.md"
OUTPUT_FILE  = VAULT_ROOT / "待閱讀清單斷連筆記.md"

WIKILINK_RE = re.compile(r'\[\[([^\]|#]+)')


# ─── 工具 ────────────────────────────────────────────────────────────────────

def normalise_url(url: str) -> str:
    return url.split("?")[0].split("#")[0].rstrip("/").lower()


# ─── Vault 索引 ──────────────────────────────────────────────────────────────

def build_name_index(vault: Path) -> set[str]:
    """收集所有 .md 檔名（不讀內容，很快）。"""
    return {p.stem for p in vault.rglob("*.md")}


SOURCE_RE = re.compile(r'^source:\s*["\']?(https?://[^\s"\']+)["\']?', re.MULTILINE)


def _read_source_url(path: Path) -> tuple[Path, str | None]:
    """讀取單一檔案的 frontmatter source URL（只讀前 30 行）。"""
    try:
        lines = []
        with path.open(encoding="utf-8", errors="ignore") as f:
            for i, line in enumerate(f):
                if i >= 30:
                    break
                lines.append(line)
                if i > 0 and line.strip() == "---":
                    break
        head = "".join(lines)
        m = SOURCE_RE.search(head)
        return path, m.group(1).strip() if m else None
    except Exception:
        return path, None


def mdfind_by_keywords(vault: Path, keywords: list[str], max_results: int = 5) -> list[Path]:
    """
    用 Spotlight 搜尋 vault 中包含這些關鍵字的 .md 檔（不讀檔案內容）。
    每次 ~0.5–1 秒。
    """
    import subprocess
    query = " ".join(keywords[:3])
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", str(vault), query],
            capture_output=True, text=True, timeout=10
        )
        hits = [Path(l) for l in result.stdout.splitlines() if l.endswith(".md")]
        return hits[:max_results]
    except Exception:
        return []


# ─── 清單解析 ────────────────────────────────────────────────────────────────

def extract_wikilinks(filepath: Path) -> list[tuple[str, str]]:
    results = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        for m in WIKILINK_RE.finditer(line):
            title = m.group(1).strip()
            if title:
                results.append((line.strip(), title))
    return results


def classify_line(line: str) -> str:
    return "[x]" if ("- [x]" in line or "- [X]" in line) else "[ ]"


def group_entries(entries: list[tuple]) -> dict[str, list[tuple]]:
    text      = READING_LIST.read_text(encoding="utf-8")
    title_map = {title: (status, extra) for status, title, extra in entries}
    current   = "未分類"
    groups: dict[str, list] = {}
    for line in text.splitlines():
        if line.startswith("### "):
            current = line.lstrip("# ").strip()
        elif line.startswith("## "):
            current = line.lstrip("# ").strip()
        for m in WIKILINK_RE.finditer(line):
            title = m.group(1).strip()
            if title in title_map:
                status, extra = title_map[title]
                groups.setdefault(current, []).append((status, title, extra))
    return groups


# ─── 報告 ────────────────────────────────────────────────────────────────────

def build_report(truly_missing: dict, renamed: dict, total: int) -> str:
    today     = date.today().strftime("%Y-%m-%d")
    n_missing = sum(len(v) for v in truly_missing.values())
    n_renamed = sum(len(v) for v in renamed.values())

    lines = [
        "---",
        "title: 待閱讀清單斷連筆記",
        f"date: {today}",
        "tags:",
        "  - 維護",
        "  - 閱讀清單",
        "---",
        "",
        "# 待閱讀清單斷連筆記",
        "",
        f"> 掃描 `待閱讀清單.md`，共 {total} 個 wikilink。",
        f"> - **真正缺失**（vault 無此筆記）：{n_missing} 筆",
        *(
            [f"> - **檔名不符**（URL 有對應但檔名不同）：{n_renamed} 筆"]
            if n_renamed else []
        ),
        "",
        "---",
        "",
    ]

    if truly_missing:
        lines += ["## ❌ 真正缺失（需補建或從清單刪除）", ""]
        for section, items in truly_missing.items():
            lines.append(f"### {section}（{len(items)} 筆）")
            lines.append("")
            for status, title, _ in items:
                suffix = " *(已讀但無筆記)*" if status == "[x]" else ""
                lines.append(f"- {status} [[{title}]]{suffix}")
            lines.append("")

    if renamed:
        lines += ["## ⚠️ 檔名不符（vault 有相同 source URL 的筆記）", ""]
        for section, items in renamed.items():
            lines.append(f"### {section}（{len(items)} 筆）")
            lines.append("")
            for status, title, existing_path in items:
                lines.append(f"- {status} [[{title}]]")
                lines.append(f"  → 現有筆記：`{existing_path}`")
            lines.append("")

    lines += ["---", "", f"*掃描日期：{today}*"]
    return "\n".join(lines)


# ─── --url 查詢 ──────────────────────────────────────────────────────────────

def search_by_url(url: str) -> Path | None:
    """
    用 mdfind 搜尋含此 URL 的筆記（< 1 秒）。
    找到後讀 frontmatter 確認 source: 欄位。
    """
    import subprocess
    key = normalise_url(url)
    # 取 URL 的最後一段作為搜尋詞（去掉 https://domain/ 前綴雜訊）
    search_term = key.split("/")[-1] or key.split("/")[-2]
    try:
        result = subprocess.run(
            ["mdfind", "-onlyin", str(VAULT_ROOT), search_term],
            capture_output=True, text=True, timeout=10
        )
        hits = [Path(l) for l in result.stdout.splitlines() if l.endswith(".md")]
        # 優先找 frontmatter 有 source: 且 URL 相符的
        for p in hits:
            _, found_url = _read_source_url(p)
            if found_url and key in normalise_url(found_url):
                return p
        # 退而求其次：有 URL 關鍵字的任何筆記
        return hits[0] if hits else None
    except Exception:
        return None


# ─── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run",    action="store_true", help="只印出，不寫入檔案")
    parser.add_argument("--check-urls", action="store_true", help="對斷連項目進行 source URL 二次比對（較慢）")
    parser.add_argument("--url",        metavar="URL",       help="直接查某個 URL 是否已有筆記")
    args = parser.parse_args()

    # ── 模式 A：URL 直接查詢 ──
    if args.url:
        print(f"搜尋 URL：{args.url}")
        result = search_by_url(args.url)
        if result:
            try:
                rel = result.relative_to(VAULT_ROOT)
            except ValueError:
                rel = result
            print(f"✓ 找到對應筆記：{rel}")
        else:
            print(f"✗ 找不到 source URL 為 {args.url} 的筆記")
        return

    # ── 模式 B：掃描清單 ──
    print(f"建立檔名索引：{VAULT_ROOT}")
    name_index = build_name_index(VAULT_ROOT)
    print(f"Vault 共 {len(name_index)} 個 .md 檔案")

    print(f"讀取清單：{READING_LIST}")
    entries = extract_wikilinks(READING_LIST)
    total   = len({title for _, title in entries})
    print(f"唯一 wikilink：{total} 個")

    # 找出所有缺失（去重）
    seen: set[str] = set()
    missing: list[tuple[str, str]] = []
    for line, title in entries:
        if title not in seen and title not in name_index:
            seen.add(title)
            missing.append((line, title))

    print(f"檔名比對後缺失：{len(missing)} 個")

    truly_missing_entries: list[tuple] = []
    renamed_entries:       list[tuple] = []

    if args.check_urls and missing:
        print(f"Spotlight 搜尋 {len(missing)} 個斷連標題（每筆 ~1s）...")
        for line, title in missing:
            status   = classify_line(line)
            keywords = [w for w in re.findall(r'[\w一-鿿]{2,}', title) if not w[0].isdigit()]
            hits     = mdfind_by_keywords(VAULT_ROOT, keywords[:3]) if keywords else []
            # 檢查命中的檔案是否有對應的 source URL（快讀 frontmatter）
            matched = None
            for p in hits:
                if p.stem != title:  # 排除檔名完全相同的（不會走到這裡）
                    _, url = _read_source_url(p)
                    if url:
                        matched = p
                        break
            if matched:
                try:
                    rel = str(matched.relative_to(VAULT_ROOT))
                except ValueError:
                    rel = str(matched)
                renamed_entries.append((status, title, rel))
            else:
                truly_missing_entries.append((status, title, None))
    else:
        for line, title in missing:
            status = classify_line(line)
            truly_missing_entries.append((status, title, None))

    print(f"真正缺失：{len(truly_missing_entries)} 筆 | 檔名不符：{len(renamed_entries)} 筆")

    truly_missing_groups = group_entries(truly_missing_entries) if truly_missing_entries else {}
    renamed_groups       = group_entries(renamed_entries)       if renamed_entries       else {}
    report               = build_report(truly_missing_groups, renamed_groups, total)

    if args.dry_run:
        print("\n" + report)
    else:
        OUTPUT_FILE.write_text(report, encoding="utf-8")
        print(f"\n報告已寫入：{OUTPUT_FILE}")

    # 終端摘要
    if truly_missing_entries:
        print("\n=== ❌ 真正缺失 ===")
        for section, items in truly_missing_groups.items():
            print(f"\n【{section}】")
            for status, title, _ in items:
                print(f"  {status} {title}")

    if renamed_entries:
        print("\n=== ⚠️ 檔名不符（URL 有對應） ===")
        for section, items in renamed_groups.items():
            print(f"\n【{section}】")
            for status, title, path in items:
                print(f"  {status} {title}")
                print(f"       → {path}")


if __name__ == "__main__":
    main()
