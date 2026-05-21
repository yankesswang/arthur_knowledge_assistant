# Future Work：transcript-note 延伸方向

## 短影片自動生成

transcript-note 目前的輸出（`analysis.json`）已包含足夠的結構化資料，可以直接延伸成短影片生成流程。

### 現有輸出可用的資料

```
analysis.json
├── tldr.核心主張     → 開場旁白 / 標題
├── key_insights      → 逐條旁白腳本（7-8 條）
├── data_table        → 數字字卡素材
└── sections[].start_time → 對應原影片 timestamp
```

---

### 路線一：文字 → 解說短影片（推薦優先實作）

**核心工具**：[MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo)

```
analysis.json → key_insights（3-5 條）
                    ↓
          MoneyPrinterTurbo API
          video_script = key_insights 串接
          video_source = pexels（股票素材）
          voice = ElevenLabs / Azure Edge TTS
          subtitle_enabled = true
                    ↓
          60-90 秒解說短影片（9:16）
```

**實作重點**：寫 `scripts/generate_short.py`，把 `analysis.json` 轉成 MoneyPrinterTurbo 的 `VideoParams`，跳過 LLM 腳本生成步驟（直接用 `video_script` 參數）。

**優點**：不需要下載原始影片，今天就能跑  
**缺點**：素材是通用 stock footage，視覺與原影片無直接關係

---

### 路線二：原始影片 → 精彩片段裁剪

**核心工具**：[OpenShorts](https://github.com/mutonby/openshorts)

```
YouTube URL
    ↓
yt-dlp 下載影片本體（setup.sh 加 --format 參數即可）
    ↓
Faster-Whisper ASR（INT8 量化，CPU 可跑）
    ↓
Gemini 病毒片段識別（15–60 秒，3–15 個片段）
    ↓
OpenShorts 雙模式 CV 裁剪
├── TRACK 模式：SmoothedCameraman（人臉追蹤 + 防抖）
└── GENERAL 模式：模糊背景佈局
    ↓
9:16 垂直短影片
```

**實作重點**：setup.sh 目前只下字幕（`--write-subs`），加一步下影片本體；其餘直接套用 OpenShorts pipeline。

**優點**：輸出與原影片直接相關，品質最高  
**缺點**：影片本體較大（1 小時 ≈ 1–2 GB），CV 處理需時

---

### 路線三：字卡短影片（最輕量，無外部依賴）

純本地，無需任何第三方服務：

```
data_table  → 逐條數字字卡（PIL 繪製）
key_insights → 逐條文字動畫
                ↓
            ffmpeg 串接 + BGM
                ↓
        30–60 秒資訊型短影片
```

**實作重點**：`generate_short.py` 用 PIL 生成每張字卡圖片，ffmpeg 控制每張顯示秒數 + 疊加 BGM，無需 GPU 或外部 API。

**優點**：完全本地、零成本、可直接整合進現有 finalize.sh  
**缺點**：純文字視覺，無語音

---

## 參考研究

詳細技術分析（各 repo 演算法、ffmpeg pipeline、CV 追蹤邏輯）：

`arthurwang_DB/AI Knowledge/創業/AI 影片製作/影片自動生成.md`

| 能力 | 最佳 Repo |
|------|-----------|
| 端到端文字→影片 | MoneyPrinterTurbo |
| 病毒片段識別 | OpenShorts（Gemini + Whisper） |
| 人臉追蹤裁剪 | OpenShorts（SmoothedCameraman） |
| 精彩度評分 | AutoClip（LLM 批量評分） |
| 多 TTS 引擎 | RedditVideoMakerBot（ElevenLabs 最自然） |

---

## 建議實作順序

1. **路線一先跑通**：寫 `generate_short.py`，MoneyPrinterTurbo 本地起服務，驗證 `key_insights → 短影片` 的完整 pipeline
2. **路線三作為 fallback**：不依賴外部服務，適合離線或快速產出
3. **路線二長期規劃**：需要額外儲存空間和 GPU，等有需求再接入
