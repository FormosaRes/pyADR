![logo](.work/logo.png)
# pyADR — NTNU modified fork (v3.9.11)

40Ar/39Ar data reduction tool with GUI. Modified fork of [pyADR](https://github.com/AndrewLiu0725/pyADR) (original by **An-Jun (Andrew) Liu**), now maintained by **PANG Chi-Hsiu (Academia Sinica)**.

This fork adds: a full batch-automation pipeline (**Argon Pipeline**: Calculate T₀ → MassRatio → AgeCalc + Datum), modern isochron math (York 2004 default, Vermeesch 2018/2024), editable J / parameters with on-the-fly recompute, ³⁶Ar-blank sensitivity tools (age spectrum + inverse isochron), a **mineral closure-temperature calculator** (Dodson 1973; hornblende / muscovite / biotite / K-feldspar), 2σ reporting with uncertainty budgets, a bilingual (中 / EN) in-app Help & formulas reference, Excel native chart export, step-heating diagram types (DFD/DFS/DFM + grouped 3D plane fit), performance optimization, and auto-update notification.

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

點本頁右上方綠色 **Code** 鈕 → **Download ZIP**。檔名是 `pyADR-main.zip`，**解壓到 `C:\` 根目錄**，會得到 `C:\pyADR-main\`（**路徑不要含中文或空白**）。

或用 git（之後想 git pull 更新比較方便）：
```
cd C:\
git clone https://github.com/FormosaRes/pyADR.git pyADR-main
```

### Step 3 — 一鍵安裝

進到 `C:\pyADR-main\` → **雙擊 `setup.bat`**

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
cd C:\pyADR-main
python install.py
```

效果跟 setup.bat 一樣。

---

## Update

更新到新版有兩種方式：

### 方式 A：Git pull（推薦給用 git clone 安裝的）

```
cd C:\pyADR-main
git pull
```

完成。`.py` 檔案會更新，數據（`Data/`、`Figures/`、`.work/setting.csv`）不會被動到。

### 方式 B：重新下載 ZIP

1. 備份 `Data/`、`Figures/`、`.work/setting.csv`
2. 刪除舊 `C:\pyADR-main\` 整個資料夾
3. 重新 Download ZIP → 解壓到 `C:\` → `python install.py`
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
| `CHANGELOG.md` | 完整版本變更紀錄 (V2.5 → v3.8.96) |
| `README_origin.md` | 原版 pyADR 的 README (Andrew Liu) |

---

## 子程式功能一覽（Program modules）

主畫面（Home）每顆按鈕對應一個子程式。標準流程是由上而下的定年主鏈（Calculate T₀ → Mass Ratio → J → Age → Diagram / Datum），**Argon Pipeline** 把主鏈整條自動化，其餘為輔助工具。各步驟以 CSV 銜接：前一步的輸出即下一步的輸入。

| 子程式（Home 按鈕） | 功能 | 輸入 → 輸出 |
|---|---|---|
| **Calculate T₀** | 質譜訊號外推到 inlet 時刻 t=0，逐同位素（³⁶–⁴⁰Ar）擬合 blank 與 signal 的 T₀，含 Δt decay correction | raw `.dat`（mass + preline）→ T₀ CSV |
| **Mass Ratio** | 由各同位素 T₀ 算質量歧視校正後的同位素比值 | T₀ CSV（mass + preline）→ measurement CSV |
| **J Calculation** | 由標準樣品年代反算中子通量參數 J（及 σ_J） | 標準樣 measurement → J、σ_J |
| **Salt Calculation** | 鹽類 / 特殊樣品專用校正流程 | 對應 raw 檔 → 校正結果 |
| **Parameter Setting** | 集中設定生產比、大氣比、λ、J、cycle 數等常數（全流程共用） | 手動輸入 → `.work/setting.csv` |
| **Age Calculation** | 由 measurement + J + 常數算單樣品年代（F、T、⁴⁰Ar\*%、Ca/K、Cl/K） | measurement CSV + 參數 → age CSV |
| **Statistics** | 多檔 T₀ / 比值統計（挑 blank cycle、離群檢查） | 多個 T₀ / 比值檔 → 統計摘要 |
| **Diagram Plots** | 出圖：age spectrum、normal / inverse isochron（York 2004 / Vermeesch）、Ca-K、Cl-K、degassing pattern（DFD/DFS/DFM）、3D 平面擬合 | age / datum CSV → PNG + 統計（plateau、WMA、MSWD、isochron age） |
| **Datum Publication** | 產出投稿級 datum 總表（88 欄）與 isochron ratio 表（ISOr） | age / measurement CSV → publication CSV |
| **Argon Pipeline** | 上述主鏈的批次自動化（Calculate T₀ → MassRatio → AgeCalc + Datum 一次跑完），含可編輯 J 即時重算、³⁶Ar-blank 敏感度、plateau 勾選、`.adr` session 存讀 | raw `.dat` 一組 → 全套輸出（CSV + PNG + datum） |
| **Closure Temperature** | 獨立工具，兩分頁：①**Single mineral** — Dodson (1973) 礦物封閉溫度 Tᴄ 計算器（14 個 ⁴⁰Ar/³⁹Ar 定年計 preset，Schaen et al. 2021 GSA Bull. 133, Table 5，或自訂 E / D₀ / 幾何 / 粒徑 / 冷卻速率；E 單位 kJ/kcal 可切換）②**Cooling history (T–t)** — 輸入多個定年計（Ar/Ar 礦物 + 裂變徑跡 / (U-Th)/He / U-Pb 等其他熱定年系統）的年代 + Tᴄ，繪降溫曲線、標段間冷卻速率、Tᴄ 參考帶，可 Save PNG/PDF/SVG | 擴散參數 + 冷卻速率 → Tᴄ、對照表、Tᴄ–冷卻速率曲線；多定年計 (age, Tᴄ) → T–t 冷卻路徑 + 冷卻速率 + 圖片匯出 |

> 與 pipeline 數據解耦的純工具：**Closure Temperature**（不讀 / 不寫任何樣品 CSV，只做參數計算）。

---

## Changelog 摘要

### v3.8.9 – v3.9.4 (2026-05 → 2026-07) — 摘要

> **v3.9.4**：冷卻史段間冷卻速率標籤移到路徑線一側 + 加半透明白底，不再壓到線與資料點。
> **v3.9.3**：冷卻史表格每列加 **Show 勾選框**，可選擇哪些定年計畫在 T–t 圖上（取消的不畫但保留在表格）。
> **v3.9.2**：冷卻史圖清爽化 — 移除資料點旁礦物/方法文字（改由右側 Tᴄ 帶 + Method 欄識別）；Tᴄ 帶標籤改用礦物縮寫（Apatite fission track→AFT、Hornblende→Hbl…）。
> **v3.9.1**：Single mineral 對照表拿掉捲軸（六列全顯示）；冷卻史新增 **Method 欄**標示定年方法（⁴⁰Ar/³⁹Ar、Rb–Sr、U–Pb、FT、(U-Th)/He），下拉加 **Rb–Sr** 系統。
> **v3.9.0**：冷卻史細節收尾 — Tᴄ 參考帶寬**與 ±(°C) 同步**、帶**顏色可選**（Band 欄）、Single mineral 算出的 Tᴄ 可**一鍵加到 Cooling history**。
> **v3.8.99**：冷卻史（T–t）加 **Save 圖片**（PNG/PDF/SVG）、**其他定年方法**（裂變徑跡 / (U-Th)/He / U-Pb 標稱 Tᴄ，Reiners & Brandon 2006）可與 Ar/Ar 混用、**Tᴄ 參考帶**（發表級 T–t path 風格）。
> **v3.8.98**：冷卻史表格新增 **↑ / ↓** 按鈕，可上下移動列調整礦物順序（覆寫的 Tᴄ 隨列保留）。
> **v3.8.97**：Closure Temperature 新增 **Cooling history (T–t) 分頁**：輸入多個定年計的年代 + 封閉溫度，繪出溫度–時間降溫曲線（含年代/溫度誤差棒、依年代連線、各段冷卻速率標註）。新增純函數 `cooling_segments()`。
> **v3.8.96**：Home 頁新增 **Closure Temperature 主按鈕**（Argon Pipeline 下方）；計算器活化能 E 單位可切換 **kJ/mol ↔ kcal/mol**（切換不動 preset、Tᴄ 不變）。
> **v3.8.95**：Closure Temperature 入口搬家：主程式 Home 頁 **Menu → Closure Temperature** + AutoPipeline **AgeCalc+Datum 左側按鈕列**（Parameter 下方），移除 v3.8.94 的 Tools 選單。礦物擴散參數庫改引 **Schaen et al. (2021) GSA Bulletin 133, 461–487, Table 5**，5 → **14 個 ⁴⁰Ar/³⁹Ar 定年計**（單位改 kJ/mol、m²/s，可直接對照論文表格）；self-test 14 個 nominal T_cb 全數 ±6 °C 吻合（anorthoclase 為 non-Arrhenian 已知例外，UI 有警語）。
> **v3.8.94**：新增 **Tools → Closure Temperature (Dodson 1973)** 礦物封閉溫度計算器。可選礦物 preset（角閃石／白雲母／黑雲母／鉀長石，內建 Harrison 1981/1985/2009、Grove & Harrison 1996、Foland 1974 擴散參數）或自訂 E / D₀ / 幾何 / 粒徑 / 冷卻速率，即時算 Tᴄ、對照表與 Tᴄ–冷卻速率曲線。純參數工具，與 pipeline 解耦。
> **v3.8.89–93**：in-app Help 改**中英雙語**（左下角 CN/EN 切換）+ 補 isochron 兩種回歸方法（OLS / York）物理意義 + 新增 σ(T₀) 分頁；DiagramPlot SH isochron 預設也改 **York**；修「在 AutoPipeline 按 Help 會跳出開機 splash」。
> **v3.8.88**：修 Plot Controls 改軸範圍按 Apply 後，切到 diagram 分頁圖才刷新（分頁顯示時自動重新縮放 PNG）。
> **v3.8.87**：³⁶Ar-blank 敏感度對話框加「Inverse Isochron」檢視（拉 ³⁶ blank 看 trapped ⁴⁰/³⁶、age、各溫階共線性怎麼動）。
> **v3.8.86**：從 AutoPipeline 進 Parameter 頁後，Return 直接回 Argon Pipeline（session 保留），不必再繞首頁重載。
> **v3.8.85**：AutoPipeline 三頁（Calculate T₀ / MassRatio / AgeCalc）左側按鈕列新增 **Parameter** 鈕，直接開主程式的 Parameter Settings 頁。
> **v3.8.84**：AgeCalc 控制列新增可編輯 **J value**（及 atm）欄位，按 Recalculate 會用新 J 重跑 pipeline，所有輸出（表/banner/圖/datum/export）一致更新。
> **v3.8.83**：啟動時 splash/loading 畫面改成**一啟動就出現**（先顯示 splash 再跑 numpy/pandas/matplotlib 等重 import），不再讓使用者對著黑 cmd 等。
> **v3.8.82**：isochron(normal/inverse)在 MSWD>1 時 σ 加 √MSWD 外部誤差膨脹（對齊 plateau / IsoplotR）；Age Spectrum 面板新增 total-fusion 的 σ_age budget（J / ⁴⁰Ar* / ³⁹Ar_K 各佔幾 %）。
> **v3.8.81 啟動加速**：移除只為了 `r2_score` 而拖累冷啟動約 7.5s 的 sklearn import（改用等價 numpy 實作，數值 bit-identical），splash 最短顯示 3s → 1s。

這段主力在 **AutoPipeline（主畫面「Argon Pipeline」）** 的三個子頁面與科學輸出修正，逐版細節見 `CHANGELOG.md`：

- **Calculate T₀**：Signal T₀ Range 盒鬚圖輔助挑 blank cycle、Δt decay correction、σ_T0 SE-from-covariance、`.adr` session 存讀。
- **AgeCalc + Datum**：Excel 風格分頁（Summary / Age Spectrum / Inverse・Normal Isochron / Ca/K / Cl/K / Degassing / ⁴⁰Ar(r)%）、York 2004 預設、plateau step 勾選 + Auto plateau、³⁶Ar 大氣敏感度試算、MSWD 顏色提示 + inverse-isochron 裁判 readout、年代結果一律 **2σ**、Copy table、Plot Controls 軸範圍顯示現值。
- **科學輸出修正（已用 NO.65 muscovite 9.77 ± 0.28 Ma 對照）**：`calcAge` stale-index（⁴⁰Ar(r)% / isochron / Ca/K）、Ca/K 方向、Total Fusion 改真 gas-weighted（ΣAr40\*/ΣAr39K）、σ_J 括號 bug、isochron F = −slope/intercept（York / Vermeesch 2024）。
- 主畫面「Auto Pipeline」更名 **Argon Pipeline**。

### v3.8.8 (2026-05-26)

**Select-style sub-window 加上 Return 按鈕**。`TypeSelect`、`StatSelect`、`JSelect`、`SaltSelect`、`SaltStatSelect`、`DiagramSelect`、`DatumSelect` 七個分支選擇子視窗原本沒 Return 按鈕（只能透過 menubar 回主頁），跟其他子頁面介面不一致。新增 `_add_return_button` helper 在左側標準位置（`QRect(0, 200, 91, 51)`）放上按鈕，App init 加 7 個 `clicked → toMain` 連線。UI/*.py 保持不動。

### v3.8.7 (2026-05-26)

**Select-style sub-window 按鈕響應式置中**。`DiagramSelect`、`TypeSelect`、`StatSelect`、`JSelect`、`SaltSelect`、`SaltStatSelect`、`DatumSelect` 七個分支選擇子視窗原本用絕對 `QRect(210, y, 421, 51)` 設計給 800px 寬視窗，視窗放大時按鈕卡左邊。新增 `_make_select_page_responsive` helper 攔 `resizeEvent` 動態置中，wrapper class 各加一行呼叫。HomePage 已用 layout-based 不受影響；UI/*.py 檔保持原樣不動（auto-generated 容易被覆蓋）。

### v3.8.6 (2026-05-26)

**DiagramPlot UX 重整 + Main/Help 選單 + PlaneFit3D 數學文件 + σ_40 fix**。

DiagramPlot SH：DFN/DFI 拿掉視覺干擾的「pre-outlier-removal」第一條 fit line；regression annotation 從圖上搬到上方灰色 infoLabel（跟滑鼠座標合併），切到 non-isochron panel 時自動清空；NTNU 主 GUI 加上 OLS / York 2004 dropdown（之前只有 AutoPipeline 有）。

Main / Help 選單：DiagramPlots_SH 跟 AutoPipelineWindow 都補上 menubar，Help 開 7-tab 對話框（Plateau/WMA, Isochron, MSWD, Age, Ar components, 3D Plane Fit, References），共用單一來源。

PlaneFit3D：審查 Kent (1990) + Wu (2007) NTU 碩論 → `PlaneFit3D.py` 本體沒 bug。但 caller-side `s40 = np.hypot(σ_40r, σ_40a)` 雙重計算 σ_40a（40Ar(r) 跟 40Ar(a) 透過 40r = 40m − 40a − 40K 負相關，跟 v3.8.1 修的 σ_36m/σ_39m 同 pattern）。修為 `sqrt(max(σ²_40r − σ²_40a, 0))`。σ_36 / σ_39 inputs 驗證乾淨。FORMULAS.md 新增 §11 完整數學推導。

Splash：3 秒最短顯示時間、版本/日期改 runtime QPainter overlay 不 baked-in、credits 改 NTNU Ar/Ar Lab + Prof. Meng Wan (Mary) Yeh。pyADR.bat 改 `if errorlevel 1 pause` 正常關閉時 cmd 自動收掉。

### v3.8.5 (2026-05-26)

**isochron regression math 補丁 + 方法 toggle + MSWD label 釐清**。

A1 補對稱漏修：Normal isochron `n_std` 從 v3.7 留下的 OLS-on-error-bars 寫法（數學上沒意義）改用 `sqrt(pcov[1,1])`，跟 v3.8.0 已修的 inverse isochron 同步。

A3 跨 path 統一：AutoPipeline `_update_isochron_stats` 的 σ_F propagation 加入 slope-intercept covariance 項 `-2(m/b³)·cov(m,b)`，跟 Utilities.getDFStatistics_sh 一致。York regression 加回傳 `cov_ab`。

A2 + B3 部分實作：isochron 回歸方法做成 toggle（OLS / York 2004，預設 OLS 維持向後相容）。York 算 slope/intercept 跟 OLS 不同會影響 age 中心值，所以做成可切換不強制。AgeCalcPage 加 dropdown，切換自動重生 DFI/DFN PNG。

B1 MSWD label 釐清：原本 stat 區只標「MSWD」混淆 plateau 跟 regression 兩種。現在 stat 區明確標「Plateau MSWD」，inverse isochron 圖上額外標註 regression MSWD + 用什麼方法。

B2 撤回：審查時建議的傾斜 error ellipse 經 Schaen 2021 / 文獻盤查確認不是 Ar/Ar 主流（IsoplotR 風格 vs McDougall & Harrison + ArArCALC + NTNU code 慣例不同），維持 axis-aligned。

### v3.8.4 (2026-05-25)

**AutoPipeline AgeCalcPage isochron 公式修正 + λ 統一來源**。

v3.8.3 (cont.) 在 `_update_isochron_stats` 加 York 2004 isochron 時寫錯主公式：`F_i = -b_i/m_i`（intercept/slope）。文獻正解是 `F = -slope/intercept = -m_i/b_i`（Vermeesch 2024 Geochronology 6:398 page 2, Li & Vermeesch 2021 Eq. 5）。WIP 算出來的是 1/F 不是 F，對 10 Ma 樣品偏高約 18%。σ_F propagation 偏導跟著修，inverse b≈0 fallback（v3.7 buggy `1/(-m_i)`）刪掉改 degenerate 顯示。

λ 統一：原 `_update_isochron_stats` 內 4 處 hardcoded `5.543e-10`（Steiger-Jäger 1977），加上 2 處 `hasattr(Utilities,'LAMBDA_K')` fallback（Utilities 從未定義 LAMBDA_K）。calcAge 主路徑用 parameters.csv 內 5.49e-10，所以 plateau age 跟 isochron age 之間有 ~1% 系統性偏移。加 module-level `LAMBDA_K = 5.49e-10`，`AutoPipelineWindow.set_context()` 從 `params['λ for age calculation']` 注入，所有 isochron age / σ_age 改用同一條 λ。

不影響 plateau age、calcAge 主路徑、Utilities、DiagramPlot SH。NO.65 muscovite 驗證：Inv. Iso 從 ~11.5 Ma 應變回 ~9.77 Ma；SYL31 LS Sylhet Trap basalt（115.4 ± 3.9 Ma）作為第二驗證樣品。

附加：`NTNU_DataReduction.py` 加 `setWindowIcon` + `SetCurrentProcessExplicitAppUserModelID`，PyQt5 主視窗 taskbar 圖示顯示 pyADR.ico 而非 Python 預設圖。`pyADR.ico` 多解析度 (16/24/32/48/64/128/256) 加入 `.work/`，logo 拉伸填滿 ~94% canvas。可選 `pyADR_launch.vbs` silent launcher（不彈 cmd 視窗）。

### v3.8.3 (2026-05-25)

**`Utilities.py:getJVolumeStatistics` σ_J 括號 bug fix + AutoPipeline 大幅擴充**。

#### σ_J bug

`getJVolumeStatistics` L2864 σ_J 計算有 operator precedence 造成的括號錯誤：

```python
v3 = F_std**2 * ((np.exp(l*t)) - 1 / Ar_39_K_40_r_ratio**2) ** 2   # 錯
v3 = F_std**2 * ((np.exp(l*t) - 1) / Ar_39_K_40_r_ratio**2) ** 2   # 正
```

由 `J = (e^(λt) − 1) / F_r` 的偏導 `∂J/∂F_r = (e^(λt) − 1)/F_r²` 推得正確分子是 `(e^(λt) − 1)`。typical `λt ≈ 1.5e-10`，錯誤公式算 `e^(λt) − 1/F_r² ≈ 1 − 1/F_r²`，量級錯了好幾個 order，σ_J 系統性高估數個數量級，並透過 `∂T/∂J = F/(λ(1+JF))` 傳到所有 step 的 σ_age。age 中心值不變（J 中心值未動），只有 σ_age 變小。

#### AutoPipeline 擴充（同版本 cont. commit）

- **Decay correction 基礎建設**：`LAMBDA_37` / `LAMBDA_39` (Renne 2010 / 2011 半衰期)、`decay_correct()` helper、`_extract_dat_date()` 從 .dat header 抓 SPD、`compute_delta_t_days()` 算 Δt = SPD − OGD、`DELTA_T_DAYS` global 與 CalcT0Page Δt UI 自動更新
- **σ method toggle**：`SIGMA_METHOD` global，UI dropdown 切換 `'standard'`（pcov[-1,-1]，v3.8.2 行為）與 `'calc_t0'`（std(|r|)/√n，NTNU CalcT0Page convention），plot 上同時顯示兩種公式對照（active 用 ▶ 標）。**不影響 NTNU_DataReduction CalcT0Page**（Lee 老師指定的 σ 寫法不動）
- **Cycle 按鈕 z-score 著色**：MAD-based robust z-score，藍/琥珀/紅三段，tooltip 含 t / mV / z / used|excluded
- **`_signal_out_pass` serial per-isotope 重寫**：Ar37（含 decay correction）→ Ar36（用 Ar37_dc 推 Ar36_ca、constraint Ar36_air > 0）→ Ar38/39/40（σ/T0 + R² penalty）。舊邏輯保留為 `_legacy_signal_out_pass()` fallback
- **AgeCalcPage isochron 升級**：York 2004 regression + Wendt & Carl 1991 √MSWD 修正（MSWD > 1 用 σ_external = σ_internal·√MSWD）+ Normal/Inverse isochron age 從 placeholder 改實算

### v3.8.2 (2026-05-13)

**AutoPipeline `σ_T0` SE-from-covariance fix + PlaneFit3D refactor**。

AutoPipeline 內 baseline / signal `_fit_one` / `_fit_with_errors` 把 σ_T0 從 `std(|residuals|)/√n` 換成 `sqrt(pcov[-1,-1])`（Li et al. 2019 Eq.1），舊式系統性低估約 4×。NTNU_DataReduction CalcT0Page 的 σ 寫法是 Lee 老師指定，**不動**。`PlaneFit3D.py` 大幅 refactor（+358 行），整合 Kent 1990 ML σ-cap。

### v3.8.1 (2026-05-11)

**DiagramPlot UI 修正 + σ_36/σ_39 雙重計算 hotfix**。

UI：DFN/DFI 大氣值與 group X-intercept marker 從圓圈改為 X；補上 `UI/DiagramPlots_SH.py` 被截斷的「Int age std」row label。

Bug：(a) DFN/DFI 不能點 data 加入 group — 初次顯示時 `getDFStatistics_sh` 沒傳 `return_points=True`，`iso_pts` 為空。(b) Age spectrum group ³⁹Ar% 累積算錯（`x1−x0` 是 min→max span，含未選步驟），改為 `sum(stepw[i] for i in gi)`。

σ：`σ_36(m)` 與 `σ_39(m)` 原本用四個 component quadrature 加總，但 `Ar36_a` / `Ar39_k` 本身包含 raw σ + corrections σ，等於把 corrections 算兩遍。套用與 v3.7.4-hotfix σ_40m 同款的反向減法 `σ²_36m = σ²_36a − σ²_36ca − σ²_36cl − σ²_36c`、`σ²_39m = σ²_39k − σ²_39ca`，並讓 `getDFStatistics_sh` **永遠從 raw component 重算 σ**（避免讀到 toDP / normalize_csv_to_v37 寫進舊 CSV 的 buggy pre-calc σ）。對雲母/長石樣品影響 < 5%，對玄武岩 groundmass / 輝石較大。IsoplotR 跨驗證確認 MSWD < 1 對 mature 樣品是正常統計現象，不是 bug。

### v3.8.0 (2026-05-11)

**DiagramPlot 數學式 critical fixes** — 修正 6 個 P1 公式 bug，全部有 primary literature 支持。

`getDFStatistics_sh` (SH step heating)：(1) Inverse isochron F 公式 `F = 1/inv_slope` → `F = −b/a`，符合 York convention（Vermeesch 2024 Geochronology 6:398），並加入 slope-intercept covariance；(2) WMA loop 內 `1/σ²` 互消的 bug → `Σ(T/σ²)/Σ(1/σ²)`（Vermeesch 2018 IsoplotR Eq. 5）；(3) MSWD 參考點從算術平均 → WMA（Schaen et al. 2021 GSA Bull. p.470）。

`getDFStatistics_ls` (LS / total fusion)：原用 Y-intercept (= trapped 36/40) 當 F → 物理錯誤，改用 `F = −slope/intercept`；WMA、MSWD 同 SH 同樣修正。

影響：所有 v3.7.x 跑出來的 Int age（SH 系統性偏低；LS 完全錯）、WMA（等同 Σ T_i）、MSWD（參考點錯）。建議所有過去樣品重算。SYL31 LS 驗證資料集（Sylhet Trap 玄武岩 115.4 ± 3.9 Ma，NTU 碩論 R94224113）。

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
