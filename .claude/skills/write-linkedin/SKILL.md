---
name: write-linkedin
description: 根據筆記或主題，依照 Arthur 的聲音與人設，產出 LinkedIn 英文 + 繁體中文貼文各一，並存到帶日期資料夾。觸發關鍵字：寫貼文、LinkedIn、draft、short post、社群。
metadata:
  version: 1.0.0
---

# LinkedIn 貼文寫作 Skill

## Workflow

1. **讀取來源**：讀取使用者指定的筆記或主題內容
2. **讀取規範**：讀取 `/home/trx50/Project/arthur_knowledge_assistant/instructions/write-linkedin.md`
3. **撰寫貼文**：依照規範產出英文版 + 繁體中文版
4. **建立資料夾**：格式為 `YYYY-MM-DD 貼文主題`（日期取今天）
5. **存檔**：英文存 `post_en.md`，中文存 `post_zh.md`，兩者放在同一資料夾下
6. **回報路徑**：告知使用者存檔位置

## 存檔規則

- **根目錄**：`/home/trx50/Documents/arthurwang_DB/Arthur_Blog/Posts/`
- **資料夾命名**：`YYYY-MM-DD_slug`（日期 = 今天，slug = 主題的小寫英文 kebab-case）
- **檔案**：`post_en.md`（英文）、`post_zh.md`（繁體中文）

範例路徑：
```
Posts/
└── 2026-05-06_ahe-coding-agent-harness/
    ├── post_en.md
    └── post_zh.md
```

## 貼文規範摘要

完整規範見 `instructions/write-linkedin.md`，核心要點：

### 聲音
- 角色：AI 實踐者 / 架構師，讀論文然後提煉可執行洞見
- 語調：專業有活力，有立場，反直覺
- 必須有個人 "I" / "我" 時刻、驚訝感、不完美的對話感

### 結構（五段骨架）
1. **Hook**：反直覺主張或令人意外的數字，必須含關鍵字（工具名/論文名）
2. **Context**：2–4 行，設立背景與賭注
3. **Numbered Breakdown**：3–6 點，每點粗體標題 + 具體數字/例子
4. **Takeaway**：可執行洞見，1–2 句
5. **CTA + Hashtags**

### 長度
- 英文：200–400 字
- 中文：150–300 字

### Anti-patterns（立刻排除）
- ❌ 每句話結構完全對稱整齊
- ❌ 純陳述句，沒有個人反應
- ❌ 「Here's the thing:」「Let's dive in.」等 AI 填充語
- ❌ 全文沒有 "I" 或 "我"
- ❌ 簡體中文
