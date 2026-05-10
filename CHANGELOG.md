# pyADR — NTNU_DataReduction / Utilities 更新日誌

版本追蹤：V2.5 → V2.6 → V2.7 → V2.7.1 → V3.0 → V3.0.1 → V3.1 → V3.1.1 → V3.2 → V3.3 → V3.4 → V3.4.1 → V3.5 → V3.6 → V3.7 → V3.7.1 → V3.7.2 → V3.7.3 → V3.7.4
最後整理日期：2026-05-11
整理者：Claude (based on git-style diff across all versions)

---

## V3.7.4（2026-05-11）

### Critical Bug Fix — `calcAge` 函式從 V3.4.1 archive 完整還原

**症狀：** 在 GUI 點 Age Calculation 頁面的計算按鈕, 程式崩潰 (`TypeError: 'NoneType' object is not subscriptable`)。AutoPipeline 跑 step heating 也壞。

**Root cause：** `Utilities.py:calcAge` 函式從 V3.7 release (commit `afb2268`) 起就被 iCloud sync 截斷, 函式只走到 `Ar_39_Ca = Ar_37_Ca * constants[0]` 就斷尾, 沒做 38Ar/40Ar/F/age/std 計算, 沒 return。所有 v3.7.x release HEAD 都帶這個 bug。

**修法：** 從 V3.4.1 archive (`程式修改的Data_Reduction/V3.4.1/Utilities.py`) 還原完整 100 行 calcAge 函式, 包含:
- 38Ar(K)、38Ar(Air) 計算
- 40Ar(air) = 36Ar(Air) × C1, 40Ar(K) = 39Ar(K) × C5, 40Ar(r) = 40Ar(m) − 40Ar(air) − 40Ar(K)
- F = 40Ar(r) / 39Ar(K), F_std (1 階近似 partial derivative)
- T = ln(1 + J·F) / λ (constants[16])
- T_std, T_int 完整 error propagation
- 59-element return 含 Ar components, ratios, F, J, T, info, t, Min, PK
- caller `NTNU_DataReduction.py:2240` 用 `result[46]` 取 Age, `result[47]` 取 std, `result[55-58]` 取 metadata 全部對齊

**`Utilities.py` 同時還原檔尾 88 行 (line 3523 起的 `_draw_iso_n` group fit MSWD 計算 + `_apply_panel_extras` + `getSummaryPlot` 主迴圈), 同樣是被 iCloud 截斷的部分。**

**保留現狀的（待跟老師討論後再修）：**
- 線性誤差傳播 (`Ar_39_Ca_std = (...+...) * Ar_39_Ca`) — 不改 quadrature
- Ca/K 常數 0.52 — 不改 1.83
- F_std 一階近似 — 沒包含 (1−C4·D) 完整分母
- 36Ar(Cl) 大氣校正 — 沒加進去

**檔案影響：**
- `Utilities.py` 從 3707 行壞掉 → 3794 行完整
- `NTNU_DataReduction.py`、`AutoPipeline.py` 內容沒改, 但 caller 不再 crash

---

## V3.7.3（2026-05-11）

### Revert — Datum Publication Table 改回 88 欄格式

**動機：** v3.7.2 修好 ISOr export (toDPR, 8 欄獨立 isochron-ratio 表) 後, 原本 v3.7 為了補救壞掉的 isochron 計算而塞進 Publish Table 末端的 10 欄 isochron section 變得多餘, 而且跟老師那邊 V2.0 88 欄格式不相容, 容易在交流檔案時出錯。

**改動 (`NTNU_DataReduction.py` toDP)：**
- header 從 98 欄縮回 88 欄, 砍掉:
  ```
  "normal isochron","40Ar(m)/36Ar(m)","40Ar(m)/36Ar(m)_std","39Ar(m)/36Ar(m)","39Ar(m)/36Ar(m)_std",
  "inverse isochron","36Ar(m)/40Ar(m)","36Ar(m)/40Ar(m)_std","39Ar(m)/40Ar(m)","39Ar(m)/40Ar(m)_std"
  ```
- `row = ["0"] * 98` → `row = ["0"] * 88`

**影響：** 之後跑 ISOr 要走 Datum Publication Page 的 ISOr 按鈕 (toDPR), 不再從 Publish Table 末端撈 isochron ratio。內部 V2.0 → V3.7 normalization (Utilities.normalize_csv_to_v37) 維持原樣, 讀舊 88 欄 / 98 欄 CSV 都還能正常 plot。

---

## V3.7.2（2026-05-10）

### Bug Fix — 修復 ISOr (Datum Publication) export

**症狀：** 在 Datum Publication Page 點擊 ISOr 按鈕時, 跑出來的不是預期的 8 欄 isochron-ratio 表, 而是跟 Publish Table 一模一樣的 98 欄完整 datum 表。

**Root cause：** 重構過程中 `toDPR` 函式整段被刪掉, ISOr 按鈕的 signal connection 被誤改成綁 `self.toDP`：

```python
# 錯誤 (V3.7.1 之前的某次重構誤改)
self.DatumSelectPage.isor.clicked.connect(self.toDP)
```

**修法：**

1. 從 V2.0 移植 `toDPR` 邏輯回來, 加上 V3.7 慣用的 try/except/finally + utf-8 encoding。
2. 修正 signal binding：

```python
self.DatumSelectPage.isor.clicked.connect(self.toDPR)
```

**`toDPR` 行為（與 V2.0 完全相容）：**

- 讀取 `MassRatio/` 底下的 CSV
- 驗證 header (`Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,...`)
- 抽出 39/40, 36/40, 39/36 三組 ratio + std + 39Ar amount + Samp#
- 輸出 8 欄表頭：

```
39/40,err[39/40],36/40,err[36/40],39/36,err[39/36],39,Samp#
```

**檔案影響：**

- `NTNU_DataReduction.py`：+65 行（toDPR method）, 1 行 binding fix
- 其他模組無變動

---

## V3.7.1（2026-05-09）

### V2.0 CSV 自動轉換（雙格式支援）

**動機：** 老師電腦使用 V2.0 pyADR，產出的 datum publication CSV 是 88 欄、第 23–24 欄 `K/Ca, K/Ca_std`、無 isochron section。先前 V3.7 plotting 工具讀這種 CSV 會卡 header 驗證。

**做法：在記憶體內自動把 V2.0 88 欄格式轉成 V3.7 98 欄格式**，下游 plotting 完全不變動。

**`Utilities.py` — 新增 `normalize_csv_to_v37()` helper（~95 行）**

讀檔後呼叫此函式，自動：
1. 偵測 header 是 V2.0（88 欄, `K/Ca`）還是 V3.7（98 欄, `Ca/K`）
2. **V2.0 → V3.7 in-memory 轉換**：
   - col 23-24 倒數：`Ca/K = 1 / (K/Ca)`，std 用 `σ(Ca/K) = σ(K/Ca) / (K/Ca)²`
   - 補 10 欄 isochron section（從 raw Ar component cols 計算）：
     - 36Ar(m) = 36Ar(a) + 36Ar(c) + 36Ar(ca) + 36Ar(cl)
     - 39Ar(m) = 39Ar(k) + 39Ar(ca)
     - 40Ar(m) = 40Ar(r) + 40Ar(a) + 40Ar(c) + 40Ar(k)
     - normal isochron: 40/36, 39/36
     - inverse isochron: 36/40, 39/40
     - quadrature 誤差傳播
3. V3.7 → 不動

**5 個讀檔點全部呼叫 normalize：**
- `NTNU_DataReduction.py`：`toDF_LS()` (L3205)、`toDF_SH()` (L3281)
- `Utilities.py`：`getDFStatistics_ls()` (L312)、`getDFStatistics_sh()` (L540)、`getDFStatistics_t()` (L2007)
- 同時把原本嚴格的 `if data[0].rstrip() != "..."` header 字串檢查改成 loose 的「88 或 98 欄都接」

**結果：**
- V3.7 內部 plotting 完全不需修改，所有圖一律以 Ca/K 顯示
- 讀 V2.0 88 欄老 CSV：自動轉成 Ca/K + isochron 計算後丟進 plotting
- 讀 V3.7 98 欄新 CSV：直接 plotting（normalize 無動作）
- toDP 仍輸出完整 V3.7 98 欄格式（給以後的工具用），不影響老師工作流（老師繼續用他自己 V2.0 工具產 datum publication）

**注意：**
- V2.0 isochron 是計算出來的（從 raw Ar component），不是直接讀；如果 V2.0 CSV 內某些 Ar 分量是 0（例如 36Ar(c) 占位符），isochron 會略有偏差但合理
- 如果有未來的 V4.x 又改格式，這個 helper 要更新

---

## V3.7（2026-05-09）

### 新功能 — DFD（Degassing Pattern Diagram，新 diagram 類型）

**`Utilities.py` — 新增 `getDegasPlot()` (~330 lines)：**
- X = Temperature (°C)，Y = Ar amount (V)，預設 log scale
- 讀取 CSV 中 `Degassing Patterns` section 的 16 個 individual components（³⁶Ar(a/c/ca/cl), ³⁷Ar(ca), ³⁸Ar(a/c/k/ca/cl), ³⁹Ar(k/ca), ⁴⁰Ar(r/a/c/k)）
- 也計算 5 個 sum series（³⁶/³⁷/³⁸/³⁹/⁴⁰Ar(m)）：用 quadrature 誤差傳播加總
- helpers `_read_col()`（從 Degassing Patterns section 取最後一次出現的同名欄位以避開「main」欄位）、`_series()`, `_series_err()`, `_sum_with_err()`

**`NTNU_DataReduction.py` — DFD widget hooks：**
- 新增 `DF_SDeg()`：呼叫 `getDegasPlot`、渲染、帶入 step_data 給 hover system
- 新增 `_dfd_open_components_dialog()`：選擇 21 個 components 子集合（5 sums + 16 individual），含 5 sums / 16 individual / All 21 / None 四個快速 preset
- `_get_xy_current` 加入 DFD branch（X = `deg C`，Y = 39Ar(k) 最後一個欄位）
- DFD-專屬 hover：用 normalized log10 distance 找最近 (component, step) 點
- `SH_auto_axes` 加入 DFD branch（log scale 時 y 範圍延伸 ×0.5/×2）

### Plot Controls UI 大幅重新設計

- 改成 scrollable（`QScrollArea` 包住 inner widget）
- 新增 visual helpers `_mk_header()` (light-gray bold section labels) 與 `_mk_sep()` (HLine separator)
- Apply 按鈕改藍色 primary style（`#2980b9`）；Auto / Reset 改灰色 secondary style
- X / Y axis label 跟著當前 pname 動態顯示物理意義（DFW="Cumulative ³⁹Ar (%) → Age (Ma)"，DFI="³⁹Ar/⁴⁰Ar → ³⁶Ar/⁴⁰Ar"，DFD="Temperature (°C) → Ar amount (V)"，等）
- 新增 isochron control row：`showAtmCheckbox`、`atmRatio` (QDoubleSpinBox 200–400, default 298.56)、`showTempCheckbox`
- 新增 group-fit toggles：`showGroupsCheckbox`、`showGroupFitsCheckbox`、`showOverallFitCheckbox`（控制 isochron 是否顯示 per-group 回歸線、整體紅色 dashed 回歸線）
- 新增 DFD-專屬 row：`showAllCompCheckbox` ("Show all 16")、`showErrorBarsCheckbox`、`btnDFDComponents` ("Components..." 按鈕)

### Utilities — `getDFStatistics_sh` 與 `getSummaryPlot` 加入 fit toggle

- `getDFStatistics_sh(... show_group_fits=True, show_overall_fit=True)`：可獨立關掉整體紅 dashed 線或 per-group 線
- `getSummaryPlot(... step_groups=None, group_colors=None, show_group_fits=True, show_overall_fit=True)`：
  - DFM Summary 內的 inverse isochron panel 重寫，現在含 1σ error ellipses、per-point group color、紅色 dashed overall fit、per-group regression line + colored info box（N、MSWD、age、⁴⁰/³⁶ intercept），與 standalone DFI 視覺對齊
  - `_draw_step_bars` 接受 `step_groups` / `group_colors` 參數，bar fill 跟著 group color
- DFM `getSummaryPlot` 呼叫端：每 panel 從對應 standalone diagram 繼承 axis range（`_actual_xlims/_actual_ylims[pname]`），但 user 已經自訂的 `_dfm_panel_limits[k]` 不會被覆蓋
- Cl/K 圖 X label 從 "Percentage ³⁹Ar released" 改為 "Cumulative ³⁹Ar Released(%)"（與其他 spectrum 圖一致）

### 其他

- DiagramPlots_SH 加入 `btnDeg`（Degas 按鈕）→ `DF_SDeg`、`btnDFDComponents` → `_dfd_open_components_dialog`
- 新增 `_effective_step_groups()`：計算傳給 `getSummaryPlot` 的 step_groups（依目前 group selection 過濾）
- CSV header 從 88 欄擴充為 98 欄版本（加入 Degassing Patterns section + 額外 isochron ratios 欄位），舊 V3.5/V3.6 的 88-欄 CSV 會在 V3.7 卡 header 驗證

---

## V3.6（2026-05-08）

### 新功能 — DFS（Stacked Spectrum 2-panel）

**`NTNU_DataReduction.py`：**
- `_get_xy_current` 加入 DFS branch：top panel = Ca/K 或 Cl/K（依 `_dfs_top_type` 與 `stackPanelCombo` 切換），bottom panel = Age
- `SH_apply_axes`、`SH_auto_axes`、`SH_reset_axes` 都加入 DFS handling：每 panel 各有 `top_xlim / top_ylim / bot_xlim / bot_ylim` 獨立 config（存在 `self._dfs_config`）
- 新增 `_dfs_load_panel_into_spinboxes()`：切 panel 時把該 panel 的 saved limits 載入右側 spinboxes（用 `blockSignals` 防 recursive trigger）
- 新增 `_on_stack_panel_changed()` callback
- 右側 Plot Controls 加入 `stackPanelLabel + stackPanelCombo`（"Top (Ca/K or Cl/K)" / "Bottom (Age)"），只有 DFS 頁顯示
- `logYCheckbox` 對 DFS 也生效（控制 top panel log scale）

### 新功能 — DFM（Summary multi-panel）

- `_get_xy_current` 加入 DFM branch：依 `_dfm_active_key` 取對應 panel 的 X/Y（`age`/`atm`/`cak`/`clk` 用 cumulative 39Ar X，`isn`/`iso` 用 isochron 比值 X/Y）
- `SH_apply_axes` / `SH_auto_axes` / `SH_reset_axes` 各 panel 個別處理，存在 `self._dfm_panel_limits` dict
- Stack diagram dialog 中原本的 "Stack axis ranges" sub-panel（top/bottom Y range）整段移除，改由右側 Plot Controls 統一處理；popup dialog 縮小
- Mode group (Stack vs Summary radio) 改 fixed vertical size，避免切換時 dialog 高度跳動
- Summary 切 mode 時 `dlg.adjustSize()`

### Hover info 擴充

- DFW step_data tuple 從 8 欄擴成 11 欄，新增 `ar_r_pct`（%⁴⁰Ar*）、`cak_step`、`cak_step_std`
- DFA step_data tuple +1 欄：`ar_r_pct`
- DFC step_data tuple +2 欄：`ar_r_pct`、`cak_step`
- 三種 hover 文字都加入 `%⁴⁰Ar*: X.X%` 與（DFW/DFC）`Ca/K: X.XXXX`
- Tuple 用 `*_rest` 解構配 `len(_rest) >=` 檢查，向後相容舊資料

### Bug fix — NaN row removal off-by-one

**`Utilities.py` (Datum Publication CSV 讀取)：**
- 舊 code：`while i != (len(data)-2)` 假設 CSV 一定有 trailing blank row，遇到沒 trailing blank 的 CSV 會誤刪最後一筆 real data row
- Fix：先用 `while data and not data[-1].strip(): data.pop()` 剝掉所有 trailing blank，然後 `i=1; while i < len(data)`（從 i=1 跳過 header），刪 row 後不增 i（讓下一 row shift 進來）
- `original_rows = len(data) - 1`、`nstep = len(data) - 1`（原本是 `-2`）

### Isochron 增強 — Per-group MSWD + N display

- DFN/DFI per-group annotation 加入 `N=X`（point count）與 `MSWD=Y.YY`（weighted by `y_std`，自由度 N-2）
- iso_groups dict 改存 `(_gx, _gy, _gys)` 三 list（多了 std），原本只有 `(_gx, _gy)`

### PlaneFit3D — `plot_result_grouped()` 新增

`PlaneFit3D.py` (+240 lines)：
- 新增 `plot_result_grouped(results, title='', labels_per_group=None, group_colors=None, figsize=(16,12), save_path=None)`
- 4-panel figure，多個 group 共用一組 axes（用於 grouped 3D plane fit 視覺化）
- Default palette: `['#FF8C00', '#1E90FF', '#2ECC40', '#FF4136', '#B10DC9']`

### NTNU `DF_S3D` — Grouped fitting

- 用 `step_groups` 把 isochron 群組各自做 plane fit
- 過濾條件：每組 ≥ 3 點才 fit；不夠的 group 印 `[3D Plane Fit] skipped groups (n<3): [...]` 後 fallback 到全資料 single fit（呼叫原本 `plot_result`）
- 結果用 `plot_result_grouped` 一次畫多 group
- `orig_to_masked` mapping：把 `step_groups` 的 df-row indices 轉成 masked-array indices

### Stats table 寫多 row

- 原本 hardcoded 只寫 row 1，現在 `for ri, (_, r) in enumerate(pairs, start=1):` loop，每組 fit 結果都寫進對應 row

---

## V3.5（2026-05-07）

### 合併版 — V3.3 + V3.5 BUG FIX + V3.4.1 性能優化

詳見 `V3.5/README_v3.5.md`。

**繼承內容：**
- V3.3 完整穩定基底（保留 V3.4 / V3.4.1 砍掉的 38 KB 內容）
- V3.4.1 `_iter_combos` iterative 改寫、`pd.read_csv(usecols=...)`、3D plane fit early skip
- V3.4 新增的 `ExcelChartExporter.py`（修好 `error_bar` typo）

**Bug fix（NTNU_DataReduction）：**
- A3：Step Heating 圖檔一次選資料夾、自動命名所有輸出（取代 5 次 QFileDialog）
- A4：統一 `_show_diagram` method 取代 5 個重複 method（DF_SN/DF_SI/DF_SW/DF_SA/DF_SC）
- A8：加 logging 模組
- B1：誤差傳播改 quadrature（`sqrt(a² + b²)` 取代 `|a| + |b|`）
- B2：`actual_xlim` / `actual_ylim` 初始化避免 NameError
- B3：CSV 寫入用 `csv.writer` + `newline=''`
- B6：替換 bare `except:` 為 `except Exception as e:`
- B8：移除多餘的 `f.close()`（已用 `with` statement）
- B9：用常數 `_CLICK_TOL` 取代 magic number `0.03`

**Bug fix（AutoPipeline）：**
- B1：誤差傳播改 quadrature
- B4：OGD 日期解析支援 `-` 與 `/` 分隔符 + try/except 容錯
- B7：強制 `set_context()` 載入 parameters，移除 hardcoded 預設值

**修正 V3.5 舊版 bug：**
- AutoPipeline.py 結尾截斷（補回 `_on_done` 結尾與 `load_files` method）
- NTNU_DataReduction.py 結尾大量 padding 空白（移除）

---

## V3.4.1（2026-05-07）

### 性能優化 — Performance Release

詳見 `V3.4.1/README_v3.4.1.md`。**注意：基底是 V3.4（精簡版），缺 V3.3 的 38 KB 內容；建議用 V3.5 或之後版本。**

**`AutoPipeline.py`：**
- `_iter_combos` 從 recursive 改 iterative（index-based），時間複雜度 O(C(n,k)×k) → O(C(n,k))，**60–70% 加速**

**`NTNU_DataReduction.py`：**
- `toDF_SH` NaN row removal：`list.pop()` in loop → list comprehension + 一次重建，O(n²) → O(n)，**70–85% 加速**
- `toDF_SH` Table filling：multi-pass `split()` → 預先 split + lambda，O(loops × cols) → O(cols)，**30–50% 加速**
- `toDF_SH` CSV 載入：`pd.read_csv(usecols=[14 cols])`（原本讀 88 欄），I/O 減少 84%，**40–60% 加速**
- 3D plane fit early skip（masked points < 3 跳過）
- 整合 `ExcelChartExporter`：新增 `import` 與 `DFSH_export_excel` method

**整體：** end-to-end pipeline 35–50% 加速。

---

## V3.4（2026-05-07）

### 重構 — Pre-optimization Baseline（**不建議使用**）

`V3.4/README_v3.4.md` 自己標記為「unoptimized baseline」——存在的目的是讓 V3.4.1 有比較對象。

**問題：**
- 砍掉了 V3.3 中的 38 KB 內容（`NTNU_DataReduction.py` 3,832 行 → 3,139 行；`Utilities.py` 3,052 行 → 2,242 行）
- 這些精簡是錯誤的，丟失了 V3.3 的功能
- 不要直接用 V3.4，要用 V3.4.1（性能優化過）或 V3.5（合併穩定）

**新增：**
- `ExcelChartExporter.py`（408 行新檔）：Excel native chart export
- 內建有 `error_bar` typo（V3.4.1 / V3.5 修正為 `error_bar`，原誤寫 `error_bars`）
- 三個 debug 用 script：`debug_pyadr.py`, `debug_pyadr2.py`, `diagnose_crash.py`

---

## V3.3（2026-05-06）— 完整版（穩定基底）

### 大規模 UI 互動性擴充

V3.5 / V3.6 / V3.7 都以這個版本為基底，是穩定參考點。

**`NTNU_DataReduction.py`（3,832 行，較 V3.2 大幅增加）：**

新增（DFM panel 與 step grouping 互動系統）：
- `_dfm_load_active_to_controls()`、`_dfm_on_panel_changed()`：DFM panel 啟用切換
- `_clear_groups()`、`_redraw_with_groups()`、`_make_grp_handler()`、`_smart_set()`：step group 管理
- `_make_range_row()`：step 範圍輸入列 UI 元件
- `_ensure_click_callback()`、`_pixel_to_data()`、`on_click_SH()`：SH diagram 滑鼠點擊互動（直接點圖選 step）
- `textFromValue()`、`valueFromText()`、`validate()`：自訂 QSpinBox 文字格式化（負數、科學記號等驗證）
- `_h()`：水平佈局 helper

**`Utilities.py`：** 補回 V2.6 大重構時誤刪的部分函式，3,052 行（較 V3.2 增加 ~26 KB）。

---

## V3.2（2026-05-05）

### 新功能 — DFS（Stacked Spectrum）匯出

**`NTNU_DataReduction.py`：**
- 新增 `DF_SSTACK()`：將多個 sample 的 age spectrum 疊圖匯出
- 新增 `_generate()`：批次生成輔助
- 新增 `_get_plot_style()`：取得目前配色／線型設定

**`Utilities.py`：** 同步擴充以支援 stacked plot 計算。

---

## V3.1.1（2026-05-05）

### 新功能 — Cl/K Ratio 計算

**`NTNU_DataReduction.py`：**
- 新增 `DF_SCL()`：Cl/K spectrum 圖（步驟對 Cl/K 比值）
- Datum Publication / Step Heating 數據加入 Cl/K 欄位

**`Utilities.py`：** 新增 Cl/K 計算（基於 38Ar(cl) / 39Ar(k)），含 quadrature error propagation。

---

## V3.1（2026-05-05）— Add planeFit3D

### 新功能 — 3D Plane Fit 模組

**新增檔案：**
- `PlaneFit3D.py`（466 行）：三維平面擬合（least-squares），用於 isochron 三維分析

**`NTNU_DataReduction.py`：**
- 整合 `PlaneFit3D` 到 Step Heating workflow（masked points 子集擬合）
- 加入 3D plane fit 結果寫入 datum publication

---

## V3.0.1（2026-05-03）

### Bug Fix — Ca/K 計算公式錯誤（雙重錯誤）

**影響範圍：** Step-heating diagram Ca/K spectrum 數值完全錯誤

#### `Utilities.py` — `getJVolumeStatistics()`

| | 說明 |
|---|---|
| **Bug** | `(Ar_39_K * 0.52) / Ar_37_Ca` → 分子分母接反，計算的是 K/Ca，不是 Ca/K |
| **Fix** | `(Ar_37_Ca * 0.52) / Ar_39_K` |
| **std Bug** | `... * (... + 0.02/0.52)` → 多餘的 `0.02/0.52` 項無物理意義 |
| **std Fix** | `CaK * (σ₃₇/37Ar + σ₃₉/39Ar)` 正確 error propagation |

#### `NTNU_DataReduction.py` — Datum Publication row[23–24]

| | 說明 |
|---|---|
| **Bug A** | 用 `pr_ratio`（39Ar/37Ar_ca = 0.000377631）當 calibration factor，應用 0.52（差 1379×） |
| **Bug B** | 39Ar 在分子，37Ar 在分母（接反） |
| **Fix** | `(37Ar_ca × 0.52) / 39Ar_k` |
| **std Bug** | 固定 1% 不確定度（`KCa * 0.01`） |
| **std Fix** | `CaK × (σ₃₇/37Ar + σ₃₉/39Ar)` |

```
物理公式：Ca/K = (³⁷Ar_ca / ³⁹Ar_k) × R，R = 0.52（lab calibration）
驗證（NO.65 Muscovite 900°C）：修正前 0.982，修正後 2.0×10⁻⁴（muscovite Ca/K << 1 ✓）
```

#### `Utilities.py` — `calculateT0()` decay correction

| | 說明 |
|---|---|
| **Bug** | `measurement[1] *= decay_37` 有做，但 `measurement_std[1]` 沒跟著 scale |
| **Fix** | `measurement_std[1] *= decay_37`（37Ar sigma 同步 decay 校正） |
| **Bug** | `measurement[3] *= decay_39` 有做，但 `measurement_std[3]` 沒跟著 scale |
| **Fix** | `measurement_std[3] *= decay_39`（39Ar sigma 同步 decay 校正） |

#### `Utilities.py` — `ratio_std` 符號問題

| | 說明 |
|---|---|
| **Bug** | `ratio_std[i] = ratio[i] * sqrt(...)` → ratio 可為負值，導致 std 為負 |
| **Fix** | `ratio_std[i] = abs(ratio[i]) * sqrt(...)` |

#### `Utilities.py` — 日期解析

| | 說明 |
|---|---|
| **Bug** | `date.fromisoformat(SPD_raw)` → 遇到 `YYYY/MM/DD` 格式會 crash |
| **Fix** | 手動 split('/') 再 int() 轉換，相容多種日期格式 |

---

## V3.0（2026-??-??）

### 新功能 — AutoPipeline 自動流程模組

**新增檔案：**
- `AutoPipeline.py`（1050 行）：自動資料處理 pipeline 視窗
- `HomePage.py`（124 行）：首頁新增 AutoPipeline 入口

**`NTNU_DataReduction.py`：**
- 新增 `import AutoPipeline`
- Widget stack 新增 `AutoPipelinePage`（頁面 index 20）
- 新增 `toAP()` 方法，帶入 parameters/parameters_name/numCycle context
- HomePage 新增 `AP` 按鈕 → `toAP()`
- `insertLogo()` 加入 try/except 處理沒有 `centralwidget` 屬性的特殊頁面（AutoPipelinePage）

**`Utilities.py`：** 與 V2.7.1 相同，無改動。

---

## V2.7.1（2026-??-??）

### 新功能 — Isochron 控制面板擴充

**`NTNU_DataReduction.py`：**
- SH 控制面板新增：
  - `showAtmCheckbox`：切換是否顯示 40Ar/36Ar 大氣比值線
  - `atmRatio` QDoubleSpinBox：可調大氣比值（預設 298.56，範圍 200–400）
  - `showTempCheckbox`：切換是否顯示溫度標籤
- 新增 `_update_control_visibility(pname)`：isochron 頁面才顯示上述控制項
- 控制面板尺寸調整：高度 120→180，寬度 281→300
- Mouse 座標計算加入 `if xlim is not None and ylim is not None` guard（防止 NoneType crash）
- `SH_apply_axes()` 讀取 show_temp / show_atm / atm_ratio 後傳給 Utilities
- 接收 `getDFStatistics_sh()` 回傳的 `return_limits` 實際軸範圍，存入 `current_xlim/ylim`

### Bug Fix — 軸範圍異常

**`Utilities.py`：**
- `apply_axis()` 新增軸範圍驗證：
  - 若 range > 1e6 → autoscale（防止不合理範圍）
  - 若 max ≤ min → autoscale（防止反轉範圍）
- 圖存檔後二次確認：若最終軸範圍 > 1e6 → 呼叫 autoscale
- `original_indices` 追蹤：溫度標籤位置現在用原始資料行號，修正 mask 過濾後的 index 偏移 bug
- 移除 `bbox_inches="tight"`（DFN/DFI savefig），改回 dpi=300 無 tight（避免軸擠壓）
- `atm_value = atm_ratio` 正確帶入使用者設定值

---

## V2.7（2026-??-??）

### 新功能 — 滑鼠懸停步驟資訊

**`NTNU_DataReduction.py`：**
- SH diagram 頁新增 `infoLabel`（QLabel）：顯示滑鼠位置或 step 資訊
- 啟用 `setMouseTracking(True)` + `installEventFilter(self)`
- 新增 `eventFilter()` 攔截 MouseMove，轉換 pixel → data 座標
- 新增 `step_data` dict（`DFW`：age spectrum steps，`DFA`：Ca/K spectrum steps）
- 新增 `on_mouse_move_SH()` callback：
  - DFW 模式：顯示 step 範圍 / Age ± std / ³⁹Ar 量
  - DFA 模式：顯示 step 範圍 / Ca/K ± std / ³⁹Ar 量
- `getSHStatistics()` 回傳 `step_data` dict 並寫入 `self.step_data`

### Bug Fix — CSV header 格式相容

**`NTNU_DataReduction.py`：**
- header 驗證從「嚴格比對字串」改為「比對欄位數」：
  - 88 欄 → old format
  - 98 欄 → new format（含 isochron ratios）
  - 欄位數正確但字串不同 → 警告但繼續（不再 crash）

### Bug Fix — Isochron 計算用量錯誤

**`Utilities.py`：**
- Normal isochron X/Y：改用 `39Ar(m)/36Ar(m)` 和 `40Ar(m)/36Ar(m)`
  （原本用 `39Ar(k)/36Ar(a)`，未包含所有同位素的 measured total）
- Inverse isochron X/Y：改用 `39Ar(m)/40Ar(m)` 和 `36Ar(m)/40Ar(m)`

---

## V2.6（2026-01-13）

### 大規模重構 — UI 架構清理 + SH 圖新架構

**`NTNU_DataReduction.py`（2666 行，較 V2.5 減少 838 行）：**

移除（過時/實驗性功能）：
- `Clear Memory` 按鈕及 `_place_clear_memory_button()`
- 獨立 axis 控制類 `_connectUI`, `applyAxis`, `autoAxis`, `_setAxisUI`, `_calcAutoAxis`
- 全域 xy 函式 `xy_DFN`, `xy_DFI`, `xy_DFW`, `xy_DFA`
- `_get_40Ar_m_from_df()`, `_get_xy_current()`, `_cfg_apply_to_axis_ui()`
- `toDPS()`, `DFSH_save()`, `DFLS_save()`, `SH_reselect()`

新增：
- `insertLogo()`：統一處理各頁面 logo 插入
- `_read_SH_controls()`：讀取 SH 控制面板設定
- `_save_SH_config()` / `_load_SH_config()`：SH 軸設定的 persist
- `_calc_auto_range()`：自動計算合理軸範圍
- `_get_current_xy_data()`：依目前 pname 回傳對應 XY data
- `SH_apply_axes()` / `SH_auto_axes()`：SH 軸設定主入口

**`Utilities.py`（2000 行，較 V2.5 增加 203 行）：**

移除：
- `_clean_series()`, `auto_axis()`, `parse_date()`（移至 DR 或改寫）

新增：
- `getDFStatistics_ls()`：Laser Step 資料統計
- `getDFStatistics_sh()` 重構：加入 `show_temp`, `show_atm`, `atm_ratio`, `return_limits` 參數

---

## V2.5（2025-12-24）— 基線版本

- NTNU_DataReduction.py：3504 行
- Utilities.py：1797 行
- 包含 `Clear Memory` 按鈕、獨立 axis 控制類、`auto_axis()` 等現已移除的實驗性功能
- SH diagram 軸控制散布在多個獨立函式（`_connectUI`, `applyAxis` 等）

---

## 已知待修項目

| 項目 | 說明 |
|---|---|
| Ca/K calibration hardcoded | R = 0.52 寫死，建議加入 parameter table（`"Ca/K Calibration Factor"`） |
| 38Ar(ca) 置 0 | Datum Publication row[42–43] = 0，尚未計算 Ca-derived ³⁸Ar |
| 36Ar(c), 40Ar(c) 置 0 | cosmogenic components 尚未實作 |
