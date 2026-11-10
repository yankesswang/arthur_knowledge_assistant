---
name: paper-note
description: Given an arXiv URL or ID, fetch the full paper and figures, then generate a decision-first, readable Traditional Chinese Obsidian research note for Arthur. Use when turning an arXiv paper into a new note or rewriting an existing paper note that is too dense, repetitive, or unclear.
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
NOTE_DIR="/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/論文筆記"
VAULT_ROOT="/Users/yankesswang/Documents/arthurwang_DB"
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
VENV_PYTHON="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/.venv/bin/python3"

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
vault_root = "/Users/yankesswang/Documents/arthurwang_DB"

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
VENV_PYTHON="/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/.venv/bin/python3"

mkdir -p /tmp/arxiv_src
curl -L -A "Mozilla/5.0" "https://arxiv.org/src/$ARXIV_ID" -o /tmp/arxiv_src.tar.gz -s

# Try to extract (arXiv source is usually .tar.gz but sometimes plain .gz or .pdf)
tar -xzf /tmp/arxiv_src.tar.gz -C /tmp/arxiv_src 2>/dev/null || \
tar -xf  /tmp/arxiv_src.tar.gz -C /tmp/arxiv_src 2>/dev/null

find /tmp/arxiv_src -type f | sort
```

Then parse the `.tex` file to find `\includegraphics` references and map them to figure numbers.

**Critical**: Must follow `\input{}`/`\include{}` directives recursively in paper order — do NOT simply concatenate all `.tex` files (that produces wrong figure numbering because: (1) it ignores include order, (2) figures buried in `sections/` and `tables/` subdirectories are missed or mis-ordered, (3) the same image reused in appendix gets double-counted).

```bash
$VENV_PYTHON << 'PYEOF'
import re, os, shutil, json
import pypdfium2 as pdfium

src_dir = "/tmp/arxiv_src"
vault_root = "/Users/yankesswang/Documents/arthurwang_DB"
arxiv_id_safe = os.environ.get("ARXIV_ID_SAFE", "")

# Step 1: Find the main .tex file (has \documentclass)
def find_main_tex(src_dir):
    for root, dirs, files in os.walk(src_dir):
        for f in files:
            if not f.endswith(".tex"):
                continue
            path = os.path.join(root, f)
            with open(path, encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            if "\\documentclass" in content:
                return path
    # Fallback: pick the largest .tex file at root
    candidates = [os.path.join(src_dir, f) for f in os.listdir(src_dir) if f.endswith(".tex")]
    return max(candidates, key=os.path.getsize) if candidates else None

main_tex = find_main_tex(src_dir)
print(f"  Main tex: {main_tex}", flush=True)

# Step 2: Recursively expand \input{} / \include{} to produce full content in paper order
visited = set()

def resolve_input(ref, current_dir, src_dir):
    """Try to find the actual file for a \\input{ref} call."""
    candidates = [
        os.path.join(current_dir, ref),
        os.path.join(current_dir, ref + ".tex"),
        os.path.join(src_dir, ref),
        os.path.join(src_dir, ref + ".tex"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return None

def flatten_tex(path):
    """Return full TeX content with \\input/\\include expanded in order."""
    real_path = os.path.realpath(path)
    if real_path in visited:
        return ""
    visited.add(real_path)
    with open(path, encoding="utf-8", errors="ignore") as f:
        content = f.read()
    current_dir = os.path.dirname(path)

    def replace_input(m):
        ref = m.group(1).strip()
        sub = resolve_input(ref, current_dir, src_dir)
        if sub:
            return flatten_tex(sub)
        return ""

    content = re.sub(r'\\input\{([^}]+)\}', replace_input, content)
    content = re.sub(r'\\include\{([^}]+)\}', replace_input, content)
    return content

full_tex = flatten_tex(main_tex)

# Step 3: Extract figure environments in paper order; skip decoration (no caption)
figure_envs = re.findall(
    r'\\begin\{figure[^}]*\}(.*?)\\end\{figure[^}]*\}',
    full_tex, re.DOTALL
)

saved = {}        # fig_counter → {"path": ..., "src": ..., "panel": N_of_M, "caption": ...}
fig_counter = 0
seen_src_files = set()   # realpath → fig_counter; deduplicates same image in main text + appendix

for env in figure_envs:
    # Skip figure environments with no caption (decorative/logo figures)
    if not re.search(r'\\caption', env):
        continue

    inc_matches = re.findall(r'\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}', env)
    if not inc_matches:
        continue

    # Grab caption once per figure environment (shared across all panels)
    cap_m = re.search(r'\\caption(?:\[[^\]]*\])?\{([^}]{0,200})', env, re.DOTALL)
    caption = cap_m.group(1).replace('\n', ' ').strip()[:160] if cap_m else ""

    # Collect unique, resolvable panels for this environment
    panels = []
    for src_file_base in inc_matches:
        src_file_base = src_file_base.strip()
        found_path = None
        for ext in ["", ".pdf", ".png", ".jpg", ".eps"]:
            for base in [
                os.path.join(src_dir, src_file_base + ext),
                os.path.join(src_dir, os.path.basename(src_file_base) + ext),
            ]:
                if os.path.exists(base):
                    found_path = base
                    break
            if found_path:
                break
        if not found_path:
            continue
        real_src = os.path.realpath(found_path)
        if real_src in seen_src_files:
            print(f"  ⟳ skipping duplicate: {os.path.basename(found_path)}", flush=True)
            continue
        panels.append((found_path, real_src))

    if not panels:
        continue

    n_panels = len(panels)
    for panel_idx, (found_path, real_src) in enumerate(panels):
        seen_src_files.add(real_src)
        fig_counter += 1
        dest = os.path.join(vault_root, f"{arxiv_id_safe}_fig{fig_counter:02d}.png")
        ext_lower = os.path.splitext(found_path)[1].lower()

        if ext_lower == ".png":
            shutil.copy(found_path, dest)
        elif ext_lower in (".pdf", ".eps"):
            try:
                doc = pdfium.PdfDocument(found_path)
                page = doc[0]
                bm = page.render(scale=3.0)
                img = bm.to_pil()
                img.save(dest)
            except Exception as e:
                print(f"  ✗ fig{fig_counter:02d}: {e}", flush=True)
                continue

        panel_label = f"{panel_idx+1}/{n_panels}" if n_panels > 1 else "1/1"
        saved[fig_counter] = {
            "path": dest,
            "filename": os.path.basename(dest),
            "src": os.path.basename(found_path),
            "panel": panel_label,   # "1/2", "2/2", or "1/1" for single-panel figures
            "caption": caption,
        }
        print(f"  ✓ fig{fig_counter:02d} [{panel_label}]: {os.path.basename(found_path)}", flush=True)

        if fig_counter >= 20:
            break
    if fig_counter >= 20:
        break

print(json.dumps({"saved": list(saved.keys()), "manifest": {str(k): v for k, v in saved.items()}}))
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
vault_root = "/Users/yankesswang/Documents/arthurwang_DB"

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
            # Figure is ABOVE the caption: crop from prev text end to just before caption
            # crop_bot stops at caption_y_top so the caption text is NOT included in the image
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
            crop_bot_pt = caption_y_top - 5  # stop before caption text starts

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
- Smart-cropped from PDF: figure only, caption excluded; crop stops at `caption_y_top - 5` so no caption text bleeds into the image

---

### Step 4 — Read vault conventions

Read the existing note specification for frontmatter, language, filename, and Obsidian conventions:

```bash
cat "/Users/yankesswang/Desktop/Projects/Arthur_App/arthur_knowledge_assistant/instructions/note-paper.md"
```

Then read the global output rules from CLAUDE.md.

Treat the structure and prioritization rules in Step 5 below as authoritative. If the legacy
`note-paper.md` asks for an exhaustive fixed chapter list, every figure, or every number, do not
follow those requirements: they are the failure mode this skill is designed to avoid.

---

### Step 5 — Generate a layered, decision-first note

Using the full paper text from Step 2 and the figure manifest from Step 3, generate a detailed but readable Obsidian note. Use two reading layers: the TL;DR and section openings let a reader grasp the paper quickly; the technical subsections retain enough architecture, objective, training, experiment, and deployment detail to study the work without reopening the PDF.

Before writing, identify these five items in scratch reasoning:

1. The paper's one-sentence claim
2. The 2–4 genuinely new ideas
3. The strongest quantitative evidence for each major modality or contribution
4. The most important caveat or counter-result
5. The concrete situation in which Arthur should or should not use the work

Build the note around those items. Do not organize it by mechanically mirroring the paper.

**Mandatory structure**:

```
Frontmatter
TL;DR [!abstract]: 一句結論 + 3 個要點 + 適用/不適用
# 一、這篇論文解決什麼問題
# 二、整體架構：先看懂資料怎麼流
# 三、方法深挖
  ## 3.1 各模態如何變成 token
  ## 3.2 Backbone 與核心結構創新
  ## 3.3 訓練目標、資料與課程
  ## 3.4 Model merging、MRL 與量化
# 四、實驗結果
  ## 4.1 總覽與比較基準
  ## 4.2 文字與程式碼
  ## 4.3 圖像、文件與影片
  ## 4.4 音訊
  ## 4.5 效率與量化
# 五、消融實驗與真正值得記住的發現
# 六、限制與使用判斷
# 七、對 Arthur 的意義（有明確關聯才寫）
## 附：關鍵數據速查
```

Keep the main note around 4,000–7,000 Chinese characters for a normal empirical paper, excluding frontmatter and the final data table. Complex system or multimodal papers may reach 8,500 characters when the additional detail explains distinct mechanisms or evidence. Do not compress away technical content merely to hit a length target.

**Section rules**:
- Start each section with its conclusion, then explain the evidence. Never make the reader wait until the end for the point.
- Begin the architecture section with a 5–8 step data-flow overview, then explain each important component in the technical subsections. Cover all mechanisms needed for conceptual reproduction: modality preprocessing, tensor/token flow, backbone changes, pooling/output, objectives, training stages, data recipe, and inference-time controls.
- Prefer plain-language mechanisms, numbered steps, and small input/output examples over equations. Keep at most 0–2 equations in the entire note, and only when the equation itself is a central contribution that cannot be explained accurately in prose.
- Never make the reader decode single-letter symbols. Do not write unexplained variables such as `s`, `q`, `p_i`, `H_l`, or `Z`. Replace them with semantic Chinese phrases such as「背景資料」「查詢內容」「第 i 個選項的機率」「這一層的輸出」. If an equation must remain, introduce every quantity in Chinese before the equation, annotate it with meaningful names, and immediately give a concrete example.
- Do not introduce notation that appears only once. Convert secondary formulas into: `輸入是什麼 → 怎麼計算 → 輸出是什麼 → 為什麼需要`.
- Explain training objectives separately rather than collapsing them into one sentence. For each loss or regularizer, state its input, optimization behavior, and intended failure mode.
- In `四、實驗結果`, give each materially evaluated modality its own subsection. Use compact tables, but include enough comparisons to show both strengths and weaknesses. State what each benchmark measures before citing its score.
- Preserve important per-dimension, per-modality, and quantization results when they affect deployment decisions. Avoid dumping every task row, but do not omit an entire result family merely because it is not the top headline.
- In `五、消融實驗與真正值得記住的發現`, keep 3–6 findings supported by ablations or counter-results. Use `發現 → 實驗控制 → 數字 → 為什麼 → 意義`; note when the authors provide only a hypothesis.
- In `六、限制與使用判斷`, separate `適合`, `不適合`, and `尚未證明`. Include evaluation-scope, reproducibility, data/teacher dependence, context limits, and modality-specific weaknesses when applicable.
- Write `七、對 Arthur 的意義` only when there is a concrete connection to Arthur's systems or workflow. Give 3–5 actionable design decisions and state the tradeoff behind each one.
- Use bullets for scannability, but avoid bullets nested deeper than one level.
- Define an acronym once. Prefer concrete nouns over chains of jargon.
- Do not repeat the same explanation in multiple sections. A headline result may appear in the TL;DR, its experiment subsection, and the appendix; elsewhere refer back instead of restating it.
- Explicitly label inference with `我的判斷：`; otherwise attribute claims to the paper.

**Figure embedding rules**:
- Embed figures that materially explain the mechanism, training design, or a central result, normally 2–6 figures. Downloaded figures may remain unused.
- Each selected figure file must be embedded **exactly once** in the entire note.
- Place each selected figure beside the paragraph it supports; do not create a separate figure-gallery chapter.
- Multi-panel figures (manifest `panel` field = "1/2", "2/2"): embed both panels back-to-back at the same location, they are halves of the same logical figure
- Below each embed, write 2–4 concise Chinese bullets covering `看什麼`, `關鍵數字`, and `為什麼重要`. Do not paste a long original caption.
- Do not stack figures at the end or repeat a figure.

**Output language rules** (from CLAUDE.md):
- All text in 繁體中文
- Use Chinese-first terminology. On first occurrence, write `好懂的中文名稱（official English term）`; afterward use only the Chinese name. Examples: `背景資料（state）`, `查詢內容（query）`, `目標內容（target）`, `損失函數（loss）`, `獎勵（reward）`, `模型嘗試軌跡（rollout）`, `文字單元（token）`, `近似最近鄰搜尋（ANN）`.
- Keep English only for proper names that should not be translated: arXiv IDs, model/product names, benchmark names, people, companies, code/API identifiers, and an official algorithm name whose Chinese translation would be ambiguous. Even then, explain its role in Chinese on first use.
- Avoid decorative or unnecessary English in headings and prose. Prefer「主幹模型」over `backbone`,「讀出頭」over `readout head`,「檢查器」over `verifier`,「檢查點」over `checkpoint`,「前向計算」over `forward pass`, and「評測集」over `benchmark` when referring to the generic concept.
- Acronyms may remain only when they recur or are standard names. Define them once in Chinese, then use the acronym. Do not make the reader remember an acronym used only once.
- In prose, never use a bare mathematical letter as a noun. Say「背景資料」instead of `s`,「選項機率」instead of `p`, and「第 3 個候選答案」instead of `o_3`.
- Numbers must include units (%, ×, tokens, seconds, ms)

**TL;DR rules**:
- Open with a one-sentence verdict that includes the method, core mechanism, strongest result, and comparison target.
- Follow with exactly three bullets: `新意`, `證據`, `代價`.
- End with one line: `適合：...｜不適合：...`.
- Bad: "提升了性能" — Good: "Pass@3 從 0.523 → 0.560（+3.7%），以更少 token 擊敗 MAS"
- If paper has no quantitative result (pure theory), use the alternative format from note-paper.md

**Key-data appendix rules**:
- Always end with `## 附：關鍵數據速查`
- Include 15–30 decision-relevant values: model size, data scale, main and secondary result families, important ablations, compute/latency/memory when reported, and thresholds needed to reproduce or deploy the method.
- Group related values in one row. Omit secondary per-task scores that do not change the conclusion.
- If a value is not mentioned in the paper, write "原文未提" — never invent numbers

**Pre-save quality gate**:
1. A reader who sees only the TL;DR can answer: what changed, how much it helped, and what it costs.
2. Every main section has a distinct job; remove any paragraph that merely restates another section.
3. The main body covers every major result family in the paper, while keeping total benchmark rows around 12–20 across all tables.
4. Every major method component answers three questions: what it does, why it exists, and what evidence supports it.
5. Claims distinguish paper evidence from your inference.
6. The note is easy to scan despite its depth: short paragraphs, informative subheadings, selective callouts, and no wall of equations or unfiltered benchmark dumps.
7. If rewriting an existing note, preserve valid frontmatter, source URL, and working image links while replacing the body with the clearer structure.
8. Search the draft for single-letter variables, unexplained acronyms, and avoidable English. Rewrite them into semantic Chinese; no reader should need to look backward to remember what a symbol means.
9. Verify that removing an equation did not remove the mechanism: its prose replacement must still explain the input, operation, output, purpose, and one concrete consequence.

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

Then add it to 待閱讀清單 (本週「LLM 技術 / 論文」). The note isn't done until this runs —
the daily `sync_reading_list.py` safety net only scans `投資/`, so a skipped step is never recovered.
`--link` is the filename without `.md`; the script dedups, and if the vault is unreadable it
queues the entry and still exits 0.

```bash
python3 ~/Projects/Arthur_App/scripts/lib/article_list.py \
  --section "LLM 技術 / 論文" --link "<sanitized_title>"
```

---

### Step 7 — Report results

Print a concise summary:

```
✓ Note saved:    AI Knowledge/論文筆記/{title}.md
✓ Figures saved: {N} images → vault root
✓ Reading list:  added to 待閱讀清單 / LLM 技術 / 論文  (or "already present" / "queued")

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
