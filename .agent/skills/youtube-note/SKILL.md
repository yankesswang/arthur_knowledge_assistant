---
name: youtube-note
description: YouTube URL → yt-dlp transcript + Gemini/ChatGPT analysis → Obsidian note with key screenshots
---

# /youtube-note

Given a YouTube URL, automatically:
1. Download transcript + metadata (use YouTube chapters if available)
2. Analyze with `opencli gemini ask` — chunked for long videos (fallback: `opencli chatgpt-app ask`)
3. Download video once (480p) → extract multi-candidate screenshots → pick best by image score
4. Generate Obsidian note with timestamp links + embedded screenshots

## Usage

```
/youtube-note https://youtu.be/znlGltyc6Yw
/youtube-note https://www.youtube.com/watch?v=znlGltyc6Yw
/youtube-note https://www.youtube.com/shorts/VIDEO_ID
/youtube-note https://www.youtube.com/live/VIDEO_ID
```

## Vault Paths

- **Notes**: `/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/影片筆記/`
- **Screenshots**: `/Users/yankesswang/Documents/arthurwang_DB/` (vault root)
- **Temp work**: `/tmp/yt_note/<VIDEO_ID>/`

---

## What You Must Do When Invoked

Follow these steps in order. Do not skip or reorder.

---

### Step 1 — Parse URL, setup, dependency check

```bash
export YT_URL="<user-provided URL>"

# Support v=, youtu.be, shorts, embed, live
export VIDEO_ID=$(python3 - "$YT_URL" << 'PYEOF'
import re, sys
url = sys.argv[1]
for p in [
    r'(?:v=)([A-Za-z0-9_-]{11})',
    r'youtu\.be/([A-Za-z0-9_-]{11})',
    r'youtube\.com/(?:shorts|embed|live)/([A-Za-z0-9_-]{11})',
]:
    m = re.search(p, url)
    if m: print(m.group(1)); import sys; sys.exit(0)
print("")
PYEOF
)
if [ -z "$VIDEO_ID" ]; then echo "ERROR: Cannot extract video ID from URL"; exit 1; fi

export WORK_DIR="/tmp/yt_note/$VIDEO_ID"
export NOTE_DIR="/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/影片筆記"
export VAULT_ROOT="/Users/yankesswang/Documents/arthurwang_DB"
mkdir -p "$WORK_DIR/shots" "$NOTE_DIR"
echo "Video ID: $VIDEO_ID  |  Work dir: $WORK_DIR"

# Dependency check — fail fast before any downloads
command -v yt-dlp >/dev/null || { echo "ERROR: yt-dlp not found. Run: pip install yt-dlp"; exit 1; }
command -v ffmpeg  >/dev/null || { echo "ERROR: ffmpeg not found. Run: brew install ffmpeg"; exit 1; }
python3 - << 'PYEOF'
try:
    from PIL import Image, ImageStat
except ImportError:
    print("ERROR: Pillow not installed. Run: pip install Pillow")
    raise SystemExit(1)
print("Dependencies OK")
PYEOF
```

---

### Step 2 — Download metadata and transcript

```bash
yt-dlp --dump-json --no-playlist "$YT_URL" 2>/dev/null > "$WORK_DIR/meta.json"
if [ ! -s "$WORK_DIR/meta.json" ]; then
  echo '{"title":"Unknown","channel":"Unknown","duration":0,"description":"","chapters":[]}' > "$WORK_DIR/meta.json"
fi

yt-dlp --skip-download \
  --write-subs --write-auto-subs \
  --sub-lang "en,zh-TW,zh-Hant,zh" \
  --sub-format "vtt" \
  -o "$WORK_DIR/transcript.%(ext)s" \
  "$YT_URL" 2>/dev/null

export VTT_FILE=$(ls "$WORK_DIR"/transcript.*.vtt 2>/dev/null | head -1)
echo "Meta: $(python3 -c "import json; d=json.load(open('$WORK_DIR/meta.json')); ch=d.get('chapters') or []; print(d.get('title','?')[:60], '| dur:', d.get('duration',0),'s | chapters:', len(ch))" 2>/dev/null)"
echo "VTT:  ${VTT_FILE:-NONE}"
```

---

### Step 3 — Parse transcript + extract chapters

```bash
python3 << 'PYEOF'
import re, json, os, sys

work_dir = os.environ["WORK_DIR"]
vtt_file = os.environ.get("VTT_FILE", "")

with open(f"{work_dir}/meta.json") as f:
    meta = json.load(f)

title        = meta.get("title", "Unknown")
channel      = meta.get("channel", "Unknown")
duration_sec = int(meta.get("duration", 0))
duration_fmt = f"{duration_sec//3600:02d}:{(duration_sec%3600)//60:02d}:{duration_sec%60:02d}"
chapters_raw = meta.get("chapters") or []

chapters = [
    {"title": ch.get("title",""), "start_sec": int(ch.get("start_time",0)), "end_sec": int(ch.get("end_time", duration_sec))}
    for ch in chapters_raw
]

info = {
    "title": title, "channel": channel,
    "duration": duration_fmt, "duration_sec": duration_sec,
    "has_chapters": len(chapters) > 0, "chapters": chapters
}
with open(f"{work_dir}/info.json", "w") as f:
    json.dump(info, f, ensure_ascii=False)

if chapters:
    print(f"YouTube chapters: {len(chapters)}")
    for ch in chapters[:6]:
        m, s = divmod(ch["start_sec"], 60)
        print(f"  [{m:02d}:{s:02d}] {ch['title']}")

if not vtt_file or not os.path.exists(vtt_file):
    desc = meta.get("description", "")[:3000]
    with open(f"{work_dir}/condensed.txt", "w") as f:
        f.write(f"[Description]\n{desc}")
    print(f"No VTT — using description ({len(desc)} chars)")
    sys.exit(0)

with open(vtt_file, encoding="utf-8", errors="ignore") as f:
    content = f.read()

content = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', content)
content = re.sub(r'</?c>', '', content)
for ent, val in [('&gt;','>'),('&lt;','<'),('&amp;','&'),('&nbsp;',' ')]:
    content = content.replace(ent, val)

blocks = re.split(r'\n{2,}', content)
timeline, prev_text = [], ''
for block in blocks:
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
    ts_line = next((l for l in lines if '-->' in l), None)
    if not ts_line: continue
    parts = ts_line.split('-->')[0].strip().replace(',','.').split(':')
    try:
        secs = int(parts[0])*3600+int(parts[1])*60+float(parts[2]) if len(parts)==3 \
               else int(parts[0])*60+float(parts[1])
    except: continue
    text = ' '.join(l for l in lines if '-->' not in l).strip()
    if text and text != prev_text and not text.startswith('['):
        timeline.append((secs, text)); prev_text = text

# Collect all text in each 30-second bucket, then dedupe-merge
interval = 30
buckets = {}
for secs, text in timeline:
    buckets.setdefault(int(secs) // interval, []).append(text)

def dedupe_keep_order(items):
    seen, out = set(), []
    for x in items:
        x = re.sub(r'\s+', ' ', x).strip()
        if x and x not in seen:
            seen.add(x); out.append(x)
    return out

condensed_lines = []
for b in sorted(buckets):
    texts  = dedupe_keep_order(buckets[b])
    merged = " ".join(texts)
    m2, s2 = divmod(b * interval, 60)
    h2, m2 = divmod(m2, 60)
    ts = f"{h2:02d}:{m2:02d}:{s2:02d}" if h2 else f"{m2:02d}:{s2:02d}"
    condensed_lines.append(f"[{ts}] {merged}")

condensed = '\n'.join(condensed_lines)
with open(f"{work_dir}/condensed.txt", "w") as f:
    f.write(condensed)
print(f"Transcript: {len(timeline)} entries → {len(condensed_lines)} lines ({len(condensed)} chars)")
PYEOF
```

---

### Step 4 — LLM analysis (chapters-aware + chunk-aware for long videos)

```bash
python3 << 'PYEOF'
import subprocess, json, os, sys

work_dir = os.environ["WORK_DIR"]
video_id = os.environ["VIDEO_ID"]

with open(f"{work_dir}/info.json")     as f: info       = json.load(f)
with open(f"{work_dir}/condensed.txt") as f: transcript = f.read()

title        = info["title"]
channel      = info["channel"]
duration     = info["duration"]
has_chapters = info["has_chapters"]
chapters     = info.get("chapters", [])

chapter_hint = ""
if has_chapters:
    ch_lines = []
    for ch in chapters:
        m, s = divmod(ch["start_sec"], 60); h, m = divmod(m, 60)
        ts = f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
        ch_lines.append(f"  [{ts}] {ch['title']}")
    chapter_hint = "\n\n影片已有官方章節（請以此為基礎，不要自行重新切分章節）：\n" + "\n".join(ch_lines)

JSON_SCHEMA = """{
  "title_zh": "影片中文標題（保留英文專有名詞）",
  "summary": "2-3句話的核心摘要（繁體中文）",
  "sections": [
    {"title":"章節標題（繁體中文，5-15字）","start_time":"MM:SS","key_points":["重點1","重點2","重點3"],"screenshot_at":"MM:SS"}
  ],
  "key_insights": ["洞見1","洞見2","洞見3"],
  "data_table": [{"指標":"...","數值":"...","備註":"..."}]
}"""

llm_provider_used = ""

def call_llm(prompt_text):
    global llm_provider_used
    for provider in [
        ["opencli", "gemini",      "ask", "--timeout", "120"],
        ["opencli", "chatgpt-app", "ask", "--timeout", "120"],
    ]:
        try:
            r = subprocess.run(provider + [prompt_text], capture_output=True, text=True, timeout=150)
            if r.returncode == 0 and r.stdout.strip():
                if not llm_provider_used:
                    llm_provider_used = provider[1]
                print(f"  LLM OK via {provider[1]} ({len(r.stdout)} chars)")
                return r.stdout.strip()
            print(f"  {provider[1]} failed: {r.stderr[:80]}", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"  {provider[1]} timed out", file=sys.stderr)
        except Exception as e:
            print(f"  {provider[1]} error: {e}", file=sys.stderr)
    return ""

CHUNK_LIMIT = 12000
section_rule = "使用上方官方章節，不要重新切分" if has_chapters else "sections 請分 5-8 個章節涵蓋全片"

if len(transcript) <= CHUNK_LIMIT:
    print("Single-call analysis...")
    prompt = f"""你是影片筆記專家。請分析以下 YouTube 影片字幕，輸出 JSON 格式的筆記結構。{chapter_hint}

影片資訊：標題：{title} | 頻道：{channel} | 時長：{duration}

字幕（格式 [HH:MM:SS 或 MM:SS] 文字）：
{transcript}

只輸出以下 JSON，不要其他文字：
{JSON_SCHEMA}

要求：
- {section_rule}
- screenshot_at 選講者提到具體數據/圖表/投影片切換的時刻
- key_insights 3-5 條每條不超過 30 字
- data_table 包含影片中所有具體數字（無則空 array）
- 全部繁體中文，保留英文術語和人名"""
    response = call_llm(prompt)

else:
    print(f"Long transcript ({len(transcript)} chars) — chunked analysis...")
    lines_all = transcript.split('\n')
    chunks, cur, cur_len = [], [], 0
    for line in lines_all:
        if cur_len + len(line) > CHUNK_LIMIT and cur:
            chunks.append('\n'.join(cur)); cur, cur_len = [], 0
        cur.append(line); cur_len += len(line) + 1
    if cur: chunks.append('\n'.join(cur))

    print(f"  {len(chunks)} chunks")
    partial_summaries = []
    for idx, chunk in enumerate(chunks):
        print(f"  Chunk {idx+1}/{len(chunks)}...")
        p = f"""以下是影片《{title}》第 {idx+1}/{len(chunks)} 段字幕。只輸出 JSON（不要其他文字）：
{{
  "segment": {idx+1},
  "time_range": "從字幕第一行到最後一行的時間範圍",
  "topics": ["主題1","主題2"],
  "key_moments": [{{"time":"MM:SS","description":"重要時刻"}}],
  "numbers": ["數字1：說明"]
}}

字幕：
{chunk}"""
        r = call_llm(p)
        # Cap each partial at 1500 chars so merge input stays balanced across all chunks
        if r: partial_summaries.append(r[:1500])

    print("  Merging...")
    merge_input = '\n\n---\n\n'.join(partial_summaries)
    response = call_llm(f"""以下是影片《{title}》各段的摘要，請合併成完整的筆記結構。{chapter_hint}

影片資訊：頻道：{channel} | 時長：{duration}

各段摘要（每段平衡截取）：
{merge_input}

只輸出以下 JSON，不要其他文字：
{JSON_SCHEMA}""")

if not response:
    print("WARNING: LLM unavailable — fallback skeleton", file=sys.stderr)
    llm_provider_used = "fallback"
    fallback_sections = []
    if has_chapters:
        for ch in chapters:
            m, s = divmod(ch["start_sec"], 60); ts = f"{m:02d}:{s:02d}"
            fallback_sections.append({"title": ch["title"], "start_time": ts,
                                      "key_points": ["請手動整理重點"], "screenshot_at": ts})
    else:
        fallback_sections = [{"title":"完整影片","start_time":"00:00",
                              "key_points":["請手動整理重點"],"screenshot_at":"00:00"}]
    response = json.dumps({
        "title_zh": title,
        "summary": "（LLM 無法分析，請確認 Browser Bridge 已連接）",
        "sections": fallback_sections, "key_insights": [], "data_table": []
    }, ensure_ascii=False)

with open(f"{work_dir}/llm_response.txt", "w") as f: f.write(response)
with open(f"{work_dir}/llm_provider.txt", "w") as f: f.write(llm_provider_used)
print(f"Step 4 done (provider: {llm_provider_used})")
PYEOF
```

---

### Step 5 — Parse + validate JSON

```bash
python3 << 'PYEOF'
import re, json, os, sys

work_dir     = os.environ["WORK_DIR"]
duration_sec = json.load(open(f"{work_dir}/info.json"))["duration_sec"]

with open(f"{work_dir}/llm_response.txt") as f:
    response = f.read()

def extract_json(text):
    m = re.search(r'```(?:json)?\s*([\s\S]+?)\s*```', text)
    if m: return m.group(1)
    m = re.search(r'(\{[\s\S]+\})', text)
    return m.group(1) if m else text

def ts_to_seconds(ts):
    parts = ts.strip().split(":")
    try:
        if len(parts) == 3: return int(parts[0])*3600+int(parts[1])*60+int(float(parts[2]))
        elif len(parts) == 2: return int(parts[0])*60+int(float(parts[1]))
    except: pass
    return 0

def validate(data):
    if not all(k in data for k in ["title_zh","summary","sections"]):
        return False, "missing required keys"
    for s in data.get("sections",[]):
        if not all(k in s for k in ["title","start_time","key_points"]):
            return False, "section missing keys"
        if ts_to_seconds(s["start_time"]) > duration_sec + 60:
            return False, f"timestamp out of range: {s['start_time']}"
        s.setdefault("screenshot_at", s["start_time"])
    return True, "ok"

def smart_repair(s):
    """Find last complete nested object (depth==1), close remaining brackets."""
    best_pos, depth = 0, 0
    for i, ch in enumerate(s):
        if ch == '{': depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 1: best_pos = i + 1
    truncated = s[:best_pos].rstrip().rstrip(',')
    dc = ds = 0
    in_str = esc = False
    for ch in truncated:
        if esc: esc = False; continue
        if ch == '\\' and in_str: esc = True; continue
        if ch == '"' and not esc: in_str = not in_str; continue
        if in_str: continue
        if ch == '{': dc += 1
        elif ch == '}': dc -= 1
        elif ch == '[': ds += 1
        elif ch == ']': ds -= 1
    if in_str: truncated += '"'
    return truncated + ']' * max(0, ds) + '}' * max(0, dc)

# Strip leading emoji / non-JSON chars before first {
raw = re.sub(r'^[^\{]*', '', extract_json(response).strip())

data = None
for label, candidate in [
    ("direct",             raw),
    ("repaired",           smart_repair(raw)),
    ("trailing-comma fix", re.sub(r',\s*([}\]])', r'\1', smart_repair(raw))),
]:
    try:
        data = json.loads(candidate)
        ok, reason = validate(data)
        if ok:
            print(f"Parsed OK ({label})"); break
        print(f"  {label} validation failed: {reason}", file=sys.stderr)
        data = None
    except json.JSONDecodeError as e:
        print(f"  {label} JSON error: {e}", file=sys.stderr)

if data is None:
    print("Using minimal fallback", file=sys.stderr)
    data = {"title_zh":"影片筆記","summary":response[:200],"sections":[],"key_insights":[],"data_table":[]}

with open(f"{work_dir}/analysis.json", "w") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

sections = data.get("sections", [])
print(f"Sections: {len(sections)}")
for s in sections:
    print(f"  [{s.get('start_time','?')}] {s.get('title','?')} → screenshot@{s.get('screenshot_at','?')}")
PYEOF
```

---

### Step 6 — Get stream URLs (no video download)

```bash
python3 << 'PYEOF'
import subprocess, json, os, sys

work_dir = os.environ["WORK_DIR"]
yt_url   = os.environ["YT_URL"]

with open(f"{work_dir}/info.json") as f:
    info = json.load(f)
sections = json.load(open(f"{work_dir}/analysis.json")).get("sections", [])

print(f"Getting stream URLs for {len(sections)} sections (no download)...")

# Get one stream URL per unique timestamp bucket (±30s window)
# yt-dlp -g returns direct HTTP URL(s); we pick the video-only 480p stream
result = subprocess.run(
    ["yt-dlp", "-g", "-f",
     "bestvideo[height<=480][ext=mp4]/bestvideo[height<=480]/best[height<=480]/worst",
     "--no-playlist", yt_url],
    capture_output=True, text=True, timeout=60
)

stream_urls = [u.strip() for u in result.stdout.strip().splitlines() if u.strip()]
# First line is video stream; second (if any) is audio — we only need video
stream_url = stream_urls[0] if stream_urls else ""

if not stream_url:
    print(f"WARNING: Could not get stream URL: {result.stderr[:120]}", file=sys.stderr)
    open(f"{work_dir}/stream_failed", "w").close()
else:
    print(f"Stream URL obtained ({len(stream_url)} chars)")

with open(f"{work_dir}/stream_url.txt", "w") as f:
    f.write(stream_url)
PYEOF
```

---

### Step 7 — Extract screenshots via stream seek (3 candidates per section, pick best by image score)

```bash
python3 << 'PYEOF'
import subprocess, json, os, shutil
from PIL import Image, ImageStat

work_dir   = os.environ["WORK_DIR"]
video_id   = os.environ["VIDEO_ID"]
vault_root = "/Users/yankesswang/Documents/arthurwang_DB"

with open(f"{work_dir}/analysis.json") as f: data = json.load(f)
with open(f"{work_dir}/info.json")     as f: info = json.load(f)
stream_url = open(f"{work_dir}/stream_url.txt").read().strip()

sections     = data.get("sections", [])
duration_sec = info["duration_sec"]
screenshots  = []
stream_ok    = bool(stream_url) and not os.path.exists(f"{work_dir}/stream_failed")

shots_dir = f"{work_dir}/shots"
os.makedirs(shots_dir, exist_ok=True)

def ts_to_seconds(ts):
    parts = ts.strip().split(":")
    try:
        if len(parts) == 3: return int(parts[0])*3600+int(parts[1])*60+int(float(parts[2]))
        elif len(parts) == 2: return int(parts[0])*60+int(float(parts[1]))
    except: pass
    return 0

def secs_to_hhmmss(s):
    h, r = divmod(int(s), 3600); m, s2 = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s2:02d}"

def image_score(path):
    try:
        img = Image.open(path).convert('L').resize((100, 100))
        return ImageStat.Stat(img).stddev[0]
    except: return 0

def seek_screenshot(source, seek_sec, out_path):
    """Seek to seek_sec in source (file or HTTP URL) and grab one frame."""
    subprocess.run([
        "ffmpeg", "-ss", str(seek_sec), "-i", source,
        "-vframes", "1", "-q:v", "3", "-f", "image2", out_path,
        "-y", "-loglevel", "quiet"
    ], capture_output=True, timeout=30)

for i, section in enumerate(sections):
    ts         = section.get("screenshot_at") or section.get("start_time", "00:00")
    center_sec = min(ts_to_seconds(ts), duration_sec - 2)
    shot_name  = f"{video_id}_shot_{i+1:02d}_{secs_to_hhmmss(center_sec).replace(':','')}.jpg"
    shot_path  = os.path.join(vault_root, shot_name)

    print(f"  [{i+1:02d}/{len(sections)}] {ts}", end="", flush=True)

    if not stream_ok:
        # Fallback: yt-dlp --download-sections to grab a short clip then extract frame
        s_str = secs_to_hhmmss(max(0, center_sec - 1))
        e_str = secs_to_hhmmss(center_sec + 5)
        clip  = f"{shots_dir}/clip_{i+1:02d}.mp4"
        subprocess.run([
            "yt-dlp", "--download-sections", f"*{s_str}-{e_str}",
            "-f", "worst[ext=mp4]/worst", "--force-keyframes-at-cuts",
            "-o", clip, "--no-playlist", os.environ["YT_URL"]
        ], capture_output=True, text=True, timeout=120)
        if os.path.exists(clip) and os.path.getsize(clip) > 1000:
            seek_screenshot(clip, 1, shot_path)
            os.remove(clip)
        if os.path.exists(shot_path):
            print(f" ✓ fallback ({os.path.getsize(shot_path)//1024}KB)", flush=True)
            screenshots.append({"section_idx": i, "filename": shot_name, "timestamp": ts})
        else:
            print(" SKIP", flush=True)
        continue

    # 3 candidates at center-5s, center, center+5s — seek directly in stream URL
    candidates = []
    for off in [-5, 0, 5]:
        sec  = max(0, min(center_sec + off, duration_sec - 1))
        cand = f"{shots_dir}/cand_{i+1:02d}_off{off:+d}.jpg"
        seek_screenshot(stream_url, sec, cand)
        if os.path.exists(cand) and os.path.getsize(cand) > 500:
            candidates.append((image_score(cand), cand))

    if not candidates:
        print(" SKIP (no frames)", flush=True); continue

    candidates.sort(reverse=True)
    best_score, best_path = candidates[0]
    shutil.copy(best_path, shot_path)
    for _, p in candidates:
        if os.path.exists(p): os.remove(p)

    print(f" ✓ score={best_score:.1f} ({os.path.getsize(shot_path)//1024}KB)", flush=True)
    screenshots.append({"section_idx": i, "filename": shot_name, "timestamp": ts})

with open(f"{work_dir}/screenshots.json", "w") as f:
    json.dump(screenshots, f, ensure_ascii=False, indent=2)
print(f"\nScreenshots: {len(screenshots)}/{len(sections)}")
PYEOF
```

---

### Step 8 — Generate Obsidian note

```bash
python3 << 'PYEOF'
import json, os, re
from datetime import date

work_dir = os.environ["WORK_DIR"]
yt_url   = os.environ["YT_URL"]
video_id = os.environ["VIDEO_ID"]
note_dir = "/Users/yankesswang/Documents/arthurwang_DB/AI Knowledge/影片筆記"

with open(f"{work_dir}/analysis.json")    as f: data  = json.load(f)
with open(f"{work_dir}/info.json")         as f: info  = json.load(f)
with open(f"{work_dir}/screenshots.json")  as f: shots = json.load(f)

title_zh     = data.get("title_zh", info["title"])
summary      = data.get("summary", "")
sections     = data.get("sections", [])
key_insights = data.get("key_insights", [])
data_table   = data.get("data_table", [])
shot_map     = {s["section_idx"]: s["filename"] for s in shots}
today        = date.today().isoformat()

def ts_to_seconds(ts):
    parts = ts.strip().split(":")
    try:
        if len(parts) == 3: return int(parts[0])*3600+int(parts[1])*60+int(float(parts[2]))
        elif len(parts) == 2: return int(parts[0])*60+int(float(parts[1]))
    except: pass
    return 0

def yt_link(ts):
    return f"https://www.youtube.com/watch?v={video_id}&t={ts_to_seconds(ts)}s"

# json.dumps for YAML-safe quoting (handles colons, quotes, special chars)
def yq(x):
    return json.dumps(str(x), ensure_ascii=False)

lines = [
    "---", "tags:", "  - 影片筆記", "  - YouTube",
    f"source: {yq(yt_url)}",
    f"channel: {yq(info['channel'])}",
    f"duration: {yq(info['duration'])}",
    f"created: {yq(today)}",
    "---", "",
    f"# {title_zh}", "",
    "> [!abstract] TL;DR",
    f"> {summary}", "",
    "## 影片資訊", "",
    "| 欄位 | 內容 |", "| ---- | ---- |",
    f"| 頻道 | {info['channel']} |",
    f"| 時長 | {info['duration']} |",
    f"| 來源 | [{info['title']}]({yt_url}) |", "",
    "## 章節筆記", "",
]

for i, sec in enumerate(sections):
    start   = sec.get("start_time", "00:00")
    title_s = sec.get("title", f"章節 {i+1}")
    points  = sec.get("key_points", [])
    # Plain Markdown link — avoid [[wikilink]] collision in Obsidian
    lines.append(f"### {i+1}. [{start}]({yt_link(start)}) {title_s}")
    lines.append("")
    if i in shot_map:
        lines += [f"![[{shot_map[i]}]]", ""]
    for pt in points:
        lines.append(f"- {pt}")
    lines.append("")

if key_insights:
    lines += ["## 關鍵洞見", ""]
    for ins in key_insights: lines.append(f"- {ins}")
    lines.append("")

lines += ["## 附：關鍵數據速查", ""]
if data_table:
    lines += ["| 指標 | 數值 | 備註 |", "| ---- | ---- | ---- |"]
    for row in data_table:
        lines.append(f"| {row.get('指標','')} | {row.get('數值','')} | {row.get('備註','')} |")
else:
    lines += ["| 指標 | 數值 | 備註 |", "| ---- | ---- | ---- |",
              "| （影片無具體數字） | — | — |"]
lines.append("")

note_content = "\n".join(lines)

# Include video_id in filename to prevent overwrite on re-run or title collision
safe_title = re.sub(r'[/\\:*?"<>|]', ' ', title_zh).strip()
safe_title = re.sub(r'\s+', ' ', safe_title)[:70]
note_path  = os.path.join(note_dir, f"{safe_title} - {video_id}.md")

with open(note_path, "w", encoding="utf-8") as f:
    f.write(note_content)
with open(f"{work_dir}/note_path.txt", "w") as f:
    f.write(note_path)
print(f"Note: {note_path}")
PYEOF
```

---

### Step 9 — Write manifest + report

```bash
python3 << 'PYEOF'
import json, os
from datetime import date

work_dir = os.environ["WORK_DIR"]
video_id = os.environ["VIDEO_ID"]
yt_url   = os.environ["YT_URL"]

with open(f"{work_dir}/info.json")        as f: info      = json.load(f)
with open(f"{work_dir}/analysis.json")    as f: data      = json.load(f)
with open(f"{work_dir}/screenshots.json") as f: shots     = json.load(f)
with open(f"{work_dir}/note_path.txt")    as f: note_path = f.read().strip()

llm_provider = open(f"{work_dir}/llm_provider.txt").read().strip() \
    if os.path.exists(f"{work_dir}/llm_provider.txt") else "unknown"
sections = data.get("sections", [])
has_vtt  = os.path.exists(f"{work_dir}/condensed.txt") \
    and not open(f"{work_dir}/condensed.txt").read().startswith("[Description]")

manifest = {
    "video_id":          video_id,
    "url":               yt_url,
    "title":             info["title"],
    "channel":           info["channel"],
    "duration":          info["duration"],
    "note_path":         note_path,
    "created":           date.today().isoformat(),
    "has_transcript":    has_vtt,
    "has_chapters":      info["has_chapters"],
    "chapters_count":    len(info.get("chapters", [])),
    "llm_provider":      llm_provider,
    "sections_count":    len(sections),
    "screenshots_count": len(shots),
    "screenshots_ok":    len(shots) == len(sections),
}
with open(f"{work_dir}/manifest.json", "w") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

short = note_path.replace("/Users/yankesswang/Documents/arthurwang_DB/", "")
print(f"\n✓ Note:        {short}")
print(f"✓ Screenshots: {len(shots)}/{len(sections)} (3-candidate, best image score)")
print(f"✓ Provider:    {llm_provider}")
print(f"✓ Chapters:    {'yes (' + str(len(info.get('chapters',[]))) + ')' if info['has_chapters'] else 'no (LLM inferred)'}")
print(f"✓ Transcript:  {'yes' if has_vtt else 'description only'}")
for s in shots:
    print(f"   shot {s['section_idx']+1:02d} [{s['timestamp']}]: {s['filename']}")
print(f"\nManifest → {work_dir}/manifest.json")
PYEOF
```

---

## Edge Cases

| Situation | Action |
| --------- | ------ |
| YouTube chapters available | Used as section boundaries; LLM only fills content |
| shorts / embed / live URL | Step 1 parser handles all 4 URL patterns |
| No transcript | Use video description (up to 3000 chars) |
| Gemini not connected | Auto-fallback to `opencli chatgpt-app ask` |
| Both CLIs unavailable | Skeleton note using chapter titles as placeholders |
| LLM returns truncated JSON | `smart_repair()` finds last complete section, closes brackets |
| LLM response has emoji prefix | Strip non-`{` chars before parsing |
| Timestamp out of range | Validation rejects; fallback to section start_time |
| Stream URL unavailable | Per-section `--download-sections` fallback (downloads short clip) |
| Long video (>12K chars) | Chunked: each partial capped 1500 chars → balanced merge |
| Same video re-run | note filename has `video_id` → no overwrite |
| YAML special chars | All frontmatter values wrapped with `json.dumps()` |
| PIL not installed | Caught in Step 1 dependency check before any network call |

---

## Architecture

```
URL (v=, youtu.be, shorts, embed, live)
 │
 ├─ Step 1: parse + dep check (yt-dlp, ffmpeg, Pillow)
 ├─ Step 2: yt-dlp → meta.json (chapters) + transcript.vtt
 ├─ Step 3: VTT parse → 30s bucket merge + dedupe → condensed.txt
 │           chapters → info.json
 ├─ Step 4: LLM (Gemini → ChatGPT fallback)
 │           chapters-aware · chunked (partial 1500c) → merge
 ├─ Step 5: strip emoji → smart_repair → validate → analysis.json
 ├─ Step 6: yt-dlp -g → stream_url.txt (no download, just HTTP URL)
 ├─ Step 7: ffmpeg -ss <sec> -i <stream_url> → 3 candidates (±5s) → image std-dev → best
 │           fallback: --download-sections short clip if stream URL fails
 ├─ Step 8: note with [MM:SS](yt-link) · ![[shot]] · json.dumps YAML
 │           filename = title[:70] + video_id (no overwrite)
 └─ Step 9: manifest.json + report
```
