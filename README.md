# pyADR — NTNU modified fork (v3.7)

This is a modified fork of [pyADR](https://github.com/AndrewLiu0725/pyADR), originally created by **An-Jun (Andrew) Liu** to automate Prof. Mary Yeh's 40Ar/39Ar data reduction at NTNU.

This fork (maintained by **PANG Chi-Hsiu, NTNU**) adds bug fixes, performance improvements, Excel native chart export, and several new step-heating diagram types. Original README preserved as `README_origin.md`. Full per-version detail in `CHANGELOG.md`.

---

## Requirements

- **Anaconda3** (https://www.anaconda.com/download) — 強烈建議用 Anaconda 安裝 Python
- Python 3.10+ （Anaconda 內建符合）
- Windows (tested on Win10/11)
- Microsoft Excel (for native chart export)

Python packages: see `requirements.txt` (自動安裝)。

---

## Installation（Windows + Anaconda 流程）

### Step 1 — 裝 Anaconda

如果還沒裝：https://www.anaconda.com/download → 下載 Anaconda3 → 安裝（一路 Next 即可）。

### Step 2 — 下載 pyADR

兩種方式選一個：

**方式 A：Download ZIP（最簡單）**
1. 點本頁綠色 **Code** 鈕 → **Download ZIP**
2. 解壓到 `C:\pyADR\`（**路徑不要含中文或空白**）

**方式 B：Git clone**（之後想 pull 更新比較方便）
- 開 Anaconda Prompt → `cd C:\` → `git clone https://github.com/FormosaRes/pyADR.git`

### Step 3 — 跑 install.py

1. 按 Windows 鍵 → 打 **Anaconda Prompt** → 開啟（注意：是 Anaconda Prompt，**不是** cmd 或 PowerShell）
2. 在 Anaconda Prompt 視窗輸入：

```
cd C:\pyADR
python install.py
```

3. 按 Enter，跟著提示按 Enter 確認。完成後桌面會出現 `pyADR.bat`。

---

## 為什麼一定要 Anaconda Prompt

Anaconda 安裝時**預設不會把 Python 加進系統 PATH**，所以普通 cmd / PowerShell 找不到 `python` 指令；雙擊 `setup.bat` 會直接報錯。

Anaconda Prompt 是 Anaconda 自己包裝的 cmd，**已經先 activate Anaconda 環境**，可以直接用 `python`、`pip`、`conda` 等指令。所有 Python/Anaconda 操作都建議在 Anaconda Prompt 進行。

---

## Run

桌面 / 工作資料夾雙擊 **`pyADR.bat`** 即可啟動 GUI。

或在 Anaconda Prompt 內：

```
cd C:\pyADR
python NTNU_DataReduction.py
```

Debug 模式：雙擊 `pyADR_debug.bat`（會保留 console 視窗顯示錯誤訊息）。

---

## File overview

| File | 說明 |
|------|------|
| `NTNU_DataReduction.py` | 主程式入口（GUI） |
| `AutoPipeline.py` | 批次自動化 pipeline |
| `Utilities.py` | 共用函式 / 繪圖核心 |
| `PlaneFit3D.py` | 3D 平面擬合（含 grouped fitting） |
| `ExcelChartExporter.py` | Excel 原生圖表匯出 |
| `UI/` | PyQt5 對話框模組 |
| `pyADR_excel_template.xlsx` | Excel 輸出模板 |
| `install.py` | 套件安裝 / 環境檢查 |
| `CHANGELOG.md` | 完整版本變更紀錄（V2.5 → V3.7） |
| `README_v3.5.md` | V3.5 合併版說明（歷史文件） |
| `README_origin.md` | 原版 pyADR 的 README（Andrew Liu） |

---

## Changelog 摘要

完整內容見 `CHANGELOG.md`。

### v3.7 (2026-05-09)

新增 **DFD（Degassing Pattern Diagram）**：X = Temperature (°C)，Y = Ar amount (V, log scale)，21 個 Ar components 可自由組合（5 sums + 16 individual），含 Components 選擇對話框。

Plot Controls UI 大改：scrollable、Apply 改藍色 primary、X/Y label 跟著 pname 動態顯示物理意義、新增 isochron control row（`⁴⁰Ar/³⁶Ar atm`、Temperature label）、新增 group-fit toggles（`Show groups` / `Group fits` / `Overall fit`）。

`getDFStatistics_sh` 與 `getSummaryPlot` 加入 `show_group_fits` / `show_overall_fit` 參數；DFM Summary 的 inverse isochron 重寫，與 standalone DFI 視覺對齊（error ellipses、per-point group color、per-group regression + colored info box）。

### v3.6 (2026-05-08)

新增 **DFS（2-panel Stack diagram）**：top = Ca/K 或 Cl/K，bottom = Age，每 panel 獨立 axis range；右側 Plot Controls 加入 Stack panel selector。

新增 **DFM（Multi-panel Summary diagram）**：可選 panels（age / atm / cak / clk / isn / iso），每 panel 各有獨立 limits。

Hover info 擴充：DFW / DFA / DFC step hover 加顯示 `%⁴⁰Ar*` 與 `Ca/K`。

`PlaneFit3D.plot_result_grouped()` 新增（4-panel grouped fit 圖），`DF_S3D` 改 grouped fitting（每 group n≥3 才 fit，不夠的 fallback 到全資料 single fit）。

Bug fix（`Utilities.py`）：CSV NaN row removal off-by-one — 舊 code `while i != (len(data)-2)` 在 CSV 沒 trailing blank line 時會誤刪最後一筆 real data row，改用 `data.pop()` 剝 trailing blank + 從 i=1 起 loop。

### v3.5 (2026-05-07)

合併 V3.3 (穩定基底) + V3.5 BUG FIX + V3.4.1 性能優化。詳見 `README_v3.5.md`。

- `_iter_combos` 改 iterative，~50–70% 加速
- 3D plane fit 用 `pd.read_csv(usecols=...)`，I/O ~84% 減少
- Step Heating 圖檔一次選資料夾批次匯出
- `_show_diagram` 統一 5 個重複 method
- 誤差傳播改 quadrature（`sqrt(a² + b²)`）
- ExcelChartExporter `error_bar` typo 修正
- OGD 日期解析支援 `-` 與 `/`

### 更早

詳見 `CHANGELOG.md`（V2.5 → V3.4.1）。重點：V3.0.1 修 Ca/K 計算公式接反 + missing decay correction on σ；V3.1 加 PlaneFit3D；V3.1.1 加 Cl/K ratio；V3.2 加 DFS stacked spectrum；V3.3 加大量 UI 互動性（on-isochron click、step grouping、QSpinBox 自訂格式）。

---

## Notes for users

- 實驗數據（`Data/`、`Figures/`、`1200S 數據/`）不會被追蹤，已在 `.gitignore`。
- 升級到 V3.7 後，CSV header 從 88 欄擴成 98 欄（新增 isochron ratios 與 Degassing Patterns section）。**舊版 V3.5 / V3.6 產的 88 欄 CSV 在 V3.7 開啟可能會卡 header 驗證**，建議重新跑或手動補欄。
- iCloud 路徑跑 git 容易出現 `*.icloud`、`* 2.py` 衝突檔，建議放在非同步資料夾（如 `C:\Users\<user>\Documents\GitHub\`）。

---

## Credits

- Original author: **An-Jun (Andrew) Liu** — https://github.com/AndrewLiu0725/pyADR
- Modifications: **PANG Chi-Hsiu** (andy830205@gmail.com), NTNU

## License

[依需求填入，例如 MIT，或保留 Andrew Liu 原版授權]
