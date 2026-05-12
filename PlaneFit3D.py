# -*- coding: utf-8 -*-
"""
PlaneFit3D.py  —  3D plane regression for 40Ar/39Ar dating
============================================================
Kent et al. (1990) maximum likelihood method.
Reference: Wu (2007) NTU MSc thesis "3-D Plane-fitting Program in 40Ar/39Ar Dating"

Model: 40Ar = α·36Ar + β·39Ar
  α = (40Ar/36Ar)₀  →  initial non-radiogenic ratio (intercept)
  β = 40Ar*/39Ar_K  →  radiogenic parameter for age calculation

v3.4.2 (2026-05):
  - Vectorized grad/Hess; internal X (n,3) and A (n,3,3) ndarrays
  - Newton–Raphson with backtracking line search (monotone L_p increase)
  - MSWD CI via scipy.stats.chi2 (exact)
  - _param_cov uses np.linalg.solve instead of inv
  - fit_plane: verbose flag (default False); returns standardized residuals
  - plot_result: distinguishes under/over-dispersed MSWD; highlights |r|>2 in red
  - extract_from_pipeline: step_idx + min_steps
  - Documented sign correction of _grad/_param_cov vs Wu (2007) eq 3-10/3-27

v3.4.3 (2026-05):
  - fit_plane: sigma_cap_rel (Mahon 1996-style modified weighting). Caps σ/|x|
        per axis to prevent background-dominated steps from underdispersing MSWD.
  - Inverse-isochron x-axis (39/40) errorbar now includes cov(39,40)=−k0·σ_39²
  - 3D surface plot uses additive padding (safe with negative minima).
  - find_subplanes(): sliding-window search for valid sub-plateaus.
  - _ols_initial: removed hardcoded 295.5; data-driven fallback.
"""

import numpy as np
from numpy.linalg import solve, LinAlgError
from scipy.stats import chi2 as _chi2
import matplotlib
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401
import matplotlib.gridspec as gridspec
import warnings

LAM_DEFAULT = 5.543e-10      # 40K total decay constant (a⁻¹), Steiger & Jäger 1977


def _mswd_ci(df, level=0.95):
    """Exact MSWD = χ²(df)/df CI via scipy."""
    if df < 1:
        return np.nan, np.nan
    a = 1.0 - level
    lo, hi = _chi2.ppf([a/2, 1.0 - a/2], df) / df
    return float(lo), float(hi)


# ═══════════════════════════════════════════════════════════════════════════════
#  MATH CORE — Wu (2007) eq numbering
# ═══════════════════════════════════════════════════════════════════════════════

def build_cov(s36, s39, s40, k0):
    """3×3 covariance matrix A_i (Wu 2007 eq 3-19)."""
    v36, v39, v40 = s36**2, s39**2, s40**2
    return np.array([
        [v36,  0.,          0.       ],
        [0.,   v39,        -k0*v39   ],
        [0.,  -k0*v39,      v40      ],
    ])


def _apply_sigma_cap(x, s, cap):
    """Mahon-1996-style σ cap: σ_eff = min(σ, cap · |x|). cap=None disables."""
    if cap is None:
        return np.asarray(s, float)
    s_arr = np.asarray(s, float)
    return np.minimum(s_arr, float(cap) * np.abs(np.asarray(x, float)))


def _parse_cap(cap):
    """Return (cap36, cap39, cap40). Accepts None, scalar, 3-tuple, or dict."""
    if cap is None:
        return None, None, None
    if isinstance(cap, dict):
        return cap.get('36'), cap.get('39'), cap.get('40')
    if np.isscalar(cap):
        return float(cap), float(cap), float(cap)
    c36, c39, c40 = cap
    return c36, c39, c40


def _build_arrays(x36, x39, x40, s36, s39, s40, k0, sigma_cap_rel=None):
    """
    Pack columns into X (n,3) and A (n,3,3); apply Mahon σ-cap if requested.

    sigma_cap_rel:
        None             → classical Kent weights (no cap)
        float c          → cap σ/|x| ≤ c on all three isotopes
        (c36, c39, c40)  → per-axis cap (None in any slot skips that axis)
        dict {'36':..., '39':..., '40':...}  → same, by key

    Caps prevent background-dominated steps (σ ≫ signal) from underdispersing
    MSWD and over-estimating σ_α, σ_β.
    """
    n = len(x36)
    X = np.column_stack([x36, x39, x40]).astype(float)
    c36, c39, c40 = _parse_cap(sigma_cap_rel)
    s36e = _apply_sigma_cap(x36, s36, c36)
    s39e = _apply_sigma_cap(x39, s39, c39)
    s40e = _apply_sigma_cap(x40, s40, c40)
    v36, v39, v40 = s36e**2, s39e**2, s40e**2
    A = np.zeros((n, 3, 3))
    A[:, 0, 0] = v36
    A[:, 1, 1] = v39
    A[:, 2, 2] = v40
    A[:, 1, 2] = -k0 * v39
    A[:, 2, 1] = -k0 * v39
    return X, A, (s36e, s39e, s40e)


def _kernels(delta, X, A):
    """Vectorized s_i, q_i, v_i, xs, As (per-point quantities)."""
    xs = X[:, :2]; x3 = X[:, 2]
    As = A[:, :2, :2]; b = A[:, :2, 2]; c = A[:, 2, 2]
    s = xs @ delta - x3
    Asd = np.einsum('nij,j->ni', As, delta)
    v = Asd - b
    q = (Asd * delta).sum(-1) - 2.0 * (b @ delta) + c
    return s, q, v, xs, As


def _Lp(delta, X, A):
    """Profile log-likelihood L_p(δ) = −½ Σ s²/q (Wu eq 3-7)."""
    s, q, *_ = _kernels(delta, X, A)
    return -0.5 * float((s**2 / q).sum())


def _grad(delta, X, A):
    """
    Return +∂L_p/∂δ.

    SIGN CONVENTION vs Wu (2007) eq 3-10: that equation writes −∂L_p/∂δ; this
    returns the negative of that. Combined with _hess() returning H = −∂²L_p,
    the Newton update d_new = d + H⁻¹·g moves uphill on L_p (signs cancel).
    """
    s, q, v, xs, _ = _kernels(delta, X, A)
    return ((s**2 / q**2)[:, None] * v - (s / q)[:, None] * xs).sum(axis=0)


def _hess(delta, X, A):
    """H = −∂²L_p/∂δ∂δᵀ (Wu eq 3-11), positive-definite at MLE."""
    s, q, v, xs, As = _kernels(delta, X, A)
    w1 = 1.0 / q
    w2 = 2.0 * s / q**2
    w3 = 4.0 * s**2 / q**3
    w4 = s**2 / q**2
    xx = np.einsum('ni,nj->nij', xs, xs)
    xv = np.einsum('ni,nj->nij', xs, v)
    vv = np.einsum('ni,nj->nij', v, v)
    H = (  w1[:, None, None] * xx
         - w2[:, None, None] * (xv + xv.transpose(0, 2, 1))
         + w3[:, None, None] * vv
         - w4[:, None, None] * As).sum(axis=0)
    return H


def _ols_initial(x36, x39, x40):
    """OLS δ₀ (Wu eq 3-17). Fallback uses 1D regression of x40 on x39."""
    M = np.column_stack([x36, x39])
    try:
        return solve(M.T @ M, M.T @ x40)
    except LinAlgError:
        x39m, x40m, x36m = x39.mean(), x40.mean(), x36.mean()
        denom = float(np.sum((x39 - x39m)**2)) + 1e-300
        beta0  = float(np.sum((x39 - x39m) * (x40 - x40m))) / denom
        alpha0 = (x40m - beta0 * x39m) / (x36m + 1e-300)
        return np.array([alpha0, beta0])


def _newton_raphson(X, A, d0, tol=1e-10, max_iter=500, ls_max=20):
    """Newton–Raphson with backtracking line search (monotone L_p increase)."""
    d = np.asarray(d0, float).copy()
    Lp_cur = _Lp(d, X, A)
    for k in range(max_iter):
        g = _grad(d, X, A)
        H = _hess(d, X, A)
        try:
            step = solve(H, g)
        except LinAlgError:
            return d, k + 1, False
        a = 1.0
        d_new  = d + step
        Lp_new = _Lp(d_new, X, A)
        ls = 0
        while (not np.isfinite(Lp_new) or Lp_new < Lp_cur) and ls < ls_max:
            a *= 0.5
            d_new  = d + a * step
            Lp_new = _Lp(d_new, X, A)
            ls += 1
        e = np.linalg.norm(d - d_new) / (np.linalg.norm(d_new) + 1e-40)
        d, Lp_cur = d_new, Lp_new
        if e < tol:
            return d, k + 1, True
    return d, max_iter, False


def _compute_mswd(delta, X, A):
    """S²=Σs²/q (Wu eq 3-24); MSWD=S²/(n-2); 95% CI via scipy."""
    s, q, *_ = _kernels(delta, X, A)
    S2 = float((s**2 / q).sum())
    df = len(X) - 2
    mswd = S2 / df if df > 0 else np.nan
    lo, hi = _mswd_ci(df)
    return S2, mswd, df, lo, hi


def _param_cov(delta, X, A, tau2=1.0):
    """
    cov(δ̂) = τ² · H⁻¹  where H = −∂²L_p/∂δ∂δᵀ (observed Fisher info).

    ⚠ TYPO CORRECTION vs Wu (2007) eq 3-27
    Wu eq 3-27 writes cov(δ̂) = τ²·(∂²L_p/∂δ∂δᵀ)⁻¹ — sign error: at the MLE
    ∂²L_p is negative-definite, so its inverse is negative-definite and gives
    negative variances. The correct ML asymptotic covariance is
        cov(δ̂) = τ²·(−∂²L_p/∂δ∂δᵀ)⁻¹ = τ²·H⁻¹.
    """
    H = _hess(delta, X, A)
    try:
        cov = tau2 * solve(H, np.eye(2))
    except LinAlgError:
        return np.nan, np.nan, None
    return float(cov[0, 0]), float(cov[1, 1]), cov


def age_from_beta(beta, J, lam=LAM_DEFAULT):
    """t = (1/λ)·ln(β·J + 1)  in years."""
    v = beta * J + 1.0
    return np.log(v) / lam if v > 0 else np.nan


def age_error_1sigma(beta, s_beta, J, s_J, lam=LAM_DEFAULT, s_lam=0.0):
    """σ_t via standard error propagation."""
    v = beta * J + 1.0
    if v <= 0 or beta <= 0:
        return np.nan
    dt_db = J / (lam * v)
    dt_dJ = beta / (lam * v)
    dt_dl = -np.log(v) / lam**2
    return np.sqrt((dt_db*s_beta)**2 + (dt_dJ*s_J)**2 + (dt_dl*s_lam)**2)


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def fit_plane(x36, s36, x39, s39, x40, s40,
              J=None, s_J=0.0,
              lam=LAM_DEFAULT, s_lam=0.0,
              k0=0.025004,
              tol=1e-10,
              sigma_cap_rel=None,
              verbose=False):
    """
    Fit 40Ar = α·36Ar + β·39Ar by Kent (1990) ML.

    sigma_cap_rel : None | float | (c36, c39, c40) | dict
        Mahon (1996)-style modified weighting. Caps σ_i/|x_i| at given relative
        value(s). Typical 0.2–0.5. Default None (classical weights).

    Returns dict with keys including:
      alpha, s_alpha, beta, s_beta, mswd, df, mswd_lo95, mswd_hi95,
      residuals (s/√q), age_Ma, s_age_Ma,
      s36_eff, s39_eff, s40_eff (σ after σ-cap), sigma_cap_rel.
    """
    x36, s36, x39, s39, x40, s40 = (np.asarray(a, float)
                                     for a in (x36, s36, x39, s39, x40, s40))
    n = len(x36)
    assert n >= 3, "Need ≥ 3 points for plane fit."

    X, A, (s36e, s39e, s40e) = _build_arrays(
        x36, x39, x40, s36, s39, s40, k0, sigma_cap_rel=sigma_cap_rel)

    d0 = _ols_initial(x36, x39, x40)
    delta, ni, conv = _newton_raphson(X, A, d0, tol=tol)
    alpha, beta = delta

    S2, mswd, df, mlo, mhi = _compute_mswd(delta, X, A)
    tau2 = S2 / df if (not np.isnan(mswd) and mswd > mhi) else 1.0
    va, vb, cov_mat = _param_cov(delta, X, A, tau2)
    sa = np.sqrt(max(va, 0.0)) if not np.isnan(va) else np.nan
    sb = np.sqrt(max(vb, 0.0)) if not np.isnan(vb) else np.nan

    s_arr, q_arr, *_ = _kernels(delta, X, A)
    residuals = s_arr / np.sqrt(np.maximum(q_arr, 1e-300))

    age_yr = s_age_yr = np.nan
    if J is not None and beta > 0:
        age_yr   = age_from_beta(beta, J, lam)
        s_age_yr = age_error_1sigma(beta, sb, J, s_J, lam, s_lam)

    if verbose:
        print(f"PlaneFit3D: n={n}, df={df}")
        print(f"  α = {alpha:.5g} ± {sa:.4g}")
        print(f"  β = {beta:.5g} ± {sb:.4g}")
        print(f"  MSWD = {mswd:.3f}  (95% CI: {mlo:.2f}–{mhi:.2f})")
        if not np.isnan(age_yr):
            print(f"  Age = {age_yr/1e6:.3f} ± {s_age_yr/1e6:.3f} Ma")
        print(f"  N-R: {ni} iter, converged={conv}")
        n_out = int(np.sum(np.abs(residuals) > 2))
        if n_out:
            print(f"  outliers (|r|>2): {n_out} point(s)")

    return dict(
        alpha=alpha, s_alpha=sa, beta=beta, s_beta=sb,
        mswd=mswd, df=df, mswd_lo95=mlo, mswd_hi95=mhi,
        S2=S2, tau2=tau2,
        age_yr=age_yr, s_age_yr=s_age_yr,
        age_Ma=age_yr/1e6    if not np.isnan(age_yr)   else np.nan,
        s_age_Ma=s_age_yr/1e6 if not np.isnan(s_age_yr) else np.nan,
        n_iter=ni, converged=conv,
        delta=delta, X=X, A=A,
        residuals=residuals,
        cov_matrix=cov_mat,
        x36=x36, s36=s36, x39=x39, s39=s39, x40=x40, s40=s40,
        s36_eff=s36e, s39_eff=s39e, s40_eff=s40e,
        sigma_cap_rel=sigma_cap_rel,
        J=J, s_J=s_J, lam=lam, k0=k0, n=n,
    )


def find_subplanes(x36, s36, x39, s39, x40, s40,
                   J=None, s_J=0.0, k0=0.025004,
                   min_steps=4, consecutive=True,
                   sigma_cap_rel=None, max_results=10):
    """
    Sliding-window search for sub-plateaus with MSWD inside the 95% χ² CI.
    Returns list of dicts {idx, i, j, n, result}, sorted by length (desc).
    """
    if not consecutive:
        raise NotImplementedError("consecutive=False not yet implemented.")
    n_total = len(x36)
    hits = []
    for i in range(n_total):
        for j in range(i + min_steps, n_total + 1):
            try:
                r = fit_plane(x36[i:j], s36[i:j], x39[i:j], s39[i:j],
                              x40[i:j], s40[i:j],
                              J=J, s_J=s_J, k0=k0, sigma_cap_rel=sigma_cap_rel)
            except Exception:
                continue
            if not r['converged']:
                continue
            if r['mswd_lo95'] <= r['mswd'] <= r['mswd_hi95']:
                hits.append(dict(idx=range(i, j), i=i, j=j, n=j-i, result=r))
    hits.sort(key=lambda h: (-h['n'], abs(h['result']['mswd'] - 1.0)))
    return hits[:max_results]


def extract_from_pipeline(step_results, step_idx=None, min_steps=3, k0=0.025004):
    """
    Build (x36, s36, x39, s39, x40, s40) from _propagate() result dicts.
    step_idx selects a subset; min_steps enforces lower bound.
    """
    if step_idx is not None:
        step_idx = list(step_idx)
        try:
            step_results = [step_results[i] for i in step_idx]
        except (IndexError, TypeError) as e:
            raise ValueError(f"step_idx contains out-of-range index: {e}")
    if len(step_results) < min_steps:
        raise ValueError(f"need ≥ {min_steps} steps, got {len(step_results)}")
    arrs = {'x36': [], 's36': [], 'x39': [], 's39': [], 'x40': [], 's40': []}
    for c in step_results:
        arrs['x36'].append(c['Ar36_air'][0])
        arrs['s36'].append(c['Ar36_air'][1])
        arrs['x39'].append(c['Ar39_K'][0])
        arrs['s39'].append(c['Ar39_K'][1])
        arrs['x40'].append(c['Ar40_r'][0] + c['Ar40_air'][0])
        arrs['s40'].append(np.hypot(c['Ar40_r'][1], c['Ar40_air'][1]))
    return tuple(np.array(arrs[k]) for k in ('x36','s36','x39','s39','x40','s40'))
# ═══════════════════════════════════════════════════════════════════════════════
#  PLOTTING — single fit
# ═══════════════════════════════════════════════════════════════════════════════

def plot_result(result, title='', labels=None, figsize=(16, 12), save_path=None,
                outlier_sigma=2.0):
    """
    4-panel figure with outlier highlighting (|standardized residual| > outlier_sigma → red).
    """
    r = result
    x36, s36, x39, s39, x40, s40 = r['x36'], r['s36'], r['x39'], r['s39'], r['x40'], r['s40']
    alpha, beta, sa, sb = r['alpha'], r['beta'], r['s_alpha'], r['s_beta']
    n = r['n']
    resid = np.asarray(r['residuals'])
    outlier = np.abs(resid) > outlier_sigma
    color_main = '#1a5fb4'
    color_out  = '#c01c28'
    lbl = labels if labels else [str(i+1) for i in range(n)]

    fig = plt.figure(figsize=figsize, facecolor='#f8f8f6')
    gs  = gridspec.GridSpec(2, 2, figure=fig, wspace=0.38, hspace=0.42)

    # A: 3D
    ax3 = fig.add_subplot(gs[0, 0], projection='3d')
    ax3.set_facecolor('#f0f0f0')
    for i in range(n):
        ax3.scatter([x36[i]], [x39[i]], [x40[i]],
                    c=color_out if outlier[i] else color_main,
                    s=42, zorder=5, depthshade=True)
        ax3.text(x36[i], x39[i], x40[i], lbl[i], fontsize=6, color='#333')
    rg36 = max(x36.max() - x36.min(), 1e-30)
    rg39 = max(x39.max() - x39.min(), 1e-30)
    pad = 0.15
    x36g = np.linspace(x36.min() - pad*rg36, x36.max() + pad*rg36, 20)
    x39g = np.linspace(x39.min() - pad*rg39, x39.max() + pad*rg39, 20)
    G36, G39 = np.meshgrid(x36g, x39g)
    G40 = alpha*G36 + beta*G39
    ax3.plot_surface(G36, G39, G40, alpha=0.22, color='#3584e4',
                     edgecolor='#3584e4', linewidth=0.1)
    ax3.set_xlabel('$^{36}$Ar', fontsize=8, labelpad=3)
    ax3.set_ylabel('$^{39}$Ar', fontsize=8, labelpad=3)
    ax3.set_zlabel('$^{40}$Ar', fontsize=8, labelpad=3)
    ax3.set_title('3D Plane: $^{40}$Ar $= \\alpha\\cdot^{36}$Ar $+ \\beta\\cdot^{39}$Ar',
                  fontsize=8.5, pad=6)
    ax3.tick_params(labelsize=6)

    # B: Normal isochron
    ax_ni = fig.add_subplot(gs[0, 1])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        mask = x36 > 0
        rx = np.where(mask, x39/x36, np.nan)
        ry = np.where(mask, x40/x36, np.nan)
        x36s = np.where(x36 != 0, x36, 1)
        x39s = np.where(x39 != 0, x39, 1)
        x40s = np.where(x40 != 0, x40, 1)
        erx = np.abs(rx) * np.sqrt((s39/x39s)**2 + (s36/x36s)**2)
        ery = np.abs(ry) * np.sqrt((s40/x40s)**2 + (s36/x36s)**2)
    for i in range(n):
        if np.isnan(rx[i]):
            continue
        col = color_out if outlier[i] else color_main
        ax_ni.errorbar(rx[i], ry[i], xerr=erx[i], yerr=ery[i], fmt='o',
                        color=col, ms=4, elinewidth=0.8, capsize=2, zorder=3)
        ax_ni.annotate(lbl[i], (rx[i], ry[i]), fontsize=6, color='#444',
                       xytext=(3,3), textcoords='offset points')
    xl = np.array([np.nanmin(rx)*0.85, np.nanmax(rx)*1.15])
    ax_ni.plot(xl, alpha + beta*xl, 'r-', lw=1.3,
               label=f'slope (β) = {beta:.4g} ± {sb:.3g}')
    ax_ni.axhline(alpha, ls='--', color='#888', lw=0.8,
                  label=f'intercept (α) = {alpha:.4g} ± {sa:.3g}')
    ax_ni.set_xlabel('$^{39}$Ar / $^{36}$Ar', fontsize=9)
    ax_ni.set_ylabel('$^{40}$Ar / $^{36}$Ar', fontsize=9)
    ax_ni.set_title('Normal Isochron', fontsize=9)
    ax_ni.legend(fontsize=7)
    ax_ni.tick_params(labelsize=7)
    ax_ni.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
    ax_ni.grid(True, lw=0.3, alpha=0.5)

    # C: Inverse isochron (with cov(39,40) correction on x errorbar)
    ax_ii = fig.add_subplot(gs[1, 0])
    k0_val = r.get('k0', 0.025004)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        mask40 = x40 > 0
        rx2 = np.where(mask40, x39/x40, np.nan)
        ry2 = np.where(mask40, x36/x40, np.nan)
        # var(39/40)/(39/40)² = (s39/39)² + (s40/40)² + 2·k0·s39²/(39·40)
        cov_term = 2.0 * k0_val * s39**2 / (x39s * x40s)
        var_rx2_rel = (s39/x39s)**2 + (s40/x40s)**2 + cov_term
        erx2 = np.abs(rx2) * np.sqrt(np.maximum(var_rx2_rel, 0.0))
        ery2 = np.abs(ry2) * np.sqrt((s36/x36s)**2 + (s40/x40s)**2)
    for i in range(n):
        if np.isnan(rx2[i]):
            continue
        col = color_out if outlier[i] else color_main
        ax_ii.errorbar(rx2[i], ry2[i], xerr=erx2[i], yerr=ery2[i], fmt='o',
                       color=col, ms=4, elinewidth=0.8, capsize=2, zorder=3)
        ax_ii.annotate(lbl[i], (rx2[i], ry2[i]), fontsize=6, color='#444',
                       xytext=(3,3), textcoords='offset points')
    if alpha != 0:
        xl2 = np.array([0.0, np.nanmax(rx2)*1.15])
        yl2 = 1./alpha + (-beta/alpha)*xl2
        ax_ii.plot(xl2, yl2, 'r-', lw=1.3)
        ax_ii.axhline(1./alpha, ls='--', color='#888', lw=0.8,
                      label=f'y-int = 1/α = {1/alpha:.4g}')
        if beta != 0:
            ax_ii.axvline(1./beta, ls=':', color='#888', lw=0.8,
                          label=f'x-int = 1/β = {1/beta:.4g}')
    ax_ii.set_xlabel('$^{39}$Ar / $^{40}$Ar', fontsize=9)
    ax_ii.set_ylabel('$^{36}$Ar / $^{40}$Ar', fontsize=9)
    ax_ii.set_title('Inverse Isochron', fontsize=9)
    ax_ii.legend(fontsize=7)
    ax_ii.tick_params(labelsize=7)
    ax_ii.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
    ax_ii.grid(True, lw=0.3, alpha=0.5)

    # D: Results table
    ax_tb = fig.add_subplot(gs[1, 1])
    ax_tb.axis('off')

    mswd_lo, mswd_hi, mswd_val = r['mswd_lo95'], r['mswd_hi95'], r['mswd']
    if np.isnan(mswd_val):
        mswd_status, status_color = 'n/a', '#eeeeee'
    elif mswd_val < mswd_lo:
        mswd_status, status_color = '⚠ underdispersed', '#fff5d6'
    elif mswd_val > mswd_hi:
        mswd_status, status_color = '✗ overdispersed', '#fde8e8'
    else:
        mswd_status, status_color = '✓ OK', '#d0edda'

    n_out = int(np.sum(outlier))
    rows = [
        ['n',               str(r['n'])],
        ['df',              str(r['df'])],
        ['α (40Ar/36Ar)₀',  f"{alpha:.5g}"],
        ['σ_α',             f"± {sa:.4g}"],
        ['β (40Ar*/39Ar)',  f"{beta:.5g}"],
        ['σ_β',             f"± {sb:.4g}"],
        ['MSWD',            f"{mswd_val:.3f}"],
        ['95% CI',          f"[{mswd_lo:.2f}, {mswd_hi:.2f}]"],
        ['MSWD status',     mswd_status],
        ['τ²',              f"{r['tau2']:.3f}"],
        [f'outliers (|r|>{outlier_sigma:g})', f"{n_out}"],
        ['N-R iters',       f"{r['n_iter']} ({'converged' if r['converged'] else 'NOT converged'})"],
    ]
    if r.get('sigma_cap_rel') is not None:
        rows.insert(2, ['σ-cap (Mahon)', f"{r['sigma_cap_rel']}"])
    if r['J'] is not None and not np.isnan(r['age_Ma']):
        rows += [
            ['J',           f"{r['J']:.6g} ± {r['s_J']:.3g}"],
            ['Age (Ma)',    f"{r['age_Ma']:.3f} ± {r['s_age_Ma']:.3f}"],
        ]

    tab = ax_tb.table(cellText=rows, colLabels=['Parameter', 'Value'],
                      loc='center', cellLoc='left')
    tab.auto_set_font_size(False)
    tab.set_fontsize(8.5)
    tab.scale(1.0, 1.5)
    for (row, col), cell in tab.get_celld().items():
        cell.set_edgecolor('#cccccc')
        if row == 0:
            cell.set_facecolor('#eeede8')
            cell.set_text_props(fontweight='bold')
        else:
            param_key = rows[row-1][0].lower()
            if 'status' in param_key:
                cell.set_facecolor(status_color)
            elif 'outlier' in param_key and n_out > 0:
                cell.set_facecolor('#fde8e8')
            elif row % 2 == 0:
                cell.set_facecolor('#f5f5f2')
    ax_tb.set_title('Regression Summary', fontsize=9, pad=3)

    if title:
        fig.suptitle(title, fontsize=11, y=1.01, fontweight='bold')
    fig.subplots_adjust(left=0.05, right=0.97, top=0.92, bottom=0.08,
                        wspace=0.38, hspace=0.42)
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  GROUP-AWARE PLOTTING
# ═══════════════════════════════════════════════════════════════════════════════

def plot_result_grouped(results, title='', labels_per_group=None,
                        group_colors=None, figsize=(16, 12), save_path=None):
    """4-panel multi-group figure. Same fixes as plot_result (cov correction etc.)."""
    if group_colors is None:
        group_colors = ['#FF8C00', '#1E90FF', '#2ECC40', '#FF4136', '#B10DC9']
    if labels_per_group is None:
        labels_per_group = {}
    if not results:
        raise ValueError("plot_result_grouped: results dict is empty")

    sorted_gns = sorted(results.keys())
    def _gc(gn):
        return group_colors[(gn - 1) % len(group_colors)]

    fig = plt.figure(figsize=figsize, facecolor='#f8f8f6')
    gs  = gridspec.GridSpec(2, 2, figure=fig, wspace=0.38, hspace=0.42)

    all_x36 = np.concatenate([results[g]['x36'] for g in sorted_gns])
    all_x39 = np.concatenate([results[g]['x39'] for g in sorted_gns])

    ax3 = fig.add_subplot(gs[0, 0], projection='3d')
    ax3.set_facecolor('#f0f0f0')
    rg36 = max(all_x36.max() - all_x36.min(), 1e-30)
    rg39 = max(all_x39.max() - all_x39.min(), 1e-30)
    pad = 0.15
    x36g = np.linspace(all_x36.min() - pad*rg36, all_x36.max() + pad*rg36, 20)
    x39g = np.linspace(all_x39.min() - pad*rg39, all_x39.max() + pad*rg39, 20)
    G36, G39 = np.meshgrid(x36g, x39g)
    for gn in sorted_gns:
        r = results[gn]; c = _gc(gn)
        x36, x39, x40 = r['x36'], r['x39'], r['x40']; n = r['n']
        lbl = labels_per_group.get(gn, [str(i + 1) for i in range(n)])
        ax3.scatter(x36, x39, x40, c=c, s=35, zorder=5,
                    depthshade=True, label=f'G{gn} (n={n})')
        for i in range(n):
            ax3.text(x36[i], x39[i], x40[i], lbl[i], fontsize=6, color='#333')
        G40 = r['alpha'] * G36 + r['beta'] * G39
        ax3.plot_surface(G36, G39, G40, alpha=0.18, color=c,
                         edgecolor=c, linewidth=0.1)
    ax3.set_xlabel('$^{36}$Ar', fontsize=8, labelpad=3)
    ax3.set_ylabel('$^{39}$Ar', fontsize=8, labelpad=3)
    ax3.set_zlabel('$^{40}$Ar', fontsize=8, labelpad=3)
    ax3.set_title('3D Plane', fontsize=8.5, pad=6)
    ax3.tick_params(labelsize=6)
    ax3.legend(fontsize=6, loc='upper left')

    ax_ni = fig.add_subplot(gs[0, 1])
    for gn in sorted_gns:
        r = results[gn]; c = _gc(gn)
        x36, s36 = r['x36'], r['s36']; x39, s39 = r['x39'], r['s39']
        x40, s40 = r['x40'], r['s40']
        alpha, beta = r['alpha'], r['beta']
        sa, sb = r['s_alpha'], r['s_beta']
        n = r['n']
        lbl = labels_per_group.get(gn, [str(i + 1) for i in range(n)])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            mask = x36 > 0
            rx = np.where(mask, x39 / x36, np.nan)
            ry = np.where(mask, x40 / x36, np.nan)
            erx = np.abs(rx) * np.sqrt(
                (s39 / np.where(x39 != 0, x39, 1))**2 +
                (s36 / np.where(x36 != 0, x36, 1))**2)
            ery = np.abs(ry) * np.sqrt(
                (s40 / np.where(x40 != 0, x40, 1))**2 +
                (s36 / np.where(x36 != 0, x36, 1))**2)
        ax_ni.errorbar(rx, ry, xerr=erx, yerr=ery, fmt='o', color=c,
                       ms=4, elinewidth=0.8, capsize=2, zorder=3)
        for i in range(n):
            if not np.isnan(rx[i]):
                ax_ni.annotate(lbl[i], (rx[i], ry[i]), fontsize=6, color='#444',
                               xytext=(3, 3), textcoords='offset points')
        if np.any(~np.isnan(rx)):
            xl = np.array([np.nanmin(rx) * 0.85, np.nanmax(rx) * 1.15])
            ax_ni.plot(xl, alpha + beta * xl, '-', color=c, lw=1.3,
                       label=f'G{gn}: β={beta:.4g}±{sb:.2g}')
    ax_ni.set_xlabel('$^{39}$Ar / $^{36}$Ar', fontsize=9)
    ax_ni.set_ylabel('$^{40}$Ar / $^{36}$Ar', fontsize=9)
    ax_ni.set_title('Normal Isochron', fontsize=9)
    ax_ni.legend(fontsize=6, loc='best')
    ax_ni.tick_params(labelsize=7)
    ax_ni.ticklabel_format(style='sci', axis='both', scilimits=(0, 0))
    ax_ni.grid(True, lw=0.3, alpha=0.5)

    ax_ii = fig.add_subplot(gs[1, 0])
    for gn in sorted_gns:
        r = results[gn]; c = _gc(gn)
        x36, s36 = r['x36'], r['s36']; x39, s39 = r['x39'], r['s39']
        x40, s40 = r['x40'], r['s40']
        alpha, beta = r['alpha'], r['beta']; n = r['n']
        k0_val = r.get('k0', 0.025004)
        lbl = labels_per_group.get(gn, [str(i + 1) for i in range(n)])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            mask40 = x40 > 0
            rx2 = np.where(mask40, x39 / x40, np.nan)
            ry2 = np.where(mask40, x36 / x40, np.nan)
            x39s = np.where(x39 != 0, x39, 1)
            x40s = np.where(x40 != 0, x40, 1)
            x36s = np.where(x36 != 0, x36, 1)
            cov_term = 2.0 * k0_val * s39**2 / (x39s * x40s)
            erx2 = np.abs(rx2) * np.sqrt(np.maximum(
                (s39/x39s)**2 + (s40/x40s)**2 + cov_term, 0.0))
            ery2 = np.abs(ry2) * np.sqrt((s36/x36s)**2 + (s40/x40s)**2)
        ax_ii.errorbar(rx2, ry2, xerr=erx2, yerr=ery2, fmt='o', color=c,
                       ms=4, elinewidth=0.8, capsize=2, zorder=3)
        for i in range(n):
            if not np.isnan(rx2[i]):
                ax_ii.annotate(lbl[i], (rx2[i], ry2[i]), fontsize=6, color='#444',
                               xytext=(3, 3), textcoords='offset points')
        if alpha != 0 and np.any(~np.isnan(rx2)):
            xl2 = np.array([0.0, np.nanmax(rx2) * 1.15])
            yl2 = 1. / alpha + (-beta / alpha) * xl2
            age_str = ''
            if not np.isnan(r.get('age_Ma', np.nan)):
                age_str = f", T={r['age_Ma']:.2f} Ma"
            ax_ii.plot(xl2, yl2, '-', color=c, lw=1.3,
                       label=f'G{gn}: 1/α={1/alpha:.4g}{age_str}')
    ax_ii.set_xlabel('$^{39}$Ar / $^{40}$Ar', fontsize=9)
    ax_ii.set_ylabel('$^{36}$Ar / $^{40}$Ar', fontsize=9)
    ax_ii.set_title('Inverse Isochron', fontsize=9)
    ax_ii.legend(fontsize=6, loc='best')
    ax_ii.tick_params(labelsize=7)
    ax_ii.ticklabel_format(style='sci', axis='both', scilimits=(0, 0))
    ax_ii.grid(True, lw=0.3, alpha=0.5)

    ax_tb = fig.add_subplot(gs[1, 1])
    ax_tb.axis('off')
    param_names = ['n', 'df', 'α (40Ar/36Ar)₀', 'σ_α',
                   'β (40Ar*/39Ar)', 'σ_β',
                   'MSWD', '95% CI', 'MSWD status', 'τ²', 'N-R iters']
    has_age = any(r.get('J') is not None and not np.isnan(r.get('age_Ma', np.nan))
                  for r in results.values())
    if has_age:
        param_names += ['J', 'Age (Ma)']

    rows = []
    mswd_status_per_g = {}
    for pname in param_names:
        row = [pname]
        for gn in sorted_gns:
            r = results[gn]
            mswd = r['mswd']; lo = r['mswd_lo95']; hi = r['mswd_hi95']
            if np.isnan(mswd):       st = 'n/a'
            elif mswd < lo:          st = 'under'
            elif mswd > hi:          st = 'over'
            else:                    st = 'ok'
            mswd_status_per_g[gn] = st
            if pname == 'n':
                v = str(r['n'])
            elif pname == 'df':
                v = str(r['df'])
            elif pname.startswith('α'):
                v = f"{r['alpha']:.5g}"
            elif pname == 'σ_α':
                v = f"± {r['s_alpha']:.4g}"
            elif pname.startswith('β'):
                v = f"{r['beta']:.5g}"
            elif pname == 'σ_β':
                v = f"± {r['s_beta']:.4g}"
            elif pname == 'MSWD':
                v = f"{r['mswd']:.3f}"
            elif pname == '95% CI':
                v = f"[{r['mswd_lo95']:.2f}, {r['mswd_hi95']:.2f}]"
            elif pname == 'MSWD status':
                v = {'ok':'✓ OK','under':'⚠ under','over':'✗ over','n/a':'n/a'}[st]
            elif pname == 'τ²':
                v = f"{r['tau2']:.3f}"
            elif pname == 'N-R iters':
                v = f"{r['n_iter']} ({'conv' if r['converged'] else 'NOT'})"
            elif pname == 'J':
                v = (f"{r['J']:.6g}±{r['s_J']:.2g}" if r.get('J') is not None else '-')
            elif pname == 'Age (Ma)':
                v = (f"{r['age_Ma']:.3f}±{r['s_age_Ma']:.3f}"
                     if not np.isnan(r.get('age_Ma', np.nan)) else '-')
            else:
                v = '-'
            row.append(v)
        rows.append(row)

    col_labels = ['Parameter'] + [f'G{gn}' for gn in sorted_gns]
    tab = ax_tb.table(cellText=rows, colLabels=col_labels,
                      loc='center', cellLoc='left')
    tab.auto_set_font_size(False)
    tab.set_fontsize(8)
    tab.scale(1.0, 1.4)
    status_color = {'ok':'#d0edda','under':'#fff5d6','over':'#fde8e8','n/a':'#eeeeee'}
    for (row, col), cell in tab.get_celld().items():
        cell.set_edgecolor('#cccccc')
        if row == 0:
            cell.set_facecolor('#eeede8')
            cell.set_text_props(fontweight='bold')
            if col >= 1:
                gn = sorted_gns[col - 1]
                cell.set_facecolor(_gc(gn))
                cell.set_text_props(fontweight='bold', color='white')
        elif rows[row - 1][0] == 'MSWD status' and col >= 1:
            gn = sorted_gns[col - 1]
            cell.set_facecolor(status_color[mswd_status_per_g[gn]])
        elif row % 2 == 0:
            cell.set_facecolor('#f5f5f2')
    ax_tb.set_title('Regression Summary (per group)', fontsize=9, pad=3)

    if title:
        fig.suptitle(title, fontsize=11, y=1.01, fontweight='bold')
    fig.subplots_adjust(left=0.05, right=0.97, top=0.92, bottom=0.08,
                        wspace=0.38, hspace=0.42)
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    return fig


if __name__ == '__main__':
    matplotlib.use('Agg')
    print("PlaneFit3D v3.4.3 smoke test")
    rng = np.random.default_rng(42)
    n_pts = 14
    alpha_true, beta_true = 295.5, 52.3
    x36 = rng.uniform(0.5e-13, 5.0e-13, n_pts)
    x39 = rng.uniform(1.0e-12, 8.0e-12, n_pts)
    noise = 5e-14
    x40 = alpha_true*x36 + beta_true*x39 + rng.normal(0, noise, n_pts)
    s36 = 0.01*x36 + noise*0.3
    s39 = 0.01*x39 + noise*0.3
    s40 = 0.015*x40 + noise*0.5
    res = fit_plane(x36, s36, x39, s39, x40, s40,
                    J=0.01234, s_J=1e-4, k0=0.025004, verbose=True)
    fig = plot_result(res, title='PlaneFit3D — Demo',
                      save_path='PlaneFit3D_demo.png')
    print("  Saved → PlaneFit3D_demo.png")
