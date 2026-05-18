# X 自動化工具與 Repo 整理

> 來源：知識創作/X 筆記彙整｜更新：2026-05-17

---

## GitHub Repos

### 1. xiaomu_x_creator
- **Repo**：[github.com/JayceHuang/xiaomu_x_creator](https://github.com/JayceHuang/xiaomu_x_creator)
- **作者**：@JayceHuang（小木）
- **功能**：Claude Code Skill，把素材庫 `.md` 批量提煉成推文，設定定時發送
- **用法**：把素材放進對應資料夾 → Skill 提煉核心內容 → 複製 → 定時發送
- **來源筆記**：20 天萬粉的 X 帳號 AI 運營攻略

---

### 2. x-article-in-obsidian
- **Repo**：[github.com/Icy-Cat/x-article-in-obsidian](https://github.com/Icy-Cat/x-article-in-obsidian)
- **作者**：@lngkximo
- **功能**：Obsidian 插件，在 Obsidian 內直接發布長文到 X 草稿箱，不需開瀏覽器
- **用法**：配置好後，在 Obsidian 寫完文章 → 一鍵推送到 X 草稿
- **來源筆記**：20 天萬粉的 X 帳號 AI 運營攻略

---

### 3. cc-switch
- **Repo**：[github.com/farion1231/cc-switch](https://github.com/farion1231/cc-switch)
- **作者**：farion1231
- **功能**：Claude API 帳號切換工具，多帳號絲滑切換，支援多 API Key 配置
- **用法**：填寫帳號資訊後快速切換，避免單一 API 額度耗盡影響工作流
- **來源筆記**：draft 工作流

---

## 平台工具（非 Repo）

### 4. CREAO — X 自動監控 Agent
- **平台**：[creao.ai](https://creao.ai)（非開源）
- **功能**：
  - 自帶 X API Connector，無需申請開發者帳號
  - 一句話指令自動拆解任務，抓取 X 指定帳號推文
  - 從 40 條推文篩出 8 條信息差精選，自動生成 Notion 日報
  - 支援 Schedule（Cron `0 8 * * *` 每天早 8 點自動執行）
  - Tool Maker：Agent 可現場造工具（如用 Twitterbot UA 抓 og:image 預覽圖）
- **整合**：Gmail、Slack、Notion、Discord、YouTube、X、GitHub、Google Sheets 等 20+ 工具
- **費用**：免費 30 credits/月；Pro Plus $12.50/月（原價 $25）
- **Twitterbot UA trick**：用 Twitterbot User-Agent 抓推文 og:image，不需申請 X 圖片 API 權限
- **來源筆記**：CREAO 打造 X 自動監控 Agent、X增長完整系統

---

### 5. X Viral Monitor（Chrome 插件）
- **連結**：[Chrome Web Store](https://chromewebstore.google.com/detail/x-viral-monitor/dkplofpecmjmbhgjgleeflcnfgfkdfpd)
- **功能**：在 X 時間線上顯示各推文的 viral 程度（火箭圖標），幫助判斷要回覆哪些帖子借勢
- **使用場景**：0–4000 粉階段，靠蹭大 V 熱帖回覆獲取流量
- **來源筆記**：20 天萬粉的 X 帳號 AI 運營攻略

---

### 6. getname.zip — 標題生成工具
- **連結**：[getname.zip](https://getname.zip/)
- **作者**：@snail_9106
- **功能**：生成有情緒、有鉤子的 X 標題（X 無敏感詞限制，標題需更具攻擊性）
- **來源筆記**：20 天萬粉的 X 帳號 AI 運營攻略

---

## 技術 Trick 備忘

| Trick | 說明 |
|---|---|
| Twitterbot UA 抓 og:image | 用 Twitterbot User-Agent 發 HTTP 請求，可拉取推文卡片預覽圖，無需 X 圖片 API 權限 |
| X Premium CSV 分析 | X Premium → 分析 → 內容 → 下載 CSV，丟給 Skill 生成作戰計畫 + JSON 護照 |
| 定時發推 | 配合 xiaomu_x_creator Skill 或排程工具，設定批量定時發送 |

---

## 相關筆記

- [CREAO 打造 X 自動監控 Agent](obsidian://open?vault=arthurwang_DB&file=AI%20Knowledge%2F知識創作%2FX%2F2026-04-23%20CREAO%20打造%20X%20自動監控%20Agent：從入門到信息差永久資產)
- [20 天萬粉的 X 帳號 AI 運營攻略](obsidian://open?vault=arthurwang_DB&file=AI%20Knowledge%2F知識創作%2FX%2F20%20天萬粉的%20X%20帳號%20AI%20運營攻略：定位、素材庫、發推節奏、自動化)
- [X增長完整系統](obsidian://open?vault=arthurwang_DB&file=AI%20Knowledge%2F知識創作%2FX%2F2026-04-25%20X增長完整系統：增粉閉環、病毒發布、AI自動化工作流)
- [draft 工作流](obsidian://open?vault=arthurwang_DB&file=AI%20Knowledge%2F知識創作%2FX%2F%20draft%20工作流)
