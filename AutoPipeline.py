# -*- coding: utf-8 -*-
"""
AutoPipeline.py  —  pyADR Auto Pipeline (full PyQt5 UI)
=========================================================
Native PyQt5 interface matching the HTML design:
  - Top navigation: 1.Calculate T0 → 2.Mass Ratio → 3.Age Calc+Datum
  - Left sidebar: Return / Save T0 / Linear/Average / Auto Blank / Auto Signal / Manual
  - 5 mV-vs-time canvases with 10-cycle toggle buttons
  - T0 summary table
  - Mass Ratio table
  - Age Calc + Datum table + 4 diagram panels

Integration (4 changes in NTNU_DataReduction.py):
  1. import AutoPipeline
  2. __init__():
       self.AutoPipelinePage = AutoPipeline.AutoPipelineWindow()
       self.widget.addWidget(self.AutoPipelinePage)   # p20
       self.AutoPipelinePage.returnBtn.clicked.connect(self.toMain)
  3. Connections:
       self.HomePage.AP.clicked.connect(self.toAP)
  4. New method:
       def toAP(self):
           self.AutoPipelinePage.set_context(
               self.parameters, self.parameters_name,
               int(self.parameters[self.parameters_name.index('numCycle')])
           )
           self.widget.setCurrentIndex(20)
"""

import os, sys, csv, shutil, math
import warnings
warnings.filterwarnings('ignore', category=UserWarning, module='matplotlib')
import numpy as np
from PyQt5 import QtWidgets, QtCore, QtGui
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
import Utilities

# ── Decay constants (Renne et al. 2010, 2011) ───────────────────────────────
ARGON_37_HALFLIFE_DAYS = 35.011
ARGON_39_HALFLIFE_YEARS = 269.0
LAMBDA_37 = math.log(2) / ARGON_37_HALFLIFE_DAYS                # 1/day
LAMBDA_39 = math.log(2) / (ARGON_39_HALFLIFE_YEARS * 365.25)    # 1/day

# ⁴⁰K total decay constant for age calculation (1/yr).
# pyADR default 5.49e-10 matches parameters.csv default and what calcAge uses.
# Updated at runtime by AutoPipelineWindow.set_context() from
# parameters['λ for age calculation'], so isochron age in AgeCalcPage stays
# consistent with the main calcAge path.
LAMBDA_K = 5.49e-10

def decay_correct(t0_net, sig, delta_t_days, isotope='37'):
    """Correct an isotope's net T0 for radioactive decay between irradiation
    midpoint and analysis time. 37Ar: t½ = 35.011 d; 39Ar: t½ = 269 yr.
    Returns (t0_corrected, sig_corrected). sig scales by same factor."""
    if delta_t_days <= 0:
        return t0_net, sig
    lam = LAMBDA_37 if str(isotope) == '37' else LAMBDA_39
    factor = math.exp(lam * delta_t_days)
    return t0_net * factor, abs(sig) * factor

# ── σ method toggle ─────────────────────────────────────────────────────────
# 'standard' : SE of y-intercept (statistically correct, Li et al. 2019 Eq.1)
# 'calc_t0'  : std(|residuals|)/sqrt(n)  (matches Calculate T0; underestimates σ)
# v3.8.18: default changed 'standard' → 'calc_t0' per user request — AutoPipeline
# now matches the standalone CalcT0Page (NTNU_DataReduction.py) σ output by
# default. User can still flip to 'standard' via the sidebar σ method dropdown.
SIGMA_METHOD = 'calc_t0'

# ── Δt (days, irradiation midpoint → analysis) ──────────────────────────────
# Set via UI; 0 means no decay correction.
DELTA_T_DAYS = 0.0

def _ratio_sigma(num, snum, den, sden, rho=0.0):
    """σ of ratio R = num/den via quadrature.
       (σR/R)² = (σnum/num)² + (σden/den)² - 2·rho·(σnum/num)(σden/den)"""
    if abs(num) < 1e-30 or abs(den) < 1e-30:
        return 0.0
    r = num/den
    return abs(r) * math.sqrt((snum/num)**2 + (sden/den)**2
                              - 2*rho*(snum/num)*(sden/den))


def york_regression(x, sx, y, sy, rho_xy=None, max_iter=50, tol=1e-12):
    """v3.8.5: delegate to Utilities.york_regression (single source of truth).
    Kept here as a thin wrapper so existing callers in AutoPipeline work
    unchanged."""
    return Utilities.york_regression(x, sx, y, sy, rho_xy=rho_xy,
                                     max_iter=max_iter, tol=tol)


# Original local implementation preserved below for reference but no longer
# called — kept temporarily in case Utilities import fails.  Will be removed
# in a follow-up cleanup once Utilities.york_regression is verified.
def _york_regression_legacy(x, sx, y, sy, rho_xy=None, max_iter=50, tol=1e-12):
    """LEGACY: pre-v3.8.5 local copy.  Use Utilities.york_regression instead."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    sx = np.asarray(sx, float); sy = np.asarray(sy, float)
    n = len(x)
    if n < 2: return 0.0, 0.0, 0.0, 0.0, 0.0, 0.0
    if rho_xy is None: rho_xy = np.zeros(n)
    else: rho_xy = np.asarray(rho_xy, float)
    # weights
    wx = 1.0/(sx**2 + 1e-300)
    wy = 1.0/(sy**2 + 1e-300)
    # initial slope from OLS
    b = np.polyfit(x, y, 1)[0]
    for _ in range(max_iter):
        alpha = np.sqrt(wx * wy)
        W = wx * wy / (wx + b*b * wy - 2*b*rho_xy*alpha + 1e-300)
        X_bar = np.sum(W*x) / np.sum(W)
        Y_bar = np.sum(W*y) / np.sum(W)
        U = x - X_bar
        V = y - Y_bar
        beta = W * (U/wy + b*V/wx - (b*U + V)*rho_xy/alpha)
        num = np.sum(W * beta * V)
        den = np.sum(W * beta * U)
        if abs(den) < 1e-300:
            break
        b_new = num/den
        if abs(b_new - b) < tol*max(1.0, abs(b)):
            b = b_new; break
        b = b_new
    a = Y_bar - b * X_bar
    # σ on slope and intercept
    x_adj = X_bar + beta
    x_adj_bar = np.sum(W*x_adj)/np.sum(W)
    u = x_adj - x_adj_bar
    sb2 = 1.0 / np.sum(W*u*u)
    sa2 = 1.0/np.sum(W) + x_adj_bar*x_adj_bar*sb2
    # v3.8.5 (A3): cov(intercept, slope).  Typically negative for inverse
    # isochrons (when slope goes up, intercept goes down).  Required by σ_F
    # propagation in _update_isochron_stats inverse path.
    cov_ab = -x_adj_bar * sb2
    # MSWD
    if n > 2:
        chi2 = np.sum(W * (y - b*x - a)**2)
        mswd = chi2 / (n - 2)
    else:
        mswd = 0.0
    return (float(b), float(a),
            float(np.sqrt(max(sb2, 0))), float(np.sqrt(max(sa2, 0))),
            float(mswd), float(cov_ab))


def _sigma_from_fit(residuals, n, popt, pcov, t, method=None):
    """Return σ_T0 according to global SIGMA_METHOD (or override).
    'standard': pcov[-1,-1] (SE of intercept, with closed-form fallback).
    'calc_t0' : np.std(np.abs(residuals)) / sqrt(n) (Calculate T0 convention)."""
    m = method or SIGMA_METHOD
    if m == 'calc_t0':
        return float(np.std(np.abs(residuals)) / np.sqrt(n)) if n > 0 else 1e-9
    # standard SE of intercept
    if pcov is not None and pcov.shape[0] > 0 and np.isfinite(pcov[-1, -1]):
        return float(np.sqrt(np.abs(pcov[-1, -1])))
    # closed-form fallback (Li et al. 2019 Eq. 1)
    if n < 3:
        return 1e-9
    x_bar = float(np.mean(t))
    Sxx = float(np.sum((t - x_bar) ** 2))
    s = float(np.std(residuals, ddof=max(1, n - len(popt))))
    return s * np.sqrt(1.0 / n + x_bar ** 2 / Sxx) if Sxx > 0 else s

# ── Irradiation parameters (hardcoded, same for entire irradiation) ──────────
_PR = {
    'PR_39_37ca' : 0.000377631,
    'PR_39_37ca_s': 0.0000609,
    'PR_36_37ca' : 0.0000346,
    'PR_36_37ca_s': 4.97e-7,
    'PR_40_39k'  : 0.025004,
    'PR_40_39k_s': 0.002866,
    'PR_38_39k'  : 0.0126288,
    'PR_38_39k_s': 0.000010529,
    'R_40_36a'   : 298.56,
    'R_40_36a_s' : 0.31,
    'R_38_36a'   : 0.1885,
    'R_38_36a_s' : 0.000347,
    'PR_36_38cl' : 0.0,
}

def _propagate(T0, sT0, bT0, bsT0):
    """
    Given T0[5] and σ_T0[5] for one signal step, and blank T0[5]/σ[5],
    compute component values and their 1-sigma uncertainties.
    Returns a dict of (value, sigma, ok) triples.
    """
    p = _PR
    # net T0 = signal - blank
    t  = T0  - bT0
    st = np.sqrt(sT0**2 + bsT0**2)
    # indices: 0=36, 1=37, 2=38, 3=39, 4=40

    # ── 36 chain ─────────────────────────────────────────────
    Ar36_ca  = t[1] * p['PR_36_37ca']
    sAr36_ca = Ar36_ca * np.sqrt((st[1]/t[1])**2 + (p['PR_36_37ca_s']/p['PR_36_37ca'])**2) if (t[1]!=0 and p['PR_36_37ca']!=0) else 0
    Ar36_air = t[0] - Ar36_ca
    sAr36_air= np.sqrt(st[0]**2 + sAr36_ca**2)

    # ── 39 chain ─────────────────────────────────────────────
    Ar39_ca  = t[1] * p['PR_39_37ca']
    sAr39_ca = Ar39_ca * np.sqrt((st[1]/t[1])**2 + (p['PR_39_37ca_s']/p['PR_39_37ca'])**2) if (t[1]!=0 and p['PR_39_37ca']!=0) else 0
    Ar39_K   = t[3] - Ar39_ca
    sAr39_K  = np.sqrt(st[3]**2 + sAr39_ca**2)

    # ── 40 chain ─────────────────────────────────────────────
    Ar40_air = Ar36_air * p['R_40_36a']
    sAr40_air= Ar40_air * np.sqrt((sAr36_air/Ar36_air)**2 + (p['R_40_36a_s']/p['R_40_36a'])**2) if Ar36_air!=0 else abs(sAr36_air*p['R_40_36a'])
    Ar40_K   = Ar39_K * p['PR_40_39k']
    sAr40_K  = Ar40_K * np.sqrt((sAr39_K/Ar39_K)**2 + (p['PR_40_39k_s']/p['PR_40_39k'])**2) if Ar39_K!=0 else abs(sAr39_K*p['PR_40_39k'])
    Ar40_r   = t[4] - Ar40_air - Ar40_K
    sAr40_r  = np.sqrt(st[4]**2 + sAr40_air**2 + sAr40_K**2)
    Ar40r_pct= Ar40_r / t[4] * 100 if t[4] != 0 else 0

    # ── 38 internal consistency check ────────────────────────
    Ar38_air_pred = Ar36_air * p['R_38_36a']
    Ar38_K_pred   = Ar39_K   * p['PR_38_39k']
    Ar38_cl       = t[2] - Ar38_air_pred - Ar38_K_pred
    # sigma of 38Ar(cl): all terms quadrature
    sAr38_cl = np.sqrt(
        st[2]**2 +
        (sAr36_air * p['R_38_36a'])**2 +
        (sAr39_K   * p['PR_38_39k'])**2
    )
    chi2_38 = (Ar38_cl / sAr38_cl)**2 if sAr38_cl > 0 else 0
    sig38_n  = Ar38_cl / sAr38_cl if sAr38_cl > 0 else 0  # n-sigma significance

    return {
        'Ar36_air' : (Ar36_air,  sAr36_air,  Ar36_air > 0),
        'Ar36_ca'  : (Ar36_ca,   sAr36_ca,   True),
        'Ar39_K'   : (Ar39_K,    sAr39_K,    Ar39_K > 0),
        'Ar39_ca'  : (Ar39_ca,   sAr39_ca,   True),
        'Ar40_air' : (Ar40_air,  sAr40_air,  Ar36_air > 0),
        'Ar40_K'   : (Ar40_K,    sAr40_K,    Ar39_K > 0),
        'Ar40_r'   : (Ar40_r,    sAr40_r,    Ar40_r > 0),
        'Ar40r_pct': (Ar40r_pct, 0,          0 < Ar40r_pct < 100),
        'Ar38_cl'  : (Ar38_cl,   sAr38_cl,   True),
        'chi2_38'  : (chi2_38,   0,          chi2_38 < 4),   # <4 = within 2σ
        'sig38_n'  : (sig38_n,   0,          abs(sig38_n) < 2),
    }

# ── colour palette (matches HTML) ──────────────────────────────────────────
AR_COLS  = ['#1a5fb4','#1c7a3a','#8a5a00','#b41a1a','#533ab7']
AR_NAMES = ['36','37','38','39','40']

BG   = '#f5f4f0'
PNL  = '#f0f0f0'   # matches Fusion default
BRD  = '#cccccc'
BRD2 = '#bbbbbb'
TXT  = '#222222'
TXT2 = '#444444'
TXT3 = '#888888'
BLUE_BG = '#d6e8f7'
GRN_BG  = '#d0edda'
AMB_BG  = '#fdf0d0'
RED_BG  = '#fde8e8'

def _sheet():
    return f"""
QWidget{{background:{BG};color:{TXT};font-family:Georgia,serif;font-size:11px;}}
QLabel{{background:transparent;}}
QPushButton{{background:{PNL};color:{TXT};border:1px solid {BRD};border-radius:2px;padding:5px 6px;}}
QPushButton:hover{{background:{BG};}}
QTableWidget{{gridline-color:{BRD};font-family:'Courier New',monospace;font-size:10px;}}
QHeaderView::section{{background:#eeede8;border:1px solid {BRD2};padding:3px;font-family:Georgia,serif;font-size:10px;}}
QTabBar::tab{{padding:4px 12px;border:1px solid {BRD};border-bottom:none;background:#eeede8;}}
QTabBar::tab:selected{{background:{PNL};color:#1a5fb4;}}
QTabWidget::pane{{border:1px solid {BRD};}}
"""

def _btn_style(bg, col, brd):
    return (f'QPushButton{{background:{bg};color:{col};border:1px solid {brd};'
            f'border-radius:2px;padding:5px 4px;font-size:10px;font-family:Georgia,serif;}}'
            f'QPushButton:hover{{background:{BG};}}')

# ── helpers ─────────────────────────────────────────────────────────────────
def _sf(v, d=0.0):
    try: return float(v)
    except: return d

def _fe(v):
    try: return '{:.6e}'.format(float(v))
    except: return '0'

def _norm_date(raw):
    try:
        p = raw.split('/')
        if len(p)==3: return '{}/{:02d}/{:02d}'.format(p[0],int(p[1]),int(p[2]))
    except: pass
    return raw

# ── dat parser ───────────────────────────────────────────────────────────────
def _extract_dat_date(filepath):
    """Extract analysis date from .dat header.
    Looks for 'Project #' line which contains YYYY/M/D, falls back to
    line[1] (MM/DD HH:MM) combined with current year. Returns datetime.date
    or None."""
    from datetime import date as _date
    try:
        with open(filepath, 'rb') as f:
            lines = f.read().decode('latin-1').splitlines()
        # Look for "Project #" line (typically has YYYY/M/D)
        for ln in lines[:30]:
            if 'Project' in ln:
                parts = ln.split()
                for tok in parts:
                    if '/' in tok and tok.count('/') == 2:
                        y, m, d = tok.split('/')
                        try:
                            return _date(int(y), int(m), int(d))
                        except (ValueError, TypeError):
                            continue
        # Fallback: line[1] is "MM/DD HH:MM"
        if len(lines) > 1:
            t = lines[1].strip().split()[0]
            if '/' in t:
                m, d = t.split('/')
                # default year — try other places in file or use file mtime
                try:
                    import os as _os
                    mt = _os.path.getmtime(filepath)
                    yr = _date.fromtimestamp(mt).year
                    return _date(yr, int(m), int(d))
                except Exception:
                    pass
    except Exception:
        pass
    return None


def compute_delta_t_days(ogd_str, spd_date):
    """Δt = SPD − OGD, both as datetime.date.
    ogd_str: YYYYMMDD or YYYY-MM-DD or YYYY/M/D format from params['OG Date'].
    Returns int days, or 0 if cannot parse."""
    from datetime import date as _date
    import re as _re
    if spd_date is None or not ogd_str:
        return 0
    try:
        s = _re.sub(r'[-/]', '', str(ogd_str).strip())
        if len(s) < 8: return 0
        ogd = _date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
        d = (spd_date - ogd).days
        return max(0, int(d))
    except Exception:
        return 0


def parse_dat(filepath, numCycle=10):
    with open(filepath,'rb') as f: raw=f.read()
    lines = raw.decode('latin-1').splitlines()
    stl = 0
    for i in reversed(range(len(lines))):
        if len(lines[i].split())==4: stl=i; break
    stl -= (6*numCycle-2)
    info = ['','','','','']
    try:
        if lines[2].strip()=='':
            info[0]=lines[17].split()[2]+' '+lines[4].split()[3]
            info[1]=lines[18].split()[2]; info[2]=lines[0].split()[1]
            info[3]=lines[21].split()[2]; info[4]=lines[23].split()[2]
        else:
            info[0]=lines[15].split()[2]; info[1]=lines[16].split()[2]
            info[2]=lines[0].split()[1]; info[3]=lines[19].split()[2]
            info[4]=lines[21].split()[2]
    except: pass
    v_t = np.zeros((5,numCycle,2))
    for i in range(numCycle):
        for j in range(5):
            parts=lines[stl+6*i+j].split()
            v_t[j,i,0]=float(parts[2]); v_t[j,i,1]=float(parts[3])
    return v_t, info

# ── best-mask (min exclusions) ───────────────────────────────────────────────
def _combos(n, k, limit=300):
    if k>=n: return [list(range(n))]
    result=[]
    def go(s,c):
        if len(c)==k: result.append(list(c)); return
        for i in range(s,n):
            if len(result)>=limit: return
            c.append(i); go(i+1,c); c.pop()
    go(0,[]); return result

def best_mask(vt_i, numCycle, blank_t0=None, fit_type=0):
    f=Utilities.fit_func_list[fit_type]
    bm=np.ones(numCycle); bs=np.inf
    for ne in range(7):
        nu=numCycle-ne
        if nu<4: break
        imp=False
        for combo in _combos(numCycle,nu):
            m=np.zeros(numCycle)
            for idx in combo: m[idx]=1
            sel=np.where(m==1)[0]; t,v=vt_i[sel,1],vt_i[sel,0]
            try:
                popt,_=curve_fit(f,t,v); t0=f(0,*popt)
                sig=np.std(np.abs(v-f(t,*popt)))/np.sqrt(nu)
            except: continue
            if blank_t0 is not None and t0<=blank_t0: continue
            if sig<bs*0.95: bs=sig; bm=m.copy(); imp=True
        if ne>0 and not imp: break
    return bm

def calc_t0(vt, mask, numCycle, fit_type=0):
    """Batch T0 fit for all 5 isotopes. σ uses pcov[-1,-1] (see _fit_one)."""
    f=Utilities.fit_func_list[fit_type]
    T0=np.zeros(5); SIG=np.zeros(5); R=np.zeros(5)
    for i in range(5):
        sel=np.where(mask[i]==1)[0]; n=len(sel)
        if n<2: continue
        t,v=vt[i,sel,1],vt[i,sel,0]
        try:
            popt,pcov=curve_fit(f,t,v)
            T0[i]=f(0,*popt)
            # σ_T0 = SE of intercept from covariance (not std/√n; see _fit_one)
            if pcov is not None and pcov.shape[0] > 0 and np.isfinite(pcov[-1,-1]):
                SIG[i] = float(np.sqrt(np.abs(pcov[-1,-1])))
            else:
                SIG[i] = float(np.std(np.abs(v-f(t,*popt)))/np.sqrt(n))
            R[i]=r2_score(v,f(t,*popt))
        except: pass
    return T0,SIG,R

def write_t0_csv(filepath, info, T0, SIG, R):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    date_str=_norm_date(info[3])
    with open(filepath,'w') as f:
        f.write("Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2\n")
        for i in range(5):
            f.write(f"{info[0]},{info[1]},{info[2]},{date_str},{info[4]},Ar{i+36},{T0[i]},{SIG[i]},{R[i]}\n")


# ═══════════════════════════════════════════════════════════
#  MvCanvas  — one isotope, matplotlib-based, independent refresh
#    Row 1: mV vs time  (matplotlib → QPixmap)
#    Row 2: cycle buttons (4+4+2)
#    Row 3: T0 vs 2σ scatter (matplotlib → QPixmap)
# ═══════════════════════════════════════════════════════════
import io as _io
import matplotlib as _mpl
_mpl.use('Agg')
import matplotlib.pyplot as _plt
import matplotlib.ticker as _ticker
# Interactive scatter canvas uses Qt5Agg backend in a separate figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as _FigCanvas
import matplotlib.figure as _mfig

def _fit_one(f, vt_i, mask):
    """Returns (t0, sig, r2, popt) or (0,1e-9,0,None).

    σ_T0 BUG FIX (2026-05):
        Earlier this returned `sig = std(residuals)/√n`, which is the standard
        error of the MEAN, not of the y-INTERCEPT. For step-heating data with
        cycle times t ∈ [320..600] s, the intercept extrapolated to t=0 has a
        much larger uncertainty (typically ~10× of std/√n) because of the
        lever-arm from t̄ to 0.

        Fixed: σ_T0 is now `sqrt(pcov[-1,-1])` — the SE of the y-intercept from
        the regression covariance matrix (matches `_fit_with_errors`'s
        `sig_model`, Li et al. 2019 Eq. 1). For linear y=a·t+b and constant
        y=b fit funcs in `fit_func_list`, the intercept is the LAST parameter
        of popt; hence pcov[-1,-1] is its variance.
    """
    sel = np.where(mask == 1)[0]
    n = len(sel)
    if n < 2:
        return 0.0, 1e-9, 0.0, None
    t, v = vt_i[sel, 1], vt_i[sel, 0]
    try:
        popt, pcov = curve_fit(f, t, v)
        t0  = f(0, *popt)
        residuals = v - f(t, *popt)
        # σ via global SIGMA_METHOD toggle
        sig = _sigma_from_fit(residuals, n, popt, pcov, t)
        r2 = r2_score(v, f(t, *popt))
        return t0, sig, r2, popt
    except Exception:
        return 0.0, 1e-9, 0.0, None


def _fit_with_errors(f, vt_i, mask):
    """Returns (t0, sig_a, sig_m, r2, popt).

    Two σ slots kept for back-compat with existing scoring code, BUT both
    now respect the global SIGMA_METHOD toggle:
       sig_a = σ via std(|residuals|)/√n (Calculate T0 convention)
       sig_m = σ via pcov[-1,-1] (statistically correct SE of intercept)

    Down-stream scoring uses `sig_a + sig_m`. To avoid double-counting the
    "wrong" σ, when SIGMA_METHOD == 'standard' both slots return the same
    standard-SE value; when 'calc_t0' both return std(|r|)/√n. This makes
    `sig_a + sig_m == 2·σ_selected`, a constant scale on the score that
    doesn't affect ranking.
    """
    sel = np.where(mask == 1)[0]
    n = len(sel)
    if n < 2:
        return 0.0, 1e-9, 1e-9, 0.0, None
    t, v = vt_i[sel, 1], vt_i[sel, 0]
    try:
        popt, pcov = curve_fit(f, t, v)
        t0 = f(0, *popt)
        residuals = v - f(t, *popt)
        sig = _sigma_from_fit(residuals, n, popt, pcov, t)
        # both slots = selected σ → score uses 2·σ, ranking preserved
        r2 = r2_score(v, f(t, *popt))
        return t0, sig, sig, r2, popt
    except Exception:
        return 0.0, 1e-9, 1e-9, 0.0, None


def _both_sigmas(f, vt_i, mask):
    """Compute BOTH σ formulas for the same fit. Useful for side-by-side reporting.
    Returns (t0, sig_calc_t0, sig_standard, r2, popt)."""
    sel = np.where(mask == 1)[0]
    n = len(sel)
    if n < 2:
        return 0.0, 1e-9, 1e-9, 0.0, None
    t, v = vt_i[sel, 1], vt_i[sel, 0]
    try:
        popt, pcov = curve_fit(f, t, v)
        t0 = f(0, *popt)
        residuals = v - f(t, *popt)
        sig_calc_t0 = _sigma_from_fit(residuals, n, popt, pcov, t, method='calc_t0')
        sig_standard = _sigma_from_fit(residuals, n, popt, pcov, t, method='standard')
        r2 = r2_score(v, f(t, *popt))
        return t0, sig_calc_t0, sig_standard, r2, popt
    except Exception:
        return 0.0, 1e-9, 1e-9, 0.0, None


def _all_combos_cached(n, min_use=4, max_excl=6, limit=200):
    """All (mask, n_used) combos with n_used >= min_use."""
    results = []
    def go(start, cur, remaining):
        results.append(np.array(cur + [1]*remaining, dtype=float))
        if remaining == 0:
            return
        for excl_from in range(start, n):
            if n - excl_from - 1 < (min_use - len(cur) - remaining + 1):
                break
            new = cur + [1]*(excl_from - start) + [0]
            rem = n - excl_from - 1
            if len(new) + rem >= min_use and len(results) < limit:
                pass
        # simpler: enumerate all combos of size k for k = n down to min_use
    results.clear()
    for k in range(n, min_use - 1, -1):
        for combo in _iter_combos(n, k, limit - len(results)):
            m = np.zeros(n)
            for idx in combo:
                m[idx] = 1
            results.append(m)
            if len(results) >= limit:
                return results
    return results


def _iter_combos(n, k, limit=200):
    """Generate k-combinations from n elements, up to limit.

    Optimized iterative version (V3.4.1) using index-based approach.
    Avoids deep recursion and excessive list copying.
    Time: O(C(n,k) x k) worst case, but early-exits on limit.
    ~50-70% faster than original recursive version.
    """
    result = []
    if k <= 0 or k > n:
        return result
    indices = list(range(k))

    while indices[0] < n - k + 1:
        result.append(indices[:])  # Shallow copy (k elements only)
        if len(result) >= limit:
            return result

        # Next combination
        i = k - 1
        while i >= 0 and indices[i] == n - k + i:
            i -= 1

        if i < 0:
            break

        indices[i] += 1
        for j in range(i + 1, k):
            indices[j] = indices[j - 1] + 1

    return result


# ═══════════════════════════════════════════════════════════
# Bi-directional Strategy Core Functions
# ═══════════════════════════════════════════════════════════

# Strategy parameters (can be tuned)
STRAT_ALPHA = 0.3   # n weight: small n → larger score penalty
STRAT_BETA  = 0.5   # cycle spread penalty strength (only for n≤5)
SPREAD_MIN_SPAN = {4: 5, 5: 6}  # minimum required span for n=4, n=5


def _n_weight(n, n_max=10, n_min=4):
    """Weight function: penalize small n heavily.
    Returns 0 for n_max, 1 for n_min.
    Exponential growth makes small-n combinations clearly worse.
    """
    # Linear in [0, 1]
    x = (n_max - n) / (n_max - n_min)
    # Exponential: n=10 → 0, n=9 → 0.28, n=7 → 1.0, n=4 → 4.0
    return (np.exp(2 * x) - 1) / (np.exp(2) - 1) * 4


def _cycle_spread_penalty(mask, n_total=10):
    """Penalize 'clustered' cycle selection for n=4, n=5.
    Returns 0 if n >= 6 or if span is adequate.
    Returns 0-1 scaled by how far span falls short.
    """
    selected = np.where(mask == 1)[0]
    n_used = len(selected)
    
    if n_used >= 6:
        return 0.0
    
    span = selected.max() - selected.min()
    min_span = SPREAD_MIN_SPAN.get(n_used, 0)
    
    if span >= min_span:
        return 0.0
    
    # Linear penalty: closer to 0 span → closer to 1
    return (min_span - span) / min_span


def _compute_combo_score(sig_a, sig_m, n, mask, nc=10,
                         alpha=STRAT_ALPHA, beta=STRAT_BETA):
    """Compute total score for a cycle combination.
    
    score = (σ_a + σ_m) × (1 + α × w_n)² + β × σ × spread_penalty × 10
    
    Quadratic penalty ensures small-n solutions are decisively worse
    unless they have drastically lower σ.
    """
    total_sig = sig_a + sig_m
    wn = _n_weight(n)           # 0 for n=10, up to 4 for n=4
    spread = _cycle_spread_penalty(mask, nc)
    
    # Multiplicative penalty: n=10 × 1, n=4 × (1+0.3×4)² = 4.84
    n_factor = (1 + alpha * wn) ** 2
    
    # Base score
    base = total_sig * n_factor
    # Spread penalty: strong, scaled by σ
    penalty = beta * total_sig * spread * 10
    
    return base + penalty


def _enumerate_combos_simple(vt_i, fit_type, n_total):
    """v3.8.26: worker-callable enumerate, mirrors MvCanvas._enumerate_combos
    exactly (k = n_total..4, no penalty, no R² rejection). Returns list of
    (t0, sig, k, mask) tuples. Used by PrefetchWorker to pre-compute combo
    fits for all step/isotope pairs in a background thread."""
    f = Utilities.fit_func_list[fit_type]
    out = []
    for k in range(n_total, 3, -1):
        for combo in _iter_combos(n_total, k):
            m = np.zeros(n_total)
            for idx in combo: m[idx] = 1
            t0, sig, _, _ = _fit_one(f, vt_i, m)
            out.append((t0, sig, k, m.copy()))
    return out


def _enumerate_combos_for_isotope(vt_i, fit_type=0, n_total=10,
                                    min_use=4, limit_per_n=150):
    """Enumerate all cycle combos for an isotope, returning detailed info.
    
    Returns list of dicts:
      {'mask': np.array, 'n': int, 't0': float,
       'sig_a': float, 'sig_m': float, 'sig_total': float,
       'score': float, 'n_weight': float, 'spread_penalty': float}
    """
    f = Utilities.fit_func_list[fit_type]
    combos = []
    
    for k in range(n_total, min_use - 1, -1):
        for combo in _iter_combos(n_total, k, limit_per_n):
            m = np.zeros(n_total)
            for idx in combo:
                m[idx] = 1
            
            t0, sig_a, sig_m, r2, _ = _fit_with_errors(f, vt_i, m)
            
            if sig_a <= 0 or sig_m <= 0:
                continue
            
            score = _compute_combo_score(sig_a, sig_m, k, m, n_total)
            
            combos.append({
                'mask': m.copy(),
                'n': k,
                't0': t0,
                'sig_a': sig_a,
                'sig_m': sig_m,
                'sig_total': sig_a + sig_m,
                'r2': r2,
                'score': score,
                'n_weight': _n_weight(k),
                'spread_penalty': _cycle_spread_penalty(m, n_total),
            })
    
    return combos


def _blank_out_pass(blank_vt, fit_type=0, n_total=10):
    """Blank-out pass: find best T0 for each of 5 blank isotopes.
    
    For each isotope independently:
      - Enumerate all (n, combo) 
      - Minimize: score = (σ_a + σ_m) × (1 + α·w_n) + β·spread_penalty
      - No blank-constraint (this IS the blank)
    
    Returns: list of 5 result dicts, one per isotope
    """
    results = []
    for ai in range(5):
        combos = _enumerate_combos_for_isotope(blank_vt[ai], fit_type, n_total)
        if not combos:
            results.append(None)
            continue
        # Pick the one with minimum score
        best = min(combos, key=lambda c: c['score'])
        results.append(best)
    return results


def _signal_out_pass(sample_vt, blank_t0, fit_type=0, n_total=10):
    """Signal-out pass with SERIAL per-isotope cycle selection.

    Order:
      1. Ar37  — minimize σ(T0_net_37) / |T0_net_37| + n-penalty
                 (apply 37Ar decay correction with DELTA_T_DAYS for Ca check)
      2. Ar36  — minimize |Ar36_air|/|T0_blank_36|
                            + α · σ_air/|T0_blank_36|
                            + n-penalty
                 where Ar36_air = T0_net_36 - PR(36/37ca) × T0_net_37_dc
                 (hard constraint Ar36_air > 0; falls back to legacy score if all
                 candidates violate)
      3. Ar38  — same as 39/40 family
      4. Ar39  — minimize σ/|T0_net| + γ·(1-R²) + n-penalty
      5. Ar40  — same as 39

    Returns same list-of-5-dicts shape as before, plus extra keys
    ('Ar36_air_est', 'sig_air_est' for ai==0).
    """
    f = Utilities.fit_func_list[fit_type]
    p = _PR
    ALPHA_36 = 0.3                       # bias/variance weight for 36Ar
    GAMMA_R2 = 0.2                       # linearity penalty for strong isotopes
    BETA_N   = 1.0                       # n-count penalty (also see STRAT params)
    results = [None] * 5

    # ── helper: score-min over combos with custom score fn ────────────────
    def best_combo(ai, score_fn, valid_fn=lambda c: True):
        combos = _enumerate_combos_for_isotope(sample_vt[ai], fit_type, n_total)
        if not combos:
            return None
        for c in combos:
            c['custom_score'] = score_fn(c)
        valid = [c for c in combos if valid_fn(c) and np.isfinite(c['custom_score'])]
        if not valid:
            return None
        return min(valid, key=lambda c: c['custom_score'])

    # ── Step 1: Ar37 ──────────────────────────────────────────────────────
    bt0_37 = blank_t0[1]
    def score37(c):
        t0n = c['t0'] - bt0_37
        if abs(t0n) < 1e-15:
            return float('inf')
        return c['sig_total']/abs(t0n) + BETA_N*(1 - c['n']/n_total)
    best_37 = best_combo(1, score37)
    if best_37 is None:
        # legacy fallback if Ar37 cannot be fit at all
        return _legacy_signal_out_pass(sample_vt, blank_t0, fit_type, n_total)
    # apply 37Ar decay (Δt = DELTA_T_DAYS, half-life 35.011 d)
    t0_net_37_raw = best_37['t0'] - bt0_37
    sig_37_net    = best_37['sig_total']
    t0_net_37_dc, sig_37_net_dc = decay_correct(
        t0_net_37_raw, sig_37_net, DELTA_T_DAYS, isotope='37')
    best_37['t0_net'] = t0_net_37_raw
    best_37['t0_net_dc'] = t0_net_37_dc
    best_37['sig_net'] = sig_37_net
    best_37['sig_net_dc'] = sig_37_net_dc
    best_37['constraint_ok'] = True
    best_37['violation'] = 0.0
    results[1] = best_37

    # ── Step 2: Ar36 (depends on Ar37) ────────────────────────────────────
    bt0_36 = blank_t0[0]
    norm_36 = max(abs(bt0_36), 1e-12)
    Ar36_ca   = p['PR_36_37ca'] * t0_net_37_dc
    sig_36_ca = abs(p['PR_36_37ca']) * sig_37_net_dc
    def score36(c):
        t0n = c['t0'] - bt0_36
        Ar36_air = t0n - Ar36_ca
        sig_air  = math.sqrt(c['sig_total']**2 + sig_36_ca**2)
        c['Ar36_air_est'] = Ar36_air
        c['sig_air_est']  = sig_air
        if Ar36_air <= 0:
            return float('inf')
        return (Ar36_air/norm_36
                + ALPHA_36 * sig_air/norm_36
                + BETA_N * (1 - c['n']/n_total))
    best_36 = best_combo(0, score36, valid_fn=lambda c: c.get('Ar36_air_est', -1) > 0)
    if best_36 is None:
        # No combo gives Ar36_air > 0: fall back to legacy least-violating logic
        combos = _enumerate_combos_for_isotope(sample_vt[0], fit_type, n_total)
        for c in combos:
            c['violation'] = max(0, bt0_36 - c['t0'])
            c['combined']  = c['violation']*1e6 + c['score']
        best_36 = min(combos, key=lambda c: c['combined']) if combos else None
        if best_36 is not None:
            best_36['constraint_ok'] = False
    else:
        best_36['constraint_ok'] = True
        best_36['violation'] = 0.0
    results[0] = best_36

    # ── Steps 3-5: Ar38, Ar39, Ar40 (independent, σ/T0 + R² penalty) ──────
    for ai in (2, 3, 4):
        bt = blank_t0[ai]
        def score_strong(c, bt=bt):
            t0n = c['t0'] - bt
            if t0n <= 0:
                return float('inf')
            return (c['sig_total']/t0n
                    + GAMMA_R2 * max(0, 1 - c.get('r2', 0))
                    + BETA_N * (1 - c['n']/n_total))
        best = best_combo(ai, score_strong, valid_fn=lambda c, bt=bt: c['t0'] > bt)
        if best is None:
            # legacy least-violating
            combos = _enumerate_combos_for_isotope(sample_vt[ai], fit_type, n_total)
            for c in combos:
                c['violation'] = max(0, bt - c['t0'])
                c['combined']  = c['violation']*1e6 + c['score']
            best = min(combos, key=lambda c: c['combined']) if combos else None
            if best is not None:
                best['constraint_ok'] = False
        else:
            best['constraint_ok'] = True
            best['violation'] = 0.0
        results[ai] = best

    return results


def _legacy_signal_out_pass(sample_vt, blank_t0, fit_type=0, n_total=10):
    """Old per-isotope independent enumeration. Used as fallback."""
    f = Utilities.fit_func_list[fit_type]
    ref_mask = np.ones(n_total)
    ref_t0 = np.zeros(5)
    for ai in range(5):
        t0, _, _, _, _ = _fit_with_errors(f, sample_vt[ai], ref_mask)
        ref_t0[ai] = t0
    p = _PR
    results = []
    for ai in range(5):
        combos = _enumerate_combos_for_isotope(sample_vt[ai], fit_type, n_total)
        if not combos:
            results.append(None); continue
        bt0 = blank_t0[ai]
        valid = [c for c in combos if c['t0'] > bt0]
        if ai == 0 and valid:
            t0n37 = ref_t0[1] - blank_t0[1]
            Ar36_ca_ref = t0n37 * p['PR_36_37ca']
            for c in valid:
                c['Ar36_air_est'] = (c['t0'] - bt0) - Ar36_ca_ref
            good = [c for c in valid if c['Ar36_air_est'] > 0]
            if good: valid = good
        if valid:
            best = min(valid, key=lambda c: c['score'])
            best['constraint_ok'] = True; best['violation'] = 0.0
        else:
            for c in combos:
                c['violation'] = max(0, bt0 - c['t0'])
                c['combined']  = c['violation']*1e6 + c['score']
            best = min(combos, key=lambda c: c['combined'])
            best['constraint_ok'] = False
        results.append(best)
    return results


def _check_physics_constraints(t0_sample, sig_sample_a, sig_sample_m,
                                 t0_blank, sig_blank_a, sig_blank_m):
    """Check physics constraints on a candidate T0 set.
    
    Returns dict with:
      'ok': bool - all constraints satisfied
      'violations': list of str - human readable violation descriptions
      'values': dict of derived quantities (Ar36_air, Ar39_K, Ar40_r, etc.)
    """
    p = _PR
    violations = []
    
    # T0_net
    t0n = t0_sample - t0_blank
    sig_a_net = np.sqrt(sig_sample_a**2 + sig_blank_a**2)
    sig_m_net = np.sqrt(sig_sample_m**2 + sig_blank_m**2)
    sig_total_net = sig_a_net + sig_m_net
    
    # A: T0_net > 0 for all
    for i, tn in enumerate(t0n):
        if tn <= 0:
            violations.append(f'T0_net[{36+i}Ar] ≤ 0 (signal ≤ blank)')
    
    # B: 36Ar_air > 0
    Ar36_ca = t0n[1] * p['PR_36_37ca']
    Ar36_air = t0n[0] - Ar36_ca
    if Ar36_air <= 0:
        violations.append(f'Ar36_air ≤ 0 (37Ar too high?)')
    
    # C: 39Ar_K > 0
    Ar39_ca = t0n[1] * p['PR_39_37ca']
    Ar39_K = t0n[3] - Ar39_ca
    if Ar39_K <= 0:
        violations.append(f'Ar39_K ≤ 0 (37Ar contamination)')
    
    # D: 40Ar_r > 0
    Ar40_air = Ar36_air * p['R_40_36a']
    Ar40_K = Ar39_K * p['PR_40_39k']
    Ar40_r = t0n[4] - Ar40_air - Ar40_K
    if Ar40_r <= 0:
        violations.append(f'Ar40_r ≤ 0 (no radiogenic signal)')
    
    # E: 38Ar_Cl sanity check
    Ar38_air = Ar36_air * p['R_38_36a']
    Ar38_K = Ar39_K * p['PR_38_39k'] if Ar39_K > 0 else 0
    Ar38_cl = t0n[2] - Ar38_air - Ar38_K
    sig_38cl = np.sqrt(sig_total_net[2]**2 + 
                       (sig_total_net[0] * p['R_38_36a'])**2)
    if sig_38cl > 0 and abs(Ar38_cl) > 2 * sig_38cl:
        violations.append(f'Ar38_Cl > 2σ anomaly')
    
    # F: 40Ar_r% (use net value as denominator, consistent with _propagate)
    Ar40r_pct = Ar40_r / t0n[4] * 100 if t0n[4] != 0 else 0
    if 0 < Ar40r_pct < 5:
        violations.append(f'40Ar_r% = {Ar40r_pct:.1f}% (very low)')
    
    return {
        'ok': len(violations) == 0,
        'violations': violations,
        'values': {
            'T0_net': t0n,
            'Ar36_air': Ar36_air,
            'Ar36_ca': Ar36_ca,
            'Ar39_K': Ar39_K,
            'Ar39_ca': Ar39_ca,
            'Ar40_air': Ar40_air,
            'Ar40_K': Ar40_K,
            'Ar40_r': Ar40_r,
            'Ar40r_pct': Ar40r_pct,
            'Ar38_Cl': Ar38_cl,
        }
    }


# ═══════════════════════════════════════════════════════════
# End of bi-directional strategy core
# ═══════════════════════════════════════════════════════════


class MvCanvas(QtWidgets.QWidget):
    maskChanged = QtCore.pyqtSignal()

    # colour map by n_used: 10→4
    _NCOLS = {
        10: '#1a5fb4', 9: '#2e8b57', 8: '#e67e00',
        7:  '#9b59b6', 6: '#e74c3c', 5: '#16a085', 4: '#f39c12'
    }

    def __init__(self, ai, parent=None):
        super().__init__(parent)
        self.ai   = ai
        self.col  = AR_COLS[ai]
        self.nm   = AR_NAMES[ai]
        self._vt   = None
        self._mask = None
        self._bt   = None
        self._fit  = 0
        self._manual = False
        self._nc   = 10
        # all combo cache: list of (t0, sig2, n_used, mask_arr)
        self._all_pts = []
        # sibling T0: used for 36Ar physical constraint
        # For Ar36 (ai=0): _t0_net_37 = T0_net[37] from sibling Ar37 canvas
        # Set externally by CalcT0Page after each mask change
        self._t0_net_37 = 0.0   # T0_net[37], updated by CalcT0Page
        self._bt_sig    = None  # blank T0 for this isotope (raw, not net)
        self._build()

    # ── build ────────────────────────────────────────────────
    def _build(self):
        vb = QtWidgets.QVBoxLayout(self)
        vb.setContentsMargins(2, 2, 2, 2); vb.setSpacing(2)

        # Ar title above the chart (Qt label).
        # v3.8.16: restored from v3.8.15 attempt to move it inside the chart —
        # user prefers the external label format. Title shows
        # "Ar36  T₀=...  err=...  R²=..." in a single rich-text line.
        sup_map = {'36':'³⁶','37':'³⁷','38':'³⁸','39':'³⁹','40':'⁴⁰'}
        self.titleLbl = QtWidgets.QLabel(f'Ar{sup_map.get(self.nm, self.nm)}')
        self.titleLbl.setTextFormat(QtCore.Qt.RichText)
        self.titleLbl.setStyleSheet(
            f'font-size:18px;font-weight:bold;color:{AR_COLS[self.ai]};'
            f'padding-bottom:0px;margin-bottom:0px;background:transparent;')
        self.titleLbl.setAlignment(QtCore.Qt.AlignLeft)
        self.titleLbl.setMinimumWidth(1)
        vb.addWidget(self.titleLbl)

        # mV canvas. v3.8.17: min width 220 → 260 so enlarged button rows
        # (n-filter, best-per-n) still fit inside the chart's horizontal extent.
        self.cv_mv = QtWidgets.QLabel()
        self.cv_mv.setMinimumSize(260, 1)
        self.cv_mv.setAlignment(QtCore.Qt.AlignCenter)
        self.cv_mv.setStyleSheet(f'background:white;border:1px solid {BRD};')
        self.cv_mv.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        vb.addWidget(self.cv_mv, 1)   # v3.8.16: stretch 1:1 with cv_sc → square scatter

        # cycle buttons 1-10. v3.8.16: stretch on BOTH sides → row centred,
        # roughly aligning with the chart's x-axis data range (which is itself
        # centred within cv_mv after matplotlib's internal margins).
        # v3.8.17: size 22×22 → 26×24 for better readability under enlarged charts.
        self._btns = []
        cg = QtWidgets.QWidget()
        gl = QtWidgets.QHBoxLayout(cg)
        gl.setContentsMargins(0, 0, 0, 0); gl.setSpacing(0)
        gl.addStretch()
        for i in range(10):
            b = QtWidgets.QPushButton(str(i + 1))
            b.setFixedSize(26, 24); b.setCheckable(True); b.setChecked(True)
            b.setStyleSheet(self._cs(True))
            b.clicked.connect(lambda _, idx=i: self._toggle(idx))
            gl.addWidget(b)
            self._btns.append(b)
        gl.addStretch()
        vb.addWidget(cg)

        self.usedLbl = QtWidgets.QLabel('Used: 10/10')
        self.usedLbl.setStyleSheet(
            f'font-size:12px;color:{TXT3};font-family:Courier New;')
        self.usedLbl.setMinimumWidth(1)
        vb.addWidget(self.usedLbl)

        # T0 vs 2σ — interactive FigureCanvas
        # v3.8.17: title text shown only on Ar36 (ai==0); other canvases get an
        # empty label of same style so the border-top line continues across all
        # 5 columns, visually acting as one shared "T\u2080 vs 2\u03c3" header.
        sc_hdr_text = 'T\u2080 vs 2\u03c3' if self.ai == 0 else ''
        sc_hdr = QtWidgets.QLabel(sc_hdr_text)
        sc_hdr.setStyleSheet(
            f'font-size:14px;font-weight:bold;color:{TXT2};'
            f'border-top:1px solid {BRD};padding-top:2px;')
        sc_hdr.setToolTip('Manual mode: click any dot to select that cycle combo.')
        sc_hdr.setMinimumWidth(1)
        sc_hdr.setFixedHeight(22)  # same height across all 5 \u2192 divider aligns
        vb.addWidget(sc_hdr)

        # v3.8.12: \u03c3 values shown as a Qt label above the scatter (was an
        # in-axes text annotation that overlapped data on Ar39/Ar40).
        self.scInfoLbl = QtWidgets.QLabel('')
        self.scInfoLbl.setStyleSheet(
            f'font-size:10px;font-family:"Courier New",monospace;color:{TXT2};'
            f'background:transparent;padding:1px 4px;')
        self.scInfoLbl.setTextFormat(QtCore.Qt.RichText)
        # v3.8.14: word-wrap on + minWidth 1 so this label cannot inflate the
        # MvCanvas min size when σ strings are long.
        self.scInfoLbl.setWordWrap(True)
        self.scInfoLbl.setMinimumWidth(1)
        vb.addWidget(self.scInfoLbl)

        # n-filter toggle row: All + n=10..4 (移到 scatter plot 上方，透明背景)
        self._n_filter = set(range(4, 11))
        nf_row = QtWidgets.QWidget()
        nf_row.setStyleSheet('background:transparent;')  # 透明背景
        nf_gl  = QtWidgets.QHBoxLayout(nf_row)
        nf_gl.setContentsMargins(0,0,0,0); nf_gl.setSpacing(0)
        self._nf_btns = {}
        # v3.8.16: stretch on BOTH sides → row centred under the scatter chart.
        # v3.8.17: button sizes ~1.4× larger (All 28→40, n=10 24→32, n=9..4 20→28),
        # font 12→14 px. Row total ≈ 40+32+6×28 = 240 px → fits inside the
        # 260 px cv_mv min width.
        nf_gl.addStretch()
        btn_all = QtWidgets.QPushButton('All')
        btn_all.setFixedSize(40, 30); btn_all.setCheckable(True); btn_all.setChecked(True)
        btn_all.setStyleSheet(
            f'QPushButton{{background:{BLUE_BG};color:#000;border:1px solid #1a5fb4;'
            f'border-radius:3px;font-size:14px;font-weight:bold;}}'
            f'QPushButton:!checked{{background:#eeede8;color:#000;border:1px solid {BRD};}}')
        btn_all.clicked.connect(self._nf_toggle_all)
        nf_gl.addWidget(btn_all)
        self._nf_all_btn = btn_all
        for n in range(10, 3, -1):
            b = QtWidgets.QPushButton(f'{n}')
            w = 32 if n == 10 else 28
            b.setFixedSize(w, 30); b.setCheckable(True); b.setChecked(True)
            b.setStyleSheet(
                f'QPushButton{{background:{BLUE_BG};color:#000;border:1px solid #1a5fb4;'
                f'border-radius:3px;font-size:14px;font-weight:bold;}}'
                f'QPushButton:!checked{{background:#eeede8;color:#000;border:1px solid {BRD};}}')
            b.clicked.connect(lambda _, nv=n: self._nf_toggle(nv))
            nf_gl.addWidget(b)
            self._nf_btns[n] = b
        nf_gl.addStretch()
        vb.addWidget(nf_row)

        self._sc_fig = _mfig.Figure(facecolor='white')
        self._sc_ax  = self._sc_fig.add_subplot(111)
        QtWidgets.QApplication.processEvents()
        self.cv_sc   = _FigCanvas(self._sc_fig)
        self.cv_sc.setMinimumSize(1, 1)
        self.cv_sc.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.cv_sc.setStyleSheet(f'border:1px solid {BRD};')
        self.cv_sc.mpl_connect('button_press_event', self._sc_click)
        vb.addWidget(self.cv_sc, 1)   # v3.8.16: 1:1 with cv_mv; scatter near 1:1 W:H

        # Best-n buttons: one per n_used (10→4), shows min-error for that n
        # v3.8.17: header text on Ar36 only (matches sc_hdr dedupe pattern).
        best_hdr_text = 'Best per n' if self.ai == 0 else ''
        best_hdr = QtWidgets.QLabel(best_hdr_text)
        best_hdr.setStyleSheet(
            f'font-size:14px;font-weight:bold;color:{TXT2};padding-top:2px;')
        best_hdr.setToolTip('Cycle count with the minimum residual error '
                            '(click to apply that mask).')
        best_hdr.setMinimumWidth(1)
        best_hdr.setFixedHeight(22)
        vb.addWidget(best_hdr)

        self._best_row = QtWidgets.QWidget()
        self._best_gl  = QtWidgets.QHBoxLayout(self._best_row)
        self._best_gl.setContentsMargins(0,0,0,0); self._best_gl.setSpacing(0)
        # v3.8.16: leading stretch + trailing stretch (added below) → centred
        # v3.8.17: button sizes ~1.4× larger (28×28 → 40×34, 24×28 → 32×34),
        # font set in _update_best_btns bumped 9→13. Row total ≈ 40+6×32 = 232 px.
        self._best_gl.addStretch()
        self._best_btns = {}   # n_used → QPushButton
        for n in range(10, 3, -1):
            b = QtWidgets.QPushButton(str(n))   # v3.8.12: drop "n=" prefix
            # v3.8.14: fixed width so the row min stays compact (was variable
            # width with Qt's ~75 px default → blew up MvCanvas min size).
            b.setFixedSize(40 if n == 10 else 32, 34)
            b.setStyleSheet(
                f'QPushButton{{background:#eeede8;color:{TXT2};'
                f'border:1px solid {BRD};border-radius:3px;font-size:13px;'
                f'font-weight:bold;}}'
                f'QPushButton:hover{{background:{BLUE_BG};}}')
            b.clicked.connect(lambda _, nv=n: self._apply_best(nv))
            self._best_gl.addWidget(b)
            self._best_btns[n] = b
        self._best_gl.addStretch()
        vb.addWidget(self._best_row)
        # bestLbl 移除（圖上已有綠色標示最佳解）


    # ── cycle button style ───────────────────────────────────
    def _cs(self, sel, z=None):
        """Style for cycle button.
           sel : True if this cycle is included in current mask
           z   : residual z-score (MAD-based) of this cycle vs current fit.
                 None → plain colour. z < 1.8 → healthy (blue);
                 1.8 ≤ z < 3.0 → suspicious (amber); z ≥ 3.0 → outlier (red)."""
        if not sel:
            # excluded cycle — always greyed out red text
            return (f'QPushButton{{background:#eeede8;color:#b41a1a;'
                    f'border:1px solid {BRD2};border-radius:3px;'
                    f'font-size:12px;font-weight:bold;}}')
        # included: tint by z
        if z is not None and np.isfinite(z):
            if z >= 3.0:        # outlier — alert red
                return (f'QPushButton{{background:#ffd6d6;color:#a01010;'
                        f'border:1.5px solid #b41a1a;border-radius:3px;'
                        f'font-size:12px;font-weight:bold;}}')
            if z >= 1.8:        # suspicious — amber
                return (f'QPushButton{{background:#fff4d0;color:#8a6000;'
                        f'border:1.5px solid #c0a020;border-radius:3px;'
                        f'font-size:12px;font-weight:bold;}}')
        # healthy / no z available
        return (f'QPushButton{{background:{BLUE_BG};color:#1a5fb4;'
                f'border:1.5px solid #1a5fb4;border-radius:3px;'
                f'font-size:12px;font-weight:bold;}}')

    def _cycle_z_scores(self):
        """Return per-cycle MAD-based z-score from residuals of current fit.
        Uses ALL cycles to compute residuals against the line fit to the
        currently-selected subset.  Returns np.array of length nc or None."""
        if self._vt is None or self._mask is None:
            return None
        try:
            f = Utilities.fit_func_list[self._fit]
            sel = np.where(self._mask == 1)[0]
            if len(sel) < 3:
                return None
            t_sel = self._vt[sel, 1]; v_sel = self._vt[sel, 0]
            popt, _ = curve_fit(f, t_sel, v_sel)
            all_t = self._vt[:self._nc, 1]
            all_v = self._vt[:self._nc, 0]
            resid = all_v - f(all_t, *popt)
            # MAD on selected subset (robust to outliers)
            med = float(np.median(resid[sel]))
            mad = float(np.median(np.abs(resid[sel] - med)))
            sigma_mad = 1.4826 * mad
            if sigma_mad < 1e-15:
                sigma_mad = float(np.std(resid[sel]) + 1e-15)
            return np.abs(resid - med) / sigma_mad
        except Exception:
            return None

    def _apply_btn_styles(self):
        """Re-apply colour + tooltip on all 10 cycle buttons."""
        if self._vt is None or self._mask is None: return
        zs = self._cycle_z_scores()
        for i, b in enumerate(self._btns[:self._nc]):
            b.setChecked(bool(self._mask[i]))
            z = float(zs[i]) if zs is not None else None
            b.setStyleSheet(self._cs(bool(self._mask[i]), z=z))
            try:
                t_val = float(self._vt[i, 1])
                mv_val = float(self._vt[i, 0])
                lines = [f'Cycle {i+1}',
                         f't = {t_val:.1f} s',
                         f'mV = {mv_val:.3e}']
                if z is not None:
                    tag = ('outlier' if z >= 3 else
                           'suspicious' if z >= 1.8 else 'healthy')
                    lines.append(f'z = {z:.2f}  ({tag})')
                lines.append(f"status: {'used' if self._mask[i] else 'excluded'}")
                b.setToolTip('\n'.join(lines))
            except Exception:
                pass

    # ── toggle ───────────────────────────────────────────────
    def _toggle(self, idx):
        if not self._manual or self._mask is None:
            self._btns[idx].setChecked(not self._btns[idx].isChecked()); return
        self._mask[idx] = 1 if self._btns[idx].isChecked() else 0
        if self._mask.sum() < 4:
            self._mask[idx] = 1 - self._mask[idx]
            self._btns[idx].setChecked(bool(self._mask[idx])); return
        self._refresh(); self.maskChanged.emit()

    # ── load / refresh ───────────────────────────────────────
    def load(self, vt_i, mask, bt=None, fit=0, manual=False, prefetched_fits=None):
        self._vt     = vt_i
        self._mask   = mask.copy()
        self._bt     = bt
        self._fit    = fit
        self._manual = manual
        self._nc     = len(mask)
        # v3.8.10 perf: cache the expensive combo enumeration (~848 curve_fits
        # per isotope) keyed by (vt object id, fit type, nc). When user switches
        # between Blank ↔ signal step, each step reuses its cached fits and only
        # validity flags (cheap) are recomputed. Cuts step-switch latency ~20×.
        # v3.8.26: if CalcT0Page background-prefetched fits are available, take
        # them straight from the parent's cache — skips the ~4 s enumerate per
        # isotope when first visiting a step.
        cache_key = (id(vt_i), fit, self._nc)
        if getattr(self, '_combo_cache_key', None) != cache_key:
            if prefetched_fits is not None:
                self._combo_fits = prefetched_fits
            else:
                self._enumerate_combos()
            self._combo_cache_key = cache_key
        self._recompute_validity()
        self._refresh()

    def _enumerate_combos(self):
        """Run C(nc,k) curve_fit enumeration for k=4..nc. Stores raw (t0, sig, k, mask)
        in self._combo_fits. Does NOT compute valid flags — those depend on bt and
        sibling T0_net[37] which can change without invalidating the cached fits."""
        if self._vt is None: return
        f  = Utilities.fit_func_list[self._fit]
        nc = self._nc
        self._combo_fits = []
        for k in range(nc, 3, -1):
            for combo in _iter_combos(nc, k):
                m = np.zeros(nc)
                for idx in combo: m[idx] = 1
                t0, sig, _, _ = _fit_one(f, self._vt, m)
                self._combo_fits.append((t0, sig, k, m.copy()))

    def _recompute_validity(self):
        """Reapply current bt / _t0_net_37 to the cached combo fits to derive
        _all_pts (with valid flag) and _best_n. Cheap — no curve_fit calls."""
        if self._vt is None or not getattr(self, '_combo_fits', None): return
        ar36_ca_thresh = self._t0_net_37 * _PR['PR_36_37ca'] if self.ai == 0 else 0.0
        self._all_pts = []
        best_n = {}
        bt = self._bt or 0.0
        for t0, sig, k, m in self._combo_fits:
            if self.ai == 0:
                t0_net = t0 - bt
                valid  = (t0_net > 0) and (t0_net - ar36_ca_thresh > 0)
            elif self.ai == 1:
                valid = (t0 - bt) > 0
            else:
                valid = (self._bt is None) or (t0 > self._bt)
            self._all_pts.append((t0, sig * 2, k, valid, m))
            if valid:
                if self.ai == 0:
                    score = t0 - bt
                    if k not in best_n or score < best_n[k][3]:
                        best_n[k] = (t0, sig, m, score)
                else:
                    if k not in best_n or sig < best_n[k][1]:
                        best_n[k] = (t0, sig, m, sig)
        self._best_n = {k: (v[0], v[1], v[2]) for k, v in best_n.items()}
        self._ar36_ca_thresh = ar36_ca_thresh
        self._update_best_btns()

    # Back-compat alias (used by set_sibling_t0_net_37 below)
    def _build_combos(self):
        self._enumerate_combos()
        self._recompute_validity()

    def _update_best_btns(self):
        """Colour best-n buttons; highlight the currently selected n."""
        if not hasattr(self, '_best_btns'): return
        cur_n = int(self._mask.sum()) if self._mask is not None else 10
        # find global best (most cycles, then min error)
        if self._best_n:
            g_best_n = max(self._best_n.keys())
        else:
            g_best_n = None
        for n, b in self._best_btns.items():
            if n not in self._best_n:
                b.setEnabled(False)
                b.setStyleSheet(
                    f'QPushButton{{background:#f0f0f0;color:#ccc;'
                    f'border:1px solid {BRD};border-radius:3px;font-size:13px;}}')
                b.setToolTip('No valid combo')
                continue
            t0v, sigv, _ = self._best_n[n]
            b.setEnabled(True)
            # colour: current n = blue, global best = green, others = default
            if n == cur_n:
                bg = BLUE_BG; fc = '#1a5fb4'; brd = '#1a5fb4'
            elif n == g_best_n:
                bg = GRN_BG; fc = '#1c7a3a'; brd = '#1c7a3a'
            else:
                bg = '#eeede8'; fc = TXT2; brd = BRD
            b.setStyleSheet(
                f'QPushButton{{background:{bg};color:{fc};'
                f'border:1px solid {brd};border-radius:3px;font-size:13px;font-weight:bold;}}'
                f'QPushButton:hover{{background:{BLUE_BG};}}')
            b.setToolTip(f'n={n}: T0={t0v:.3e}  err={sigv:.3e}')
        # bestLbl 已移除

    def _apply_best(self, n):
        """Apply the best mask for n cycles."""
        if not hasattr(self,'_best_n') or n not in self._best_n: return
        _, _, m = self._best_n[n]
        self._mask = m.copy()
        self._apply_btn_styles()
        u    = int(self._mask.sum())
        excl = [str(i+1) for i in range(self._nc) if self._mask[i] == 0]
        self.usedLbl.setText(
            f'Used: {u}/{self._nc}' +
            (f'  Excl: {",".join(excl)}' if excl else ''))
        self._update_best_btns()
        self._paint_mv()
        self._paint_sc()
        self.maskChanged.emit()

    def get_t0_sig_r2(self):
        if self._vt is None: return 0.0, 0.0, 0.0
        f = Utilities.fit_func_list[self._fit]
        t0, sig, r2, _ = _fit_one(f, self._vt, self._mask)
        return t0, sig, r2

    def set_sibling_t0_net_37(self, t0_net_37):
        """Called by CalcT0Page when Ar37 mask changes.
        Only relevant for Ar36 canvas (ai=0)."""
        if self.ai != 0: return
        if abs(t0_net_37 - self._t0_net_37) < 1e-15: return  # no change
        self._t0_net_37 = t0_net_37
        # Only validity changes — fits are cached and don't need to re-run
        if self._vt is not None:
            self._recompute_validity()
            self._paint_sc()

    def _refresh(self):
        if self._vt is None: return
        self._apply_btn_styles()
        u    = int(self._mask.sum())
        excl = [str(i+1) for i in range(self._nc) if self._mask[i] == 0]
        self.usedLbl.setText(
            f'Used: {u}/{self._nc}' +
            (f'  Excl: {",".join(excl)}' if excl else ''))
        self._paint_mv()
        # v3.8.26: defer scatter + best-btn render to the next event loop
        # tick. This lets the mV chart + tab change paint immediately, so
        # the step switch feels snappy even when scatter still has to draw
        # ~848 points. _paint_sc is the heaviest operation in this widget
        # (recolors per-n, recomputes range, draws axvspan etc).
        QtCore.QTimer.singleShot(0, self._refresh_deferred)

    def _refresh_deferred(self):
        if self._vt is None: return
        self._paint_sc()
        self._update_best_btns()

    # ── mV vs time ────────────────────────────────────────────
    def _paint_mv(self):
        W = self.cv_mv.width(); H = self.cv_mv.height()
        if W < 20 or H < 20 or self._vt is None: return

        f    = Utilities.fit_func_list[self._fit]
        vt_i = self._vt
        vs   = vt_i[:, 0]; ts = vt_i[:, 1]
        mask = self._mask; nc = self._nc

        t0_all, _, _, popt_all = _fit_one(f, vt_i, np.ones(nc))
        t0_inc, sig_inc, r2_inc, popt_inc = _fit_one(f, vt_i, mask)

        dpi = 96
        # v3.8.18: dropped the v3.8.17 strict 1.2:1 W:H aspect constraint —
        # cv_mv aspect (set by Qt vertical layout, ~1.1–1.3:1 depending on
        # window size) was usually taller than 1.2:1, so the 1.2:1 pixmap left
        # visible top/bottom white space inside cv_mv. Now the figure fills
        # cv_mv exactly (pixmap aspect = QLabel aspect → no padding). Y-axis
        # data range is unchanged; only the white margins disappear.
        fig_w = max(W / dpi, 1.0)
        fig_h = max(H / dpi, 1.0)
        # v3.8.15: drop the explicit white facecolor override so seaborn's
        # default 'darkgrid' style (light blue-grey axes + white grid)
        # propagates from Utilities.sns.set(). Matches the CalcT0Page sub-
        # program look (NTNU_DataReduction.py + Utilities.calculateT0).
        fig, ax = _plt.subplots(figsize=(fig_w, fig_h), dpi=dpi)

        # Y-axis: based on DATA only (never expand for blank T0 line)
        vspan = max(vs) - min(vs)
        vpad  = vspan * 0.15 if vspan > 0 else abs(np.mean(vs)) * 0.1 + 1e-10
        ax.set_ylim(min(vs) - vpad, max(vs) + vpad)

        # blank reference line (signal tab only, drawn AFTER ylim set so it won't expand)
        if self._bt is not None:
            ax.axhline(self._bt, color='grey', linestyle='--', linewidth=1.4,
                       alpha=0.7)

        # raw data
        ax.plot(ts, vs, color='#4c72b0', marker='o', linewidth=1.2,
                markersize=4, zorder=3)

        # excluded ×
        excl_idx = [i for i in range(nc) if mask[i] == 0]
        if excl_idx:
            ax.plot(ts[excl_idx], vs[excl_idx], marker='x', color='#b41a1a',
                    linewidth=0, markersize=7, markeredgewidth=1.5, zorder=5)

        t_range = np.linspace(ts[0], ts[-1], 50)
        if popt_all is not None:
            ax.plot(t_range, f(t_range, *popt_all),
                    color='#e67e00', linestyle='--', linewidth=1.2)
        if excl_idx and popt_inc is not None:
            ax.plot(t_range, f(t_range, *popt_inc),
                    color='#1c7a3a', linestyle='--', linewidth=1.2)

        # v3.8.16: update Qt titleLbl above chart (was set_title inside chart in
        # v3.8.15, reverted per user). Single line: "Ar36  T₀=...  err=...  R²=..."
        # Title goes red when blank T₀ ≥ signal T₀ (physics constraint violation).
        if hasattr(self, 'titleLbl'):
            sup_map2 = {'36':'³⁶','37':'³⁷','38':'³⁸','39':'³⁹','40':'⁴⁰'}
            sup2 = sup_map2.get(self.nm, self.nm)
            is_warning = (self._bt is not None) and (t0_inc <= self._bt)
            warn = '⚠ ' if is_warning else ''
            txt_col = '#b41a1a' if is_warning else self.col
            # v3.8.17: T₀/err/R² font 11 → 13 px (user feedback: slightly bigger
            # so values are readable, while staying within the titleLbl width).
            self.titleLbl.setText(
                f'<span style="font-size:18px;font-weight:bold;color:{self.col};">'
                f'Ar{sup2}</span>'
                f'&nbsp;<span style="font-size:13px;font-family:Courier New;color:{txt_col};">'
                f'{warn}T₀={t0_inc:.3e}&nbsp;&nbsp;err={sig_inc:.3e}&nbsp;&nbsp;'
                f'R²={r2_inc:.3f}</span>'
            )

        ax.set_xlabel('t (sec)', fontsize=11)
        if self.ai == 0:
            ax.set_ylabel('mV', fontsize=11)
        else:
            ax.set_ylabel('')
        ax.tick_params(labelsize=9)
        ax.ticklabel_format(axis='y', style='sci', scilimits=(0, 0))
        ax.tick_params(labelsize=14)
        ax.yaxis.set_major_formatter(
            _ticker.ScalarFormatter(useMathText=True))
        ax.ticklabel_format(style='sci', axis='y', scilimits=(0, 0))
        # No per-canvas legend: shared legend shown below Row 1
        ax.grid(True, alpha=0.2, linewidth=0.4)

        _plt.tight_layout(pad=0.2)
        buf = _io.BytesIO()
        fig.savefig(buf, format='png', dpi=dpi, facecolor='white')
        _plt.close(fig)
        buf.seek(0)
        pm = QtGui.QPixmap(); pm.loadFromData(buf.read())
        self.cv_mv.setPixmap(
            pm.scaled(W, H, QtCore.Qt.KeepAspectRatio,
                      QtCore.Qt.SmoothTransformation))
        self.cv_mv._pm = pm

    # ── T0 vs 2σ scatter (interactive FigureCanvas) ─────────
    def _nf_toggle(self, n):
        if n in self._n_filter: self._n_filter.discard(n)
        else: self._n_filter.add(n)
        # Update All button state
        if hasattr(self,'_nf_all_btn'):
            self._nf_all_btn.setChecked(len(self._n_filter)==7)
        self._paint_sc()

    def _nf_toggle_all(self):
        all_on = len(self._n_filter) == 7
        if all_on:
            self._n_filter.clear()
            for b in self._nf_btns.values(): b.setChecked(False)
            self._nf_all_btn.setChecked(False)
        else:
            self._n_filter = set(range(4,11))
            for b in self._nf_btns.values(): b.setChecked(True)
            self._nf_all_btn.setChecked(True)
        self._paint_sc()

    def _paint_sc(self):
        if self._vt is None or not self._all_pts: return

        ax = self._sc_ax
        ax.clear()
        ax.set_facecolor('white')
        self._sc_fig.patch.set_facecolor('white')

        pts = self._all_pts
        t0_cur, sig_cur, _, _ = _fit_one(
            Utilities.fit_func_list[self._fit], self._vt, self._mask)
        # Also compute BOTH σ formulas for display
        _, sig_calc, sig_std, _, _ = _both_sigmas(
            Utilities.fit_func_list[self._fit], self._vt, self._mask)

        # blank T0 vertical line (green dashed)
        if self._bt is not None:
            ax.axvline(self._bt, color='#1c7a3a', linestyle='--',
                       linewidth=0.8, alpha=0.5)

        # Ar36 special: draw 36Ar_ca threshold (purple dotted)
        # Points RIGHT of this line → 36Ar_air > 0 (valid)
        ar36_thresh = getattr(self, '_ar36_ca_thresh', 0.0)
        if self.ai == 0 and self._bt is not None:
            thresh_abs = ar36_thresh + (self._bt or 0.0)
            ax.axvline(thresh_abs, color='#9b59b6', linestyle=':',
                       linewidth=1.2, alpha=0.9,
                       label=f'36ca={ar36_thresh:.2e}')
            # shade invalid region (left of threshold)
            ax.axvspan(ax.get_xlim()[0] if ax.get_xlim()[0] < thresh_abs
                       else thresh_abs - abs(thresh_abs)*0.5,
                       thresh_abs, alpha=0.05, color='#b41a1a', zorder=0)

        from collections import defaultdict
        n_filter = getattr(self, '_n_filter', set(range(4,11)))
        groups = defaultdict(list)
        for t0, e2, nu, valid, _ in pts:
            groups[nu].append((t0, e2, valid))

        for nu in sorted(groups.keys(), reverse=True):
            col = self._NCOLS.get(nu, '#888888')
            xs = [p[0] for p in groups[nu]]
            ys = [p[1] for p in groups[nu]]
            vf = [p[2] for p in groups[nu]]
            if nu not in n_filter:
                # hidden: draw as tiny grey (still use for click selection)
                continue
            vx = [x for x,v in zip(xs,vf) if v]
            vy = [y for y,v in zip(ys,vf) if v]
            ix = [x for x,v in zip(xs,vf) if not v]
            iy = [y for y,v in zip(ys,vf) if not v]
            if vx: ax.scatter(vx, vy, s=max(6,(nu-3)*4), color=col,
                              alpha=0.80, linewidths=0, zorder=3)
            if ix: ax.scatter(ix, iy, s=max(6,(nu-3)*4), color='#cccccc',
                              alpha=0.4, linewidths=0, zorder=2)

        # Mark best Ar36 point: smallest T0_net where 36air>0
        if self.ai == 0 and hasattr(self,'_best_n') and self._best_n:
            # find the best among all n: smallest t0 (closest to thresh)
            best_all = min(self._best_n.values(), key=lambda v:v[0])
            t0_best, sig_best, _ = best_all
            ax.scatter(t0_best, sig_best*2, marker='D', s=60,
                      color='#9b59b6', zorder=7,
                      edgecolors='black', linewidths=0.5)

        # current marker
        self._sc_cur = ax.scatter(
            t0_cur, sig_cur*2, marker='^', s=70,
            color='#e67e00', zorder=6,
            edgecolors='black', linewidths=0.6)

        ax.set_xlabel('$T_0$', fontsize=15)
        # v3.8.13: only Ar36 shows the y-axis '2σ' label
        if self.ai == 0:
            ax.set_ylabel('2σ', fontsize=15)
        else:
            ax.set_ylabel('')
        ax.tick_params(labelsize=14)
        ax.xaxis.set_major_formatter(_ticker.ScalarFormatter(useMathText=True))
        ax.yaxis.set_major_formatter(_ticker.ScalarFormatter(useMathText=True))
        ax.ticklabel_format(style='sci', axis='both', scilimits=(0,0))
        # v3.8.17: enforce 1:1.2 H:W aspect on the axes box — user feedback that
        # the previous 1:1 scatter (v3.8.16) was too tall. set_box_aspect takes
        # H/W ratio, so 1/1.2 → width is 1.2× the box height.
        ax.set_box_aspect(1.0 / 1.2)

        # v3.8.12: σ annotation moved out of axes (was top-left text box,
        # blocked data on Ar39/Ar40 where points cluster top-left). Now
        # rendered as a Qt label above the scatter via _update_sc_info().
        self._update_sc_info(t0_cur, sig_std, sig_calc)

        # No per-canvas legend: shared legend shown below Row 2
        # No per-canvas legend (shared widget below)
        leg = ax.get_legend()
        if leg: leg.remove()
        ax.grid(True, alpha=0.2, linewidth=0.3)

        self._sc_fig.tight_layout(pad=0.3)
        self.cv_sc.draw()

    def _update_sc_info(self, t0, sig_std, sig_calc):
        """Render T₀ / σ(SE) / σ(Calc T₀) into the Qt label above the scatter,
        marking which method is currently active with a ▶."""
        if not hasattr(self, 'scInfoLbl'): return
        active = SIGMA_METHOD
        m_std  = '▶' if active == 'standard' else ' '
        m_calc = '▶' if active != 'standard' else ' '
        # Single-line label; small enough to fit narrow canvases
        txt = (f'<span>T₀={t0:.3e}</span> &nbsp; '
               f'<span>{m_std}σ(SE)={sig_std:.2e}</span> &nbsp; '
               f'<span>{m_calc}σ(Calc T₀)={sig_calc:.2e}</span>')
        self.scInfoLbl.setText(txt)

    # ── scatter click → select nearest combo (real data coords) ──
    def _sc_click(self, event):
        if not self._all_pts or event.inaxes is None: return
        if not self._manual: return

        t0_click = event.xdata; e2_click = event.ydata
        if t0_click is None or e2_click is None: return

        # v3.8.22: respect n-filter — clicks only snap to visible (not greyed-out)
        # combos. Before this fix, picking n=6 then clicking still hit hidden n=7
        # / n=8 points because the loop scanned self._all_pts unconditionally.
        n_filter = getattr(self, '_n_filter', set(range(4, 11)))
        visible = [p for p in self._all_pts if p[2] in n_filter]
        if not visible: return  # nothing to pick

        # normalise for fair distance (use visible-only range so the metric
        # matches what the user sees)
        t0s = [p[0] for p in visible]
        e2s = [p[1] for p in visible]
        t0_rng = max(t0s) - min(t0s) + 1e-30
        e2_rng = max(e2s) - min(e2s) + 1e-30

        best = None; best_d = 1e30
        for t0, e2, nu, valid, m in visible:
            dt = (t0 - t0_click) / t0_rng
            de = (e2 - e2_click) / e2_rng
            d  = dt*dt + de*de
            if d < best_d:
                best_d = d; best = m

        if best is not None:
            self._mask = best.copy()
            self._apply_btn_styles()
            u    = int(self._mask.sum())
            excl = [str(i+1) for i in range(self._nc) if self._mask[i] == 0]
            self.usedLbl.setText(
                f'Used: {u}/{self._nc}' +
                (f'  Excl: {",".join(excl)}' if excl else ''))
            self._paint_mv()
            self._paint_sc()
            self.maskChanged.emit()

    # ── resize ───────────────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._paint_mv()
        if self._vt is not None and self._all_pts:
            self._paint_sc()


# ═══════════════════════════════════════════════════════════
#  CalcT0Page  — 5 independent MvCanvas panels
#    Blank tab:  [Ar36][Ar37][Ar38][Ar39][Ar40]
#    Signal tab: same + step selector + blank ref row
# ═══════════════════════════════════════════════════════════
class _DummyLbl:
    """Placeholder label - chips displayed in nav bar instead."""
    def __init__(self): self._txt = ''
    def setText(self, t): self._txt = t
    def text(self): return self._txt


class CalcT0Page(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._bvt    = None
        self._binfo  = None
        self._bmask  = None
        self._svt    = {}
        self._sinfo  = {}
        self._smask  = {}
        self._bT0    = np.zeros(5)
        self._bSIG   = np.zeros(5)
        self._cur    = None
        self._fit    = 0
        self._manual = False
        self._nc     = 10
        self._build()

    # ── UI ───────────────────────────────────────────────────
    def _build(self):
        main_vl = QtWidgets.QVBoxLayout(self)
        main_vl.setContentsMargins(0, 0, 0, 0); main_vl.setSpacing(0)

        # v3.8.21: "Calculate T₀" page header removed per user request — the
        # pipeline strip in top_bar already shows which page is active, so the
        # in-page title is redundant and wasted ~50 px of vertical room. Charts
        # below now fill the freed space automatically (QVBoxLayout reflow).
        # _hdr_subtitle kept as a hidden placeholder so any code that still
        # writes to it doesn't AttributeError.
        self._hdr_subtitle = QtWidgets.QLabel('')
        self._hdr_subtitle.hide()

        # ═══ Main content ═══
        hl = QtWidgets.QHBoxLayout()
        hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(0)

        # v3.8.12: Sidebar copied 1:1 from DiagramPlots_SH layout —
        # buttons setFixedSize(91, 51), spacing=0 so they touch like Qt
        # Designer's absolute setGeometry produced. Two ComboBox dropdowns
        # at top (parity with DiagramPlots_SH's color + marker pickers),
        # here repurposed as σ method + fit type. No setStyleSheet anywhere
        # → buttons render with OS-native Qt look.
        sb  = QtWidgets.QWidget(); sb.setFixedWidth(95)
        sbl = QtWidgets.QVBoxLayout(sb)
        sbl.setContentsMargins(2, 4, 2, 4); sbl.setSpacing(0)

        def sb_btn(txt, col='default'):
            b = QtWidgets.QPushButton(txt)
            b.setFixedSize(91, 51)
            return b

        # Dropdown 1: σ method (slot ≈ DiagramPlots_SH 'red' color picker)
        self.sigmaCombo = QtWidgets.QComboBox()
        self.sigmaCombo.addItem('Standard SE', 'standard')
        self.sigmaCombo.addItem('Calc T₀',     'calc_t0')
        self.sigmaCombo.setToolTip(
            'Standard SE: σ via pcov[-1,-1] (Li et al. 2019 Eq.1).\n'
            'Calc T₀: σ via std(|residuals|)/√n (matches CalcT0Page).')
        idx = 0 if SIGMA_METHOD == 'standard' else 1
        self.sigmaCombo.setCurrentIndex(idx)
        self.sigmaCombo.currentIndexChanged.connect(self._on_sigma_method_changed)
        self.sigmaCombo.setFixedSize(91, 30)
        sbl.addWidget(self.sigmaCombo)

        # Dropdown 2: fit type (slot ≈ DiagramPlots_SH 'o' marker picker)
        # Replaces the separate Linear / Average buttons.
        self.fitCombo = QtWidgets.QComboBox()
        self.fitCombo.addItem('Linear',  0)
        self.fitCombo.addItem('Average', 1)
        self.fitCombo.setCurrentIndex(0)
        self.fitCombo.currentIndexChanged.connect(
            lambda i: self._set_fit(self.fitCombo.itemData(i)))
        self.fitCombo.setFixedSize(91, 30)
        sbl.addWidget(self.fitCombo)

        # Buttons — 91×51, default Qt look, no stylesheets.
        # v3.8.18: Bi-Dir All button removed entirely (v3.8.10 panel cleanup
        # was meant to drop it from the UI, but the sidebar button slipped through).
        # Method `_auto_best_all` retained for possible future re-introduction.
        self.returnBtn  = sb_btn('Return')
        self.saveBtn    = sb_btn('Save T₀')
        self.btnLdBlank = sb_btn('Load Blank')
        self.btnLdSig   = sb_btn('Load Sample')
        self.btnAB      = sb_btn('Auto Blank')
        self.btnAS      = sb_btn('Auto Signal')
        self.btnM       = sb_btn('Manual')
        # Back-compat hidden widget so any lingering reference doesn't AttributeError
        self.btnABest = QtWidgets.QPushButton(); self.btnABest.hide()
        # Back-compat aliases so existing code referring to btnL/btnA still works
        # (they no longer have a UI surface; fit type is now via fitCombo).
        self.btnL = QtWidgets.QPushButton(); self.btnL.hide()
        self.btnA = QtWidgets.QPushButton(); self.btnA.hide()

        for b in (self.returnBtn, self.saveBtn, self.btnLdBlank, self.btnLdSig,
                  self.btnAB, self.btnAS, self.btnM):
            sbl.addWidget(b)

        # v3.8.18: Δt label moved out of sidebar into the top nav bar (chip
        # right of 'Current step'). Local widget kept as a hidden back-compat
        # placeholder so any code that still calls deltaTLbl.setText() works,
        # but it has no UI surface. Real display goes through _chips['Δt'].
        self.deltaTLbl = QtWidgets.QLabel(f'Δt: {DELTA_T_DAYS:.0f} d')
        self.deltaTLbl.hide()

        sbl.addStretch()

        self.statusLbl = QtWidgets.QLabel('Ready')
        self.statusLbl.setStyleSheet(
            f'font-size:8px;color:{TXT3};font-family:Courier New;padding:4px;')
        self.statusLbl.setWordWrap(True)
        sbl.addWidget(self.statusLbl)
        hl.addWidget(sb)

        # Main: QScrollArea for vertical scrolling
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        mn  = QtWidgets.QWidget()
        left_vb = QtWidgets.QVBoxLayout(mn)
        left_vb.setContentsMargins(8, 4, 6, 6); left_vb.setSpacing(4)
        ml = left_vb  # alias for compatibility

        # v3.8.10: Blank / Temperature step switcher — QTabBar (Chrome-style)
        # Replaces previous colored-button row. Tab 0 = Blank; tabs 1..N built by
        # _rebuild_step_btns() when signal files are loaded.
        self._step_tabs = QtWidgets.QTabBar()
        self._step_tabs.setShape(QtWidgets.QTabBar.RoundedNorth)
        self._step_tabs.setDocumentMode(True)
        self._step_tabs.setExpanding(False)
        self._step_tabs.setUsesScrollButtons(True)
        self._step_tabs.setDrawBase(False)
        self._step_tabs.setStyleSheet(
            'QTabBar::tab{'
            f'background:#eeede8;border:1px solid {BRD};border-bottom:none;'
            'border-top-left-radius:6px;border-top-right-radius:6px;'
            'padding:6px 14px;margin-right:2px;font-size:11px;color:#444;'
            'min-width:50px;}'
            'QTabBar::tab:selected{'
            'background:white;color:#1a5fb4;font-weight:bold;}'
            'QTabBar::tab:hover:!selected{background:#f5f4f0;}'
        )
        # _tab_step_map[index] = step name ('__BLANK__' or 'Temperature 1100°C')
        self._tab_step_map = {0: '__BLANK__'}
        self._step_tabs.addTab('Blank')
        self._step_tabs.currentChanged.connect(self._on_tab_changed)
        # Suppress recursion when _sel_step calls back into setCurrentIndex
        self._tab_sync_lock = False

        tab_wrap = QtWidgets.QWidget()
        tab_l = QtWidgets.QHBoxLayout(tab_wrap)
        tab_l.setContentsMargins(8, 4, 0, 0); tab_l.setSpacing(0)
        tab_l.addWidget(self._step_tabs)
        tab_l.addStretch()
        tab_wrap.setMaximumHeight(36)
        left_vb.addWidget(tab_wrap)

        # ── Single canvas area (replaces Blank/Signal tabs) ──
        canvas_w = QtWidgets.QWidget()
        cvl = QtWidgets.QVBoxLayout(canvas_w)
        cvl.setContentsMargins(4, 4, 4, 4); cvl.setSpacing(3)
        
        self._lbl_title = QtWidgets.QLabel('mV vs time (sec)')
        self._lbl_title.setStyleSheet(
            f'font-size:15px;font-weight:bold;color:{TXT2};'
            f'border-bottom:1px solid {BRD};padding-bottom:2px;')
        cvl.addWidget(self._lbl_title)
        
        # 5 canvases in a horizontal row (shared by Blank and Signal).
        # v3.8.11: removed horizontal scroll wrapper. Canvases now share available
        # horizontal space evenly via stretch=1, letting the 5th (⁴⁰Ar) stay
        # visible on full-screen without needing to scroll sideways.
        crow = QtWidgets.QHBoxLayout(); crow.setSpacing(2)
        self._cv = [MvCanvas(i) for i in range(5)]
        for cv in self._cv:
            cv.maskChanged.connect(self._mask_changed)
            crow.addWidget(cv, 1)
        crow_w = QtWidgets.QWidget(); crow_w.setLayout(crow)
        crow_w.setMinimumHeight(620)
        cvl.addWidget(crow_w, 1)
        # v3.8.24: keep handle so _save can grab().save() this for PNG export
        # (5 mV row + 5 scatter row combined as user sees them)
        self._crow_w = crow_w
        
        # ── Shared legend for Row 1 (mV vs time) ────────────────
        mv_legend = QtWidgets.QLabel(
            '<span style="color:grey;">- - -</span> blank T₀ &nbsp;&nbsp;'
            '<span style="color:#4c72b0;">———</span> raw data &nbsp;&nbsp;'
            '<span style="color:#e67e00;">- - -</span> fitted line &nbsp;&nbsp;'
            '<span style="color:#1c7a3a;">- - -</span> fitted line (excl.)')
        mv_legend.setAlignment(QtCore.Qt.AlignCenter)
        mv_legend.setStyleSheet(f'font-size:12px;color:{TXT};background:transparent;padding:2px;')
        cvl.addWidget(mv_legend)
        
        # ── Shared legend for Row 2 (T₀ vs 2σ scatter) ──────────
        sc_legend = QtWidgets.QLabel(
            '<span style="color:#1f77b4;">●</span> n=10 &nbsp;'
            '<span style="color:#2ca02c;">●</span> n=9 &nbsp;'
            '<span style="color:#ff7f0e;">●</span> n=8 &nbsp;'
            '<span style="color:#d62728;">●</span> n=7 &nbsp;'
            '<span style="color:#9467bd;">●</span> n=6 &nbsp;'
            '<span style="color:#8c564b;">●</span> n=5 &nbsp;'
            '<span style="color:#e377c2;">●</span> n=4 &nbsp;&nbsp;'
            '<span style="color:#9b59b6;">◆</span> 36air min &nbsp;'
            '<span style="color:#e67e00;">▲</span> current')
        sc_legend.setAlignment(QtCore.Qt.AlignCenter)
        sc_legend.setStyleSheet(f'font-size:12px;color:{TXT};background:transparent;padding:2px;')
        cvl.addWidget(sc_legend)
        
        left_vb.addWidget(canvas_w, 1)

        # ── Degassing Pattern Overview (single panel) ──
        # v3.8.10: removed Panel ⑥ MC, ⑦ Bi-Dir, ⑧ Final Rec — only ⑤ kept.
        analysis_hdr_row = QtWidgets.QHBoxLayout()
        analysis_hdr = QtWidgets.QLabel(
            '<b style="font-size:15px;">Degassing Pattern Overview</b>')
        analysis_hdr.setStyleSheet(
            f'color:{TXT2};border-top:1px solid {BRD};padding-top:3px;margin-bottom:2px;')
        analysis_hdr_row.addWidget(analysis_hdr, 1)
        left_vb.addLayout(analysis_hdr_row)

        # Container for 2×2 grid
        guide_container = QtWidgets.QWidget()
        guide_vl = QtWidgets.QVBoxLayout(guide_container)
        guide_vl.setContentsMargins(0,0,0,0)
        guide_vl.setSpacing(6)

        # ── Degassing Pattern Overview (single panel; ⑥⑦⑧ removed in v3.8.10) ──
        # v3.8.12: Degassing canvas at fixed 4:3 ratio (~480×280) and centered
        # horizontally — the previous full-width version was elongated and
        # cramped the aspect ratio.
        p5 = QtWidgets.QWidget()
        p5l = QtWidgets.QVBoxLayout(p5); p5l.setContentsMargins(0,0,0,0); p5l.setSpacing(1)
        self._degas_fig = _mfig.Figure(facecolor='white')
        self._degas_ax1 = self._degas_fig.add_subplot(211)
        self._degas_ax2 = self._degas_fig.add_subplot(212)
        QtWidgets.QApplication.processEvents()
        self.cv_degas   = _FigCanvas(self._degas_fig)
        self.cv_degas.setFixedSize(480, 280)
        p5l.addWidget(self.cv_degas)

        # v3.8.23: yield panel — side-by-side with degassing pattern.
        # x: cumulative ³⁹Ar(K) %  |  y: %⁴⁰Ar(r) and %³⁹Ar(K) of Σ(³⁶+³⁷+³⁸+³⁹+⁴⁰)
        # Lets the user see, while still on Calculate T₀, which temperature steps
        # contribute most ⁴⁰Ar(r) and how clean each release is — before pipeline
        # ever computes the age.
        p5_yield = QtWidgets.QWidget()
        p5yl = QtWidgets.QVBoxLayout(p5_yield); p5yl.setContentsMargins(0,0,0,0); p5yl.setSpacing(1)
        self._yield_fig = _mfig.Figure(facecolor='white')
        self._yield_ax  = self._yield_fig.add_subplot(111)
        self.cv_yield   = _FigCanvas(self._yield_fig)
        self.cv_yield.setFixedSize(480, 280)
        p5yl.addWidget(self.cv_yield)

        degas_center = QtWidgets.QHBoxLayout()
        degas_center.addStretch()
        degas_center.addWidget(p5)
        degas_center.addSpacing(10)
        degas_center.addWidget(p5_yield)
        degas_center.addStretch()
        guide_vl.addLayout(degas_center)

        guide_container.setFixedHeight(300)
        left_vb.addWidget(guide_container)
        
        # Hidden tables used by _refresh_sum / _refresh_prev (no UI surface)
        self.sumTbl = QtWidgets.QTableWidget(0, 8); self.sumTbl.hide()
        self.prevTbl = QtWidgets.QTableWidget(0, 10); self.prevTbl.hide()

        # Footer (移除 nextBtn，已在頂部)
        ftr = QtWidgets.QHBoxLayout()
        self.footMsg = QtWidgets.QLabel('Load blank and sample .dat files')
        self.footMsg.setStyleSheet(f'font-size:9px;color:{TXT3};')
        ftr.addWidget(self.footMsg); ftr.addStretch()
        left_vb.addLayout(ftr)

        # _chips: internal dict for status updates (not displayed in this widget).
        # v3.8.18: added 'Δt' so _auto_update_delta_t can write to it even before
        # AutoPipelineWindow's real chip dict is wired in via t0Page._chips=...
        self._chips = {'Mode': _DummyLbl(), 'Fit': _DummyLbl(),
                       'Blank file': _DummyLbl(), 'Signal': _DummyLbl(),
                       'Current step': _DummyLbl(), 'Δt': _DummyLbl()}
        self._chips['Mode'].setText('Auto')
        self._chips['Fit'].setText('Linear')
        # nextBtn will be set by AutoPipelineWindow
        # v3.8.11: minimum height driven by inner layout (crow_w 620 + guide
        # 280 + chrome ≈ 950). Don't hardcode 900 here — that was forcing the
        # outer QScrollArea to ALWAYS show vertical scroll even on tall screens.
        # Defer scroll.setWidget to avoid FigCanvas sizeHint deadlock on Py3.13
        self._deferred_mn = mn
        self._deferred_scroll = scroll
        hl.addWidget(scroll, 1)
        
        # Add main content to vertical layout (below header)
        main_content_w = QtWidgets.QWidget()
        main_content_w.setLayout(hl)
        main_vl.addWidget(main_content_w, 1)

        # Connections
        self.btnL.clicked.connect(lambda: self._set_fit(0))
        self.btnA.clicked.connect(lambda: self._set_fit(1))
        self.btnLdBlank.clicked.connect(self._load_blank_dialog)
        self.btnLdSig.clicked.connect(self._load_signal_dialog)
        self.btnAB.clicked.connect(self._auto_blank)
        self.btnAS.clicked.connect(self._auto_signal)
        # v3.8.18: btnABest hidden (not added to sidebar); no click wire needed.
        self.btnM.clicked.connect(self._toggle_manual)
        self.saveBtn.clicked.connect(self._save)
        # Deferred: set scroll content after event loop starts (avoids Py3.13 hang)
        QtCore.QTimer.singleShot(0, self._deferred_scroll_setup)

    def _deferred_scroll_setup(self):
        """Set scroll widget content after event loop is running."""
        if hasattr(self, '_deferred_mn') and hasattr(self, '_deferred_scroll'):
            self._deferred_scroll.setWidget(self._deferred_mn)
            del self._deferred_mn
            del self._deferred_scroll

    # ── File dialogs ─────────────────────────────────────────
    def _load_blank_dialog(self):
        fp, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, 'Select blank .dat', '', 'DAT files (*.dat);;All files (*)')
        if fp:
            self.load_blank(fp, self._nc)

    def _load_signal_dialog(self):
        import re
        fps, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, 'Select sample .dat files', '',
            'DAT files (*.dat);;All files (*)')
        if fps:
            fps.sort(
                key=lambda p: int(re.search(r'(\d+)', os.path.basename(p)).group(1))
                if re.search(r'(\d+)', os.path.basename(p)) else 0)
            self.load_signal(fps, self._nc)

    # ── Data loading ─────────────────────────────────────────
    def load_blank(self, fp, nc=10):
        self._nc = nc
        self._bvt, self._binfo = parse_dat(fp, nc)
        self._bmask = np.ones((5, nc))
        self._chips['Blank file'].setText(os.path.basename(fp))
        self._cur = '__BLANK__'
        # v3.8.26: drop stale prefetch cache (id(vt) collisions possible after
        # new parse_dat) so PrefetchWorker re-fills with fresh arrays
        self._prefetch_cache = {}
        self._refresh_blank()
        self._update_step_colors()
        # Kick off background combo-fit pre-compute (blank only here; full
        # set including signal steps re-runs from load_signal)
        self._start_prefetch()

    def load_signal(self, fps, nc=10):
        self._nc = nc
        self._svt.clear(); self._sinfo.clear(); self._smask.clear()
        self._step_dates = {}
        for fp in fps:
            nm = os.path.splitext(os.path.basename(fp))[0]
            v, i = parse_dat(fp, nc)
            self._svt[nm] = v; self._sinfo[nm] = i
            self._smask[nm] = np.ones((5, nc))
            d = _extract_dat_date(fp)
            if d is not None:
                self._step_dates[nm] = d
        self._chips['Signal'].setText(f'{len(fps)} steps')
        self._rebuild_step_btns()
        # v3.8.26: invalidate stale prefetch cache before restart so a previous
        # dataset's id() entries don't collide with the new one
        self._prefetch_cache = {}
        if self._svt:
            self._cur = list(self._svt.keys())[0]
            self._refresh_signal()
        # auto Δt from OGD (param) + SPD (first sample's Project# date)
        self._auto_update_delta_t()
        self.nextBtn.setEnabled(True)
        self.footMsg.setText('Files loaded')
        # v3.8.26: kick off background prefetch for blank + all signal steps
        self._start_prefetch()
        # v3.8.20: refresh pipeline strip visuals — circle 0 now ✓ done since
        # blank + signal are loaded, Next button text/enabled state updated.
        try:
            parent = self.parent()
            while parent is not None and not hasattr(parent, '_refresh_pipe_visuals'):
                parent = parent.parent()
            if parent is not None:
                parent._refresh_pipe_visuals(parent.stack.currentIndex())
        except Exception:
            pass

    def _auto_update_delta_t(self):
        """Read OGD from AutoPipelineWindow's _params; combine with first sample
        date → Δt. Update the sidebar label and DELTA_T_DAYS global."""
        global DELTA_T_DAYS
        # v3.8.11 fix: AutoPipelineWindow stores params as self._params (underscore)
        # via set_context(), but this function used to look for `parent.params`
        # without underscore — search always failed, label stuck at "0 d".
        try:
            parent = self.parent()
            while parent is not None and not hasattr(parent, '_params'):
                parent = parent.parent()
            if parent is None or getattr(parent, '_params', None) is None:
                return
            ogd = parent._params[parent._pnames.index('OG Date')]
        except (AttributeError, ValueError, IndexError):
            return
        if not self._step_dates:
            return
        spd = list(self._step_dates.values())[0]
        dt = compute_delta_t_days(ogd, spd)
        DELTA_T_DAYS = float(dt)
        if hasattr(self, 'deltaTLbl'):
            self.deltaTLbl.setText(f'Δt: {dt} d')
            self.deltaTLbl.setToolTip(
                f'OGD: {ogd}\nSPD: {spd}\nΔt = SPD − OGD = {dt} days')
        # v3.8.18: also push to top nav bar chip (Δt sits right of Current step).
        if 'Δt' in getattr(self, '_chips', {}):
            self._chips['Δt'].setText(f'{dt} d')
            # Tooltip lives on the chip's container widget which we set in
            # AutoPipelineWindow._build, so set on the QLabel itself for safety.
            self._chips['Δt'].setToolTip(
                f'OGD: {ogd}\nSPD: {spd}\nΔt = SPD − OGD = {dt} days')
        if hasattr(parent, 'statusBar'):
            try:
                parent.statusBar().showMessage(
                    f'Auto Δt = {dt} d  (OGD {ogd} → SPD {spd})', 5000)
            except Exception:
                pass

    # ── Step buttons ─────────────────────────────────────────
    def _rebuild_step_btns(self):
        # v3.8.10: rebuild QTabBar tabs (Blank stays at index 0, signal steps follow)
        self._tab_sync_lock = True
        while self._step_tabs.count() > 1:
            self._step_tabs.removeTab(1)
        self._tab_step_map = {0: '__BLANK__'}
        for nm in self._svt:
            lbl = nm.replace('Temperature ', '').replace('°C', '°').strip()
            idx = self._step_tabs.addTab(lbl)
            self._tab_step_map[idx] = nm
        self._tab_sync_lock = False
        self._update_step_colors()

    def _on_tab_changed(self, idx):
        if self._tab_sync_lock: return
        nm = self._tab_step_map.get(idx)
        if nm is not None:
            self._sel_step(nm)

    def _sync_tab_to_step(self, nm):
        """Keep the QTabBar selection in sync when _sel_step is called directly."""
        target_idx = None
        for idx, sn in self._tab_step_map.items():
            if sn == nm:
                target_idx = idx; break
        if target_idx is None or target_idx == self._step_tabs.currentIndex():
            return
        self._tab_sync_lock = True
        self._step_tabs.setCurrentIndex(target_idx)
        self._tab_sync_lock = False

    def _sel_step(self, nm):
        self._cur = nm
        self._sync_tab_to_step(nm)
        if nm == '__BLANK__':
            self._chips['Current step'].setText('Blank')
            self._lbl_title.setText('Blank — mV vs time (sec)')
            self._refresh_blank()
        else:
            self._chips['Current step'].setText(nm)
            lbl = nm.replace('Temperature ', '').replace('°C', '°').strip()
            self._lbl_title.setText(f'{lbl} — mV vs time (sec)')
            self._refresh_signal()
        self._update_step_colors()
        self._refresh_guide()

    def _update_step_colors(self):
        """v3.8.10: tabs use QTabBar's built-in selected-tab highlight.
        Only flag invalid signal steps with an amber text color."""
        for idx, nm in self._tab_step_map.items():
            if nm == '__BLANK__':
                self._step_tabs.setTabTextColor(idx, QtGui.QColor('#1a5fb4'))
                continue
            ok = self._step_ok(nm)
            if not ok:
                self._step_tabs.setTabTextColor(idx, QtGui.QColor('#8a5a00'))
            else:
                self._step_tabs.setTabTextColor(idx, QtGui.QColor('#222222'))

    def _step_ok(self, nm):
        if nm not in self._smask or self._bvt is None: return True
        f = Utilities.fit_func_list[self._fit]
        for ai in range(5):
            t0, _, _, _ = _fit_one(f, self._svt[nm][ai], self._smask[nm][ai])
            if t0 <= self._bT0[ai]: return False
        return True

    # ── Refresh canvases ─────────────────────────────────────
    def _calc_blank_t0(self):
        if self._bvt is None: return
        f = Utilities.fit_func_list[self._fit]
        for ai in range(5):
            t0, sig, _, _ = _fit_one(f, self._bvt[ai], self._bmask[ai])
            self._bT0[ai] = t0; self._bSIG[ai] = sig

    def _refresh_blank(self):
        if self._bvt is None: return
        self._calc_blank_t0()
        cache = getattr(self, '_prefetch_cache', {})
        for ai, cv in enumerate(self._cv):
            # v3.8.26: hand over prefetched combo fits if background worker
            # already finished this isotope — skips ~4 s enumerate per cv.
            key = (id(self._bvt[ai]), self._fit, self._nc)
            cv.load(self._bvt[ai], self._bmask[ai],
                    bt=None, fit=self._fit, manual=self._manual,
                    prefetched_fits=cache.get(key))
        self._broadcast_t0_net_37()
        self._refresh_sum()

    def _refresh_signal(self):
        if not self._svt or self._cur is None or self._cur == '__BLANK__': return
        vt   = self._svt[self._cur]
        mask = self._smask[self._cur]
        cache = getattr(self, '_prefetch_cache', {})
        for ai, cv in enumerate(self._cv):
            # v3.8.26: ditto — try prefetch cache first
            key = (id(vt[ai]), self._fit, self._nc)
            cv.load(vt[ai], mask[ai],
                    bt=self._bT0[ai], fit=self._fit, manual=self._manual,
                    prefetched_fits=cache.get(key))
        self._broadcast_t0_net_37()
        self._refresh_sum()

    # ── Background prefetch (v3.8.26) ────────────────────────
    def _start_prefetch(self):
        """Spawn PrefetchWorker that pre-computes combo enumeration for every
        (step, isotope) pair the user hasn't visited yet. Pulls step-switch
        latency from ~4 s/isotope down to <50 ms once a step is in the cache.

        Re-loading new files cancels any in-flight worker first."""
        # Cancel + wait for previous worker (drop its results — cache was
        # already cleared by the caller)
        old = getattr(self, '_prefetch_worker', None)
        if old is not None:
            try:
                old.abort()
                old.wait(100)
            except Exception: pass
            self._prefetch_worker = None

        if not hasattr(self, '_prefetch_cache'):
            self._prefetch_cache = {}

        tasks = []
        # Blank first — user lands on Blank tab, then moves to signal
        if self._bvt is not None:
            for ai in range(5):
                key = (id(self._bvt[ai]), self._fit, self._nc)
                if key not in self._prefetch_cache:
                    tasks.append((key, self._bvt[ai]))
        for nm, vt in self._svt.items():
            for ai in range(5):
                key = (id(vt[ai]), self._fit, self._nc)
                if key not in self._prefetch_cache:
                    tasks.append((key, vt[ai]))

        if not tasks: return

        self._prefetch_worker = PrefetchWorker(tasks, self._fit, self._nc, self)
        self._prefetch_worker.sig_one_done.connect(self._on_prefetch_one)
        self._prefetch_worker.sig_progress.connect(self._on_prefetch_progress)
        self._prefetch_worker.sig_finished.connect(self._on_prefetch_finished)
        self._prefetch_worker.start()

    def _on_prefetch_one(self, key, fits):
        """Background worker finished one (step, isotope) — drop into cache."""
        if not hasattr(self, '_prefetch_cache'):
            self._prefetch_cache = {}
        self._prefetch_cache[key] = fits

    def _on_prefetch_progress(self, done, total):
        if hasattr(self, 'footMsg') and done < total:
            self.footMsg.setText(f'Pre-computing combos: {done}/{total}')

    def _on_prefetch_finished(self):
        if hasattr(self, 'footMsg'):
            self.footMsg.setText('✓ Pre-compute done — step switch is now instant')
        self._prefetch_worker = None

    def _mask_changed(self):
        # Sync canvas masks back to _bmask / _smask before recalculating
        if self._cur == '__BLANK__' and self._bvt is not None:
            for ai, cv in enumerate(self._cv):
                if cv._mask is not None:
                    self._bmask[ai] = cv._mask.copy()
        elif self._cur and self._cur in self._smask:
            for ai, cv in enumerate(self._cv):
                if cv._mask is not None:
                    self._smask[self._cur][ai] = cv._mask.copy()
        self._calc_blank_t0()
        self._broadcast_t0_net_37()
        # Always do fast summary update
        self._refresh_sum_only()
        self._update_step_colors()
        # Auto mode: debounced guide (Degassing) refresh after 300ms idle.
        # Manual mode: skip (Degassing pattern uses cache so refresh is cheap on next step click).
        if not self._manual:
            self._schedule_guide_refresh()

    def _schedule_guide_refresh(self):
        """Debounced refresh: triggers guide update only after user pauses clicking."""
        if not hasattr(self, '_guide_timer'):
            self._guide_timer = QtCore.QTimer(self)
            self._guide_timer.setSingleShot(True)
            self._guide_timer.timeout.connect(self._do_guide_refresh)
        self._guide_timer.start(300)

    def _do_guide_refresh(self):
        """Actually refresh the guide panels."""
        self._refresh_prev()
        self._refresh_guide()
    
    def _refresh_sum_only(self):
        """Fast version: only update summary table, skip heavy guide panels.
        Called on every cycle toggle.
        """
        rows = []
        if self._bvt is not None:
            r = ['Blank']
            for ai in range(5): r.append(f'{self._bT0[ai]:.3e}')
            r += ['—', '—']; rows.append(r)
        f = Utilities.fit_func_list[self._fit]
        for nm, vt in self._svt.items():
            mask = self._smask[nm]; r = [nm]; ok = True
            for ai in range(5):
                t0, _, _, _ = _fit_one(f, vt[ai], mask[ai])
                r.append(f'{t0:.3e}')
                if t0 <= self._bT0[ai]: ok = False
            r += ['✓' if ok else '✗', 'ok' if ok else 'warn']
            rows.append(r)
        self.sumTbl.setRowCount(len(rows))
        for ri, rv in enumerate(rows):
            for ci, val in enumerate(rv):
                item = QtWidgets.QTableWidgetItem(val)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if val in ('✗','warn'):
                    item.setForeground(QtGui.QColor('#b41a1a'))
                elif val in ('✓','ok'):
                    item.setForeground(QtGui.QColor('#1c7a3a'))
                self.sumTbl.setItem(ri, ci, item)

    def _broadcast_t0_net_37(self):
        """Compute T0_net[37] = T0_sig[37] - T0_blank[37] and
        push to all Ar36 canvases (blank and signal)."""
        f = Utilities.fit_func_list[self._fit]
        # blank Ar37
        T0b_37 = self._bT0[1] if self._bvt is not None else 0.0
        # signal Ar37 (current step)
        T0s_37 = 0.0
        if self._cur and self._cur in self._svt:
            t0,_,_,_ = _fit_one(f, self._svt[self._cur][1],
                                  self._smask[self._cur][1])
            T0s_37 = t0
        t0_net_37 = T0s_37 - T0b_37
        # push to Ar36 canvas (ai=0)
        for cv in self._cv:
            if cv.ai == 0:
                cv.set_sibling_t0_net_37(t0_net_37)

    # ── Controls ─────────────────────────────────────────────
    def _set_fit(self, ft):
        self._fit = ft
        self.btnL.setStyleSheet(
            _btn_style(BLUE_BG,'#1a5fb4','#1a5fb4') if ft==0
            else _btn_style(PNL, TXT, BRD))
        self.btnA.setStyleSheet(
            _btn_style(BLUE_BG,'#1a5fb4','#1a5fb4') if ft==1
            else _btn_style(PNL, TXT, BRD))
        self._chips['Fit'].setText('Linear' if ft==0 else 'Average')
        self._refresh_blank(); self._refresh_signal()

    def _on_sigma_method_changed(self, idx):
        """User toggled σ method in sidebar. Re-fit blank + samples."""
        global SIGMA_METHOD
        new_m = self.sigmaCombo.itemData(idx) or 'standard'
        if new_m == SIGMA_METHOD:
            return
        SIGMA_METHOD = new_m
        self.statusLbl.setText(f'σ method = {SIGMA_METHOD}; re-fitting...')
        QtWidgets.QApplication.processEvents()
        try:
            self._refresh_blank()
            self._refresh_signal()
            self.statusLbl.setText(f'σ method = {SIGMA_METHOD}  ✓')
        except Exception as e:
            self.statusLbl.setText(f'σ refit error: {e}')

    def _on_delta_t_changed(self):
        """User edited Δt (days, irradiation→analysis). Re-run signal pass."""
        global DELTA_T_DAYS
        try:
            v = float(self.deltaTEdit.text().strip())
            if v < 0:
                v = 0.0
        except ValueError:
            self.deltaTEdit.setText(f'{DELTA_T_DAYS:.1f}')
            return
        if abs(v - DELTA_T_DAYS) < 1e-9:
            return
        DELTA_T_DAYS = v
        self.statusLbl.setText(f'Δt = {v:.2f} d; re-running signal pass...')
        QtWidgets.QApplication.processEvents()
        try:
            self._refresh_signal()
            self.statusLbl.setText(f'Δt = {v:.2f} d  ✓')
        except Exception as e:
            self.statusLbl.setText(f'Δt refit error: {e}')

    def _toggle_manual(self):
        self._manual = not self._manual
        col = AMB_BG if self._manual else PNL
        tc  = '#8a5a00' if self._manual else TXT
        bc  = '#8a5a00' if self._manual else BRD
        self.btnM.setStyleSheet(_btn_style(col, tc, bc))
        self._chips['Mode'].setText('Manual' if self._manual else 'Auto')
        for cv in self._cv:
            cv._manual = self._manual

    def _auto_blank(self):
        if self._bvt is None: return
        self.statusLbl.setText('Auto blank...')
        QtWidgets.QApplication.processEvents()
        result, self._bmask = Utilities.calculateT0(
            self._fit, self._bvt, np.ones((5, self._nc)), self._nc)
        self._bT0, self._bSIG = result[1], result[2]
        self._refresh_blank()
        self.statusLbl.setText('✓ Blank done')

    def _auto_signal(self):
        if not self._svt: return
        self._calc_blank_t0()
        for nm, vt in self._svt.items():
            self.statusLbl.setText(f'Auto {nm}...')
            QtWidgets.QApplication.processEvents()
            # calculateT0 auto-detects outliers and returns updated mask
            result, new_mask = Utilities.calculateT0(
                self._fit, vt, np.ones((5, self._nc)), self._nc)
            self._smask[nm] = new_mask   # save auto-detected mask per isotope
        if self._cur: self._refresh_signal()
        self.statusLbl.setText('✓ Signal done')
        self.nextBtn.setEnabled(True)

    def _auto_best_all(self):
        """One-click bi-directional strategy for ALL signal steps.
        
        Pipeline:
          1. Compute blank T0 (use current blank masks)
          2. For each signal step:
             a. Run blank-out pass: re-optimize blank + find best sample cycles
             b. Run signal-out pass: use current blank, find best sample cycles
             c. Check physics constraints for both
             d. Pick the pass with fewer violations (tiebreak: lower score)
             e. Apply masks to _smask[nm]
          3. Show summary of choices
        
        Uses score = (σ_a + σ_m) × (1 + α·w_n) + β·spread_penalty
          α = STRAT_ALPHA (0.3)
          β = STRAT_BETA (0.5)
        """
        if not self._svt: return
        if self._bvt is None:
            self.statusLbl.setText('⚠ Load blank first')
            return
        
        self._calc_blank_t0()
        f = Utilities.fit_func_list[self._fit]
        
        # Pre-compute blank sig_a, sig_m for physics constraint checks
        blank_sig_a = np.zeros(5)
        blank_sig_m = np.zeros(5)
        for bai in range(5):
            bmask = self._cv[bai]._mask if self._cv[bai]._mask is not None else np.ones(self._nc)
            _, sa, sm, _, _ = _fit_with_errors(f, self._bvt[bai], bmask)
            blank_sig_a[bai] = sa
            blank_sig_m[bai] = sm
        
        # Pre-compute blank-out pass ONCE (it's the same for all steps)
        self.statusLbl.setText('Bi-directional: computing blank-out reference...')
        QtWidgets.QApplication.processEvents()
        blank_results = _blank_out_pass(self._bvt, self._fit, self._nc)
        blank_t0_bo = np.array([b['t0'] if b else 0.0 for b in blank_results])
        
        # Summary tracker
        summary = []  # (nm, choice, n_list, ar40r_pct, violations_count)
        
        total = len(self._svt)
        for done, (nm, vt) in enumerate(self._svt.items(), 1):
            self.statusLbl.setText(f'Bi-directional [{done}/{total}] {nm}...')
            QtWidgets.QApplication.processEvents()
            
            # Run both passes
            so_results = _signal_out_pass(vt, self._bT0, self._fit, self._nc)
            bo_results = _signal_out_pass(vt, blank_t0_bo, self._fit, self._nc)
            
            def eval_pass(sample_recs, blank_t0):
                t0s = np.array([s['t0'] if s else 0 for s in sample_recs])
                sig_as = np.array([s['sig_a'] if s else 0 for s in sample_recs])
                sig_ms = np.array([s['sig_m'] if s else 0 for s in sample_recs])
                chk = _check_physics_constraints(t0s, sig_as, sig_ms,
                                                   blank_t0, blank_sig_a, blank_sig_m)
                total_score = sum(s['score'] if s else 1e30 for s in sample_recs)
                return chk, total_score
            
            so_chk, so_score = eval_pass(so_results, self._bT0)
            bo_chk, bo_score = eval_pass(bo_results, blank_t0_bo)
            
            so_viol = len(so_chk['violations'])
            bo_viol = len(bo_chk['violations'])
            
            # Pick: fewer violations wins; tiebreak by score
            if bo_viol < so_viol:
                choice = 'blank_out'
                chosen = bo_results
                chosen_chk = bo_chk
            elif so_viol < bo_viol:
                choice = 'signal_out'
                chosen = so_results
                chosen_chk = so_chk
            else:
                # Tiebreak: lower total score
                if bo_score <= so_score:
                    choice = 'blank_out'
                    chosen = bo_results
                    chosen_chk = bo_chk
                else:
                    choice = 'signal_out'
                    chosen = so_results
                    chosen_chk = so_chk
            
            # Apply masks
            new_mask = np.ones((5, self._nc))
            for ai in range(5):
                if chosen[ai] is not None:
                    new_mask[ai] = chosen[ai]['mask']
            self._smask[nm] = new_mask
            
            # Track summary
            n_list = [chosen[ai]['n'] if chosen[ai] else 0 for ai in range(5)]
            ar40r_pct = chosen_chk['values']['Ar40r_pct']
            summary.append((nm, choice, n_list, ar40r_pct, 
                           chosen_chk['violations']))
        
        # Refresh UI
        if self._cur: self._refresh_signal()
        self._refresh_sum()
        
        # Show summary dialog
        self._show_bidirectional_summary(summary)
        
        n_ok = sum(1 for s in summary if len(s[4]) == 0)
        n_warn = total - n_ok
        self.statusLbl.setText(f'✓ Bi-directional done: {n_ok}/{total} clean, {n_warn} with warnings')
        self.nextBtn.setEnabled(True)
    
    def _show_bidirectional_summary(self, summary):
        """Show a dialog with per-step results after bi-directional run."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Bi-directional Strategy Summary')
        dlg.setMinimumWidth(700)
        dlg.setMinimumHeight(400)
        
        vl = QtWidgets.QVBoxLayout(dlg)
        
        # Header
        hdr = QtWidgets.QLabel(
            '<b>Summary of bi-directional strategy</b><br>'
            '<span style="font-size:11px;color:#666;">'
            'Chose the pass with fewer constraint violations.<br>'
            'Warnings: Ar40_r ≤ 0, Ar36_air ≤ 0, etc.</span>'
        )
        vl.addWidget(hdr)
        
        # Table
        tbl = QtWidgets.QTableWidget(len(summary), 5)
        tbl.setHorizontalHeaderLabels(
            ['Step', 'Chosen', 'n [36,37,38,39,40]', '40Ar_r%', 'Warnings']
        )
        tbl.horizontalHeader().setStretchLastSection(True)
        
        for ri, (nm, choice, n_list, ar40r, violations) in enumerate(summary):
            step_lbl = nm.replace('Temperature ', '').replace('°C', '°').strip()
            tbl.setItem(ri, 0, QtWidgets.QTableWidgetItem(step_lbl))
            
            chi = QtWidgets.QTableWidgetItem(choice.replace('_', '-'))
            if choice == 'blank_out':
                chi.setForeground(QtGui.QColor('#1c7a3a'))
            else:
                chi.setForeground(QtGui.QColor('#9b59b6'))
            tbl.setItem(ri, 1, chi)
            
            tbl.setItem(ri, 2, QtWidgets.QTableWidgetItem(str(n_list)))
            
            pct = QtWidgets.QTableWidgetItem(f'{ar40r:.1f}%')
            if ar40r < 0:
                pct.setForeground(QtGui.QColor('#b41a1a'))
                pct.setBackground(QtGui.QColor('#fff0f0'))
            elif ar40r < 5:
                pct.setForeground(QtGui.QColor('#e67e00'))
            else:
                pct.setForeground(QtGui.QColor('#1c7a3a'))
            tbl.setItem(ri, 3, pct)
            
            # Show violations as text
            if violations:
                viol_txt = '; '.join(violations)
                w = QtWidgets.QTableWidgetItem(viol_txt)
                w.setForeground(QtGui.QColor('#b41a1a'))
                w.setToolTip(viol_txt)
            else:
                w = QtWidgets.QTableWidgetItem('✓ OK')
                w.setForeground(QtGui.QColor('#1c7a3a'))
            tbl.setItem(ri, 4, w)
        
        tbl.resizeColumnsToContents()
        vl.addWidget(tbl, 1)
        
        # Close button
        btn = QtWidgets.QPushButton('Close')
        btn.clicked.connect(dlg.accept)
        vl.addWidget(btn)
        
        dlg.exec_()

    # ── Summary table ─────────────────────────────────────────
    def _refresh_sum(self):
        rows = []
        if self._bvt is not None:
            r = ['Blank']
            for ai in range(5): r.append(f'{self._bT0[ai]:.3e}')
            r += ['—', '—']; rows.append(r)
        f = Utilities.fit_func_list[self._fit]
        for nm, vt in self._svt.items():
            mask = self._smask[nm]; r = [nm]; ok = True
            for ai in range(5):
                t0, _, _, _ = _fit_one(f, vt[ai], mask[ai])
                r.append(f'{t0:.3e}')
                if t0 <= self._bT0[ai]: ok = False
            r += ['✓' if ok else '✗', 'ok' if ok else 'warn']
            rows.append(r)
        self.sumTbl.setRowCount(len(rows))
        for ri, rv in enumerate(rows):
            for ci, val in enumerate(rv):
                item = QtWidgets.QTableWidgetItem(val)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if val in ('✗','warn'):
                    item.setForeground(QtGui.QColor('#b41a1a'))
                elif val in ('✓','ok'):
                    item.setForeground(QtGui.QColor('#1c7a3a'))
                self.sumTbl.setItem(ri, ci, item)
        # also update propagation preview and guide panels
        self._refresh_prev()
        self._refresh_guide()

    # ── Propagation preview ──────────────────────────────────
    def _refresh_prev(self):
        """Update propagation preview table for current signal step."""
        if not hasattr(self, 'prevTbl'): return
        rows = []
        f = Utilities.fit_func_list[self._fit]

        for nm, vt in self._svt.items():
            mask = self._smask[nm]
            # get T0 and σ_T0 for each isotope
            T0  = np.zeros(5); sT0 = np.zeros(5)
            for ai in range(5):
                t0v, sigv, _, _ = _fit_one(f, vt[ai], mask[ai])
                T0[ai] = t0v; sT0[ai] = sigv

            # blank T0 / sigma (use stored)
            bT0  = self._bT0.copy()  if self._bvt is not None else np.zeros(5)
            bsT0 = self._bSIG.copy() if self._bvt is not None else np.zeros(5)

            p = _propagate(T0, sT0, bT0, bsT0)

            def fmt(key):
                v, s, ok = p[key]
                if key in ('chi2_38','sig38_n','Ar40r_pct'):
                    return f'{v:.3f}', ok
                return f'{v:.3e}±{s:.1e}', ok

            row = [nm]
            for key in ['Ar36_air','Ar39_K','Ar40_air','Ar40_K',
                        'Ar40_r','Ar40r_pct','Ar38_cl','chi2_38','sig38_n']:
                txt, ok = fmt(key)
                row.append((txt, ok))
            rows.append(row)

        self.prevTbl.setRowCount(len(rows))
        for ri, rv in enumerate(rows):
            # col 0: step name
            item = QtWidgets.QTableWidgetItem(rv[0])
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.prevTbl.setItem(ri, 0, item)
            # cols 1-9: (text, ok)
            for ci, (txt, ok) in enumerate(rv[1:], 1):
                item = QtWidgets.QTableWidgetItem(str(txt))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                if not ok:
                    item.setForeground(QtGui.QColor('#b41a1a'))
                    item.setBackground(QtGui.QColor('#fff0f0'))
                else:
                    item.setForeground(QtGui.QColor('#1c7a3a'))
                self.prevTbl.setItem(ri, ci, item)

    # ── Guide panel (only ⑤ Degassing kept in v3.8.10) ─────────────────────
    def _refresh_guide(self):
        if not hasattr(self, 'cv_degas'): return
        self._paint_degas_pattern()
        if hasattr(self, 'cv_yield'):
            self._paint_yield_pattern()

    # New advanced analysis panels (⑤⑥⑦⑧)
    # ══════════════════════════════════════════════════════════
    
    def _paint_degas_pattern(self):
        """Panel ⑤: Degassing Pattern Overview (10-cycle for all temps).
        Upper subplot: T₀ signal (mV) vs temperature, 5 isotope lines + blank ref
        Lower subplot: CV (σ/T₀ %) vs temperature, 5 isotope lines
        
        CACHED: only recomputes when signal files change, not on every mask toggle.
        """
        ax1 = self._degas_ax1; ax1.clear()
        ax2 = self._degas_ax2; ax2.clear()
        ax1.set_facecolor('white'); ax2.set_facecolor('white')
        self._degas_fig.patch.set_facecolor('white')
        
        if not self._svt:
            ax1.text(0.5, 0.5, 'Load signal files first', 
                    transform=ax1.transAxes, ha='center', va='center',
                    fontsize=10, color='grey')
            self._degas_fig.tight_layout(pad=0.5)
            self.cv_degas.draw()
            return
        
        # Extract data for all temps (use n=10 full cycles)
        iso_names = ['³⁶Ar', '³⁷Ar', '³⁸Ar', '³⁹Ar', '⁴⁰Ar']
        iso_colors = ['#e67e00', '#9b59b6', '#1c7a3a', '#b41a1a', '#3584e4']
        
        # Check cache: degassing pattern only depends on _svt keys and fit type
        cache_key = (tuple(sorted(self._svt.keys())), self._fit, id(self._bvt))
        cached = getattr(self, '_degas_cache', None)
        
        if cached is not None and cached.get('key') == cache_key:
            # Use cached values
            temps = cached['temps']
            t0_all = cached['t0_all']
            cv_all = cached['cv_all']
        else:
            # Recompute and cache
            import re
            temp_map = {}
            for nm in self._svt.keys():
                m = re.search(r'(\d+)', nm)
                if m:
                    temp_map[int(m.group(1))] = nm
            
            temps = sorted(temp_map.keys())
            t0_all = [[] for _ in range(5)]
            cv_all = [[] for _ in range(5)]
            
            f = Utilities.fit_func_list[self._fit]
            
            for temp_val in temps:
                nm = temp_map[temp_val]
                vt = self._svt[nm]
                
                for ai in range(5):
                    mask_full = np.ones(self._nc)
                    t0, sig, r2, _ = _fit_one(f, vt[ai], mask_full)
                    t0_all[ai].append(t0)
                    
                    t0_threshold = abs(self._bT0[ai]) * 0.1
                    if abs(t0) > t0_threshold:
                        cv_all[ai].append(sig / abs(t0) * 100)
                    else:
                        cv_all[ai].append(np.nan)
            
            # Save to cache
            self._degas_cache = {
                'key': cache_key,
                'temps': temps,
                't0_all': t0_all,
                'cv_all': cv_all,
            }
        
        # Plot: Signal strength
        for ai in range(5):
            ax1.plot(temps, t0_all[ai], marker='o', markersize=3,
                    color=iso_colors[ai], label=iso_names[ai], linewidth=1.5, alpha=0.8)
        
        # Blank reference (horizontal line)
        if self._bT0[0] != 0:
            for ai in range(5):
                ax1.axhline(self._bT0[ai], color=iso_colors[ai], 
                           linestyle='--', linewidth=0.8, alpha=0.3)
        
        ax1.set_ylabel('T₀ signal (mV)', fontsize=8)
        ax1.tick_params(labelsize=7)
        ax1.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
        ax1.legend(fontsize=6, ncol=5, framealpha=0.8, loc='upper left')
        ax1.grid(True, alpha=0.2)
        
        # Plot: CV
        for ai in range(5):
            valid_temps = [t for t, cv in zip(temps, cv_all[ai]) if not np.isnan(cv)]
            valid_cvs = [cv for cv in cv_all[ai] if not np.isnan(cv)]
            if valid_temps:
                ax2.plot(valid_temps, valid_cvs, marker='s', markersize=3,
                        color=iso_colors[ai], label=iso_names[ai], linewidth=1.5, alpha=0.8)
        
        ax2.set_xlabel('Temperature (°C)', fontsize=8)
        ax2.set_ylabel('CV (σ/T₀ %)', fontsize=8)
        ax2.set_ylim(-2, 20)
        ax2.tick_params(labelsize=7)
        ax2.grid(True, alpha=0.2)
        
        # Mark current step with vertical line
        if self._cur and self._cur != '__BLANK__':
            import re
            m = re.search(r'(\d+)', self._cur)
            if m:
                cur_temp = int(m.group(1))
                ax1.axvline(cur_temp, color='#e67e00', linestyle=':', 
                           linewidth=1.2, alpha=0.7, zorder=0)
                ax2.axvline(cur_temp, color='#e67e00', linestyle=':', 
                           linewidth=1.2, alpha=0.7, zorder=0)
        
        self._degas_fig.tight_layout(pad=0.5)
        self.cv_degas.draw()

    def _paint_yield_pattern(self):
        """v3.8.23: Yield diagram next to degassing pattern.

        x-axis : cumulative ³⁹Ar(K) %, computed across all sample steps
                 sorted by temperature
        y-axis : %⁴⁰Ar(r) and %³⁹Ar(K), defined as
                   numerator / Σ(³⁶+³⁷+³⁸+³⁹+⁴⁰)_(measured, blank-corr) × 100

        Per-step ⁴⁰Ar(r) and ³⁹Ar(K) come from _propagate() using n=10 full
        mask — independent of any per-cycle manual mask, so this view is
        stable while user tweaks individual step masks.

        Cache: separate _yield_cache, same key shape as _degas_cache. Both
        invalidate when signal files change.
        """
        ax = self._yield_ax; ax.clear()
        ax.set_facecolor('white')
        self._yield_fig.patch.set_facecolor('white')

        if not self._svt:
            ax.text(0.5, 0.5, 'Load signal files first',
                    transform=ax.transAxes, ha='center', va='center',
                    fontsize=10, color='grey')
            self._yield_fig.tight_layout(pad=0.5)
            self.cv_yield.draw()
            return

        cache_key = (tuple(sorted(self._svt.keys())), self._fit, id(self._bvt))
        cached = getattr(self, '_yield_cache', None)

        if cached is not None and cached.get('key') == cache_key:
            temps      = cached['temps']
            ar40r_pct  = cached['ar40r_pct']
            ar39k_pct  = cached['ar39k_pct']
            cum_ar39k  = cached['cum_ar39k']
        else:
            import re
            temp_map = {}
            for nm in self._svt.keys():
                m = re.search(r'(\d+)', nm)
                if m:
                    temp_map[int(m.group(1))] = nm

            temps = sorted(temp_map.keys())
            ar39k_vals = []
            ar40r_pct  = []
            ar39k_pct  = []

            f = Utilities.fit_func_list[self._fit]

            for temp_val in temps:
                nm = temp_map[temp_val]
                vt = self._svt[nm]
                mask_full = np.ones(self._nc)

                T0  = np.zeros(5); sT0 = np.zeros(5)
                for ai in range(5):
                    t0, sig, _, _ = _fit_one(f, vt[ai], mask_full)
                    T0[ai]  = t0
                    sT0[ai] = sig

                res = _propagate(T0, sT0, self._bT0, self._bSIG)
                ar40_r = res['Ar40_r'][0]
                ar39_k = res['Ar39_K'][0]

                # blank-corrected sum of all 5 measured isotopes
                sum_meas = float(np.sum(T0 - self._bT0))
                if abs(sum_meas) > 1e-30:
                    ar40r_pct.append(ar40_r / sum_meas * 100)
                    ar39k_pct.append(ar39_k / sum_meas * 100)
                else:
                    ar40r_pct.append(np.nan)
                    ar39k_pct.append(np.nan)
                # clip negative for cumulative (rare: blank > signal)
                ar39k_vals.append(max(ar39_k, 0.0))

            tot = sum(ar39k_vals) if sum(ar39k_vals) > 0 else 1.0
            cum_ar39k = []
            running = 0.0
            for v in ar39k_vals:
                running += v
                cum_ar39k.append(running / tot * 100)

            self._yield_cache = {
                'key': cache_key,
                'temps': temps,
                'ar40r_pct': ar40r_pct,
                'ar39k_pct': ar39k_pct,
                'cum_ar39k': cum_ar39k,
            }

        # Plot — two lines
        ax.plot(cum_ar39k, ar40r_pct, marker='o', markersize=4,
                color='#3584e4', label='%⁴⁰Ar(r)', linewidth=1.5, alpha=0.9)
        ax.plot(cum_ar39k, ar39k_pct, marker='s', markersize=4,
                color='#b41a1a', label='%³⁹Ar(K)', linewidth=1.5, alpha=0.9)

        # Mark current step with orange dotted line (matches degas convention)
        if self._cur and self._cur != '__BLANK__':
            import re
            m = re.search(r'(\d+)', self._cur)
            if m:
                cur_temp = int(m.group(1))
                if cur_temp in temps:
                    idx = temps.index(cur_temp)
                    ax.axvline(cum_ar39k[idx], color='#e67e00', linestyle=':',
                               linewidth=1.2, alpha=0.7, zorder=0)

        ax.set_xlabel('cumulative ³⁹Ar(K) (%)', fontsize=8)
        ax.set_ylabel('% of Σ(³⁶+³⁷+³⁸+³⁹+⁴⁰)', fontsize=8)
        ax.set_xlim(-2, 102)
        ax.tick_params(labelsize=7)
        ax.legend(fontsize=7, framealpha=0.8, loc='best')
        ax.grid(True, alpha=0.2)

        self._yield_fig.tight_layout(pad=0.5)
        self.cv_yield.draw()


    # ── Save ─────────────────────────────────────────────────
    def _save(self):
        """v3.8.15: rewritten to mirror NTNU_DataReduction.CalcT0Page.LRP_save:
        - blank CSV → <work_dir>/Data/T0/PBs/<blank_name>.csv
        - sample step CSVs → <work_dir>/Data/T0/Sample/<sample_set>/<step>.csv
        - folder dialog lets user pick / create the sample-set folder
        - (PNG screenshots skipped for now; AutoPipeline canvases render to
          per-isotope QPixmaps not a single LR.png, so a direct shutil.copy
          doesn't apply here)."""
        if self._bvt is None:
            QtWidgets.QMessageBox.warning(self, 'Save T₀',
                'No blank loaded — load Blank + Sample first.')
            return

        work_dir = os.path.dirname(os.path.abspath(__file__))
        sample_root = os.path.join(work_dir, 'Data', 'T0', 'Sample')
        pbs_root    = os.path.join(work_dir, 'Data', 'T0', 'PBs')
        os.makedirs(sample_root, exist_ok=True)
        os.makedirs(pbs_root,    exist_ok=True)

        # Ask user for a target sample folder (created if missing). Default
        # location is Data/T0/Sample/ so the dialog opens at the right place.
        target = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose sample folder for T₀ output (under Data/T0/Sample/)',
            sample_root)
        if not target:
            return
        os.makedirs(target, exist_ok=True)

        written = []
        # Blank: write to Data/T0/PBs/<blank_name>.csv  AND  a copy inside the
        # sample folder for easy lookup with the matching sample step files.
        blank_name = self._chips['Blank file'].text().replace('.dat','') or 'blank'
        bp_pbs    = os.path.join(pbs_root, blank_name + '.csv')
        bp_sample = os.path.join(target,    blank_name + '.csv')
        write_t0_csv(bp_pbs,    self._binfo, self._bT0, self._bSIG, np.zeros(5))
        write_t0_csv(bp_sample, self._binfo, self._bT0, self._bSIG, np.zeros(5))
        written.extend([bp_pbs, bp_sample])

        # Each signal step: re-fit with its saved mask and write to target folder
        for sn, vt in self._svt.items():
            ff = Utilities.fit_func_list[self._fit]
            T0  = np.zeros(5); SIG = np.zeros(5); R = np.zeros(5)
            for ai in range(5):
                t0, sig, r2, _ = _fit_one(ff, vt[ai], self._smask[sn][ai])
                T0[ai] = t0; SIG[ai] = sig; R[ai] = r2
            sp = os.path.join(target, sn + '.csv')
            write_t0_csv(sp, self._sinfo[sn], T0, SIG, R)
            written.append(sp)

        # v3.8.24: PNG screenshot of current step's combined 5 mV + 5 scatter view.
        # Mirrors NTNU_DataReduction.LRP_save's LR.png export — but since
        # AutoPipeline renders to live Qt widgets (not a single LR.png on disk),
        # we use QWidget.grab() on the crow_w container that holds all 10 sub-plots.
        # Only the currently-shown step gets a PNG; switch step + Save again to
        # capture another step's view.
        # v3.8.25: PNG target moved from Data/T0/Sample/{folder}/ to
        # Figures/T0/Sample/{folder}/ so it matches the sub-program convention
        # (LRP_save line 3737: pn = work_dir + 'Figures/' + 'T0/' + T0type + '/').
        # CSVs stay under Data/ exactly as before — only PNGs split off.
        png_written = None
        if hasattr(self, '_crow_w') and self._crow_w is not None:
            step_label = (self._cur if self._cur and self._cur != '__BLANK__'
                          else 'blank' if self._cur == '__BLANK__'
                          else 'current')
            sample_folder_name = os.path.basename(target.rstrip(os.sep)) or 'unknown'
            fig_target = os.path.join(work_dir, 'Figures', 'T0', 'Sample',
                                      sample_folder_name)
            os.makedirs(fig_target, exist_ok=True)
            png_path = os.path.join(fig_target, step_label + '.png')
            try:
                self._crow_w.grab().save(png_path, 'PNG')
                written.append(png_path)
                png_written = png_path
            except Exception as e:
                # PNG failure should not block CSV save
                self.statusLbl.setText(f'PNG export failed: {e}')

        self.statusLbl.setText(f'✓ Saved {len(written)} files')
        png_msg = (f'\n  • PNG → {png_written}' if png_written else '')
        QtWidgets.QMessageBox.information(self, 'Save T₀ — Done',
            'Saved:\n'
            f'  • Blank → Data/T0/PBs/{blank_name}.csv\n'
            f'  • Blank + {len(self._svt)} step(s) → {target}'
            f'{png_msg}\n\n'
            f'Total: {len(written)} files')

    # ── Public getters ────────────────────────────────────────
    def get_blank_csv(self, out_dir):
        if self._bvt is None: return None
        os.makedirs(os.path.join(out_dir,'T0'), exist_ok=True)
        f = Utilities.fit_func_list[self._fit]
        T0=np.zeros(5); SIG=np.zeros(5); R=np.zeros(5)
        # v3.8.9 fix: only sync canvas mask → _bmask when canvas IS showing blank.
        # Previously this always took cv._mask, so if user navigated to a signal
        # step before Save, the blank got re-fit with that step's mask, writing
        # a wrong blank T0 → MassRatio Measurement (esp. 36Ar/37Ar) off by 25×/13×.
        if self._cur == '__BLANK__':
            for ai, cv in enumerate(self._cv):
                if cv._mask is not None:
                    self._bmask[ai] = cv._mask.copy()
        for ai in range(5):
            t0,sig,r2,_ = _fit_one(f, self._bvt[ai], self._bmask[ai])
            T0[ai]=t0; SIG[ai]=sig; R[ai]=r2
        nm = self._chips['Blank file'].text().replace('.dat','') or 'blank'
        p  = os.path.join(out_dir,'T0', nm+'.csv')
        write_t0_csv(p, self._binfo, T0, SIG, R)
        return p

    def get_signal_csvs(self, out_dir):
        os.makedirs(os.path.join(out_dir,'T0'), exist_ok=True)
        out = {}
        f   = Utilities.fit_func_list[self._fit]
        for nm, vt in self._svt.items():
            T0=np.zeros(5); SIG=np.zeros(5); R=np.zeros(5)
            mask_src = self._smask[nm]
            # If current step, use live canvas masks
            if nm == self._cur:
                for ai, cv in enumerate(self._cv):
                    m = cv._mask if cv._mask is not None else mask_src[ai]
                    t0,sig,r2,_ = _fit_one(f, vt[ai], m)
                    T0[ai]=t0; SIG[ai]=sig; R[ai]=r2
                    self._smask[nm][ai] = m.copy()
            else:
                for ai in range(5):
                    t0,sig,r2,_ = _fit_one(f, vt[ai], mask_src[ai])
                    T0[ai]=t0; SIG[ai]=sig; R[ai]=r2
            p = os.path.join(out_dir,'T0', nm+'.csv')
            write_t0_csv(p, self._sinfo[nm], T0, SIG, R)
            out[nm] = p
        return out


# ═══════════════════════════════════════════════════════════
#  MassRatioPage
# ═══════════════════════════════════════════════════════════
class MassRatioPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        vb=QtWidgets.QVBoxLayout(self); vb.setContentsMargins(10,8,8,8); vb.setSpacing(6)
        
        # Header with centered title and Save button
        hdr=QtWidgets.QHBoxLayout()
        hdr.addStretch()
        lbl=QtWidgets.QLabel('<b>Mass Ratio</b>')
        lbl.setStyleSheet(f'font-size:20px;color:{TXT};')
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        hdr.addWidget(lbl)
        hdr.addStretch()
        self.saveBtn=QtWidgets.QPushButton('Save')
        self.saveBtn.setStyleSheet(_btn_style('#2e7d52','white','#2e7d52')+
                                   'QPushButton{font-weight:bold;padding:6px 12px;}')
        self.saveBtn.clicked.connect(self._save)
        hdr.addWidget(self.saveBtn)
        vb.addLayout(hdr)
        
        # Date info label
        self.dateInfoLbl = QtWidgets.QLabel('')
        self.dateInfoLbl.setStyleSheet(f'font-size:12px;color:{TXT2};background:transparent;')
        self.dateInfoLbl.setAlignment(QtCore.Qt.AlignCenter)
        vb.addWidget(self.dateInfoLbl)
        
        # Decay correction note (English)
        decayNote = QtWidgets.QLabel(
            '<span style="font-size:11px;color:#666;">³⁷Ar & ³⁹Ar decay corrected '
            '(³⁷Ar: t<sub>½</sub>=35 days, ³⁹Ar: t<sub>½</sub>=269 years)</span>')
        decayNote.setAlignment(QtCore.Qt.AlignCenter)
        vb.addWidget(decayNote)
        
        # Scrollable area for all temperature blocks
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        
        self.scrollContent = QtWidgets.QWidget()
        self.scrollLayout = QtWidgets.QVBoxLayout(self.scrollContent)
        self.scrollLayout.setContentsMargins(0,8,0,8)
        self.scrollLayout.setSpacing(20)
        
        scroll.setWidget(self.scrollContent)
        vb.addWidget(scroll,1)
        
        # nextBtn 保留但隱藏（被 top bar 統一管理）
        self.nextBtn=QtWidgets.QPushButton('Next: Age Calc & Datum →')
        self.nextBtn.setVisible(False)
        
        self._steps = []
        self._ratio_names = ['Ar39/40','Ar36/40','Ar39/36','Ar40/36','Ar38/36']
        self._date_info = {}

    def populate(self, steps):
        self._steps = steps
        
        # Extract date info (English format)
        if steps and 'date_info' in steps[0]:
            info = steps[0]['date_info']
            spd = info.get('SPD', '—')
            ogd = info.get('OGD', '—')
            days = info.get('days', 0)
            self.dateInfoLbl.setText(
                f'Experiment Date: {spd} | Irradiation Date: {ogd} | Interval: {days} days')
        else:
            self.dateInfoLbl.setText('')
        
        # Clear existing blocks
        while self.scrollLayout.count():
            item = self.scrollLayout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Create block for each temperature step
        for step in steps:
            block = self._create_temp_block(step)
            self.scrollLayout.addWidget(block)
        
        self.scrollLayout.addStretch()
    
    def _create_temp_block(self, step):
        """Create a temperature block with title + 5-isotope table"""
        container = QtWidgets.QWidget()
        vb = QtWidgets.QVBoxLayout(container)
        vb.setContentsMargins(0,0,0,0)
        vb.setSpacing(6)
        
        # Check if any negative values
        raw = step.get('raw', [0]*5)
        net = step.get('net', [0]*5)
        sigma = step.get('sigma', [0]*5)
        ratio = step.get('ratio', [0]*5)
        ratio_sigma = step.get('ratio_sigma', [0]*5)
        
        has_negative = any(v < 0 for v in raw + net + sigma + ratio + ratio_sigma)
        
        # Temperature title with ! if negative values exist
        title_text = f'<b>{step["name"]}</b>'
        if has_negative:
            title_text = f'<b>{step["name"]} <span style="color:#b41a1a;">!</span></b>'
        titleLbl = QtWidgets.QLabel(title_text)
        titleLbl.setStyleSheet(f'font-size:15px;color:{TXT};background:transparent;')
        vb.addWidget(titleLbl)
        
        # 5-isotope table (7 columns: Isotope, Raw, Net, Sigma, Ratio, Value, Ratio σ)
        ratio_names_col = ['Ar39/Ar40', 'Ar36/Ar40', 'Ar39/Ar36', 'Ar40/Ar36', 'Ar38/Ar36']
        tbl = QtWidgets.QTableWidget(5, 7)
        tbl.setHorizontalHeaderLabels([
            'Isotope', 'Raw (T₀)', 'Measurement', 'Sigma (σ)',
            'Ratio', 'Value', 'Ratio σ'
        ])
        tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        tbl.horizontalHeader().resizeSection(0, 60)    # Isotope narrow
        tbl.horizontalHeader().setSectionResizeMode(4, QtWidgets.QHeaderView.Fixed)
        tbl.horizontalHeader().resizeSection(4, 95)    # Ratio name fixed
        for i in [1, 2, 3, 5, 6]:
            tbl.horizontalHeader().setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        tbl.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        tbl.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        tbl.verticalHeader().setDefaultSectionSize(36)
        header_height = tbl.horizontalHeader().height()
        tbl.setFixedHeight(header_height + 36 * 5 + 2)
        tbl.setStyleSheet(
            f'QTableWidget{{font-size:14px;gridline-color:{BRD};font-family:"Courier New",monospace;background:{PNL};}}'
            f'QHeaderView::section{{font-size:12px;background:#eeede8;border:1px solid {BRD2};padding:4px;}}')
        
        isotopes = ['³⁶Ar','³⁷Ar','³⁸Ar','³⁹Ar','⁴⁰Ar']
        for r in range(5):
            def _ci(text, red=False):
                it = QtWidgets.QTableWidgetItem(str(text))
                it.setTextAlignment(QtCore.Qt.AlignCenter)
                if red: it.setForeground(QtGui.QColor('#b41a1a'))
                return it
            tbl.setItem(r, 0, _ci(isotopes[r]))
            tbl.setItem(r, 1, _ci(f'{raw[r]:.6e}',         red=raw[r]<0))
            tbl.setItem(r, 2, _ci(f'{net[r]:.6e}',         red=net[r]<0))
            tbl.setItem(r, 3, _ci(f'{sigma[r]:.3e}',       red=sigma[r]<0))
            tbl.setItem(r, 4, _ci(ratio_names_col[r]))                            # ratio label
            tbl.setItem(r, 5, _ci(f'{ratio[r]:.6e}',       red=ratio[r]<0))      # ratio value
            tbl.setItem(r, 6, _ci(f'{ratio_sigma[r]:.3e}', red=ratio_sigma[r]<0))
        
        vb.addWidget(tbl)
        return container
    
    def _save(self):
        if not self._steps: return
        
        # 建立多選 checkbox dialog (English)
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('Save Mass Ratio')
        dialog.setMinimumWidth(400)
        vb = QtWidgets.QVBoxLayout(dialog)
        
        # 標題
        lbl = QtWidgets.QLabel('Select temperature steps to save:')
        lbl.setStyleSheet('font-size:13px;font-weight:bold;')
        vb.addWidget(lbl)
        
        # Checkbox grid
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMaximumHeight(300)
        scroll_widget = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(scroll_widget)
        grid.setSpacing(8)
        
        # 全選 checkbox (English)
        self._select_all_cb = QtWidgets.QCheckBox('Select All')
        self._select_all_cb.setStyleSheet('font-weight:bold;')
        self._select_all_cb.stateChanged.connect(lambda: self._toggle_all())
        grid.addWidget(self._select_all_cb, 0, 0, 1, 3)
        
        # 各溫階 checkboxes (3 columns layout)
        self._temp_checkboxes = []
        for i, step in enumerate(self._steps):
            cb = QtWidgets.QCheckBox(step['name'])
            cb.setChecked(True)
            self._temp_checkboxes.append(cb)
            row = (i // 3) + 1
            col = i % 3
            grid.addWidget(cb, row, col)
        
        scroll.setWidget(scroll_widget)
        vb.addWidget(scroll)
        
        # 按鈕
        btn_box = QtWidgets.QHBoxLayout()
        saveBtn = QtWidgets.QPushButton('Save')
        saveBtn.setStyleSheet(_btn_style('#2e7d52','white','#2e7d52'))
        saveBtn.clicked.connect(lambda: dialog.accept())
        cancelBtn = QtWidgets.QPushButton('Cancel')
        cancelBtn.setStyleSheet(_btn_style('#888','white','#888'))
        cancelBtn.clicked.connect(lambda: dialog.reject())
        btn_box.addStretch()
        btn_box.addWidget(saveBtn)
        btn_box.addWidget(cancelBtn)
        vb.addLayout(btn_box)
        
        # 顯示 dialog
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            # 取得選中的溫階
            selected = []
            for i, cb in enumerate(self._temp_checkboxes):
                if cb.isChecked():
                    selected.append(self._steps[i])
            
            if not selected:
                QtWidgets.QMessageBox.warning(self, 'Warning', 'Please select at least one temperature step')
                return
            
            # 選擇存檔目錄 (English)
            save_dir = QtWidgets.QFileDialog.getExistingDirectory(
                self, 'Select Save Directory', 'Data/MassRatio')
            if not save_dir:
                return
            
            # 存檔每個選中的溫階
            saved_files = []
            try:
                for step in selected:
                    # 檔名格式: Temperature_700_C.csv
                    temp_name = step['name'].replace(' ','_').replace('°','_')
                    filename = f'{temp_name}.csv'
                    filepath = os.path.join(save_dir, filename)
                    
                    with open(filepath, 'w', newline='', encoding='utf-8') as f:
                        w = csv.writer(f)
                        # v3.8.24: header was previously a single-element list whose
                        # string contained commas → csv.writer wrapped the whole
                        # header in quotes, collapsing it to one cell. Split into
                        # per-column entries to match PipelineWorker's f.write
                        # header (line 4140) exactly.
                        w.writerow(["Samp#", "t", "Min", "iradiation PK 90%",
                                    "Mass", "Raw", "Measurment",
                                    "Measurement's Sigma", "Ratio",
                                    "Value", "Ratio's Sigma"])
                        
                        # 取得資料
                        raw = step.get('raw', [0]*5)
                        net = step.get('net', [0]*5)
                        sigma = step.get('sigma', [0]*5)
                        ratio_sigma = step.get('ratio_sigma', [0]*5)
                        
                        # 從 mr_csv 讀取 Samp#, t, Min, PK (如果有的話)
                        samp_info = ['—', step['name'].replace('Temperature ','').replace('°C',''), '—', '—']
                        if 'mr_csv' in step:
                            try:
                                with open(step['mr_csv'], 'r') as mf:
                                    lines = mf.readlines()
                                    if len(lines) > 1:
                                        parts = lines[1].split(',')
                                        if len(parts) >= 4:
                                            samp_info = [parts[0], parts[1], parts[2], parts[3]]
                            except: pass
                        
                        # 5 rows (36/37/38/39/40 Ar)
                        isotopes = ['Ar36','Ar37','Ar38','Ar39','Ar40']
                        for i in range(5):
                            row_data = [
                                samp_info[0],  # Samp#
                                samp_info[1],  # t
                                samp_info[2],  # Min
                                samp_info[3],  # iradiation PK 90%
                                isotopes[i],   # Mass
                                f'{raw[i]:.17e}',  # Raw
                                f'{net[i]:.17e}',  # Measurement
                                f'{sigma[i]:.17e}',  # Sigma
                                self._ratio_names[i],  # Ratio name
                                '—',  # Ratio value (原始程式沒有這欄數值)
                                f'{ratio_sigma[i]:.17e}'  # Ratio sigma
                            ]
                            # 寫成單一 string 避免多餘引號
                            f.write(','.join(row_data) + '\n')
                    
                    saved_files.append(filename)
                
                QtWidgets.QMessageBox.information(
                    self, 'Saved', 
                    f'Saved {len(saved_files)} file(s) to:\n{save_dir}\n\n' + 
                    '\n'.join(saved_files[:5]) + 
                    (f'\n... and {len(saved_files)} files total' if len(saved_files) > 5 else ''))
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f'Save failed:\n{e}')
    
    def _toggle_all(self):
        """全選/取消全選"""
        state = self._select_all_cb.isChecked()
        for cb in self._temp_checkboxes:
            cb.setChecked(state)

# ═══════════════════════════════════════════════════════════
#  AgeCalcPage
# ═══════════════════════════════════════════════════════════
class AgeCalcPage(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._work_dir = ''
        self._datum_csv = ''
        self._steps = []
        
        vb=QtWidgets.QVBoxLayout(self); vb.setContentsMargins(10,8,10,8); vb.setSpacing(6)
        
        # ═══ Header: centered title + Save button ═══
        hdr = QtWidgets.QHBoxLayout()
        hdr.addStretch()
        lbl=QtWidgets.QLabel('<b>Age Calculation &amp; Datum</b>')
        lbl.setStyleSheet(f'font-size:20px;color:{TXT};')
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        hdr.addWidget(lbl)
        hdr.addStretch()
        
        self.exportBtn = QtWidgets.QPushButton('Export')
        self.exportBtn.setStyleSheet(_btn_style('#2e7d52','white','#2e7d52')+
                                     'QPushButton{font-weight:bold;padding:6px 12px;}')
        self.exportBtn.clicked.connect(self._export)
        hdr.addWidget(self.exportBtn)
        vb.addLayout(hdr)
        
        # ═══ Summary banner (row 1: stat cells; row 2: controls) ═══
        self.summaryFrame = QtWidgets.QFrame()
        self.summaryFrame.setStyleSheet(
            f'background:#eeede8;border:1px solid {BRD};border-radius:4px;')
        sf_vl = QtWidgets.QVBoxLayout(self.summaryFrame)
        sf_vl.setContentsMargins(12,6,12,6)
        sf_vl.setSpacing(6)
        
        # Row 1: stats (6 cells)
        sf_hl = QtWidgets.QHBoxLayout()
        sf_hl.setSpacing(16)
        
        def stat_cell(label, w_width=None):
            w = QtWidgets.QWidget()
            wl = QtWidgets.QVBoxLayout(w)
            wl.setContentsMargins(0,0,0,0); wl.setSpacing(1)
            lbl_k = QtWidgets.QLabel(label)
            lbl_k.setStyleSheet(f'font-size:10px;color:{TXT3};background:transparent;')
            val = QtWidgets.QLabel('—')
            val.setStyleSheet(f'font-size:13px;font-weight:bold;color:{TXT};'
                             f'background:transparent;font-family:Courier New;')
            wl.addWidget(lbl_k)
            wl.addWidget(val)
            if w_width: w.setFixedWidth(w_width)
            return w, val
        
        w1, self._stat_total = stat_cell('Total Fusion Age')
        sf_hl.addWidget(w1)
        w2, self._stat_plateau = stat_cell('Weighted Plateau')
        sf_hl.addWidget(w2)
        w3, self._stat_normiso = stat_cell('Normal Isochron')
        sf_hl.addWidget(w3)
        w4, self._stat_invIso = stat_cell('Inverse Isochron')
        sf_hl.addWidget(w4)
        # v3.8.5 (B1): MSWD label clarified as Plateau MSWD (regression MSWD
        # shown on the inverse isochron PNG itself via annotation).
        w5, self._stat_mswd = stat_cell('Plateau MSWD')
        sf_hl.addWidget(w5)
        w6, self._stat_j = stat_cell('J value')
        sf_hl.addWidget(w6)
        w7, self._stat_steps = stat_cell('Steps')
        sf_hl.addWidget(w7)
        # v3.8.5 (A2): isochron regression method toggle.  Default OLS for
        # backward compatibility.  York 2004 uses both x,y errors per Schaen 2021.
        _method_widget = QtWidgets.QWidget()
        _method_vl = QtWidgets.QVBoxLayout(_method_widget)
        _method_vl.setContentsMargins(0,0,0,0); _method_vl.setSpacing(1)
        _method_lbl = QtWidgets.QLabel('Isochron method')
        _method_lbl.setStyleSheet(f'font-size:10px;color:{TXT3};background:transparent;')
        self._isochron_method_combo = QtWidgets.QComboBox()
        self._isochron_method_combo.addItem('OLS',  'ols')
        self._isochron_method_combo.addItem('York 2004', 'york')
        self._isochron_method_combo.setCurrentIndex(0)
        self._isochron_method_combo.setToolTip(
            'OLS: scipy.curve_fit, assumes σ_x = 0 (older Ar/Ar convention).\n'
            'York 2004: bivariate weighted regression with both σ_x and σ_y\n'
            '(Schaen 2021 GSA Bull standard, IsoplotR default).')
        self._isochron_method_combo.setStyleSheet(
            'QComboBox{font-size:11px;padding:2px 4px;background:white;'
            f'border:1px solid {BRD};border-radius:3px;}}')
        _method_vl.addWidget(_method_lbl)
        _method_vl.addWidget(self._isochron_method_combo)
        sf_hl.addWidget(_method_widget)
        sf_hl.addStretch()
        sf_vl.addLayout(sf_hl)
        
        # Row 2: controls (atm ratio input + Temp label checkbox)
        ctrl_hl = QtWidgets.QHBoxLayout()
        ctrl_hl.setSpacing(10)
        
        ctrl_hl.addWidget(QtWidgets.QLabel(
            '<span style="font-size:11px;color:#444;">⁴⁰Ar/³⁶Ar atm:</span>'))
        self.atmRatioEdit = QtWidgets.QLineEdit('298.56')
        self.atmRatioEdit.setFixedWidth(80)
        self.atmRatioEdit.setStyleSheet(
            f'QLineEdit{{background:white;border:1px solid {BRD};'
            f'padding:2px 6px;font-size:11px;font-family:Courier New;}}')
        self.atmRatioEdit.setValidator(QtGui.QDoubleValidator(0.0, 1e6, 4))
        ctrl_hl.addWidget(self.atmRatioEdit)
        
        self.atmSigmaLbl = QtWidgets.QLabel(
            '<span style="font-size:10px;color:#888;">± 0.31 (default)</span>')
        ctrl_hl.addWidget(self.atmSigmaLbl)
        
        ctrl_hl.addSpacing(20)
        
        self.tempLabelCB = QtWidgets.QCheckBox('Show Temp labels on Isochron')
        self.tempLabelCB.setStyleSheet('font-size:11px;')
        self.tempLabelCB.setChecked(True)
        self.tempLabelCB.stateChanged.connect(self._refresh_diagrams)
        ctrl_hl.addWidget(self.tempLabelCB)
        
        ctrl_hl.addSpacing(20)
        
        self.recalcBtn = QtWidgets.QPushButton('Recalculate')
        self.recalcBtn.setStyleSheet(
            _btn_style('#1a5fb4','white','#1a5fb4') +
            'QPushButton{font-size:11px;padding:3px 10px;}')
        self.recalcBtn.clicked.connect(self._recalculate_with_atm)
        ctrl_hl.addWidget(self.recalcBtn)
        
        ctrl_hl.addStretch()
        sf_vl.addLayout(ctrl_hl)
        
        vb.addWidget(self.summaryFrame)
        
        # ═══ Main splitter: table (left) + diagrams (right) ═══
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Left: Results table
        table_w = QtWidgets.QWidget()
        table_vl = QtWidgets.QVBoxLayout(table_w)
        table_vl.setContentsMargins(0,0,0,0); table_vl.setSpacing(4)
        
        tbl_hdr = QtWidgets.QLabel('<b>Results per Step</b>')
        tbl_hdr.setStyleSheet(f'font-size:13px;color:{TXT};padding:2px 0;')
        table_vl.addWidget(tbl_hdr)
        
        self.tbl=QtWidgets.QTableWidget(0,6)
        self.tbl.setHorizontalHeaderLabels(
            ['Step','Age (Ma)','±σ (Ma)','⁴⁰Ar(r)%','Ca/K','Issues'])
        self.tbl.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl.setStyleSheet(
            f'QTableWidget{{font-size:12px;gridline-color:{BRD};font-family:"Courier New",monospace;}}'
            f'QHeaderView::section{{font-size:11px;background:#eeede8;border:1px solid {BRD2};padding:4px;}}')
        table_vl.addWidget(self.tbl, 1)
        splitter.addWidget(table_w)
        
        # Right: Diagrams (clickable to enlarge, with axis controls)
        dg_w = QtWidgets.QWidget()
        dg_vl = QtWidgets.QVBoxLayout(dg_w)
        dg_vl.setContentsMargins(4,0,0,0); dg_vl.setSpacing(4)
        
        dg_hdr = QtWidgets.QLabel(
            '<b>Diagrams</b> <span style="font-size:10px;color:#888;">'
            '(click image to enlarge · click ⚙ to adjust axis range)</span>')
        dg_hdr.setStyleSheet(f'font-size:13px;color:{TXT};padding:2px 0;')
        dg_vl.addWidget(dg_hdr)
        
        dg_grid = QtWidgets.QGridLayout()
        dg_grid.setSpacing(6)
        self._dlbls={}
        self._daxis={}  # Store axis ranges per diagram: {key: {'xmin':..,'xmax':..,'ymin':..,'ymax':..}}
        for idx,(key,title) in enumerate([('DFW','Age Spectrum'),('DFA','Ca/K'),
                                           ('DFN','Normal Isochron'),('DFI','Inverse Isochron')]):
            fr=QtWidgets.QFrame()
            fr.setFrameShape(QtWidgets.QFrame.Box)
            fr.setStyleSheet(f'QFrame{{border:1px solid {BRD};background:white;}}'
                           f'QFrame:hover{{border:2px solid #1a5fb4;}}')
            fr.setMinimumSize(220,180)
            fvb=QtWidgets.QVBoxLayout(fr); fvb.setContentsMargins(4,4,4,4); fvb.setSpacing(2)
            
            # Header row: title + gear button
            hdr_hl = QtWidgets.QHBoxLayout()
            hdr_hl.setContentsMargins(0,0,0,0)
            h=QtWidgets.QLabel(f'<b>{title}</b>')
            h.setAlignment(QtCore.Qt.AlignCenter)
            h.setStyleSheet(f'font-size:11px;color:{TXT2};border:none;background:transparent;')
            hdr_hl.addWidget(h, 1)
            
            gear_btn = QtWidgets.QPushButton('⚙')
            gear_btn.setFixedSize(20, 20)
            gear_btn.setStyleSheet('QPushButton{border:none;background:transparent;font-size:14px;}'
                                   'QPushButton:hover{background:#ddd;border-radius:3px;}')
            gear_btn.setCursor(QtCore.Qt.PointingHandCursor)
            gear_btn.clicked.connect(lambda _, k=key, t=title: self._axis_dialog(k, t))
            hdr_hl.addWidget(gear_btn)
            hdr_w = QtWidgets.QWidget()
            hdr_w.setLayout(hdr_hl)
            fvb.addWidget(hdr_w)
            
            l=QtWidgets.QLabel('(pending)')
            l.setAlignment(QtCore.Qt.AlignCenter)
            l.setScaledContents(True)
            l.setMinimumSize(210,150)
            l.setStyleSheet('border:none;background:transparent;')
            l.setCursor(QtCore.Qt.PointingHandCursor)
            # Click to enlarge (only on image, not gear button)
            l.mousePressEvent = lambda e, k=key, t=title: self._show_enlarged(k, t)
            fvb.addWidget(l,1)
            
            dg_grid.addWidget(fr,idx//2,idx%2)
            self._dlbls[key]=l
            self._daxis[key]={'xmin':None,'xmax':None,'ymin':None,'ymax':None}
        
        dg_grid_w = QtWidgets.QWidget()
        dg_grid_w.setLayout(dg_grid)
        dg_vl.addWidget(dg_grid_w, 1)
        splitter.addWidget(dg_w)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        vb.addWidget(splitter, 1)

    def populate(self, steps, datum_csv, work_dir, consts=None):
        self._steps = steps
        self._work_dir = work_dir
        self._datum_csv = datum_csv
        self._consts = consts
        # v3.8.5 (A2): wire dropdown change → regen diagrams with new method
        try:
            self._isochron_method_combo.currentIndexChanged.disconnect()
        except Exception:
            pass
        self._isochron_method_combo.currentIndexChanged.connect(self._on_isochron_method_changed)
        
        # Populate results table
        self.tbl.setRowCount(len(steps))
        total_age_sum = 0.0
        total_age_weight = 0.0
        valid_count = 0
        
        for r,step in enumerate(steps):
            ar=step.get('age_result',[])
            age_Ma =_sf(ar[46])/1e6 if len(ar)>47 else float('nan')
            age_std=_sf(ar[47])/1e6 if len(ar)>47 else float('nan')
            ar40pct=_sf(ar[50])*100  if len(ar)>50 else 0.0
            cak = _sf(ar[23]) if len(ar)>24 else 0.0
            issues=', '.join(step.get('neg_datum',[])) or '—'
            vals=[step['name'],f'{age_Ma:.4f}',f'{age_std:.4f}',
                 f'{ar40pct:.1f}%',f'{cak:.3f}',issues]
            for c,v in enumerate(vals):
                item=QtWidgets.QTableWidgetItem(v)
                if c==5 and v!='—':
                    item.setForeground(QtGui.QColor('#b41a1a'))
                self.tbl.setItem(r,c,item)
            
            # Accumulate for total fusion age (weighted by 1/σ²)
            if not (age_Ma != age_Ma) and age_std > 0:  # not NaN and valid σ
                weight = 1.0 / (age_std**2)
                total_age_sum += age_Ma * weight
                total_age_weight += weight
                valid_count += 1
        
        # Update summary banner
        if total_age_weight > 0:
            total_age = total_age_sum / total_age_weight
            total_sigma = (1.0 / total_age_weight) ** 0.5
            self._stat_total.setText(f'{total_age:.3f} ± {total_sigma:.3f} Ma')
        else:
            self._stat_total.setText('—')
        
        # Plateau, Normal/Inverse Isochron, MSWD (computed from ar_list)
        self._update_isochron_stats(steps)
        
        self._stat_steps.setText(f'{valid_count} / {len(steps)}')
        
        # Try to extract J value + atm ratio from first step's age_result
        if steps:
            ar = steps[0].get('age_result',[])
            if len(ar) > 45:
                J = _sf(ar[44])
                Js = _sf(ar[45])
                self._stat_j.setText(f'{J:.2e} ± {Js:.0e}')
            # Atm ratio (row[82] in datum row is atm 40/36)
            if len(ar) > 83:
                atm = _sf(ar[82])
                atm_s = _sf(ar[83])
                if atm > 0:
                    self.atmRatioEdit.setText(f'{atm:.2f}')
                    self.atmSigmaLbl.setText(
                        f'<span style="font-size:10px;color:#888;">± {atm_s:.2f}</span>')
        
        # Load diagrams
        for key,lbl in self._dlbls.items():
            src=os.path.join(work_dir,'.work',key+'.png')
            if os.path.exists(src):
                pm=QtGui.QPixmap(src)
                if not pm.isNull():
                    lbl.setPixmap(pm.scaled(lbl.size(),
                        QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
                    lbl.setText('')
    
    def _on_isochron_method_changed(self, idx):
        """v3.8.5 (A2): user changed OLS / York dropdown. Regenerate DFI/DFN
        PNGs by re-calling Utilities.getDFStatistics_sh with the new method,
        then reload the diagram labels."""
        if not getattr(self, '_datum_csv', None) or not getattr(self, '_consts', None):
            return
        method = self._isochron_method_combo.itemData(idx) or 'ols'
        try:
            mask_all = np.ones(len(self._steps))
            Utilities.getDFStatistics_sh(self._datum_csv, mask_all, self._consts,
                                         'b', 'o', isochron_method=method)
            for key, lbl in self._dlbls.items():
                src = os.path.join(self._work_dir, '.work', key + '.png')
                if os.path.exists(src):
                    pm = QtGui.QPixmap(src)
                    if not pm.isNull():
                        lbl.setPixmap(pm.scaled(
                            lbl.size(),
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation))
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, 'Regen diagrams failed',
                f'isochron_method={method}: {e}')

    def _update_isochron_stats(self, steps):
        """Compute plateau (Wendt-Carl 1991 √MSWD corrected), and both
        normal/inverse isochrons via York (2004) regression.

        Plateau:
          σ_internal = 1/√Σ(1/σᵢ²)
          MSWD       = (1/(N−1)) Σ((ageᵢ−mean)/σᵢ)²
          σ_external = σ_internal · √MSWD   if MSWD > 1   (Wendt-Carl)
          σ_external = σ_internal           else

        Normal isochron : y = ⁴⁰Ar/³⁶Ar,  x = ³⁹Ar/³⁶Ar
                          y-intercept = (⁴⁰/³⁶)_trapped
                          slope ×  = ⁴⁰Ar*/³⁹Ar_K
        Inverse isochron: y = ³⁶Ar/⁴⁰Ar,  x = ³⁹Ar/⁴⁰Ar
                          y-intercept = (³⁶/⁴⁰)_trapped (= 1/atm-ratio for air)
                          x-intercept → ⁴⁰Ar*/³⁹Ar_K
        Both fit via York et al. (2004) Unified Equations (with x,y errors).
        Age computed from F = ⁴⁰Ar*/³⁹Ar_K using J value from each step.
        """
        # --- collect step-level age + isotope ratios ---
        ages = []        # (age_Ma, sig_Ma, name)
        iso_data = []    # (Ar36_m, Ar37_m, Ar39_m, Ar40_m, σ36, σ37, σ39, σ40, J, Js)
        for step in steps:
            ar = step.get('age_result', [])
            if len(ar) > 47:
                age = _sf(ar[46]) / 1e6
                age_std = _sf(ar[47]) / 1e6
                ar40r = _sf(ar[24])
                ar39k = _sf(ar[18])
                if age_std > 0 and ar40r > 0 and ar39k > 0:
                    ages.append((age, age_std, step['name']))
            # measured (raw) isotopes for isochron
            if len(ar) > 17:
                try:
                    Ar36_m, sAr36 = _sf(ar[2]),  _sf(ar[3])
                    Ar37_m, sAr37 = _sf(ar[4]),  _sf(ar[5])
                    Ar38_m, sAr38 = _sf(ar[6]),  _sf(ar[7])
                    Ar39_m, sAr39 = _sf(ar[8]),  _sf(ar[9])
                    Ar40_m, sAr40 = _sf(ar[10]), _sf(ar[11])
                    Jv = _sf(ar[44]) if len(ar) > 44 else 0.0
                    if Ar36_m > 0 and Ar39_m > 0 and Ar40_m > 0:
                        iso_data.append({
                            '36':Ar36_m,'37':Ar37_m,'38':Ar38_m,'39':Ar39_m,'40':Ar40_m,
                            's36':sAr36,'s37':sAr37,'s38':sAr38,'s39':sAr39,'s40':sAr40,
                            'J':Jv,'name':step['name']})
                except Exception:
                    pass

        # --- Plateau weighted mean (with √MSWD correction) ---
        if ages:
            total_w = sum(1.0/a[1]**2 for a in ages)
            if total_w > 0:
                mean = sum(a[0]/a[1]**2 for a in ages) / total_w
                sigma_int = (1.0/total_w) ** 0.5
                n = len(ages)
                if n > 1:
                    chi2 = sum(((a[0]-mean)/a[1])**2 for a in ages)
                    mswd = chi2 / (n - 1)
                    # Wendt & Carl 1991: σ_ext = σ_int · √MSWD if MSWD > 1
                    sigma_ext = sigma_int * math.sqrt(mswd) if mswd > 1 else sigma_int
                    self._stat_mswd.setText(f'{mswd:.2f} (n={n})')
                    self._stat_plateau.setText(
                        f'{mean:.3f} ± {sigma_ext:.3f} Ma  (1σ, '
                        f'{"ext" if mswd > 1 else "int"})')
                else:
                    self._stat_mswd.setText('—')
                    self._stat_plateau.setText(f'{mean:.3f} ± {sigma_int:.3f} Ma')
            else:
                self._stat_plateau.setText('—'); self._stat_mswd.setText('—')
        else:
            self._stat_plateau.setText('—'); self._stat_mswd.setText('—')

        # --- Normal & Inverse isochron via York regression ---
        if len(iso_data) >= 3:
            try:
                # Normal: x = 39/36, y = 40/36
                xs_n  = np.array([d['39']/d['36'] for d in iso_data])
                ys_n  = np.array([d['40']/d['36'] for d in iso_data])
                sxs_n = np.array([_ratio_sigma(d['39'],d['s39'],d['36'],d['s36']) for d in iso_data])
                sys_n = np.array([_ratio_sigma(d['40'],d['s40'],d['36'],d['s36']) for d in iso_data])
                m_n, b_n, sm_n, sb_n, mswd_n, _cov_n = york_regression(xs_n, sxs_n, ys_n, sys_n)
                # Normal isochron (Vermeesch 2024 Eq. 1, Y=a+bX convention):
                #   slope b_York     = F = ⁴⁰Ar*/³⁹Ar_K   →  pyADR m_n
                #   intercept a_York = (⁴⁰/³⁶)_trapped     →  pyADR b_n
                F_n = m_n; sF_n = sm_n  # F is just slope → no cov term needed
                Jv = iso_data[0]['J'] if iso_data[0]['J'] > 0 else 0.0
                if F_n > 0 and Jv > 0:
                    # v3.8.4: λ from parameters via module LAMBDA_K (was hardcoded 5.543e-10)
                    age_n = (1/LAMBDA_K)*math.log(1+Jv*F_n)/1e6
                    sage_n = abs((1/LAMBDA_K)*Jv/(1+Jv*F_n)/1e6)*sF_n
                    self._stat_normiso.setText(
                        f'{age_n:.3f} ± {sage_n:.3f} Ma  '
                        f'(MSWD={mswd_n:.2f}, n={len(iso_data)}, '
                        f'(40/36)ₜ={b_n:.1f}±{sb_n:.1f})')
                else:
                    self._stat_normiso.setText(f'(MSWD={mswd_n:.2f}, slope ≤ 0)')

                # Inverse: x = 39/40, y = 36/40
                xs_i  = np.array([d['39']/d['40'] for d in iso_data])
                ys_i  = np.array([d['36']/d['40'] for d in iso_data])
                sxs_i = np.array([_ratio_sigma(d['39'],d['s39'],d['40'],d['s40']) for d in iso_data])
                sys_i = np.array([_ratio_sigma(d['36'],d['s36'],d['40'],d['s40']) for d in iso_data])
                m_i, b_i, sm_i, sb_i, mswd_i, cov_mb_i = york_regression(xs_i, sxs_i, ys_i, sys_i)
                # Inverse isochron (Vermeesch 2024 Eq. 2, Li & Vermeesch 2021 Eq. 5):
                #   intercept a_York = (³⁶/⁴⁰)_trapped     →  pyADR b_i (≈ 1/298.56 for atm)
                #   slope b_York     = -a_York · (e^(λt)-1) →  pyADR m_i (negative)
                #   F = -slope / intercept = -m_i / b_i
                # v3.8.4 fix: previous code had F_i = -b_i/m_i (intercept/slope, REVERSED)
                # which computed 1/F rather than F.  This is the Vermeesch 2024 page 2
                # formulation "[D/P]* = -b/a for inverse isochrons (Li and Vermeesch, 2021)".
                if abs(m_i) > 1e-30 and abs(b_i) > 1e-30 and Jv > 0:
                    F_i = -m_i / b_i
                    # v3.8.5 (A3): σ_F propagation now includes cov(slope, intercept).
                    # F = -m/b:
                    #   ∂F/∂m = -1/b
                    #   ∂F/∂b =  m/b²
                    # σ_F² = (σ_m/b)² + (m·σ_b/b²)² - 2·(m/b³)·cov(m,b)
                    # cov term typically negative for York fits → reduces σ_F (more confident).
                    # Matches Utilities.py:1496-1498 (getDFStatistics_sh) formula.
                    _varF = ((sm_i/b_i)**2
                             + (m_i*sb_i/(b_i*b_i))**2
                             - 2.0 * (m_i / (b_i**3)) * cov_mb_i)
                    sF_i = math.sqrt(abs(_varF)) if _varF == _varF else 0.0
                    if F_i > 0:
                        # v3.8.4: λ from parameters via module LAMBDA_K (was hardcoded 5.543e-10)
                        age_i = (1/LAMBDA_K)*math.log(1+Jv*F_i)/1e6
                        sage_i = abs((1/LAMBDA_K)*Jv/(1+Jv*F_i)/1e6)*sF_i
                        atm_ratio = 1/b_i  # b_i = (36/40)_t, so 1/b_i = (40/36)_t
                        self._stat_invIso.setText(
                            f'{age_i:.3f} ± {sage_i:.3f} Ma  '
                            f'(MSWD={mswd_i:.2f}, n={len(iso_data)}, '
                            f'(40/36)ₜ={atm_ratio:.1f})')
                    else:
                        self._stat_invIso.setText(f'(MSWD={mswd_i:.2f}, F ≤ 0)')
                else:
                    self._stat_invIso.setText('— (degenerate fit)')
            except Exception as e:
                self._stat_normiso.setText(f'fit error')
                self._stat_invIso.setText(f'fit error')
        else:
            self._stat_normiso.setText('— (need ≥3 steps)')
            self._stat_invIso.setText('— (need ≥3 steps)')
    
    def _axis_dialog(self, key, title):
        """Dialog to set XY axis range for a specific diagram"""
        current = self._daxis.get(key, {'xmin':None,'xmax':None,'ymin':None,'ymax':None})
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(f'Axis Range — {title}')
        dialog.setMinimumWidth(300)
        vl = QtWidgets.QVBoxLayout(dialog)
        
        form = QtWidgets.QFormLayout()
        
        def mkedit(val):
            e = QtWidgets.QLineEdit('' if val is None else str(val))
            e.setPlaceholderText('auto')
            return e
        
        xmin_e = mkedit(current['xmin'])
        xmax_e = mkedit(current['xmax'])
        ymin_e = mkedit(current['ymin'])
        ymax_e = mkedit(current['ymax'])
        
        form.addRow('X min:', xmin_e)
        form.addRow('X max:', xmax_e)
        form.addRow('Y min:', ymin_e)
        form.addRow('Y max:', ymax_e)
        vl.addLayout(form)
        
        hint = QtWidgets.QLabel('<span style="color:#888;font-size:10px;">'
                               'Leave blank for auto. Click Apply to regenerate diagram.</span>')
        vl.addWidget(hint)
        
        btn_box = QtWidgets.QHBoxLayout()
        resetBtn = QtWidgets.QPushButton('Reset to Auto')
        resetBtn.clicked.connect(lambda: [e.clear() for e in [xmin_e,xmax_e,ymin_e,ymax_e]])
        applyBtn = QtWidgets.QPushButton('Apply')
        applyBtn.setStyleSheet(_btn_style('#1a5fb4','white','#1a5fb4'))
        applyBtn.clicked.connect(dialog.accept)
        cancelBtn = QtWidgets.QPushButton('Cancel')
        cancelBtn.clicked.connect(dialog.reject)
        btn_box.addWidget(resetBtn)
        btn_box.addStretch()
        btn_box.addWidget(applyBtn)
        btn_box.addWidget(cancelBtn)
        vl.addLayout(btn_box)
        
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            def parse(e):
                txt = e.text().strip()
                if not txt: return None
                try: return float(txt)
                except: return None
            
            self._daxis[key] = {
                'xmin': parse(xmin_e), 'xmax': parse(xmax_e),
                'ymin': parse(ymin_e), 'ymax': parse(ymax_e)
            }
            self._refresh_diagrams()
    
    def _refresh_diagrams(self):
        """Regenerate diagrams with current axis ranges and temp labels."""
        # Signal to parent/worker to regenerate diagrams
        # For now just reload existing PNGs (actual regeneration needs matplotlib hook into Utilities)
        if hasattr(self, '_on_refresh_request'):
            self._on_refresh_request(self._daxis, self.tempLabelCB.isChecked(),
                                    self._get_atm_ratio())
        # Reload images
        for key,lbl in self._dlbls.items():
            src=os.path.join(self._work_dir,'.work',key+'.png')
            if os.path.exists(src):
                pm=QtGui.QPixmap(src)
                if not pm.isNull():
                    lbl.setPixmap(pm.scaled(lbl.size(),
                        QtCore.Qt.KeepAspectRatio,QtCore.Qt.SmoothTransformation))
    
    def _get_atm_ratio(self):
        """Get current atm ratio from input."""
        try: return float(self.atmRatioEdit.text())
        except: return 298.56
    
    def _recalculate_with_atm(self):
        """Recalculate ages using user-specified atm ratio."""
        try:
            atm = float(self.atmRatioEdit.text())
        except:
            QtWidgets.QMessageBox.warning(self, 'Error', 'Invalid ⁴⁰Ar/³⁶Ar value')
            return
        
        # Emit signal for parent to recompute with new atm ratio
        if hasattr(self, '_on_recalc_request'):
            self._on_recalc_request(atm)
        else:
            QtWidgets.QMessageBox.information(
                self, 'Recalculate',
                f'Atm ratio updated to {atm:.2f}.\n\n'
                'Note: full recalculation requires re-running the Age Calc pipeline.\n'
                'The new value will be applied to subsequent calculations.')
    
    def _show_enlarged(self, key, title):
        """Show enlarged diagram in dialog"""
        src = os.path.join(self._work_dir, '.work', key+'.png')
        if not os.path.exists(src):
            QtWidgets.QMessageBox.information(self, 'Info', f'{title} not available yet.')
            return
        
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(800, 600)
        vl = QtWidgets.QVBoxLayout(dialog)
        
        lbl = QtWidgets.QLabel()
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        pm = QtGui.QPixmap(src)
        lbl.setPixmap(pm.scaled(780, 560, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
        vl.addWidget(lbl, 1)
        
        btn_box = QtWidgets.QHBoxLayout()
        saveBtn = QtWidgets.QPushButton('Save Image')
        saveBtn.clicked.connect(lambda: self._save_single_diagram(src, title))
        closeBtn = QtWidgets.QPushButton('Close')
        closeBtn.clicked.connect(dialog.accept)
        btn_box.addStretch()
        btn_box.addWidget(saveBtn)
        btn_box.addWidget(closeBtn)
        vl.addLayout(btn_box)
        
        dialog.exec_()
    
    def _save_single_diagram(self, src, title):
        """Save a single diagram"""
        out, ok = QtWidgets.QFileDialog.getSaveFileName(
            self, f'Save {title}', f'{title.replace(" ","_")}.png', 'PNG (*.png)')
        if out:
            try:
                shutil.copy(src, out)
                QtWidgets.QMessageBox.information(self, 'Saved', f'Saved to:\n{out}')
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, 'Error', f'Save failed:\n{e}')
    
    def _export(self):
        """Export datum CSV + all diagrams"""
        if not self._steps:
            QtWidgets.QMessageBox.warning(self, 'Warning', 'No data to export.')
            return
        
        # Dialog for what to export
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle('Export')
        dialog.setMinimumWidth(320)
        vl = QtWidgets.QVBoxLayout(dialog)
        
        lbl = QtWidgets.QLabel('Select items to export:')
        lbl.setStyleSheet('font-size:13px;font-weight:bold;')
        vl.addWidget(lbl)
        
        cb_datum = QtWidgets.QCheckBox('Datum CSV')
        cb_datum.setChecked(True)
        vl.addWidget(cb_datum)
        
        cb_summary = QtWidgets.QCheckBox('Summary table (Results per Step)')
        cb_summary.setChecked(True)
        vl.addWidget(cb_summary)
        
        cb_figs = QtWidgets.QCheckBox('All diagrams (PNG)')
        cb_figs.setChecked(True)
        vl.addWidget(cb_figs)
        
        btn_box = QtWidgets.QHBoxLayout()
        okBtn = QtWidgets.QPushButton('Export')
        okBtn.setStyleSheet(_btn_style('#2e7d52','white','#2e7d52'))
        okBtn.clicked.connect(dialog.accept)
        cancelBtn = QtWidgets.QPushButton('Cancel')
        cancelBtn.setStyleSheet(_btn_style('#888','white','#888'))
        cancelBtn.clicked.connect(dialog.reject)
        btn_box.addStretch()
        btn_box.addWidget(okBtn)
        btn_box.addWidget(cancelBtn)
        vl.addLayout(btn_box)
        
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return
        
        save_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Select Export Directory', self._work_dir or '.')
        if not save_dir:
            return
        
        exported = []
        try:
            # Datum CSV
            if cb_datum.isChecked() and self._datum_csv and os.path.exists(self._datum_csv):
                dest = os.path.join(save_dir, os.path.basename(self._datum_csv))
                shutil.copy(self._datum_csv, dest)
                exported.append(os.path.basename(dest))
            
            # Summary table
            if cb_summary.isChecked():
                dest = os.path.join(save_dir, 'AgeCalc_summary.csv')
                with open(dest, 'w', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    w.writerow(['Step','Age (Ma)','±σ (Ma)','40Ar(r)%','Ca/K','Issues'])
                    for step in self._steps:
                        ar = step.get('age_result', [])
                        age_Ma =_sf(ar[46])/1e6 if len(ar)>47 else float('nan')
                        age_std=_sf(ar[47])/1e6 if len(ar)>47 else float('nan')
                        ar40pct=_sf(ar[50])*100  if len(ar)>50 else 0.0
                        cak = _sf(ar[23]) if len(ar)>24 else 0.0
                        issues=', '.join(step.get('neg_datum',[])) or '—'
                        w.writerow([step['name'],f'{age_Ma:.4f}',f'{age_std:.4f}',
                                  f'{ar40pct:.1f}%',f'{cak:.3f}',issues])
                exported.append('AgeCalc_summary.csv')
            
            # Diagrams
            if cb_figs.isChecked():
                for key, title in [('DFW','Age_Spectrum'),('DFA','CaK'),
                                  ('DFN','Normal_Isochron'),('DFI','Inverse_Isochron')]:
                    src = os.path.join(self._work_dir, '.work', key+'.png')
                    if os.path.exists(src):
                        dest = os.path.join(save_dir, f'{title}.png')
                        shutil.copy(src, dest)
                        exported.append(f'{title}.png')
            
            QtWidgets.QMessageBox.information(
                self, 'Export Complete',
                f'Exported {len(exported)} file(s) to:\n{save_dir}\n\n' +
                '\n'.join(exported))
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, 'Error', f'Export failed:\n{e}')

# ═══════════════════════════════════════════════════════════
#  Pipeline worker
# ═══════════════════════════════════════════════════════════
_DATUM_HEADER=[
    "Samp#","Min","IRR","deg C","J","J_std","J_int",
    "36Ar(a)","36Ar(a)_std","37Ar(ca)","37Ar(ca)_std","38Ar(cl)","38Ar(cl)_std",
    "39Ar(k)","39Ar(k)_std","40Ar(r)","40Ar(r)_std","Age(Ma)","Age_std(Ma)",
    "40Ar(r)(%)","39Ar(k)(%)","40Ar(r)(%)(step heating)","39Ar(k)(%)(step heating)",
    "Ca/K","Ca/K_std","Degassing Patterns",
    "36Ar(a)","36Ar(a)_std","36Ar(c)","36Ar(c)_std","36Ar(ca)","36Ar(ca)_std","36Ar(cl)","36Ar(cl)_std",
    "37Ar(ca)","37Ar(ca)_std","38Ar(a)","38Ar(a)_std","38Ar(c)","38Ar(c)_std","38Ar(k)","38Ar(k)_std",
    "38Ar(ca)","38Ar(ca)_std","38Ar(cl)","38Ar(cl)_std",
    "39Ar(k)","39Ar(k)_std","39Ar(ca)","39Ar(ca)_std",
    "40Ar(r)","40Ar(r)_std","40Ar(a)","40Ar(a)_std","40Ar(c)","40Ar(c)_std","40Ar(k)","40Ar(k)_std",
    "Additional Parameters","40(r)/39(k)","40(r)/39(k)_std","40(r+a)","40(r+a)_std",
    "40Ar/39Ar","40Ar/39Ar_std","37Ar/39Ar","37Ar/39Ar_std","36Ar/39Ar","36Ar/39Ar_std",
    "Parameters","39Ar/37Ar(ca)","39Ar/37Ar(ca)_std","36Ar/37Ar(ca)","36Ar/37Ar(ca)_std",
    "40Ar/39Ar(k)","40Ar/39Ar(k)_std","38Ar/39Ar(k)","38Ar/39Ar(k)_std",
    "39Ar/37Ar(k)","39Ar/37Ar(k)_std","36Ar/38Ar(cl)","36Ar/38Ar(cl)_std",
    "40Ar/36Ar(a)","40Ar/36Ar(a)_std","38Ar/36Ar(a)","38Ar/36Ar(a)_std",
    "Lambda","numCycle",
    # v3.8.24: removed normal/inverse isochron columns (10 cols total) to
    # match NTNU_DataReduction DatumPublication header exactly. Isochron
    # ratios are still recoverable from the raw Ar40(m)/Ar39(m)/Ar36(m)
    # in the Degassing Patterns section above.
]

def _build_datum_row(ar, info, temperature, params, pnames, ar39pct, ar40pct):
    def gp(n,d=0.0):
        try: return float(params[pnames.index(n)])
        except: return d
    samp,mineral,_,_,irr=info
    r38_36=gp("Atmospheric Ratio 38/36(a)",0.1885); r38_36s=gp("Atmospheric Ratio 38/36(a) std",0.000347)
    r38_39=gp("Production Ratio 38Ar/39Ar(k)",0.0126288); r38_39s=gp("Production Ratio 38Ar/39Ar(k) std",0.0000105)
    pr=gp("Production Ratio 39Ar/37Ar(ca)",0.0007); pr3638=gp("Production Ratio 36Ar/38Ar(cl)",0.0)
    a36a=_sf(ar[2]);a36as=_sf(ar[3]);a36ca=_sf(ar[4]);a36cas=_sf(ar[5])
    a37ca=_sf(ar[8]);a37cas=_sf(ar[9])
    a38m=_sf(ar[10]);a38ms=_sf(ar[11])
    a39k=_sf(ar[18]);a39ks=_sf(ar[19]);a39ca=_sf(ar[20]);a39cas=_sf(ar[21])
    a39m=_sf(ar[16]);a39ms=_sf(ar[17])
    a40m=_sf(ar[22]);a40ms=_sf(ar[23])
    a40r=_sf(ar[24]);a40rs=_sf(ar[25])
    a40air=_sf(ar[26]);a40airs=_sf(ar[27])
    a40k=_sf(ar[28]);a40ks=_sf(ar[29])
    a36m=_sf(ar[0]);a36ms=_sf(ar[1])
    air_r=a36a*r38_36
    # BUG FIX B1: Quadrature error propagation for air_r ratio
    rel_err_a36a = (a36as/a36a) if a36a != 0 else 0
    rel_err_r38_36 = (r38_36s/r38_36) if r38_36 != 0 else 0
    air_rs = abs(air_r) * math.sqrt(rel_err_a36a**2 + rel_err_r38_36**2) if (rel_err_a36a != 0 or rel_err_r38_36 != 0) else 0

    ak_r=a39k*r38_39
    # BUG FIX B1: Quadrature error propagation for ak_r ratio
    rel_err_a39k = (a39ks/a39k) if a39k != 0 else 0
    rel_err_r38_39 = (r38_39s/r38_39) if r38_39 != 0 else 0
    ak_rs = abs(ak_r) * math.sqrt(rel_err_a39k**2 + rel_err_r38_39**2) if (rel_err_a39k != 0 or rel_err_r38_39 != 0) else 0
    a38cl=a38m-air_r-ak_r; a38cls=(a38ms**2+air_rs**2+ak_rs**2)**0.5
    F=_sf(ar[36]);Fs=_sf(ar[37]);G=_sf(ar[38]);Gs=_sf(ar[39])
    B=_sf(ar[40]);Bs=_sf(ar[41]);D=_sf(ar[42]);Ds=_sf(ar[43])
    J=_sf(ar[44]);Js=_sf(ar[45]);Ji=_sf(ar[48])
    Ts=_sf(ar[46]);Tss=_sf(ar[47]);Ti=_sf(ar[49])
    age=Ts/1e6; ages=Tss/1e6
    CaK=(a39k*pr)/a37ca if a37ca!=0 else 1.0; CaKs=CaK*0.01
    # v3.8.24: row sized to 88 (was 98) — last 10 isochron columns removed to
    # align with NTNU_DataReduction DatumPublication output exactly.
    row=['0']*88
    row[0]=samp;row[1]=mineral;row[2]=irr;row[3]=str(temperature)
    row[4]=_fe(J);row[5]=_fe(Js);row[6]=_fe(Ji)
    row[7]=_fe(a36a);row[8]=_fe(a36as);row[9]=_fe(a37ca);row[10]=_fe(a37cas)
    row[11]=_fe(a38cl);row[12]=_fe(a38cls);row[13]=_fe(a39k);row[14]=_fe(a39ks)
    row[15]=_fe(a40r);row[16]=_fe(a40rs)
    row[17]='{:.6f}'.format(age);row[18]='{:.6f}'.format(ages)
    row[19]='{:.4f}'.format(a40r/a40m*100 if a40m!=0 else 0)
    row[20]='{:.4f}'.format(a39k/a39m*100 if a39m!=0 else 0)
    row[21]='{:.4f}'.format(ar40pct);row[22]='{:.4f}'.format(ar39pct)
    row[23]=_fe(CaK);row[24]=_fe(CaKs);row[25]=''
    row[26]=_fe(a36a);row[27]=_fe(a36as);row[28]='0.0';row[29]='0.0'
    row[30]=_fe(a36ca);row[31]=_fe(a36cas)
    row[32]=_fe(pr3638*a38cl);row[33]=_fe(abs(pr3638)*a38cls)
    row[34]=_fe(a37ca);row[35]=_fe(a37cas)
    row[36]=_fe(air_r);row[37]=_fe(air_rs);row[38]='0.0';row[39]='0.0'
    row[40]=_fe(ak_r);row[41]=_fe(ak_rs);row[42]='0.0';row[43]='0.0'
    row[44]=_fe(a38cl);row[45]=_fe(a38cls)
    row[46]=_fe(a39k);row[47]=_fe(a39ks);row[48]=_fe(a39ca);row[49]=_fe(a39cas)
    row[50]=_fe(a40r);row[51]=_fe(a40rs);row[52]=_fe(a40air);row[53]=_fe(a40airs)
    row[54]='0.0';row[55]='0.0';row[56]=_fe(a40k);row[57]=_fe(a40ks)
    row[58]='Additional Parameters'
    row[59]=_fe(F);row[60]=_fe(Fs)
    row[61]=_fe(a40r+a40air);row[62]=_fe((a40rs**2+a40airs**2)**0.5)
    row[63]=_fe(G);row[64]=_fe(Gs);row[65]=_fe(D);row[66]=_fe(Ds)
    row[67]=_fe(B);row[68]=_fe(Bs);row[69]='Parameters'
    pkeys=["Production Ratio 39Ar/37Ar(ca)","Production Ratio 39Ar/37Ar(ca) std",
           "Production Ratio 36Ar/37Ar(ca)","Production Ratio 36Ar/37Ar(ca) std",
           "Production Ratio 40Ar/39Ar(k)","Production Ratio 40Ar/39Ar(k) std",
           "Production Ratio 38Ar/39Ar(k)","Production Ratio 38Ar/39Ar(k) std",
           "Production Ratio 39Ar/37Ar(k)","Production Ratio 39Ar/37Ar(k) std",
           "Production Ratio 36Ar/38Ar(cl)","Production Ratio 36Ar/38Ar(cl) std",
           "Atmospheric Ratio 40/36(a)","Atmospheric Ratio 40/36(a) std",
           "Atmospheric Ratio 38/36(a)","Atmospheric Ratio 38/36(a) std"]
    for idx,key in enumerate(pkeys):
        try: row[70+idx]=params[pnames.index(key)]
        except: row[70+idx]='0'
    try: row[86]=params[pnames.index("λ for age calculation")]
    except: row[86]='5.49e-10'
    try: row[87]=params[pnames.index("numCycle")]
    except: row[87]='10'
    # v3.8.24: isochron columns (row[88]..row[97]) removed to match
    # NTNU_DataReduction DatumPublication format.
    return row


# ═══════════════════════════════════════════════════════════
#  PrefetchWorker — background combo-fit pre-computation
# ═══════════════════════════════════════════════════════════
class PrefetchWorker(QtCore.QThread):
    """v3.8.26: background QThread that pre-computes combo enumeration for
    every (step, isotope) pair after blank+signal load. Each emitted result
    lands in CalcT0Page._prefetch_cache so subsequent step switches skip
    the ~4 s/isotope curve_fit loop and feel instant.

    Scipy curve_fit releases the GIL inside its C/Fortran inner loop, so
    running this in a background QThread keeps the UI responsive while it
    grinds through ~12 step × 5 isotope × 848 fits = ~50 800 curve_fits.

    Cancellable via abort() — CalcT0Page calls this when the user loads a
    fresh dataset to avoid wasted work."""

    sig_one_done = QtCore.pyqtSignal(object, list)   # (cache_key, fits)
    sig_progress = QtCore.pyqtSignal(int, int)        # (done, total)
    sig_finished = QtCore.pyqtSignal()

    def __init__(self, tasks, fit, nc, parent=None):
        super().__init__(parent)
        # tasks: list of (cache_key, vt_array)
        self.tasks = tasks
        self.fit   = fit
        self.nc    = nc
        self._abort = False

    def abort(self):
        self._abort = True

    def run(self):
        try:
            total = len(self.tasks)
            for idx, (key, vt) in enumerate(self.tasks):
                if self._abort: return
                fits = _enumerate_combos_simple(vt, self.fit, self.nc)
                if self._abort: return
                self.sig_one_done.emit(key, fits)
                self.sig_progress.emit(idx + 1, total)
            self.sig_finished.emit()
        except Exception:
            # Background work failure must not crash the GUI
            import traceback; traceback.print_exc()
            self.sig_finished.emit()


class PipelineWorker(QtCore.QThread):
    sig_prog=QtCore.pyqtSignal(str)
    sig_warn=QtCore.pyqtSignal(str)
    sig_done=QtCore.pyqtSignal(dict)
    sig_err =QtCore.pyqtSignal(str)

    def __init__(self,blank_csv,sig_csvs,params,pnames,out_dir):
        super().__init__()
        self.blank_csv=blank_csv; self.sig_csvs=sig_csvs
        self.params=params; self.pnames=pnames; self.out_dir=out_dir

    def run(self):
        try: self._run()
        except Exception as e:
            import traceback; self.sig_err.emit(str(e)+'\n\n'+traceback.format_exc())

    def _run(self):
        out=self.out_dir
        mr_d=os.path.join(out,'MassRatio'); os.makedirs(mr_d,exist_ok=True)
        ac_d=os.path.join(out,'Agecalc');   os.makedirs(ac_d,exist_ok=True)
        dp_d=os.path.join(out,'Publish');   os.makedirs(dp_d,exist_ok=True)
        # v3.8.25: diagram PNGs moved out of Data/Figures/ and into
        # Figures/Publish/StepHeating/ (relative to work_dir, not out_dir)
        # to align with NTNU_DataReduction line 4885 path convention:
        #     screenshot_folder + 'Publish/StepHeating/'
        # where screenshot_folder = 'Figures/'.
        # fig_d is computed later (after work_dir is known, near line 4216).
        OGD=self.params[self.pnames.index('OG Date')]
        J=float(self.params[self.pnames.index('J value')])
        Js=float(self.params[self.pnames.index('J std')])
        Ji=float(self.params[self.pnames.index('J int')])
        consts=[float(x) for x in self.params]
        
        # Extract date info from first signal file
        date_info = {}
        first_csv = list(self.sig_csvs.values())[0] if self.sig_csvs else None
        if first_csv:
            try:
                with open(first_csv, 'r') as f:
                    lines = f.readlines()
                    if len(lines) > 1:
                        parts = lines[1].split(',')
                        if len(parts) >= 4:
                            from datetime import date
                            import re
                            import logging
                            # Fix: handle non-zero-padded dates like '2023/4/18'
                            spd_parts = parts[3].strip().split('/')
                            SPD = date(int(spd_parts[0]), int(spd_parts[1]), int(spd_parts[2]))
                            # BUG FIX B4: OGD date parsing - support both - and / separators
                            try:
                                ogd_str = re.sub(r'[-/]', '', OGD.strip())
                                OGD_date = date(int(ogd_str[0:4]), int(ogd_str[4:6]), int(ogd_str[6:8]))
                                days = (SPD - OGD_date).days
                                date_info = {
                                    'SPD': SPD.strftime('%Y-%m-%d'),
                                    'OGD': OGD_date.strftime('%Y-%m-%d'),
                                    'days': days
                                }
                            except (ValueError, IndexError) as e:
                                # Log warning if OGD parsing fails, don't fail silently
                                logging.warning(f"Failed to parse OGD date: {OGD}")
                                date_info = {}
            except: pass
        
        steps=[]; warns=[]
        for nm,sig_csv in self.sig_csvs.items():
            self.sig_prog.emit(f'Mass Ratio {nm}...')
            try: mr=Utilities.calculateMassRatio(sig_csv,self.blank_csv,OGD)
            except Exception as e: self.sig_err.emit(f'MassRatio {nm}: {e}'); return
            mr_csv=os.path.join(mr_d,nm+'.csv')
            with open(mr_csv,'w') as f:
                f.write("Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma\n")
                for i in range(5):
                    f.write(f"{mr[5]},{mr[6]},{mr[7]},{mr[8]},Ar{i+36},{mr[0][i]},{mr[1][i]},{mr[2][i]},"
                            f"{['Ar39/40','Ar36/40','Ar39/36','Ar40/36','Ar38/36'][i]},{mr[3][i]},{mr[4][i]}\n")
            step={'name':nm,'raw':list(mr[0]),'net':list(mr[1]),'sigma':list(mr[2]),
                  'ratio':list(mr[3]),'ratio_sigma':list(mr[4]),'mr_csv':mr_csv,
                  'decay_note':'37Ar/39Ar decay corr.','date_info':date_info}
            for ai,(a,net) in enumerate(zip([36,37,38,39,40],mr[1])):
                if net<=0: warns.append(f'Ar{a} @{nm}')
            steps.append(step)
        if warns: self.sig_warn.emit('Net values ≤0:\n'+'\n'.join(warns))
        ar_list=[]; s39=0.0; s40=0.0
        for step in steps:
            self.sig_prog.emit(f'Age Calc {step["name"]}...')
            try: ar=Utilities.calcAge(step['mr_csv'],J,Js,Ji,consts)
            except Exception as e: self.sig_err.emit(f'AgeCalc {step["name"]}: {e}'); return
            ar_list.append(ar); s39+=_sf(ar[18]); s40+=_sf(ar[24])
        s39=s39 or 1e-30; s40=s40 or 1e-30
        datum_rows=[]
        for step,ar in zip(steps,ar_list):
            step['age_result']=ar
            neg=[]
            if _sf(ar[24])<0: neg.append(f'40Ar(r)={_sf(ar[24]):.3e}')
            if _sf(ar[18])<0: neg.append(f'39Ar(K)={_sf(ar[18]):.3e}')
            if _sf(ar[2]) <0: neg.append(f'36Ar(air)={_sf(ar[2]):.3e}')
            step['neg_datum']=neg
            if neg: self.sig_warn.emit(f'Negative datum at {step["name"]}:\n'+', '.join(neg))
            # v3.8.24: also pull Min (mineral name) from mr_csv col 2 so the
            # downstream Datum row gets 'Muscovite' / 'Mus' instead of the step
            # temperature.  Mirrors NTNU_DataReduction line 5347:
            #     row[1] = lines[1].split(',')[2]  # Min
            temperature=step['name']; mineral_from_csv=''
            try:
                with open(step['mr_csv']) as f: lines=f.readlines()
                if len(lines)>1:
                    _parts=lines[1].split(',')
                    if len(_parts)>1: temperature=_parts[1]
                    if len(_parts)>2: mineral_from_csv=_parts[2].strip()
            except: pass
            ac_csv=os.path.join(ac_d,step['name']+'.csv')
            vnm=['Ar_36_m','Ar_36_m_std','Ar_36_Air','Ar_36_Air_std','Ar_36_Ca','Ar_36_Ca_std',
                 'Ar_37_m','Ar_37_m_std','Ar_37_Ca','Ar_37_Ca_std',
                 'Ar_38_m','Ar_38_m_std','Ar_38_Air','Ar_38_Air_std','Ar_38_K','Ar_38_K_std',
                 'Ar_39_m','Ar_39_m_std','Ar_39_K','Ar_39_K_std','Ar_39_Ca','Ar_39_Ca_std',
                 'Ar_40_m','Ar_40_m_std','Ar_40_r','Ar_40_r_std','Ar_40_air','Ar_40_air_std',
                 'Ar_40_K','Ar_40_K_std',
                 'Ar_39_K/Ar_40_r','Ar_39_K/Ar_40_r_std','Ar_36_Air/Ar_40_r','Ar_36_Air/Ar_40_r_std',
                 'Ar_39_K/Ar_36_Air','Ar_39_K/Ar_36_Air_std',
                 'F(Ar_40_r/Ar_39_K)','F(Ar_40_r/Ar_39_K)_std',
                 'G(Ar_40_m/Ar_39_m)','G(Ar_40_m/Ar_39_m)_std',
                 'B(Ar_36_m/Ar_39_M)','B(Ar_36_m/Ar_39_M)_std',
                 'D(Ar_37_m/Ar_39_m)','D(Ar_37_m/Ar_39_m)_std',
                 'J','J_std','T','T_std','J_int','T_int','Ar_40_r_ratio',
                 'C1_40/36(a)','C2_36/37(ca)','C3_40/39(k)','C4_39/37(ca)']
            sid=ar[-4] if len(ar)>57 else step['name']
            # v3.8.24: prefer mr_csv col 2 (mineral name) over ar[-3] — calcAge
            # was returning the step temperature in ar[-3] instead of mineral,
            # so the Datum 'Min' column was getting '1150' / '1200' instead of
            # 'Muscovite'.
            mn=mineral_from_csv if mineral_from_csv else (ar[-3] if len(ar)>57 else '')
            irr=ar[-1] if len(ar)>57 else ''
            with open(ac_csv,'w',newline='',encoding='utf-8') as f:
                w=csv.writer(f,lineterminator='\n')
                w.writerow(['Samp#','t','Min','IRR','Variable','Value','Sigma'])
                for i,nm_ in enumerate(vnm):
                    val=ar[i] if i<len(ar) else 0
                    w.writerow([sid,temperature,mn,irr,nm_,
                                 '{:.6e}'.format(float(val)) if isinstance(val,(int,float)) else str(val),''])
            step['ac_csv']=ac_csv
            ar39p=_sf(ar[18])/s39*100; ar40p=_sf(ar[24])/s40*100
            info_t=(str(sid),str(mn),'',str(temperature),str(irr))
            datum_rows.append(_build_datum_row(ar,info_t,temperature,self.params,self.pnames,ar39p,ar40p))
        sid=steps[0]['age_result'][-4] if steps and len(steps[0]['age_result'])>57 else 'sample'
        datum_csv=os.path.join(dp_d,str(sid)+'_datum.csv')
        with open(datum_csv,'w',newline='',encoding='utf-8') as f:
            w=csv.writer(f,lineterminator='\n'); w.writerow(_DATUM_HEADER)
            for row in datum_rows: w.writerow(row)
        work_dir=os.path.dirname(os.path.realpath(__file__))
        mask_all=np.ones(len(steps))
        try: Utilities.getSHStatistics(datum_csv,mask_all,consts)
        except Exception as e: self.sig_warn.emit(f'getSHStatistics: {e}')
        try: Utilities.getDFStatistics_sh(datum_csv,mask_all,consts,'b','o',
                                          isochron_method='ols')
        except Exception as e: self.sig_warn.emit(f'getDFStatistics_sh: {e}')
        # v3.8.25: Figures/Publish/StepHeating/ (work_dir-relative) instead of
        # Data/Figures/ to match NTNU_DataReduction.line 4885.
        fig_d=os.path.join(work_dir,'Figures','Publish','StepHeating')
        os.makedirs(fig_d,exist_ok=True)
        for key in ['DFW','DFA','DFN','DFI']:
            src=os.path.join(work_dir,'.work',key+'.png')
            if os.path.exists(src): shutil.copyfile(src,os.path.join(fig_d,str(sid)+'_'+key+'.png'))
        self.sig_prog.emit('Done')
        # v3.8.5: include consts so AgeCalcPage can re-run getDFStatistics_sh
        # when the isochron_method dropdown changes.
        self.sig_done.emit({'steps':steps,'datum_csv':datum_csv,
                            'work_dir':work_dir,'consts':consts})

# ═══════════════════════════════════════════════════════════
#  AutoPipelineWindow  — main window
# ═══════════════════════════════════════════════════════════
class AutoPipelineWindow(QtWidgets.QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('pyADR — Auto Pipeline')
        self._params=self._pnames=None; self._nc=10; self._worker=None
        self._build(); self.setStyleSheet(_sheet())
        self.setMinimumSize(1280, 720)
        # 全螢幕模式（可用 Esc 退出）
        self.showFullScreen()

    def set_context(self, params, pnames, nc=10):
        self._params=params; self._pnames=pnames; self._nc=nc
        # v3.8.4: sync module-level LAMBDA_K with parameters so isochron age
        # in AgeCalcPage uses the same λ as calcAge (avoids 0.2–1% systematic
        # mismatch between plateau and isochron ages).
        global LAMBDA_K
        try:
            LAMBDA_K = float(params[pnames.index('λ for age calculation')])
        except (ValueError, IndexError, TypeError):
            pass  # keep module default 5.49e-10

    def _show_help(self):
        """v3.8.6: open the shared Formulas & References help dialog.
        Delegates to NTNU_DataReduction._show_diagram_plot_help so both
        windows share the same content (single source of truth)."""
        try:
            import NTNU_DataReduction as _N
            _N._show_diagram_plot_help(self)
        except Exception as e:
            QtWidgets.QMessageBox.information(
                self, 'Help',
                f'Help dialog unavailable: {e}\n\n'
                'Documentation lives in NTNU_DataReduction.py '
                '(_show_diagram_plot_help function).')

    def _show_cycle_guide(self):
        """v3.8.17: scrollable rich-text dialog explaining the cycle 1-10
        button color scheme (MAD z-score tiers) and a practical selection
        strategy. Triggered by the Help → Cycle Selection Guide menu item.
        Content mirrors the user-facing chat reply so the in-app docs match
        what gets said in conversation."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Cycle Selection Guide — 按鈕顏色與挑選策略')
        dlg.setMinimumSize(720, 640)

        vl = QtWidgets.QVBoxLayout(dlg)
        vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)

        # Scrollable rich-text content
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('QScrollArea{background:white;border:none;}')

        body = QtWidgets.QLabel()
        body.setTextFormat(QtCore.Qt.RichText)
        body.setWordWrap(True)
        body.setAlignment(QtCore.Qt.AlignTop)
        body.setMargin(20)
        body.setStyleSheet('background:white;color:#222;font-size:13px;')

        # Build HTML — colored badges mirror MvCanvas._cs() actual styles.
        def badge(bg, brd, txt_col, label):
            return (f'<span style="display:inline-block;background:{bg};'
                    f'border:1.5px solid {brd};color:{txt_col};'
                    f'padding:2px 10px;border-radius:3px;'
                    f'font-weight:bold;font-family:Courier New;">{label}</span>')

        b_blue  = badge('#d6e8f7', '#1a5fb4', '#1a5fb4', ' 5 ')
        b_amber = badge('#fff4d0', '#c0a020', '#8a6000', ' 5 ')
        b_red   = badge('#ffd6d6', '#b41a1a', '#a01010', ' 5 ')
        b_grey  = badge('#eeede8', '#bbbbbb', '#b41a1a', ' 5 ')

        html = f'''
<h2 style="color:#1a5fb4;margin-top:0;">Cycle 1-10 按鈕顏色（直觀版）</h2>

<p>每個按鈕的顏色 = <b>這個 cycle 偏離擬合線多嚴重</b>：</p>

<table cellspacing="0" cellpadding="8" style="border-collapse:collapse;width:100%;">
  <tr style="background:#f5f4f0;">
    <th style="border:1px solid #ccc;text-align:center;width:70px;">顏色</th>
    <th style="border:1px solid #ccc;text-align:left;">直觀解讀</th>
    <th style="border:1px solid #ccc;text-align:left;">數學意義</th>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;">{b_blue}</td>
    <td style="border:1px solid #ccc;">這點貼合，沒事</td>
    <td style="border:1px solid #ccc;">殘差正常（z &lt; 1.8 σ）</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;">{b_amber}</td>
    <td style="border:1px solid #ccc;">這點有點偏，要小心看</td>
    <td style="border:1px solid #ccc;">殘差偏大（1.8–3.0 σ）</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;">{b_red}</td>
    <td style="border:1px solid #ccc;">這點明顯離群，建議排除</td>
    <td style="border:1px solid #ccc;">殘差很大（≥ 3 σ），統計上 &lt; 0.3% 機率</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;">{b_grey}</td>
    <td style="border:1px solid #ccc;">你已經把它排除了</td>
    <td style="border:1px solid #ccc;">mask=0，不參與 fit</td>
  </tr>
</table>

<p style="margin-top:14px;background:#f8f8f0;padding:10px;border-left:3px solid #c0a020;">
z 用 <b>MAD（median absolute deviation）</b>算，不是普通 std。好處：單一極端值不會把分母拉爆，紅色判斷比較「真實」，不會因為自己是 outlier 卻把自己 normalize 掉。
</p>

<h2 style="color:#1a5fb4;border-top:2px solid #1a5fb4;padding-top:12px;">挑 cycle 的實戰策略</h2>

<h3 style="color:#b41a1a;">① 先排紅色（強制）</h3>
<p>紅色幾乎一定是 mass-spec 突波、訊號跳動，或前 1–2 cycle 還沒穩定。
<b>直接點掉，不要猶豫</b>。</p>

<h3 style="color:#8a6000;">② 黃色看情況決定</h3>
<table cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;">
  <tr style="background:#f5f4f0;">
    <th style="border:1px solid #ccc;text-align:left;">黃色排掉後</th>
    <th style="border:1px solid #ccc;text-align:left;">該怎麼做</th>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;">n 還有 ≥ 7 → R² 變高、err 變小</td>
    <td style="border:1px solid #ccc;"><b>排掉</b>，比較乾淨</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;">n 已經剩 ≤ 5</td>
    <td style="border:1px solid #ccc;"><b>留著</b>，n 太少 σ 反而不穩</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;">排掉後 R²、err 沒明顯改善</td>
    <td style="border:1px solid #ccc;"><b>留著</b>，沒必要硬排</td>
  </tr>
</table>

<h3 style="color:#1c7a3a;">③ 用 scatter 圖的 "Best per n" 對照</h3>
<p>scatter 圖底下 [10][9][8][7][6][5][4] 按鈕：</p>
<ul>
  <li><span style="background:#d0edda;border:1.5px solid #1c7a3a;padding:1px 6px;color:#1c7a3a;font-weight:bold;">綠色</span> 那顆 = 全部 C(10, n) 組合裡 σ 最小的 n（演算法挑的最佳）</li>
  <li>點下去 → 自動套用那個 n 的最佳 mask</li>
</ul>

<p><b>策略</b>：先看綠色顯示在哪個 n（通常 n=8–10），點下去看 mV chart 兩條虛線：</p>
<ul>
  <li><span style="color:#e67e00;font-weight:bold;">━ ━</span> 橘虛線 = 全部 10 點 fit</li>
  <li><span style="color:#1c7a3a;font-weight:bold;">━ ━</span> 綠虛線 = 你選的 subset fit</li>
</ul>
<p>兩條應該 <b>接近平行</b>。差很多 → 代表排掉的點影響太大，要重新檢查。</p>

<h3 style="color:#9b59b6;">④ scatter 圖標記讀法</h3>
<table cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;">
  <tr style="background:#f5f4f0;">
    <th style="border:1px solid #ccc;text-align:center;width:80px;">符號</th>
    <th style="border:1px solid #ccc;text-align:left;">含義</th>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;color:#e67e00;font-size:18px;">▲</td>
    <td style="border:1px solid #ccc;">你 <b>目前</b> 選的 mask</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;color:#9b59b6;font-size:18px;">◆</td>
    <td style="border:1px solid #ccc;">物理 valid 範圍內 36Ar_air 最小（最逼近大氣值）— 只有 Ar36 顯示</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;color:#1f77b4;font-size:18px;">●</td>
    <td style="border:1px solid #ccc;">全部 C(10, k) 組合，按 n_used 上色（n=10 藍、n=9 綠…）</td>
  </tr>
  <tr>
    <td style="border:1px solid #ccc;text-align:center;color:#cccccc;font-size:18px;">●</td>
    <td style="border:1px solid #ccc;">不符合物理條件（如 36Ar_air ≤ 0），不可用</td>
  </tr>
</table>
<p>選 cycle 時看：<b>你的橘三角應該落在點雲的左下角</b>（小 T₀ + 小 σ）。如果落在右上，代表你選的 mask 不是好選擇。</p>

<h3 style="color:#444;">⑤ 別過度修剪</h3>
<ul>
  <li>R² = 0.0 並 <b>不一定</b> 代表 fit 不好 — 數據本身可能就是水平線（mass-spec 訊號穩定），σ 仍然有效</li>
  <li>一個 cycle 黃色但所有指標都還 OK → 不必硬排</li>
  <li><b>目標是讓 fit 反映物理真相，不是讓 R² 變漂亮</b></li>
</ul>

<h2 style="color:#1a5fb4;border-top:2px solid #1a5fb4;padding-top:12px;">Auto Blank / Auto Signal 邏輯</h2>

<p>左側 sidebar 上 <b>Auto Blank</b> 和 <b>Auto Signal</b> 兩個按鈕呼叫 <code>Utilities.calculateT0()</code>（跟 NTNU_DataReduction 的 CalcT0Page 子程式 <b>同一個函式</b>，行為一致）。流程：</p>

<h3 style="color:#1c7a3a;">Auto Blank</h3>
<ol>
  <li>對 blank.dat 5 個同位素各跑 <b>linear fit on full 10 cycles</b>，求 T₀ 與 σ（σ = std(|r|)/√n）。</li>
  <li>若 <b>R² &lt; 0.8</b>，啟動 outlier removal loop：
    <ul>
      <li>逐 cycle 計算殘差 r = v − f(t, popt)</li>
      <li>若 |r| &gt; σ，標記為 outlier（mask=0），<b>重新 fit</b> 剩下的點</li>
      <li>最多排 4 個（保留 ≥ 6 個 cycle）</li>
    </ul>
  </li>
  <li>R² ≥ 0.8 的同位素 → 全部 10 點留著，不動。</li>
  <li>更新 _bT0[5] / _bSIG[5]，blank canvas 重繪。</li>
</ol>

<h3 style="color:#9b59b6;">Auto Signal</h3>
<ol>
  <li>先呼叫 <code>_calc_blank_t0()</code> 把當前 blank mask 算出的 T₀ 鎖定。</li>
  <li>對每個 sample step（如 700°C, 800°C, ..., 1400°C）<b>獨立</b> 跑與 Auto Blank 完全相同的 outlier 機制（每個同位素 R²&lt;0.8 才啟動 outlier removal）。</li>
  <li>每個 step 的 mask 寫進 <code>_smask[nm]</code>，後續可在 step tabs 之間切換檢視。</li>
</ol>

<p style="background:#fff4d0;padding:10px;border-left:3px solid #c0a020;">
<b>注意</b>：Auto Blank/Signal 的 outlier threshold 是 |r| &gt; σ，<b>比手動 cycle button</b> 的 z-score MAD 判定<b>寬鬆</b>（手動是 z ≥ 1.8 才標黃、z ≥ 3.0 才標紅）。所以 Auto 跑出來的結果，可能還有藍色但偏黃的 cycle 留在裡面，那些可手動進一步排除。
</p>

<p><b>什麼時候用 Auto vs Manual？</b></p>
<ul>
  <li><b>Auto Blank/Signal</b> = 一鍵跑全部，速度快，適合先看整體脈絡，當作起點。</li>
  <li><b>Manual</b> 模式（按 Manual 按鈕後啟動）= 你可以點 cycle button 或 scatter 圖上的點來細調，適合 Auto 結果不理想時 fine-tune。</li>
  <li>建議流程：<b>Auto Signal → 切換到各 step 檢查 → 看顏色 + scatter 橘三角位置 → 需要時切 Manual fine-tune</b>。</li>
</ul>

<h2 style="color:#1a5fb4;border-top:2px solid #1a5fb4;padding-top:12px;">一句話 SOP</h2>
<p style="background:#eef5ff;padding:12px;border-left:4px solid #1a5fb4;font-size:14px;">
<b>Auto Blank → Auto Signal → 紅色全排 → 看 scatter 綠色 best 點哪個 n → 點下去 → 看 mV chart 兩條虛線是否平行 → 不平行就手動 fine-tune（多看黃色幾顆）→ 確認橘三角落在點雲左下。</b>
</p>

<p style="color:#888;font-size:11px;margin-top:18px;">
v3.8.18 — 顏色閾值定義於 <code>MvCanvas._cs()</code>，z-score 演算於 <code>_cycle_z_scores()</code>；
Auto Blank/Signal 走 <code>Utilities.calculateT0()</code>（與 CalcT0Page 子程式共用）。
</p>
'''
        body.setText(html)

        scroll.setWidget(body)
        vl.addWidget(scroll, 1)

        # Close button row
        btn_w = QtWidgets.QWidget()
        btn_w.setStyleSheet(f'background:{BG};border-top:1px solid {BRD};')
        btn_l = QtWidgets.QHBoxLayout(btn_w)
        btn_l.setContentsMargins(12, 8, 12, 8)
        btn_l.addStretch()
        btn = QtWidgets.QPushButton('Close')
        btn.setFixedSize(80, 28)
        btn.clicked.connect(dlg.accept)
        btn_l.addWidget(btn)
        vl.addWidget(btn_w)

        dlg.exec_()

    def _build(self):
        cw=QtWidgets.QWidget(); self.setCentralWidget(cw)
        vb=QtWidgets.QVBoxLayout(cw); vb.setContentsMargins(0,0,0,0); vb.setSpacing(0)

        # v3.8.6: top menu bar with Main (return) + Help (formulas / refs).
        _mb = self.menuBar()
        _menu_main = _mb.addMenu('Main')
        self._actGoHome = QtWidgets.QAction('Return to pyADR Home', self)
        _menu_main.addAction(self._actGoHome)
        # Hook: NTNU_DataReduction.py wires actGoHome to toMain via returnBtn
        # signal (existing pattern); to avoid breaking that, the menu action
        # just emits the same signal as the existing returnBtn click.
        self._actGoHome.triggered.connect(lambda: self.returnBtn.click()
                                          if hasattr(self, 'returnBtn') else None)
        _menu_help = _mb.addMenu('Help')
        _act_help = QtWidgets.QAction('Formulas && References', self)
        _menu_help.addAction(_act_help)
        _act_help.triggered.connect(self._show_help)
        # v3.8.17: cycle button color tier + selection strategy guide.
        _act_cycle_guide = QtWidgets.QAction('Cycle Selection Guide', self)
        _menu_help.addAction(_act_cycle_guide)
        _act_cycle_guide.triggered.connect(self._show_cycle_guide)

        # Top bar: Mode/Fit/Blank/Signal chips + Pipeline progress + Run button
        # v3.8.21: pipeline moved BACK inside top_bar (was a separate strip in
        # v3.8.20), occupying the space between Δt chip and Run Pipeline button.
        # top_bar height 65 → 80 to fit the larger pipeline visuals.
        top_bar = QtWidgets.QWidget()
        top_bar.setStyleSheet(f'background:{PNL};border-bottom:2px solid {BRD};')
        top_bar.setFixedHeight(80)
        tbl = QtWidgets.QHBoxLayout(top_bar)
        tbl.setContentsMargins(12,6,12,6); tbl.setSpacing(10)
        
        # Left: Mode/Fit/Blank/Signal chips (字體放大 1.7x)
        # v3.8.18: 'Δt' chip added right of 'Current step'. Displays the
        # auto-computed OG→Sample-Project days gap, populated by
        # CalcT0Page._auto_update_delta_t via self._chips['Δt'].setText().
        self._nav_chips = {}
        self._nav_chip_widgets = []  # Store chip widgets for hiding
        for key in ['Mode','Fit','Blank file','Signal','Current step','Δt']:
            chip = QtWidgets.QWidget()
            chip.setStyleSheet(f'background:#eeede8;border:1px solid {BRD};border-radius:3px;')
            cl = QtWidgets.QVBoxLayout(chip)
            cl.setContentsMargins(7,3,7,3); cl.setSpacing(1)
            lbl_k = QtWidgets.QLabel(key)
            lbl_k.setStyleSheet(f'font-size:9px;color:{TXT3};background:transparent;border:none;')
            val_k = QtWidgets.QLabel('—')
            val_k.setStyleSheet(f'font-size:15px;font-weight:bold;font-family:Courier New;background:transparent;border:none;')
            cl.addWidget(lbl_k); cl.addWidget(val_k)
            tbl.addWidget(chip)
            self._nav_chips[key] = val_k
            self._nav_chip_widgets.append(chip)
        
        tbl.addStretch()

        # ═══ Inline pipeline (v3.8.21) ═══════════════════════════════════════
        # Lives inside top_bar between the chips and the Run Pipeline button.
        # Design:
        #   • Circle 22 px (filled blue if done/active, grey ring if pending)
        #   • Step name 12 px bold beneath circle (no DONE/ACTIVE/PENDING badge)
        #   • Thin 2 px connector lines, blue if both endpoints are blue
        #   • No checkmark icons — just solid blue / grey circles
        # Click anywhere on a step card → _pipe_click(idx): idx 0 = navigate to
        # T₀ page; idx 1 / 2 = run pipeline then land on that page.
        pipe_container = QtWidgets.QWidget()
        pipe_container.setFixedSize(450, 68)
        self._pipe_circles = []
        self._pipe_labels  = []
        self._pipe_lines   = []
        # Status labels removed in v3.8.21 — keep an empty list for back-compat
        # so _refresh_pipe_visuals iteration logic doesn't need conditionals.
        self._pipe_status  = []
        self._state_done = {0: False, 1: False, 2: False}

        BLUE = '#1a5fb4'
        GREY = '#bbbbbb'

        step_names = ['Calculate T₀', 'Mass Ratio', 'Age Calc + Datum']
        circle_y    = 6
        circle_size = 22
        line_y      = circle_y + circle_size // 2 - 1   # center of circle, 2 px line
        # Card x positions: 3 evenly spaced over 450 px container.
        card_w   = 130
        card_gap = (450 - 3 * card_w) // 2   # ≈ 30 px between cards
        for i, name in enumerate(step_names):
            x = i * (card_w + card_gap)

            # ── Connector line to NEXT step (draw before circles so circles overlap) ──
            if i < 2:
                ln = QtWidgets.QLabel('', pipe_container)
                ln.setGeometry(
                    x + card_w // 2 + circle_size // 2,
                    line_y,
                    (card_w + card_gap) - circle_size,
                    2,
                )
                ln.setStyleSheet(f'background:{GREY};')
                self._pipe_lines.append(ln)

            # ── Circle indicator ──
            circle = QtWidgets.QLabel('●', pipe_container)
            circle.setGeometry(x + card_w // 2 - circle_size // 2, circle_y,
                               circle_size, circle_size + 4)
            circle.setAlignment(QtCore.Qt.AlignCenter)
            circle.setStyleSheet(
                f'color:{GREY};font-size:24px;font-weight:bold;'
                f'background:transparent;')
            circle.setCursor(QtCore.Qt.PointingHandCursor)
            circle.mousePressEvent = lambda e, idx=i: self._pipe_click(idx)
            self._pipe_circles.append(circle)

            # ── Step name below circle ──
            name_lbl = QtWidgets.QLabel(name, pipe_container)
            name_lbl.setAlignment(QtCore.Qt.AlignCenter)
            name_lbl.setGeometry(x, circle_y + circle_size + 6, card_w, 18)
            name_lbl.setStyleSheet(
                f'color:#666;font-size:12px;font-weight:bold;'
                f'background:transparent;')
            name_lbl.setCursor(QtCore.Qt.PointingHandCursor)
            name_lbl.mousePressEvent = lambda e, idx=i: self._pipe_click(idx)
            self._pipe_labels.append(name_lbl)

        tbl.addWidget(pipe_container)
        tbl.addStretch()

        # v3.8.21: Next button stays in top bar on the right.
        self.nextBtn = QtWidgets.QPushButton('Run Pipeline →')
        self.nextBtn.setStyleSheet(
            f'QPushButton{{background:#1a5fb4;color:white;border:1px solid #1a5fb4;'
            f'border-radius:4px;padding:8px 16px;font-size:13px;font-weight:bold;}}'
            f'QPushButton:hover{{background:#1c5fa0;}}'
            f'QPushButton:disabled{{background:#aaa;border-color:#aaa;}}')
        self.nextBtn.setFixedHeight(44)
        self.nextBtn.setEnabled(False)
        self.nextBtn.clicked.connect(self._next_action)
        tbl.addWidget(self.nextBtn)

        # v3.8.10: removed Output dir picker (Out: [Data/] 📁). Pipeline writes
        # to './Data/' relative to cwd (same as previous default).
        vb.addWidget(top_bar)

        # Stack
        self.stack=QtWidgets.QStackedWidget()
        self.t0Page=CalcT0Page()
        self.t0Page._chips = self._nav_chips   # wire chips to nav bar
        self.t0Page._chips['Mode'].setText('Auto')
        self.t0Page._chips['Fit'].setText('Linear')
        self.t0Page.nextBtn = self.nextBtn  # wire nextBtn from top bar
        self.t0Page.returnBtn.clicked.connect(self._ret)
        self.stack.addWidget(self.t0Page)
        self.mrPage=MassRatioPage()
        self.mrPage.nextBtn.clicked.connect(lambda: self._go(2))
        self.stack.addWidget(self.mrPage)
        self.agePage=AgeCalcPage()
        self.stack.addWidget(self.agePage)
        vb.addWidget(self.stack,1)
        self.statusBar().showMessage('Ready')
        self._go(0)

    def _go(self, idx):
        """Switch to the given page WITHOUT recomputing. Updates chip visibility,
        Next button text/enabled state, and the pipeline-strip visuals."""
        self.stack.setCurrentIndex(idx)

        # Hide nav chips on Mass Ratio (idx==1) and Age Calc (idx==2), show on T0
        for chip in self._nav_chip_widgets:
            chip.setVisible(idx == 0)

        # v3.8.20: Next button always functional — text reflects which action it
        # will take, but it's never the "Done / disabled" dead-end of before.
        # Enabled requires t0Page to have loaded files (the only true prereq).
        ready = self._t0_has_data()
        if idx == 0:
            self.nextBtn.setText('Run Pipeline →')
            self.nextBtn.setEnabled(ready)
        elif idx == 1:
            self.nextBtn.setText('↻ Recompute → Age Calc')
            self.nextBtn.setEnabled(ready)
        elif idx == 2:
            self.nextBtn.setText('↻ Recompute Pipeline')
            self.nextBtn.setEnabled(ready)

        self._refresh_pipe_visuals(idx)

    def _t0_has_data(self):
        """True if t0Page has at least blank + signal loaded — pipeline can run."""
        return (getattr(self.t0Page, '_bvt', None) is not None
                and bool(getattr(self.t0Page, '_svt', {})))

    def _refresh_pipe_visuals(self, current_idx):
        """v3.8.21 simplified rule: a step is BLUE if completed OR active,
        GREY otherwise. No checkmark — just solid filled circles. Connector
        line BLUE if both endpoints are blue, GREY otherwise.

        Idx 0 (T₀) is "completed" the moment data is loaded — there's no
        separate compute stage for it (T₀ fitting runs inside the worker
        alongside MR/Age)."""
        self._state_done[0] = self._t0_has_data()
        BLUE = '#1a5fb4'
        GREY = '#bbbbbb'

        # Per-circle blue flag
        is_blue = [None, None, None]
        for i in range(3):
            is_blue[i] = self._state_done[i] or (i == current_idx)

        for i in range(3):
            circle   = self._pipe_circles[i]
            name_lbl = self._pipe_labels[i]
            colour = BLUE if is_blue[i] else GREY
            text_col = BLUE if is_blue[i] else '#666666'
            circle.setText('●')
            circle.setStyleSheet(
                f'color:{colour};font-size:24px;font-weight:bold;'
                f'background:transparent;')
            name_lbl.setStyleSheet(
                f'color:{text_col};font-size:12px;font-weight:bold;'
                f'background:transparent;')
            if i < 2:
                line_col = BLUE if (is_blue[i] and is_blue[i + 1]) else GREY
                self._pipe_lines[i].setStyleSheet(f'background:{line_col};')

    def _pipe_click(self, idx):
        """Pipeline circle/card clicked. v3.8.20: navigate AND recompute.
          • idx 0: just navigate to T₀ page (interactive page, no auto-recompute)
          • idx 1: run pipeline → land on Mass Ratio page
          • idx 2: run pipeline → land on Age Calc page
        Requires t0Page to have data loaded; otherwise shows a warning."""
        if idx == 0:
            self._go(0)
            return
        if not self._t0_has_data():
            QtWidgets.QMessageBox.warning(
                self, 'Load files first',
                'Load blank + sample .dat files on the Calculate T₀ page '
                'before running the pipeline.')
            return
        # Worker thread might already be running — guard against re-entry.
        if getattr(self, '_worker', None) is not None and \
           self._worker.isRunning():
            self.statusBar().showMessage('Pipeline already running…')
            return
        self._target_after_run = idx
        self._run_pipeline()

    def _next_action(self):
        """Top bar Next button: always re-runs the pipeline (no more one-shot
        Done state). Target page after run is current+1, clamped to 2."""
        idx = self.stack.currentIndex()
        if not self._t0_has_data():
            QtWidgets.QMessageBox.warning(
                self, 'Load files first',
                'Load blank + sample .dat files on the Calculate T₀ page first.')
            return
        if getattr(self, '_worker', None) is not None and \
           self._worker.isRunning():
            self.statusBar().showMessage('Pipeline already running…')
            return
        # idx 0 → go to MR (1); idx 1 → go to Age (2); idx 2 → stay at Age (2)
        self._target_after_run = min(idx + 1, 2)
        self._run_pipeline()

    def _ret(self):
        try: self.parent().toMain()
        except: pass

    def _run_pipeline(self):
        # BUG FIX: B7 - Require set_context() to load parameters, prevent invalid standalone mode
        if self._params is None:
            QtWidgets.QMessageBox.critical(
                self, "Missing Parameters",
                "Parameters must be loaded via set_context() in NTNU_DataReduction.py.\n"
                "Please access AutoPipeline from the main program, not standalone mode."
            )
            return
        out = 'Data/'   # v3.8.10: hardcoded after Out picker removal
        blank_csv=self.t0Page.get_blank_csv(out)
        if blank_csv is None:
            QtWidgets.QMessageBox.warning(self,'Error','Load blank file first.'); return
        sig_csvs=self.t0Page.get_signal_csvs(out)
        if not sig_csvs:
            QtWidgets.QMessageBox.warning(self,'Error','Load sample files first.'); return
        self.statusBar().showMessage('Running pipeline...')
        # v3.8.20: disable Next button while worker is running so user can't
        # double-click. _on_done / sig_err handlers restore it.
        self.nextBtn.setEnabled(False)
        self.nextBtn.setText('Running…')
        self._worker=PipelineWorker(blank_csv,sig_csvs,self._params,self._pnames,out)
        self._worker.sig_prog.connect(self.statusBar().showMessage)
        self._worker.sig_warn.connect(lambda m: QtWidgets.QMessageBox.warning(self,'Warning',m))
        self._worker.sig_done.connect(self._on_done)
        self._worker.sig_err.connect(self._on_pipeline_err)
        self._worker.start()

    def _on_pipeline_err(self, msg):
        """Worker failed — restore Next button + show error dialog."""
        self.statusBar().showMessage('✗ Pipeline failed')
        # Restore Next button to whatever the current page wants it to say
        self._go(self.stack.currentIndex())
        QtWidgets.QMessageBox.critical(self, 'Pipeline Error', msg)

    def _on_done(self, res):
        self.mrPage.populate(res['steps'])
        self.agePage.populate(res['steps'],res['datum_csv'],res['work_dir'],
                              consts=res.get('consts'))
        self.statusBar().showMessage('✓ Done — '+res['datum_csv'])
        # v3.8.20: pipeline computes T0, MR, and Age all in one shot — mark all
        # three as done. Navigate to the target page the caller requested
        # (set by _pipe_click or _next_action) instead of always landing on MR.
        self._state_done[1] = True
        self._state_done[2] = True
        target = getattr(self, '_target_after_run', 1)
        self._go(target)
        # Reset target so a stale value doesn't carry over to the next run
        self._target_after_run = 1

    def load_files(self, blank_path, sample_paths):
        self.t0Page.load_blank(blank_path, self._nc)
        self.t0Page.load_signal(sample_paths, self._nc)
