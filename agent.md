# Arthur Knowledge Assistant — Agent 入口

> 本檔案為轉發器。所有規範以 `CLAUDE.md` 為主，本檔案不重複任何規則。

---

## 接到任務時，依序執行：

1. **讀取 `CLAUDE.md`** — 取得全域規範與 instruction 索引
2. **判斷任務類型** — 對照 CLAUDE.md 的 Instruction 索引表
3. **讀取對應 instruction 檔案** — 路徑在 `instructions/` 資料夾下
4. **執行任務**

---

## Instruction 索引

完整索引見 `CLAUDE.md`，以該檔為準。
