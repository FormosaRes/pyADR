# pyADR Formulas — ⁴⁰Ar/³⁹Ar Reduction Math Reference

**Version**: v3.7.2 (2026-05) · **Scope**: T0 fitting → Mass Ratio → Air Ratio → J → Age → Datum Publication

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

**T0 sigma (residual SE of the mean, `Utilities.py:180,209,268,287`):**

$$
\sigma_{T_0,i} \;=\; \frac{\mathrm{std}\!\left(\,\bigl|\,V_j - \hat{V}(t_j)\bigr|\,\right)}{\sqrt{N-n_{\text{out}}}}
$$

where `n_out` is the number of cycles masked out by the outlier rule

$$
|V_j-\hat V(t_j)| > \sigma_{T_0,i}^{(\text{prev})} \quad\text{and}\quad R^2 \le 0.8
$$

(at most 4 cycles removed; up to 1 retry).

**Goodness:** R² from `sklearn.metrics.r2_score`.

> The "STD-of-residuals over √N" form is what the NTNU lab uses for ToD reproducibility; it is **not** the formal regression-coefficient SE that `curve_fit` returns.

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
\boxed{\;\text{Ar}_{40,r} = \text{Ar}_{40,m} - \text{Ar}_{40,\text{air}} - \text{Ar}_{40,K}\;}
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
\sigma_J^{2} = \underbrace{\left(\frac{t\,e^{\lambda t}}{F_{r/k}}\right)^{2}\sigma_\lambda^{2}}_{v_1}
+ \underbrace{\left(\frac{\lambda\,e^{\lambda t}}{F_{r/k}}\right)^{2}\sigma_t^{2}}_{v_2}
+ \underbrace{\left(\frac{e^{\lambda t}-1}{F_{r/k}^{2}}\right)^{2}\sigma_F^{2}}_{v_3}
$$

$$
\sigma_J^{(\text{int})} = \sqrt{v_3}
$$

Hard-coded constants in this function: `λ = 5.531e-10 /yr`, `σ_λ = 0.0135e-10 /yr` (Steiger & Jäger 1977 ⁴⁰K → ⁴⁰Ar branch). For Min et al. (2000) values, change `l, l_std` at `Utilities.py:2748–2749`.

**Ca/K (`:2807–2808`):**

$$
\mathrm{Ca/K} = \frac{0.52\cdot\text{Ar}_{37,\text{Ca}}}{\text{Ar}_{39,K}}, \qquad
\sigma = \mathrm{Ca/K}\!\cdot\!\left(\frac{\sigma_{37,\text{Ca}}}{\text{Ar}_{37,\text{Ca}}}+\frac{\sigma_{39,K}}{\text{Ar}_{39,K}}\right)
$$

The factor 0.52 is the lab calibration (production cross-section for ³⁷Ar from ⁴⁰Ca / ³⁹Ar from ³⁹K). v3.0.1 fixed an inverted Ca/K and a wrong constant (was `pr_ratio=0.000377`).

---

## 7. Age Calculation — `calcAge`

`Utilities.py:2811–2846`  ⚠️ **TRUNCATED in current HEAD** (see warning at end of doc)

Reconstructed from the symmetric structure of `getJVolumeStatistics` and the 31 result rows defined in `UI/AgeCalculation.py:121–182`. The result vector `AgeCalculation_result` packs each row as `(value, sigma)` with `[46]/[47]` = T (yr), σ_T (yr).

**Component partition** (identical to §6 with σ propagated):

$$
\text{Ar}_{37,\text{Ca}} = \text{Ar}_{37,m}
$$

$$
\text{Ar}_{36,\text{Ca}} = \text{Ar}_{37,\text{Ca}}\cdot c_2, \qquad
\sigma = \text{Ar}_{36,\text{Ca}}\!\cdot\!\left(\frac{\sigma_{37,\text{Ca}}}{\text{Ar}_{37,\text{Ca}}}+\frac{c_3}{c_2}\right)
$$

$$
\text{Ar}_{36,\text{air}} = \text{Ar}_{36,m} - \text{Ar}_{36,\text{Ca}}, \qquad
\sigma = \sqrt{\sigma_{36,m}^{2}+\sigma_{36,\text{Ca}}^{2}}
$$

(same pattern for ³⁹_K, ⁴⁰_air, ⁴⁰_K, ⁴⁰_r as §6.)

**F = ⁴⁰Ar*/³⁹Arₖ:**

$$
F = \frac{\text{Ar}_{40,r}}{\text{Ar}_{39,K}}, \qquad
\sigma_F = F\sqrt{\left(\frac{\sigma_{40,r}}{\text{Ar}_{40,r}}\right)^{2}+\left(\frac{\sigma_{39,K}}{\text{Ar}_{39,K}}\right)^{2}}
$$

**Age equation (`age equation`, line referenced at `:444, :970, :1428, :1443, :1972` in plotting helpers):**

$$
\boxed{\;T \;=\; \frac{1}{\lambda_{\text{total}}}\,\ln\!\bigl(1 + J\cdot F\bigr)\;}
$$

**Age uncertainty (full propagation, McDougall & Harrison 1999 eq. 4.7):**

$$
\sigma_T^{2} = \left(\frac{\partial T}{\partial J}\right)^{2}\sigma_J^{2}
+ \left(\frac{\partial T}{\partial F}\right)^{2}\sigma_F^{2}
+ \left(\frac{\partial T}{\partial \lambda}\right)^{2}\sigma_\lambda^{2}
$$

with partials

$$
\frac{\partial T}{\partial J} = \frac{F}{\lambda(1+JF)}, \qquad
\frac{\partial T}{\partial F} = \frac{J}{\lambda(1+JF)}, \qquad
\frac{\partial T}{\partial \lambda} = -\frac{T}{\lambda}
$$

**Internal age uncertainty** (J-internal only, used for inter-aliquot comparison):

$$
\sigma_T^{(\text{int})} = \frac{F}{\lambda(1+JF)}\,\sigma_J^{(\text{int})}
$$

i.e. drop the σ_λ and the J-from-standard component (item v₁+v₂ in §6).

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
\boxed{\;\text{Ar}_{38,Cl} = \text{Ar}_{38,m} - \text{Ar}_{38,\text{air}} - \text{Ar}_{38,K}\;}
$$

$$
\sigma_{38,Cl} = \sqrt{\sigma_{38,m}^{2}+\sigma_{38,\text{air}}^{2}+\sigma_{38,K}^{2}}\quad\text{(quadrature, `:4664`)}
$$

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

## 10. Diagram-page derived quantities (Inverse / Normal Isochron, Spectrum)

`Utilities.py:307–460, 462–1496, 928–946, 1086+, 1395–1517, 3255–3370`

**Inverse isochron (DF Inverse Isochron, e.g. `:336–341`):**

$$
x = \frac{m_{39}}{m_{40}}, \qquad y = \frac{m_{36}}{m_{40}}, \qquad
\sigma_x = \sigma_{m_{39}}/\sigma_{m_{40}}\ldots
$$

Linear regression by York-style weighted least squares (point-by-point in `_smart_set` / DF panels). Age from x-intercept (`:1318–1326`):

$$
T = \frac{1}{\lambda}\ln\!\left(1+\frac{J}{x_{\text{int}}}\right)\quad\text{or}\quad T = \frac{1}{\lambda}\ln(1+J\cdot F_{\text{x-int}})
$$

where `F_x-int = -slope/intercept` for the inverse-isochron geometry.

**Normal isochron (rare in this codebase; computed in step plots when invoked).**

**Step age (`:1428–1443`):**

$$
T_j = \frac{1}{\lambda}\ln(1+J\cdot F_j)
$$

**Total fusion / weighted-mean plateau age (`:1543–1551, 1972`):**

$$
F_{\text{total}} = \frac{\sum_j {}^{40}\mathrm{Ar}_{r,j}}{\sum_j {}^{39}\mathrm{Ar}_{K,j}},\qquad
T_{\text{total}} = \frac{\ln(1+J\cdot F_{\text{total}})}{\lambda}/10^{6}\ \text{(Ma)}
$$

σ for plateau weighted mean: standard inverse-variance (see §5 form, applied to per-step T).

---

## ⚠️ Code-state warnings (must address before publishing this doc)

1. **`calcAge` in `Utilities.py:2811` is truncated.** Function ends mid-statement at line 2846 (`Ar_39_Ca = Ar_37_Ca * constants[0] #3` with no return) and has been so since commit `afb2268` (initial v3.7 release). Either:
   - the AgeCalculation page in pyADR has never run successfully under HEAD, or
   - calls bypass it via `getJVolumeStatistics` + per-step recomputation in `toDP`.
   §7 above is the **intended** math reconstructed from the UI row labels and the symmetric structure of `getJVolumeStatistics`. Fix `calcAge` to actually compute and return the 31-row vector before relying on this section in production.

2. Several σ formulas use **linear sum** (`F·Σ|σ_x/x|`) instead of **quadrature**. This is not wrong — it's a conservative bound — but it differs from McDougall & Harrison 1999 / ArArCalc / Mass Spec. Lines flagged in §0 Note. Decide on one convention before submitting Datum tables to a journal.

3. Atmospheric ⁴⁰/³⁶ is **hardcoded 298.56** in `calculateSlatCa/K` (`:2708, 2737–2738`). The rest of the program reads `constants[12]` from Parameter Setting. If you change air ratio in PS, you must also edit those two lines or your salt-derived interference factors will not match the rest of the calculation chain.

4. Decay constants `λ=5.531e-10`, `σ_λ=0.0135e-10` in `getJVolumeStatistics:2748–2749` are **also hardcoded** (Steiger & Jäger 1977). To switch to Min et al. 2000 (`λ=5.463e-10`, `σ_λ=0.0107e-10`) edit those lines AND the corresponding entries in `constants[14]/[16]`.

---

## References

- McDougall, I., Harrison, T.M. (1999). *Geochronology and Thermochronology by the ⁴⁰Ar/³⁹Ar Method*, 2nd ed. Oxford UP.
- Koppers, A.A.P. (2002). ArArCALC — software for ⁴⁰Ar/³⁹Ar age calculations. *Computers & Geosciences* 28, 605–619. doi:10.1016/S0098-3004(01)00095-4
- Min, K., Mundil, R., Renne, P.R., Ludwig, K.R. (2000). A test for systematic errors in ⁴⁰Ar/³⁹Ar geochronology through comparison with U/Pb analysis of a 1.1-Ga rhyolite. *Geochim. Cosmochim. Acta* 64, 73–98.
- Steiger, R.H., Jäger, E. (1977). Subcommission on geochronology: convention on the use of decay constants in geo- and cosmochronology. *EPSL* 36, 359–362.
- Lee, J.-Y. et al. (2006). A redetermination of the isotopic abundances of atmospheric Ar. *GCA* 70, 4507–4512.

