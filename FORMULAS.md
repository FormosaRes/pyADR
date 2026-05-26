# pyADR Formulas — ⁴⁰Ar/³⁹Ar Reduction Math Reference

**Version**: v3.8.1 (2026-05) · **Scope**: T0 fitting → Mass Ratio → Air Ratio → J → Age → Datum Publication

> **v3.8.0 update**: §10 (DiagramPlot) rewritten to reflect corrected inverse-isochron F = −b/a, inverse-variance-weighted WMA, and WMA-referenced MSWD per Vermeesch (2024, 2018) and Schaen et al. (2021). Previous §10 description matched the buggy v3.7.x code (§10.x note retains the bug history for traceability).
>
> **v3.8.1 update (2026-05)**: Documentation-only changes — no math code modified. (1) §1 T0 sigma now properly flagged as **math bug** (was previously described as "NTNU lab convention" — too soft); cross-references the correct intercept-SE formula and AutoPipeline `_fit_one` v3.8.2 patch. (2) §6 J-Volume now flags the **σ_J bracket bug** at `Utilities.py:2864` (operator precedence drops a critical pair). (3) §10.7 flags that the plateau "avg_age" still uses arithmetic `np.mean`, not the v3.8-corrected WMA in §10.5. (4) §10.8 adds a warning about isochron-intercept SE computed by running OLS on the error bars (`curve_fit(linear, x_std, y_std)`) at `Utilities.py:389-390, 965-966` — mathematically meaningless. See §⚠ for the consolidated outstanding-bug list synced with the v5 math-audit report.

This document is a one-stop reference for every numeric formula pyADR evaluates, written as math (LaTeX) plus the corresponding `.py` line. Error propagation is derived from first-order partials of each expression as **actually coded** — pyADR mixes proper quadrature (`sqrt(Σ(∂F/∂x · σ_x)²)`) with linear-sum approximations (`F·Σ|σ_x/x|`); both are documented faithfully. Where the code's choice diverges from the McDougall & Harrison (1999) / Koppers (2002) convention, a **Note** flags it.

Symbol convention:
- `mᵢ` = measured intensity of ⁴ⁱAr (already T0-extrapolated, blank-corrected, decay-corrected)
- `aᵢ` / `kᵢ` / `caᵢ` / `clᵢ` / `rᵢ` = atmospheric / K-derived / Ca-derived / Cl-derived / radiogenic component
- `σ_x` = 1σ uncertainty on `x`
- `λ_total` = total ⁴⁰K decay constant (parameter `constants[14]`, /yr)

---

## 0. Generic uncertainty helpers

`Utilities.py:124–128`

**Ratio (proper quadrature):**

$$
\sigma_{y/x} \;=\; \frac{y}{x}\sqrt{\left(\frac{\sigma_y}{y}\right)^{2}+\left(\frac{\sigma_x}{x}\right)^{2}}
$$

∂(y/x)/∂y = 1/x, ∂(y/x)/∂x = −y/x². The implementation expects callers to pass the ratio value as the 5th arg.

**Difference / sum (proper quadrature):**

$$
\sigma_{y\pm x} \;=\; \sqrt{\sigma_x^{2}+\sigma_y^{2}}
$$

∂(y±x)/∂y = ±1, ∂(y±x)/∂x = ±1.

> **Note**: Several places in pyADR (e.g. `getJVolumeStatistics`, `calcAge`, `calculateSlatCa`) use the **linear-sum** approximation `|F|·(σ_a/|a| + σ_b/|b|)` instead of quadrature. This is conservative (slightly overestimates σ when terms are independent) and is preserved here as-is for backward compatibility with NTNU lab outputs.

---

## 1. T0 extrapolation — `calculateT0` / `REcalculateT0`

`Utilities.py:142–305`

For each isotope i ∈ {36,37,38,39,40} the raw voltage trace `(t, V)` is fit with one of:

**Linear** (`fit_func_list[0]`, `Utilities.py:132`):

$$
V(t) = a\,t + b \quad\Longrightarrow\quad T_0 \equiv V(0) = b
$$

**Average** (`fit_func_list[1]`, `Utilities.py:135`):

$$
V(t) = a \quad\Longrightarrow\quad T_0 = a
$$

**T0 sigma (as coded — `Utilities.py:187, 216, 275, 294`):**

$$
\sigma_{T_0,i}^{(\text{coded})} \;=\; \frac{\mathrm{std}\!\left(\,\bigl|\,V_j - \hat{V}(t_j)\bigr|\,\right)}{\sqrt{N-n_{\text{out}}}}
$$

where `n_out` is the number of cycles masked out by the outlier rule

$$
|V_j-\hat V(t_j)| > \sigma_{T_0,i}^{(\text{prev})} \quad\text{and}\quad R^2 \le 0.8
$$

(at most 4 cycles removed; up to 1 retry).

**Goodness:** R² from `sklearn.metrics.r2_score`.

> ⚠ **Math bug — σ_T0 is not the intercept SE.** The coded formula above is the standard error of the *mean* (`std(residuals)/√N`), not the SE of the y-intercept of a linear fit. For typical step-heating cycle times `t ∈ [320, 600] s` with `t̄ ≈ 460 s` ≫ 0, the intercept extrapolated to `t=0` carries a large lever-arm term that is completely missing here.
>
> **Correct intercept SE (Li et al. 2019 Eq. 1):**
>
> $$
> \sigma_{T_0,i}^{(\text{correct})} \;=\; \sigma_r \sqrt{\frac{1}{N} + \frac{\bar t^{\,2}}{\sum_j (t_j - \bar t)^2}}
> \;=\; \sqrt{\mathrm{pcov}[-1,-1]}\quad\text{from}\quad\mathrm{curve\_fit}(f, t, V)
> $$
>
> where `σ_r = std(residuals, ddof=N−p)` is the unbiased residual SD and `pcov` is the regression covariance matrix.
>
> **Empirical impact (NTNU 0621-01C 1100 °C step, 10 cycles, t ∈ [320, 601] s):**
>
> | Isotope | T0           | σ_coded (`std/√N`) | σ_correct (`pcov`) | ratio |
> |---------|--------------|--------------------|--------------------|-------|
> | ³⁶Ar    | 3.58 × 10⁻⁴  | 4.6 × 10⁻⁶         | 4.6 × 10⁻⁵         | **10.1×** |
> | ³⁷Ar    | 1.62 × 10⁻⁴  | 5.6 × 10⁻⁶         | 5.5 × 10⁻⁵         | 9.8×  |
> | ³⁸Ar    | 6.44 × 10⁻⁴  | 6.9 × 10⁻⁶         | 6.9 × 10⁻⁵         | 10.0× |
> | ³⁹Ar    | 1.91 × 10⁻²  | 9.6 × 10⁻⁶         | 9.8 × 10⁻⁵         | 10.2× |
> | ⁴⁰Ar    | 2.04 × 10⁻²  | 4.8 × 10⁻⁶         | 5.8 × 10⁻⁵         | 11.9× |
>
> The coded form underestimates σ_T0 by **~10×** for every isotope. This propagates through `getJVolumeStatistics`, `calcAge`, plane-fit weighting, and downstream WMA / MSWD computations — every reported σ in pyADR currently inherits this underestimate.
>
> **Status**: Fixed in AutoPipeline `_fit_one` (v3.8.2 patch — uses `sqrt(pcov[-1,-1])` with Li 2019 closed-form fallback). Legacy `Utilities.calculateT0` / `REcalculateT0` (this section) still uses the buggy form pending advisor review; the upstream `AndrewLiu0725/pyADR` GitHub repo uses a different but also-incorrect formula `std(|residuals|)` (no `/√N` divisor). Reference: Li, X., Naeher, U. and Pross, J. (2019). *Mass spectrometric data processing in stable isotope analysis: regression-based standard errors of the y-intercept.* J. Mass Spectrom. **54**, 145–152, Eq. 1.

---

## 2. T0 Statistics — `getT0Statistics` / `REgetT0Statistics`

`Utilities.py:2529–2625`

For each isotope i, given N saved T0 files:

$$
\overline{T_0}_i = \frac{1}{N}\sum_{j=1}^{N} T_{0,i,j}, \qquad
\sigma_{i}^{(\text{group})} = \mathrm{std}\!\left(T_{0,i,j}\right)
$$

**Auto-mask rule (`getT0Statistics:2550`):**

$$
\text{mask}_j = 0 \iff \bigl|\,T_{0,i,j}-\overline{T_0}_i\,\bigr| \;>\; \tfrac{\sigma_i^{(\text{group})}}{2}+\overline{T_0}_i
$$

After masking, recompute mean/std over the surviving subset → `restatistics`.

> **Caveat**: the threshold `σ/2 + mean` mixes a half-σ scale with the mean itself; this is what the code does. Standard practice would be `|x − μ| > kσ`. Keep in mind when interpreting outlier rejection.

---

## 3. Mass Ratio — `calculateMassRatio`

`Utilities.py:2629–2687`

**Inputs**: mass file T0 (5 isotopes, with σ), preline/background T0 (5 isotopes, with σ), days `T = SPD − OGD` (sample-prep date minus original-gas date).

**Step 1 — blank subtraction (`:2670–2671`):**

$$
m_i = T_{0,i}^{(\text{mass})} - T_{0,i}^{(\text{bg})}, \qquad
\sigma_{m_i} = \sqrt{\sigma_{T_0,i}^{(\text{mass})\,2} + \sigma_{T_0,i}^{(\text{bg})\,2}}
$$

**Step 2 — short-lived isotope decay correction (`:2673–2678`):**

$$
m_{37} \;\to\; m_{37}\,e^{\,\lambda_{37} T}, \quad \lambda_{37} = 0.0198\ \mathrm{day^{-1}} \;(\equiv \ln 2/35.04)
$$

$$
m_{39} \;\to\; m_{39}\,e^{\,\lambda_{39} T}, \quad \lambda_{39} = 7.1\times 10^{-6}\ \mathrm{day^{-1}} \;(\equiv \ln 2/(269\cdot 365.25))
$$

σ scales by the same factor: ∂(m·eᵏᵀ)/∂m = eᵏᵀ.

**Step 3 — five reported ratios (`:2682–2685`, `pair_indices` at `:2627`):**

| idx | y / x | meaning |
|-----|-------|---------|
| 0   | 39 / 40 | Ar(39ₘ)/Ar(40ₘ) |
| 1   | 36 / 40 | Ar(36ₘ)/Ar(40ₘ) |
| 2   | 39 / 36 | Ar(39ₘ)/Ar(36ₘ) |
| 3   | 40 / 36 | Ar(40ₘ)/Ar(36ₘ) — for atmospheric check |
| 4   | 38 / 36 | Ar(38ₘ)/Ar(36ₘ) — for atmospheric check |

$$
R_k \;=\; \frac{m_y}{m_x}, \qquad
\sigma_{R_k} \;=\; \bigl|R_k\bigr|\sqrt{\left(\frac{\sigma_{m_y}}{m_y}\right)^{2}+\left(\frac{\sigma_{m_x}}{m_x}\right)^{2}}
$$

(ratio-quadrature; `abs()` added in v3.7.x bug-fix.)

---

## 4. Air Ratio Statistics — `getAirRatioStatistics`

`Utilities.py:2066–2109`

For N air-shot files, extracts the (40/36)ₐ and (38/36)ₐ ratios (rows 4 and 5, col 9), then trims any |40/36| > 313 outlier:

$$
\overline{R}_{p} = \frac{1}{N}\sum_{j=1}^{N} R_{p,j}, \qquad
\sigma_{R_p} = \mathrm{std}(R_{p,j})
$$

for p ∈ {40/36, 38/36}. No weighted mean here — pure population mean / std.

---

## 5. J Statistics — `getJStatistics` / `REgetJStatistics`

`Utilities.py:2111–2210, 2435+`

Two estimators are computed in parallel and both reported:

**Arithmetic mean & SE-of-the-mean (used for outlier mask):**

$$
\bar J = \frac{1}{N}\sum_j J_j, \qquad
\sigma_{\bar J}^{(\text{SE})} = \frac{\mathrm{std}(J_j)}{\sqrt{N}}
$$

Mask points where `J_j` falls outside `[J̄ − σ_SE, J̄ + σ_SE]`. After masking, the second pass uses `std(J)` (no /√N), i.e. switches to population std.

**Inverse-variance weighted mean (`:2137–2146`):**

$$
\mu_J = \frac{\sum_j J_j/\sigma_{J_j}^{2}}{\sum_j 1/\sigma_{J_j}^{2}}, \qquad
\sigma_{\mu_J} = \sqrt{\frac{1}{\sum_j 1/\sigma_{J_j}^{2}}}
$$

Returned tuple `[avg, σ_pop, μ, σ_μ]`. `σ_J` from the J-volume calc is propagated via `1/σ²` weights.

> **Note**: pyADR uses `avg` (arithmetic) for the outlier filter but reports the inverse-variance pair `(μ, σ_μ)` separately. Decide explicitly which to forward to AgeCalc.

---

## 6. J-Volume / J Calculation — `getJVolumeStatistics`

`Utilities.py:2747–2809`

**Constants used (irradiation parameter array, indexed by `constants[i]`):**

| idx | symbol | description |
|-----|--------|-------------|
| 0 | (³⁹Ar/³⁷Ar)_Ca | Ca-derived ³⁹Ar production ratio |
| 1 | σ of [0] | |
| 2 | (³⁶Ar/³⁷Ar)_Ca | |
| 3 | σ of [2] | |
| 4 | (⁴⁰Ar/³⁹Ar)_K | K-derived ⁴⁰Ar production |
| 12 | (⁴⁰Ar/³⁶Ar)_air | atmospheric, default 295.5 or 298.56 |
| 14 | λ_total | total ⁴⁰K decay (/yr), used in T = ln(1+JF)/λ |
| 16 | λ_total /1e6 | same, scaled to Ma |

**Ar component partition (`:2764–2785`):**

$$
\text{Ar}_{37,\text{Ca}} = \text{Ar}_{37,m}, \quad \sigma=\sigma_{37,m}
$$

$$
\text{Ar}_{36,\text{Ca}} = \text{Ar}_{37,\text{Ca}}\cdot c_2, \qquad
\text{Ar}_{36,\text{air}} = \text{Ar}_{36,m} - \text{Ar}_{36,\text{Ca}}
$$

$$
\text{Ar}_{39,\text{Ca}} = \text{Ar}_{37,\text{Ca}}\cdot c_0
$$

$$
\sigma_{\text{Ar}_{39,\text{Ca}}} = \text{Ar}_{39,\text{Ca}}\!\cdot\!\left(\frac{\sigma_{37,\text{Ca}}}{\text{Ar}_{37,\text{Ca}}}+\frac{c_1}{c_0}\right)\quad\text{(linear sum)}
$$

$$
\text{Ar}_{39,K} = \text{Ar}_{39,m} - \text{Ar}_{39,\text{Ca}}, \qquad \sigma = \sqrt{\sigma_{39,m}^{2}+\sigma_{39,\text{Ca}}^{2}}
$$

$$
\text{Ar}_{40,\text{air}} = \text{Ar}_{36,\text{air}}\cdot c_{12}, \qquad
\text{Ar}_{40,K} = \text{Ar}_{39,K}\cdot c_4
$$

$$
\boxed{\text{Ar}_{40,r} = \text{Ar}_{40,m} - \text{Ar}_{40,\text{air}} - \text{Ar}_{40,K}}
$$

**Standard ratios (`:2789–2796`):**

$$
G = \frac{m_{40}}{m_{39}}, \quad B=\frac{m_{36}}{m_{39}}, \quad D=\frac{m_{37}}{m_{39}}
$$

each with linear-sum σ: `σ_G = G·(σ_{40m}/m_{40} + σ_{39m}/m_{39})` etc.

**F (radiogenic ⁴⁰Ar* per ³⁹Arₖ) propagation (`:2796`):**

pyADR codes:

$$
\sigma_F = \sqrt{\sigma_G^{2} + (c_{12}\sigma_B)^{2} + \bigl[(c_0 G - c_{12}c_0 B + c_{12}c_2)\,\sigma_D\bigr]^{2}}
$$

This matches the partials of

$$
F = G - c_{12}B - c_0 D\,(G - c_{12}B + c_{12}c_2/c_0)
$$

i.e. the K-corrected F = (⁴⁰* − air − K-interference) / ³⁹ₖ form, with air- and Ca-correction terms.

**J value & uncertainty (`:2799–2804`):**

For an irradiation standard of known age `t` (years):

$$
J \;=\; \frac{e^{\lambda t}-1}{\text{Ar}_{40,r}/\text{Ar}_{39,K}}
$$

$$
\sigma_J^{2} = \underbrace{\left(\frac{t\,e^{\lambda t}}{F_{r/k}}\right)^{2}\sigma_\lambda^{2}}_{v_1} {} + \underbrace{\left(\frac{\lambda\,e^{\lambda t}}{F_{r/k}}\right)^{2}\sigma_t^{2}}_{v_2} {} + \underbrace{\left(\frac{e^{\lambda t}-1}{F_{r/k}^{2}}\right)^{2}\sigma_F^{2}}_{v_3}
$$

$$
\sigma_J^{(\text{int})} = \sqrt{v_3}
$$

Hard-coded constants in this function: `λ = 5.531e-10 /yr`, `σ_λ = 0.0135e-10 /yr` (Steiger & Jäger 1977 ⁴⁰K → ⁴⁰Ar branch). For Min et al. (2000) values, change `l, l_std` at `Utilities.py:2748–2749`.

> ⚠ **Bug — σ_J v₃ term missing a pair of parentheses (`Utilities.py:2864`).**
>
> The code reads:
>
> ```python
> v3 = F_std**2 * ((np.exp(l*t)) - 1 / Ar_39_K_40_r_ratio**2) ** 2
> ```
>
> Python operator precedence binds `1 / F²` before `(e^λt) − …`, so this evaluates to
>
> $$
> v_3^{(\text{coded})} = F_{\text{std}}^{2} \cdot \bigl(e^{\lambda t} - \tfrac{1}{F_{r/k}^{2}}\bigr)^{2}
> $$
>
> instead of the intended
>
> $$
> v_3^{(\text{correct})} = F_{\text{std}}^{2} \cdot \left(\frac{e^{\lambda t}-1}{F_{r/k}^{2}}\right)^{2}.
> $$
>
> **Fix**: one extra pair of parentheses
>
> ```python
> v3 = F_std**2 * ((np.exp(l*t) - 1) / Ar_39_K_40_r_ratio**2) ** 2
> ```
>
> **Impact**: When `λt ≪ 1` (typical young samples), `e^{λt} ≈ 1` so the correct form gives `v₃ ≈ (λt/F²)² · σ_F²` (small), while the coded form gives `v₃ ≈ (1 − 1/F²)² · σ_F²` (dominated by the spurious `1`). σ_J is **massively over-estimated** for young samples — sign and rough magnitude reversed from the correct error budget. 5-minute fix; deferred only because Utilities.py is on the advisor-owned upstream.

**Ca/K (`:2807–2808`):**

$$
\mathrm{Ca/K} = \frac{0.52\cdot\text{Ar}_{37,\text{Ca}}}{\text{Ar}_{39,K}}, \qquad
\sigma = \mathrm{Ca/K}\!\cdot\!\left(\frac{\sigma_{37,\text{Ca}}}{\text{Ar}_{37,\text{Ca}}}+\frac{\sigma_{39,K}}{\text{Ar}_{39,K}}\right)
$$

The factor 0.52 is the lab calibration (production cross-section for ³⁷Ar from ⁴⁰Ca / ³⁹Ar from ³⁹K). v3.0.1 fixed an inverted Ca/K and a wrong constant (was `pr_ratio=0.000377`).

---

## 7. Age Calculation — `calcAge`

`Utilities.py:2811–2920` — restored from V3.4.1 archive in v3.7.4 (was truncated mid-function in v3.7.0–v3.7.3 release HEAD).

Returns 59-element list. Key indices: `[18,19]` Ar_39_K ± σ; `[24,25]` Ar_40_r ± σ; `[36,37]` F ± σ; `[46,47]` T ± σ (years); `[48,49]` J_int, T_int.

**Constants used (extends §6 table):**

| idx | symbol | description |
|-----|--------|-------------|
| 0,1 | (39/37)_Ca, σ | Ca-derived 39 production |
| 2,3 | (36/37)_Ca, σ | |
| 4,5 | (40/39)_K, σ | K-derived 40 production |
| 6,7 | (38/39)_K, σ | K-derived 38 production |
| 12,13 | (40/36)_air, σ | atmospheric, default 298.56 |
| 14 | λ_total (/yr) | used in degas plot per-step `T = ln(1+JF)/λ` |
| 16 | λ_total (/yr) | used in **calcAge** AND `getStackPlot` total age |

> **⚠️ Code inconsistency**: per-step T in `getDegasPlot:444` uses `constants[14]`, but `calcAge:2904` and `getStackPlot:1972` use `constants[16]`. If PS sets [14] ≠ [16] (e.g. Steiger 5.531e-10 vs Min 5.463e-10), per-step ages and total age use **different λ** — check PS values match.

**Step 1 — Ar component partition (`:2858–2890`):**

$$
\text{Ar}_{37,\text{Ca}} = \text{Ar}_{37,m},\qquad \sigma_{37,\text{Ca}} = \sigma_{37,m}
$$

$$
\text{Ar}_{36,\text{Ca}} = \text{Ar}_{37,\text{Ca}}\cdot c_2,\qquad
\sigma_{36,\text{Ca}} = \text{Ar}_{36,\text{Ca}}\!\cdot\!\left(\frac{\sigma_{37,\text{Ca}}}{\text{Ar}_{37,\text{Ca}}}+\frac{c_3}{c_2}\right)\quad\text{(linear sum)}
$$

$$
\text{Ar}_{36,\text{air}} = \text{Ar}_{36,m} - \text{Ar}_{36,\text{Ca}},\qquad
\sigma_{36,\text{air}} = \sqrt{\sigma_{36,m}^{2}+\sigma_{36,\text{Ca}}^{2}}\quad\text{(quadrature)}
$$

$$
\text{Ar}_{39,\text{Ca}} = \text{Ar}_{37,\text{Ca}}\cdot c_0,\qquad
\sigma_{39,\text{Ca}} = \text{Ar}_{39,\text{Ca}}\!\cdot\!\left(\frac{\sigma_{37,\text{Ca}}}{\text{Ar}_{37,\text{Ca}}}+\frac{c_1}{c_0}\right)
$$

$$
\text{Ar}_{39,K} = \text{Ar}_{39,m} - \text{Ar}_{39,\text{Ca}},\qquad
\sigma_{39,K} = \sqrt{\sigma_{39,m}^{2}+\sigma_{39,\text{Ca}}^{2}}
$$

**³⁸Ar partition (`:2876–2880`):**

$$
\text{Ar}_{38,K} = \text{Ar}_{39,K}\cdot c_6,\qquad
\sigma_{38,K} = \text{Ar}_{38,K}\!\cdot\!\left(\frac{\sigma_{39,K}}{\text{Ar}_{39,K}}+\frac{c_7}{c_6}\right)
$$

$$
\text{Ar}_{38,\text{Air}}^{\,(\text{calcAge})} = \text{Ar}_{38,m} - \text{Ar}_{38,K},\qquad
\sigma = \sqrt{\sigma_{38,m}^{2}+\sigma_{38,K}^{2}}
$$

> **⚠️ Misleading variable name**: the field labelled `Ar_38_Air` in the AgeCalc table actually contains ³⁸Ar(air) **+** ³⁸Ar(Cl). The proper split (³⁸Ar_air = ³⁶Ar_air · (³⁸/³⁶)_a, ³⁸Ar_Cl = ³⁸m − ³⁸_air − ³⁸_K) is only done at the Datum Publication stage in `toDP:4648–4664`. Don't quote the AgeCalc page's "Ar_38_Air" as pure atmospheric ³⁸Ar.

**⁴⁰Ar partition (`:2884–2891`):**

$$
\text{Ar}_{40,\text{air}} = \text{Ar}_{36,\text{air}}\cdot c_{12},\qquad
\sigma_{40,\text{air}} = \text{Ar}_{40,\text{air}}\!\cdot\!\left(\frac{\sigma_{36,\text{air}}}{\text{Ar}_{36,\text{air}}}+\frac{c_{13}}{c_{12}}\right)
$$

$$
\text{Ar}_{40,K} = \text{Ar}_{39,K}\cdot c_4,\qquad
\sigma_{40,K} = \text{Ar}_{40,K}\!\cdot\!\left(\frac{\sigma_{39,K}}{\text{Ar}_{39,K}}+\frac{c_5}{c_4}\right)
$$

$$
\boxed{\text{Ar}_{40,r} = \text{Ar}_{40,m} - \text{Ar}_{40,\text{air}} - \text{Ar}_{40,K}}, \qquad \sigma_{40,r} = \sqrt{\sigma_{40,m}^{2}+\sigma_{40,\text{air}}^{2}+\sigma_{40,K}^{2}}
$$

**Step 2 — F = ⁴⁰Ar*/³⁹Arₖ (`:2904`):**

$$
F = \frac{\text{Ar}_{40,r}}{\text{Ar}_{39,K}}
$$

**F uncertainty** — code uses the explicit-partial form (NOT the simple ratio quadrature on F):

$$
\sigma_F = \sqrt{\sigma_G^{2} + (C_1\,\sigma_B)^{2} + \bigl[(C_4 G - C_1 C_4 B + C_1 C_2)\,\sigma_D\bigr]^{2}}
$$

where, using the calcAge naming `(C₁,C₂,C₃,C₄) = (c₁₂, c₂, c₄, c₀)`:

$$
G = \frac{m_{40}}{m_{39}},\quad B = \frac{m_{36}}{m_{39}},\quad D = \frac{m_{37}}{m_{39}}
$$

with linear-sum σ on each (e.g. `σ_G = G·(σ_{40m}/m_{40} + σ_{39m}/m_{39})`). Same form as §6's σ_F. Note: code defines `C3=c₄` but **C3 is not used** in the σ_F expression above (only C1, C2, C4 appear).

**Step 3 — Age equation (`:2906`):**

$$
\boxed{T = \frac{\ln(1+JF)}{\lambda}}, \qquad \lambda = c_{16}\ (\text{/yr})
$$

**T uncertainty as coded (`:2907`):**

$$
\sigma_T^{(\text{code})} = \frac{\sqrt{(F\,\sigma_J)^{2}+(J\,\sigma_F)^{2}}}{\lambda(1+JF)}
$$

i.e. partials ∂T/∂J = F/[λ(1+JF)], ∂T/∂F = J/[λ(1+JF)] in quadrature.

**T uncertainty per McDougall & Harrison 1999 eq. 4.7 (full):**

$$
\sigma_T^{2} = \left(\frac{F}{\lambda(1+JF)}\right)^{2}\sigma_J^{2} {} + \left(\frac{J}{\lambda(1+JF)}\right)^{2}\sigma_F^{2} {} + \left(\frac{T}{\lambda}\right)^{2}\sigma_\lambda^{2}
$$

> **⚠️ Code drops the σ_λ term**: pyADR's `T_std` formula at `:2907` omits the third partial `(∂T/∂λ)²σ_λ²`. For Steiger & Jäger λ with σ_λ ≈ 0.24% relative, this under-estimates σ_T by ≈ 0.5% relative. For a 50 Ma age with σ_T ≈ 0.5 Ma, the missing contribution is ≈ 0.12 Ma — small but systematic. Flag for advisor discussion before publication.

**Internal age uncertainty (`:2908`):**

$$
\sigma_T^{(\text{int})} = \frac{\sqrt{(F\,\sigma_J^{(\text{int})})^{2}+(J\,\sigma_F)^{2}}}{\lambda(1+JF)}
$$

Same form as σ_T but with σ_J replaced by σ_J^(int) (the v₃-only J uncertainty from §6). σ_λ also dropped here.

**Auxiliary ratios returned (`:2895–2900`):**

$$
\frac{\text{Ar}_{39,K}}{\text{Ar}_{40,r}},\quad
\frac{\text{Ar}_{36,\text{air}}}{\text{Ar}_{40,r}},\quad
\frac{\text{Ar}_{39,K}}{\text{Ar}_{36,\text{air}}}
$$

each with linear-sum σ. Used by inverse-isochron / atmospheric-correction plots.

---

## 8. Salt / Interference factors — `calculateSlatCa`, `calculateSlatK`

`Utilities.py:2689–2745`

**CaF₂ salt → (³⁶/³⁷)_Ca and (³⁹/³⁷)_Ca (`:2708–2711`):**

$$
\left(\frac{^{36}\!\mathrm{Ar}}{^{37}\!\mathrm{Ar}}\right)_{Ca} \;=\; \frac{\text{Ar}_{36}-\text{Ar}_{\text{air}}/298.56}{\text{Ar}_{37}}
$$

$$
\sigma = \mathrm{ratio}\cdot\sqrt{\!\left(\frac{\sigma_{36}+\sigma_{\text{air}}/298.56}{\text{Ar}_{36}-\text{Ar}_{\text{air}}/298.56}\right)^{2}+\left(\frac{\sigma_{37}}{\text{Ar}_{37}}\right)^{2}}
$$

$$
\left(\frac{^{39}\!\mathrm{Ar}}{^{37}\!\mathrm{Ar}}\right)_{Ca} = \frac{\text{Ar}_{39}}{\text{Ar}_{37}}, \quad \sigma = \mathrm{ratio}\sqrt{(\sigma_{39}/\text{Ar}_{39})^{2}+(\sigma_{37}/\text{Ar}_{37})^{2}}
$$

The 298.56 is the assumed atmospheric ⁴⁰/³⁶ used to back-correct the air component; this is **lab-fixed** (Lee et al. 2006). To use 295.5 (Steiger & Jäger 1977) edit `:2708–2738`.

**K salt → (⁴⁰/³⁹)_K, (³⁸/³⁹)_K, (³⁹/³⁷)_K (`:2737–2742`):**

$$
\left(\frac{^{40}\!\mathrm{Ar}}{^{39}\!\mathrm{Ar}}\right)_{K} = \frac{\text{Ar}_{40}-298.56\cdot\text{Ar}_{36}}{\text{Ar}_{39}}
$$

σ analogous to the CaF case (linear-sum on the numerator's air subtraction).

---

## 9. Datum Publication (post-Age recalculation) — `toDP`

`NTNU_DataReduction.py:4507–4834`

For each AgeCalc CSV row, the publication table re-derives:

**Step heating fractions (`:4636–4637`):**

$$
{}^{40}\mathrm{Ar}_r\ (\%)_{step} = \frac{\text{Ar}_{40,r,j}}{\sum_j \text{Ar}_{40,r,j}}\cdot 100, \qquad
{}^{39}\mathrm{Ar}_K\ (\%)_{step} = \frac{\text{Ar}_{39,K,j}}{\sum_j \text{Ar}_{39,K,j}}\cdot 100
$$

(Note: σ not propagated for these — pure denominators.)

**Per-step atmospheric ⁴⁰/³⁶ ratio (`:4692`):**

$$
{}^{40}\mathrm{Ar}_r\ (\%) = \frac{\text{Ar}_{40,r}}{\text{Ar}_{40,m}}\cdot 100, \qquad
{}^{39}\mathrm{Ar}_K\ (\%) = \frac{\text{Ar}_{39,K}}{\text{Ar}_{39,m}}\cdot 100
$$

**³⁸Ar component breakdown (`:4648–4664`):**

$$
\text{Ar}_{38,\text{air}} = \text{Ar}_{36,a}\cdot \left(\tfrac{38}{36}\right)_a
$$

$$
\sigma_{38,\text{air}} = |\text{Ar}_{38,\text{air}}|\cdot\!\left(\frac{\sigma_{36,a}}{\text{Ar}_{36,a}}+\frac{\sigma_{(38/36)a}}{(38/36)_a}\right)\quad\text{(linear)}
$$

$$
\text{Ar}_{38,K} = \text{Ar}_{39,K}\cdot \left(\tfrac{38}{39}\right)_k, \quad \sigma\ \text{analogous}
$$

$$
\boxed{\text{Ar}_{38,Cl} = \text{Ar}_{38,m} - \text{Ar}_{38,\text{air}} - \text{Ar}_{38,K}}
$$

$$
\sigma_{38,Cl} = \sqrt{\sigma_{38,m}^{2}+\sigma_{38,\text{air}}^{2}+\sigma_{38,K}^{2}}
$$

(quadrature, `Utilities → toDP:4664`)

**³⁶Ar(Cl) from production ratio (`:4744–4748`):**

$$
\text{Ar}_{36,Cl} = \left(\tfrac{36}{38}\right)_{Cl}\cdot\text{Ar}_{38,Cl}, \qquad
\sigma = \left|\left(\tfrac{36}{38}\right)_{Cl}\right|\cdot\sigma_{38,Cl}
$$

**Ca/K (rederived, lab calibration R = 0.52, `:4710–4711`):**

$$
\mathrm{Ca/K} = \frac{0.52\cdot\text{Ar}_{37,Ca}}{\text{Ar}_{39,K}}, \qquad
\sigma = \mathrm{Ca/K}\cdot\!\left(\frac{\sigma_{37,Ca}}{\text{Ar}_{37,Ca}}+\frac{\sigma_{39,K}}{\text{Ar}_{39,K}}\right)
$$

v3.0.1 fix-record: prior version inverted Ca/K and used `pr_ratio = 0.000377` instead of 0.52.

**⁴⁰Ar(r+a):**

$$
\text{Ar}_{40,(r+a)} = \text{Ar}_{40,r}+\text{Ar}_{40,a}, \qquad
\sigma = \sqrt{\sigma_{40,r}^{2}+\sigma_{40,a}^{2}}
$$

Age in Ma (`:4686–4687`):

$$
T_{\mathrm{Ma}} = T_{\mathrm{yr}}/10^{6}, \qquad \sigma_{T_{\mathrm{Ma}}} = \sigma_{T_{\mathrm{yr}}}/10^{6}
$$

---

## 10. DiagramPlot — Inverse / Normal Isochron, Plateau WMA, MSWD

`Utilities.py:307–490 (getDFStatistics_ls), 462–1535 (getDFStatistics_sh), 928–1050 (DFN group fit), 1340–1395 (DFI group fit), 1500–1535 (WMA & MSWD)`

All formulas in this section use the **York convention** `Y = a + b·X`, where `a` = y-intercept and `b` = slope (per Vermeesch 2024 Eq. p.398, Vermeesch 2018 IsoplotR §11). pyADR's `curve_fit(linear, x, y)` returns `popt = [b, a]` (slope first, intercept second).

### 10.1 Normal isochron (DFN)

$$
X = \frac{{}^{39}\mathrm{Ar}_m}{{}^{36}\mathrm{Ar}_m},\qquad
Y = \frac{{}^{40}\mathrm{Ar}_m}{{}^{36}\mathrm{Ar}_m}
$$

Linear fit gives `Y = a_N + b_N·X` where:

$$
a_N = \left(\tfrac{^{40}\mathrm{Ar}}{^{36}\mathrm{Ar}}\right)_{\!\text{trapped}}, \qquad
b_N = F = \tfrac{^{40}\mathrm{Ar}^*}{^{39}\mathrm{Ar}_K}
$$

So **slope = F**, **intercept = trapped 40/36** (direct read-off).

### 10.2 Inverse isochron (DFI) — F = −b/a (v3.8 corrected)

$$
X = \frac{{}^{39}\mathrm{Ar}_m}{{}^{40}\mathrm{Ar}_m},\qquad
Y = \frac{{}^{36}\mathrm{Ar}_m}{{}^{40}\mathrm{Ar}_m}
$$

Linear fit gives `Y = a_I + b_I·X` where (Vermeesch 2024, eq. p.398):

$$
a_I = \left(\tfrac{^{36}\mathrm{Ar}}{^{40}\mathrm{Ar}}\right)_{\!\text{trapped}} = \tfrac{1}{(^{40}\mathrm{Ar}/^{36}\mathrm{Ar})_{\text{trapped}}}, \qquad
b_I = -F \cdot a_I
$$

Therefore (`Utilities.py:1479`):

$$
\boxed{\;F = -\dfrac{b_I}{a_I} = \dfrac{1}{X_{\text{intercept}}}\;}
$$

Equivalently, the X-intercept of the inverse isochron equals `1/F` (Vermeesch 2018 Geosci Frontiers, IsoplotR p.8).

**Error propagation for F = −b/a** including slope-intercept covariance from `pcov_inv`:

$$
\sigma_F^{\,2} = \left(\frac{\sigma_b}{a}\right)^{\!2} + \left(\frac{b\,\sigma_a}{a^{2}}\right)^{\!2} - \frac{2b}{a^{3}}\,\mathrm{cov}(b,a)
$$

Implemented at `Utilities.py:455-465` (LS) and `Utilities.py:1479-1502` (SH).

> **v3.8.0 fix**: Previously the code used `F = 1/inv_slope` (i.e. `F = 1/b`). This is dimensionally and geometrically wrong — for typical samples `b < 0` (X = 39/40 increases as Y = 36/40 decreases), so `1/b` is a small negative number, producing `log(1 + J·F) ≈ 0` and absurdly young ages (e.g. SYL31 Sylhet Trap basalt, 115.4 ± 3.9 Ma per NTU thesis R94224113, returned T = 0.903 Ma in v3.7.4).

### 10.3 Isochron age — Int age

$$
T_{\text{Int}} = \frac{1}{\lambda}\ln(1 + J\cdot F)
$$

with the standard three-source error propagation (`Utilities.py:466, 1503`):

$$
\sigma_T^{\,2} = \frac{J^2\,\sigma_F^{\,2} + F^2\,\sigma_J^{\,2}}{\bigl[\lambda(1 + J\cdot F)\bigr]^{2}}
$$

(σ_λ omitted; see §10.x note 3.)

### 10.4 Step age (per heating step)

$$
T_j = \frac{1}{\lambda}\ln(1 + J\cdot F_j)
$$

where `F_j = ⁴⁰Ar*_j / ³⁹Ar_K,j` is computed per-step in `calcAge` (§7).

### 10.5 Weighted Mean Age (WMA) — inverse-variance form (v3.8 corrected)

For N step ages `{T_i ± σ_i}`:

$$
\boxed{\;\mathrm{WMA} = \dfrac{\displaystyle\sum_i T_i/\sigma_i^{\,2}}{\displaystyle\sum_i 1/\sigma_i^{\,2}}\;}
\qquad
\sigma_{\mathrm{WMA}} = \dfrac{1}{\sqrt{\displaystyle\sum_i 1/\sigma_i^{\,2}}}
$$

This is the maximum-likelihood estimator for a Normal model with two variance components (Vermeesch 2018, IsoplotR Eq. 5) and the standard form assumed by Schaen et al. (2021) GSA Bull. p.470 MSWD definition.

Implemented at `Utilities.py:468-477` (LS) and `Utilities.py:1514-1523` (SH).

> **v3.8.0 fix**: The previous code wrote:
> ```python
> wma += (1/σ²·T) / (1/σ²)
> ```
> The numerator and denominator cancel inside the loop, so each iteration adds `T_i` and the final `wma = Σ T_i` is the **sum**, not the weighted mean. SYL31 with 40 spots reported WMA = 4481.9 (= 40 × ~112 Ma ≈ Σ T) instead of ~115 Ma. Output is internally inconsistent with the MSWD (which assumes WMA is the reference point).

### 10.6 Mean Square Weighted Deviates (MSWD) — WMA reference (v3.8 corrected)

For plateau / weighted-mean MSWD (Schaen et al. 2021 p.470):

$$
\boxed{\;\mathrm{MSWD} = \dfrac{1}{N-1}\sum_{i=1}^{N}\dfrac{(T_i - \mathrm{WMA})^2}{\sigma_i^{\,2}}\;}
$$

For isochron-regression MSWD (group fits at `Utilities.py:1029-1037`, `1372-1380`):

$$
\mathrm{MSWD}_{\text{iso}} = \dfrac{1}{N-2}\sum_{i=1}^{N}\dfrac{(y_i - \hat{y}_i)^2}{\sigma_{y,i}^{\,2}}
$$

with `ŷ_i = a + b·x_i` from the linear fit. The N−2 reflects two fitted parameters (slope, intercept); the plateau form uses N−1 (one fitted parameter, the WMA itself).

> **v3.8.0 fix**: Previously the plateau-MSWD reference was the **arithmetic** mean `T_sum/N` instead of WMA. With a non-uniform `σ_i`, this gives a different — and inconsistent with the reported WMA — measure of dispersion. Schaen 2021 specifies WMA as the reference, matching the maximum-likelihood form.

### 10.7 Total fusion age and plateau average

$$
F_{\text{total}} = \frac{\sum_j {}^{40}\mathrm{Ar}_{r,j}}{\sum_j {}^{39}\mathrm{Ar}_{K,j}},\qquad
T_{\text{total}} = \frac{\ln(1 + J\cdot F_{\text{total}})}{\lambda}
$$

`Utilities.py:2033-2034`. Computed before any plateau/isochron filtering.

> ⚠ **Plateau "avg_age" still uses arithmetic mean (`Utilities.py:2031`).** Despite the §10.5 WMA being fixed in v3.8, the plateau display computes
>
> ```python
> avg_age = np.mean([y_age[i] for i in range(n) if mask[i] == 1])
> ```
>
> i.e. unweighted arithmetic mean of unmasked step ages. The "weighted plateau age" shown in the plateau-step plot is therefore **not** consistent with the WMA reported in the regression summary (§10.5). For an external `±σ` table, use the WMA from §10.5; treat the plot's avg-age annotation as visual only. Same pattern as the v3.7.x WMA bug — should be unified.

### 10.8 Regression method — current status

pyADR currently uses `scipy.optimize.curve_fit(linear, x, y)`, which is **ordinary least squares (OLS)** with no weights. This:

- Ignores σ_y (no inverse-variance weighting of the fit)
- Ignores σ_x (assumes all uncertainty is in y)
- Ignores correlations between σ_x and σ_y (which are large for inverse isochrons because ⁴⁰Ar is the denominator of both axes)

The standard for ⁴⁰Ar/³⁹Ar isochron fitting is **York regression** (York et al. 2004; Vermeesch 2018, IsoplotR), which accounts for σ_x, σ_y, and ρ(x,y). Replacing OLS with York is a planned v3.9+ task (see CHANGELOG.md "仍待處理" list).

The MSWD formulas in §10.6 are unaffected by the OLS vs York choice as long as σ_y dominates and ρ(x,y) is small.

> ⚠ **Intercept SE bug — running OLS on the error bars (`Utilities.py:389-390, 965-966`).** Two normal-isochron paths compute the intercept uncertainty by re-fitting:
>
> ```python
> popt_std, _ = curve_fit(linear, x_std, y_std)   # ← fit to the σ values themselves
> n_std       = linear(0, *popt_std)              # ← "intercept" of that fit, called n_std
> ```
>
> This treats the σ_x, σ_y arrays as if they were a new (x, y) dataset and reads its intercept. **Mathematically meaningless** — the resulting `n_std` is not the SE of the original-fit intercept; it is a slope-of-error-bars number with no statistical interpretation. The inverse-isochron paths (`:441, :1286`) correctly read `pcov[1,1]` from the main fit's covariance matrix — that's the form that should be used everywhere. Fix is one-line: replace each `curve_fit(linear, x_std, y_std) → linear(0, *popt_std)` pair with `np.sqrt(pcov[1, 1])` from the main fit at the same call site.

### 10.x v3.7.x bug-history note (preserved for traceability)

For context: the v3.7.x F, WMA, and MSWD formulas in `getDFStatistics_sh` / `getDFStatistics_ls` were all buggy in distinct ways:

| Item | v3.7.x code | v3.8 fix | Reference |
|---|---|---|---|
| F (inverse isochron) | `F = 1/inv_slope` | `F = −b/a` | Vermeesch 2024 p.398 |
| F (LS isochron) | `T = log(1 + J·iv)` using Y-intercept | `F = −b/a` | Vermeesch 2024 p.398 |
| WMA | `(1/σ²·T)/(1/σ²)` inside loop → Σ T | `Σ(T/σ²)/Σ(1/σ²)` | Vermeesch 2018 Eq. 5 |
| MSWD reference | arithmetic mean | WMA | Schaen 2021 p.470 |

Validation: SYL31 LS (NTU thesis R94224113, Sylhet Trap basalt 115.4 ± 3.9 Ma).

---

## 11. 3D Plane Fit — `PlaneFit3D.py`

`PlaneFit3D.py:1–791`

Reference implementation of Kent et al. (1990) maximum-likelihood plane regression for ⁴⁰Ar/³⁹Ar, following Wu (2007) NTU master thesis (R94224113, advisor: Ching-Hua Lo). Provides an alternative to the 2D isochron projection that retains all three isotope axes directly, avoiding error accumulation from ratio computation.

### 11.1 Plane equation

For a well-behaved sample with two end-members (trapped + radiogenic), the three Ar isotopes lie on a plane in (³⁶Ar, ³⁹Ar, ⁴⁰Ar) space:

$$
^{40}\text{Ar} \;=\; \alpha \cdot {}^{36}\text{Ar} \;+\; \beta \cdot {}^{39}\text{Ar}
$$

**Physical meaning**:
- $\alpha = (^{40}\text{Ar}/^{36}\text{Ar})_0$ = trapped (initial / atmospheric) composition (≈ 298.56 for pure air)
- $\beta = ^{40}\text{Ar}^*/^{39}\text{Ar}_K$ = radiogenic-to-K ratio (= F in the standard age equation)

Age from β:
$$
T \;=\; \frac{1}{\lambda} \ln(1 + \beta \cdot J)
$$

### 11.2 Maximum-likelihood objective

Following Wu (2007) eq 3-7 and Kent et al. (1990), with each data point $x_i = (^{36}\text{Ar}_i, ^{39}\text{Ar}_i, ^{40}\text{Ar}_i)$ assumed to follow a 3D multivariate normal $N_3(\mu_i, A_i)$:

Define the plane normal vector $\gamma = [\alpha, \beta, -1]^T$ and:

$$
s_i \;=\; \gamma^T x_i \;=\; \alpha\,^{36}\text{Ar}_i + \beta\,^{39}\text{Ar}_i - {}^{40}\text{Ar}_i
$$

$$
q_i \;=\; \gamma^T A_i\, \gamma \;=\; \alpha^2\,A_{i,11} + \beta^2\,A_{i,22} + A_{i,33} + 2\alpha\beta\,A_{i,12} - 2\alpha\,A_{i,13} - 2\beta\,A_{i,23}
$$

After Lagrange-multiplier elimination of $\mu_i$ (Wu 2007 eq 3-5 → 3-7), the **profile log-likelihood** is:

$$
L_p(\delta) \;=\; -\tfrac{1}{2}\sum_i \frac{s_i^2}{q_i}
\qquad \text{where}\;\delta = [\alpha, \beta]^T
$$

Maximizing $L_p$ is equivalent to a weighted-least-squares minimisation where weights account for variance in all three isotope dimensions (no axis is preferred).

`PlaneFit3D.py:_Lp` L126-129.

### 11.3 Per-point covariance matrix $A_i$ (3×3)

`PlaneFit3D.py:build_cov` L56-63.

$$
A_i \;=\;
\begin{bmatrix}
\sigma_{36,i}^2 & 0 & 0 \\
0 & \sigma_{39,i}^2 & -k_0\,\sigma_{39,i}^2 \\
0 & -k_0\,\sigma_{39,i}^2 & \sigma_{40,i}^2
\end{bmatrix}
$$

where $k_0 = $ PR(⁴⁰Ar/³⁹Ar)_K production ratio (default 0.025004).

The off-diagonal $\text{cov}(^{39}\text{Ar},^{40}\text{Ar}) = -k_0\,\sigma_{39}^2$ captures the anti-correlation introduced when ⁴⁰Ar = ⁴⁰Ar(m) − k₀·³⁹Ar(K) is back-corrected for the K-derived interference. Other off-diagonals are zero under the standard assumption of independent isotope measurements.

### 11.4 Newton–Raphson optimisation

`PlaneFit3D.py:_newton_raphson` L174-198. `PlaneFit3D.py:_grad`, `_hess` L132-158.

Solve $\partial L_p/\partial \delta = 0$ iteratively starting from an OLS initial guess (`_ols_initial`, L161-171):

$$
\delta_{k+1} \;=\; \delta_k + H^{-1}\, g
$$

where
$$
g = -\frac{\partial L_p}{\partial \delta}\Big|_{\delta_k}, \qquad H = -\frac{\partial^2 L_p}{\partial \delta \partial \delta^T}\Big|_{\delta_k}
$$

At the MLE, $-\partial^2 L_p/\partial \delta \partial \delta^T$ is positive-definite (the observed Fisher information).

**Backtracking line search** (v3.4 addition): halve the step size up to 20× until $L_p$ strictly increases. Prevents Newton-method overshoot in regions with large curvature. Convergence tolerance $|\Delta\delta|/|\delta| < 10^{-10}$.

> **Sign-convention note**: pyADR's `_grad()` returns $+\partial L_p/\partial \delta$ (opposite sign to Wu 2007 eq 3-10). Combined with $H = -\partial^2 L_p$, the update $\delta_{k+1} = \delta_k + H^{-1} g$ moves uphill on $L_p$ (signs cancel). Documented inline in `_grad`'s docstring.

### 11.5 MSWD goodness-of-fit

`PlaneFit3D.py:_compute_mswd` L201-208.

$$
S^2 \;=\; \sum_i \frac{s_i^2}{q_i}, \qquad \text{df} = n - 2
$$

$$
\text{MSWD} \;=\; \frac{S^2}{n - 2}
$$

(Wu 2007 eq 3-24; Mahon 1996.) Two free parameters (α, β) → df = n−2.

**95% confidence interval** for MSWD computed exactly via $\chi^2_{df}$ quantiles (`scipy.stats.chi2`), not the normal approximation of Wendt & Carl (1991):
$$
\text{CI}_{95\%}(\text{MSWD}) \;=\; \left[\frac{\chi^2_{df}(0.025)}{df}, \frac{\chi^2_{df}(0.975)}{df}\right]
$$

If MSWD exceeds the upper bound, pyADR applies a Wendt-Carl style σ-expansion:
$$
\tau^2 \;=\; \frac{S^2}{df} \;=\; \text{MSWD}
\qquad \Longrightarrow \qquad \sigma_{\delta} \to \sqrt{\tau^2}\,\sigma_{\delta}
$$

### 11.6 Parameter covariance

`PlaneFit3D.py:_param_cov` L211-226.

$$
\text{cov}(\hat{\delta}) \;=\; \tau^2 \cdot H^{-1}
$$

where $H = -\partial^2 L_p/\partial \delta \partial \delta^T$ (positive definite at MLE).

> **Wu (2007) eq 3-27 sign-error correction**: The thesis writes $\text{cov}(\hat{\delta}) = \tau^2 \cdot (\partial^2 L_p/\partial \delta \partial \delta^T)^{-1}$. At the MLE, $\partial^2 L_p$ is negative-definite, so its inverse gives **negative variances** — clearly wrong. The correct ML asymptotic covariance is $\tau^2 \cdot (-\partial^2 L_p/\partial \delta \partial \delta^T)^{-1} = \tau^2 \cdot H^{-1}$. pyADR uses the corrected form and documents this inline.

Marginal 1σ uncertainties:
$$
\sigma_\alpha \;=\; \sqrt{\text{cov}(\hat\delta)_{11}}, \qquad \sigma_\beta \;=\; \sqrt{\text{cov}(\hat\delta)_{22}}
$$

### 11.7 Age and σ_T

`PlaneFit3D.py:age_from_beta`, `age_error_1sigma` L229-243.

$$
T \;=\; \frac{1}{\lambda}\,\ln(1 + \beta J)
$$

Renne (1998) / Min et al. (2000) error propagation:

$$
\sigma_T^2 \;=\; \left(\frac{\partial T}{\partial \beta}\sigma_\beta\right)^2 + \left(\frac{\partial T}{\partial J}\sigma_J\right)^2 + \left(\frac{\partial T}{\partial \lambda}\sigma_\lambda\right)^2
$$

with partial derivatives:
$$
\frac{\partial T}{\partial \beta} = \frac{J}{\lambda(1 + \beta J)}, \qquad
\frac{\partial T}{\partial J} = \frac{\beta}{\lambda(1 + \beta J)}, \qquad
\frac{\partial T}{\partial \lambda} = -\frac{\ln(1 + \beta J)}{\lambda^2}
$$

### 11.8 Mahon (1996) modified weighting — optional σ-cap

`PlaneFit3D.py:_apply_sigma_cap` L66-71 (v3.4.3 addition).

For background-dominated steps where $\sigma_i / |x_i| \gg 1$ (e.g. blank-corrected low-signal steps), classical Kent weights give those points outsize influence and underdisperse MSWD. Mahon (1996) suggests capping the relative uncertainty:

$$
\sigma_{i,\text{eff}} \;=\; \min\bigl(\sigma_i,\;c \cdot |x_i|\bigr)
$$

with typical $c = 0.2$–$0.5$. pyADR exposes `sigma_cap_rel` parameter; `None` disables (classical Kent), per-axis values supported.

### 11.9 Sub-plane search

`PlaneFit3D.py:find_subplanes` L325+.

Sliding-window search over consecutive heating steps to identify the longest run with MSWD inside the 95% χ² CI. Used to detect sub-plateaus when not all steps share a single isotope system. Returns ranked candidates by window length.

### 11.10 ⚠ Known issue — input σ_40 double-counting (caller-side bug)

**Location**: `NTNU_DataReduction.py:3901-3902` (single fit) and `:4489+` (group fit).

```python
x40 = (df3["40Ar(r)"] + df3["40Ar(a)"]).values[m3]
s40 = np.hypot(df3["40Ar(r)_std"].values, df3["40Ar(a)_std"].values)[m3]
```

**Math problem**:
- $x_{40} = ^{40}\text{Ar}(r) + ^{40}\text{Ar}(a)$
- $^{40}\text{Ar}(r) = ^{40}\text{Ar}_m - ^{40}\text{Ar}(a) - ^{40}\text{Ar}(K)$, so $^{40}\text{Ar}(r)$ and $^{40}\text{Ar}(a)$ are **anti-correlated**: $\text{cov}(^{40}\text{Ar}(r), ^{40}\text{Ar}(a)) = -\sigma_{40a}^2$
- Correct variance: $\sigma_{x_{40}}^2 = \sigma_{40r}^2 + \sigma_{40a}^2 + 2\,\text{cov} = \sigma_{40r}^2 - \sigma_{40a}^2$
- pyADR's `np.hypot` gives $\sigma_{40r}^2 + \sigma_{40a}^2$ — **over by $2\sigma_{40a}^2$**

Same pattern as v3.8.1 fix for σ_36(m)/σ_39(m). Effect: σ_40 inflated, MSWD systematically low, α/β/T potentially biased toward 36Ar/39Ar.

**Proposed fix**: `s40 = np.sqrt(max(σ_40r² − σ_40a², 0))` (clip-to-zero in the rare case σ_40a > σ_40r). Validation sample: SYL31 (Wu 2007, 115.4 ± 3.9 Ma).

### References for §11

| Topic | Reference |
|---|---|
| 3D plane ML algorithm | Kent J.T. et al. (1990) *Maximum likelihood estimation of a plane in three dimensions.* Statistics 21: 411–426 |
| Implementation (NTU thesis) | Wu C.-Y. (2007) *3-D Plane-fitting Program in 40Ar/39Ar Dating.* MSc thesis, NTU Geosciences (R94224113), advisor Ching-Hua Lo. Math derivations in Chapter 3 |
| Newton-Raphson + Lagrange | Titterington D.M., Halliday A.N. (1979) *On the fitting of parallel isochrons and the method of maximum likelihood.* Chem. Geol. 26: 183–195 |
| MSWD / residual analysis | Mahon K.I. (1996) *The new "York" regression: application of an improved statistical method to geochemistry.* Int. Geol. Rev. 38: 293–303 |
| σ-cap modified weighting | Mahon (1996); pyADR v3.4.3 addition |
| Age + σ_T propagation | Renne P.R. et al. (1998) *Intercalibration of standards, absolute ages and uncertainties in 40Ar/39Ar dating.* Chem. Geol. 145: 117–152.  Min K. et al. (2000) *A test for systematic errors in 40Ar/39Ar geochronology.* GCA 64: 73–98 |
| Koppers age error tables | Koppers A.A.P. (2002) *ArArCALC — software for 40Ar/39Ar age calculations.* Comput. Geosci. 28: 605–619 |
| Validation sample | SYL31 (Sylhet Trap basalt, India), Rajmahal-Sylhet eruption 119–116 Ma, Kerguelen Plume early product. Wu 2007 chapter 5

---

## ⚠️ Code-state warnings (v3.8.1 — synced with v5 math-audit report)

### Resolved in v3.7.4 / v3.8.0 (kept for traceability)

1. **`calcAge` truncation — RESOLVED in v3.7.4**. Function was truncated mid-statement in v3.7.0–v3.7.3; v3.7.4 restored the full implementation from the V3.4.1 archive.

2. **DiagramPlot F / WMA / MSWD bugs — RESOLVED in v3.8.0**. Three distinct bugs in `getDFStatistics_sh`/`_ls`: (a) inverse-isochron `F = 1/slope` (should be `−b/a`); (b) WMA loop with `(1/σ²·T)/(1/σ²)` cancels to Σ T; (c) MSWD reference was arithmetic mean instead of WMA. All three corrected. Validated against SYL31 LS (115.4 ± 3.9 Ma).

### Outstanding (P1 — Critical)

3. **σ_T0 underestimated ~10× (§1)** — `Utilities.calculateT0`/`REcalculateT0` lines 187, 216, 275, 294. Uses `std(|residuals|)/√N` instead of intercept SE `sqrt(pcov[-1,-1])`. AutoPipeline `_fit_one` was patched in v3.8.2; legacy functions still pending.

4. **σ_J v₃ bracket bug (§6)** — `Utilities.py:2864`. Operator precedence parses `((np.exp(l*t)) - 1 / F²)²` as `(e^λt − 1/F²)²` instead of `((e^λt − 1)/F²)²`. σ_J massively over-estimated for young samples. 5-min fix: add one pair of parentheses.

5. **Isochron intercept SE — OLS on the error bars (§10.8)** — `Utilities.py:389-390` (LS), `965-966` (SH normal). `curve_fit(linear, x_std, y_std) → linear(0, *popt_std)` is mathematically meaningless. Inverse-isochron paths (`441`, `1286`) correctly use `pcov[1,1]`; propagate that pattern.

### Outstanding (P2 — Major)

6. **Plateau "avg_age" uses arithmetic mean (§10.7)** — `Utilities.py:2031`. `np.mean(y_age[mask==1])` instead of the v3.8-corrected WMA from §10.5. Plot annotation inconsistent with the WMA in the regression summary.

7. **Linear-sum σ propagation in `getJVolumeStatistics`/`calcAge`** — `Utilities.py:2839, 2926, 2942` etc. Uses `F·Σ|σ_x/x|` instead of `√Σ(∂F/∂x · σ_x)²`. Inconsistent with AutoPipeline `_propagate` quadrature.

8. **J/Salt outlier mask uses ±1·σ_SE** — `getJStatistics:2209-2210`, `getSaltStatistics:2250`. Too tight; masks ~32% of normal points. Use 2σ or Chauvenet.

9. **Isochron regression — OLS not York (§10.8)** — `Utilities.py:360, 905, 1234`. Ignores σ_x and ρ(x,y). York regression planned for v3.9+.

### Outstanding (P3 — Minor)

10. **`Ar_38_Air` mis-named in calcAge** (`Utilities.py:2879`). Variable contains ³⁸Ar(air) + ³⁸Ar(Cl), but is labelled "Ar_38_Air". Proper split only in `toDP:4648–4664`.

11. **`T_std` in calcAge omits σ_λ** (`:2907`). McDougall & Harrison 1999 eq. 4.7 has three partials; pyADR drops `(∂T/∂λ)²σ_λ²`. ~0.5% relative under-estimate.

12. **λ source split: `constants[14]` vs `constants[16]`** — `getDegasPlot:444` uses [14]; calcAge `:2904`, `getStackPlot:1972` use [16]. Audit PS to confirm [14]==[16] or unify.

13. **J calc uses hardcoded λ, Age calc reads `constants[16]`** (`getJVolumeStatistics:2748-2749`). λ=5.531e-10 written in source. PS change creates systematic offset.

14. **Atmospheric ⁴⁰/³⁶ hardcoded 298.56 in salt functions** (`:2708, 2737-2738`). Rest of program reads `constants[12]`. Code style: replace literal with `constants[12]`.

15. **§2 T0 outlier mask threshold** uses `|T_{0,j} − μ| > σ/2 + μ` (`getT0Statistics:2550`). The `+ μ` term is dimensionally suspect. Verify with advisor.

16. **Salt σ on numerator subtraction** (`calculateSlatCa:2709`, `calculateSlatK:2738`) uses linear sum on `Ar36 − air/298.56`. Should be quadrature.

17. **Datum CSV does not write cov[X,Y]** (`NTNU_DR.py:3493`). Without ρ(x,y), downstream York / IsoplotR refitting from the CSV is impossible. Add 4 columns per Vermeesch (2018) Eq. 2.

---

## References

**Primary ⁴⁰Ar/³⁹Ar data-reduction:**

- McDougall, I., Harrison, T.M. (1999). *Geochronology and Thermochronology by the ⁴⁰Ar/³⁹Ar Method*, 2nd ed. Oxford UP.
- Koppers, A.A.P. (2002). ArArCALC — software for ⁴⁰Ar/³⁹Ar age calculations. *Computers & Geosciences* 28, 605–619.
- Schaen, A.J. et al. (2021). Interpreting and reporting ⁴⁰Ar/³⁹Ar geochronologic data. *GSA Bulletin* 133(3/4), 461–487.

**Isochron regression & WMA statistics (§10):**

- Vermeesch, P. (2024). Errorchrons and anchored isochrons in IsoplotR. *Geochronology* 6, 397–407.
- Vermeesch, P. (2018). IsoplotR: free open toolbox for geochronology. *Geoscience Frontiers* 9, 1479–1493.
- Vermeesch, P. (2015). Revised error propagation of ⁴⁰Ar/³⁹Ar data, including covariances. *GCA* 171, 325–337.
- Li, Y., Vermeesch, P. (2021). Inverse isochron regression for Re–Os, K–Ca, and other chronometers. *Geochronology* 3, 415–420.
- Powell, R., Green, E.C.R., Marillo Sialer, E., Woodhead, J. (2020). Robust Isochron Calculation. *Geochronology*.
- York, D., Evensen, N.M., Lopez-Martinez, M., De Basabe Delgado, J. (2004). Unified equations for the slope, intercept, and standard errors of the best straight line. *Am. J. Phys.* 72(3), 367–375.
- Kuiper, K.F. (2002). The interpretation of inverse isochron diagrams in ⁴⁰Ar/³⁹Ar geochronology. *EPSL* 203, 499–506.

**Intercept SE for linear regression (§1):**

- Li, X., Naeher, U., Pross, J. (2019). Mass spectrometric data processing in stable isotope analysis: regression-based standard errors of the y-intercept. *J. Mass Spectrom.* 54, 145–152.

**Modified weighting & 3D plane fit (PlaneFit3D):**

- Mahon, K.I. (1996). The New "York" Regression. *Int. Geol. Rev.* 38(4), 293–303.
- Kent, J.T., Watson, G.S., Onstott, T.C. (1990). Fitting straight lines and planes with an application to radiometric dating. *EPSL* 97, 1–17.
- Wu, M.-W. (2007). 3-D Plane-fitting Program in 40Ar/39Ar Dating. NTU MSc thesis R94224113.
