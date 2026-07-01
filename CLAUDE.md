# CLAUDE.md — pyADR 開發指引

此檔案給 Claude Code（以及任何接手此 repo 的 AI agent）使用。讀完再動程式碼。

---

## 1. 專案背景

pyADR 是 ⁴⁰Ar/³⁹Ar geochronology data reduction 工具，fork 自 NTNU CalcT0/DataReduction 老版本，逐步補上 ArArCALC v2.5.2 規格 + 現代 isochron 數學（York 2004, Vermeesch 2018/2024, Schaen 2021）。

- 主要 entry point：`NTNU_DataReduction.py`（GUI，~244k 行）+ `AutoPipeline.py`（批次/自動化）
- 數學核心：`Utilities.py`（~163k 行）
- 目前版本：v3.8.54（2026-05-29），版本字串在 `.work/.app_info.txt`；最新 GitHub Release 也是 v3.8.54
- 開發者：Chi-Hsiu Pang（龐麒修，Academia Sinica PhD candidate）
- 完整版本歷史看 `CHANGELOG.md`，數學式推導看 `FORMULAS.md`

---

## 2. 三資料夾分工（鐵則）

| 用途 | 路徑 | 操作 |
|---|---|---|
| **DEV**（改 .py） | `C:\Users\龐麒修\Documents\GitHub\pyADR\` | git repo，所有 Edit/Write 都在這 |
| **RUN**（執行） | `C:\pyADR-main\` | 跑 program；不要手 Edit，但每次改完要從 DEV cp 過來 |
| **DATA**（樣品數據） | iCloud `pyADR開發\` 各 transect 資料夾 | 只放 .dat / .csv，不放 .py |

**版本歸檔用 git tag**，不要開 `pyADR-v3.8.2/`、`pyADR-backup/` 這種目錄。

**「不改檔」的意思**：禁止把 Edit/Write 直接打在 `C:\pyADR-main\`（會跟 git repo 失步、用 iCloud sync 還會被截斷）。Edit 完一律從 DEV `cp` 過去 RUN。詳細流程看 §7。

---

## 3. 絕對不要動的東西

### 3.1 NTNU_DataReduction.py 內的 CalcT0Page σ_T0

該頁 σ_T0 用 `std(|residuals|)/√n`，**教授（Jian-Cheng Lee）指定保留**，未經他同意不改。

AutoPipeline.py 的 σ_T0 已經改成 SE-from-covariance（pcov[-1,-1]，v3.8.2），並透過 `SIGMA_METHOD` toggle 提供兩條路徑 — 但這只影響 AutoPipeline，**不要把這個改動 port 回 NTNU_DataReduction**。

### 3.2 在 iCloud 路徑下 Edit 大型 .py 檔

iCloud 同步會把寫入截斷，且 tool 會回報成功（無錯誤訊息）。曾經發生：`UI/DiagramPlots_SH.py` row 14 setText 被截斷，整列標籤空白。

**規則**：所有 .py 編輯必須在 `Documents\GitHub\pyADR\`（本地 SSD），絕不在 iCloud。

### 3.3 教授沒同意的大幅重寫

指出問題 → 等同意 → 才動手。不要為了「順便清理」改 unrelated 段落。

---

## 4. 任務完成通知

長任務跑完要通知 Pang，**不要直接呼叫 Telegram API**。寫進 queue 即可：

```
C:\Users\龐麒修\iCloudDrive\claude cowork\telegram-notify\notify-queue.jsonl
```

格式參考該資料夾的 README。daemon 會自動送出。

---

## 5. 近期關鍵修正（v3.8.x，2026-05）

理解這些 fix 的脈絡再動相關函式：

### v3.8.0（DiagramPlot 數學式 critical fixes）
影響**所有歷史 Int age + WMA**。修在 `Utilities.py`：
- `getDFStatistics_sh` / `getDFStatistics_ls`：inverse isochron `F = -slope/intercept`（York convention，Vermeesch 2024）
- WMA：`Σ(T/σ²)/Σ(1/σ²)`（原本 1/σ² 互消 → 退化成 Σ T_i）
- MSWD 參考點從 arithmetic mean 改成 WMA

### v3.8.1（DiagramPlot UI + σ_36/σ_39 雙重計算）
- σ²_36m = σ²_36a − σ²_36ca − σ²_36cl − σ²_36c（避免 corrections σ 被雙重計算）
- σ²_39m = σ²_39k − σ²_39ca
- 永遠從 raw component 重算 σ，**不讀 CSV 內 pre-calc σ**（v3.7 寫進去的是 buggy 值）

### v3.8.2（AutoPipeline σ_T0 SE-from-covariance）
- AutoPipeline 的 baseline fit σ_T0 改用 `pcov[-1,-1]`（Li et al. 2019 Eq.1）
- 舊公式 `std(|r|)/√n` 系統性低估約 4×
- **注意**：NTNU_DataReduction.CalcT0Page 仍維持舊公式（見 §3.1）

### v3.8.3（σ_J 括號 bug fix）
- `Utilities.py` L2864 `getJVolumeStatistics`：`((np.exp(l*t) - 1) / Ar_39_K_40_r_ratio**2)`
- 影響：σ_age 過去整條 pipeline 系統性高估數個數量級
- age 中心值不變，只有 σ_age 變小

### v3.8.3 cont.（AutoPipeline 大擴充）
- `LAMBDA_37` / `LAMBDA_39` decay constants + `decay_correct()` helper
- `SIGMA_METHOD` global toggle（'standard' = pcov vs 'calc_t0' = std(|r|)/√n）
- `_signal_out_pass` 改 serial per-isotope（Ar37 → Ar36 → Ar38/39/40，按物理依賴順序）
- York 2004 isochron + Wendt-Carl 1991 √MSWD 修正

### v3.8.4 → v3.8.54（逐版細節見 `CHANGELOG.md`，這裡只列要動 code 前該知道的）
這段大多是 `AutoPipeline.py` 的擴充與 UI，數學核心多半沒動。要點：
- **v3.8.9（critical，影響科學輸出）**：blank T₀ 寫檔曾用錯 mask，已修。動 blank fit / `_calc_blank_t0` / SaveT0 路徑前先看這版。
- **效能**：`_fit_one` 有 closed-form OLS fast path（linear/average），與 curve_fit bit-identical（v3.8.27）；step 切換靠 `_prefetch_cache` + `PrefetchWorker`（v3.8.26）。動 fit 邏輯要同步維護快取 key `(id(vt), fit, nc)`。
- **AgeCalcPage**：底部 Excel 風格 tab（Summary/Datum/Age Spectrum/Inverse/Normal/Ca/K/Cl/K/Degassing），diagram tab = 左圖 + 右側資訊面板；軸/legend 走 `_refresh_diagrams` 的 per-target dispatch（v3.8.36/43/48/49/50）。
- **CalcT0Page**：Signal T₀ Range 盒鬚圖（挑 blank cycle 用），含 blank box + 各 step 選定 T₀ ± σ 點（v3.8.44–46/52/53）。matplotlib 字型是 Arial，缺下標 `₀`：圖上文字一律用 mathtext `$T_0$`，別用 unicode `₀`/`≪`（v3.8.30/54）。
- **Session**：`.adr` 存檔/開檔（zip+json+npz），只還原 Calculate T₀ 狀態（v3.8.28）。
- 輸出格式（T0/MassRatio/Datum/AgeCalc CSV、PNG 路徑 Data↔Figures）對齊 NTNU 子程式（v3.8.24/25/32）。

---

## 6. 已知未解 issue（不要忘記）

### 6.1 `Utilities.LAMBDA_K` 還沒定義
AutoPipeline isochron age 計算用 `hasattr(Utilities, 'LAMBDA_K')` fallback 到 `5.543e-10`（Steiger-Jäger 1977）。**應該**改成 `5.531e-10`（Renne 2010）並在 `Utilities.py` 正式定義。

### 6.2 Inverse isochron F 的 fallback
`AutoPipeline.py` 內 `F_i = -b_i/m_i if abs(b_i) > 1e-30 else (1/(-m_i) ...)` — fallback 走的是 v3.7 buggy 公式。正常不會觸發，但建議改成回傳 0 或 raise。

### 6.3 馬遠溪 phengite excess Ar
research-side 議題，不是 code bug。若 AutoPipeline 跑馬遠溪數據出現 plateau 異常或 inverse isochron trapped 40/36 偏離大氣值，這是 excess Ar 物理問題，不是 reduction 錯誤。

---

## 7. 開發 SOP

1. **改之前**：先 `git log --oneline -20` 看最近改了什麼、`cat CHANGELOG.md | head -100` 看當前版本脈絡
2. **改 .py**：一律在 `Documents\GitHub\pyADR\`，不在 iCloud、不在 `C:\pyADR-main\`
3. **改完寫文件**：
   - bump `.work/.app_info.txt` 版本號
   - 在 `CHANGELOG.md` 開新區塊（格式參考 v3.8.3 / v3.8.10）：問題 → 影響 → 修法 → 驗證 checklist → 檔案改動
   - **`README.md` 也要跟著更新**（很常忘）：頁首標題版本號 `# pyADR — NTNU modified fork (vX.Y.Z)`、有新功能就改「This fork adds」、「Changelog 摘要」段。CHANGELOG 改了 README 沒改就會版本對不上。
4. **同步到 RUN**：複製所有改動的檔案到 `C:\pyADR-main\` 對應路徑。Pang 是在 RUN 跑 program，DEV 改完不同步等於沒改。
   ```bash
   # 範例（複製 AutoPipeline.py + 版本檔 + changelog）：
   cp "C:/Users/龐麒修/Documents/GitHub/pyADR/AutoPipeline.py"      "C:/pyADR-main/AutoPipeline.py"
   cp "C:/Users/龐麒修/Documents/GitHub/pyADR/.work/.app_info.txt"   "C:/pyADR-main/.work/.app_info.txt"
   cp "C:/Users/龐麒修/Documents/GitHub/pyADR/CHANGELOG.md"          "C:/pyADR-main/CHANGELOG.md"
   ```
   每動到任何檔案都要 sync，子目錄（`UI/`, `Utilities.py`, etc.）一樣。
5. **commit + push**：
   - commit 訊息格式：`vX.Y.Z: <one-line summary>` + 詳細 body（重點、影響、檔案）
   - 預設直接 `git push origin main`，不用問，除非是 force-push
   - 這是 single-developer repo，Pang 不需要 PR review
6. **驗證**：盡量用 NO.65 muscovite（irradiation 0621-01C）或 SYL31 LS（Sylhet Trap 玄武岩，論文值 115.4 ± 3.9 Ma）對照。`memory/pyADR_validation_target_no65.md` 有目標值 9.77 ± 0.28 Ma。
7. **完成通知**：寫 telegram-notify queue（見 §4）
8. **發 GitHub Release 時**（不是每個 commit，累積一段落或使用者要發才做 — 改科學輸出的版本要等 NO.65 驗過再發，見 §6 / memory）：
   - 建 Release：`gh release create vX.Y.Z --target main --title "..." --notes-file <file>`（或 heredoc）。notes 涵蓋**上一個 Release 之後**的所有版本。發完 GitHub 「Releases」才會更新（Windows 自動更新通知 + toast 都靠這頁）。
   - **同時更新 repo 的「About」描述**：`gh repo edit FormosaRes/pyADR --description "..."`。⚠️ **描述不要寫死版本號**（以前寫死 "v3.8.27" 一直過時忘了改），只寫功能。
   - 這三個（Release、About、README）很常漏，發版前對一下：**版本號 = `.app_info.txt` = README 標題 = 最新 Release tag**。

---

## 8. 相關文件

- `CHANGELOG.md` — 完整版本歷史（V2.5 → 現在）
- `FORMULAS.md` — Ar isotope 數學式 reference
- `README.md` — 安裝 + 使用
- `pyADR_全module數學式審查_v5.docx`（iCloud 開發資料夾）— 公式審查報告，含 P1/P2 分類與文獻 quote

---

## 9. 溝通風格（給 AI agent）

Pang 偏好：
- 直接、簡短、不要鋪陳
- 預設 Python + 構造地質學 + Ar/Ar geochronology 專業知識，不解釋基礎
- 「不要糾結了」「直接告訴我」= 給結論
- 程式碼直接給，不逐行解釋
- 繁中為主，技術術語英文
- em-dash 結構（— ... —）拒用，改逗號 appositive
