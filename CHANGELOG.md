# pyADR — NTNU_DataReduction / Utilities 更新日誌

版本追蹤：V2.5 → V2.6 → V2.7 → V2.7.1 → V3.0 → V3.0.1 → V3.1 → V3.1.1 → V3.2 → V3.3 → V3.4 → V3.4.1 → V3.5 → V3.6 → V3.7 → V3.7.1 → V3.7.2 → V3.7.3 → V3.7.4 → V3.8.0 → V3.8.1 → V3.8.2 → V3.8.3 → V3.8.4 → V3.8.5 → V3.8.6 → V3.8.7 → V3.8.8 → V3.8.9 → V3.8.10 → V3.8.11 → V3.8.12 → V3.8.13 → V3.8.14 → V3.8.15 → V3.8.16 → V3.8.17 → V3.8.18 → V3.8.19 → V3.8.20 → V3.8.21 → V3.8.22 → V3.8.23 → V3.8.24 → V3.8.25 → V3.8.26 → V3.8.27 → V3.8.28 → V3.8.29 → V3.8.30 → V3.8.31 → V3.8.32 → V3.8.33 → V3.8.34 → V3.8.35 → V3.8.36 → V3.8.37 → V3.8.38 → V3.8.39 → V3.8.40 → V3.8.41 → V3.8.42 → V3.8.43 → V3.8.44 → V3.8.45
最後整理日期：2026-05-28
整理者：Claude (based on git-style diff across all versions)

---

## V3.8.45（2026-05-28）— T₀ Range chart 擴成 5 isotope + legend 嵌入 blank target 策略

### 需求

v3.8.44 加的 T₀ Range chart 只有 ³⁶/³⁷/³⁸Ar 三個 isotope（³⁹/⁴⁰Ar 沒放）。使用者要：
1. 加 ³⁹Ar / ⁴⁰Ar 兩個 isotope 進去
2. 把「blank T₀ target」策略直接顯示在程式內（不只是聊天解釋）

### 修法

#### 1. 5 isotope 全上

`_paint_t0range_pattern` 內 `range(3)` → `range(5)`。每個 step 從 3 個 box → 5 個 box。為了 fit 同樣 1450 px 寬度：

- `bar_w` 0.65 → 0.55
- `gap_in` 0.05 → 0.04
- `gap_out` 0.6 → 0.7（步間 spacing 稍微拉開讓視覺易分組）

顏色用 module-level `AR_COLS = ['#1a5fb4','#1c7a3a','#8a5a00','#b41a1a','#533ab7']`，跟 cycle button / mV chart 既存配色一致。

#### 2. Per-isotope T₀ pool 計算 blank target

跑 box plot 同時 build `per_iso_t0s[ai]` (5 個 list)，累積每個 isotope 跨所有 step 所有 combo 的 T₀ 值。

```python
sig_min = min(per_iso_t0s[ai])
if sig_min <= 1e-7:
    target = 0.0            # 訊號在 noise，建議 blank ≈ 0
else:
    target = sig_min / 10.0  # blank 應比 signal min 小一個數量級
```

#### 3. Legend 嵌入 target

每個 isotope 的 legend label 包含 target：

```
³⁶Ar  blank < 5e-06
³⁷Ar  blank ≈ 0 (noise)
³⁸Ar  blank < 3e-05
³⁹Ar  blank < 4e-04
⁴⁰Ar  blank < 2e-03
```

legend title 寫 "Blank T₀ target (= signal min / 10)" 說明算法來源。

target format：
- `< 5e-06` 一般情況（科學記號 1 位有效數字）
- `≈ 0 (noise)` 當 signal min ≤ 1e-7（訊號淹在底噪）
- `no data` 當該 isotope 沒 cache 資料

### 怎麼用

1. 載入 sample → 等 prefetch 完成（`✓ Pre-compute done`）
2. T₀ Range chart 顯示 5 個 isotope，legend 直接列出每個的 target
3. 切到 Blank tab，看 5 個 mV chart titleLbl 的 T₀ 值
4. 對照 chart legend target：
   - 達標（|blank T₀| < target）→ OK
   - 超標 → 排 cycle 1, 10 兩端 / 點 Best per n / Auto Blank
5. ³⁷Ar 如果 legend 顯示 `≈ 0 (noise)`，blank ³⁷Ar 不用 fine-tune，全勾或 best per n 都 OK

### 驗證 checklist

- [ ] 載 NO.65 muscovite → 等 prefetch 完成
- [ ] T₀ Range chart 應該每個 step 5 個 box（³⁶ ³⁷ ³⁸ ³⁹ ⁴⁰ 五色）
- [ ] Legend 右上角列出 5 個 isotope 的 blank target
- [ ] Target 數字合理（signal min 可從 chart 上 box 鬚下緣讀，target 應是其 1/10）
- [ ] ³⁷Ar 如果 signal min ≤ 0，target 應顯示 `≈ 0 (noise)`

### 檔案改動

- `AutoPipeline.py`：
  - `_paint_t0range_pattern` 內 `range(3)` → `range(5)`，iso_colors 改用 `AR_COLS`，iso_names 加 ³⁹/⁴⁰Ar
  - box 寬度 + spacing 微調容納 5 isotope
  - 新增 `per_iso_t0s` 累積 + per-isotope target 計算
  - Legend label 嵌 target 字串 + legend title 加說明
- `.work/.app_info.txt`：3.8.44 → 3.8.45
- `CHANGELOG.md`：本段

---

## V3.8.44（2026-05-28）— CalcT0Page 新增 Signal T₀ Range 第三 panel（給 blank 挑 cycle 用）

### 需求

使用者在挑 Blank 的時候，不知道 Signal 各個溫度 step 的 ³⁶/³⁷/³⁸Ar T₀ 大概在什麼範圍，所以也不知道 Blank T₀ 應該壓在多少才合理（blank 應 ≪ signal）。要在 Degassing Pattern Overview 區加一張圖顯示「signal 各 step 跑所有 C(10, 4..10) cycle combos 的 T₀ 分佈」。

### 修法

#### 1. 新 wide chart 加在 Degassing/Yield 下方

`CalcT0Page._build` Degassing 區改成兩排：

```
┌────────────── guide_container (860 px tall) ───────────────┐
│  [Degassing 720×440]  [Yield 720×440]      ← row 1         │
│         [T₀ Range 1450×380]                ← row 2 (NEW)   │
└────────────────────────────────────────────────────────────┘
```

`guide_container.setFixedHeight(460 → 860)`。

#### 2. `_paint_t0range_pattern()` 新方法

對每個 signal step、每個 ³⁶/³⁷/³⁸Ar isotope，從 v3.8.26 加的 `_prefetch_cache` 拿全部 C(10, 4..10) ≈ 848 個 combos 的 T₀ 值，畫 matplotlib `boxplot`：

- box = Q1–Q3 範圍
- median 黑色橫線
- 鬚 = min/max (no fliers)
- 顏色：藍 ³⁶Ar / 綠 ³⁷Ar / 棕 ³⁸Ar
- 灰虛線 reference at y=0
- 標題：「Signal T₀ range (all C(10, 4..10) combos per isotope) — pick blank T₀ ≪ min of these」

每個溫度 step 三個 box 並排（³⁶/³⁷/³⁸ 一組），step 之間留 gap。x 軸 label 是溫度數字。

#### 3. Prefetch finished 自動 trigger refresh

`_on_prefetch_finished` 加 `self._paint_t0range_pattern()` call，使用者不用切 step 就能看到 chart 自動 populate。

`_refresh_guide` 也加這張 paint call，跟 Degassing / Yield 同步刷新。

### 怎麼用

1. 載入 sample signal 之後 sidebar status 會顯示 `Pre-computing: 12/45...`
2. 等到 `✓ Pre-compute done` （v3.8.27 closed-form fast path 後 < 5 秒）
3. T₀ Range chart 自動顯示：每個 step 三個 box，標出 ³⁶/³⁷/³⁸Ar 的 T₀ 範圍
4. 切到 Blank tab → 看自己挑的 cycle 算出來的 blank T₀，比照 chart 上 signal 範圍：
   - 如果 |blank T₀| > 某些 step 的 min signal T₀ → blank correction 過頭，要重挑
   - 如果 blank T₀ << min signal T₀（差 1 個數量級以上）→ OK

### 驗證 checklist

- [ ] 載入 NO.65 muscovite blank + 多個溫度 sample → Calculate T₀
- [ ] 等 footer 顯示 `✓ Pre-compute done`
- [ ] 下方第二排（Degassing / Yield 之下）應該有第三 panel，標題 "Signal T₀ range..."
- [ ] 每個 step 三個 colored box (³⁶ ³⁷ ³⁸Ar)
- [ ] 切到 Blank tab → 看 mV chart 顯示的 blank T₀ 跟 T₀ range chart 對照

### 檔案改動

- `AutoPipeline.py`：
  - `CalcT0Page._build` Degassing 區段加第三個 canvas `cv_t0range` (1450×380)
  - `guide_container.setFixedHeight(460 → 860)`
  - `_paint_t0range_pattern()` 新方法（box plot from prefetch cache）
  - `_refresh_guide()` 加 t0range paint call
  - `_on_prefetch_finished()` 加 t0range repaint trigger
- `.work/.app_info.txt`：3.8.43 → 3.8.44
- `CHANGELOG.md`：本段

---

## V3.8.43（2026-05-28）— AgeCalcPage 新增 Cl/K + Degassing tabs（Stack/Summary 留下版）

### 修法

使用者要求加 3 個新 chart：Degassing pattern、Cl/K spectrum、Stack/Summary。本版做前兩個（單 chart tab 形式），Stack/Summary 是 dialog 形式，下版做。

#### 1. PipelineWorker 加跑 Degassing

`_run` 結尾呼叫 `Utilities.getDegasPlot(datum_csv, mask_all, consts)` 產 `.work/DFD.png`。`getSHStatistics`（既有 call）本來就會產 `.work/DFC.png` (Cl/K spectrum)，不用加新 call。

加入 try/except + `_warns.append` 模式（跟其他 Utilities call 一致）。

#### 2. AgeCalcPage 加 2 個 tab + 2 個 thumbnail

`_build` 內兩個 diagram list 都從 4 個擴成 6 個：

```python
# Tab 1 Summary 內的 4-grid thumbnail → 改成 6-grid (3x2)
('DFW','Age Spectrum'),('DFA','Ca/K'),
('DFN','Normal Isochron'),('DFI','Inverse Isochron'),
('DFC','Cl/K'),('DFD','Degassing')

# Bottom tabs（每個 tab 大圖 + axis controls）
... 同樣 6 個 key/title pair
```

`_dlbls` / `_dlbls_big` / `_daxis` / `_daxis_edits` 4 個 dict 因為都用 key 自動 populate，加 2 個 key 不需要其他改動。`_reload_all_pngs` 跟 `_axis_dialog` 也都是 key-iteration，自動支援新 key。

#### 3. `_refresh_diagrams` 額外跑 SH + Degassing

User 在 isochron tab 改 axis 並 Apply 後，原本只重產 DFW/DFA/DFN/DFI（getDFStatistics_sh）。現在也跟著刷 DFC（getSHStatistics）+ DFD（getDegasPlot），確保 6 個 tab 同步：

```python
try: Utilities.getSHStatistics(...)
except Exception: pass   # 非 fatal
try: Utilities.getDegasPlot(...)
except Exception: pass
```

#### 4. 出版資料夾也包含新 PNG

`PipelineWorker._run` 結尾把 PNG copy 到 `Figures/Publish/StepHeating/` 的 list 從 4 擴成 6：

```python
for key in ['DFW','DFA','DFN','DFI','DFC','DFD']:
```

User export 時 4+2 個 PNG 都會一起出現。

### 下版預告（Stack / Summary）

需要實作的部分（已 audit）：

- `Utilities.getStackPlot(file, mask, constants, top='Ca/K' or 'Cl/K')` → `.work/DFS.png`
- `Utilities.getSummaryPlot(file, mask, constants, panels=[...], layout='vertical' or 'grid')` → caller 自己 savefig

UI：sidebar 加 "Stack / Summary" button → 彈 dialog（按截圖）：
- Mode (radio): Stack 2-panel / Summary multi-panel
- Summary Panels (checkboxes): Age spectrum / %⁴⁰Ar* spectrum / Ca/K / Cl/K / Normal isochron / Inverse isochron
- Layout (radio): Vertical stack / 2-column grid
- Generate / Cancel

Generate 後產 PNG 彈出大圖 dialog 給 user 看 / 存。

### 驗證 checklist

- [ ] 跑 Run Pipeline → 進 AgeCalc page
- [ ] Summary tab 的 thumbnail grid 應該是 3×2 = 6 張（多了 Cl/K + Degassing）
- [ ] 底部 tabs 應該有 8 個：Summary / Datum / Age Spectrum / Ca/K / Normal Isochron / Inverse Isochron / **Cl/K** / **Degassing**
- [ ] 點 Cl/K tab → 大圖顯示 Cl/K spectrum
- [ ] 點 Degassing tab → 大圖顯示 Degassing pattern
- [ ] Cl/K / Degassing tab 的 axis dialog 可以調 XY range，Apply 後重產（注意：DFC / DFD 用同一個 xlim/ylim，跟 isochron 共用，不分離）
- [ ] Sidebar Save → Export → `Agecalc/` 子資料夾應該包含 6 個 PNG 完整集（之前只有 4 個）

### 已知限制（待下版）

- `_refresh_diagrams` 用的是同一個 (xlim, ylim) 給所有 6 張圖，沒有 per-tab axis 獨立 — 因為 Utilities 各 function 只接單 xlim/ylim。DFW (Age) 的橫軸是 cumulative ³⁹Ar%，DFA/DFC/DFD 也類似，DFN/DFI 是 isochron ratio，邏輯上不應該共用。如果要 per-tab axis 獨立，要改 Utilities 簽名（風險高，下版討論）

### 檔案改動

- `AutoPipeline.py`：
  - `PipelineWorker._run` 加 `Utilities.getDegasPlot` call
  - `PipelineWorker._run` copy PNG list 從 4 擴成 6（加 DFC, DFD）
  - `AgeCalcPage._build`：thumbnail grid + bottom tabs 兩處 list 從 4 擴成 6
  - `AgeCalcPage._refresh_diagrams` 加 `getSHStatistics` + `getDegasPlot` re-call
- `.work/.app_info.txt`：3.8.42 → 3.8.43
- `CHANGELOG.md`：本段

---

## V3.8.42（2026-05-28）— MassRatio / AgeCalc sidebar Return 改成「回上一步」

### 修法

`_build_minimal_sidebar._on_return`：

```python
cur_idx = win.stack.currentIndex()
if cur_idx > 0:
    win._go(cur_idx - 1)   # 上一步
else:
    # fallback: 已在 CalcT0Page，走原本回 home 邏輯
    win.t0Page.returnBtn.click()
```

| 當前 page | Return 行為 |
|---|---|
| **MassRatio** (stack idx=1) | → Calculate T₀ (idx=0) |
| **AgeCalc** (stack idx=2) | → MassRatio (idx=1) |
| **CalcT0Page** (idx=0) | 走 fallback → pyADR Home（但 CalcT0Page 自己有獨立 sidebar Return，不用 `_build_minimal_sidebar`，所以 fallback 不會實際觸發） |

用 `win._go(target)` 而不是 `stack.setCurrentIndex(target)`，因為 `_go` 同時更新 pipeline strip 顏色 + Next button 文字，保持 UI 一致。

### 驗證 checklist

- [ ] 跑 Run Pipeline → MassRatio page → 點 sidebar **Return** → 應該跳回 Calculate T₀
- [ ] Next 跑到 AgeCalc → 點 sidebar **Return** → 應該跳回 MassRatio
- [ ] CalcT0Page sidebar **Return** 應該還是回 pyADR Home（這個是 CalcT0Page 自己的 sidebar，不在這版改的範圍）

### 檔案改動

- `AutoPipeline.py`：`_build_minimal_sidebar._on_return` 改成 `_go(cur_idx - 1)`
- `.work/.app_info.txt`：3.8.41 → 3.8.42
- `CHANGELOG.md`：本段

---

## V3.8.41（2026-05-28）— MassRatio / AgeCalc sidebar 拿掉 Load Blank / Load Sample

### 問題

使用者反映：MassRatioPage / AgeCalcPage 的 sidebar 上 Load Blank / Load Sample 兩個按鈕沒必要。載入 raw .dat 只有在 Calculate T₀ 階段才有意義（要看 mV chart 調 mask），在後段 page 沒有對應 UI 顯示。

### 修法

`_build_minimal_sidebar` (v3.8.31) 移除 `btnLdBlank` / `btnLdSig` 兩個 button 跟對應 callback。剩下 4 個按鈕：

```
Return / Save / Open Session / Save Session
```

CalcT0Page 自己 sidebar 的 Load Blank / Load Sample **不動**，那邊才是這兩個 action 的正確入口。

### 影響

- MassRatio / AgeCalc sidebar 從 6 個 button 縮到 4 個
- 整體 sidebar 高度變短
- 使用者要載新檔案：先用左下 Return 回 home，或者用 File → Open Session 切回 T₀ 階段；或者直接從 CalcT0Page sidebar 操作

### 檔案改動

- `AutoPipeline.py`：`_build_minimal_sidebar` 移除 `btnLdBlank` / `btnLdSig` 跟相關 callback；button list 改 4 個
- `.work/.app_info.txt`：3.8.40 → 3.8.41
- `CHANGELOG.md`：本段

---

## V3.8.40（2026-05-28）— 修 MassRatio / AgeCalc sidebar Return 無反應 + menu File→Home 同 bug

### 問題

`MassRatioPage` / `AgeCalcPage` sidebar 上的 Return 按鈕點下去無反應。Menu File → "Return to pyADR Home" 也同樣壞。

### 根因

`_build_minimal_sidebar` (v3.8.31) 內 `_on_return` 寫的 attribute path 錯誤：

```python
def _on_return():
    win = _find_window()                     # 找到 AutoPipelineWindow
    if win is not None and hasattr(win, 'returnBtn'):   # ← False, 不存在
        win.returnBtn.click()
```

`AutoPipelineWindow` **沒有** `returnBtn` attribute。真正的 Return button 在 `CalcT0Page.returnBtn` (line 2026, sidebar 第一顆按鈕)。`AutoPipelineWindow._build` line 5764 把 `t0Page.returnBtn.clicked` 接到 `self._ret`，所以**只有 click 那顆 button 才會 trigger 返回邏輯**。

`hasattr(win, 'returnBtn')` False → callback 是 no-op → 按鈕看似死的。

同個 bug 也存在 menu `_actGoHome` (line 5623)：

```python
self._actGoHome.triggered.connect(lambda: self.returnBtn.click()
                                  if hasattr(self, 'returnBtn') else None)
```

→ menu File → "Return to pyADR Home" 也是死的。

### 修法

兩處 callback 都改走 `t0Page.returnBtn.click()`：

```python
# _build_minimal_sidebar._on_return
win = _find_window()
if win is not None and hasattr(win, 't0Page'):
    t0 = getattr(win, 't0Page', None)
    if t0 is not None and hasattr(t0, 'returnBtn'):
        t0.returnBtn.click()
```

```python
# AutoPipelineWindow menu _actGoHome
def _go_home():
    t0 = getattr(self, 't0Page', None)
    if t0 is not None and hasattr(t0, 'returnBtn'):
        t0.returnBtn.click()
self._actGoHome.triggered.connect(_go_home)
```

CalcT0Page sidebar 的 Return button 本身沒問題（v3.8.31 之前就 work），這版只修兩個 indirect 路徑。

### 驗證 checklist

- [ ] 進 MassRatio page → 點 sidebar **Return** → 應該回 pyADR Home
- [ ] 進 AgeCalc + Datum page → 點 sidebar **Return** → 應該回 pyADR Home
- [ ] 從任何 page 點 File menu → **Return to pyADR Home** → 應該回 pyADR Home
- [ ] CalcT0Page sidebar **Return**（原本就 work）→ 確認沒被改壞

### 檔案改動

- `AutoPipeline.py`：
  - `_build_minimal_sidebar._on_return` 改走 `t0.returnBtn.click()`
  - `AutoPipelineWindow` 內 `_actGoHome.triggered` lambda 改成 `_go_home` 走同樣 path
- `.work/.app_info.txt`：3.8.39 → 3.8.40
- `CHANGELOG.md`：本段

---

## V3.8.39（2026-05-28）— 修 Auto Blank/Signal 真正 bug + Degassing/Yield 圖放大

### 問題

1. v3.8.37 以為 Auto Blank/Signal 閃退是 matplotlib mathtext bug，加 try/except 後仍然失敗，dialog 顯示真正錯誤：

   ```
   list indices must be integers or slices, not tuple
   ```

   每個 step 都同樣錯誤。**根本不是 mathtext 問題**。

2. Degassing Pattern + Yield panel 兩張圖各 480×280，使用者反映在全螢幕看起來太小、字太擠。

### 根因 1: Auto Blank/Signal

`Utilities.calculateT0` (Utilities.py line 205) 內部：

```python
def calculateT0(fit_function_type, v_t, mask, num):
    for i in range(5):
        t = v_t[i, :, 1]      # ← 多軸 numpy indexing，要 3D ndarray
        v = v_t[i, :, 0]
```

`v_t[i, :, 1]` 是 numpy 風格的多軸切片，**只能用在 3D ndarray**。

但 `self._bvt` 是 **list of 5 個 (nc, 2) ndarrays**，不是 stacked 3D ndarray：

- `parse_dat` 返回 list
- `session load` (`load_session_adr`) 也是 `[npz[f'ar{i+36}'] for i in range(5)]` → list
- `_refresh_blank` / `_refresh_signal` 用 `self._bvt[ai]` 是因為 Python list 也支援 single-axis `[ai]` indexing

對 Python list 寫 `v_t[i, :, 1]` 等價於 `v_t[(i, slice, 1)]`，list 不接受 tuple 索引 → raise `list indices must be integers or slices, not tuple`。

### 修法 1

`_auto_blank` / `_auto_signal` 傳給 `Utilities.calculateT0` 之前先 `np.asarray()` stack 成 3D：

```python
v_t_3d = np.asarray(self._bvt)     # shape (5, nc, 2)
result, self._bmask = Utilities.calculateT0(
    self._fit, v_t_3d, np.ones((5, self._nc)), self._nc)
```

每個 step 跑 Auto Signal 時對 `self._svt[nm]` 同樣處理。

如果原本就是 3D ndarray（NTNU sub-program 路徑可能），`np.asarray` 直接 return 原物件，no-op。雙路徑都 work。

### 修法 2: Degassing / Yield 放大

- `cv_degas` 480×280 → **720×440**
- `cv_yield` 480×280 → **720×440**
- `guide_container.setFixedHeight` 300 → **460**
- Font sizes 對應放大：
  - ylabel / xlabel: 8 → **11**
  - tick labels: 7 → **10**
  - legend (degassing): 6 → **9**
  - legend (yield): 7 → **10**

整個 panel 區域寬約 1460 px（720+720+spacing），全螢幕下 fit 沒問題。

### 影響

- Auto Blank / Auto Signal 真的能跑了
- Degassing + Yield 圖視覺面積 ×2.4 (480×280 ≈ 134k px² → 720×440 ≈ 317k px²)
- Font scaling 後文字清晰可讀，圖例不再重疊
- 數值結果不變

### 驗證 checklist

- [ ] 載入 blank + signal → Calculate T₀
- [ ] 點 Auto Blank → 5 個 mV chart 應該更新，無 error dialog
- [ ] 點 Auto Signal → 所有 step 跑完，無 error dialog（之前每個 step 都失敗）
- [ ] Degassing Pattern + Yield panel 兩張圖明顯比之前大
- [ ] 字體大小可讀，圖例不擠在角落

### 檔案改動

- `AutoPipeline.py`：
  - `_auto_blank` / `_auto_signal` 加 `np.asarray()` stack
  - `cv_degas` / `cv_yield` `setFixedSize(720, 440)`
  - `guide_container.setFixedHeight(460)`
  - `_paint_degas_pattern` / `_paint_yield_pattern` font sizes 全面 +3pt
- `.work/.app_info.txt`：3.8.38 → 3.8.39
- `CHANGELOG.md`：本段

---

## V3.8.38（2026-05-28）— 修 Manual button 文字 '✓' 不會清的 bug

### 問題

使用者看到 Manual button 顯示 `Manual ✓` 跟黃色背景，問為什麼會打勾。

### 根因

`_toggle_manual` 切換時只改**背景顏色**（amber = manual / panel-gray = auto），**不動文字**。

v3.8.28 加 session load 同步時多寫了 `self.btnM.setText('Manual ✓' if self._manual else 'Manual')`（在 `_open_session` 內），結果造成兩套互相不同步的狀態指示：

- 背景色 → `_toggle_manual` 會動
- 文字 ✓ → 只有 session load 時設，之後 `_toggle_manual` 不會清掉

→ 從帶 `manual=True` 的 .adr 載入後，即使再點 Manual button 切回 auto（背景變灰），文字還是顯示 `Manual ✓`。

### 修法

`CalcT0Page` 抽出 `_apply_manual_style()` 共用 helper：

```python
def _apply_manual_style(self):
    col = AMB_BG if self._manual else PNL
    tc  = '#8a5a00' if self._manual else TXT
    bc  = '#8a5a00' if self._manual else BRD
    self.btnM.setStyleSheet(_btn_style(col, tc, bc))
    self.btnM.setText('Manual')   # always plain; color signals state
    if hasattr(self, '_chips'):
        self._chips['Mode'].setText('Manual' if self._manual else 'Auto')
    for cv in self._cv:
        cv._manual = self._manual

def _toggle_manual(self):
    self._manual = not self._manual
    self._apply_manual_style()
```

`_open_session` 內也改 call 同樣 helper（不再 setText ✓）。

設計決定：Button text 永遠是 plain `Manual`，**背景顏色 + Mode chip 才表示狀態**：
- Manual mode：amber 黃底 + Mode chip 顯示 "Manual"
- Auto mode：灰底 + Mode chip 顯示 "Auto"

### 影響

- Toggle / session load 兩條路徑現在用同一個 styling 邏輯，不會 drift
- Button 文字一律 `Manual`，狀態看背景跟頂部 chip
- 純 UI 改動，無數值變化

### 驗證 checklist

- [ ] 啟動 AutoPipeline 預設 → btnM 灰底 `Manual` 文字、Mode chip 顯示 `Auto`
- [ ] 點 Manual button → btnM 黃底 `Manual` 文字、Mode chip 變 `Manual`
- [ ] 再點 → 回灰底 `Manual` 文字、Mode chip 變 `Auto`
- [ ] 載入 manual=True 的 .adr → btnM 黃底 `Manual` 文字（不再是 `Manual ✓`）
- [ ] 載入後再點 toggle → 正常切換回 Auto

### 檔案改動

- `AutoPipeline.py`：
  - `CalcT0Page._apply_manual_style` 新 helper
  - `_toggle_manual` 改 call helper
  - `_open_session` 內 `btnM.setText` 改 call helper
- `.work/.app_info.txt`：3.8.37 → 3.8.38
- `CHANGELOG.md`：本段

---

## V3.8.37（2026-05-28）— 修 Auto Blank / Auto Signal 閃退 + Help 加 Guide

### 問題

使用者按 Auto Blank 或 Auto Signal 後 GUI 整個閃退。Console 沒留 traceback（因為 worker 是 sync call 在主執行緒、crash 直接掛）。

### 根因

`Utilities.calculateT0` (line 205) 內部：
- Line 281：`axs[i//3, i%3].set_title("Ar ...\n$T_{0}$ = ...")` 使用 LaTeX `$T_{0}$`
- Line 284：`plt.tight_layout()`
- Line 285：`plt.savefig(".work/LR.png")`

`tight_layout` / `savefig` 都會觸發 matplotlib renderer pass，跟 v3.8.30 修過的 mathtext parser bug 同一個（Anaconda Py 3.13 + 較新 matplotlib 對 `$\\mathdefault{...}$` parse 失敗 → ValueError）。AutoPipeline v3.8.30 修了自己 chart code，但 **Utilities.calculateT0 沒包**。

### 修法

#### 1. `Utilities.calculateT0` / `REcalculateT0` 包 try/except

兩處 `plt.tight_layout()` + `plt.savefig()` 全包 try/except：

```python
try: plt.tight_layout()
except Exception: pass
try: plt.savefig(".work/LR.png", dpi=200)
except Exception: pass
```

失敗時還是會 `return [status, T0, T0_SIGMA, R], mask` 給 caller — figure 沒存沒關係（AutoPipeline 自己有 mV chart，不依賴 LR.png）。

#### 2. AutoPipeline 端 `_auto_blank` / `_auto_signal` 包 try/except

雙保險。即使 Utilities 端的 try/except 沒攔住（例如以後新的 mathtext code path），AutoPipeline 端也會 catch + show warning dialog 而不是 crash。

`_auto_signal` 額外處理：某個 step 失敗時繼續跑下一個，最後列出失敗的 step 清單給使用者參考（保留它們的既有 mask）。

#### 3. Help menu 加 `Auto Blank / Signal Guide` entry

新 menu item 開新 `_show_auto_guide()` dialog，內容包含：

- **演算法**：每 isotope 跑 R²<0.8 trigger outlier removal、|r|>σ threshold、最多 4 個
- **兩按鈕差異**：Auto Blank 只跑 blank、Auto Signal 跑所有 step
- **何時用 / 何時不用**：4 個情境表格 — 第一次看樣品 ✓、發表級 fine-tune ⚠、low-T ³⁶Ar 受限 ✗、³⁷Ar 訊號小 ✗
- **跟手動差別**：Auto threshold 比手動 MAD z-score 寬鬆，Auto 完還可以手動 fine-tune
- **建議流程**：Auto Blank → Auto Signal → 手動排除紅色 → 點 Best per n button → 確認

跟既存的 Cycle Selection Guide 區隔（Cycle Guide 著重在手動 cycle button 顏色/挑選策略；Auto Guide 是 high-level 「這兩個按鈕做什麼、怎麼用」）。

### 影響

- Auto Blank / Auto Signal 現在 robust，不會閃退
- 失敗時 user 看到清楚的 warning dialog，知道是 matplotlib 問題，可以選擇手動或重試
- 數值結果不變（沒動 σ_T0 公式跟 outlier criteria，只是包安全網）

### 驗證 checklist

- [ ] 載入 blank + signal → 進 Calculate T₀ page
- [ ] 點 sidebar **Auto Blank** → 應該成功跑完，5 個 mV chart 更新；如果 Utilities 內部 raise，看到「Auto Blank failed」warning dialog 而非閃退
- [ ] 點 **Auto Signal** → 所有 step 跑完，無閃退；如果有 step 失敗，最後 dialog 列出哪些
- [ ] Help → Auto Blank / Signal Guide → 看到完整說明 dialog

### 檔案改動

- `Utilities.py`：`calculateT0` / `REcalculateT0` 兩處 `plt.tight_layout()` + `plt.savefig()` 包 try/except
- `AutoPipeline.py`：
  - `CalcT0Page._auto_blank` / `_auto_signal` 包 try/except + warning dialog
  - `AutoPipelineWindow` Help menu 新增 `Auto Blank / Signal Guide` action
  - `AutoPipelineWindow._show_auto_guide` 新 method（scrollable QDialog with rich-text content）
- `.work/.app_info.txt`：3.8.36 → 3.8.37
- `CHANGELOG.md`：本段

---

## V3.8.36（2026-05-28）— AgeCalcPage 底部 Excel 風格 Tab：Summary / Datum / 4×大圖

### 修法

#### 1. AgeCalcPage `_build` 加 `QTabWidget` 在 content 內

`tabPosition=South` 把 tab bar 放底部（Excel-style）：

```
┌────────────────────────────────────────┐
│  AgeCalcPage content                   │
│  (summary banner: Total/Plateau/...)   │
├────────────────────────────────────────┤
│                                        │
│  QTabWidget                            │
│   ↓ Tab 1: Summary (既存 layout)        │
│      [Results per Step] [4-grid PNGs] │
│   ↓ Tab 2: Datum (新增 QTableWidget)    │
│      raw {sid}_datum.csv 88 cols      │
│   ↓ Tab 3: Age Spectrum (大圖+axis)     │
│   ↓ Tab 4: Ca/K (大圖+axis)             │
│   ↓ Tab 5: Normal Isochron (大圖+axis)  │
│   ↓ Tab 6: Inverse Isochron (大圖+axis) │
└────────────────────────────────────────┘
      [Summary] [Datum] [Age Spectrum] [Ca/K] ...   ← bottom tabs
```

#### 2. `_make_diagram_tab(key, title)` helper

每個 diagram tab 自帶 XY axis 控制：

```
┌─────────────────────────────────────────────────┐
│ Age Spectrum   X min:[] X max:[] Y min:[] Y max:[]│
│                            [Apply] [Reset]       │
├─────────────────────────────────────────────────┤
│                                                 │
│         (大圖 600×400 minimum)                   │
│                                                 │
└─────────────────────────────────────────────────┘
```

`Apply` 解析 4 個 LineEdit 值（空白 = auto），寫進 `self._daxis[key]`，呼叫 `self._refresh_diagrams()` 真的重產 PNG。`Reset` 清空後 trigger refresh，回 auto 範圍。

#### 3. Datum tab：`_load_datum_into_table(datum_csv)` 

讀 `{sid}_datum.csv` 全 88 欄塞進 QTableWidget，header 自動設成 CSV 第一列，跳過全空 row。column 預設寬 110 px、`Interactive` mode 讓使用者可以拖拉調寬。

#### 4. 統一 `_reload_all_pngs()` helper

之前三處（populate / `_on_isochron_method_changed` / `_refresh_diagrams`）各自寫 PNG reload 迴圈，現在抽成單一 method，同時刷 thumbnail 跟 big view labels。

### 影響

- 介面上多 5 個底部 tab（Summary 之外另 5 個）
- Summary tab 內容跟之前介面完全一樣，沒移動 widget
- 大圖 tab 的 axis 控制現在真的 work（搭配 v3.8.35 修好的 `_refresh_diagrams`）
- Datum tab 即時顯示計算結果，不需要另外開 CSV 檔

### 已知待做（不在本版）

| 項目 | 規模 | 備註 |
|---|---|---|
| 抄 DiagramPlot 還有什麼 feature | 中 | DiagramPlot 已有 4 個圖跟 AutoPipeline 相同，主要差別是大圖 + 軸控（本版已做）。額外功能（style 切換、export per-figure、mouse hover info 等）視需要再加 |
| 大圖 resize 時 pixmap 自適應 | 小 | 目前 setMinimumSize(600, 400)，再 resize 視窗 pixmap 不會跟著縮放。要 override resizeEvent |

### 驗證 checklist

- [ ] 跑 Run Pipeline → 進 AgeCalc + Datum page
- [ ] 介面下方應該有 6 個 tab：Summary / Datum / Age Spectrum / Ca/K / Normal Isochron / Inverse Isochron
- [ ] Summary tab = 既存介面（results table + 4 縮圖）
- [ ] 點 Datum tab → 表格顯示 datum CSV 完整內容（88 欄）
- [ ] 點 Age Spectrum tab → 大圖顯示，上方有 X/Y min/max 4 個 input + Apply / Reset
- [ ] 在 Normal Isochron tab 設 X max=100, Y max=600, Apply → 圖真的調軸
- [ ] Reset → 圖回 auto 範圍

### 檔案改動

- `AutoPipeline.py`：
  - `AgeCalcPage._make_diagram_tab(key, title)` 新 helper
  - `AgeCalcPage._load_datum_into_table(datum_csv)` 新 helper
  - `AgeCalcPage._reload_all_pngs()` 新 helper（抽出統一 reload 邏輯）
  - `AgeCalcPage._build` splitter 包進 QTabWidget(South)，加 5 個 tab
  - `populate` / `_on_isochron_method_changed` / `_refresh_diagrams` 三處 PNG reload 改用 `_reload_all_pngs()`
  - `populate` 加 `_load_datum_into_table(datum_csv)` call
- `.work/.app_info.txt`：3.8.35 → 3.8.36
- `CHANGELOG.md`：本段

---

## V3.8.35（2026-05-28）— Sidebar 統一 Save 命名 / Session 對調 / 修 Show Temp 跟 axis 失效

### 問題

使用者在 AgeCalc+Datum 介面回饋四件事：

1. Sidebar 的 `Save To` 跟 CalcT0Page 的 `Save` 不一致 → 統一叫 `Save`
2. `Save Session` 在上、`Open Session` 在下 → 對調（Open 在上）
3. `Show Temp labels on Isochron` checkbox 勾了沒反應、每張圖 ⚙ 齒輪 axis dialog 設了 XY range 也沒效果
4. （大改動）AgeCalc+Datum 介面加 Excel-style 底部 tabs 顯示 Datum data；抄 DiagramPlot 功能進來

本版只做 1、2、3。4 是大改動先報告再做。

### 修法

#### 1. Sidebar `Save To` → `Save`

`_build_minimal_sidebar(page, save_handler, save_label='Save')` default label 從 `Save To` 改 `Save`。兩個 caller (`MassRatioPage._build` / `AgeCalcPage._build`) 對應 `save_label='Save To'` 也一起拿掉 → 三個 page (CalcT0 / MassRatio / AgeCalc) sidebar 第二顆按鈕全部叫 `Save`。

#### 2. Open Session / Save Session 上下對調

兩處 sidebar 排列順序：

- `CalcT0Page._build`：`..., self.btnSaveSession, self.btnOpenSession` → `..., self.btnOpenSession, self.btnSaveSession`
- `_build_minimal_sidebar`：`..., btnSaveSess, btnOpenSess` → `..., btnOpenSess, btnSaveSess`

#### 3. 修 Show Temp labels + axis 失效

定位：`AgeCalcPage._refresh_diagrams`（line 4419）之前只是 stub：

```python
# 之前
if hasattr(self, '_on_refresh_request'):
    self._on_refresh_request(self._daxis, self.tempLabelCB.isChecked(), self._get_atm_ratio())
# Reload existing PNGs   ← 但 PNG 從來沒被重新產生
```

只 reload disk 上的 PNG，**沒呼叫 `Utilities.getDFStatistics_sh` 真的重產 PNG**。所以 Show Temp checkbox / ⚙ axis dialog 設了值都 dead code。

`Utilities.getDFStatistics_sh` 簽名 (line 557) 早就支援這些參數：

```python
def getDFStatistics_sh(file, mask, constants, Ncolor, Nmaker,
                       xlim=None, ylim=None, ...
                       show_temp=False, atm_ratio=298.56,
                       isochron_method='ols'):
```

修法 — 改 `_refresh_diagrams` 成跟 `_on_isochron_method_changed` 同樣 pattern：

```python
xlim = (xmin, xmax) if 都 not None else None
ylim = (ymin, ymax) if 都 not None else None   # 從 self._daxis['DFN'] 取
Utilities.getDFStatistics_sh(self._datum_csv, mask_all, self._consts,
                             'b', 'o',
                             xlim=xlim, ylim=ylim,
                             show_temp=show_temp,
                             atm_ratio=atm_ratio,
                             isochron_method=method)
# 然後 reload PNG
```

Axis 從 DFN (Normal Isochron) 取因為兩張 isochron diagram 一般一起調，DFN 的設定當 canonical。

### 驗證 checklist

- [ ] 三個 page sidebar 第二顆按鈕現在都是 `Save`（不是 `Save To`）
- [ ] 三個 page sidebar：`Open Session` 在 `Save Session` 上方
- [ ] AgeCalc+Datum 勾掉 `Show Temp labels on Isochron` → Normal/Inverse Isochron PNG 應該真的沒了溫度標籤
- [ ] 點某張 isochron ⚙ → 設 X min/max → Apply → diagram 真的調 X 軸範圍
- [ ] 改 `40Ar/36Ar atm` 值 → Recalculate → 應該影響 isochron fit

### 待做（不在本版）

| 項目 | 規模 | 備註 |
|---|---|---|
| AgeCalc+Datum 底部 Excel-style tabs（Summary / output data / 各 chart） | 大 | 要先確認 tabs 內容 + 順序 |
| 把計算好的 datum data 在介面內顯示（output data tab） | 中 | 依賴 tabs 架構 |
| 抄 DiagramPlot 哪些功能 | 大 | 要先列清單問哪些值得搬 |

### 檔案改動

- `AutoPipeline.py`：
  - `_build_minimal_sidebar` default `save_label`：`Save To` → `Save`，buttons 排列對調 Open/Save Session
  - `CalcT0Page._build` sidebar 排列對調 Open/Save Session
  - `MassRatioPage / AgeCalcPage` caller 拿掉 `save_label='Save To'`
  - `AgeCalcPage._refresh_diagrams` 重寫，真正呼叫 `Utilities.getDFStatistics_sh` 帶 axis / show_temp / atm_ratio 參數
- `.work/.app_info.txt`：3.8.34 → 3.8.35
- `CHANGELOG.md`：本段

---

## V3.8.34（2026-05-28）— Save 按鈕改名 + 右上角綠按鈕拿掉 + Warning 統整成一個

### 問題（三件事一起做）

1. **CalcT0Page sidebar "Save T₀" 改成 "Save"**（使用者口頭要求）
2. **MassRatioPage / AgeCalcPage 右上角綠色 Save / Export 按鈕拿掉** — sidebar Save To 已經是唯一入口，右上角的副本多餘
3. **Mass Ratio Warning 跳很多視窗** — 9 個 step、每個 step 可能 1~5 個 Negative datum / Net≤0 警告，原本一次跑完 pipeline 會 pop 10+ 個重疊的 MessageBox。整成一個

### 修法

#### 1. Save T₀ → Save

- `CalcT0Page._build` sidebar 按鈕 label: `'Save T₀'` → `'Save'`
- `_save` dialog title: `'Save T₀'` → `'Save'`, `'Save T₀ — Done'` → `'Save — Done'`
- 檔頭 module docstring 同步更新

#### 2. 移除右上角綠色按鈕

兩個 page header 都改成只有 centered title，原綠色按鈕變成 `QPushButton(); .hide()` 隱形 placeholder（保留 method 觸發路徑，sidebar Save To 透過 `lambda: self._save()` / `self._export()` 仍然可以叫到）。

```python
# 之前
self.saveBtn = QtWidgets.QPushButton('Save')
self.saveBtn.setStyleSheet(_btn_style('#2e7d52','white','#2e7d52')+...)
self.saveBtn.clicked.connect(self._save)
hdr.addWidget(self.saveBtn)            # ← 拿掉

# 現在
self.saveBtn = QtWidgets.QPushButton(); self.saveBtn.hide()
self.saveBtn.clicked.connect(self._save)
# 不 addWidget — 不在 UI 顯示
```

`AgeCalcPage.exportBtn` 同樣處理。

#### 3. Warning 統整成一個 dialog

`PipelineWorker`：

- `__init__` 加 `self._warns = []` buffer
- 4 處 `self.sig_warn.emit(msg)` 改成 `self._warns.append(msg)`：
  - `Net values ≤0` (Mass Ratio 階段每個 step 都可能)
  - `Negative datum at <step>` (Datum 階段每個 step 都可能)
  - `getSHStatistics: <err>` (Statistics 階段)
  - `getDFStatistics_sh: <err>` (Diagram 階段)
- `_run` 結尾、`sig_prog.emit('Done')` 之前：

```python
if self._warns:
    self.sig_warn.emit('\n\n'.join(self._warns))
```

→ 一次 emit 含所有累積訊息的單一 string，AutoPipelineWindow 端的 `sig_warn` slot 只觸發一個 QMessageBox。

### 截圖前後

- 之前：跑 9 step pipeline → 3+ 個重疊的 MessageBox（Net≤0 / Negative @1400°C / Negative @1500°C），user 要點 OK 3 次
- 現在：跑完只有 1 個 MessageBox：

```
Net values ≤0:
  Ar38 @Temperature 600°C
  Ar37 @Temperature 850°C
  ...

Negative datum at Temperature 1400°C:
  40Ar(r)=-4.284e-03, 36Ar(air)=-3.21e-06

Negative datum at Temperature 1500°C:
  40Ar(r)=-2.184e-02
```

點一次 OK 即可。

### 驗證 checklist

- [ ] CalcT0Page sidebar 第二顆按鈕標籤是 `Save`（不再是 `Save T₀`）
- [ ] 按 Save 之後 dialog 標題 `Save` / `Save — Done`
- [ ] MassRatioPage 右上角沒有綠色 Save 按鈕；header 只剩置中的 "Mass Ratio" 標題
- [ ] AgeCalcPage 右上角沒有綠色 Export 按鈕；header 只剩 "Age Calculation & Datum" 標題
- [ ] sidebar Save To 仍然能正常存檔（Mass Ratio CSV / Datum export）
- [ ] 跑 Run Pipeline → pipeline 結束後**只有 1 個 Warning dialog**，內容包含所有 step 的 Net≤0 / Negative datum 訊息

### 檔案改動

- `AutoPipeline.py`：
  - `CalcT0Page._build` sidebar `'Save T₀'` → `'Save'`
  - `CalcT0Page._save` dialog title 兩處 `Save T₀` → `Save`
  - 檔頭 docstring 更新
  - `MassRatioPage.__init__` header Save button 隱藏（saveBtn 保留 hidden）
  - `AgeCalcPage.__init__` header Export button 隱藏（exportBtn 保留 hidden）
  - `PipelineWorker.__init__` 加 `self._warns = []`
  - 4 處 `sig_warn.emit` → `_warns.append`
  - `_run` 結尾加 final batch emit
- `.work/.app_info.txt`：3.8.33 → 3.8.34
- `CHANGELOG.md`：本段

---

## V3.8.33（2026-05-28）— MassRatioPage._save Value 欄修正（從 '—' 改成實際 ratio 數值）

### 問題

使用者要求審查 AutoPipeline 的 Calculate T₀ 跟 Mass Ratio 輸出格式對齊度。Audit 結果：

| 項目 | 子程式 | AutoPipeline | 一致？ |
|---|---|---|---|
| Calculate T₀ (`write_t0_csv` vs `LRP_save`) | header + 欄序 100% 同 | ✓ | ✓ |
| T₀ Date 格式 | `2024/4/18` raw | `2024/04/18` zero-padded | ⚠ 微改進，不算 bug |
| MR PipelineWorker._run | header + 欄序 + ratio name 全同 | ✓ | ✓ |
| MR MassRatioPage._save header | 11 cols 拆開 (v3.8.24 修過) | ✓ | ✓ |
| MR MassRatioPage._save **Value 欄** | `ratio_result[3][i]` (實際數值) | `'—'` 永遠 dash | **❌ Bug** |

子程式 `MR_save`（NTNU line 3014）跟 AutoPipeline `PipelineWorker._run`（line 4143）都在 Mass Ratio CSV 第 10 欄 (`Value`) 寫實際 ratio 數值（mr[3][i]），但 `MassRatioPage._save` 卻寫 `'—'`。代碼註解 `# Ratio value (原始程式沒有這欄數值)` 是錯的——子程式有這欄而且有數值。

→ 使用者按 sidebar **Save To** 手動存的 Mass Ratio CSV，Value 欄全是 dash，缺真實數值；按 pipeline 自動跑出來的 CSV 則正確。**兩個入口輸出不一致**。

### 修法

`MassRatioPage._save` 兩處改動：

```python
# 取資料時順便拿 ratio (PipelineWorker._run 已經存在 step['ratio'] 內)
ratio = step.get('ratio', [0]*5)

# row 寫入：'—' → f'{ratio[i]:.17e}'
self._ratio_names[i],          # Ratio name (col 9)
f'{ratio[i]:.17e}',            # Ratio value (col 10) ← 修
f'{ratio_sigma[i]:.17e}'       # Ratio sigma (col 11)
```

`step['ratio']` 由 PipelineWorker line 4154 寫入 `list(mr[3])`，已經包含在 AgeCalcPage / MassRatioPage 共用的 `_steps` 結構裡，不需要重新計算。

### Ratio name 對照（已對齊，記錄供 audit）

三邊完全一致 `['Ar39/40', 'Ar36/40', 'Ar39/36', 'Ar40/36', 'Ar38/36']`：
- 子程式 `self.mass_pair` (NTNU line 1332)
- AutoPipeline `MassRatioPage._ratio_names` (line 3609)
- AutoPipeline `PipelineWorker._run` hardcoded (line 4143)

### Date format（不動，記錄差異）

子程式 LRP_save 寫 raw `info[3]`（e.g. `2024/4/18`），AutoPipeline `write_t0_csv` 通過 `_norm_date` zero-pad 成 `2024/04/18`。這是 **AutoPipeline 的改進**（統一格式），不破壞讀取相容性，**保留**。

### 驗證 checklist

- [ ] 跑 Run Pipeline → 進 Mass Ratio page
- [ ] 點 sidebar Save To → 選溫度 → 選存檔資料夾
- [ ] 開存出來的 CSV → 第 10 欄 `Value` 應該是 ratio 數值（科學記號），**不再是** `—`
- [ ] 數值跟 `Data/MassRatio/{step}.csv` （PipelineWorker 寫的）第 10 欄一致
- [ ] 拿手動 Save 出來的 CSV 跟子程式 MR_save 同一 step 對比，格式相同

### 檔案改動

- `AutoPipeline.py`：`MassRatioPage._save` 取 `step['ratio']` + row 寫入 Value 改 ratio[i]
- `.work/.app_info.txt`：3.8.32 → 3.8.33
- `CHANGELOG.md`：本段

---

## V3.8.32（2026-05-28）— AgeCalc per-step CSV 對齊 NTNU 子程式 AC_save 格式

### 問題

子程式 `NTNU_DataReduction.AC_save`（line 2879）每按一次儲存會把當前 step 的 AgeCalc 結果寫成一個 CSV：

```
Samp#, t, Min, iradiation PK 90%, Variable, Value, Sigma
0621-01C, 1100, Muscovite, NTNU-2, Ar_36_m, 1.23e-05, 2.5e-07
0621-01C, 1100, Muscovite, NTNU-2, Ar_36_Air, ..., ...
...
0621-01C, 1100, Muscovite, NTNU-2, J_int, 1e-06, N/A
```

AutoPipeline PipelineWorker 在 Pipeline 跑完時也會寫 `Data/Agecalc/{step}.csv`，但格式不對：每個變數跟 std 各佔一 row，Sigma 欄永遠空白。使用者要求 AutoPipeline AgeCalc+Datum export 能輸出**子程式格式**的 per-step CSV，**不同溫度也不同檔案**。

### 修法

#### 1. 新 helper `_write_agecalc_csv_subprog(path, vnm, ar, sid, t, mn, irr)`

掃描 `vnm` list，若 `vnm[i+1] == vnm[i] + '_std'`，把 (value, sigma) 合成一個 row；單值 entry（J_int / T_int / Ar_40_r_ratio / C1..C4）沒有 `_std` twin，Sigma 欄填 `N/A`。

```python
while i < n:
    if vnm[i+1] == vnm[i] + '_std':
        w.writerow([sid, t, mn, irr, vnm[i], _fmt(ar[i]), _fmt(ar[i+1])])
        i += 2
    else:
        w.writerow([sid, t, mn, irr, vnm[i], _fmt(ar[i]), 'N/A'])
        i += 1
```

Header 對齊子程式：`Samp#, t, Min, iradiation PK 90%, Variable, Value, Sigma` (用 `iradiation PK 90%` 不是 `IRR`)。

#### 2. PipelineWorker 改用新 helper

`_run` 內既存 ac_csv 寫法（每變數獨立 row、Sigma 空白）整段替換成 `_write_agecalc_csv_subprog(...)` 一行 call。原本 ~7 行寫入邏輯 → 1 行。

#### 3. AgeCalcPage._export dialog 加 checkbox

```python
cb_agecalc = QtWidgets.QCheckBox('AgeCalc CSV per temperature (sub-program format)')
cb_agecalc.setChecked(True)
```

勾選後 export 時新建 `<save_dir>/Agecalc/` 子資料夾，把每個 step 的 `ac_csv`（PipelineWorker 寫的）`shutil.copy` 過去。每個溫度一個 CSV，命名跟 step name 相同（例如 `Temperature 1100°C.csv`）。

Export dialog 現在有 4 個 checkbox：
- Datum CSV
- Summary table (Results per Step)
- All diagrams (PNG)
- **AgeCalc CSV per temperature** (新)

### 影響

- 數值內容完全不變 — 只改 row 格式 (value/std 合併成 value+sigma 兩欄)
- `Data/Agecalc/{step}.csv` 從 ~55 row 縮到 ~30 row（合併後）
- 外部 tool 讀 ac_csv 時格式跟子程式 AC_save 完全一致，可以無縫互換

### 驗證 checklist

- [ ] 跑 Run Pipeline → 進 AgeCalc + Datum page
- [ ] 點 Save To（或 header Export）→ dialog 應該有 4 個 checkbox
- [ ] 全部勾選 → 選目標資料夾
- [ ] 確認 `<save_dir>/Agecalc/` 內有每個 step 一個 CSV（檔名 `Temperature X°C.csv`）
- [ ] 打開其中一個 CSV，header 應該是 `Samp#, t, Min, iradiation PK 90%, Variable, Value, Sigma`
- [ ] 確認 Ar_36_m 那 row 的 Sigma 欄有數值（不是空白）
- [ ] 確認 J_int / T_int / Ar_40_r_ratio / C1..C4 那些 row 的 Sigma 欄是 `N/A`

### 檔案改動

- `AutoPipeline.py`：
  - 加 module-level `_write_agecalc_csv_subprog(path, vnm, ar, sid, t, mn, irr)` helper
  - `PipelineWorker._run` ac_csv 寫法改用 helper（內聯 7 行 → 1 行）
  - `AgeCalcPage._export` dialog 加 `cb_agecalc` checkbox + copy logic
- `.work/.app_info.txt`：3.8.31 → 3.8.32
- `CHANGELOG.md`：本段

---

## V3.8.31（2026-05-28）— MassRatioPage / AgeCalcPage 加 sidebar

### 問題

使用者要求 MassRatioPage 跟 AgeCalcPage 也要有跟 CalcT0Page 一致的左側 sidebar，但**不要 Auto Blank / Auto Signal / Manual 三個 T₀ 專屬按鈕**。三個 page 之間應該都能無縫 Return / Save / 切換載檔 / 存讀 session。

「Save To」按鈕在不同 page 觸發不同存檔行為：
- MassRatio page → 存 Mass Ratio CSV
- AgeCalc+Datum page → Export (datum CSV + summary + diagrams)

### 修法

#### 1. Module-level `_build_minimal_sidebar(page, save_handler, save_label)`

mirror CalcT0Page sidebar (91×51 button, vertical column)，按鈕子集：

| 按鈕 | 行為 |
|---|---|
| `Return` | walk_parent 找 AutoPipelineWindow → click `returnBtn`（回 pyADR Home） |
| `Save To` | 呼叫傳入的 page-specific `save_handler`（MassRatio: `_save`；AgeCalc: `_export`） |
| `Load Blank` | `stack.setCurrentIndex(0)` 跳回 CalcT0 → `t0Page._load_blank_dialog()` |
| `Load Sample` | 同上 → `_load_signal_dialog()` |
| `Save Session` | `t0Page._save_session()` |
| `Open Session` | `t0Page._open_session()` |

每個 handler 內用 walk_parent 找 AutoPipelineWindow，所以 page 不需要 ctor 注入 reference。

#### 2. MassRatioPage / AgeCalcPage layout 重構

`__init__` 開頭改成 outer `QHBoxLayout`：

```python
outer = QtWidgets.QHBoxLayout(self)
self._sidebar = _build_minimal_sidebar(self, lambda: self._save(),  # or _export
                                       save_label='Save To')
outer.addWidget(self._sidebar)
_content = QtWidgets.QWidget()
outer.addWidget(_content, 1)
vb = QtWidgets.QVBoxLayout(_content)   # ← 既存 vb 全部 widget 改用這個
```

既存 header / save button / table / chart layout 完全不動，只是包進 `_content` 內。

#### 3. 既存 header Save / Export button 保留

兩個 page 既存的 page-header Save / Export 按鈕沒拿掉，sidebar 是額外的入口。使用者習慣哪個 click 哪個。

### 影響

- 純 UI layout 改動，無數值變化
- 內容區域寬度減 110 px（sidebar 寬度），但兩個 page 內容本來就有 splitter / scroll area 自適應，不影響使用
- Sidebar Load Blank/Sample 會切回 Calculate T₀ page 後彈 file dialog — 這是合理的因為載檔後需要在 T₀ page 看資料

### 驗證 checklist

- [ ] 跑完 pipeline，導到 Mass Ratio page
- [ ] 左側應該有 6 個按鈕：Return / Save To / Load Blank / Load Sample / Save Session / Open Session
- [ ] 點 Save To → 彈 Save Mass Ratio dialog（跟 header 的 Save 按鈕一樣）
- [ ] 點 Load Blank → 跳回 Calculate T₀ page，彈檔案選擇 dialog
- [ ] 點 Save Session → .adr 對話框
- [ ] 點 Return → 回 pyADR Home
- [ ] 切到 Age Calc + Datum page → sidebar 一樣 6 個按鈕
- [ ] 點 Save To → 彈 Export dialog（datum CSV / summary / diagrams 三選一）

### 檔案改動

- `AutoPipeline.py`：
  - 加 module-level `_build_minimal_sidebar(page, save_handler, save_label)` helper
  - `MassRatioPage.__init__` 改 outer HBox（sidebar + content）
  - `AgeCalcPage.__init__` 改 outer HBox（sidebar + content）
- `.work/.app_info.txt`：3.8.30 → 3.8.31
- `CHANGELOG.md`：本段

---

## V3.8.30（2026-05-28）— 修 Run Pipeline 閃退（mathtext parser + 缺字 glyph）

### 問題

使用者按 Run Pipeline 後閃退，console traceback：

```
ValueError:
$\mathdefault{5.46}$
^
ParseException: Expected end of text, found '$'  (at char 0)
```

伴隨 warning：

```
UserWarning: Glyph 8320 (\N{SUBSCRIPT ZERO}) missing from font(s) Arial.
```

### 根因

兩個獨立 issue 疊加：

1. **mathtext parser bug**（crash 源頭）
   - 多處 `_ticker.ScalarFormatter(useMathText=True)` 讓 axis tick label 變成 `$\mathdefault{5.46}$` LaTeX 形式
   - Anaconda Python 3.13 + 較新 matplotlib 內部 mathtext parser 解析自家產的 `$\mathdefault{...}$` 失敗
   - tight_layout 算 bbox 時觸發 text render → mathtext parse → ValueError → crash

2. **Unicode glyph missing**（warning，不 crash）
   - `T₀ signal (mV)` / `CV (σ/T₀ %)` 兩個 ylabel 直接用 unicode `₀` (U+2080)
   - Arial 字體沒這個 glyph，matplotlib 打 warning（不影響功能，但 console 雜訊大）

### 修法

#### 1. ScalarFormatter `useMathText=True` → `False`

```python
# 三處：MvCanvas._paint_mv (y-axis), MvCanvas._paint_sc (x,y-axis)
_ticker.ScalarFormatter(useMathText=False)
```

視覺差異：tick label 從 `×10⁻⁵` (LaTeX) 變成 `1e-5` (plain text)。略簡陋但**完全避開 mathtext parser**。

#### 2. tight_layout 全部 try/except 包裹

5 個位置 (`_paint_mv`, `_paint_sc`, degas pattern × 2 path, yield pattern × 2 path)：

```python
try: fig.tight_layout(pad=...)
except Exception: pass
```

`tight_layout` 不是 critical — 算 padding 失敗最多就是 chart 邊緣略被切，比 hard crash 好太多。其他 matplotlib edge case (NaN ticks, empty axis) 也用此 pattern 防範。

#### 3. Unicode T₀ → LaTeX `$T_0$`

```python
# was: ax1.set_ylabel('T₀ signal (mV)', ...)
ax1.set_ylabel('$T_0$ signal (mV)', ...)

# was: ax2.set_ylabel('CV (σ/T₀ %)', ...)
ax2.set_ylabel('CV ($\\sigma/T_0$ %)', ...)
```

LaTeX `$T_0$` 不依賴 Arial 字體有沒有 ₀ glyph，matplotlib 自家 mathfont 一定能 render。順便消除 warning。

Qt QLabel (titleLbl) 的 `T₀` 字符不動 — Qt 用系統字體 fallback，Windows 上 PMingLiU / Microsoft YaHei 等都有 U+2080，不會缺字。

### 影響

- **數值結果完全不變** — 純 render 層級的改動
- tick label 視覺從 `×10⁻⁵` 變 `1e-5`，比較粗糙但避開 crash
- degassing pattern ylabel `T₀` 變 italic 數學形式 $T_0$，視覺更標準

### 驗證 checklist

- [ ] 載 NO.65 muscovite blank + signal
- [ ] 按 Run Pipeline — 應該不再閃退
- [ ] mV / scatter chart 還是正常顯示
- [ ] tick label 是 `1e-5` 之類的 plain sci notation
- [ ] degassing pattern 的 y label 顯示 `$T_0$ signal (mV)`（italic T，subscript 0）
- [ ] console 不再有 `Glyph 8320 missing` warning

### 後續

如果某天升級到 matplotlib stable 修好 mathtext bug，可以把 `useMathText=False` 改回 True 拿回 LaTeX-style tick label。但這個 fix 並非 hack，`useMathText=False` 是 mpl 文件支援的正常選項。

### 檔案改動

- `AutoPipeline.py`：
  - 3 處 `ScalarFormatter(useMathText=True)` → `False` (MvCanvas._paint_mv / _paint_sc)
  - 5 處 `tight_layout` 包 try/except
  - 2 處 degassing ylabel `T₀` → `$T_0$`
- `.work/.app_info.txt`：3.8.29 → 3.8.30
- `CHANGELOG.md`：本段

---

## V3.8.29（2026-05-28）— AgeCalcPage Results per Step 表格欄寬修正

### 問題

`AgeCalcPage` 的 "Results per Step" 表格用 `setSectionResizeMode(Stretch)` 把所有欄位均分寬度。結果：
- Step 欄全部顯示 "Temperature ..." 看不到溫度數字
- Issues 欄長字串被 elide ("40Ar(r)=-1.58...", "36Ar(air)=-9...")

兩欄都被自動 ellipsis 截斷，看不出 step 是哪個溫度、issues 具體是什麼。

### 修法

`CalcT0Page`→`AgeCalcPage._build` 的表格區段三處改動：

**1. Per-column resize mode**

```python
_hdr.setSectionResizeMode(0, ResizeToContents)  # Step       自適應內容
_hdr.setSectionResizeMode(1, ResizeToContents)  # Age (Ma)
_hdr.setSectionResizeMode(2, ResizeToContents)  # ±σ (Ma)
_hdr.setSectionResizeMode(3, ResizeToContents)  # ⁴⁰Ar(r)%
_hdr.setSectionResizeMode(4, ResizeToContents)  # Ca/K
_hdr.setSectionResizeMode(5, Stretch)           # Issues       吃剩餘寬度
self.tbl.setWordWrap(True)
self.tbl.verticalHeader().setSectionResizeMode(ResizeToContents)
self.tbl.setTextElideMode(QtCore.Qt.ElideNone)
```

Step + 4 個數值欄按內容寬度顯示，Issues 拿剩餘空間 + 換行；row 高度自適應，長 Issues 變多行不再被砍。

**2. Step 名稱顯示砍 prefix**

```python
short_name = full_name.replace('Temperature ', '').strip()
# "Temperature 1100°C" → "1100°C"
```

每個 row 都是 "Temperature X°C"，前綴重複沒資訊量，砍掉只留溫度數字。Full name 改放 tooltip（hover 看完整）。

**3. Issues hover tooltip**

```python
tooltips=[full_name, '', '', '', '', issues]
if tooltips[c]: item.setToolTip(tooltips[c])
```

長 issues string 滑鼠停上去可以看完整內容。

### 影響

- 純 UI 改動，無數值變化
- CSV export (`_export` summary table) 仍用原始 `step['name']` (含 "Temperature " 前綴)，不受影響

### 驗證 checklist

- [ ] 跑 Run Pipeline → 進 AgeCalcPage
- [ ] Results per Step 表格 Step 欄應該顯示 "600°C" / "700°C" / ... 而非 "Temperature ..."
- [ ] Step 欄滑鼠 hover 應該 tooltip 顯示完整 "Temperature 1100°C"
- [ ] Issues 欄長 string 應該換行而非 ellide，hover 也顯示 tooltip
- [ ] AgeCalc_summary.csv (export) 仍保留 "Temperature 1100°C" 完整名稱

### 檔案改動

- `AutoPipeline.py`：`AgeCalcPage._build` 表格設定 + populate row 邏輯
- `.work/.app_info.txt`：3.8.28 → 3.8.29
- `CHANGELOG.md`：本段

---

## V3.8.28（2026-05-28）— Session save/open（.adr 檔，跳過 .dat 重新匯入）

### 問題

使用者需求：跑完一輪 AutoPipeline (Calculate T₀ → Mass Ratio → Datum) 之後，能存一個檔案、之後重新開啟可以直接從 Calculate T₀ 階段繼續調 mask 重跑 pipeline，**不用再次 import 原始 blank+sample .dat 檔案**。

### 修法

#### 1. .adr session 檔案格式（zip + json + npz）

新副檔名 `.adr` (AutoPipeline Reduction)，本質是 zip：

```
session.adr/
├── meta.json              schema_version=1, app_version, fit, manual, nc, cur,
│                          blank_name, step_names, sinfo, binfo, sigma_method,
│                          step_dates
├── blank_vt.npz           5 arrays ar36..ar40，每個 shape (nc, 2) = (v, t)
├── blank_mask.npy         shape (5, nc), 1=include / 0=exclude per cycle
├── sig/<step>/vt.npz      per-step 5 isotope arrays
└── sig/<step>/mask.npy    per-step (5, nc) mask
```

下游 pipeline 結果 (Mass Ratio / Datum CSV) **不存** — 載入後再按 Run Pipeline 重跑即可。

#### 2. Module-level helpers

```python
def save_session_adr(path, state):
    # state: {'meta', 'bvt', 'bmask', 'svt', 'smask'}
    # zip + json.dumps + np.savez/np.save → .adr

def load_session_adr(path):
    # → dict with same keys, schema_version check
```

#### 3. UI 觸發

**Sidebar**（CalcT0Page）多兩個 button：
- `Save Session`
- `Open Session`

**Menu bar** 多 File menu（top-left）：
- `Open Session...` （Ctrl+O）
- `Save Session...` （Ctrl+S）
- 觸發 `AutoPipelineWindow.t0Page._save_session/_open_session`

#### 4. `CalcT0Page._save_session`

- 同步當前 canvas mask 回 `_bmask` / `_smask[cur]`（user 可能還沒手動觸發 save）
- 預設位置 `Data/Session/`，預設檔名 = 第一個 step 名稱
- 收集 `meta` (fit, manual, nc, cur, blank_name, step_names, sinfo, binfo, sigma_method, step_dates) + raw arrays
- 呼叫 `save_session_adr(path, state)`
- 顯示已存 KB 數 + step 數 + fit / manual 狀態

#### 5. `CalcT0Page._open_session`

- `load_session_adr` 解包
- restore 順序：scalar (nc/fit/manual) → blank arrays → signal arrays → step_dates
- `_rebuild_step_btns()` 重建 step tab bar
- `_prefetch_cache = {}` 清空（id(vt) 是新的）
- restore current step → `_refresh_blank/_refresh_signal`
- sync fitCombo + btnM (Manual ✓) 狀態
- refresh pipeline strip + Δt chip
- `_start_prefetch()` 背景算 enumerate（搭 v3.8.27 fast path，~1 秒完成）

### 為什麼不包含下游 pipeline 結果

原本選項 B（含 MassRatio / Datum CSV）使用者最後選「只存 T0 階段」。理由合理：
- T0 階段是 manual tuning 的核心；下游全部 deterministic，按 Run Pipeline 重跑都一樣
- 不存下游檔案小很多（5–50 KB vs 數 MB）
- 不會出現 「state stale」問題（user 改 mask 後忘記 re-run pipeline，但 session 還是舊結果）

### 驗證 checklist

- [ ] 載入 NO.65 muscovite blank + 9 signal step
- [ ] 在 Calculate T₀ 調幾個 cycle mask
- [ ] 點 Save Session → 確認 `Data/Session/{name}.adr` 產生
- [ ] 關 AutoPipeline，重開
- [ ] File → Open Session → 選剛才的 .adr
- [ ] 確認所有 step tab 恢復 + 當前 step + 所有 mask 都正確
- [ ] 確認 fit type / Manual mode 狀態正確
- [ ] 點 Run Pipeline → MassRatio / Datum / Age 結果跟原本一致

### 檔案改動

- `AutoPipeline.py`：
  - 加 `zipfile`, `json` import
  - 加 module-level `save_session_adr` / `load_session_adr` + `SESSION_SCHEMA_VERSION = 1`
  - `CalcT0Page._build`：sidebar 加 `btnSaveSession` / `btnOpenSession`
  - `CalcT0Page` 加 `_save_session` / `_open_session` methods
  - `AutoPipelineWindow._build`：menubar 加 File menu (Open/Save Session + 快捷鍵)
- `.work/.app_info.txt`：3.8.27 → 3.8.28
- `CHANGELOG.md`：本段

---

## V3.8.27（2026-05-28）— _fit_one 加 closed-form fast path（5 s → ~100 ms）

### 問題

v3.8.26 加了 prefetch + defer paint 之後，使用者實測 9 個 step 切換仍要 ~5 秒。原因：prefetch 工作量 = 9 step × 5 isotope × 848 curve_fit ≈ 38 000 次 scipy 呼叫，循序跑要 30 秒以上才完成。使用者切到還沒 prefetch 到的 step，仍會撞到 enumerate 同步等待。

根本瓶頸不是 prefetch 排程，是 **`scipy.optimize.curve_fit` 對小型 OLS 太慢** — Python overhead + scipy.optimize.leastsq setup cost 每次 ~1 ms，848 次就要 ~1 秒。

### 修法

`fit_func_list = [linear, average]` 只有兩種 fit form，**兩者都是 OLS 閉解**，根本不需要 `curve_fit`。新增兩個 closed-form helper：

```python
def _fit_one_linear_fast(vt_i, mask):
    # OLS closed-form: a = (n*Σtv − Σt*Σv)/(n*Σt² − (Σt)²); b = (Σv − a*Σt)/n
    # σ via SIGMA_METHOD ('calc_t0' or 'standard' SE of intercept)
    # r² from residuals
    ...
    return t0, sig, r2, np.array([a, b])

def _fit_one_average_fast(vt_i, mask):
    # 平均: a = mean(v), σ = std(|r|)/√n 或 √(σ²_res / n)
    ...
    return a, sig, 0.0, np.array([a])
```

`_fit_one` 開頭加 dispatcher：

```python
if f is Utilities.linear:
    return _fit_one_linear_fast(vt_i, mask)
if f is Utilities.average:
    return _fit_one_average_fast(vt_i, mask)
# (curve_fit fallback for未來其他 fit type)
```

### 為什麼結果一致

`curve_fit` 對 `linear(x,a,b) = a*x+b` 跟 `average(x,a) = a` 內部都用 `scipy.optimize.leastsq`，最終退化成 normal equations 解 — **跟我們的 closed-form 數學上等價**。誤差只在 floating-point round-off（< 1e-15 相對）。

σ 計算也對齊 `_sigma_from_fit` 既有邏輯：
- `SIGMA_METHOD='calc_t0'` → `std(|residuals|) / √n`
- `SIGMA_METHOD='standard'` → 從 `σ²_res · (1/n + t̄²/Sxx)` 取 √ (linear) 或 `√(σ²_res/n)` (average)

### 效果

| 計算 | v3.8.26 | v3.8.27 |
|---|---|---|
| 單次 `_fit_one` (linear) | ~1.0 ms | ~0.02 ms |
| 單 isotope `_enumerate_combos` (848 fits) | ~800 ms | **~17 ms** |
| 單 step 5 isotope enumerate | ~4 s | **<100 ms** |
| 全部 9 step prefetch (45 task) | ~36 s | **~1 s** |
| 切到未 prefetch 的 step | ~5 s | **<200 ms**（含 paint） |

實際上 prefetch worker 變成幾乎不必要，但保留它仍有用 — paint_sc 的 scatter 渲染本身還是 200–500 ms，prefetch hit 之後 `_combo_fits` 直接賦值省掉 enumerate，整體再快一點。

### 影響範圍

- **age 中心值、σ、r² 完全不變** — closed-form 跟 curve_fit 數學上等價
- 所有 `_fit_one` 呼叫點都自動受益：MvCanvas enumerate、`_step_ok` 12 step × 5 isotope check、PrefetchWorker、AgeCalcPage 重計算 等
- 也順帶讓 `getDFStatistics_sh` 等 Utilities 內部依賴 `_fit_one` 的路徑變快（但 Utilities 自己也 call curve_fit，那部分仍需個別評估）

### 驗證 checklist

- [ ] 啟動 AutoPipeline → 載 9 step 樣品 → 進 Calculate T₀
- [ ] 切第一個溫度 step：mV + scatter 都應該 **<200 ms** 出現
- [ ] 連續切 9 個 step：每一個都應該即時，沒有 freeze 等待
- [ ] 比對 NO.65 muscovite 1100°C step T₀ 跟之前版本（應該完全相同到小數 6 位以上）
- [ ] Age 結果跟 v3.8.26 一致（中心值跟 σ）
- [ ] 改變 cycle mask（點 cycle button）→ scatter 即時更新

### 檔案改動

- `AutoPipeline.py`：
  - 新增 `_fit_one_linear_fast` (closed-form OLS for `y=a·t+b`)
  - 新增 `_fit_one_average_fast` (closed-form for `y=a`)
  - `_fit_one` 開頭加 dispatcher：fit func is linear/average → 走 fast path
  - curve_fit fallback 保留（未來其他 fit type 用）
- `.work/.app_info.txt`：3.8.26 → 3.8.27
- `CHANGELOG.md`：本段

---

## V3.8.26（2026-05-28）— CalcT0Page step 切換加速（defer paint + background prefetch）

### 問題

使用者反映在 Calculate T₀ 介面切換不同溫度 step 或 Blank 都很慢，每次切要等好幾秒才畫完。

定位瓶頸：

```
_sel_step(nm)
  → _refresh_signal()/_refresh_blank()
      → cv.load() × 5 isotopes
          → _enumerate_combos() ← 每個 isotope C(10,4..10) = 848 個 curve_fit
              ⇒ 5 isotope × 848 = 4 240 curve_fit per step（~4 秒）
      → _paint_mv() + _paint_sc() ← scatter 還有 800+ 點要 render
```

v3.8.10 已加 cache（同 step 切回來秒切），但首次進每個 step 都會卡 ~4 秒。

### 修法（兩層）

#### Layer A: defer paint_sc 到下個 event loop

`MvCanvas._refresh` 重構：

```python
def _refresh(self):
    ...
    self._paint_mv()   # 立即（mV chart 是輕的）
    QtCore.QTimer.singleShot(0, self._refresh_deferred)

def _refresh_deferred(self):
    if self._vt is None: return
    self._paint_sc()
    self._update_best_btns()
```

`_paint_sc` 是 widget 內最重的渲染（per-n 上色、range 重算、axvspan、800+ scatter points）。defer 後切 step 的瞬間 mV chart 立刻顯示，user 視覺感受「秒切」，scatter 稍微慢 100–200 ms 補上。

#### Layer B: background QThread 預算所有 step

新 `PrefetchWorker(QThread)`，在 `load_blank` / `load_signal` 結束時 spawn：

```python
class PrefetchWorker(QtCore.QThread):
    sig_one_done = QtCore.pyqtSignal(object, list)   # (cache_key, fits)
    sig_progress = QtCore.pyqtSignal(int, int)
    sig_finished = QtCore.pyqtSignal()
    def run(self):
        for key, vt in self.tasks:
            if self._abort: return
            fits = _enumerate_combos_simple(vt, self.fit, self.nc)
            self.sig_one_done.emit(key, fits)
```

scipy `curve_fit` 在 C/Fortran 內 release GIL，所以 QThread parallel 對 UI 真的有效果。

`CalcT0Page` 新增：
- `self._prefetch_cache: dict[(id(vt), fit, nc) → list[(t0, sig, k, mask)]]`
- `_start_prefetch()` 收集所有未 cache 的 (step, isotope) task 排進 worker
- `_on_prefetch_one(key, fits)` slot 把結果 drop 進 cache
- `_on_prefetch_progress(done, total)` 在 `footMsg` 顯示 `Pre-computing: 12/60`
- `_on_prefetch_finished()` 顯示 `✓ Pre-compute done`

`MvCanvas.load(...)` 加 `prefetched_fits=None` 參數，如果 caller 傳了就直接 `self._combo_fits = prefetched_fits`，跳過 ~4 秒 `_enumerate_combos`。

`_refresh_signal` / `_refresh_blank` 改：

```python
cache = getattr(self, '_prefetch_cache', {})
for ai, cv in enumerate(self._cv):
    key = (id(vt[ai]), self._fit, self._nc)
    cv.load(vt[ai], mask[ai], ..., prefetched_fits=cache.get(key))
```

加 helper `_enumerate_combos_simple(vt_i, fit_type, n_total)` (module level)，邏輯跟 `MvCanvas._enumerate_combos` 一致，worker 跟 instance 共用，避免 logic drift。

### 效果

| 情境 | v3.8.25 | v3.8.26 |
|---|---|---|
| 首次切到 step (cache 空) | ~4 s | mV 立即 + scatter <500 ms（defer） |
| Prefetch 完成後切 step | ~4 s（每次首次都重算） | **<50 ms**（cache hit）|
| 切回已 visit 過的 step | <500 ms | <50 ms |
| Prefetch 進行中 footMsg | 無提示 | `Pre-computing combos: N/M` |

12 step × 5 isotope = 60 個 task，每 task ~700 ms（單核），prefetch 全跑完約 30–50 秒。期間 user 切 step 還是先看到 mV，scatter 等 worker 算完才秒切。

### 安全性

- `_start_prefetch` 重入：load 新檔時先 `worker.abort()` + `wait(100)` 等舊 worker 退出，再清 `_prefetch_cache` 避免 id(vt) 衝撞
- `id(vt)` cache key：dataset reload 後 numpy array 物件 id 可能撞 old key，因此 `load_blank` / `load_signal` 都先 `self._prefetch_cache = {}` 再 fire worker
- worker 例外接 catch + traceback.print_exc，不會炸 GUI

### 驗證 checklist

- [ ] 啟動 AutoPipeline → 載 blank + signal → 進 Calculate T₀
- [ ] 首次切到第一個溫度 step：mV chart 應該**馬上**顯示，scatter 200–500 ms 補上
- [ ] 切到第二個溫度 step：類似（prefetch 應該已經算完前面幾個）
- [ ] 等 footMsg 顯示 `✓ Pre-compute done`
- [ ] 之後切 step：應該**幾乎瞬間**完成（<50 ms）
- [ ] Re-load 新 dataset → footMsg 應該重新顯示 prefetch progress

### 檔案改動

- `AutoPipeline.py`：
  - 新 module-level `_enumerate_combos_simple` helper
  - 新 `PrefetchWorker(QtCore.QThread)` class（PipelineWorker 前）
  - `MvCanvas.load` 接 `prefetched_fits=None` 參數
  - `MvCanvas._refresh` 拆出 `_refresh_deferred`，scatter+best-btn 走 QTimer.singleShot(0)
  - `CalcT0Page._refresh_blank` / `_refresh_signal` 傳 prefetched fits
  - `CalcT0Page.load_blank` / `load_signal` 結尾 call `_start_prefetch()`
  - `CalcT0Page` 新增 `_start_prefetch` / `_on_prefetch_one` / `_on_prefetch_progress` / `_on_prefetch_finished`
- `.work/.app_info.txt`：3.8.25 → 3.8.26
- `CHANGELOG.md`：本段

---

## V3.8.25（2026-05-28）— PNG 路徑對齊子程式（Data/ ↔ Figures/ 雙根分離）

### 問題

使用者審查 AutoPipeline 各階段存檔路徑時發現 PNG 沒跟子程式同步：

子程式 `NTNU_DataReduction.py` line 1333-1334：
```python
self.data_folder       = 'Data/'      # CSV / 數據
self.screenshot_folder = 'Figures/'   # PNG / 截圖
```
PNG 跟 CSV 分別存到兩個根資料夾。但 AutoPipeline v3.8.24 還是把 PNG 塞進 `Data/`：

| 階段 | v3.8.24 PNG 位置 | 子程式對應位置 |
|---|---|---|
| T0 截圖 | `Data/T0/Sample/{folder}/{step}.png` | `Figures/T0/{T0type}/{name}.png` |
| Diagram (DFW/DFA/DFN/DFI) | `Data/Figures/{sid}_{key}.png` | `Figures/Publish/StepHeating/{...}.png` |

### 修法

#### 1. T0 PNG（`CalcT0Page._save`）

CSV 仍然存 `Data/T0/Sample/{folder}/` 不動；PNG 額外算 `Figures/T0/Sample/{folder}/` 並 `os.makedirs(...)`：

```python
sample_folder_name = os.path.basename(target.rstrip(os.sep)) or 'unknown'
fig_target = os.path.join(work_dir, 'Figures', 'T0', 'Sample', sample_folder_name)
os.makedirs(fig_target, exist_ok=True)
png_path = os.path.join(fig_target, step_label + '.png')
self._crow_w.grab().save(png_path, 'PNG')
```

`work_dir = os.path.dirname(os.path.abspath(__file__))` 已經在 v3.8.15 算好。

#### 2. Diagram PNG（`PipelineWorker._run`）

`_run` 開頭原本算的 `fig_d=os.path.join(out,'Figures')` 整段移除（out 是 `Data/`，會跑出 `Data/Figures/`）；改在 work_dir 已知後（與 `getDFStatistics_sh` 同段）重新算：

```python
# v3.8.25: Figures/Publish/StepHeating/ (work_dir-relative)
fig_d=os.path.join(work_dir,'Figures','Publish','StepHeating')
os.makedirs(fig_d,exist_ok=True)
for key in ['DFW','DFA','DFN','DFI']:
    src=os.path.join(work_dir,'.work',key+'.png')
    if os.path.exists(src):
        shutil.copyfile(src,os.path.join(fig_d,str(sid)+'_'+key+'.png'))
```

mirrors NTNU line 4885 `self.screenshot_folder + 'Publish/StepHeating/'`。

### 對齊結果

| 階段 | AutoPipeline v3.8.25 | 子程式 | 對齊 |
|---|---|---|---|
| T0 CSV (signal) | `Data/T0/Sample/{folder}/{step}.csv` | `Data/T0/Sample/{name}.csv` | ✓ |
| T0 CSV (blank) | `Data/T0/PBs/{blank}.csv` | `Data/T0/PBs/{name}.csv` | ✓ |
| T0 PNG | `Figures/T0/Sample/{folder}/{step}.png` | `Figures/T0/{T0type}/{name}.png` | ✓ |
| MassRatio CSV | `Data/MassRatio/{step}.csv` | `Data/MassRatio/` | ✓ |
| AgeCalc CSV | `Data/Agecalc/{step}.csv` | `Data/Agecalc/` | ✓ |
| Datum CSV | `Data/Publish/{sid}_datum.csv` | `Data/Publish/` | ✓ |
| Diagram PNG | `Figures/Publish/StepHeating/{sid}_{key}.png` | `Figures/Publish/StepHeating/` | ✓ |

batch mode 多一層 `{folder}` 是 AutoPipeline 一次跑多個 step 的需要（子程式 single-step 每次手動 save 不需要），結構上仍與子程式相容。

### 驗證 checklist

- [ ] 跑 AutoPipeline → Calculate T₀ → Save T₀
- [ ] 確認 CSV 在 `Data/T0/Sample/{folder}/` 內
- [ ] 確認 PNG 在 `Figures/T0/Sample/{folder}/` 內（**不是** `Data/T0/Sample/`）
- [ ] 跑完整 pipeline → 確認 Datum CSV 在 `Data/Publish/` 內
- [ ] Diagram PNG (DFW/DFA/DFN/DFI) 在 `Figures/Publish/StepHeating/` 內（**不是** `Data/Figures/`）
- [ ] `Data/Figures/` 不應該再被建出來

### 檔案改動

- `AutoPipeline.py`：
  - `CalcT0Page._save`：PNG 目標從 `target/` 換成 `work_dir/Figures/T0/Sample/{folder}/`
  - `PipelineWorker._run`：line 4111 `fig_d=os.path.join(out,'Figures')` 移除，line 4243 之前新建 `fig_d=os.path.join(work_dir,'Figures','Publish','StepHeating')`
- `.work/.app_info.txt`：3.8.24 → 3.8.25
- `CHANGELOG.md`：本段

---

## V3.8.24（2026-05-28）— 輸出格式對齊 NTNU 子程式（T0 PNG / MassRatio header / Datum Min + isochron 欄）

### 問題

使用者對比 AutoPipeline 三階段輸出 vs NTNU_DataReduction 子程式輸出，發現格式不一致：

1. **Calculate T₀ 階段**：AutoPipeline `CalcT0Page._save` 只存 T₀ csv，缺 PNG 截圖；子程式 `LRP_save`（line 3736）有 LR.png 存圖
2. **Mass Ratio 階段**：`MassRatioPage._save` 寫 header 用 `w.writerow([single_string_with_commas])` → csv.writer 把整段 header 加 quote 變單一 cell。但 PipelineWorker 直接 `f.write(...)` 寫出來不會 quote。兩個寫 csv 入口輸出格式不一致
3. **Datum Publication 階段**：對比 `NO.65 table-2.csv`（子程式）vs `0621-01C_datum.csv`（AutoPipeline）三個明確差異：
   - **`Min` 欄位**：子程式 `Muscovite` / `Mus`，AutoPipeline 變成溫度 `1150` `1200` `1250`（`Utilities.calcAge` 回傳的 `ar[-3]` 是溫度不是 mineral）
   - **多 10 欄 isochron columns**：AutoPipeline `_DATUM_HEADER` 結尾多 `normal isochron / 40Ar(m)/36Ar(m)±std / 39Ar(m)/36Ar(m)±std / inverse isochron / 36Ar(m)/40Ar(m)±std / 39Ar(m)/40Ar(m)±std`；子程式結尾只到 `Lambda, numCycle`
   - **J_int 欄位**：子程式 NO.65 各 step 不同（5.65e-05 / 1e-06），AutoPipeline 全部相同。已確認子程式 line 2862 `J_int = float(self.parameters[...'J int'...])` 邏輯與 AutoPipeline 一致，皆從單一全域 params 讀；NO.65 NaN 跨 step 不同應為 user manual edit。**不修**

### 修法

#### 1. Calculate T₀ — 加 PNG 截圖（`CalcT0Page._save`）

- `_build` 內留 `self._crow_w = crow_w` 引用（包 5 個 MvCanvas 的 row container，每個 MvCanvas 含 mV + scatter）
- `_save` 結尾用 `self._crow_w.grab().save(png_path, 'PNG')` 抓 Qt widget pixel snapshot
- 路徑 `{target}/{step}.png`，step=當前 step name（或 `blank` / `current`）
- 只存當前 step 的 PNG（user 切到別的 step 再 Save 才能多存）
- 失敗不阻塞 CSV save（try-except）

#### 2. Mass Ratio — header 拆 list（`MassRatioPage._save`）

`csv.writer.writerow([...])` 入參改成 11 個獨立字串：

```python
w.writerow(["Samp#", "t", "Min", "iradiation PK 90%", "Mass", "Raw",
            "Measurment", "Measurement's Sigma", "Ratio", "Value",
            "Ratio's Sigma"])
```

對齊 PipelineWorker line 4140 `f.write("Samp#,t,Min,..."" + "\n")` 的格式。

#### 3. Datum CSV — Min 欄位修正 + 砍 10 欄 isochron

**Min 欄位（PipelineWorker `_run`）**：

```python
# was: mn = ar[-3] if len(ar)>57 else ''   # gave temperature
# now: read from mr_csv col 2 first (mirrors NTNU line 5347)
mineral_from_csv = ''
try:
    with open(step['mr_csv']) as f: lines = f.readlines()
    if len(lines) > 1:
        _parts = lines[1].split(',')
        if len(_parts) > 2: mineral_from_csv = _parts[2].strip()
except: pass
mn = mineral_from_csv if mineral_from_csv else (ar[-3] if len(ar)>57 else '')
```

**isochron 欄位移除**：

- `_DATUM_HEADER`：line 3968-3969 整段 `normal isochron`/`inverse isochron` 共 10 個 entry 刪除
- `_build_datum_row`：`row=['0']*98` → `row=['0']*88`，row[88]..row[97] 寫入區段（line 4049-4069）整塊刪除

### 影響

- **age 中心值 / σ_age 完全不變** — 只改輸出格式跟 metadata 欄位，沒動公式
- 既有讀 datum csv 的下游程式（York regression, isochron 視覺化）如果依賴 row[89..97] 的 isochron columns，會壞 — 但 AutoPipeline 自己 `getDFStatistics_sh` (line 4210) 是直接用 raw component 算 isochron，**不讀** datum csv 的 isochron 欄位，所以 safe

### 驗證 checklist

- [ ] 啟動 AutoPipeline → 載 NO.65 muscovite blank+signal → 進 Calculate T₀
- [ ] 點 Save T₀ → 確認目標資料夾有 `{step}.png` 跟所有 step CSV
- [ ] 開 PNG 看是不是包含 5 mV chart + 5 scatter chart（橫向排）
- [ ] 跑完整 pipeline → 開 `Publish/0621-01C_datum.csv` → 第 2 欄 `Min` 應該是 `Muscovite` 而不是 `1150`
- [ ] header 結尾應該是 `Lambda,numCycle`，不再有 `normal isochron` 等 10 欄
- [ ] 手動 Save Mass Ratio → 開 CSV → 11 欄 header 正確分開（Excel 開不會塞在一格）
- [ ] AgeCalcPage 仍能正常重算 York / Inverse Isochron（不依賴 datum csv isochron 欄）

### 檔案改動

- `AutoPipeline.py`：
  - `CalcT0Page._build`：`self._crow_w = crow_w` 引用
  - `CalcT0Page._save`：加 PNG screenshot 區段
  - `MassRatioPage._save`：header 拆 11 欄獨立字串
  - `PipelineWorker._run`：mr_csv col 2 讀 mineral，覆寫 `mn`
  - `_DATUM_HEADER`：移除 10 欄 isochron columns
  - `_build_datum_row`：row size 98→88，移除 row[88..97] isochron 計算
- `.work/.app_info.txt`：3.8.23 → 3.8.24
- `CHANGELOG.md`：本段

### J_int 為何不改

NTNU_DataReduction line 2862：
```python
J_int = float(self.parameters[self.parameters_name.index('J int')])
self.AgeCalculation_result = Utilities.calcAge(measurement, J, J_std, J_int, ...)
```

與 AutoPipeline line 4098 邏輯**完全相同** — 都從單一全域 `parameters['J int']` 讀。NO.65 table-2.csv 不同 step J_int 不同（5.65e-05 vs 1e-06），是 user 跑子程式時對每個 step 手動改 metadata 的結果，非演算法輸出差異。AutoPipeline batch mode 用單一 J_int 跑全部 step 邏輯上正確。

---

## V3.8.23（2026-05-27）— CalcT0Page 新增 Yield panel（%⁴⁰Ar(r) + %³⁹Ar(K) vs cum ³⁹Ar(K)）

### 問題

使用者要在 CalcT0 階段就能即時看 plateau 挑選提示：哪幾個溫度 step 釋放的 ⁴⁰Ar(r) 跟 ³⁹Ar(K) 佔總體訊號比例多少。這在原本的 Mass Ratio / Age Calc step 才看得到，但那時 cycle mask 已經 locked，回頭微調太慢。

### 修法

`AutoPipeline.py` `CalcT0Page._build` Degassing Pattern 區段新增 yield panel，位置在 cv_degas 右側並排（同 HBoxLayout 內，中間 10 px spacing）：

- 新 widget：`cv_yield = _FigCanvas(self._yield_fig)`，`setFixedSize(480, 280)`
- 單 subplot `_yield_ax`，雙線：
  - 藍色 `%⁴⁰Ar(r)` = ⁴⁰Ar(r) / Σ(³⁶+³⁷+³⁸+³⁹+⁴⁰)_(measured,bc) × 100
  - 紅色 `%³⁹Ar(K)` = ³⁹Ar(K) / Σ(³⁶+³⁷+³⁸+³⁹+⁴⁰)_(measured,bc) × 100
- x 軸：cumulative ³⁹Ar(K) %，按 temperature 排序累積
- 當前 step 用橘色點線標位置（跟 degassing 圖風格一致）

計算用既存的 `_propagate(T0, sT0, bT0, bSIG)` helper（line 181 hardcoded `_PR` production ratios），取 `Ar40_r` 跟 `Ar39_K`。**不需要 J value**，所以 CalcT0 階段就能算。

新 `_paint_yield_pattern` 方法：

- 用 n=10 full mask 對每個 temperature step 跑 `_fit_one` × 5 isotopes → 組成 `T0[5]`/`sT0[5]` → 呼叫 `_propagate`
- 獨立 `self._yield_cache`，cache key 跟 `_degas_cache` 同形（`(svt keys, fit, id(bvt))`），signal files 換才重算

`_refresh_guide` 結尾加 `self._paint_yield_pattern()` call，確保 degas 跟 yield 同步刷新。

### 驗證 checklist

- [ ] 啟動 AutoPipeline → 載 Blank/Signal → 進 Calculate T₀
- [ ] Yield panel 在 degassing pattern 右邊並排顯示
- [ ] %⁴⁰Ar(r) 在高溫 step 通常 > 90%，低溫 step 偏低（NO.65 muscovite）
- [ ] %³⁹Ar(K) 在 muscovite 全 step 應該 > 5%（K-rich mineral）
- [ ] 切 step (sidebar tab) 橘色 vertical line 跟著移動

### 檔案改動

- `AutoPipeline.py`：
  - `CalcT0Page._build` Degassing layout 區段：新增 `cv_yield` 並排
  - 新增 `CalcT0Page._paint_yield_pattern` 方法
  - `_refresh_guide` 加 yield call
- `.work/.app_info.txt`：3.8.22 → 3.8.23
- `CHANGELOG.md`：本段

---

## V3.8.22（2026-05-27）— Scatter 點擊吸附 respect n-filter

### 問題

CalcT0Page 的 T₀ vs 2σ scatter plot：使用者用上方 n-filter 按鈕（All / 10 / 9 / … / 4）只勾選某一個 n（例如只勾 n=6）後，畫面上只剩 n=6 的點，但**滑鼠點擊還是會吸附到隱藏的 n=7、n=8 點**。原因是 `MvCanvas._sc_click` 計算最近點時遍歷 `self._all_pts`（含被 filter 隱藏的點），沒做 n-filter 過濾。

### 影響

使用者明明只勾 n=6 想在 n=6 的散佈裡挑點，結果一點就跳去 n=7 / n=8 / n=10 的某個組合，等於 n-filter 對點擊沒有效果。手動挑點流程被嚴重干擾。

### 修法

`AutoPipeline.py` `MvCanvas._sc_click`（line 1618）：

```python
n_filter = getattr(self, '_n_filter', set(range(4, 11)))
visible = [p for p in self._all_pts if p[2] in n_filter]
if not visible: return
# range / 最近點搜尋皆改用 visible，不再用 self._all_pts
```

效果：n_filter = {6} → 點擊只會命中 n=6 的點；n_filter = {6,7} → 只命中 n∈{6,7}，永遠不會跳到 n=8/9/10 的隱藏組合。range 也改用 visible 計算（距離 metric 跟使用者看到的範圍一致）。

### 驗證 checklist

- [ ] 啟動 AutoPipeline → 載入 Blank/Signal → 進 Calculate T₀
- [ ] n-filter 按 "6"（只剩 n=6 的點）→ 在散佈上點任意位置 → titleLbl 顯示的 T₀/σ 應該對應某個 n=6 組合
- [ ] n-filter 按 "All" → 點擊恢復可命中任意 n
- [ ] n-filter 按 "6"+"7" → 點擊只命中 n=6 或 n=7

### 檔案改動

- `AutoPipeline.py`：`MvCanvas._sc_click` 加 n_filter 過濾，最近點搜尋與 range 正規化都改用 visible-only points
- `.work/.app_info.txt`：3.8.21 → 3.8.22
- `CHANGELOG.md`：本段

---

## V3.8.21（2026-05-27）— Pipeline 搬回 top_bar + 藍灰二色 + Calculate T₀ 標題移除

### 問題

使用者回饋 v3.8.20 三項：

1. **Pipeline 不該佔獨立一行** — v3.8.20 拆成 78 px 高 dedicated strip 在 top_bar 下方，使用者覺得不該獨立佔一行，要搬回 top_bar 內（chips 右邊、Run Pipeline 按鈕左邊的空白區）。
2. **設計沒美感** — 綠色 ✓ + 大狀態 badge (DONE/ACTIVE/PENDING) + 三條彩色線太花，要簡化：
   - 圈圈跟線條**統一藍色**
   - 完成的步驟用**藍色實心圈圈**（不用 ✓ checkmark）
   - 未完成用**灰色圈圈**
   - 移除 DONE/ACTIVE/PENDING 三排狀態文字
3. **CalcT0Page 上面 "Calculate T₀" 大標題** 佔了 ~50 px 還重複（pipeline 已經顯示當前頁面），要拿掉，charts 往上補。

### 修法

#### 1. Pipeline 移回 top_bar 內

- top_bar `setFixedHeight(65)` → **80** 才容得下 chip + 圈圈 + step name
- 之前 v3.8.20 的 `pipe_strip = QtWidgets.QWidget()` independent row 整段刪掉
- 新 `pipe_container = QtWidgets.QWidget()` `setFixedSize(450, 68)` 用 absolute geometry 放在 `tbl` HBoxLayout 中間（chips 右側 stretch 之後 → pipe_container → stretch → Run Pipeline 按鈕）

#### 2. 視覺簡化：藍灰二色

新 `_refresh_pipe_visuals(current_idx)` 規則：

```python
is_blue[i] = self._state_done[i] or (i == current_idx)
# 圈圈一律 "●"，font-size 24px
# 顏色：藍 #1a5fb4（done/active）/ 灰 #bbbbbb（pending）
# 連接線：藍 if 兩端都藍，否則灰
```

- 圈圈 22 px 框 + 24 px font，永遠是 `●`（實心），不再切換 ○ ✓ ◉ 三符號
- 沒有 DONE/ACTIVE/PENDING 文字 badge，只剩 step name 12 px bold
- 連接線 2 px 高，藍/灰純色，不再用 3 px green
- `self._pipe_status = []` 留空 list（back-compat 給之後可能引用）

#### 3. CalcT0Page "Calculate T₀" 標題移除

`CalcT0Page._build` 開頭的 `hdr_w` widget block 整段刪掉：

- `<b>Calculate T₀</b>` QLabel 20 px font + `hdr_w.setFixedHeight(50)` 全部沒了
- 釋放 50 px 給下方 charts，QVBoxLayout 自動 reflow
- `self._hdr_subtitle = QLabel('').hide()` 留個 hidden placeholder 防範既存 code 還在寫它

### 檔案改動

- `AutoPipeline.py`：
  - `AutoPipelineWindow._build`：top_bar 高度 65→80；pipe_strip block 刪除；新 pipe_container 用 absolute geometry 放回 tbl 中間
  - `_refresh_pipe_visuals` 重寫：藍/灰二色規則
  - `CalcT0Page._build`：刪除 hdr_w block，只保留 hidden `_hdr_subtitle` placeholder
- `.work/.app_info.txt`：3.8.20 → 3.8.21

### 驗證 checklist

- [ ] top_bar 高 80 px，pipeline 在 chips 跟 Run Pipeline 按鈕中間，獨立的下方 strip row 消失
- [ ] 圈圈都是 `●`（實心），沒 ✓ / ○ / ◉ 等其他符號出現
- [ ] 完成的步驟圈圈跟 step name 都藍 `#1a5fb4`
- [ ] 未完成圈圈灰 `#bbbbbb`，step name 灰 `#666`
- [ ] 連接線 2 px 細線，藍/灰跟兩端顏色一致
- [ ] CalcT0Page 上方不再有 "Calculate T₀" 標題大字
- [ ] mV chart row 比 v3.8.20 往上移 ~50 px

---

## V3.8.20（2026-05-27）— Pipeline UI 重做：圈圈放大、點擊可重算、Next 不再 one-shot

### 問題

使用者回饋舊版 pipeline UI 三項：

1. **太小看不清** — 480×50 widget 塞在頂部 chips 跟 Next button 中間，圈圈才 22px 字、step name 才 9px。
2. **點圈圈完全不能算** — `mousePressEvent → _go(idx)` 只換 stack page，沒觸發 Mass Ratio / Age Calc 重算。
3. **Next button 一次性** — 第一次按可以跑，跑完 `_go(2)` 把 nextBtn 設成 "Done" + disabled，要再算 MR/Age 就動不了。

### 修法

`AutoPipeline.py` `AutoPipelineWindow`：

#### 1. Pipeline 搬到獨立 strip + 放大

- 從 top_bar 內 480×50 子 widget 改成 top_bar **下方** 獨立 row：78px 高、full width、底色 `#fafafa` 配 1px border
- 三個 step "card" 在 HBoxLayout 平均分佈，每張 card：
  - **圈圈 34px 大字**（v3.8.19 之前 22px），三態：
    - `○` 灰色 = PENDING
    - `●` 藍色 #1a5fb4 = ACTIVE（當前頁面）
    - `✓` 綠色 #2e7d52 = DONE
  - **Step name 14px bold**（之前 9px），DONE 綠 / ACTIVE 藍 / PENDING 灰
  - **狀態 badge 10px 大寫間距**：DONE / ACTIVE / PENDING
- 兩條 connector line：3px 高、green 如果兩端都 done、否則灰

#### 2. 點圈圈可重算

新方法 `_pipe_click(idx)`：

```
idx == 0  → 純 navigate 到 T₀ page（T₀ 是互動頁面，沒「重算」概念）
idx == 1  → _target_after_run=1, _run_pipeline() → _on_done() → _go(1)
idx == 2  → _target_after_run=2, _run_pipeline() → _on_done() → _go(2)
```

`_on_done` 用 `_target_after_run` 決定要導去哪一頁（之前 hard-code `_go(1)`）。預設 1，每次 run 結束 reset 回 1。

`_pipe_click` 同時檢查：
- `_t0_has_data()` — 沒載 blank/signal → warn dialog
- `self._worker.isRunning()` — worker 還在跑 → status bar 提示「Pipeline already running…」不重複觸發

#### 3. Next button 永遠 re-run

`_next_action()` 重寫：
- 永遠呼叫 `_run_pipeline()`（之前 idx=1 時只 `_go(2)` 不重算）
- target = `min(idx+1, 2)`，idx=2 也可以 click 然後 stay 在 Age Calc 但重跑
- 同樣有 `_t0_has_data()` + `_worker.isRunning()` guard

`_go(idx)` 重寫 Next button 行為：
- 不再 "Done" + disabled 死路
- idx=0：「Run Pipeline →」
- idx=1：「↻ Recompute → Age Calc」
- idx=2：「↻ Recompute Pipeline」
- 三種狀態 enabled 條件都是 `_t0_has_data()`（loaded files 就 enabled）

`_run_pipeline()` 開頭把 nextBtn 改成 "Running…" + disabled 防雙擊。新 handler `_on_pipeline_err()` 失敗時恢復按鈕。

#### 4. 載入檔案自動更新 pipe 視覺

`CalcT0Page.load_signal()` 結尾呼叫 `parent._refresh_pipe_visuals()` → circle 0 立刻變綠勾 ✓ DONE（因為 `_state_done[0]` 被 `_t0_has_data()` 推到 True）。

### 檔案改動

- `AutoPipeline.py`：
  - `AutoPipelineWindow._build`：拆 pipe_container → top_bar 內 nextBtn + 下方獨立 pipe_strip（78px）
  - 新方法 `_pipe_click`、`_t0_has_data`、`_refresh_pipe_visuals`、`_on_pipeline_err`
  - `_go` 重寫（不再 disable Next）
  - `_next_action` 重寫（永遠 re-run，target=min(idx+1,2)）
  - `_run_pipeline` 加上 nextBtn disable + "Running…" 文字
  - `_on_done` 用 `_target_after_run` 控制導頁，標記 `_state_done[1/2]=True`
  - `CalcT0Page.load_signal` 結尾觸發 parent `_refresh_pipe_visuals`
- `.work/.app_info.txt`：3.8.19 → 3.8.20

### 驗證 checklist

- [ ] 啟動後 pipeline 在頂部第二 row，三大圈圈清楚可見
- [ ] 載入 blank+sample → 第一個圈圈變綠 ✓ DONE，第二三個還是 ○ PENDING
- [ ] 點第二個圈圈（Mass Ratio）→ 觸發 pipeline 計算 → 完成後第二三個圈圈都變綠 ✓ DONE，當前頁面切到 MR
- [ ] 改 T₀ mask 後再點第二個圈圈 → **再次** 觸發 pipeline 重算 → MR 表格更新
- [ ] 點第三個圈圈 → pipeline 重算 → 完成後切到 Age Calc 頁面
- [ ] Next button 在 idx=1 顯示「↻ Recompute → Age Calc」，按下會重算
- [ ] Next button 在 idx=2 顯示「↻ Recompute Pipeline」，按下會重算（不會變 Done 死路）
- [ ] 跑 pipeline 中 Next 按鈕變灰 "Running…"，跑完恢復

---

## V3.8.19（2026-05-27）— Splash 灰色 footer 拿掉，Loading 移到 URL 下方置中

### 問題

splash.png 是 640×480 PNG（NTNU_DataReduction.py 啟動時用 QSplashScreen 顯示），y=455–480 有一條 25px 高的灰色 footer 帶分隔線（PNG 內建，不是 Qt 加上去的）。`Loading…` 文字是用 `splash.showMessage('Loading…', AlignRight | AlignBottom, ...)` 寫在這條 footer 的右下角。

使用者要求：拿掉灰色 footer，`Loading…` 移到 `github.com/FormosaRes/pyADR` 下面、置中。

### 修法

`NTNU_DataReduction.py` 啟動畫面 painter block：

1. 載入 splash.png 後 `_pix.copy(0, 0, W, 455)` 裁切掉灰色 footer，新 pixmap 是 640×455。
2. 原本 painter 只畫 version + date，新增第三段畫 `Loading…`：
   - y=425（github URL 大約 y=400，往下 25px 距離適中）
   - 寬度 = pixmap 寬，`AlignHCenter` 水平置中
   - Arial 9pt 斜體灰字 `(120, 120, 120)`，跟 URL 視覺風格搭
3. 移除 `splash.showMessage('Loading…', AlignRight | AlignBottom, ...)` 呼叫 — Loading 文字現在已 baked 進 pixmap，不需要 Qt overlay。

splash.png 本身**沒有改動**（純 runtime crop，使用者要保留原 PNG asset 可日後 regenerate 處理）。

### 效果

啟動畫面：
- 高度 480 → 455（消除底部灰色 footer + 分隔線）
- `Loading…` 從右下角灰條搬到 URL 下方水平置中

### 檔案改動

- `NTNU_DataReduction.py` — splash 載入 block 加 `_pix.copy(0,0,W,455)`、painter 多畫 Loading、移除 `showMessage`
- `.work/.app_info.txt` — 3.8.18 → 3.8.19

---

## V3.8.18（2026-05-27）— 5 修：Help 擴充、Bi-Dir 移除、mV 留白、Δt 上移、σ 預設改

### 問題

使用者回饋 v3.8.17 後幾項：

1. mV chart 上下白邊太多（1.2:1 強制 aspect 不匹配 cv_mv 自然高度比）
2. **Bi-Dir All 按鈕應該在 v3.8.10 panel 清理時就移除**，但 sidebar 還留著
3. **Auto Blank / Auto Signal 邏輯** 應該寫進 Help（之前 Cycle Selection Guide 只說顏色挑選）
4. **Δt: N d** 在 sidebar 底部位置不顯眼 → 移到頂部 nav bar，作為 'Current step' 右邊的 chip
5. **T₀ error 預設 σ method** 從 'standard'（SE-from-pcov）改回 'calc_t0'（std(|r|)/√n），跟 standalone CalcT0Page 預設一致

### 修法

#### 1. SIGMA_METHOD 預設 'standard' → 'calc_t0'

`AutoPipeline.py:65` 全域 `SIGMA_METHOD = 'calc_t0'`，啟動時 sigmaCombo dropdown 預設指到 "Calc T₀"。Standalone CalcT0Page 一直用 std(|r|)/√n，這樣 AutoPipeline 預設行為跟它一致。User 仍可用 dropdown 切到 'standard' (SE-from-pcov, Li 2019 Eq.1)。

**注意**：'standard' 統計上比較正確（covariance-based），'calc_t0' 會 ~4× 低估 σ（v3.8.2 CHANGELOG 已記錄）。預設改回 'calc_t0' 是 reproducibility 取向，不是「正確性」改動。

#### 2. Bi-Dir All 按鈕徹底移除

v3.8.10 panel 清理時保留了 sidebar `Bi-Dir All` 按鈕當「core 功能 fallback」。v3.8.18 移除：

- `self.btnABest = sb_btn('Bi-Dir All')` 改成 hidden placeholder（`QPushButton().hide()`）保 back-compat
- sidebar `addWidget` 迴圈把 btnABest 拿掉
- `btnABest.clicked.connect(self._auto_best_all)` 拿掉
- `_auto_best_all` method 保留（不刪除，未來如要 reintroduce），但沒有 UI 入口

#### 3. mV chart 上下白邊消除

v3.8.17 在 `_paint_mv` 強制 1.2:1 W:H aspect 的 figure，但 cv_mv 在 Qt vertical layout 下天生比 1.2:1 還高（~1.1:1），所以 1.2:1 pixmap 被 KeepAspectRatio 寬度限縮 → 上下產生白邊。

**改動**：拿掉 1.2:1 enforcement，`fig_w = W/dpi, fig_h = H/dpi` 直接填滿 cv_mv。pixmap 跟 cv_mv 同 aspect → KeepAspectRatio 不會 leave padding。Y 軸資料範圍不變。

#### 4. Δt 從 sidebar 移到頂部 nav bar

舊：sidebar 底部 `self.deltaTLbl = QLabel('Δt: N d')`。
新：
- sidebar `deltaTLbl` 改 `.hide()`（保留 widget 當 back-compat，所有 `deltaTLbl.setText(...)` 呼叫不會 crash）
- 頂部 nav bar chip 列表加入 `'Δt'` key，跟 Mode/Fit/Blank/Signal/Current step 同款 chip 樣式（小灰標 + 大字 Courier）
- `CalcT0Page._auto_update_delta_t` 同時更新 `deltaTLbl`（hidden）和 `_chips['Δt']`（visible chip）
- `CalcT0Page.__init__` 的 `_chips` placeholder dict 也加 `'Δt'` key 避免 KeyError 在 wire 完成前

#### 5. Cycle Selection Guide dialog 擴充 Auto Blank / Auto Signal 邏輯

`_show_cycle_guide` html 增加新 section：

- Auto Blank 流程：linear fit → R² &lt; 0.8 啟動 outlier removal → 殘差 &gt; σ 排除 → 最多排 4 個
- Auto Signal 流程：先鎖 blank T₀ → 對每個 step 獨立跑相同邏輯
- 強調 Auto 的 outlier threshold (|r| &gt; σ) 比手動 cycle button z-score MAD (1.8/3.0 σ) 寬鬆，所以 Auto 跑完仍可能留下偏黃色但 sub-threshold 的點，可手動再 fine-tune
- 「什麼時候用 Auto vs Manual」實戰建議
- 一句話 SOP 改寫：`Auto Blank → Auto Signal → 紅色全排 → ...`

### 檔案改動

- `AutoPipeline.py`：
  - L65 `SIGMA_METHOD` default 改 'calc_t0'
  - `CalcT0Page._build` sidebar Bi-Dir 按鈕移除 + `deltaTLbl.hide()`
  - `AutoPipelineWindow._build` 頂部 chip 迴圈加 'Δt'
  - `CalcT0Page._auto_update_delta_t` 加 `_chips['Δt']` 同步寫入
  - `CalcT0Page.__init__` `_chips` placeholder 加 'Δt' key
  - `MvCanvas._paint_mv` 拿掉 1.2:1 figsize enforcement
  - `AutoPipelineWindow._show_cycle_guide` html 增加 Auto Blank/Signal section + SOP 改寫
- `.work/.app_info.txt`：3.8.17 → 3.8.18

### 驗證 checklist

- [ ] 啟動後 sidebar σ method dropdown 預設顯示 "Calc T₀"（不是 Standard SE）
- [ ] sidebar 不再有 Bi-Dir All 按鈕
- [ ] 載入 sample 後 mV chart 上下白邊明顯減少，chart 幾乎填滿 cv_mv
- [ ] 載入 sample 後，頂部 nav bar 'Current step' 右邊出現 'Δt' chip 顯示數字
- [ ] sidebar 底部不再有獨立的 'Δt: N d' label
- [ ] Help menu → Cycle Selection Guide 開啟後可看到新 "Auto Blank / Auto Signal 邏輯" section
- [ ] dialog 開到底有更新的「Auto Blank → Auto Signal → ...」一句話 SOP

---

## V3.8.17（2026-05-27）— 1:1.2 aspect、統一 T₀σ 標題、按鈕放大 1.4×、titleLbl 字體加大

### 問題

v3.8.16 用後使用者回饋：
1. **mV 與 scatter 都太高**，希望高寬比 1:1.2（寬 > 高）。
2. **titleLbl 上 T₀/err/R² 字體偏小**，希望加大但不超出 diagram 寬度。
3. **"T₀ vs 2σ" 在 5 column 各印一次**，希望像 "mV vs time (sec)" 只放一次、用線條隔開上下兩 row。
4. **scatter 下的藍色 [All][10][9]...[4] 和 [Best per n] 灰色方框按鈕太小**，希望放大約 1.5×，但不超出 diagram 寬。
5. 順便問：cycle 1-10 按鈕顏色（藍/黃/紅）代表什麼？

### 修法

`AutoPipeline.py` MvCanvas：

**1. 圖表 1:1.2 W:H aspect（寬比高 1.2 倍）**

- `_paint_mv`: 算出可用的 W/H 後，挑「最大的 1.2:1 矩形」放進去（`if avail_w/avail_h > 1.2: fig_h=avail_h, fig_w=fig_h*1.2`），剩餘空間靠 KeepAspectRatio 留白。
- `_paint_sc`: 用 `ax.set_box_aspect(1.0/1.2)` 把 axes box 強制成 H/W=1/1.2（先前 v3.8.16 是 set_box_aspect None → 跟著 canvas 變化）。

**2. titleLbl T₀/err/R² 字體 11 → 13 px**

`Ar³⁶` 部分仍 18px bold；後面的 `T₀=... err=... R²=...` Courier New monospace 從 11px 提升到 13px。寬度測試過 `Ar³⁶ T₀=2.856e-04 err=7.821e-05 R²=0.000` 仍在 260px min canvas 寬內。

**3. "T₀ vs 2σ" 與 "Best per n" 標題只放在 Ar36（ai=0）column**

其他 4 個 column 的 sc_hdr / best_hdr 用空字串建構，但 stylesheet 保留 `border-top:1px solid` → 5 column 的線條串成一條（中間有 2-4px gap 是 crow spacing + MvCanvas margin，視覺上仍讀作一條 divider）。`setFixedHeight(22)` 確保 5 個 label 同高 → 線條對齊。

**4. n-filter + best-per-n 按鈕放大 ~1.4×**

| 按鈕 | v3.8.16 | v3.8.17 |
|---|---|---|
| n-filter All | 28×24, font 12 | 40×30, font 14 |
| n-filter n=10 | 24×24, font 12 | 32×30, font 14 |
| n-filter n=9..4 | 20×24, font 12 | 28×30, font 14 |
| Best-per-n n=10 | 28×28, font 12 | 40×34, font 13 |
| Best-per-n n=9..4 | 24×28, font 12 | 32×34, font 13 |
| cycle 1-10 | 22×22, font 12 | 26×24, font 12 |

`_update_best_btns` 內 stylesheet 的 font-size 也從 9 → 13 px 跟著更新（先前那段 override 蓋掉 _build 設定）。

**5. cv_mv min width 220 → 260**

放大按鈕後 n-filter row 總寬 ≈ 40+32+6×28 = 240px、best-per-n row ≈ 40+6×32 = 232px。提升 cv_mv min width 到 260px 確保 row 不會超出 chart 寬。

### 顏色說明（給使用者）

cycle 1-10 按鈕配色 = `MvCanvas._cs(sel, z)` 計算結果，z 是該 cycle 殘差的 MAD-based z-score（vs 當前 mask 的 linear fit）：

- **藍底藍框** = 健康（z < 1.8）
- **黃底深黃框** = 可疑（1.8 ≤ z < 3.0），殘差偏大但未到 outlier 程度
- **淡紅底紅框** = outlier（z ≥ 3.0），殘差大到通常該排除
- **灰底紅字** = 已被使用者排除（mask=0），不參與 fit

z-score 用 MAD（median absolute deviation）算，比 std 更 robust 對單一極端值不會被「拉開」。

### 影響

純 UI polish，**無數學/物理邏輯改動**。年代計算結果跟 v3.8.16 完全一致。

### 驗證 checklist

- [ ] mV chart 5 column 在全螢幕下 W > H（1.2:1 比例），左右留小白邊
- [ ] scatter 5 column 在全螢幕下 W > H（1.2:1 比例），不再「拉高拉瘦」
- [ ] Ar36 column 顯示 `T₀ vs 2σ` 標題；Ar37-40 column 沒有文字但 border 線條延續
- [ ] Ar36 column 顯示 `Best per n` 標題；Ar37-40 column 沒有文字
- [ ] titleLbl 的 T₀/err/R² 文字可清楚讀（13px）但不會超出 chart 寬
- [ ] n-filter [All][10]...[4] 按鈕明顯比 v3.8.16 大、文字清楚
- [ ] Best per n [10][9]...[4] 按鈕明顯比 v3.8.16 大、文字清楚
- [ ] 全螢幕 + Windows 125% scaling 下 5 column buttons 都不會被切到
- [ ] cycle 1-10 button hover tooltip 顯示 z-score + healthy/suspicious/outlier 標記

### 檔案改動

- `AutoPipeline.py` — MvCanvas `_build`（cv_mv min width、cycle/nf/best btn sizes、sc_hdr/best_hdr 文字 dedupe）、`_update_best_btns`（font 9→13）、`_paint_mv`（aspect 1.2:1、titleLbl 字體 11→13）、`_paint_sc`（set_box_aspect 1/1.2）
- `.work/.app_info.txt` — 3.8.16 → 3.8.17

### 後續增量：Help menu → Cycle Selection Guide

使用者要求把上面的「顏色說明 + 挑選策略」放進程式內 help 而不只是聊天回覆。

- `AutoPipelineWindow._show_cycle_guide()` — 新方法，開啟 QDialog with QScrollArea + rich-text QLabel：
  - 4 個彩色 badge（藍/黃/紅/灰）跟 `MvCanvas._cs()` 實際按鈕色一致（同 bg、border、text color 配色）
  - z-score MAD 機制說明（淡黃 callout box）
  - 5 步驟挑選策略表格（① 排紅、② 黃色情況判斷、③ scatter Best per n 對照、④ scatter marker 讀法、⑤ 別過度修剪）
  - 一句話 SOP（藍色 callout）
- `AutoPipelineWindow._build` Help menu 多一個 QAction "Cycle Selection Guide" 接到 `_show_cycle_guide`

入口：選單列 → Help → Cycle Selection Guide。

---

## V3.8.16（2026-05-27）— 撤銷 v3.8.15 chart 內標題、button row 置中、scatter 改 1:1

### 改動

**1. mV chart 標題搬回 chart 外（撤銷 v3.8.15 的 ax.set_title 改動）**

v3.8.15 把 `Ar36 / T₀=... / err=... / R²=...` 移進 chart 內當 ax.set_title。使用者試用後決定恢復成 v3.8.14 之前的外部 Qt label 樣式：

- titleLbl 重新顯示，單行 rich text：`Ar³⁶ T₀=... err=... R²=...`
- blank ≥ signal 警示用 ⚠ icon + 紅字（Qt rich text 樣式）
- v3.8.15 在 `_paint_mv` 內的 `ax.set_title(loc='left', ...)` 移除
- mV chart 內部恢復乾淨，仍保留 v3.8.15 的 seaborn darkgrid 風格（沒被白底 override 蓋掉）

**2. cycle / n-filter / best-n button row 改置中**

三排原本 `addStretch()` 只放尾端 → 按鈕貼左、右邊一片白。改成 `addStretch()` 加在頭尾兩端 → 按鈕置中，跟 chart x-axis range 視覺對齊。

**3. T₀ vs 2σ scatter 比例 1:1**

`vb.addWidget(self.cv_mv, 2)` + `vb.addWidget(self.cv_sc, 3)` → 改成 `1` + `1`。cv_mv 跟 cv_sc 在剩餘垂直空間平均分配，配合等寬 → scatter 接近 1:1（先前 2:3 stretch 使 scatter 太高）。

### 檔案改動

- `AutoPipeline.py` — MvCanvas `_build` titleLbl + cycle/nf/best-n 三 row stretch + cv_mv/cv_sc stretch + `_paint_mv` 撤銷 set_title 改動、改寫 titleLbl
- `.work/.app_info.txt` — 3.8.15 → 3.8.16

---

## V3.8.15（2026-05-27）— SaveT0 路徑邏輯重寫 + mV plot 對齊 CalcT0Page

### 1. SaveT0 路徑邏輯改成跟 NTNU_DataReduction.CalcT0Page.LRP_save 一致

原本 v3.8.14 寫到 `os.path.abspath('Data/T0/')` 一個資料夾，blank 跟所有 step 都堆在那邊，沒分 PBs / Sample 分類，跟既有 `pyADR-main\Data\T0\Sample\NO.65\` 結構不一致。

重寫流程比照 `LRP_save`：

```
work_dir = os.path.dirname(__file__)
sample_root = work_dir + 'Data/T0/Sample/'
pbs_root    = work_dir + 'Data/T0/PBs/'

target = QFileDialog.getExistingDirectory(at sample_root)
                                       # 使用者選 / 建 sample-set 資料夾
                                       # 如 Data/T0/Sample/NO.65

write blank   → pbs_root/<blank_name>.csv
write blank   → target/<blank_name>.csv     # 同步一份在 sample 資料夾方便對照
write step_i  → target/<step_name>.csv      for each signal step
```

完成後 popup 顯示完整存檔清單。PNG 截圖暫不存（AutoPipeline 每個 isotope 是獨立 QPixmap，沒有單一 LR.png 可以 `shutil.copyfile`，要存 PNG 還需要再寫一輪 grab pixmap → 合成 → save 的邏輯，先省略）。

### 2. mV vs time plot style 對齊 Utilities.calculateT0

原本 AutoPipeline `_paint_mv` 強制 `fig.patch.set_facecolor('white'); ax.set_facecolor('white')`，蓋掉了 `Utilities.py:15` 的 `seaborn.set()` 全域 darkgrid 設定，看起來跟 CalcT0Page 子程式（用 `Utilities.calculateT0` 畫的圖）完全不同調性。

改動：

- 拿掉 white facecolor override → 自動繼承 seaborn darkgrid（淺藍灰 `#EAEAF2` 底 + 白格線 + 隱藏 spines）
- header 資訊 `Ar 36 / T₀ = ... / error = ... / R² = ...` 從外部 Qt label 改成 `ax.set_title(loc='left', fontsize=9)`，畫在 chart 左上角，跟 CalcT0Page 一致
- blank ≥ signal 警示從 Qt 紅字 ⚠ icon 改成 chart title 字體變紅（不需 emoji）
- 字體大小：xlabel/ylabel 15 → 11，ticks → 9（跟標準 matplotlib + seaborn 比例對齊）
- `ticklabel_format(axis='y', style='sci', scilimits=(0,0))` 對齊 standalone

連帶：

- `titleLbl` Qt widget 隱藏（資訊已搬進 chart）。建構時 `setText('')` + `hide()`，留著當 back-compat 占位。
- `_paint_mv` 內部不再 setText titleLbl，相關 ⚠ icon / warning color HTML 邏輯整段刪除。

### 檔案改動

- `AutoPipeline.py` — CalcT0Page._save 重寫；MvCanvas._paint_mv style + 移除 titleLbl 邏輯
- `.work/.app_info.txt` — 3.8.14 → 3.8.15

---

## V3.8.14（2026-05-27）— Ar40 canvas 在全螢幕仍被裁切的根因修正

### 問題

v3.8.13 之後使用者反映「全螢幕下 Ar40 的 T₀ vs 2σ 跟 best-n button 仍然被切」。截圖顯示 Ar40 的 n-filter 缺少「4」、best-n 缺少「4」、scatter 右側留白被裁。其他 4 個 isotope 都完整顯示。

### 根因

MvCanvas 內的兩列：
- n-filter row：8 個 QPushButton（All / 10 / 9 / ... / 4）
- best-n row：7 個 QPushButton（10 / 9 / ... / 4）

之前**只 `setFixedHeight`，沒 `setFixedWidth`**。Qt 在 Windows 上 QPushButton 預設 min width 約 75 px。於是：

- n-filter row 實際最小寬度 ≈ 8 × 75 = 600 px
- best-n row 實際最小寬度 ≈ 7 × 75 = 525 px

MvCanvas 的 min width = max(全部 child 的 min)，被這兩列撐到 **~600 px**。5 個並排就要 3000 px，遠超任何視窗。

CalcT0Page 外層 QScrollArea 設定 `setHorizontalScrollBarPolicy(ScrollBarAlwaysOff)`，所以橫向 overflow **不會出 scrollbar 而是直接裁掉**右側。最右的 Ar40 自然被切。

### 修法

**1. 給 n-filter 跟 best-n 每個 button 明確 `setFixedSize`**

```python
# n-filter:
btn_all  setFixedSize(28, 24)     # 'All' 略寬
btn_10   setFixedSize(24, 24)     # 兩位數
其他     setFixedSize(20, 24)     # 個位數
# Total: 28 + 24 + 6*20 = 172 px

# best-n:
btn_10   setFixedSize(28, 28)
其他     setFixedSize(24, 28)
# Total: 28 + 6*24 = 172 px
```

`setSpacing(2) → 0`，並在兩列末端加 `addStretch()` 把 leftover space 推到右邊（不會撐開 min）。

**2. cv_mv min width 240 → 220、cycle button 24 → 22 px**

5 × 220 = 1100 px，加 sidebar 95 + margins ≈ 1240 px 視窗就能塞下，1280p 螢幕（含 Windows 125% DPI 縮放後的 1920p）都安全。

**3. 修掉其他 hidden width inflation**

- `scInfoLbl` (σ 標註 label)：`setWordWrap(True)` + `setMinimumWidth(1)`，避免長文字撐開 canvas
- `sc_hdr` 文字縮短：`'T₀ vs 2σ  (Manual: click to select)'` → `'T₀ vs 2σ'`，完整說明改 tooltip
- `best_hdr` 同：`'Best per cycle count  (min error):'` → `'Best per n'` + tooltip
- `usedLbl` font 14 → 12 + `setMinimumWidth(1)`

所有改動都加 `setMinimumWidth(1)` 強制這些 label 不貢獻 MvCanvas min width。

### 驗證

預期 MvCanvas min width 收斂到 **~220 px**（被 cv_mv min 跟 cycle row 雙重 binding）。5 × 220 + sidebar 95 + margins ≈ 1240 px，1366p+ 螢幕都能完整顯示 Ar40。

### 檔案改動

- `AutoPipeline.py` — MvCanvas n-filter / best-n button widths、cv_mv min、cycle button size、label min widths
- `.work/.app_info.txt` — 3.8.13 → 3.8.14

---

## V3.8.13（2026-05-27）— AutoPipeline T0 頁面 UI 微調

### 改動

**1. mV vs time / T₀ vs 2σ 只有 Ar36 顯示 y-axis 標題**

```python
if self.ai == 0: ax.set_ylabel('mV', fontsize=15)
else:            ax.set_ylabel('')
```

Ar37-Ar40 的 'mV' / '2σ' label 拿掉，每個 canvas 多 ~40 px 橫向空間給 plot。

**2. Cycle button 視覺對齊 T₀ vs 2σ n-filter button**

- size 22×22 → 24×24
- spacing 2 → 0（按鈕相連，跟 n-filter 風格一致）
- font 11px → 12px bold（_cs 整個 helper 一次改）

10 × 24 + 0 spacing = 240 px，剛好等於 cv_mv min width，第 10 cycle 仍不被切。

**3. T₀ vs 2σ scatter 拉高**

MvCanvas vb layout 的 stretch 比例從 cv_mv:cv_sc = 3:2 改成 2:3。Scatter 多拿到約 20% 額外垂直空間，不再被擠扁。

### 檔案改動

- `AutoPipeline.py` — MvCanvas (`_paint_mv`, `_paint_sc`, cycle button row, vb stretch)
- `.work/.app_info.txt` — 3.8.12 → 3.8.13

---

## V3.8.12（2026-05-27）— AutoPipeline T0 頁面 UI 第三輪精修

### 改動清單

**1. mV chart 填滿 cv_mv，去掉留白**

`_paint_mv` 原本 `fig_h = fig_w × 4/3`（強制 3:4 縱長比例）。當 QLabel 寬度大於高度時，畫出來的 pixmap 比 QLabel 短，QLabel 上下留白。改成：

```python
fig_w = max(W / dpi, 1.0)
fig_h = max(H / dpi, 1.0)   # was: fig_w * 4 / 3
```

直接用 QLabel 實際 (W,H) 算 figure 大小，畫面完全填滿。

**2. Ar40 cycle 10 不再被切**

cycle button 從 26×26 → 22×22 px。10 buttons × 22 + 9 gaps × 2 = 238 px，落在 cv_mv 240 px min width 內，第 5 個 canvas 被擠時 cycle row 也不會溢位。

**3. T₀ vs 2σ scatter 內的 σ 標註移出 chart**

原本在 `_paint_sc` 用 `ax.text(0.02, 0.97, ..., bbox=...)` 在 axes 左上角畫 σ 資訊白框，Ar39/Ar40 因為資料點集中在左上，框會擋住資料。改成：

- 在 sc_hdr 下方新增 `self.scInfoLbl`（QLabel）
- 每次 `_paint_sc` 結尾呼叫 `self._update_sc_info(t0, sig_std, sig_calc)` 把資訊寫到 label
- 用 ▶ 標當前 active 的 σ method

Chart 內完全沒文字遮擋，三個數字（T₀ / σ(SE) / σ(Calc T₀)）在 chart 上方單行顯示。

**4. Best per cycle count buttons 文字 `n=10` → `10`**

`QPushButton(f'n={n}')` → `QPushButton(str(n))`。Tooltip 還保留 `n=X: T₀=... err=...` 完整資訊。

**5. Degassing Pattern 改成置中 4:3 (~480×280)**

原本佔滿整個 left_vb 寬度，比例被拉得很扁。改成：

```python
self.cv_degas.setFixedSize(480, 280)
degas_center = QHBoxLayout()
degas_center.addStretch()
degas_center.addWidget(p5)
degas_center.addStretch()
```

固定 4:3，左右用 addStretch 置中。

**6. Sidebar 1:1 對齊 DiagramPlots_SH**

按鈕 setFixedSize(91, 51)、`spacing=0`、無任何 setStyleSheet，跟 DiagramPlots_SH 的 setGeometry(0, y, 91, 51) 視覺一致。

兩個 dropdown 在最上面（對應 DiagramPlots_SH 的 'red' / 'o'）：
- σ method (Standard SE / Calc T₀)
- Fit type (Linear / Average)

8 個 button 取代原本 10 個（Linear/Average 改成 dropdown，btnL/btnA 留 hidden 給 back-compat）：Return / Save T₀ / Load Blank / Load Sample / Auto Blank / Auto Signal / Bi-Dir All / Manual。

Δt label 放最底端，小字無 box style。

### 驗證 checklist

- [ ] mV vs time chart 沒有上下大片留白
- [ ] Ar40 第 10 cycle button 完整顯示
- [ ] T₀ vs 2σ scatter 上面有一行 `T₀=... ▶σ(SE)=... σ(Calc T₀)=...`，scatter 上沒文字框
- [ ] best-n button 顯示 `10` `9` `8`...（不是 `n=10`）
- [ ] Degassing 4:3 比例，置中
- [ ] sidebar 按鈕全部 91×51、相連（無間隔）、Qt OS 預設外觀
- [ ] Fit type 變成 dropdown（不是 Linear / Average 兩個 button）
- [ ] NO.65 1100°C 重跑：10.918 ± 0.866 Ma

### 檔案改動

- `AutoPipeline.py` — MvCanvas (mV/scatter/cycle button/best-n) + CalcT0Page (sidebar/Degassing layout)
- `.work/.app_info.txt` — 3.8.11 → 3.8.12

---

## V3.8.11（2026-05-27）— AutoPipeline T0 頁面 layout 調整 + Δt bug fix

### 問題

v3.8.10 把 Panel ⑥⑦⑧ 砍掉後，剩下的 ⑤ Degassing Pattern 用 stretch=1 + minHeight=300 → 佔據過多版面，使用者要滾才能看到每個 isotope canvas 下方的 T₀ vs 2σ scatter。其他問題：

- 5 canvases 在 v3.8.10 包了 horizontal scroll，使用者全螢幕也看到左右 scrollbar
- 左側 sidebar 仍有 group header + 各種 padding，跟 DiagramPlots_SH 風格不一致
- Δt (auto) 在 sidebar 永遠顯示 `0 d` — v3.8.10 改過但仍沒生效

### 修法

**1. Layout：固定 Degassing 高度 280 px，canvas section 填滿視窗剩餘空間**

- `guide_container.setMinimumHeight(300)` → `setFixedHeight(280)`
- `crow_w.setMinimumHeight(680)` → `setMinimumHeight(620)`
- 拿掉強制的 `mn.setMinimumHeight(900)` — 讓內層 layout 自然計算

結果：mV vs time + T₀ vs 2σ scatter 一定在初始視窗可見，往下滾才看 Degassing。

**2. 拿掉 v3.8.10 的橫向 QScrollArea**

5 個 MvCanvas 直接放 `QHBoxLayout` 並用 stretch=1 平均分配寬度。配合：

- `cv_mv.setMinimumSize(320, 1)` → `setMinimumSize(240, 1)`
- Cycle button 從 32×32 → 26×26

5 canvases 總最小寬度從 ~1820 px 降到 ~1430 px，1440p 螢幕也能塞、不再出現橫向 scrollbar。

**3. Sidebar 比照 DiagramPlots_SH 預設 Qt 按鈕**

```python
def sb_btn(txt, col='default'):
    b = QtWidgets.QPushButton(txt)
    b.setFixedSize(90, 40)   # 比照 DiagramPlots_SH 91×51
    return b                  # 無 setStyleSheet → 用 Qt 預設外觀
```

拿掉：group header (NAV/FILE/FIT/AUTO/STATS)、`sb.setStyleSheet`、每個按鈕的 `_btn_style(...)`、deltaTLbl 的 box style。

新版佈局：σ method dropdown → Δt label → 10 個按鈕（Return / Save T₀ / Load Blank / Load Sample / Linear / Average / Auto Blank / Auto Signal / Bi-Dir All / Manual）

**4. Δt = 0 d 一直不更新的 bug**

`_auto_update_delta_t()` 沿著 parent chain 找 `hasattr(parent, 'params')`，但 `AutoPipelineWindow.set_context()` 存的是 `self._params`（底線）。所以 `parent.params` 永遠不存在，function 還沒讀到 OGD 就 return，label 維持初始值。

v3.8.10 改過 `self.deltaTLbl`（label 位置）但沒改 `parent.params` → `parent._params` — 兩個 bug 接續。本版補上後者：

```python
while parent is not None and not hasattr(parent, '_params'):
    parent = parent.parent()
ogd = parent._params[parent._pnames.index('OG Date')]
```

Label 格式從 `'{dt} d'` 改成 `'Δt: {dt} d'` 比較容易辨識。

### 驗證 checklist

- [ ] 全螢幕（≥1440p）載入 blank+signal：5 canvases 平均分配、無橫向 scrollbar
- [ ] mV vs time + T₀ vs 2σ 在初始視窗都可見（不用滾）
- [ ] 滾輪往下能看到 Degassing Pattern Overview
- [ ] sidebar 按鈕全部同樣大小、用 OS 預設 Qt 風格、無自訂顏色
- [ ] 載完 blank+signal 後 sidebar 顯示 `Δt: 83 d`（NO.65 的話）而非 `Δt: 0 d`
- [ ] NO.65 1100°C 重跑驗證：10.918 ± 0.866 Ma（科學結果不能因為這些 UI 改動變）

### 檔案改動

- `AutoPipeline.py` — CalcT0Page sidebar / canvas layout / `_auto_update_delta_t` parent.params bug
- `.work/.app_info.txt` — 3.8.10 → 3.8.11

---

## V3.8.10（2026-05-27）— AutoPipeline T0 頁面瘦身、效能與 UX 大改

### 範圍

教授指示砍掉用不到的進階分析 panel、修正 Δt / Save T₀ 行為、統一介面風格、解決切換步驟卡頓。AutoPipeline.py 淨減少 ~750 行。

### 改動清單

**1. 砍 Panel ⑥ MC Uncertainty / ⑦ Bi-directional Strategy / ⑧ Final Recommendation**

只保留 ⑤ Degassing Pattern Overview（多階釋氣總覽圖，對 15 step 樣品有總覽價值）。砍掉的理由：

- ⑥ MC Uncertainty 名字誤導，實際只是把 σ_a + σ_m 拆成堆疊棒；同樣資訊在 T0 頁面 `σ(SE)` / `σ(Calc T₀)` 已顯示
- ⑦ Bi-directional Strategy 跟「Auto Best All」按鈕功能重疊；單一 step 視覺對比 panel 實務上沒人 step-by-step 看
- ⑧ Final Recommendation 的「Run Full MC」是空殼，按下去只跳 placeholder 訊息
- 「Bi-Dir All」核心邏輯（一鍵跑完 15 step）仍保留在左側按鈕

連帶移除：`_paint_mc_uncertainty` / `_paint_strategy_compare` / `_refresh_recommendation` / `_apply_recommended` / `_run_full_mc` / `_compute_bidirectional_strategy` / `_paint_guide_sc37` / `_paint_guide_sc36` / `_paint_guide_air36` / `_refresh_bestn_tbl` / `_apply_recommended_legacy` / `_guide_sc37_click` / `_guide_sc36_click` / `_get_cur_scv` 以及對應的 stub canvas / legacy widget。

**2. 切換 Blank ↔ Signal step 加速（~20× 提升）**

`MvCanvas.load()` 原本每次都重跑 `_build_combos`（每個 isotope 848 個 curve_fit，5 個 isotope 共 4240 次）。改成：

- `_enumerate_combos()`：純列舉 + curve_fit，結果 cache 在 `_combo_fits`，by `(id(vt), fit, nc)` 為 key
- `_recompute_validity()`：用 cached fits + 當下 bt / `_t0_net_37` 重算 valid flag 跟 best_n（無 curve_fit calls）

切換步驟時，每個 step 的 fits 只算一次，之後切回去都是讀 cache。`set_sibling_t0_net_37` 也改用 `_recompute_validity()`。

**3. 修正 Δt 顯示永遠是 `0 d` 的 bug**

`_auto_update_delta_t` 把 label 找錯 widget — `deltaTLbl` 在 `CalcT0Page (self)`，但程式碼裡 `hasattr(ap, 'deltaTLbl')` 找的是 `AutoPipelineWindow (parent)`，永遠 False。導致 `DELTA_T_DAYS` 全域變數有更新（decay correction 是對的），但 UI label 一直顯示初始 `0 d`。改回 `self.deltaTLbl`。

**4. Save T₀ 按鈕修復 + 加 feedback**

原本寫到相對路徑 `Data/T0/` 沒提示。若 cwd 不是 `C:\pyADR-main\` 就寫到別處而使用者不知道。改成：

- 路徑用 `os.path.abspath(os.path.join('Data', 'T0'))`（絕對路徑）
- `os.makedirs(t0_dir, exist_ok=True)` 確保資料夾存在
- 寫完彈出 `QMessageBox.information` 顯示存了幾個檔、完整路徑
- 沒載 blank 時也彈警告而非 silent return

**5. 移除右上 Out [Data/] 輸出資料夾選擇器**

`outEdit` 跟 📁 browse 按鈕拿掉；`_run_pipeline` 改用 hardcoded `'Data/'`（跟原本 default 一致）。`_browse` 方法刪除。

**6. 左側 sidebar 按鈕統一灰色**

`sb_btn(col)` 忽略 col 參數，一律 `_btn_style(PNL, TXT, BRD)` 灰色，跟 AgeCalculation / MassRatio / JCalculation 等子頁的 Return / Save 按鈕一致。原本 Save T₀ 綠、Load Blank/Sample 藍、Auto * 綠看起來雜亂。

**7. Blank/1100°C 步驟切換改 QTabBar (Chrome-style)**

原本 `_blank_btn` + `_sbtn_map`（彩色 push button + 一堆顏色狀態）→ 改 `QTabBar`：

- `setDocumentMode(True) + setDrawBase(False)` → 接近 Chrome 分頁外觀
- 選中 tab 白底 / 藍字 / 粗體；未選 tab 米色背景
- 失敗 step 用 tab text color 改成琥珀色（取代以前整個按鈕變色）
- `_on_tab_changed` ↔ `_sync_tab_to_step` 互鎖，避免 `_sel_step` 跟 tab signal 互打

**8. Ar40 第 10 cycle 被視窗右緣裁切**

5 個 mV-vs-time canvas 包進 `QScrollArea`（horizontal `ScrollBarAsNeeded`）。視窗夠寬時不顯示 scroll；窄視窗時 ⁴⁰Ar 跟其 cycle-10 按鈕仍可橫向滑到。

### 驗證 checklist

- [ ] NO.65 muscovite 1100°C：年代仍是 10.918 ± 0.866 Ma（不能因為這次大改而動到科學結果）
- [ ] NO.65 完整 step heating：plateau 9.77 ± 0.28 Ma
- [ ] Save T₀ 按鈕：點下去有 popup 提示存檔路徑
- [ ] Δt (auto)：載完 blank+signal 後左下顯示真實天數（不再是 `0 d`）
- [ ] 切換 Blank ↔ 1100°C：第一次切到該步驟稍卡（建 cache），之後切回去秒切
- [ ] Tab 風格：選中/未選中清楚分辨，失敗步驟琥珀字
- [ ] 視窗寬度 < 1600px：canvas row 出現橫向 scrollbar，可滑到 Ar40

### 檔案改動

- `AutoPipeline.py` — 淨減 ~750 行（4964 → ~4220）
- `.work/.app_info.txt` — 3.8.9 → 3.8.10

---

## V3.8.9（2026-05-27）— AutoPipeline blank T0 寫檔用錯 mask 的 critical bug fix

### 問題

`AutoPipelineWindow.T0Page.get_blank_csv()` 在寫 blank T0 CSV 時，不論當下 canvas 顯示的是 blank 還是 signal step，都直接抓 `cv._mask`（canvas 當前顯示的 mask）去 fit blank 數據：

```python
for ai, cv in enumerate(self._cv):
    mask = cv._mask if cv._mask is not None else self._bmask[ai]
    t0,sig,r2,_ = _fit_one(f, self._bvt[ai], mask)
```

T0 頁面 UI 顯示的 blank T0 是對的（因為切到 Blank 時 canvas mask 就是 blank mask），但只要使用者在點 Next 進 Mass Ratio 前切去看任何一個 signal step，`cv._mask` 就變成那個 signal step 的 mask，寫到 disk 的 `Data/T0/<blank>.csv` 就是「用 signal step mask fit blank 數據」的結果。

對照 `get_signal_csvs()`（line 3427-3448）有正確判斷 `if nm == self._cur`，只在 canvas 確實顯示該 step 時才用 canvas mask，blank 路徑就漏了這個檢查。

### 影響

NO.65 muscovite 1100°C 單一 step 重現：

| 項目 | 正確（CalcT0Page 工作流） | AutoPipeline 跑出來 |
|------|---------------------------|----------------------|
| Blank Ar36 T0 | 2.8045e-04 (R²=0.011) | 2.387e-04 (R²=0.024) |
| Blank Ar37 T0 | +2.434e-05 | −1.308e-04（連正負號都反）|
| Blank Ar40 T0 | −9.63e-05 (R²=0.921) | +2.39e-04 (R²=0.077) |
| Ar36 Measurement | 1.72e-06 | 4.35e-05（25× 偏掉）|
| Ar37 Measurement | 6.72e-05 | 8.70e-04（13× 偏掉）|
| 40Ar(r)% | 95.1% | 33.1% |
| Age | 10.918 ± 0.866 Ma | 3.770 ± 19.069 Ma |

Ar36/Ar37 受傷最重是因為 sample T0 − blank T0 本來就接近零，blank 多差 4e-5 在 Ar36 上殘量直接從 1.7e-6 跳成 4.3e-5。Ar38/39/40 因為訊號本身大，相對偏差只有 1%，但 Ar40_air = Ar36_air × 298.56 會把 Ar36 的錯誤放大 → Ar40_r 跟著錯 → F 跟著錯 → 年代直接砍到 1/3。

### 修法

加上 `_cur == '__BLANK__'` 檢查，只有當下 canvas 真的在顯示 blank 時才把 canvas mask 同步回 `_bmask`，fit 一律用 `_bmask`：

```python
if self._cur == '__BLANK__':
    for ai, cv in enumerate(self._cv):
        if cv._mask is not None:
            self._bmask[ai] = cv._mask.copy()
for ai in range(5):
    t0,sig,r2,_ = _fit_one(f, self._bvt[ai], self._bmask[ai])
```

### 驗證 checklist

- [ ] NO.65 muscovite 1100°C 單一 step：AutoPipeline 跑出年代回到 ~10.918 Ma（跟 CalcT0Page→MassRatio→AgeCalc 一致）
- [ ] NO.65 完整 step heating：plateau 回到 9.77 ± 0.28 Ma
- [ ] `Data/T0/pbs<...>.csv` 內容跟 CalcT0Page 直接 save 的 T0 一致（mask 沒被破壞）
- [ ] 在 T0 頁面切換 blank ↔ signal step 多次後再 Next，blank T0 仍然正確

### 檔案改動

- `AutoPipeline.py` — `get_blank_csv()` 加上 `_cur == '__BLANK__'` 檢查
- `.work/.app_info.txt` — 3.8.8 → 3.8.9

---

## V3.8.8（2026-05-26）— select-style sub-window 加上 Return 按鈕

### 問題

七個 select-style 子視窗（TypeSelect / StatSelect / JSelect / SaltSelect / SaltStatSelect / DiagramSelect / DatumSelect）的 UI 檔沒有 Return 按鈕，回主頁只能透過 menubar 的「Main Menu」action。其他大多數子頁面（ParameterSetting / AgeCalculation / MassRatio / JCalculation / Statistics / DiagramPlot SH/LS / SaltCalculation 等）左側都有標準 Return 按鈕，介面行為不一致。

### 修法

新增 module-level helper `_add_return_button(window, y=200)`：

```python
def _add_return_button(window, y=200):
    if getattr(window, 'return_2', None) is not None:
        return  # idempotent: skip if UI already has return_2
    if not hasattr(window, 'centralwidget'):
        return
    btn = QtWidgets.QPushButton(window.centralwidget)
    btn.setGeometry(QtCore.QRect(0, y, 91, 51))
    btn.setObjectName("return_2")
    btn.setText("Return")
    window.return_2 = btn
```

每個 select wrapper 的 `__init__` 加一行：

```python
class DiagramSelect(QtWidgets.QMainWindow, UI.DiagramSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        _add_return_button(self)              # ← 新加
        _make_select_page_responsive(self)
```

App init 加 7 個訊號連線（跟既有 return_2 wiring 同 pattern）：

```python
self.TypeSelect.return_2.clicked.connect(self.toMain)
self.StatSelectPage.return_2.clicked.connect(self.toMain)
self.JSelectPage.return_2.clicked.connect(self.toMain)
self.SaltSelectPage.return_2.clicked.connect(self.toMain)
self.SaltStatSelectPage.return_2.clicked.connect(self.toMain)
self.DiagramSelectPage.return_2.clicked.connect(self.toMain)
self.DatumSelectPage.return_2.clicked.connect(self.toMain)
```

### 為什麼不直接改 UI/*.py

`UI/*.py` 是 `pyuic5` 從 `.ui` 自動產生，檔首有「WARNING! All changes made in this file will be lost!」。改了未來重 generate 會被蓋掉。Fix 寫在 wrapper class，永久安全。

### 位置 / 樣式

`QRect(0, 200, 91, 51)` 跟其他子頁面標準 Return 按鈕一致（AgeCalculation 在 y=170、AirRatioStatistics 在 y=200、DiagramPlots_SH/LS 在 y=190）。原生 PyQt5 按鈕樣式（不額外 setStyleSheet）→ 跟其他 Return 按鈕視覺一致。

### 互動

點 Return → 跳回 pyADR 主頁面（toMain）。menubar 的「Main Menu」action 跟新加的 Return 按鈕 **獨立但等效**，使用者可選任一條路徑。

### 檔案改動

- `NTNU_DataReduction.py`：新增 helper `_add_return_button`；7 個 select wrapper class 加 `_add_return_button(self)`；App init 加 7 個 `return_2.clicked.connect(self.toMain)`
- `.work/.app_info.txt`：`3.8.7` → `3.8.8`

---

## V3.8.7（2026-05-26）— select-style sub-window 按鈕響應式置中

七個「分支選擇」型子視窗的按鈕跟標題標籤改成隨視窗縮放保持水平置中。

### 問題

`UI/DiagramSelect.py`、`UI/TypeSelect.py`、`UI/StatSelect.py`、`UI/JSelect.py`、`UI/SaltSelect.py`、`UI/SaltStatSelect.py`、`UI/DatumSelect.py` 全部用絕對 `setGeometry(QtCore.QRect(210, y, 421, 51))`，設計給 800px 寬視窗（中心 = 400，button 中心 = 210 + 421/2 ≈ 420）。視窗放大時 button 卡在 x=210，整列往左偏。

### 修法

新增 module-level helper `_make_select_page_responsive(window)`（NTNU_DataReduction.py 開頭）：

```python
def _make_select_page_responsive(window):
    cw = window.centralWidget()
    if cw is None or cw.layout() is not None:
        return  # HomePage 已用 QHBoxLayout，跳過
    def _recenter():
        w_total = cw.width()
        for widget in cw.findChildren(QtWidgets.QPushButton):
            if widget.geometry().width() > 100:
                widget.move((w_total - widget.geometry().width()) // 2,
                            widget.geometry().y())
        # 同樣處理大 QLabel（title）
    _orig = window.resizeEvent
    def _on_resize(event):
        _orig(event)
        _recenter()
    window.resizeEvent = _on_resize
    QtCore.QTimer.singleShot(0, _recenter)  # 初次延遲到 Qt layout pass 之後
```

每個 select wrapper 的 `__init__` 加一行：

```python
class DiagramSelect(QtWidgets.QMainWindow, UI.DiagramSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        _make_select_page_responsive(self)   # ← 新加
```

### 適用範圍

| Class | UI 檔 | 按鈕 |
|---|---|---|
| `TypeSelect` | UI/TypeSelect.py | MB / PBa / AS / PBs / SP / TP / ST |
| `StatSelect` | UI/StatSelect.py | J / T0 / ARS / Salt |
| `JSelect` | UI/JSelect.py | FSC / LP6 / MMHB |
| `SaltSelect` | UI/SaltSelect.py | Ca / K |
| `SaltStatSelect` | UI/SaltStatSelect.py | (similar pattern) |
| `DiagramSelect` | UI/DiagramSelect.py | SH (Step Heating) / LS (LaserOB) |
| `DatumSelect` | UI/DatumSelect.py | TT / isor |

### 不受影響

- `HomePage` 已經用 `QHBoxLayout(self.centralwidget) + addStretch()` layout-based 置中，helper 偵測到 `cw.layout() is not None` 自動跳過
- Diagram / Statistics / 主資料表頁面（DiagramPlots_SH、JStatistics、T0Statistics 等）有自己的 `resizeEvent` 處理特殊 widget，未碰

### 沒動 UI/*.py 檔的原因

`UI/*.py` 是 PyQt5 uic 自動產生的，檔首有「WARNING! All changes made in this file will be lost!」。修改 .py 容易被未來重 generate 蓋掉。所以 fix 寫在 wrapper class 那邊，UI 檔保持原樣。

### 檔案改動

- `NTNU_DataReduction.py`：新增 helper `_make_select_page_responsive`；7 個 select wrapper class 各加一行呼叫
- `.work/.app_info.txt`：`3.8.6` → `3.8.7`

---

## V3.8.6（2026-05-26）— DiagramPlot UX 重整 + Main/Help 選單 + PlaneFit3D 數學文件 + σ_40 fix

集中處理 v3.8.5 釋出後使用者回饋發現的 UX / 文件 / 邊角 bug，沒動主數學 path。

### DiagramPlot SH 介面

- DFN/DFI 移除「pre-outlier-removal」第一條 fit line。原本同時畫兩條（一條 OLS 全資料、一條 method-toggle 後去掉 outlier）視覺干擾，現在只剩最終那條
- DFI annotation「Regression: OLS/York 2004 | Regression MSWD: X.XX (n=N)」從圖上拿掉，改放到 diagram 上方既有的灰色 infoLabel 內，跟滑鼠座標訊息合併
- 切到非 isochron panel（DFW age spectrum / DFA Ca/K / DFC Cl/K / DFM summary）會自動清空 regression suffix，不再殘留誤導
- NTNU 主 GUI 的 DiagramPlots_SH page 加上 `Isochron method` dropdown（之前只在 AutoPipeline AgeCalcPage 有），方法切換時自動 re-render

### Main / Help 選單

- DiagramPlots_SH 跟 AutoPipelineWindow 都加上 menubar（之前是空的 / 缺）：
  - **Main** → Return to pyADR Home
  - **Help** → Formulas & References（共用 `_show_diagram_plot_help` 對話框，單一來源真相）
- Help 對話框 6 個 tab 涵蓋 Plateau/WMA、Isochron、MSWD、Age formula、Ar components、3D Plane Fit、References。HTML 渲染含表格、上下標、外部連結

### PlaneFit3D 數學文件 + caller-side bug fix

審查 Kent et al. (1990) + Wu (2007) NTU 碩論 (R94224113) vs `PlaneFit3D.py`：

**`PlaneFit3D.py` 本體：沒 bug**。連 Wu 2007 eq 3-27 的正負號 typo 都有註記並修正（pyADR 用 `cov(δ̂) = τ²·(-∂²L_p)⁻¹` 而非 Wu 原寫法）。

**Caller-side bug**（NTNU_DataReduction.py L4003 + L4596）：

```python
x40 = (df["40Ar(r)"] + df["40Ar(a)"]).values[mask]
s40 = np.hypot(σ_40r, σ_40a)   # ← 錯
```

`40Ar(r)` 跟 `40Ar(a)` 透過分解 `40r = 40m - 40a - 40K` **負相關**，`cov(40r, 40a) = -σ²_40a`。所以：

```
var(40r + 40a) = σ²_40r + σ²_40a + 2·cov = σ²_40r - σ²_40a
              = σ²_40m + σ²_40K
```

`np.hypot` 給的是 `σ²_40r + σ²_40a`，double-counts σ_40a。**跟 v3.8.1 修的 σ_36(m)/σ_39(m) 雙重計算同 pattern**。

修法：`s40 = sqrt(max(σ²_40r - σ²_40a, 0))`。效果：σ_40 不再 inflated → MSWD 略升（更誠實）、σ_α/σ_β 略降、α/β/age 微移（<1%）。

**σ_36 / σ_39 input 都直接從 CSV column 讀，沒做相加，沒類似 bug**。

### Splash / 啟動體驗（從 v3.8.5 延伸）

- Splash 至少顯示 3 秒（`QEventLoop + QTimer.singleShot` 不會凍結 splash 渲染）
- Splash 版本/日期改 runtime QPainter overlay，不再 baked-in；改 `.app_info.txt` 自動套用，不用重生 splash.png
- Splash credits 改 NTNU Ar/Ar Lab + Prof. Meng Wan (Mary) Yeh，移除個人姓名
- pyADR.bat 改成 `if errorlevel 1 pause`，正常關 GUI 時 cmd 視窗自動收掉，Python 崩潰才停下來顯示錯誤

### 文件

- `FORMULAS.md` 新增 §11「3D Plane Fit」完整數學推導（10 小節 11.1-11.10），含 Kent 1990 + Wu 2007 引文跟驗證樣品（SYL31）
- Help dialog 新增 "3D Plane Fit" tab
- References tab 加 Kent 1990, Wu 2007, Titterington & Halliday 1979 等引文

### 檔案改動

- `Utilities.py` — `getDFStatistics_sh` 移除兩個 DFI/DFN 第一條 fit line drawing；regression annotation 改透過 `return_limits` dict 回傳
- `NTNU_DataReduction.py` — DiagramPlots_SH 加 isochron_method dropdown + Main/Help menu；`_show_diagram_plot_help` 新增（7-tab 對話框）；`SH_apply_axes` 清 suffix；σ_40 input fix ×2
- `AutoPipeline.py` — `AutoPipelineWindow` 加 Main/Help menu，Help action 委派 NTNU 共用 dialog
- `FORMULAS.md` — 新增 §11
- `.work/.app_info.txt` — `3.8.5` → `3.8.6`

### 驗證 checklist

- [ ] NO.65 muscovite 跑全 pipeline，比對 plateau 9.77 ± 0.28 Ma 維持不變
- [ ] DiagramPlot SH 切 OLS / York 2004，infoLabel 顯示對應方法 + regression MSWD
- [ ] DFW / DFA / DFC / DFM 切換時 infoLabel 不殘留 regression info
- [ ] Help dialog 開得起來，3D Plane Fit tab 顯示正常
- [ ] SYL31（Sylhet Trap basalt 115.4 ± 3.9 Ma）跑 PlaneFit3D，MSWD / α / β 略偏離 v3.8.5 數值（σ_40 fix 影響）

---

## V3.8.5（2026-05-26）— isochron regression math 補丁 + 方法 toggle + MSWD label 釐清

DiagramPlot SH 跟 AutoPipeline AgeCalcPage 兩條 isochron path 的數學審查發現幾個問題，這個版本一次處理。第二波（OLS → York 強制升級）需要老師確認，這邊暫時做成可切換。

### A1：Normal isochron `n_std` 不再用 OLS-on-error-bars

**位置**：`Utilities.py:965-966`（`getDFStatistics_sh` 內 normal isochron 第二次擬合處）

**原寫法**：
```python
popt_std, _ = curve_fit(linear, x_std, y_std)
n_std = linear(0, *popt_std)
```
把每點的 `(σ_x[i], σ_y[i])` 當成新資料點，再對這 N 個誤差棒做 OLS 線性擬合，然後取那條虛構直線在 x=0 處的 y 值當截距 σ。**數學上沒任何意義**：誤差棒不是資料點，σ_x 跟 σ_y 之間沒理由要符合線性關係。

**新寫法**：
```python
popt, pcov = curve_fit(linear, x, y)
n_std = float(np.sqrt(pcov[1, 1]))
```
直接從主擬合的 covariance 矩陣取截距方差。對線性模型 y = a·x + b，`pcov[1,1] = var(intercept)`。

v3.8.0 已經在 inverse isochron 同款寫法 (L1300-1302) 改成 `pcov` 路徑，這次補上 normal isochron 漏修的部分。

### A3：AutoPipeline 的 σ_F 加上 slope-intercept covariance

**位置**：`AutoPipeline.py:_update_isochron_stats` 內 inverse isochron σ_F 計算

**問題**：v3.8.4 加 York 回歸時，σ_F 公式只算對角線兩項：
```python
sF = sqrt((σ_m/b)² + (m·σ_b/b²)²)
```
沒包含 cov(m,b) 項。對 York 擬合來說 cov 一般為負，σ_F 系統性過大。`Utilities.py:getDFStatistics_sh` 的 σ_F 公式 (L1496-1498) 含 cov 項，兩條 path 不一致。

**修法**：`york_regression` 加回傳 `cov_ab = -x_adj_bar · σ_b²`（Mahon 1996 / Schaen 2021 Eq.14b）。σ_F 公式改成：
```python
σ_F² = (σ_m/b)² + (m·σ_b/b²)² - 2·(m/b³)·cov(m,b)
```

兩條 path（Utilities.py getDFStatistics_sh, AutoPipeline _update_isochron_stats）的 σ_F 公式現在完全一致。

### A2 + B3：isochron 回歸方法 toggle（不是強制升級，可切換）

**背景**：

| 方法 | 假設 | x error 處理 | Ar/Ar 採用時期 |
|---|---|---|---|
| **OLS** (curve_fit) | σ_x = 0，所有誤差在 y | 忽略 σ_x | 傳統（McDougall & Harrison 教科書）|
| **York 2004** | σ_x, σ_y 兩軸都有誤差，可含相關性 | 完整考慮 σ_x + σ_y + 相關性 | 社群現代標準（Schaen 2021 GSA Bull, Vermeesch 2018 IsoplotR）|

**為什麼做成 toggle 而不是強制升級**：York 算出的 slope/intercept 跟 OLS 不同，導致 age 中心值會變。NO.65 9.77 Ma 是 OLS 算的歷史值，換 York 會跑出略不一樣的數字。「換回歸方法」屬於方法論決策，需要老師確認。為避免單方面改動破壞歷史比對，做成可切換。

**實作**：

1. `Utilities.py` L131+ 新增 `york_regression(x, sx, y, sy, ...)` 函式，回傳 (slope, intercept, σ_slope, σ_intercept, MSWD, cov_ab)。AutoPipeline 原本的版本 (L81-130) 改為呼叫 Utilities 版（單一來源真相）
2. `Utilities.py:getDFStatistics_sh` 加 `isochron_method='ols'` 參數。`'york'` 走 York 分支
3. `AutoPipeline.py:AgeCalcPage` 加 "Isochron method" dropdown（OLS / York 2004），預設 OLS 維持向後相容
4. dropdown 切換時，AgeCalcPage 自動重新呼叫 `getDFStatistics_sh` 用新方法，重新載入 DFI/DFN PNG

### B1：MSWD label 釐清為 Plateau / Regression 兩種

**問題**：原本 `getDFStatistics_sh` 回傳的 `mswd` 是 **plateau MSWD**（從 step ages 對 WMA 算的 χ²/(N-1)），但顯示時只標 "MSWD"。看 inverse isochron diagram 的人通常預期看到 **regression MSWD**（χ² of points to fit line / (N-2)），兩種混淆。

**修法**：

1. **DFI.png 上加文字標註**：右上角顯示 "Regression: OLS/York 2004" + "Regression MSWD: X.XX (n=N)"，標清楚是 regression-quality MSWD
2. **AutoPipeline AgeCalcPage stat labels**：原本 "MSWD" 改為 "Plateau MSWD"（B1 的另一面），明確指這是 step ages 的 plateau quality

兩種 MSWD 並存：plateau MSWD 顯示在 stat labels（左上 summary 區），regression MSWD 顯示在 diagram annotation 上。各自有不同物理意義，不再混為一談。

### B2：撤回，axis-aligned ellipse 維持

審查時提到「inverse isochron error ellipse 應該畫傾斜（含 σ_x, σ_y 相關性）」，查文獻後確認這是 IsoplotR 風格、不是 Ar/Ar 主流。McDougall & Harrison 教科書 + ArArCALC + 原 NTNU code 都用 axis-aligned 或 error cross。傾斜橢圓的長軸方向跟 inverse isochron 負斜率方向相反，視覺上反而誤導。維持現狀（axis-aligned）。

### 已知未在這版動的議題

- **AutoPipeline `_update_isochron_stats` 的 stat labels 仍走 York**（不受 dropdown 影響）。dropdown 只切換 DFI/DFN PNG 內的回歸方法。完整對齊需要把 stat labels 也做成可切換，留待 v3.8.6
- **`getDFStatistics_sh` group fit MSWD 仍是 OLS-style**（B3 範圍內）。需要 York-style effective σ 公式，跟 A2 一起做。dropdown 切到 York 主要影響整體擬合，group fits 維持舊算法
- **NTNU_DataReduction.py DiagramPlot SH page 還沒加 dropdown**。手動呼叫 path 仍走預設 OLS。需要在 NTNU GUI 加同款 dropdown

### 檔案改動

- `Utilities.py`：
  - L131+ 新增 `york_regression()` 函式（從 AutoPipeline 搬過來，加 `cov_ab` 回傳）
  - `getDFStatistics_sh` signature 加 `isochron_method='ols'`
  - inverse isochron 第二次擬合改為 method-aware 分支（L1344-1380 附近）
  - σ_F propagation 改用統一 `cov_si_method` 變數（OLS 從 pcov、York 從 york_regression）
  - DFI.png 加 "Regression: <method>" + "Regression MSWD: X.XX" 文字標註
  - **A1**：normal isochron `n_std` 從 OLS-on-σ 改為 `sqrt(pcov[1,1])`（L957-968）
- `AutoPipeline.py`：
  - `york_regression()` 改為呼叫 `Utilities.york_regression`（單一真相）
  - `_update_isochron_stats` inverse σ_F 加 cov 項（A3）
  - `AgeCalcPage` 加 "Isochron method" dropdown + `_on_isochron_method_changed` regen handler
  - "MSWD" label 改 "Plateau MSWD"（B1）
  - worker `sig_done` payload 加 `consts`，方便 regen 時重新呼叫
- `.work/.app_info.txt`：`3.8.4` → `3.8.5`

### 驗證 checklist

- [ ] NO.65 muscovite 跑 AutoPipeline 全流程，AgeCalcPage 右下 stats 區：
  - [ ] Plateau MSWD 標籤正確（不是混淆的 "MSWD"）
  - [ ] Inverse Isochron stats 跟 Plateau age 一致（in 1σ）
- [ ] 點 "Isochron method" dropdown 切到 York 2004，DFI/DFN PNG 重新生成
  - [ ] DFI.png 右上角文字標註出現 "Regression: York 2004"
  - [ ] regression MSWD 數字跟 OLS 版略不同（York 含 σ_x 後 σ 變化）
- [ ] 切回 OLS，annotation 變回 "Regression: OLS"
- [ ] SYL31 LS 玄武岩比對 ~115 Ma（規模較大的測試）

---

## V3.8.4 (cont.)（2026-05-26）— branding + launcher + splash screen

同版本後續，集中在 UX 跟桌面整合，沒動到任何數學或計算 path。

### 桌面捷徑 + ICO

- `.work/pyADR.ico`（81 KB）多解析度 ICO（16/24/32/48/64/128/256）。Source: `.work/logo_square.png`，由 1024×1024 內部 render 降採樣，邊緣銳利
- 桌面捷徑 `pyADR.lnk` 用 PowerShell 建立，Target → `pyADR.bat`、IconLocation → `pyADR.ico`、WindowStyle = 7（cmd 啟動時直接最小化到工作列，不彈窗擋 splash；要看 log 點工作列那顆 cmd）
- 捷徑屬性寫進 `PKEY_AppUserModel_ID = NTNU.pyADR.ArAr.v3.8`（用 pywin32 propsys 設定），讓 Windows pin / group 行為跟 process AUMID 對齊

### Square logo 重新設計

- 原 logo 是 1.88:1 寬扁形狀，硬塞正方形 ICO 後 content 只佔 53% 高度
- 新 `.work/logo_square.png`（512×512）保留原始 layout（"Ar" 中央左、"40/39" 上方貼著 r 自然小尺寸、印章右側），fit-by-width 進方形，比例正確
- 元素萃取流程：navy 色 + 連通元件分析切出「Ar 主體」「40/39 碎片」「印章紅環 + 內部 navy 符號」三組 mask
- Mask edge 用 dilation + Gaussian blur 軟化，alpha_composite 取代 paste，消除前一版的鋸齒缺陷

### Splash screen

- `.work/splash.png`（640×480）啟動畫面：navy 頂條 → logo 180×180 → "pyADR" 標題 → "⁴⁰Ar/³⁹Ar Data Reduction" 副標 → divider → NTNU Ar/Ar Lab → Prof. Meng Wan (Mary) Yeh → [version slot] → [date slot] → github.com/FormosaRes/pyADR → 薄 footer
- splash 設計成靜態 template，**版本跟日期** runtime 才用 QPainter 畫上去，讀 `.work/.app_info.txt`。改版本只要編輯 .app_info.txt，下次啟動自動套用，不用重生 splash.png
- `NTNU_DataReduction.py` `App.__init__` 內接 `QSplashScreen`，記錄 `_splash_t0` 時間戳
- `run()` 內 `widget.show()` 之前用 `QEventLoop + QTimer.singleShot` 強制 splash 至少顯示 3 秒（plain `time.sleep` 會凍結 splash 渲染，QEventLoop 不會）
- splash 右下 runtime 寫 "Loading…" via `QSplashScreen.showMessage`

### Taskbar icon 修正

- `NTNU_DataReduction.py` `App.__init__` 加 `app.setWindowIcon(QtGui.QIcon('.work/pyADR.ico'))` + `ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NTNU.pyADR.ArAr.v3.8')`
- 沒這兩行 Windows 會把 pyADR process 認成 "Python.exe"，taskbar 顯示 Python 預設藍蛇圖示，pin 後關閉程式也會卡 Python 圖示
- 三層 AUMID 對齊：捷徑 .lnk 屬性 + Python `SetCurrentProcessExplicitAppUserModelID` + Qt `setWindowIcon`

### 可選 silent launcher

- `pyADR_launch.vbs`（path-relative）用 VBS 包一層讓 `pyADR.bat` 完全隱形跑（連 taskbar 都不出現 cmd）
- 預設不啟用（cmd 留著看 log）。如果想完全乾淨啟動，把桌面捷徑 Target 改成 `pyADR_launch.vbs` 即可

### 檔案改動

- `NTNU_DataReduction.py` — `App.__init__` 加 icon + AUMID + splash setup + QPainter overlay + `_splash_t0`；`run()` 加 3 秒 QEventLoop 等待 + `splash.finish()`
- `.work/pyADR.ico` 新增
- `.work/logo_square.png` 新增（forced-add，原 .gitignore 排除 `.work/*.png`）
- `.work/splash.png` 新增（同上 forced-add）
- `.work/logo.png` 更新（pyADR + NTNU banner 高品質版）
- `.work/.app_info.txt` Developer 欄修正 "An-J" → "An-Jun (Andrew) Liu"
- `pyADR_launch.vbs` 新增（optional silent launcher）
- `CLAUDE.md` 新增（AI agent 開發指引，§2 三資料夾分工、§3 不要動的東西、§5 v3.8.x 修正脈絡、§9 溝通風格）
- `README.md` Changelog 摘要區更新 v3.8.2 / v3.8.3 / v3.8.4 entry，頁首版本號 3.8.1 → 3.8.4

---

## V3.8.4（2026-05-25）— AutoPipeline AgeCalcPage isochron 公式修正 + λ 統一來源

### 問題

v3.8.3 (cont.) 在 `AutoPipeline.py:AgeCalcPage._update_isochron_stats` 加了 York 2004 isochron 計算，但有三個 bug。其中議題 1 是 v3.8.3 (cont.) 寫進去就錯的，CLAUDE.md §6 只記到後兩個小議題，沒注意到主公式也反了。

#### 議題 1：Inverse isochron F 公式分子分母對調（HIGH，會改變 age 中心值）

`_update_isochron_stats` 中對 inverse isochron 寫：

```python
F_i = -b_i/m_i if abs(b_i) > 1e-30 else (1/(-m_i) if m_i != 0 else 0)
```

其中 `m_i = slope`、`b_i = intercept`（由 york_regression return 順序 `(slope, intercept, ...)` 對應而來，跟同函式內 normal isochron `F_n = m_n` 用法一致）。

但 inverse isochron 的 F 應該是 `−slope/intercept`，依據：

- Vermeesch (2024) Geochronology 6:398 page 2:「[D/P]\* = −b/a for inverse isochrons (Li and Vermeesch, 2021)」（其中 a = intercept、b = slope、[D/P]\* = F）
- Li & Vermeesch (2021) Geochronology 3:415 Eq. 5: `b' = -a' × (e^(λt) − 1)`，解出 `e^(λt) − 1 = -b'/a' = -slope/intercept`
- Utilities.py:getDFStatistics_sh v3.8.0 fix 已採此公式（同 CHANGELOG V3.8.0）

舊 code 寫成 `-b_i/m_i = -intercept/slope`，**正好是正解的倒數**，所以實際算出來是 1/F 而非 F。對 10 Ma 樣品估計 age 偏高約 18%（NO.65 9.77 Ma 會跑到約 11.5 Ma）。

正解：

```python
F_i = -m_i / b_i
```

#### 議題 2：σ_F propagation 偏導跟舊 F 公式綁定

原 σ_F 是給 `F = -b/m` 用的偏導：`∂F/∂b = -1/m`、`∂F/∂m = b/m²`。改成 `F = -m/b` 後對應的偏導：

- `∂F/∂m = -1/b`
- `∂F/∂b = m/b²`
- `σ_F² = (σ_m/b)² + (m·σ_b/b²)²`

#### 議題 3：λ hardcoded 5.543e-10，跟 calcAge 走的 5.49e-10 不一致

`_update_isochron_stats` 內 4 個位置寫死 `5.543e-10`（Steiger-Jäger 1977），另有兩處透過 `hasattr(Utilities, 'LAMBDA_K')` fallback，但 `Utilities.py` 從未定義 `LAMBDA_K`，永遠走 fallback。

calcAge 主路徑用的是 `parameters.csv` 內 `λ for age calculation = 5.49e-10`（透過 `constants[16]` 讀進來），跟 isochron path 不一致，會造成同樣資料的 plateau age 跟 isochron age 差約 1.0% 系統性偏移。

修法：加 module-level `LAMBDA_K = 5.49e-10` 預設，並在 `AutoPipelineWindow.set_context()` 時從 `params['λ for age calculation']` 注入更新。所有 isochron age / σ_age 計算改用 `LAMBDA_K`，把 `Utilities.LAMBDA_K` hasattr 路徑刪掉。

#### 議題 4：Inverse isochron b≈0 fallback 是 v3.7 buggy 公式

原 code 在 b ≈ 0 時走 `1/(-m_i)`，這正是 v3.8.0 在 `getDFStatistics_sh` 修掉的 v3.7 buggy 公式（`F = 1/inv_slope`）。雖然門檻寬鬆到實務上不會觸發，但 dead code 裡躺著已知錯誤公式不利後續 review。

修法：guard 改成 `abs(m_i) > 1e-30 and abs(b_i) > 1e-30 and Jv > 0`，degenerate fit 顯示 `— (degenerate fit)`，不再進 buggy fallback。

### 影響

| 路徑 | 影響 |
|---|---|
| AgeCalcPage Plateau weighted mean | 不變（不走 isochron path） |
| AgeCalcPage Normal isochron age | λ 從 5.543e-10 改 5.49e-10 (parameters) → age 偏小 ~0.78% |
| AgeCalcPage Inverse isochron age | F 公式修正後**從 ~18% 過高變正確**（age 中心值大幅變動）+ λ 換源 ~0.78% |
| AgeCalcPage Inverse isochron σ_age | σ_F 偏導跟著 F 改 |
| 其他 module（Utilities, DiagramPlot SH, calcAge）| 不影響 |

### 文獻支持

- Vermeesch P. (2024) "Errorchrons and anchored isochrons in IsoplotR." Geochronology 6: 397–407. （inverse isochron 公式在 page 398）
- Li Y. & Vermeesch P. (2021) "Short communication: Inverse isochron regression for Re–Os, K–Ca and other chronometers." Geochronology 3: 415–420. （Eq. 5 提供完整推導）
- York D., Evensen N.M., Martínez M.L., De Basabe Delgado J. (2004) Am. J. Phys. 72: 367–375.（York regression）

### 驗證 checklist

- [ ] NO.65 muscovite 跑 AutoPipeline 全流程，AgeCalcPage 右下 stats 區
  - [ ] **Plateau**：應仍 ≈ 9.77 ± 0.28 Ma（不變）
  - [ ] **Normal Iso**：應 ≈ 9.77 ± something Ma（λ 變動造成微小偏移）
  - [ ] **Inv. Iso**：應從 v3.8.3 (cont.) 的 ~11.5 Ma 改為 ≈ 9.77 Ma（這就是這次主要 fix 的證據）
  - [ ] (40/36)_t 仍 ≈ 290–300（air 範圍內）
- [ ] SYL31 LS（Sylhet Trap 玄武岩，論文 115.4 ± 3.9 Ma）跑 AutoPipeline → AgeCalcPage Inv. Iso 應 ≈ 115 Ma
- [ ] CalcT0Page Δt 自動偵測仍正常（這次沒改 decay correction infra）

### 檔案改動

- `AutoPipeline.py`：
  - 新增 module-level `LAMBDA_K = 5.49e-10`（line ~46，緊鄰 LAMBDA_37/LAMBDA_39）
  - `AutoPipelineWindow.set_context()` 加 `LAMBDA_K` 注入（line ~4637）
  - `_update_isochron_stats` inverse 公式 `−b_i/m_i` → `−m_i/b_i`、σ_F 偏導對應更新、`1/(-m_i)` fallback 刪除、4 處 hardcoded `5.543e-10` → `LAMBDA_K`、Utilities.LAMBDA_K hasattr 檢查移除（line ~4080-4131）
- `.work/.app_info.txt`：`3.8.3` → `3.8.4`

### 跟 Jian-Cheng Lee 老師討論時要講的點

- v3.8.4 修了三件事：inverse isochron F 公式（主 bug，age 偏 18%）、σ_F 偏導、λ 統一來源
- 主 bug 跟 v3.8.0 在 `getDFStatistics_sh` 修的是「同一個公式錯誤的雙胞胎」，v3.8.0 之後新加的 AutoPipeline isochron path 又寫錯一次
- 不影響 plateau age，只影響 isochron age（中心值會變動）
- 過去用 AutoPipeline AgeCalcPage Inv. Iso 報的 age 都偏高約 18%，建議重跑

---

## V3.8.3（2026-05-25）— σ_J 括號 bug fix

### 問題

`Utilities.py` 中 `getJVolumeStatistics` 的 σ_J 計算（L2864）有 operator precedence 造成的括號錯誤：

```python
# 錯（Python parse 後實際是 e^(λt) − 1/F_r²）：
v3 = F_std**2 * ((np.exp(l*t)) - 1 / Ar_39_K_40_r_ratio**2) ** 2

# 正（(e^(λt) − 1) / F_r²）：
v3 = F_std**2 * ((np.exp(l*t) - 1) / Ar_39_K_40_r_ratio**2) ** 2
```

由 J = (e^(λt) − 1) / F_r 的偏導 ∂J/∂F_r = (e^(λt) − 1)/F_r² 推得正確分子應為 `(np.exp(l*t) - 1)`。

### 影響

- typical λt ≈ 1.5e-10（t ~ 100 day, λ_K = 5.531e-10/yr） → e^(λt) − 1 ≈ 1.5e-10（極小）
- 錯誤公式算 e^(λt) − 1/F_r² ≈ 1 − 1/F_r²（量級 ~ O(1)）
- 結果：**σ_J 系統性高估數個數量級**
- J 出現在 age 公式 `T = ln(1 + J·F)/λ` 中，σ_J 透過 ∂T/∂J = F/(λ(1+JF)) 傳到所有 step 的 σ_age → 整條 σ_age pipeline 過去都是嚴重高估
- **age 中心值不變**（J 中心值未動），改的只有 σ_age

### 文獻支持

`pyADR_全module數學式審查_v5.docx` §3「J Volume σ_J」（Critical, P1）；Bevington & Robinson (1992) 標準 Gaussian error propagation。

### 驗證 checklist

- [ ] NO.65 muscovite（irradiation 0621-01C, 600–1500 °C）跑完，weighted mean age 中心值應仍在 9.77 ± 0.28 Ma 內
- [ ] σ_age 個別 step 跟舊版比應**變小**（高估部分消掉）
- [ ] 過去報過的 J value σ 都需重算

### 檔案改動

- `Utilities.py` L2864 — 一對括號 + 兩行 comment 註記
- `.work/.app_info.txt` — `3.8.1` → `3.8.3`（補上跳過的 `3.8.2` AutoPipeline σ_T0 SE-from-covariance fix）

---

### V3.8.3 (cont.)（2026-05-25）— AutoPipeline 大幅擴充：decay correction + σ method toggle + York isochron

同版本第二批變更，集中在 `AutoPipeline.py`（647 insert / 133 delete）。

#### 1. Decay correction 基礎建設

- 加 `LAMBDA_37 = log(2)/35.011`（³⁷Ar，t½ = 35.011 d）、`LAMBDA_39 = log(2)/(269·365.25)`（³⁹Ar，t½ = 269 yr）
- `decay_correct(t0_net, sig, delta_t_days, isotope)` helper — 對 net T0 做 e^(λΔt) 衰變回推
- `_extract_dat_date(filepath)` 從 .dat 的 `Project #` 行（YYYY/M/D）抽分析日期；fallback 用 line[1] 的 MM/DD + 檔案 mtime 推年
- `compute_delta_t_days(ogd_str, spd_date)` — OGD（parameters 內的 irradiation date）→ SPD（分析日期）相減得 Δt (days)
- `DELTA_T_DAYS` global，預設 0；UI load_signal 時自動算

#### 2. σ method toggle

- `SIGMA_METHOD` global，兩個選項：
  - `'standard'`（預設）：σ via `pcov[-1,-1]`（Li et al. 2019 Eq.1，跟 v3.8.2 行為一致）
  - `'calc_t0'`：σ via `std(|residuals|)/√n`（NTNU CalcT0Page convention）
- `_sigma_from_fit(residuals, n, popt, pcov, t, method)` helper 統一這兩條路徑
- 重構 `_fit_one()`、`_fit_with_errors()` 透過 toggle 取 σ
- 新增 `_both_sigmas()` 同時回傳兩種 σ 給 plot 對照顯示
- CalcT0Page sidebar 加 dropdown 切換 σ method；plot 左上角同時顯示兩個公式、用 ▶ 標出哪個是 active

**注意：** 此 toggle 只影響 AutoPipeline 內的 CalcT0Page，**不影響** NTNU_DataReduction.py 內的 CalcT0Page σ_T0（那條由教授指定 `std(|r|)/√n`，未經教授同意不會動）。

#### 3. Cycle 按鈕 z-score 著色

- `_cycle_z_scores()`：MAD-based robust z = |residual − median| / (1.4826·MAD)
- `_cs(sel, z)`：z < 1.8 藍（healthy）、1.8 ≤ z < 3 琥珀（suspicious）、z ≥ 3 紅（outlier）；未選的維持灰色背景紅字
- `_apply_btn_styles()` 統一刷新所有 cycle 按鈕的 style + tooltip（含 t / mV / z / used|excluded）

#### 4. `_signal_out_pass` 重寫為 serial per-isotope

按物理依賴順序選 cycle，不再五個 isotope 各自獨立挑：

1. **Ar37**：min `σ(T0_net)/|T0_net|` + n-penalty；用 `decay_correct` 把 37Ar 衰變回推
2. **Ar36**：以 step 1 結果反推 Ar36_ca = PR(36/37ca)·Ar37_dc，constraint Ar36_air > 0；score = Ar36_air/|T0_blank| + α·σ_air/|T0_blank| + n-penalty
3. **Ar38/39/40**：score = σ/T0 + γ·(1−R²) + n-penalty，constraint T0_sample > T0_blank

舊版邏輯保留為 `_legacy_signal_out_pass()`，若新 path 任一步失敗則 fallback 回去。

#### 5. AgeCalcPage isochron 升級（York 2004 + Wendt-Carl 1991）

- `york_regression(x, sx, y, sy, rho_xy=None)` — iterative slope refinement 直到 |Δb| < tol（max 50 iter），回傳 (slope, intercept, σ_slope, σ_intercept, MSWD)
- `_ratio_sigma(num, snum, den, sden, rho=0)` quadrature helper（可選 correlation）
- `_update_isochron_stats()` 從 placeholder 改為實算：
  - **Plateau weighted mean** + Wendt & Carl 1991 √MSWD 修正：MSWD > 1 用 σ_external = σ_internal·√MSWD；否則用 σ_internal
  - **Normal isochron** (x=39/36, y=40/36)：F = slope, σ_F = σ_slope
  - **Inverse isochron** (x=39/40, y=36/40)：F = −b/m（跟 v3.8.0 在 `getDFStatistics_sh` 的 fix 一致），σ_F propagation 含 σ_b, σ_m

#### 已知小議題（未修，待後續處理）

- `Utilities.LAMBDA_K` 還沒在 `Utilities.py` 定義；isochron age 計算用 `hasattr(Utilities, 'LAMBDA_K')` fallback 到 `5.543e-10`（Steiger-Jäger 1977），實際應該是 `5.531e-10`（Renne 2010）
- Inverse isochron `F_i = -b_i/m_i if abs(b_i) > 1e-30 else (1/(-m_i) ...)` 的 fallback 走的是 v3.7 buggy 公式，正常不會觸發但建議改成 0

#### 檔案改動

- `AutoPipeline.py` — 主要變動，+647 / −133 行

---

## V3.8.1（2026-05-11）— DiagramPlot UI + σ_36/σ_39 correlated-error fix

> **追加修正（同 commit）**：v3.7 `toDP` / `normalize_csv_to_v37` 寫進 CSV 的 σ（cols 90/92/95/97）是雙重計算的 buggy 值。原本 `getDFStatistics_sh` 優先讀這些 pre-calc σ，導致對「之前已轉成 98-col CSV」的樣品 σ fix 完全沒效果。改為**永遠從 raw component 重算 σ**（ratio 值仍可從 CSV 讀，σ 不讀）。同時修正 `normalize_csv_to_v37` 自己的 σ_36m / σ_39m / σ_40m 三處 quadrature bug。

### UI 改動

1. **Atmospheric marker** — DFN/DFI 大氣值標記從紅色實心圓 → 紅色 X（更不會被誤認為 data point）
2. **Group X-intercept marker** — DFI group 回歸線與 X 軸交點從彩色圓圈 → 彩色 X
3. **Int age std 標籤補上** — `UI/DiagramPlots_SH.py` 第 14 列原本被截斷沒有 setText，導致右下表 Int age 下方那格空白；現補上「Int age std」

### Bug 修正

4. **DFN/DFI 點 data 加入 group 失效** — 初次開 DiagramPlot 頁時 `getDFStatistics_sh` 沒傳 `return_points=True`，`iso_pts_DFN/DFI` 為空，click handler 立刻 return。改為初次呼叫也傳 `return_points/return_limits=True`，並同時 wire `_click_callback` 與 `current_xlim/ylim`，使用者不用先按 Apply 即可點選

5. **Age spectrum group ³⁹Ar% 累積算錯** — 原寫法 `ar39_pct = x1 − x0`（min→max 範圍），若群組中間夾雜未選步驟則把中間步驟的 ³⁹Ar 也算進去（screenshot 顯示 N=4 的群組報出 94.1% ³⁹Ar）。改為 `sum(stepw[i] for i in gi)`，只加總實際被選的 step

6. **σ_36(m) 與 σ_39(m) 雙重計算修正**（不直接改變典型雲母/長石樣品的 MSWD）— σ_36(m) 與 σ_39(m) 原本用「四個 component 的 quadrature 和」計算，但 Ar36_a 與 Ar39_k 本身就是用 raw 測量值減掉 Ca/Cl/c 干擾算出來的（σ 已含 raw σ），quadrature 等於把 corrections σ 雙重計算。套用與 v3.7.4-hotfix σ_40m 同款修正：
   - `σ²_36m = σ²_36a − σ²_36ca − σ²_36cl − σ²_36c`（兩處：normal isochron L767、inverse isochron L1142）
   - `σ²_39m = σ²_39k − σ²_39ca`（兩處：normal isochron L788、inverse isochron L1158）
   - 影響量級取決於 corrections 相對 raw 36Ar 的大小：對雲母/長石（Ca/K、Cl/K 低）的樣品影響 < 1-5%；對玄武岩 groundmass、輝石（Ca/K 高）的樣品影響較大
   - **不是** "MSWD 過低" 的成因（IsoplotR 跑 0621-01C 同樣得到 MSWD = 0.034，N=4，p(χ²)=0.97 — 對 mature 高 ⁴⁰Ar* 樣品，36Ar 接近 noise floor 時 σ_y_inv 本來就大，使 MSWD < 1 是正常分散統計，不是 bug）

### 檔案改動

- `Utilities.py` — σ_36m / σ_39m 雙重計算修正 ×4 處；marker `'o'` → `'x'` ×3 處；group ³⁹Ar% 累積修正 ×2 處
- `NTNU_DataReduction.py` — toDF_SH 初次呼叫加 `return_points/return_limits=True`、wire click callback、push xlim/ylim
- `UI/DiagramPlots_SH.py` — 補 row 14 「Int age std」標籤（檔尾被 iCloud 截斷）
- `.work/.app_info.txt` — `3.8.0` → `3.8.1`

---

## V3.8.0（2026-05-11）— DiagramPlot 數學式 critical fixes

### 修正 6 個 P1 公式 bug（皆有 primary literature 支持）

**`getDFStatistics_sh`（SH 樣品 step heating，Utilities.py L1479-L1530）：**

1. **Inverse isochron F 公式** — `F = 1/inv_slope` → `F = -inv_slope/iv`
   - Refs: Vermeesch (2024) Geochronology 6:398；Vermeesch (2018) Geosci Frontiers p.8
   - 原公式違反 York convention（Y = a + bX → F = −b/a）
   - 加入 slope-intercept covariance 進入 F_std 誤差傳播
2. **WMA 公式** — `wma += (1/σ²·T)/(1/σ²)` → `wma = Σ(T/σ²)/Σ(1/σ²)`
   - Refs: Vermeesch (2018) IsoplotR Eq.5；Schaen et al. (2021) GSA Bull. p.470
   - 原公式 loop 內 1/σ² 互消 → 退化為 Σ T_i（純加總）
3. **MSWD 參考點** — 從 arithmetic mean 改為 WMA
   - Ref: Schaen et al. (2021) GSA Bull. p.470

**`getDFStatistics_ls`（LS 樣品 / total fusion，Utilities.py L433-L490）：**

4. **Inverse isochron F 公式** — 原使用 `iv = linear(0, *popt)`（Y-intercept = trapped 36/40）當 F 用 → 物理錯誤
   - 改用 `F = -slope/intercept`（Vermeesch 2024 公式）
   - `iv`/`iv_std` 變數保留為 Y-intercept 數值（return 介面不變）
5. **WMA 公式** — 同 #2，同樣修正
6. **MSWD 參考點** — 同 #3，同樣修正

### 影響範圍

⚠️ 此 release **影響每一份過去用 pyADR 跑出來的 Int age 與 WMA**：
- SH 樣品的 Int age（過去 F 用 1/slope，age 系統性偏低）
- LS 樣品的 Int age（過去 F 用 trapped 36/40，age 完全錯）
- SH/LS 所有 WMA（過去等同 Σ T_i 而非加權平均）
- SH/LS 所有 MSWD（過去用算術平均當參考點）

**建議**：
1. 用 SYL31 LS 資料集（`notes/LS_test_2026-05-11/SYL31_LS_88col.csv`）驗證新版
   - 論文值：115.4 ± 3.9 Ma（Sylhet Trap 玄武岩，NTU 碩論 R94224113, 2007）
   - 預期 v3.8 Date ≈ 115 Ma、WMA ≈ 115 Ma
2. 過去樣品需重算 isochron age + plateau WMA
3. 已投稿/已發表結果如使用 Int age 或 WMA → 評估是否需要 erratum

### 文獻引用

完整推導、quote 與 Convention 一致性表見 `pyADR_全module數學式審查_v3.docx` 附錄 A（在 iCloud 開發資料夾）。

主要 refs：
- Vermeesch, P. (2024). Errorchrons and anchored isochrons in IsoplotR. *Geochronology* 6: 397–407.
- Vermeesch, P. (2018). IsoplotR: A free and open toolbox for geochronology. *Geoscience Frontiers* 9: 1479–1493.
- Schaen, A.J. et al. (2021). Interpreting and reporting 40Ar/39Ar geochronologic data. *GSA Bulletin* 133: 461–487.
- Powell, R. et al. (2020). Robust Isochron Calculation. *Geochronology*.
- Kuiper, K.F. (2002). The interpretation of inverse isochron diagrams in 40Ar/39Ar geochronology. *EPSL* 203: 499–506.

### 檔案改動

- `Utilities.py` — `getDFStatistics_ls` (L433-L490) 與 `getDFStatistics_sh` (L1479-L1530)，~110 行修正
- `NTNU_DataReduction.py` — 無改動
- `AutoPipeline.py` — 無改動（內部 WMA / F 已正確）
- `.work/.app_info.txt` — `3.7.4` → `3.8.0`

### 仍待處理（後續版本）

- York regression（取代 OLS curve_fit；Vermeesch 2024 / Powell 2020）
- Errorchron Model 3a（玉里帶 retrograde excess Ar 樣品用）
- Anchored isochron（step 數少的備援）
- Spectrum vs inverse isochron 一致性檢查（防 false isochron — Kuiper 2002）
- T0 σ 計算改用 pcov[-1,-1]（舊版 Utilities.py L76）
- J Calc / Salt Calc auto-outlier 從 ±SEM 改 Chauvenet

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
