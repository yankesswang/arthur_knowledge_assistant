---
name: youtube-subtitle
description: YouTube URL → 下載影片 + 取得字幕 → Gemini 翻譯繁體中文 → ffmpeg 硬燒雙語字幕 → 輸出 mp4；或 MP3/音訊檔 → faster-whisper 逐字稿
tags: [youtube, subtitle, translate, ffmpeg, 字幕, 翻譯, gemini, whisper, transcript, mp3]
allowed-tools: Bash
---

# /youtube-subtitle

## 模式判斷

**若使用者提供 YouTube URL** → 執行 YouTube 字幕燒錄流程（Steps 0–8）

**若使用者提供本地音訊檔案路徑**（`.mp3 / .m4a / .wav / .flac`）→ 執行 MP3 逐字稿模式

---

## 模式 A：YouTube 字幕燒錄

給定 YouTube URL，自動完成：
1. 下載影片（1080p）
2. 下載現有字幕（優先英文，若無則 auto-generated）
3. 標點恢復（deepmultilingualpunctuation，fallback 規則式）
4. 用 `opencli gemini ask` 翻譯成繁體中文（批次 150 條）
5. 產生雙語 ASS 字幕（上方原文白色 / 下方中文青色），時間戳對齊實際說話時間
6. ffmpeg 硬燒字幕輸出 mp4

**完全 headless，不需要瀏覽器視窗（Gemini 需要 Browser Bridge extension 連線）。**

## Usage

```
/youtube-subtitle https://youtu.be/VIDEO_ID
/youtube-subtitle https://www.youtube.com/watch?v=VIDEO_ID --lang zh-TW
/youtube-subtitle https://youtu.be/VIDEO_ID --output /tmp/out.mp4
```

## 參數

| 參數 | 說明 | 預設 |
|------|------|------|
| URL | YouTube 影片 URL（必填） | — |
| `--lang` | 目標翻譯語言（BCP-47） | `zh-TW` |
| `--output` | 輸出路徑 | `/tmp/yt_sub/<video_id>.mp4` |
| `--style` | 字幕樣式：`bilingual`（雙語）/ `target-only`（僅中文） | `bilingual` |

---

## What You Must Do When Invoked

Follow these steps in order. Do not skip or reorder.

---

### Step 0 — 解析使用者輸入

從使用者訊息中提取：
- `YT_URL`：完整 YouTube URL
- `TARGET_LANG`：目標語言（預設 `zh-TW`）
- `OUTPUT_PATH`：輸出路徑（若未指定，用 `/tmp/yt_sub/<video_id>.mp4`）
- `SUB_STYLE`：`bilingual`（預設）或 `target-only`

---

### Step 1 — 環境檢查 + 解析 Video ID

```bash
export YT_URL="<使用者提供的 URL>"
export TARGET_LANG="${TARGET_LANG:-zh-TW}"
export SUB_STYLE="${SUB_STYLE:-bilingual}"

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

if [ -z "$VIDEO_ID" ]; then echo "ERROR: 無法解析 Video ID"; exit 1; fi

export WORK_DIR="/tmp/yt_sub/$VIDEO_ID"
export OUTPUT_PATH="${OUTPUT_PATH:-$WORK_DIR/$VIDEO_ID.mp4}"
mkdir -p "$WORK_DIR"
echo "Video ID: $VIDEO_ID"
echo "Work dir: $WORK_DIR"

# 依賴檢查
YT_DLP=""
for candidate in \
    /home/trx50/.virtualenvs/chatbot/bin/yt-dlp \
    "$HOME/.local/bin/yt-dlp" \
    "$(which yt-dlp 2>/dev/null)"; do
    if [ -x "$candidate" ]; then YT_DLP="$candidate"; break; fi
done
[ -z "$YT_DLP" ] && { echo "ERROR: yt-dlp 找不到"; exit 1; }
export YT_DLP

command -v ffmpeg >/dev/null || { echo "ERROR: ffmpeg 找不到"; exit 1; }
echo "Dependencies OK: yt-dlp=$YT_DLP, ffmpeg=$(which ffmpeg)"

# 確認 opencli/Gemini 連線
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22 --silent
opencli doctor 2>&1 | grep -E "OK|ERROR"
```

---

### Step 2 — 取得影片 metadata + 下載影片

```bash
# Metadata
"$YT_DLP" --dump-json --no-playlist "$YT_URL" 2>/dev/null > "$WORK_DIR/meta.json"
TITLE=$(python3 -c "
import json, re
d = json.load(open('$WORK_DIR/meta.json'))
t = d.get('title','video')
t = re.sub(r'[/\\\\:*?\"<>|]', ' ', t).strip()
t = re.sub(r'\s+', ' ', t)[:60]
print(t)
" 2>/dev/null || echo "video")
export TITLE
echo "Title: $TITLE"

# 下載影片（1080p）
"$YT_DLP" \
  -f "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best[height<=1080]/best" \
  --merge-output-format mp4 \
  --no-playlist \
  -o "$WORK_DIR/video.%(ext)s" \
  "$YT_URL" 2>&1 | tail -5

export VIDEO_FILE=$(ls "$WORK_DIR"/video.mp4 "$WORK_DIR"/video.mkv "$WORK_DIR"/video.webm 2>/dev/null | head -1)
if [ -z "$VIDEO_FILE" ] || [ ! -s "$VIDEO_FILE" ]; then
  echo "ERROR: 影片下載失敗"; exit 1
fi
echo "Video: $VIDEO_FILE ($(du -sh "$VIDEO_FILE" | cut -f1))"
```

---

### Step 3 — 下載字幕（優先英文，fallback auto-generated）

```bash
python3 << 'PYEOF'
import subprocess, os, glob

work_dir  = os.environ["WORK_DIR"]
yt_url    = os.environ["YT_URL"]
yt_dlp    = os.environ["YT_DLP"]

sub_args_list = [
    ["--write-subs", "--no-write-auto-subs", "--sub-lang", "en,en-US,en-GB"],
    ["--write-auto-subs", "--no-write-subs", "--sub-lang", "en,en-US"],
    ["--write-subs", "--no-write-auto-subs", "--sub-lang", "en,zh-TW,zh,ja,ko,de,fr,es"],
]

found = None
for args in sub_args_list:
    cmd = [yt_dlp, "--skip-download"] + args + [
        "--sub-format", "vtt",
        "--no-playlist",
        "-o", f"{work_dir}/subs.%(ext)s",
        yt_url
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    vtt_files = glob.glob(f"{work_dir}/subs.*.vtt")
    if vtt_files:
        found = vtt_files[0]
        print(f"字幕下載成功: {os.path.basename(found)}")
        break
    print(f"  嘗試失敗: {' '.join(args[:3])} | stderr: {r.stderr[:80]}")

if not found:
    print("WARNING: 無法取得字幕")
    import json
    meta = json.load(open(f"{work_dir}/meta.json"))
    open(f"{work_dir}/no_subs", "w").close()
else:
    with open(f"{work_dir}/vtt_path.txt", "w") as f:
        f.write(found)
PYEOF
```

---

### Step 4 — 解析 VTT，保留實際說話時間戳

**重要**：不要強制第一條從 0 開始，保留 VTT 真實的說話開始時間，避免靜音段顯示字幕。

```bash
python3 << 'PYEOF'
import re, json, os

work_dir = os.environ["WORK_DIR"]

if os.path.exists(f"{work_dir}/no_subs"):
    print("無字幕檔，跳過解析步驟")
    json.dump([], open(f"{work_dir}/srt_entries.json", "w"))
    exit(0)

vtt_path = open(f"{work_dir}/vtt_path.txt").read().strip()
with open(vtt_path, encoding="utf-8", errors="ignore") as f:
    content = f.read()

# 清理 VTT 標籤
content = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', content)
content = re.sub(r'</?[a-zA-Z][\w.]*>', '', content)
for ent, val in [('&gt;','>'),('&lt;','<'),('&amp;','&'),('&nbsp;',' '),('&#39;',"'")]:
    content = content.replace(ent, val)

blocks = re.split(r'\n{2,}', content.strip())
entries = []

for block in blocks:
    lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
    ts_line = next((l for l in lines if '-->' in l), None)
    if not ts_line:
        continue

    ts_parts = ts_line.split('-->')
    def parse_ts(s):
        s = s.strip().split()[0].replace(',', '.')
        parts = s.split(':')
        try:
            if len(parts) == 3:
                return float(parts[0])*3600 + float(parts[1])*60 + float(parts[2])
            elif len(parts) == 2:
                return float(parts[0])*60 + float(parts[1])
        except:
            pass
        return 0.0

    start = parse_ts(ts_parts[0])
    end   = parse_ts(ts_parts[1]) if len(ts_parts) > 1 else start + 3.0
    text = ' '.join(l for l in lines if '-->' not in l and not l.isdigit()).strip()
    text = re.sub(r'\s+', ' ', text)
    if text and not text.startswith('[') and len(text) > 1:
        entries.append({"start": start, "end": end, "original": text})

# YouTube auto-sub 結構：每兩條一組，取 duration >= 0.1s 的偶數條
clean = [e for e in entries if (e["end"] - e["start"]) >= 0.1]
real  = clean[1::2]
if len(clean) % 2 == 1:
    real.append(clean[-1])

# 合併成 ~6 秒段落，start 用實際說話開始時間（不補 0）
CHUNK_DURATION = 6.0
chunks = []
buf_texts, buf_start, buf_end = [], None, None

for e in real:
    if buf_start is None:
        buf_start = e["start"]   # 實際說話開始，保留靜音間隔
    buf_texts.append(e["original"])
    buf_end = e["end"]
    if (buf_end - buf_start) >= CHUNK_DURATION:
        chunks.append({"start": buf_start, "end": buf_end, "original": " ".join(buf_texts)})
        buf_texts, buf_start, buf_end = [], None, None

if buf_texts:
    chunks.append({"start": buf_start, "end": buf_end, "original": " ".join(buf_texts)})

with open(f"{work_dir}/srt_entries.json", "w") as f:
    json.dump(chunks, f, ensure_ascii=False, indent=2)

print(f"解析完成：raw={len(entries)} → clean={len(clean)} → 片段={len(real)} → 合併={len(chunks)} 段")
if chunks:
    print(f"  第一段: [{chunks[0]['start']:.1f}s] {chunks[0]['original'][:60]}")
    print(f"  最後段: [{chunks[-1]['start']:.1f}s] {chunks[-1]['original'][:60]}")
PYEOF
```

---

### Step 4.5 — 標點恢復（deepmultilingualpunctuation）

```bash
/home/trx50/.virtualenvs/chatbot/bin/python3 << 'PYEOF'
import json, os, re

work_dir = os.environ["WORK_DIR"]
entries = json.load(open(f"{work_dir}/srt_entries.json"))
if not entries:
    print("無字幕條目，跳過標點恢復")
    exit(0)

def restore_punct_neural(texts):
    from deepmultilingualpunctuation import PunctuationModel
    model = PunctuationModel()
    return [model.restore_punctuation(t) for t in texts]

def restore_punct_rule(text):
    text = text.strip()
    if text:
        text = text[0].upper() + text[1:]
    if text and text[-1] not in ".!?,;:":
        text += "."
    return text

texts = [e["original"] for e in entries]

try:
    print("使用 deepmultilingualpunctuation 恢復標點...")
    restored = restore_punct_neural(texts)
    method = "neural"
except Exception as ex:
    print(f"Neural 標點失敗（{ex}），使用規則式 fallback")
    restored = [restore_punct_rule(t) for t in texts]
    method = "rule"

for entry, new_text in zip(entries, restored):
    entry["original"] = new_text

with open(f"{work_dir}/srt_entries.json", "w") as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f"標點恢復完成（{method}）：{len(entries)} 條")
if entries:
    print(f"  範例: {entries[0]['original'][:80]}")
PYEOF
```

---

### Step 5 — 翻譯（opencli gemini ask，批次 150 條）

```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 22 --silent

python3 << 'PYEOF'
import json, subprocess, os, re

work_dir = os.environ["WORK_DIR"]
entries = json.load(open(f"{work_dir}/srt_entries.json"))
if not entries:
    print("無字幕條目，跳過翻譯")
    exit(0)

BATCH = 150

# 加上 idx 方便對應
for i, e in enumerate(entries):
    e["idx"] = i

def gemini_translate(batch_entries):
    lines = "\n".join(f"{e['idx']}|{e['original']}" for e in batch_entries)
    prompt = (
        "你是專業字幕翻譯，以下是英文演講逐字稿，每行格式「序號|英文」，每段約 6 秒。\n"
        "翻譯規則：輸出「序號|繁體中文」，行數序號一一對應，翻譯自然流暢，\n"
        "片段句中斷則結尾不加標點，保留技術術語（LLM、GPU、token、AI 等），只輸出翻譯。\n\n"
        + lines
    )
    result = subprocess.run(
        ["opencli", "gemini", "ask", "--format", "plain", "--new", "true", prompt],
        capture_output=True, text=True, timeout=120
    )
    return result.stdout.strip()

results = {}

for batch_start in range(0, len(entries), BATCH):
    batch = entries[batch_start:batch_start+BATCH]
    batch_num = batch_start // BATCH + 1
    total_batches = (len(entries) + BATCH - 1) // BATCH
    print(f"批次 {batch_num}/{total_batches}（{batch_start}–{batch_start+len(batch)-1}）...", flush=True)

    output = gemini_translate(batch)
    parsed = 0
    for line in output.strip().split("\n"):
        m = re.match(r'^(\d+)\|(.+)$', line.strip())
        if m:
            results[int(m.group(1))] = m.group(2).strip()
            parsed += 1
    print(f"  → 解析 {parsed}/{len(batch)} 條", flush=True)

# 補翻缺漏
missing = [e for e in entries if e["idx"] not in results]
if missing:
    print(f"補翻 {len(missing)} 條...")
    for e in missing:
        prompt = (
            "你是專業字幕翻譯，以下是英文演講逐字稿，每行格式「序號|英文」。\n"
            "翻譯規則：輸出「序號|繁體中文」，翻譯自然流暢，只輸出翻譯。\n\n"
            f"{e['idx']}|{e['original']}"
        )
        result = subprocess.run(
            ["opencli", "gemini", "ask", "--format", "plain", "--new", "true", prompt],
            capture_output=True, text=True, timeout=60
        )
        raw = result.stdout.strip()
        # 清理可能的 emoji + 序號前綴
        raw = re.sub(r'^[^\w\u4e00-\u9fff]*\d+\|', '', raw)
        raw = re.sub(r'[\U0001F300-\U0001F9FF]', '', raw).strip()
        results[e["idx"]] = raw

# 填回並清理
for e in entries:
    t = results.get(e["idx"], "")
    # 清理殘留的 emoji / 序號前綴
    t = re.sub(r'^[^\w\u4e00-\u9fff]*\d+\|', '', t)
    t = re.sub(r'[\U0001F300-\U0001F9FF]', '', t).strip()
    e["translated"] = t

with open(f"{work_dir}/srt_entries.json", "w") as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

ok = sum(1 for e in entries if e.get("translated"))
print(f"翻譯完成：{ok}/{len(entries)}")
for e in entries[:3]:
    print(f"  [{e['start']:.1f}s] {e['original'][:40]}")
    print(f"        → {e['translated'][:40]}")
PYEOF
```

---

### Step 6 — 產生 ASS 字幕檔（雙語或純中文）

PlayRes 依影片解析度設定（1080p → 1920×1080，480p → 854×480）。
字體大小：1080p 用 28px，480p 用 22px。

```bash
python3 << 'PYEOF'
import json, os, subprocess

work_dir  = os.environ["WORK_DIR"]
sub_style = os.environ.get("SUB_STYLE", "bilingual")
video_file = next((f for f in [
    f"{work_dir}/video.mp4",
    f"{work_dir}/video.mkv",
] if os.path.exists(f)), "")

# 偵測影片解析度
height = 480
if video_file:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=height", "-of", "csv=p=0", video_file],
        capture_output=True, text=True
    )
    try:
        height = int(r.stdout.strip())
    except:
        pass

if height >= 720:
    play_w, play_h, font_size, margin_v = 1920, 1080, 28, 35
else:
    play_w, play_h, font_size, margin_v = 854, 480, 22, 25

entries = json.load(open(f"{work_dir}/srt_entries.json"))
if not entries:
    print("無字幕條目")
    open(f"{work_dir}/no_subs", "w").close()
    exit(0)

def secs_to_ass(s):
    h  = int(s) // 3600
    m  = (int(s) % 3600) // 60
    sc = s % 60
    return f"{h}:{m:02d}:{sc:05.2f}"

ASS_HEADER = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
ScaledBorderAndShadow: yes
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,Noto Sans CJK TC,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,30,30,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

lines = [ASS_HEADER]

for e in entries:
    start = secs_to_ass(e["start"])
    end   = secs_to_ass(e["end"])
    zh    = e.get("translated", "").replace("\\", "").replace("{", "").replace("}", "")
    orig  = e["original"].replace("\\", "").replace("{", "").replace("}", "")

    if sub_style == "bilingual" and zh:
        # 英文白色（上） \N 中文青色（下）
        text = f"{orig}\\N{{\\c&H00FFFF&}}{zh}{{\\c&H00FFFFFF&}}"
    elif sub_style == "target-only" and zh:
        text = f"{{\\c&H00FFFF&}}{zh}{{\\c&H00FFFFFF&}}"
    else:
        text = orig

    lines.append(f"Dialogue: 0,{start},{end},Sub,,0,0,0,,{text}")

ass_path = f"{work_dir}/subtitles.ass"
with open(ass_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
with open(f"{work_dir}/ass_path.txt", "w") as f:
    f.write(ass_path)

print(f"ASS 字幕產生完成: {ass_path}")
print(f"  解析度: {play_w}×{play_h}，字體: {font_size}px，{len(entries)} 條")
PYEOF
```

---

### Step 7 — ffmpeg 硬燒字幕輸出 mp4

```bash
python3 << 'PYEOF'
import subprocess, os, glob

work_dir    = os.environ["WORK_DIR"]
video_id    = os.environ["VIDEO_ID"]
output_path = os.environ.get("OUTPUT_PATH", f"{work_dir}/{video_id}.mp4")

video_file = next((f for f in [
    f"{work_dir}/video.mp4",
    f"{work_dir}/video.mkv",
] if os.path.exists(f)), "")

if not video_file:
    files = glob.glob(f"{work_dir}/video.*")
    video_file = files[0] if files else ""

if not video_file:
    print("ERROR: 找不到影片檔案"); exit(1)

if os.path.exists(f"{work_dir}/no_subs"):
    print("無字幕，直接複製影片...")
    subprocess.run(["ffmpeg", "-i", video_file, "-c", "copy", output_path, "-y", "-loglevel", "quiet"], check=True)
    print(f"輸出（無字幕）: {output_path}")
    exit(0)

ass_path = open(f"{work_dir}/ass_path.txt").read().strip()
os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

print(f"ffmpeg 硬燒字幕中...")
print(f"  輸入: {video_file}")
print(f"  字幕: {ass_path}")
print(f"  輸出: {output_path}")

ass_escaped = ass_path.replace("\\", "/").replace(":", "\\:")

result = subprocess.run([
    "ffmpeg", "-i", video_file,
    "-vf", f"ass={ass_escaped}",
    "-c:v", "libx264", "-crf", "22", "-preset", "fast",
    "-c:a", "aac", "-b:a", "128k",
    "-movflags", "+faststart",
    output_path, "-y",
    "-loglevel", "warning", "-stats",
], capture_output=True, text=True, timeout=1800)

if result.returncode != 0:
    print(f"ffmpeg 錯誤:\n{result.stderr[-500:]}")
    exit(1)

size_mb = os.path.getsize(output_path) / 1024 / 1024
print(f"\n輸出完成: {output_path}")
print(f"檔案大小: {size_mb:.1f} MB")

with open(f"{work_dir}/output_path.txt", "w") as f:
    f.write(output_path)
PYEOF
```

---

### Step 8 — 報告

```bash
python3 << 'PYEOF'
import json, os

work_dir = os.environ["WORK_DIR"]

meta        = json.load(open(f"{work_dir}/meta.json")) if os.path.exists(f"{work_dir}/meta.json") else {}
entries     = json.load(open(f"{work_dir}/srt_entries.json")) if os.path.exists(f"{work_dir}/srt_entries.json") else []
output_path = open(f"{work_dir}/output_path.txt").read().strip() if os.path.exists(f"{work_dir}/output_path.txt") else "unknown"
has_subs    = not os.path.exists(f"{work_dir}/no_subs")
ok_trans    = sum(1 for e in entries if e.get("translated"))

print("=" * 50)
print("youtube-subtitle 完成")
print("=" * 50)
print(f"  影片  : {meta.get('title','?')[:60]}")
print(f"  頻道  : {meta.get('channel','?')}")
print(f"  時長  : {int(meta.get('duration',0)//60)}:{int(meta.get('duration',0)%60):02d}")
print(f"  字幕  : {'有 (' + str(len(entries)) + ' 條)' if has_subs else '無（無原始字幕）'}")
if has_subs:
    print(f"  翻譯  : {ok_trans}/{len(entries)} 條 → {os.environ.get('TARGET_LANG','zh-TW')} (Gemini)")
    print(f"  樣式  : {os.environ.get('SUB_STYLE','bilingual')}")
print(f"  輸出  : {output_path}")
if os.path.exists(output_path):
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"  大小  : {size_mb:.1f} MB")
PYEOF
```

---

## Edge Cases

| 情況 | 處理方式 |
|------|---------|
| 影片無任何字幕 | 直接輸出不含字幕的影片，報告說明 |
| 字幕只有 auto-generated | 優先使用，合併碎片後翻譯 |
| Gemini 輸出不足（truncation） | 逐條補翻缺漏 idx |
| Gemini 輸出含 emoji 前綴 | regex 清理 `emoji + 序號|` 前綴 |
| deepmultilingualpunctuation 失敗 | 自動 fallback 規則式（首字大寫+句末加句號） |
| opencli 未連線 | Step 1 doctor 提示，確保 Chrome + Browser Bridge 已開啟 |
| 影片開頭有靜音段 | Step 4 保留實際說話時間（不強制從 0 開始） |
| 影片超長（>1小時） | ffmpeg timeout 設 30 分鐘 |
| 1080p vs 480p 解析度 | Step 6 自動偵測 ffprobe，調整 PlayRes / 字體大小 |
| yt-dlp 路徑因 venv 不同 | Step 1 多路徑搜尋 |

## 架構

```
模式 A：YouTube URL
 │
 ├─ Step 0: 解析使用者參數
 ├─ Step 1: Video ID 解析 + 依賴檢查（yt-dlp / ffmpeg / opencli）
 ├─ Step 2: yt-dlp → meta.json + video.mp4（1080p）
 ├─ Step 3: yt-dlp --write-subs → .vtt（手動→auto fallback）
 ├─ Step 4: VTT 解析 → srt_entries.json（保留實際說話時間戳）
 ├─ Step 4.5: deepmultilingualpunctuation 恢復英文標點（fallback 規則式）
 ├─ Step 5: opencli gemini ask 批次翻譯（150條/批）+ 補翻缺漏
 ├─ Step 6: srt_entries → subtitles.ass（雙語/僅中文，自動偵測解析度）
 ├─ Step 7: ffmpeg ass= filter → 硬燒 mp4
 └─ Step 8: 報告（標題/字幕數/翻譯率/輸出路徑/大小）

模式 B：本地音訊
 │
 └─ scripts/mp3_to_transcript.py → <stem>_transcript.txt + <stem>_transcript.json
```

> 翻譯使用 Gemini（opencli），需要 Browser Bridge extension 連線。

---

## 模式 B：MP3 / 本地音訊 → 逐字稿

### 觸發條件

使用者提供的輸入**不是 YouTube URL**，而是本地音訊檔案路徑（`.mp3 / .m4a / .wav / .flac` 等）。

### Usage

```
/youtube-subtitle /path/to/podcast.mp3
/youtube-subtitle /path/to/lecture.mp3 --lang en
/youtube-subtitle /path/to/interview.mp3 --model medium --output-dir /tmp/transcripts
```

### 參數

| 參數 | 說明 | 預設 |
|------|------|------|
| 音訊路徑 | 本地音訊檔案（必填） | — |
| `--lang` | 音訊語言（ISO 639-1，如 `en/zh/ja`）；不指定則自動偵測 | 自動 |
| `--model` | Whisper 模型：`tiny/base/small/medium/large-v2/large-v3` | `large-v3` |
| `--output-dir` | 輸出目錄 | 與音訊同目錄 |
| `--format` | 輸出格式：`txt / json / both` | `both` |

### What You Must Do When Invoked（模式 B）

**Step 1 — 解析參數**

從使用者輸入提取：
- `AUDIO_PATH`：音訊檔案路徑
- 其他選項：`--lang`、`--model`、`--output-dir`、`--format`（有給才帶入）

**Step 2 — 執行 script**

```bash
SKILL_DIR="/home/trx50/Project/arthur_knowledge_assistant/.agent/skills/youtube-subtitle"
PYTHON="/home/trx50/.virtualenvs/chatbot/bin/python3"

$PYTHON "$SKILL_DIR/scripts/mp3_to_transcript.py" \
  "<AUDIO_PATH>" \
  [--lang <lang>] \
  [--model <model>] \
  [--output-dir <dir>] \
  [--format <fmt>]
```

**Step 3 — 報告**

script 執行完後，顯示：
- 偵測語言（若未指定）
- 轉錄段數與音訊時長
- 輸出檔案路徑（.txt 和/或 .json）

### 輸出格式

**TXT**（`<stem>_transcript.txt`）：
```
[00:00.00] And so what we're going to talk about today...
[00:06.50] The key insight here is that...
```

**JSON**（`<stem>_transcript.json`）：
```json
{
  "language": "en",
  "language_probability": 0.9987,
  "duration": 3642.5,
  "segments": [
    { "start": 0.0, "end": 6.2, "text": "And so what we're going to talk about today..." }
  ]
}
```

### Edge Cases（模式 B）

| 情況 | 處理方式 |
|------|---------|
| 找不到音訊檔案 | 顯示錯誤訊息，exit 1 |
| 無 GPU | 自動使用 CPU + int8 量化 |
| large-v3 太慢 | 建議使用者改用 `--model medium` |
| 語言偵測錯誤 | 請使用者明確指定 `--lang` |
