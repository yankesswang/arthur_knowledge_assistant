#!/usr/bin/env bash
# Steps 5-7: generate Obsidian note → update reading list → report
set -e

VIDEO_ID="$1"
if [ -z "$VIDEO_ID" ]; then echo "Usage: finalize.sh <video_id>"; exit 1; fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORK_DIR="$SCRIPT_DIR/../data/transcripts/$VIDEO_ID"

if [ ! -f "$WORK_DIR/analysis.json" ]; then
  echo "ERROR: $WORK_DIR/analysis.json not found. Claude analysis must run first."; exit 1
fi

# ── Step 5: Generate Obsidian note ──────────────────────────────────────────
YT_URL=$(python3 -c "import json; d=json.load(open('$WORK_DIR/meta.json')); print(d.get('webpage_url',''))" 2>/dev/null)
YT_URL="$YT_URL" VIDEO_ID="$VIDEO_ID" WORK_DIR="$WORK_DIR" python3 "$SCRIPT_DIR/generate_note.py"

# ── Step 6: Update 待看影片與Podcast清單 ────────────────────────────────────────────────
WORK_DIR="$WORK_DIR" python3 "$SCRIPT_DIR/update_reading_list.py"

# ── Step 6b: Update _INDEX.md ────────────────────────────────────────────────
WORK_DIR="$WORK_DIR" VIDEO_ID="$VIDEO_ID" python3 "$SCRIPT_DIR/update_index.py"

# ── Step 7: Report ───────────────────────────────────────────────────────────
python3 << PYEOF
import json, os

work_dir = "$WORK_DIR"
with open(f"{work_dir}/info.json")     as f: info      = json.load(f)
with open(f"{work_dir}/analysis.json") as f: data      = json.load(f)
with open(f"{work_dir}/note_path.txt") as f: note_path = f.read().strip()

sections = data.get("sections", [])
insights = data.get("key_insights", [])
has_vtt  = os.path.exists(f"{work_dir}/condensed.txt") and \
    not open(f"{work_dir}/condensed.txt").read().startswith("[Description")

short = note_path.replace("/home/trx50/Documents/arthurwang_DB/", "")
print(f"\n✓ Note:      {short}")
print(f"✓ Sections:  {len(sections)}")
print(f"✓ Insights:  {len(insights)}")
print(f"✓ Chapters:  {'yes (' + str(len(info.get('chapters',[]))) + ')' if info['has_chapters'] else 'no (LLM inferred)'}")
print(f"✓ Transcript: {'CC subtitles' if has_vtt else 'description only'}")
print(f"\nWork dir: {work_dir}")
PYEOF
