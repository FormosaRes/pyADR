# pyADR — NTNU modified fork (v3.7.4)

40Ar/39Ar data reduction tool with GUI. Modified fork of [pyADR](https://github.com/AndrewLiu0725/pyADR) (original by **An-Jun (Andrew) Liu**), now maintained by **PANG Chi-Hsiu (NTNU)**.

This fork adds: bug fixes, performance optimization, Excel native chart export, four new step-heating diagram types (DFD/DFS/DFM + grouped 3D plane fit), auto-update notification.

Original README → `README_origin.md` ｜ Full changelog → `CHANGELOG.md`

---

## Requirements

- Windows 10 / 11
- **Anaconda3** (https://www.anaconda.com/download) — Python 3.10+ included
- Microsoft Excel (for native chart export)

第三方 Python 套件由 `install.py` 自動安裝，需求清單見 `requirements.txt`。

---

## Installation

### Step 1 — 裝 Anaconda（如果還沒裝）

https://www.anaconda.com/download → 下載 Anaconda3 → 安裝（一路 Next 即可）。

> 為什麼用 Anaconda：常用科學運算套件已預裝，版本管理乾淨。其他 Python distribution（Python.org 原版、Miniconda）也可以，要 Python 3.10+。

### Step 2 — 下載 pyADR

點本頁右上方綠色 **Code** 鈕 → **Download ZIP** → 解壓到 `C:\pyADR\`（**路徑不要含中文或空白**）。

或用 git（之後想 git pull 更新比較方便）：
```
git clone https://github.com/FormosaRes/pyADR.git
```

### Step 3 — 一鍵安裝

進到 `C:\pyADR\` → **雙擊 `setup.bat`**

`setup.bat` 會自動：
1. 偵測 Anaconda 安裝位置（`C:\Anaconda`、`%USERPROFILE%\anaconda3`、`C:\ProgramData\Anaconda3` 等常見路徑）
2. 跑 `install.py`：自動 `pip install` 套件、建 `Data/` 與 `Figures/` 子資料夾、驗證 `.work/` seed file、產生 `pyADR.bat` 並複製到桌面

如果跳「Python / Anaconda not found」對話框，表示 Anaconda 不在預設路徑（裝在不常見位置）。改用備用方式（見下面）。

### Step 4 — 啟動

雙擊桌面 **`pyADR.bat`**。GUI 主畫面跳出來表示成功。

---

### 備用方式（setup.bat 找不到 Python 時）

按 Windows 鍵 → 打 **Anaconda Prompt** → 開啟。在視窗內執行：

```
cd C:\pyADR
python install.py
```

效果跟 setup.bat 一樣。

---

## Update

更新到新版有兩種方式：

### 方式 A：Git pull（推薦給用 git clone 安裝的）

```
cd C:\pyADR
git pull
```

完成。`.py` 檔案會更新，數據（`Data/`、`Figures/`、`.work/setting.csv`）不會被動到。

### 方式 B：重新下載 ZIP

1. 備份 `Data/`、`Figures/`、`.work/setting.csv`
2. 刪除舊 `C:\pyADR\` 整個資料夾
3. 重新 Download ZIP → 解壓 → `python install.py`
4. 把備份倒回去

### 自動更新通知

打開 pyADR 啟動後 2 秒，如果 GitHub 上有新版會自動跳 Windows 通知（右下角 toast），點「Open GitHub」直接到 Releases 頁。

也可以手動檢查：**Menu → Check Update**。

---

## Run

```
python NTNU_DataReduction.py
```

或雙擊 `pyADR.bat`。Debug 模式：`pyADR_debug.bat`（會保留 console 視窗顯示錯誤）。

---

## File overview

| File / Folder | 說明 |
|---|---|
| `NTNU_DataReduction.py` | 主程式入口 (GUI) |
| `AutoPipeline.py` | 批次自動化 pipeline |
| `Utilities.py` | 共用函式 / 繪圖核心 |
| `PlaneFit3D.py` | 3D 平面擬合（含 grouped fitting） |
| `ExcelChartExporter.py` | Excel 原生圖表匯出 |
| `UI/` | PyQt5 對話框模組 |
| `.work/` | 啟動必要 seed file（logo、setting、app_info） |
| `pyADR_excel_template.xlsx` | Excel 輸出模板 |
| `install.py` | 一鍵安裝（pip + 建資料夾 + 桌面捷徑） |
| `setup.bat` | 雙擊版安裝（自動偵測 Anaconda） |
| `requirements.txt` | Python 套件清單 |
| `CHANGELOG.md` | 完整版本變更紀錄 (V2.5 → V3.7) |
| `README_origin.md` | 原版 pyADR 的 README (Andrew Liu) |

---

## Changelog 摘要

### v3.7.4 (2026-05-11)

**Critical bug fix** — `Utilities.calcAge` 函式從 V3.7 release (commit `afb2268`) 起就被 iCloud sync 截斷在 `Ar_39_Ca = Ar_37_Ca * constants[0]`，沒做 38Ar/40Ar/F/age 計算也沒 return，導致 GUI 點 Age Calculation 或 AutoPipeline 跑 step heating 都 `TypeError: 'NoneType' object is not subscriptable`。所有 v3.7.x release HEAD 都帶這個 bug。

修法：從 V3.4.1 archive 還原完整 100 行 `calcAge`（38Ar/40Ar(air/K/r)、F = 40Ar(r)/39Ar(K)、T = ln(1 + J·F)/λ、59-element return），同時還原 `Utilities.py` 檔尾 88 行（`_draw_iso_n` group fit MSWD、`_apply_panel_extras`、`getSummaryPlot` 主迴圈）也被同一 iCloud 截斷。

保留現狀待跟老師討論：線性誤差傳播（不改 quadrature）、Ca/K 常數 0.52、F_std 一階近似、36Ar(Cl) 大氣校正未加。`Utilities.py` 從壞掉的 3707 行 → 完整 3794 行。

### v3.7.3 (2026-05-11)

Datum Publication Table 改回 88 欄格式（從 v3.7 的 98 欄 revert）。砍掉末端 10 欄 isochron section（normal/inverse isochron 與對應 std）— 那是 v3.7 為了補救壞掉的 isochron 計算才塞進去的，現在 ISOr export 已經獨立成 toDPR（8 欄），Publish Table 不需要再混 isochron。也跟老師那邊 V2.0 88 欄格式重新相容。內部 V2.0 → V3.7 normalization (`normalize_csv_to_v37`) 維持原樣。

### v3.7.2 (2026-05-10)

修復 ISOr (Datum Publication) export。`toDPR` 函式在重構過程中被整段刪掉，ISOr 按鈕的 signal 也被誤改成綁 `self.toDP`，所以點 ISOr 跑出來是 98 欄完整 datum table 而不是 8 欄 isochron-ratio 表。從 V2.0 移植 `toDPR` 邏輯回來（+ V3.7 慣用 try/except/finally + utf-8 encoding）+ 修正 signal binding 到 `self.toDPR`。輸出格式：`39/40, err[39/40], 36/40, err[36/40], 39/36, err[39/36], 39, Samp#`，與 V2.0 完全相容。

### v3.7.1 (2026-05-09)

新增 `Utilities.normalize_csv_to_v37()` helper：自動偵測 V2.0 (88 欄, K/Ca) vs V3.7 (98 欄, Ca/K) 並在記憶體內轉換。讀入老師舊 V2.0 datum publication CSV 時，自動把 col 23-24 從 K/Ca 倒數成 Ca/K，並從 raw Ar component 計算出 isochron 10 欄，下游 plotting 完全不變。toDP 仍輸出 V3.7 完整 98 欄。

### v3.7 (2026-05-09)

新增 **DFD（Degassing Pattern Diagram）**：X = Temperature (°C)，Y = Ar amount (V, log scale)，21 個 Ar components 可自由組合（5 sums + 16 individual），含 Components 選擇對話框。

Plot Controls UI 大改：scrollable、Apply 改藍色 primary、X/Y label 跟著 pname 動態顯示物理意義、新增 isochron control row（`⁴⁰Ar/³⁶Ar atm`、Temperature label）、新增 group-fit toggles（Show groups / Group fits / Overall fit）。

`getDFStatistics_sh` 與 `getSummaryPlot` 加入 `show_group_fits` / `show_overall_fit` 參數；DFM Summary 的 inverse isochron 重寫，與 standalone DFI 視覺對齊（error ellipses、per-point group color、per-group regression + colored info box）。

新增啟動時自動更新檢查（背景執行，發現新版用 Windows 通知）。

### v3.6 (2026-05-08)

新增 **DFS（2-panel Stack diagram）**：top = Ca/K 或 Cl/K，bottom = Age，每 panel 獨立 axis range；右側 Plot Controls 加入 Stack panel selector。

新增 **DFM（Multi-panel Summary diagram）**：可選 panels（age / atm / cak / clk / isn / iso），每 panel 各有獨立 limits。

Hover info 擴充：DFW / DFA / DFC step hover 加顯示 `%⁴⁰Ar*` 與 `Ca/K`。

`PlaneFit3D.plot_result_grouped()` 新增（4-panel grouped fit 圖），`DF_S3D` 改 grouped fitting（每 group n≥3 才 fit，不夠的 fallback 到全資料 single fit）。

Bug fix：`Utilities.py` CSV NaN row removal off-by-one（舊版 CSV 沒 trailing blank line 時會誤刪最後一筆 real data row）。

### v3.5 (2026-05-07)

合併 V3.3 (穩定基底) + V3.5 BUG FIX + V3.4.1 性能優化（`_iter_combos` iterative 改寫、`pd.read_csv(usecols=...)` I/O ~84% 減少、Step Heating 一次選資料夾批次匯出、誤差傳播改 quadrature、ExcelChartExporter `error_bar` typo 修正）。詳見 `CHANGELOG.md`。

### 更早

詳見 `CHANGELOG.md`（V2.5 → V3.4.1）。重點：V3.0.1 修 Ca/K 計算公式接反 + missing decay correction on σ；V3.1 加 PlaneFit3D；V3.1.1 加 Cl/K ratio；V3.2 加 DFS stacked spectrum；V3.3 加大量 UI 互動性（on-isochron click、step grouping、QSpinBox 自訂格式）。

---

## Troubleshooting

| 症狀 | 原因 / 解法 |
|---|---|
| 雙擊 `setup.bat` 視窗閃過 | Python 不在 PATH。改用 Anaconda Prompt 跑 `python install.py` |
| `pip install --upgrade` 把 numpy 升到 2.x，pandas/sklearn 報 `_ARRAY_API not found` | `pip install "numpy<2"` 降回 1.x |
| `winotify>=1.4 not found` | 已在 v3.7 後修為 `>=1.0`。舊版手動 `pip install "winotify>=1.0"` |
| pyADR 啟動 logo 不見但程式正常 | `.work/logo.png` 缺檔，從 GitHub repo 重新下載該檔 |
| 升級到 V3.7 開啟舊 V3.5/V3.6 產的 88 欄 CSV 卡 header 驗證 | V3.7 用 98 欄新格式（多 isochron ratios + Degassing Patterns section）。建議重新跑 Datum Publication |
| iCloud / OneDrive 同步路徑跑 git 出現 `*.icloud` 或 `* 2.py` 衝突檔 | 把 repo 移到非同步資料夾（如 `C:\Users\<user>\Documents\GitHub\`） |

---

## For developers — release new version

要發 v3.8 / v3.9... 的流程：

1. 改 `.py` 程式碼
2. **改 `.work/.app_info.txt` 第 2 行**版本號（例如 `3.7` → `3.8`）— 自動更新通知靠這個
3. 在 `CHANGELOG.md` 最上面加新版段落
4. 在 `README.md` 改頁首版本號 + Changelog 摘要
5. GitHub Desktop commit + push 到 `main`
6. 開 Release：https://github.com/FormosaRes/pyADR/releases/new → Tag `v3.8.0` → Publish

V3.7 使用者打開 pyADR 自動跳通知；用 git clone 的人 `git pull` 即可。

---

## Credits

- Original author: **An-Jun (Andrew) Liu** — https://github.com/AndrewLiu0725/pyADR
- NTNU fork maintainer: **PANG Chi-Hsiu** — andy830205@gmail.com

## License

[依需求填入，例如 MIT，或保留 Andrew Liu 原版授權]
