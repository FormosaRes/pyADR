# pyADR — NTNU_DataReduction / Utilities 更新日誌

版本追蹤：V2.5 → V2.6 → V2.7 → V2.7.1 → V3.0 → V3.0.1 → V3.1 → V3.1.1 → V3.2 → V3.3 → V3.4 → V3.4.1 → V3.5 → V3.6 → V3.7 → V3.7.1 → V3.7.2 → V3.7.3 → V3.7.4 → V3.8.0 → V3.8.1 → V3.8.2 → V3.8.3 → V3.8.4 → V3.8.5 → V3.8.6 → V3.8.7 → V3.8.8 → V3.8.9 → V3.8.10 → V3.8.11 → V3.8.12 → V3.8.13 → V3.8.14
最後整理日期：2026-05-27
整理者：Claude (based on git-style diff across all versions)

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
