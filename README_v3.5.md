# pyADR V3.5 — 合併版 (V3.3 base + V3.4/V3.4.1/V3.5 updates)

**Release Date**: 2026-05-07
**Base**: V3.3 (穩定架構)
**目的**: 把 V3.4、V3.4.1、V3.5 三個分支中的「更新內容」全部合併到 V3.3 架構上，產生一個正確且功能完整的 V3.5。

---

## 為什麼要重做這版

舊的 V3.4 / V3.4.1 / V3.5 三個分支各自有問題：

- **V3.4** 砍掉了 V3.3 中 38 KB 的內容（NTNU 從 3832 行 → 3139 行；Utilities 從 3052 行 → 2242 行），這些精簡是錯誤的，丟失了 V3.3 的功能。
- **V3.4.1** 沿用 V3.4 的精簡分支，雖然加了四項性能優化和 ExcelChartExporter 接線，但仍缺 V3.3 的 38 KB 內容。
- **V3.5（舊）** 雖以 V3.3 為基底加了一堆 BUG FIX，但有兩個明顯 bug：
  - `AutoPipeline.py` 結尾被截斷（少了 `_on_done` 結尾與 `load_files` method 的 10 行）
  - `NTNU_DataReduction.py` 結尾有大量 padding 空白
  - 同時也沒有繼承 V3.4 / V3.4.1 的 ExcelChartExporter 接線與性能優化。

新版 V3.5 = **V3.3 (穩定架構) + V3.5 BUG FIX (修好截斷/padding 兩個 bug) + V3.4.1 ExcelChartExporter 接線 + V3.4.1 CSV usecols 優化**。

---

## 從各版本繼承的內容

### 從 V3.3 繼承（全套穩定基底）
- `AutoPipeline.py`、`NTNU_DataReduction.py`、`Utilities.py`、`PlaneFit3D.py`、`UIConverter.py`、`install.py` 的完整架構
- V3.4 / V3.4.1 砍掉的 38 KB 內容全部保留

### 從 V3.4 繼承
- `ExcelChartExporter.py` 整個新檔（V3.3 沒有）

### 從 V3.4.1 繼承
- `AutoPipeline.py` 的 `_iter_combos` 改成 iterative（避免深度遞迴，~50–70% 加速）
- `NTNU_DataReduction.py`：
  - `import ExcelChartExporter`
  - 新增 `DFSH_export_excel` method（觸發 Excel 原生圖表匯出）
  - `toDF_SH` 中 3D plane fit 的 `pd.read_csv(usecols=[14 columns])`（I/O ~84% 減少）
  - 3D plane fit 的 early skip（masked points < 3 時跳過）
- `ExcelChartExporter.py` 的 `from openpyxl.chart.error_bar import ErrorBars`（已修 typo，原 V3.4 寫成 `error_bars` 複數會 ModuleNotFoundError）

### 從 V3.5（舊）繼承的 BUG FIX
NTNU_DataReduction.py：
- A3：Step Heating 圖檔一次選資料夾、自動命名所有輸出（取代 5 次 QFileDialog）
- A4：統一 `_show_diagram` method 取代 5 個重複 method（DF_SN/DF_SI/DF_SW/DF_SA/DF_SC）
- A8：加 logging 模組
- B1：誤差傳播改 quadrature（`sqrt(a² + b²)` 取代 `|a| + |b|`）
- B2：`actual_xlim` / `actual_ylim` 初始化避免 NameError
- B3：CSV 寫入用 `csv.writer` + `newline=''`
- B6：替換 bare `except:` 為 `except Exception as e:`
- B8：移除多餘的 `f.close()`（已用 `with` statement）
- B9：用常數 `_CLICK_TOL` 取代 magic number `0.03`

AutoPipeline.py：
- B1：誤差傳播改 quadrature（同 NTNU 中的 B1）
- B4：OGD 日期解析支援 `-` 與 `/` 分隔符 + try/except 容錯
- B7：強制 `set_context()` 載入 parameters，移除 hardcoded 預設值

---

## 不採用的東西（明確排除）

- **V3.4 / V3.4.1 砍掉的 38 KB**：那是錯誤的精簡，全部不套用
- **V3.5（舊）AutoPipeline 結尾截斷**：用 V3.3 完整結尾接回
- **V3.5（舊）NTNU 結尾 padding 垃圾**：去掉，正常結束於 `App().run()`
- **V3.4.1 NaN row removal 改寫**：與 V3.5 BUG FIX `mask = np.ones(len(self.data)-1)` 衝突（V3.5 修了 mask 大小，V3.4.1 仍是舊的 `-2`），保留 V3.5 寫法
- **V3.4.1 Table fill pre-split lambda 寫法**：V3.5 寫法可讀性更好且收益有限（只對 `self.data[1]` 一行做 split），保留 V3.5 寫法

---

## 檔案清單與大小

| File | Size | Lines | 來源 |
|------|------|-------|------|
| `AutoPipeline.py` | 193,227 B | 4,273 | V3.3 + V3.5 BUG FIX (B1/B4/B7) + V3.4.1 _iter_combos iterative |
| `NTNU_DataReduction.py` | 191,456 B | 3,894 | V3.3 + V3.5 BUG FIX (A3/A4/A8/B1-B9) + V3.4.1 ExcelChartExporter 接線 + CSV usecols |
| `Utilities.py` | 125,842 B | 3,052 | V3.3 (穩定，未修改) |
| `PlaneFit3D.py` | 20,334 B | 466 | V3.3 = V3.4 = V3.4.1 = V3.5（無差異） |
| `UIConverter.py` | 168 B | 5 | V3.3 (未修改) |
| `install.py` | 2,131 B | 71 | V3.3 (未修改) |
| `ExcelChartExporter.py` | 13,798 B | 408 | V3.4 新增 + 修好 `error_bar` typo |

---

## 驗證

所有 .py 檔案通過 `python -m py_compile` 語法檢查：

```
✓ AutoPipeline.py
✓ ExcelChartExporter.py
✓ NTNU_DataReduction.py
✓ PlaneFit3D.py
✓ UIConverter.py
✓ Utilities.py
✓ install.py
```

關鍵 marker 確認：
- `AutoPipeline.py`：`_iter_combos` 是 iterative 版（含 `while indices[0] < n - k + 1`）；結尾完整（有 `_on_done` + `load_files` method）
- `NTNU_DataReduction.py`：`import ExcelChartExporter` 在 L48；`def DFSH_export_excel` 已存在；`pd.read_csv(usecols=[...])` 已套；結尾正常於 `App().run()`
- `ExcelChartExporter.py`：`from openpyxl.chart.error_bar import ErrorBars`（單數，非複數）

---

## 備份位置

合併前的 V3.5 工作目錄完整備份：
```
C:\Users\龐麒修\iCloudDrive\claude cowork\pyADR開發\pyADR 開發\_backup_v3.5_pre-merge_2026-05-07\
```

如果新版有問題，可以從這裡還原。

---

## 已知遺留問題

- iCloud Drive 同步衝突：合併過程中工作目錄出現 `NTNU_DataReduction 2.py`、`AutoPipeline 2.py` 等衝突命名檔，這些是 iCloud 自動產生的衝突保留檔，不是合併輸出的一部分，可手動刪除。
- `ExcelChartExporter.py` 中 `_is_num` 內部函式定義在使用之後（lambda late binding 機制讓它可以跑，但順序倒置，未來重構要注意）。
