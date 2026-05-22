#!/usr/bin/env python3
"""Step 3: gpt-4o-mini 批次翻譯 srt_entries.json → 加入 translated 欄位"""
import json, os, re, sys
from openai import OpenAI

work_dir = sys.argv[1]
entries  = json.load(open(f"{work_dir}/srt_entries.json"))

if not entries:
    print("無字幕條目，跳過翻譯")
    sys.exit(0)

api_key = os.environ.get("OPENAI_API_KEY") or ""
if not api_key:
    print("WARNING: 無 OPENAI_API_KEY，跳過翻譯")
    sys.exit(0)

client = OpenAI(api_key=api_key)
BATCH  = 80

def translate(batch):
    lines = "\n".join(f"{i}|{e['original']}" for i, e in enumerate(batch))
    resp  = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": (
            "你是專業字幕翻譯，以下是英文演講逐字稿，每行格式「序號|英文」。\n"
            "輸出「序號|繁體中文」，一一對應，保留 LLM/GPU/token/AI 等術語，只輸出翻譯。\n\n"
            + lines
        )}],
        temperature=0.2, max_tokens=4000,
    )
    return resp.choices[0].message.content.strip()

results = {}
total   = (len(entries) + BATCH - 1) // BATCH

for b_start in range(0, len(entries), BATCH):
    batch = entries[b_start:b_start+BATCH]
    bn    = b_start // BATCH + 1
    print(f"批次 {bn}/{total} ({b_start}–{b_start+len(batch)-1})...", flush=True)
    out    = translate(batch)
    parsed = 0
    for line in out.split("\n"):
        m = re.match(r'^(\d+)\|(.+)$', line.strip())
        if m:
            results[b_start + int(m.group(1))] = m.group(2).strip()
            parsed += 1
    print(f"  → {parsed}/{len(batch)}", flush=True)

# 補翻缺漏
missing = [(i, e) for i, e in enumerate(entries) if i not in results]
if missing:
    print(f"補翻 {len(missing)} 條...")
    for chunk_start in range(0, len(missing), 60):
        chunk = missing[chunk_start:chunk_start+60]
        lines = "\n".join(f"{i}|{e['original']}" for i, e in chunk)
        out   = translate_batch_raw(client, lines)
        for line in out.split("\n"):
            m = re.match(r'^(\d+)\|(.+)$', line.strip())
            if m: results[int(m.group(1))] = m.group(2).strip()

for i, e in enumerate(entries):
    e["translated"] = results.get(i, "")

json.dump(entries, open(f"{work_dir}/srt_entries.json", "w"), ensure_ascii=False, indent=2)
ok = sum(1 for e in entries if e.get("translated"))
print(f"翻譯完成：{ok}/{len(entries)}")
