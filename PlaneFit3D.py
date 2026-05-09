# -*- coding: utf-8 -*-
"""
PlaneFit3D.py  —  3D plane regression for 40Ar/39Ar dating
============================================================
Kent et al. (1990) maximum likelihood method.
Reference: Wu (2007) NTU MSc thesis "3-D Plane-fitting Program in 40Ar/39Ar Dating"

Model: 40Ar = α·36Ar + β·39Ar
  α = (40Ar/36Ar)₀  →  initial non-radiogenic ratio (intercept)
  β = 40Ar*/39Ar_K  →  radiogenic parameter for age calculation

Integration with pyADR (NTNU_DataReduction.py / Utilities.py):
  - Call fit_plane() with corrected Ar data from AutoPipeline._propagate()
  - Corrected inputs:  x36=Ar36_air, x39=Ar39_K, x40=(Ar40_r + Ar40_air)
  - k0 = _PR['PR_40_39k'] (same constant as AutoPipeline)
  - Age formula identical to Utilities.py age calculation
  - MSWD formula compatible with Utilities.py compute_mswd
"""

import numpy as np
from numpy.linalg import solve, inv
import matplotlib
# Do NOT force Agg here — let the caller set the backend
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401 (registers projection)
import matplotlib.gridspec as gridspec
import warnings

# ── Constants ─────────────────────────────────────────────────────────────────
LAM_DEFAULT = 5.543e-10      # total 40K decay constant (a⁻¹), Steiger & Jäger 1977

# MSWD 95% CI table (df: [lo95, hi95]) — Table 3.1 of Wu (2007)
# χ²(df)/df at 2.5% and 97.5% quantiles
_MSWD_CI_TABLE = {
    1: (0.001, 19.00), 2: (0.025, 9.49),  3: (0.072, 6.25),
    4: (0.121, 4.79),  5: (0.166, 4.07),  6: (0.206, 3.67),
    7: (0.241, 3.41),  8: (0.272, 3.20),  9: (0.300, 3.04),
   10: (0.325, 2.91), 15: (0.437, 2.53), 20: (0.510, 2.30),
   30: (0.598, 2.04), 40: (0.646, 1.89), 50: (0.679, 1.79),
  100: (0.742, 1.57),200: (0.797, 1.40),
}

def _mswd_ci(df):
    """Linearly interpolate MSWD 95% CI for given df."""
    keys = sorted(_MSWD_CI_TABLE)
    if df <= keys[0]:  return _MSWD_CI_TABLE[keys[0]]
    if df >= keys[-1]: return _MSWD_CI_TABLE[keys[-1]]
    for i in range(len(keys) - 1):
        k0, k1 = keys[i], keys[i+1]
        if k0 <= df <= k1:
            t = (df - k0) / (k1 - k0)
            lo = _MSWD_CI_TABLE[k0][0] + t*(_MSWD_CI_TABLE[k1][0] - _MSWD_CI_TABLE[k0][0])
            hi = _MSWD_CI_TABLE[k0][1] + t*(_MSWD_CI_TABLE[k1][1] - _MSWD_CI_TABLE[k0][1])
            return lo, hi
    return 0.5, 2.5


# ═══════════════════════════════════════════════════════════════════════════════
#  MATH CORE — follows Wu (2007) eq numbering
# ═══════════════════════════════════════════════════════════════════════════════

def build_cov(s36, s39, s40, k0):
    """
    3×3 covariance matrix A_i per data point  (eq 3-19).
    k0 = (40Ar/39Ar)_K = PR_40_39k  (creates 39Ar–40Ar correlation).
    """
    v36, v39, v40 = s36**2, s39**2, s40**2
    return np.array([
        [v36,  0.,          0.       ],
        [0.,   v39,        -k0*v39   ],
        [0.,  -k0*v39,      v40      ],
    ])


def _ols_initial(x36, x39, x40):
    """OLS estimate δ₀ = (X'X)⁻¹(X'Y)  (eq 3-17)."""
    X = np.column_stack([x36, x39])
    try:
        return solve(X.T @ X, X.T @ x40)
    except np.linalg.LinAlgError:
        return np.array([295.5, np.mean(x40) / (np.mean(x39) + 1e-40)])


# Partitioned matrix helpers (eq 3-8)
def _partition(A):
    return A[:2, :2], A[:2, 2], A[2, 2]   # A*, b, c

def _s(d, xi, A):
    """rᵀxᵢ = α·x36 + β·x39 − x40  (scalar)."""
    return d[0]*xi[0] + d[1]*xi[1] - xi[2]

def _q(d, A):
    """rᵀAᵢr = δᵀA*δ − 2δᵀb + c  (scalar)."""
    As, b, c = _partition(A)
    return d @ As @ d - 2.0*(d @ b) + c

def _v(d, A):
    """A*·δ − b  (2-vector, partial grad of q w.r.t. δ)."""
    As, b, _ = _partition(A)
    return As @ d - b


def _grad(d, data):
    """−∂Lₚ/∂δ  (eq 3-10)  — zero at MLE."""
    g = np.zeros(2)
    for xi, Ai in data:
        xs = xi[:2]
        si = _s(d, xi, Ai);  qi = _q(d, Ai);  vi = _v(d, Ai)
        g += (si/qi)*xs - (si**2/qi**2)*vi
    return -g           # return −∂Lₚ/∂δ so Newton finds its zero


def _hess(d, data):
    """−∂²Lₚ/∂δ∂δᵀ  (eq 3-11)  — positive definite at MLE."""
    H = np.zeros((2, 2))
    for xi, Ai in data:
        xs = xi[:2]
        si = _s(d, xi, Ai);  qi = _q(d, Ai);  vi = _v(d, Ai)
        As = Ai[:2, :2]
        H += (np.outer(xs, xs) / qi
              - 2.0*si/qi**2 * (np.outer(xs, vi) + np.outer(vi, xs))
              + 4.0*si**2/qi**3 * np.outer(vi, vi)
              - si**2/qi**2 * As)
    return H


def _newton_raphson(data, d0, tol=1e-10, max_iter=500):
    """
    δₙ₊₁ = δₙ − H⁻¹·g  until ‖δₙ − δₙ₊₁‖/‖δₙ₊₁‖ < tol  (eq 3-13, 3-14).
    Returns (delta, n_iter, converged).
    """
    d = np.asarray(d0, float).copy()
    for k in range(max_iter):
        g = _grad(d, data);  H = _hess(d, data)
        try:
            step = solve(H, g)
        except np.linalg.LinAlgError:
            break
        d_new = d + step
        e = np.linalg.norm(d - d_new) / (np.linalg.norm(d_new) + 1e-40)
        d = d_new
        if e < tol:
            return d, k+1, True
    return d, max_iter, False


def _compute_mswd(d, data):
    """S² = Σ(rᵀxᵢ)²/(rᵀAᵢr);  MSWD = S²/(n−2)  (eq 3-24, 3-25)."""
    S2 = sum(_s(d, xi, Ai)**2 / _q(d, Ai) for xi, Ai in data)
    df = len(data) - 2
    mswd = S2 / df if df > 0 else np.nan
    lo, hi = _mswd_ci(df)
    return S2, mswd, df, lo, hi


def _param_cov(d, data, tau2=1.0):
    """cov(δ̂) = τ²·H⁻¹  (eq 3-27)."""
    H = _hess(d, data)
    try:
        Hinv = inv(H)
    except np.linalg.LinAlgError:
        return np.nan, np.nan, None
    cov = tau2 * Hinv
    return cov[0, 0], cov[1, 1], cov


# ── Age & error propagation (eq 2-14, 3-33) ──────────────────────────────────
def age_from_beta(beta, J, lam=LAM_DEFAULT):
    """t = (1/λ)·ln(β·J + 1)  in years."""
    v = beta*J + 1.0
    return np.log(v)/lam if v > 0 else np.nan

def age_error_1sigma(beta, s_beta, J, s_J, lam=LAM_DEFAULT, s_lam=0.0):
    """σ_t via error propagation (eq 3-33, standard error, λ-uncertainty optional)."""
    v = beta*J + 1.0
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
              k0=0.025004,          # _PR['PR_40_39k'] from AutoPipeline
              tol=1e-10):
    """
    Fit 40Ar = α·36Ar + β·39Ar by maximum likelihood (Kent et al. 1990).

    pyADR integration
    -----------------
    From AutoPipeline._propagate() result dict per step:
        x36[i] = comp['Ar36_air'][0]
        s36[i] = comp['Ar36_air'][1]
        x39[i] = comp['Ar39_K'][0]
        s39[i] = comp['Ar39_K'][1]
        x40[i] = comp['Ar40_r'][0] + comp['Ar40_air'][0]   # total corrected 40Ar
        s40[i] = sqrt(comp['Ar40_r'][1]**2 + comp['Ar40_air'][1]**2)
        k0     = _PR['PR_40_39k']   (= 0.025004 by default)

    Returns
    -------
    dict  —  all results; keys listed in code.
    """
    x36,s36,x39,s39,x40,s40 = (np.asarray(a, float)
                                 for a in (x36,s36,x39,s39,x40,s40))
    n = len(x36)
    assert n >= 3, "Need ≥ 3 points for plane fit."

    data = [(np.array([x36[i], x39[i], x40[i]]),
             build_cov(s36[i], s39[i], s40[i], k0))
            for i in range(n)]

    d0          = _ols_initial(x36, x39, x40)
    delta, ni, conv = _newton_raphson(data, d0, tol=tol)
    alpha, beta = delta

    S2, mswd, df, mlo, mhi = _compute_mswd(delta, data)
    tau2 = S2/df if (not np.isnan(mswd) and mswd > mhi) else 1.0
    va, vb, cov_mat = _param_cov(delta, data, tau2)
    sa = np.sqrt(max(va, 0.)) if not np.isnan(va) else np.nan
    sb = np.sqrt(max(vb, 0.)) if not np.isnan(vb) else np.nan

    age_yr = s_age_yr = np.nan
    if J is not None and beta > 0:
        age_yr   = age_from_beta(beta, J, lam)
        s_age_yr = age_error_1sigma(beta, sb, J, s_J, lam, s_lam)

    return dict(
        alpha=alpha, s_alpha=sa,
        beta=beta,   s_beta=sb,
        mswd=mswd, df=df, mswd_lo95=mlo, mswd_hi95=mhi,
        S2=S2, tau2=tau2,
        age_yr=age_yr,   s_age_yr=s_age_yr,
        age_Ma=age_yr/1e6    if not np.isnan(age_yr)   else np.nan,
        s_age_Ma=s_age_yr/1e6 if not np.isnan(s_age_yr) else np.nan,
        n_iter=ni, converged=conv,
        delta=delta, data=data, cov_matrix=cov_mat,
        x36=x36, s36=s36, x39=x39, s39=s39, x40=x40, s40=s40,
        J=J, s_J=s_J, lam=lam, k0=k0, n=n,
    )


def extract_from_pipeline(step_results, k0=0.025004):
    """
    Helper: build (x36,s36,x39,s39,x40,s40) arrays from a list of
    _propagate() return dicts (one per heating step).

    Usage:
        comps = [_propagate(T0_sig, sT0_sig, T0_bk, sT0_bk) for ...]
        x36,s36,x39,s39,x40,s40 = extract_from_pipeline(comps)
        result = fit_plane(x36,s36,x39,s39,x40,s40, J=j, s_J=sj)
    """
    arrs = {'x36':[], 's36':[], 'x39':[], 's39':[], 'x40':[], 's40':[]}
    for c in step_results:
        arrs['x36'].append(c['Ar36_air'][0])
        arrs['s36'].append(c['Ar36_air'][1])
        arrs['x39'].append(c['Ar39_K'][0])
        arrs['s39'].append(c['Ar39_K'][1])
        # total corrected 40Ar = radiogenic + trapped-air components
        arrs['x40'].append(c['Ar40_r'][0] + c['Ar40_air'][0])
        arrs['s40'].append(np.hypot(c['Ar40_r'][1], c['Ar40_air'][1]))
    return tuple(np.array(arrs[k]) for k in ('x36','s36','x39','s39','x40','s40'))


# ═══════════════════════════════════════════════════════════════════════════════
#  PLOTTING
# ═══════════════════════════════════════════════════════════════════════════════

def plot_result(result, title='', labels=None, figsize=(16, 12), save_path=None):
    """
    4-panel figure:
      [A] 3D scatter + fitted plane
      [B] Normal isochron  (39/36 vs 40/36)
      [C] Inverse isochron (39/40 vs 36/40)
      [D] Results table
    Returns matplotlib Figure.
    """
    r = result
    x36,s36,x39,s39,x40,s40 = r['x36'],r['s36'],r['x39'],r['s39'],r['x40'],r['s40']
    alpha,beta,sa,sb = r['alpha'],r['beta'],r['s_alpha'],r['s_beta']
    n = r['n']
    lbl = labels if labels else [str(i+1) for i in range(n)]

    fig = plt.figure(figsize=figsize, facecolor='#f8f8f6')
    gs  = gridspec.GridSpec(2, 2, figure=fig, wspace=0.38, hspace=0.42)

    # ── A: 3D ────────────────────────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[0, 0], projection='3d')
    ax3.set_facecolor('#f0f0f0')

    ax3.scatter(x36, x39, x40, c='#1a5fb4', s=35, zorder=5, depthshade=True)
    for i in range(n):
        ax3.text(x36[i], x39[i], x40[i], lbl[i], fontsize=6, color='#333')

    # Fitted plane surface
    mg = 0.15
    x36g = np.linspace(x36.min()*(1-mg), x36.max()*(1+mg), 20)
    x39g = np.linspace(x39.min()*(1-mg), x39.max()*(1+mg), 20)
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

    # ── B: Normal isochron 39/36 vs 40/36 ────────────────────────────────────
    ax_ni = fig.add_subplot(gs[0, 1])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        mask = x36 > 0
        rx = np.where(mask, x39/x36, np.nan)
        ry = np.where(mask, x40/x36, np.nan)
        erx = np.abs(rx) * np.sqrt((s39/np.where(x39!=0,x39,1))**2 + (s36/np.where(x36!=0,x36,1))**2)
        ery = np.abs(ry) * np.sqrt((s40/np.where(x40!=0,x40,1))**2 + (s36/np.where(x36!=0,x36,1))**2)

    ax_ni.errorbar(rx, ry, xerr=erx, yerr=ery, fmt='o', color='#1a5fb4',
                   ms=4, elinewidth=0.8, capsize=2, zorder=3)
    for i in range(n):
        if not np.isnan(rx[i]):
            ax_ni.annotate(lbl[i], (rx[i], ry[i]), fontsize=6, color='#444', xytext=(3,3),
                           textcoords='offset points')

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

    # ── C: Inverse isochron 39/40 vs 36/40 ───────────────────────────────────
    ax_ii = fig.add_subplot(gs[1, 0])
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        mask40 = x40 > 0
        rx2 = np.where(mask40, x39/x40, np.nan)
        ry2 = np.where(mask40, x36/x40, np.nan)
        erx2 = np.abs(rx2)*np.sqrt((s39/np.where(x39!=0,x39,1))**2 + (s40/np.where(x40!=0,x40,1))**2)
        ery2 = np.abs(ry2)*np.sqrt((s36/np.where(x36!=0,x36,1))**2 + (s40/np.where(x40!=0,x40,1))**2)

    ax_ii.errorbar(rx2, ry2, xerr=erx2, yerr=ery2, fmt='o', color='#c01c28',
                   ms=4, elinewidth=0.8, capsize=2, zorder=3)
    for i in range(n):
        if not np.isnan(rx2[i]):
            ax_ii.annotate(lbl[i], (rx2[i], ry2[i]), fontsize=6, color='#444', xytext=(3,3),
                           textcoords='offset points')

    # Line: 1 = α(36/40) + β(39/40)  → 36/40 = 1/α − (β/α)(39/40)
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

    # ── D: Results table ──────────────────────────────────────────────────────
    ax_tb = fig.add_subplot(gs[1, 1])
    ax_tb.axis('off')

    mswd_ok = r['mswd_lo95'] <= r['mswd'] <= r['mswd_hi95']
    rows = [
        ['n',               str(r['n'])],
        ['df',              str(r['df'])],
        ['α (40Ar/36Ar)₀',  f"{alpha:.5g}"],
        ['σ_α',             f"± {sa:.4g}"],
        ['β (40Ar*/39Ar)',   f"{beta:.5g}"],
        ['σ_β',             f"± {sb:.4g}"],
        ['MSWD',            f"{r['mswd']:.3f}"],
        ['95% CI',          f"[{r['mswd_lo95']:.2f}, {r['mswd_hi95']:.2f}]"],
        ['MSWD status',     '✓ OK' if mswd_ok else '✗ overdispersed'],
        ['τ²',              f"{r['tau2']:.3f}"],
        ['N-R iters',       f"{r['n_iter']} ({'converged' if r['converged'] else 'NOT converged'})"],
    ]
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
        elif 'status' in rows[row-1][0].lower():
            cell.set_facecolor('#d0edda' if mswd_ok else '#fde8e8')
        elif row % 2 == 0:
            cell.set_facecolor('#f5f5f2')
    ax_tb.set_title('Regression Summary', fontsize=9, pad=3)

    if title:
        fig.suptitle(title, fontsize=11, y=1.01, fontweight='bold')

    fig.subplots_adjust(left=0.05, right=0.97, top=0.92, bottom=0.08, wspace=0.38, hspace=0.42)
    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
    return fig


# ═══════════════════════════════════════════════════════════════════════════════
#  GROUP-AWARE PLOTTING
# ═══════════════════════════════════════════════════════════════════════════════

def plot_result_grouped(results, title='', labels_per_group=None,
                        group_colors=None, figsize=(16, 12), save_path=None):
    """
    4-panel figure for multiple group fits sharing one set of axes.

    Parameters
    ----------
    results : dict {group_num: result_dict}
        Each result_dict is a fit_plane() return value.
        Groups with fewer than 3 points should be excluded by the caller
        (fit_plane requires n >= 3).
    labels_per_group : dict {group_num: [point_labels]} or None
    group_colors : list of color strings; group `gn` uses group_colors[gn-1].
        Falls back to a default palette if None.
    """
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

    # 3D
    ax3 = fig.add_subplot(gs[0, 0], projection='3d')
    ax3.set_facecolor('#f0f0f0')
    mg = 0.15
    x36g = np.linspace(all_x36.min() * (1 - mg), all_x36.max() * (1 + mg), 20)
    x39g = np.linspace(all_x39.min() * (1 - mg), all_x39.max() * (1 + mg), 20)
    G36, G39 = np.meshgrid(x36g, x39g)

    for gn in sorted_gns:
        r = results[gn]
        c = _gc(gn)
        x36, x39, x40 = r['x36'], r['x39'], r['x40']
        n = r['n']
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
    ax3.set_title('3D Plane: $^{40}$Ar $= \\alpha\\cdot^{36}$Ar $+ \\beta\\cdot^{39}$Ar',
                  fontsize=8.5, pad=6)
    ax3.tick_params(labelsize=6)
    ax3.legend(fontsize=6, loc='upper left')

    # Normal isochron
    ax_ni = fig.add_subplot(gs[0, 1])
    for gn in sorted_gns:
        r = results[gn]
        c = _gc(gn)
        x36, s36 = r['x36'], r['s36']
        x39, s39 = r['x39'], r['s39']
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
            xmin = np.nanmin(rx) * 0.85
            xmax = np.nanmax(rx) * 1.15
            xl = np.array([xmin, xmax])
            ax_ni.plot(xl, alpha + beta * xl, '-', color=c, lw=1.3,
                       label=f'G{gn}: B={beta:.4g}+-{sb:.2g}, A={alpha:.4g}+-{sa:.2g}')

    ax_ni.set_xlabel('$^{39}$Ar / $^{36}$Ar', fontsize=9)
    ax_ni.set_ylabel('$^{40}$Ar / $^{36}$Ar', fontsize=9)
    ax_ni.set_title('Normal Isochron', fontsize=9)
    ax_ni.legend(fontsize=6, loc='best')
    ax_ni.tick_params(labelsize=7)
    ax_ni.ticklabel_format(style='sci', axis='both', scilimits=(0, 0))
    ax_ni.grid(True, lw=0.3, alpha=0.5)

    # Inverse isochron
    ax_ii = fig.add_subplot(gs[1, 0])
    for gn in sorted_gns:
        r = results[gn]
        c = _gc(gn)
        x36, s36 = r['x36'], r['s36']
        x39, s39 = r['x39'], r['s39']
        x40, s40 = r['x40'], r['s40']
        alpha, beta = r['alpha'], r['beta']
        n = r['n']
        lbl = labels_per_group.get(gn, [str(i + 1) for i in range(n)])
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            mask40 = x40 > 0
            rx2 = np.where(mask40, x39 / x40, np.nan)
            ry2 = np.where(mask40, x36 / x40, np.nan)
            erx2 = np.abs(rx2) * np.sqrt(
                (s39 / np.where(x39 != 0, x39, 1))**2 +
                (s40 / np.where(x40 != 0, x40, 1))**2)
            ery2 = np.abs(ry2) * np.sqrt(
                (s36 / np.where(x36 != 0, x36, 1))**2 +
                (s40 / np.where(x40 != 0, x40, 1))**2)
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
                       label=f'G{gn}: 1/A={1/alpha:.4g}{age_str}')

    ax_ii.set_xlabel('$^{39}$Ar / $^{40}$Ar', fontsize=9)
    ax_ii.set_ylabel('$^{36}$Ar / $^{40}$Ar', fontsize=9)
    ax_ii.set_title('Inverse Isochron', fontsize=9)
    ax_ii.legend(fontsize=6, loc='best')
    ax_ii.tick_params(labelsize=7)
    ax_ii.ticklabel_format(style='sci', axis='both', scilimits=(0, 0))
    ax_ii.grid(True, lw=0.3, alpha=0.5)

    # Summary table
    ax_tb = fig.add_subplot(gs[1, 1])
    ax_tb.axis('off')
    param_names = ['n', 'df', 'alpha (40Ar/36Ar)0', 's_alpha',
                   'beta (40Ar*/39Ar)', 's_beta',
                   'MSWD', '95% CI', 'MSWD status', 'tau^2', 'N-R iters']
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
            ok = r['mswd_lo95'] <= r['mswd'] <= r['mswd_hi95']
            mswd_status_per_g[gn] = ok
            if pname == 'n':
                v = str(r['n'])
            elif pname == 'df':
                v = str(r['df'])
            elif pname.startswith('alpha'):
                v = f"{r['alpha']:.5g}"
            elif pname == 's_alpha':
                v = f"+- {r['s_alpha']:.4g}"
            elif pname.startswith('beta'):
                v = f"{r['beta']:.5g}"
            elif pname == 's_beta':
                v = f"+- {r['s_beta']:.4g}"
            elif pname == 'MSWD':
                v = f"{r['mswd']:.3f}"
            elif pname == '95% CI':
                v = f"[{r['mswd_lo95']:.2f}, {r['mswd_hi95']:.2f}]"
            elif pname == 'MSWD status':
                v = 'OK' if ok else 'overdisp.'
            elif pname == 'tau^2':
                v = f"{r['tau2']:.3f}"
            elif pname == 'N-R iters':
                v = f"{r['n_iter']} ({'conv' if r['converged'] else 'NOT'})"
            elif pname == 'J':
                v = (f"{r['J']:.6g}+-{r['s_J']:.2g}"
                     if r.get('J') is not None else '-')
            elif pname == 'Age (Ma)':
                v = (f"{r['age_Ma']:.3f}+-{r['s_age_Ma']:.3f}"
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
            cell.set_facecolor('#d0edda' if mswd_status_per_g[gn] else '#fde8e8')
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

# ═══════════════════════════════════════════════════════════════════════════════
#  STANDALONE DEMO / SMOKE TEST
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == '__main__':
    matplotlib.use('Agg')  # standalone: non-interactive backend
    print("PlaneFit3D smoke test")
    rng = np.random.default_rng(42)
    n_pts = 14

    alpha_true, beta_true = 295.5, 52.3   # realistic values

    x36 = rng.uniform(0.5e-13, 5.0e-13, n_pts)
    x39 = rng.uniform(1.0e-12, 8.0e-12, n_pts)
    noise = 5e-14
    x40 = alpha_true*x36 + beta_true*x39 + rng.normal(0, noise, n_pts)
    s36 = 0.01*x36 + noise*0.3
    s39 = 0.01*x39 + noise*0.3
    s40 = 0.015*x40 + noise*0.5

    res = fit_plane(x36, s36, x39, s39, x40, s40,
                    J=0.01234, s_J=1e-4, k0=0.025004)

    print(f"  α = {res['alpha']:.5g} ± {res['s_alpha']:.4g}  (true: {alpha_true})")
    print(f"  β = {res['beta']:.5g} ± {res['s_beta']:.4g}  (true: {beta_true})")
    print(f"  MSWD = {res['mswd']:.3f}  "
          f"(95%CI: {res['mswd_lo95']:.2f}–{res['mswd_hi95']:.2f})  "
          f"{'OK' if res['mswd_lo95']<=res['mswd']<=res['mswd_hi95'] else 'overdispersed'}")
    print(f"  Age = {res['age_Ma']:.2f} ± {res['s_age_Ma']:.2f} Ma")
    print(f"  N-R: {res['n_iter']} iterations, converged={res['converged']}")

    fig = plot_result(res, title='PlaneFit3D — Demo',
                      save_path='/sessions/ecstatic-friendly-hawking/mnt/outputs/PlaneFit3D_demo.png')
    print("  Saved → PlaneFit3D_demo.png")
