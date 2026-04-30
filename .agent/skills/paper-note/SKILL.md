---
name: paper-note
description: Given an arXiv URL or ID, fetch the full paper, download all figures, and generate a complete Obsidian note following Arthur's note-paper.md format.
---

# /paper-note

Given an arXiv paper URL or ID, automatically:
1. Fetch full paper content from arXiv HTML version
2. Download all figures to the Obsidian vault
3. Generate a complete formatted note following `note-paper.md` standard
4. Save to vault

## Usage

```
/paper-note https://arxiv.org/abs/2604.02460
/paper-note https://arxiv.org/pdf/2604.02460v2
/paper-note 2604.02460
```

## Vault Paths

- **Notes**: `/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/論文筆記/`
- **Figures**: `/Users/yankesswang/Documents/arthurwang_DB/` (vault root — where Obsidian saves attachments by default)

---

## What You Must Do When Invoked

Follow these steps in order. Do not skip or reorder.

---

### Step 1 — Parse arXiv ID

Extract a clean arXiv ID from the input:

- `https://arxiv.org/abs/2604.02460` → `2604.02460`
- `https://arxiv.org/pdf/2604.02460v2` → `2604.02460v2`
- `2604.02460` → use as-is

```bash
ARXIV_ID="<extracted_id>"
ARXIV_ID_SAFE=$(echo "$ARXIV_ID" | tr './' '__')
NOTE_DIR="/home/trx50/Documents/arthurwang_DB/AI Knowledge/論文筆記"
VAULT_ROOT="/home/trx50/Documents/arthurwang_DB"
echo "ID: $ARXIV_ID  |  safe: $ARXIV_ID_SAFE"
```

---

### Step 2 — Fetch full paper text

**Primary path**: Try arXiv HTML version first (available ~24–48h after submission):

```bash
curl -L -A "Mozilla/5.0" "https://arxiv.org/html/$ARXIV_ID" -o /tmp/arxiv_paper_raw.html 2>/tmp/arxiv_curl_err.txt
# Check if we got a real HTML page (not a 404)
if grep -q "ltx_document\|ltx_paper\|arxiv-paper" /tmp/arxiv_paper_raw.html 2>/dev/null; then
    echo "HTML version available"
    HTML_AVAILABLE=1
else
    echo "HTML version not available, downloading PDF"
    HTML_AVAILABLE=0
fi
```

**If HTML available**: Extract text from HTML with Python:

```bash
python3 << 'PYEOF'
from html.parser import HTMLParser
import re, sys

with open("/tmp/arxiv_paper_raw.html", encoding="utf-8", errors="ignore") as f:
    html = f.read()

# Strip scripts/styles, extract text
text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL|re.IGNORECASE)
text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL|re.IGNORECASE)
text = re.sub(r"<[^>]+>", " ", text)
text = re.sub(r"\s{3,}", "\n\n", text)
with open("/tmp/arxiv_paper.txt", "w") as f:
    f.write(text.strip())
print(f"Extracted {len(text)} chars from HTML")
PYEOF
```

**If HTML unavailable (PDF fallback)**: Download PDF and extract with pdfplumber:

```bash
VENV_PYTHON="/home/trx50/Project/arthur_knowledge_assistant/.venv/bin/python3"

# Download PDF
curl -L -A "Mozilla/5.0" "https://arxiv.org/pdf/$ARXIV_ID" -o /tmp/arxiv_paper.pdf

# Extract text with pdfplumber
$VENV_PYTHON << 'PYEOF'
import pdfplumber, sys

with pdfplumber.open("/tmp/arxiv_paper.pdf") as pdf:
    text = ""
    for i, page in enumerate(pdf.pages):
        t = page.extract_text()
        if t:
            text += f"\n--- Page {i+1} ---\n{t}"
with open("/tmp/arxiv_paper.txt", "w") as f:
    f.write(text)
print(f"Extracted {len(text)} chars from PDF ({len(pdf.pages)} pages)")
PYEOF
```

Read `/tmp/arxiv_paper.txt`. Extract:
- Title, authors, affiliation, date, arXiv ID
- Abstract
- All section content (Introduction, Method, Experiments, Discussion, Conclusion)
- All table data
- Figure captions (you'll cross-reference these with downloaded images in Step 3)

---

### Step 3 — Extract figures

**Path A — arXiv HTML available**: Download figure images from HTML:

```bash
python3 << 'PYEOF'
import re, sys, os, json, urllib.request, urllib.parse

arxiv_id = os.environ.get("ARXIV_ID", "")
arxiv_id_safe = os.environ.get("ARXIV_ID_SAFE", "")
vault_root = "/home/trx50/Documents/arthurwang_DB"

with open("/tmp/arxiv_paper_raw.html", encoding="utf-8", errors="ignore") as f:
    html = f.read()
base_url = f"https://arxiv.org/html/{arxiv_id}/"

results = []
figure_blocks = re.findall(r"<figure\b[^>]*>(.*?)</figure>", html, re.DOTALL | re.IGNORECASE)
if not figure_blocks:
    figure_blocks = [html]

fig_num = 0
for block in figure_blocks:
    imgs = re.findall(r'<img\b[^>]+src=["\']([^"\']+)["\']', block, re.IGNORECASE)
    if not imgs:
        continue
    cap_match = re.search(r"<figcaption[^>]*>(.*?)</figcaption>", block, re.DOTALL | re.IGNORECASE)
    caption = ""
    if cap_match:
        caption = re.sub(r"<[^>]+>", "", cap_match.group(1))
        caption = re.sub(r"\s+", " ", caption).strip()
    for src in imgs[:1]:
        fig_num += 1
        # arXiv HTML img src may include version prefix like "2604.19572v1/x1.png"
        # Strip it so we don't double-path: base_url already contains the version
        src_clean = re.sub(r'^[\d.]+v\d+/', '', src)
        url = base_url + src_clean if not src_clean.startswith("http") else src_clean
        ext = os.path.splitext(src_clean.split("?")[0])[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            ext = ".png"
        filename = f"{arxiv_id_safe}_fig{fig_num:02d}{ext}"
        try:
            urllib.request.urlretrieve(url, os.path.join(vault_root, filename))
            results.append({"num": fig_num, "filename": filename, "caption": caption})
            print(f"  ✓ fig{fig_num:02d}: {filename}", file=sys.stderr)
        except Exception as e:
            print(f"  ✗ fig{fig_num:02d} failed: {e}", file=sys.stderr)
            results.append({"num": fig_num, "filename": None, "caption": caption})
        if fig_num >= 20:
            break
    if fig_num >= 20:
        break
import json
print(json.dumps(results))
PYEOF
```

**Path B — PDF only**: Three-stage approach: TeX source originals → smart page crop for the rest.

**Stage B-1: Download TeX source and extract original figure files (highest quality)**

```bash
VENV_PYTHON="/home/trx50/Project/arthur_knowledge_assistant/.venv/bin/python3"

mkdir -p /tmp/arxiv_src
curl -L -A "Mozilla/5.0" "https://arxiv.org/src/$ARXIV_ID" -o /tmp/arxiv_src.tar.gz -s

# Try to extract (arXiv source is usually .tar.gz but sometimes plain .gz or .pdf)
tar -xzf /tmp/arxiv_src.tar.gz -C /tmp/arxiv_src 2>/dev/null || \
tar -xf  /tmp/arxiv_src.tar.gz -C /tmp/arxiv_src 2>/dev/null

find /tmp/arxiv_src -type f | sort
```

Then parse the `.tex` file to find `\includegraphics` references and map them to figure numbers:

```bash
$VENV_PYTHON << 'PYEOF'
import re, os, shutil, json
import pypdfium2 as pdfium

src_dir = "/tmp/arxiv_src"
vault_root = "/home/trx50/Documents/arthurwang_DB"
arxiv_id_safe = os.environ.get("ARXIV_ID_SAFE", "")

# Read the main .tex file
tex_files = [f for f in os.listdir(src_dir) if f.endswith(".tex")]
tex_content = ""
for tf in tex_files:
    with open(os.path.join(src_dir, tf), encoding="utf-8", errors="ignore") as f:
        tex_content += f.read()

# Find figure environments and their \includegraphics
# Pattern: \begin{figure}...\includegraphics{file}...\caption{...} or vice versa
figure_envs = re.findall(
    r'\\begin\{figure[^}]*\}(.*?)\\end\{figure[^}]*\}',
    tex_content, re.DOTALL
)

saved = {}
fig_counter = 0
for env in figure_envs:
    fig_counter += 1
    inc_match = re.search(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', env)
    if not inc_match:
        continue
    src_file_base = inc_match.group(1).strip()
    # Try with and without extension
    found_path = None
    for ext in ["", ".pdf", ".png", ".jpg", ".eps"]:
        candidate = os.path.join(src_dir, src_file_base + ext)
        if os.path.exists(candidate):
            found_path = candidate
            break
    if not found_path:
        continue

    dest = os.path.join(vault_root, f"{arxiv_id_safe}_fig{fig_counter:02d}.png")
    ext_lower = os.path.splitext(found_path)[1].lower()
    if ext_lower == ".png":
        shutil.copy(found_path, dest)
        saved[fig_counter] = dest
        print(f"  ✓ fig{fig_counter:02d}: copied {os.path.basename(found_path)}", flush=True)
    elif ext_lower in (".pdf", ".eps"):
        doc = pdfium.PdfDocument(found_path)
        page = doc[0]
        bm = page.render(scale=3.0)
        img = bm.to_pil()
        img.save(dest)
        saved[fig_counter] = dest
        print(f"  ✓ fig{fig_counter:02d}: {os.path.basename(found_path)} → {img.size}", flush=True)

print(json.dumps({"saved": list(saved.keys())}))
PYEOF
```

**Stage B-2: Smart-crop remaining figures from PDF pages**

For figures not found in TeX source (TikZ-generated graphics), use pdfplumber to locate the caption and vector objects, then crop precisely:

```bash
$VENV_PYTHON << 'PYEOF'
import pdfplumber, pypdfium2 as pdfium, re, os, json, sys
from PIL import Image

pdf_path = "/tmp/arxiv_paper.pdf"
arxiv_id_safe = os.environ.get("ARXIV_ID_SAFE", "")
vault_root = "/home/trx50/Documents/arthurwang_DB"

# Read already-saved fig numbers from Stage B-1
already_saved = set()  # populate from B-1 output if available

# Find all figure pages (caption text)
figure_pages = {}
with pdfplumber.open(pdf_path) as pdf:
    for page_idx, page in enumerate(pdf.pages):
        words = page.extract_words()
        full_text = " ".join(w["text"] for w in words)
        # Match "Figure N" or "FigureN:" (pdfplumber sometimes merges tokens)
        for m in re.finditer(r'Figure\s*(\d+)\s*[:.—]|Figure(\d+)[:.—]', full_text):
            fig_num = int(m.group(1) or m.group(2))
            if fig_num not in figure_pages:
                figure_pages[fig_num] = page_idx + 1

doc_pdfium = pdfium.PdfDocument(pdf_path)
results = []

with pdfplumber.open(pdf_path) as pdf:
    for fig_num in sorted(figure_pages.keys())[:20]:
        if fig_num in already_saved:
            continue
        page_num = figure_pages[fig_num]
        page_idx = page_num - 1
        page = pdf.pages[page_idx]
        page_h = float(page.height)
        words = page.extract_words()

        # Find caption position — handle both split and merged tokens
        caption_y_top = None
        for i, w in enumerate(words):
            t = w["text"].strip()
            # Case 1: separate "Figure" + "N" tokens
            if t == "Figure" and i+1 < len(words) and words[i+1]["text"].strip().startswith(str(fig_num)):
                caption_y_top = float(w["top"])
                break
            # Case 2: merged "FigureN:" token
            if re.match(rf'Figure\s*{fig_num}[:.—]', t):
                caption_y_top = float(w["top"])
                break

        if caption_y_top is None:
            # Last resort: render full page
            p = doc_pdfium[page_idx]
            bm = p.render(scale=2.0)
            img = bm.to_pil()
            filename = f"{arxiv_id_safe}_fig{fig_num:02d}.png"
            img.save(os.path.join(vault_root, filename))
            results.append({"num": fig_num, "filename": filename, "page": page_num})
            print(f"  ⚠ fig{fig_num:02d}: caption not found, full page render", file=sys.stderr)
            continue

        # Determine if caption is ABOVE or BELOW the figure
        # Caption near top (< 15% of page height) → figure is below the caption
        caption_is_above_figure = caption_y_top < page_h * 0.15

        # Find caption block bottom (include multi-line captions, up to 70 pts below start)
        cap_block = [w for w in words
                     if float(w["top"]) >= caption_y_top - 2
                     and float(w["top"]) <= caption_y_top + 70]
        caption_bot = max((float(w["bottom"]) for w in cap_block), default=caption_y_top + 20)

        scale = 3.0

        if caption_is_above_figure:
            # Figure is BELOW the caption: crop from caption_bot to end of page
            # Find where the next body text section starts (if any)
            below_cap = [w for w in words if float(w["top"]) > caption_bot + 10]
            # Find the biggest vertical gap below the caption — that gap is the figure
            # Heuristic: next dense text block after figure ends
            crop_top_pt = caption_bot + 2
            crop_bot_pt = page_h - 10
            # If there's trailing body text after the figure, find where it starts
            if below_cap:
                # Look for a gap > 30 pts between consecutive word groups
                sorted_below = sorted(below_cap, key=lambda w: float(w["top"]))
                last_y = caption_bot
                for w in sorted_below:
                    if float(w["top"]) - last_y > 30:
                        # Gap found — figure ends before this gap
                        crop_bot_pt = last_y + 5
                        break
                    last_y = float(w["bottom"])
        else:
            # Figure is ABOVE the caption: crop from prev text end to caption_bot
            # Find text above the figure
            prev_text = [w for w in words if float(w["bottom"]) < caption_y_top - 10
                         and float(w["top"]) > 30]  # skip header
            # Use vector graphic objects to find figure top
            graphic_objs = list(page.curves) + list(page.rects) + list(page.lines)
            fig_objs = [o for o in graphic_objs
                        if float(o.get("top", o.get("y0", 0))) < caption_y_top - 5]
            if fig_objs:
                obj_tops = [float(o.get("top", o.get("y0", 0))) for o in fig_objs]
                crop_top_pt = max(0, min(obj_tops) - 8)
            elif prev_text:
                crop_top_pt = max(0, max(float(w["bottom"]) for w in prev_text) - 4)
            else:
                crop_top_pt = max(0, caption_y_top - 280)
            crop_bot_pt = caption_bot + 5

        # Render page at 3× and crop
        px_top = max(0, int(crop_top_pt * scale))
        px_bot = min(int(page_h * scale), int(crop_bot_pt * scale))
        p = doc_pdfium[page_idx]
        bm = p.render(scale=scale)
        img = bm.to_pil()
        cropped = img.crop((0, px_top, img.width, px_bot))
        filename = f"{arxiv_id_safe}_fig{fig_num:02d}.png"
        cropped.save(os.path.join(vault_root, filename))
        results.append({"num": fig_num, "filename": filename, "page": page_num})
        h_pts = crop_bot_pt - crop_top_pt
        print(f"  ✓ fig{fig_num:02d}: page {page_num}, {h_pts:.0f}pts → {cropped.size}", file=sys.stderr)

print(json.dumps(results))
PYEOF
```

Collect all saved filenames from both stages — you will use them in Step 5 to embed figures into the note.

**Notes on figure quality**:
- TeX-source figures (PDF/PNG originals): cleanly cropped, highest quality
- Smart-cropped from PDF: include figure + caption; may include small margins of surrounding text on pages with dense layout

---

### Step 4 — Read format instructions

Read the note format specification:

```bash
cat "/home/trx50/Project/arthur_knowledge_assistant/instructions/note-paper.md"
```

Then read the global output rules from CLAUDE.md (language, image placement, speed table).

---

### Step 5 — Generate the complete note

Using the full paper text from Step 2 and the figure manifest from Step 3, generate a complete Obsidian note.

**Mandatory structure** (from note-paper.md):

```
Frontmatter
TL;DR [!abstract]
# 一、核心演算法直覺
  ## 1.1 白話解釋
  ## 1.2 演算法流程 (code block)
  ## 1.3 與舊方法最大的不同 (對比表)
# 二、主要發現
  ## 2.1 發現一（以反直覺或最重要的結論命名）
  ## 2.2 發現二
  ## 2.3 ...（依論文核心論點數量決定，通常 3–5 個）
# 三、研究背景與動機
# 四、方法細節
  ## 4.1 任務定義
  ## 4.2 核心指標 / 演算法
  ## 4.3 實驗設定（如有）
# 五、實驗結果
  ## 5.1 第一組實驗名稱
  ## 5.2 ...（依實驗層次分節）
# 六、關鍵圖表解讀
  ### Figure N（頁碼）：圖表標題
# 七、侷限與風險 [!warning]
# 八、延伸應用（短期 / 中期 / 長期）
# 九、落地設計（選填，論文方法可直接落地時才寫）
## 附：關鍵數據速查
```

**章節編號規範**：
- 主章節：`# 一、` `# 二、` ... `# 九、`（中文數字）
- 子節：`## 1.1` `## 1.2`（阿拉伯數字，對應主章節編號）
- 範例：`# 四、方法細節` → `## 4.1 任務定義` → `## 4.2 核心指標`

**Figure embedding rules**:
- Embed each downloaded figure with `![[{filename}]]` immediately after the paragraph that references it
- Below the embed, write the original figure caption as plain text in italics
- In `六、關鍵圖表解讀`, one entry per figure:
  ```
  ### Figure N（頁碼）：圖表標題
  ![[filename]]
  *Figure N: 原始英文 caption（如有）*

  （一段白話說明：這張圖在比較什麼、最重要的 takeaway、關鍵數字）
  ```
- 每個圖用一段自然段落說明，不強制拆成「看什麼 / 關鍵發現 / 數字」三個固定欄位——除非圖表複雜到需要分層解讀
- Do NOT stack all figures at the end

**Output language rules** (from CLAUDE.md):
- All text in 繁體中文
- Keep in English: arXiv IDs, model names (LLM, Gemini, GPT), technical acronyms (KV cache, RLHF, MAS, SAS), person names, company names
- Numbers must include units (%, ×, tokens, seconds, ms)

**TL;DR rules**:
- Must include: method name + core mechanism + the most important result number + what it beats
- Bad: "提升了性能" — Good: "Pass@3 從 0.523 → 0.560（+3.7%），以更少 token 擊敗 MAS"
- If paper has no quantitative result (pure theory), use the alternative format from note-paper.md

**Speed table rules**:
- Always end with `## 附：關鍵數據速查`
- Include every number mentioned in the paper (accuracy, latency, token counts, dataset sizes, hyperparameters)
- If a value is not mentioned in the paper, write "原文未提" — never invent numbers

---

### Step 6 — Determine note filename and save

Generate a filename from the paper title:
- Use the Chinese title from the frontmatter
- Replace `/` and other illegal chars with space or `-`
- Keep under 80 characters
- Example: `Auto-Diagnose：用 LLM 自動診斷 Google 整合測試失敗根因.md`

Save the note:

```bash
NOTE_PATH="$NOTE_DIR/<sanitized_title>.md"
# Write note content to $NOTE_PATH
```

---

### Step 7 — Report results

Print a concise summary:

```
✓ Note saved:    AI Knowledge/論文筆記/{title}.md
✓ Figures saved: {N} images → vault root

  fig01: {arxiv_id_safe}_fig01.png  — {caption_preview}
  fig02: {arxiv_id_safe}_fig02.png  — {caption_preview}
  ...
  fig{N} failed: {error}  ← if any

Open in Obsidian to verify figure rendering.
```

If figures failed to download but the note was written, still save the note — just leave the `![[filename]]` placeholder commented out with a note: `<!-- figure not downloaded: {url} -->`.

---

## Edge Cases

| Situation | Action |
|-----------|--------|
| arXiv HTML version not available | Fall back to PDF (Path B): download PDF → extract text with pdfplumber → extract figures via TeX source + smart page crop |
| Paper is very new (HTML not processed yet) | Same PDF fallback; HTML is usually available 24–48h after submission |
| TeX source has no standalone figure files | All figures are TikZ-generated → use Stage B-2 smart crop for all |
| Caption not found by smart-crop script | Fall back to full-page render for that figure; leave a note `<!-- full page render, figure may need manual crop -->` |
| Caption is at top of page (figure below) | Detected when `caption_y_top < page_height * 0.15`; crop from caption_bot downward |
| Figure download fails (403, timeout) | Skip that figure; leave `<!-- figure not downloaded: reason -->` placeholder in note |
| Paper has > 20 figures | Only process first 20; prioritize figures referenced in main results sections |
| arXiv ID has version (e.g. `2604.02460v2`) | Use versioned URL for fetch; strip version for display in frontmatter |
| TeX source is a single `.pdf` (not tar) | `curl` downloads the compiled PDF directly; skip TeX extraction, go straight to Stage B-2 |
