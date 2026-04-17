# arthur_knowledge_assistant

這個 repo 目前主要用來整理我在本地使用的 AI / Obsidian / Claude Code / Codex 資源，包含外部 skill repo、Obsidian 相關工具，以及個人工作流程文件。

## Repo 內容

- `axton-obsidian-visual-skills/`
  - Obsidian 視覺化技能包，可產生 Canvas、Excalidraw、Mermaid 圖。
- `tutor-skills/`
  - StudyVault / quiz workflow，用來把文件或程式碼整理成可在 Obsidian 複習的結構化筆記。
- `gstack/`
  - 另一套 agent / workflow 工具集。
- `CLAUDE.md`
  - 本專案使用 Claude Code 時的工作規範。
- `AI_TECH_NOTE_CLAUDE.md`
  - AI 技術筆記整理規範。
- `PAPER_NOTE_CLAUDE.md`
  - 論文筆記整理規範。

## Skills / 參考資源

### 1. Obsidian Visual Skills

Repo:
`https://github.com/axtonliu/axton-obsidian-visual-skills`

Claude Code plugin 安裝：

```text
/plugin marketplace add axtonliu/axton-obsidian-visual-skills
/plugin install obsidian-visual-skills
```

手動安裝：

```bash
git clone https://github.com/axtonliu/axton-obsidian-visual-skills.git
```

### 2. Tutor Skills

Repo:
`https://github.com/RoundTable02/tutor-skills`

安裝：

```bash
npx skills add RoundTable02/tutor-skills
```

### 3. Scholar Skill

Repo:
`https://github.com/EESJGong/scholar-skill`

## 使用方式

如果這個 repo 被當成個人工作區使用，通常流程是：

1. 把需要的 skill repo clone 到專案內。
2. 依工具需求安裝到 Claude Code / Codex 對應的 skills 目錄。
3. 用 `CLAUDE.md`、`PAPER_NOTE_CLAUDE.md`、`AI_TECH_NOTE_CLAUDE.md` 作為整理筆記時的標準。

## 備註

- 目前這不是一個單一可執行產品 repo，比較像工作區與資源集合。
- 如果後續要把它整理成正式專案，建議再補上：
  - 專案目標
  - 安裝需求
  - 標準目錄結構
  - 常用指令
