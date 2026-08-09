#!/usr/bin/env python3
"""把 AI digest 當天輸出整理成一份可直接讀完的 Telegram 摘要報。

不同於舊版 ai-digest-top5.py（只取標題 + 第一行 + 連結），本版：
  • 跨所有分類 .md（🤖 Agent / 📡 產業動態 / 🐙 Open-source …）彙整文章
  • 依分數排序、用 URL 去重，取 Top N
  • 每篇萃取 2~3 句中文摘要（跳過圖片行與來源 meta 行）
讓使用者不必點進文章就讀得懂當天重點。

用法:
    ai-digest-report.py <summaries_dir 或 must_read.md> <YYYY-MM-DD> [top_n=8]

輸出:
    把報告切成數個 ≤3800 字的 chunk，各寫入一個暫存檔，
    並把檔案路徑逐行印到 stdout（供 ai-digest.sh 逐則發 Telegram）。
"""
import glob
import os
import re
import sys
import tempfile

MAX_CHARS = 3800            # Telegram 單則上限 4096，留餘裕
SENTENCES_PER_ITEM = 3      # 每篇取幾句中文摘要
MEDALS = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣',
          '9️⃣', '🔟', '11.', '12.']

# 一個文章 block：## [標題](url) ⭐️ 9.0/10 + 後面內容（到下一個 ## / 分隔線為止）
ARTICLE_RE = re.compile(
    r'##\s*\[(?P<title>.+?)\]\((?P<url>[^)]+)\)\s*⭐️\s*(?P<score>[\d.]+)/10'
    r'(?P<body>.*?)(?=\n##\s|\n---\n|\Z)',
    re.DOTALL)


def clean_summary(body, n):
    """從 block body 取前 n 句中文摘要：丟掉圖片行、來源 meta 行、bold 註解、details。"""
    lines = []
    for ln in body.split('\n'):
        s = ln.strip()
        if not s:
            continue
        if s.startswith('!') or s.startswith('<') or s.startswith('```'):
            continue
        if s.startswith('**'):          # **背景** / **標籤** 等
            break
        if s.startswith('<details'):
            break
        if ' · ' in s:                   # 來源 meta：rss · Google Research · Jun 26
            continue
        if s.startswith('rss') or s.startswith('hackernews') or s.startswith('reddit'):
            continue
        lines.append(s)
    text = re.sub(r'\s+', ' ', ' '.join(lines)).strip()
    parts = [p.strip() for p in re.split(r'(?<=[。！？])', text) if p.strip()]
    out = ''.join(parts[:n])
    if len(out) > 260:
        out = out[:260] + '…'
    return out


def norm_url(u):
    return u.strip().rstrip('/').split('?')[0].split('#')[0]


def main():
    target = sys.argv[1]
    date = sys.argv[2]
    top_n = int(sys.argv[3]) if len(sys.argv) > 3 else 8

    if os.path.isdir(target):
        md_files = sorted(glob.glob(os.path.join(target, '*.md')))
        must_read = os.path.join(target, '🔥 今日必追.md')
    else:
        md_files = [target]
        must_read = target

    # 今日看點 + 總篇數（只在 必追 檔裡）
    look, total = '', ''
    if os.path.isfile(must_read):
        head_txt = open(must_read, encoding='utf-8').read()
        m = re.search(r'今日精選共\s*\*\*\s*(\d+)', head_txt)
        if m:
            total = m.group(1)
        lm = re.search(r'##\s*📝\s*今日看點\s*\n+(.+?)(?=\n\n---|\n##\s|\Z)',
                       head_txt, re.DOTALL)
        if lm:
            look = re.sub(r'\s+', ' ', lm.group(1)).strip()

    # 跨檔彙整文章，URL 去重保留最高分
    best = {}
    for f in md_files:
        try:
            txt = open(f, encoding='utf-8').read()
        except OSError:
            continue
        for mt in ARTICLE_RE.finditer(txt):
            url = norm_url(mt.group('url'))
            score = float(mt.group('score'))
            if url not in best or score > best[url]['score']:
                best[url] = {
                    'title': mt.group('title').strip(),
                    'url': mt.group('url').strip(),
                    'score': score,
                    'summary': clean_summary(mt.group('body'), SENTENCES_PER_ITEM),
                }

    # 有摘要的優先、再依分數排序
    items = sorted(best.values(),
                   key=lambda x: (x['score'], len(x['summary'])),
                   reverse=True)
    items = [it for it in items if it['summary']][:top_n]

    if not items:
        return  # 萃取失敗 → bash 走 fallback

    # ── 組 block ──
    blocks = []
    head = f"📰 AI Digest — {date}"
    if total:
        head += f"\n今日精選 {total} 篇 · 取重點 {len(items)} 篇"
    if look:
        head += f"\n\n📝 今日看點\n{look}"
    blocks.append(head)

    for i, it in enumerate(items):
        medal = MEDALS[i] if i < len(MEDALS) else f"{i+1}."
        blocks.append(
            f"{medal} {it['title']} ⭐️{it['score']:g}\n{it['summary']}\n🔗 {it['url']}")

    blocks.append(f"📂 AI Knowledge/Digest/{date}/")

    # ── 貪婪打包成 ≤MAX_CHARS 的 chunk ──
    SEP = "\n\n━━━━━━━━━━━━\n"
    chunks, cur = [], blocks[0]
    for b in blocks[1:]:
        if len(cur) + len(SEP) + len(b) <= MAX_CHARS:
            cur += SEP + b
        else:
            chunks.append(cur)
            cur = b
    chunks.append(cur)

    n = len(chunks)
    for idx, ch in enumerate(chunks):
        text = ch if n == 1 else f"{ch}\n\n（{idx + 1}/{n}）"
        tf = tempfile.NamedTemporaryFile(
            mode='w', encoding='utf-8', delete=False,
            prefix='aidigest_chunk_', suffix='.txt')
        tf.write(text)
        tf.close()
        print(tf.name)


if __name__ == '__main__':
    main()
