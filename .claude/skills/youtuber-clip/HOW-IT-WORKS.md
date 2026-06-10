# How It Works — youtuber-clip

記錄 clip 從 YouTube URL 到 Shorts-ready supercut 的完整生成流程。

---

## 整體流程圖

```
YouTube URL
    │
    ▼
[01] yt-dlp 下載
    ├── video.mp4（1080p 完整影片）
    ├── subs.en.vtt（英文字幕）
    └── meta.json（標題、頻道、時長）
    │
    ▼
[02] VTT 解析
    └── srt_entries.json（每 6 秒一段，含 start/end/original）
    │
    ▼
[03] OpenAI gpt-4o-mini 翻譯
    └── srt_entries.json（加入 translated 欄位）
    │
    ▼
[04] Claude 分析逐字稿
    └── moments.json（10 個爆點，含精確時間碼 + 字卡文字）
    │
    ├──────────────────────┐
    ▼                      ▼
[04a] 裁片              [04b] 人臉追蹤
clips/*.mp4              face/*.mp4
（橫版 16:9，無字幕）    （垂直 9:16，人臉置中）
    │                      │
    └──────────────────────┘
                │
                ▼
           [05] Supercut
    supercut/supercut.mp4
    （30 秒，1080×1920，含字卡特效）
```

---

## 各步驟詳解

### Step 1 — 下載（`01_download.sh`）

用 `yt-dlp` 從 YouTube 下載：

- **影片**：優先 `bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]`，合併為 mp4
- **字幕**：優先手動 CC（`--write-subs`），fallback 自動生成（`--write-auto-subs`），語言順序 `en → en-US`
- **Metadata**：`--dump-json` 取得標題、頻道、時長、章節資訊

---

### Step 2 — VTT 解析（`02_parse_vtt.py`）

YouTube auto-caption VTT 有特殊結構：每句話會出現兩次（重疊式 rolling caption），需要去重。

```
原始 VTT（每句出現 2 次）
    │
    ▼
去重：取 clean[1::2]（每兩條取一條）
    │
    ▼
合併：每 6 秒累積為一段（CHUNK_DURATION = 6.0）
    │
    ▼
輸出：[{ start, end, original }, ...]
```

保留實際說話開始時間（不強制從 0 開始），避免靜音段顯示空字幕。

---

### Step 3 — 翻譯（`03_translate.py`）

用 OpenAI `gpt-4o-mini` 批次翻譯，每批 80 條：

- Prompt 格式：`序號|英文` → 輸出 `序號|繁體中文`
- 保留技術術語：LLM、GPU、token、AI、ARR 等
- 自動補翻：解析後若有缺漏的 idx，單獨補翻
- API Key 來源：`/home/trx50/gitlab/gigabyte_kg/.env` → `OPENAI_API_KEY`

---

### Step 4 — 爆點分析（Claude 在對話中執行）

這是唯一需要人工判斷的步驟。Claude 讀取 `srt_entries.json`，依以下標準選出 10 個爆點：

**選取標準**（依優先順序）：
1. 反直覺數字（具體數字 + 讓人意外的結論）
2. 強烈對比（「X 只要 Y，但 Z 卻要 W」）
3. 新框架 / 現場定義新術語
4. 情感高點（語氣激昂、強烈比喻）
5. 主題多元（10 個片段涵蓋不同面向）

**輸出 `moments.json` 欄位說明**：

| 欄位 | 說明 | 範例 |
|------|------|------|
| `abs_start` | 片段在原始影片的開始秒 | `0` |
| `abs_end` | 片段在原始影片的結束秒（含前後文，60–120s） | `90` |
| `slug` | 英文短標題，`NN-kebab-case` | `01-anthropic-arr-saas-10yr` |
| `moment_start` | 金句在片段內的開始秒（相對 abs_start） | `23.7` |
| `moment_dur` | 金句持續秒數（2.5–4 秒） | `3.5` |
| `label_line1` | 字卡第一行（≤ 10 字） | `Anthropic 1 個月` |
| `label_line2` | 字卡第二行（≤ 10 字，可空） | `= SaaS 三家 10 年` |

格式參考：`data/moments.sample.json`（Gavin Baker 訪談的實際範例）

---

### Step 4a — 裁片（`04a_cut_clips.py`）

從原始影片按 `moments.json` 的 `abs_start` / `abs_end` 裁出橫版片段：

```bash
ffmpeg -ss <abs_start> -i video.mp4 -t <dur> \
  -c:v libx264 -crf 18 -preset fast \
  -c:a aac clips/<slug>.mp4
```

**為什麼不直接用原始影片做 supercut？**
分段裁出後，人臉追蹤只需處理短片段，速度快 10 倍以上（每段 60–120 秒 vs 整部影片）。

---

### Step 4b — 人臉追蹤（`04b_face_track.py`）

這是整個流程最核心的視覺處理步驟，把橫版 16:9 轉成垂直 9:16 且人臉置中。

#### 裁切框計算

```
來源：1920×1080（16:9）
目標：1080×1920（9:16）
裁切框寬度：1080 × 9/16 = 607px（等比，全高 1080px）
```

#### 人臉偵測

使用 `insightface` 的 `buffalo_sc` 模型（輕量 RetinaFace）：
- 每 15 幀偵測一次（≈ 2fps），節省處理時間
- 多張臉時取**面積最大**的（通常是主說話者）
- 取臉的水平中心點 `cx = (x1 + x2) / 2`

#### 平滑化（防止畫面跳動）

```
偵測點 → 線性插值（填滿每幀）→ EMA 平滑（α=0.08）
```

EMA（指數移動平均）讓裁切框緩慢跟隨臉部移動，避免畫面因頭部晃動而抖動。α 越小越平滑，0.08 約等於「過去 12 幀的加權平均」。

#### 動態裁切（ffmpeg sendcmd）

```
生成 crop_cmd.txt：
0.0000 crop x 640;
0.5000 crop x 644;
1.0000 crop x 648;
...（只在 x 變化 ≥ 2px 時才寫一行）

ffmpeg -i clip.mp4 \
  -vf "sendcmd=f=crop_cmd.txt,crop=607:1080:<init_x>:0,scale=1080:1920" \
  face/<slug>.mp4
```

`sendcmd` 讓 ffmpeg 在渲染過程中動態修改 crop filter 的 x 參數，實現每幀不同裁切位置。

---

### Step 5 — Supercut 合成（`05_supercut.py`）

對每個金句片段依序套用三層特效，然後 concat 成一支影片。

#### 特效一：Zoom Punch-in（zoompan）

```
前 9 幀（0.3 秒）：z = 1.05 → 1.0
第 10 幀後：z = 1.0（正常）
```

每次切換到新片段時有一個瞬間放大→回正的「衝擊感」，模擬剪輯師常用的 push-in 手法。

#### 特效二：色彩增強（eq filter）

```
saturation=1.3   ← 色彩飽和度 +30%
contrast=1.06    ← 對比度 +6%
```

讓影片在手機小螢幕上更鮮明，符合 Shorts 的視覺風格。

#### 特效三：置中大字卡（drawtext）

```
字體：Noto Sans CJK TC Black（/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc）
大小：76px
顏色：#FFE033（黃色）
描邊：5px 黑色
陰影：3px offset，黑色 90% 透明度
位置：垂直置中（第一行在 h/2 - 85，第二行在 h/2 + 15）
顯示時間：整段金句全程（enable=between(t,0,dur)）
```

黃色 + 黑描邊是 Shorts / TikTok 字卡的業界標準配色，在任何背景上都清晰可讀。

#### 最終合成

```bash
# 用 concat demuxer 串接所有片段
ffmpeg -f concat -safe 0 -i concat.txt \
  -c:v libx264 -crf 18 -preset fast \
  -movflags +faststart \
  supercut/supercut.mp4
```

`-movflags +faststart` 讓 MP4 的 moov atom 移到檔案開頭，上傳後可以邊下載邊播放。

---

## 輸出目錄結構

```
data/<VIDEO_ID>/
├── video.mp4              # 原始影片（1080p，通常 400-800MB）
├── subs.en.vtt            # 英文字幕
├── srt_entries.json       # 解析後字幕（含翻譯）
├── meta.json              # yt-dlp metadata
├── moments.json           # Claude 分析出的 10 個爆點
├── clips/
│   ├── 01-slug.mp4        # 橫版原始片段（16:9，60-120s）
│   └── ...
├── face/
│   ├── 01-slug.mp4        # 9:16 人臉追蹤版（無字幕）
│   ├── 01-slug_crop.txt   # ffmpeg sendcmd 動態裁切座標
│   └── ...
└── supercut/
    ├── segs/
    │   ├── seg_00.mp4     # 各金句片段（帶字卡特效）
    │   └── ...
    └── supercut.mp4       # 最終輸出（~30s，1080×1920）
```

---

## 常見問題

**Q：為什麼要分 clips → face 兩個步驟，不直接從原始影片做臉部追蹤？**

A：人臉追蹤需要逐幀讀取影片，1 小時影片約 108,000 幀。先裁成 60-120 秒片段後，每段只有 1800-3600 幀，速度快約 30 倍，且可以分段重跑失敗的片段。

**Q：為什麼 `moment_start` 是相對於片段開頭，而不是原始影片的絕對秒數？**

A：`05_supercut.py` 直接用 `ffmpeg -ss <moment_start> -i face/<slug>.mp4`，相對時間更直覺。如果用絕對秒數，還要計算 `abs_start` 的偏移。

**Q：EMA 平滑的 α=0.08 是怎麼決定的？**

A：α=0.08 對應的「有效記憶幀數」約為 1/α = 12.5 幀，在 30fps 下約 0.4 秒。實測這個值在訪談影片（說話者頭部小幅晃動）下既不會跟不上大幅移動，也不會在靜止時抖動。

**Q：為什麼字卡用黃色 `#FFE033` 而不是白色？**

A：訪談影片背景常有大面積淺色（白牆、窗戶），白色字幕容易消失。黃色在任何背景下都高對比，是 TikTok / Shorts 最常見的字卡配色。
