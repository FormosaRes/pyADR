# ===============================================================================
# Copyright 2021 An-Jun Liu
# Last Modified Date: 12/28/2021
# ===============================================================================

# import python module
import sys
import os
from PyQt5 import QtCore, QtGui, QtWidgets

# v3.8.83: show the splash IMMEDIATELY — BEFORE the multi-second heavy imports
# (numpy, pandas, matplotlib, Utilities, AutoPipeline) — so launching pyADR
# gives instant visual feedback instead of a blank console while modules load.
# The QApplication created here is reused by App below via .instance(); the
# splash object is handed to App, which swaps in the version-overlaid pixmap.
_BOOT_APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
_BOOT_SPLASH = None
_BOOT_T0 = None
try:
    import time as _bt
    _sp = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.work', 'splash.png')
    if os.path.exists(_sp):
        _spm = QtGui.QPixmap(_sp)
        if not _spm.isNull():
            _spm = _spm.copy(0, 0, _spm.width(), 455)  # crop grey footer (v3.8.19)
            _BOOT_SPLASH = QtWidgets.QSplashScreen(_spm, QtCore.Qt.WindowStaysOnTopHint)
            _BOOT_SPLASH.setMask(_spm.mask())
            _BOOT_SPLASH.show()
            _BOOT_APP.processEvents()
            _BOOT_T0 = _bt.monotonic()
except Exception:
    _BOOT_SPLASH = None

import numpy as np
import requests
import shutil
from winotify import Notification
from tkinter import *
from datetime import date
import logging  # BUG FIX: A8 - Add logging support
import threading  # for background update check

# Setup logger
logger = logging.getLogger(__name__)

# import UI
import UI.HomePage
import UI.LinearRegression
import UI.T0Statistics
import UI.MassRatio
import UI.JCalculation
import UI.ReselectDialog
import UI.ParameterSetting
import UI.AirRatioStatistics
import UI.AgeCalculation
import UI.TypeSelect
import UI.SaltCalculation
import UI.JSelect
import UI.StatSelect
import UI.JStatistics
import UI.SaltSelect
import UI.SaltStatSelect
import UI.SaltStat
import UI.DiagramPlots_LS
import UI.DiagramPlots_SH
import UI.DiagramSelect 
import UI.DatumSelect

# import utilities
import Utilities
import AutoPipeline
import PlaneFit3D
import ExcelChartExporter  # V3.4.1: Excel native chart export


# v3.8.7: helper to add a standard "Return" button on the left edge of
# select-style sub-windows that didn't ship with one in their UI file.
# Matches the style/position used by other pages (return_2, QRect(0, 200, 91, 51)).
# The wrapper class still needs the App side to connect btn.clicked → toMain.
def _add_return_button(window, y=200):
    """Create window.return_2 button at standard left-side position. Idempotent."""
    if getattr(window, 'return_2', None) is not None:
        return
    if not hasattr(window, 'centralwidget'):
        return
    btn = QtWidgets.QPushButton(window.centralwidget)
    btn.setGeometry(QtCore.QRect(0, y, 91, 51))
    btn.setObjectName("return_2")
    btn.setText("Return")
    window.return_2 = btn


# v3.8.7: helper to keep buttons / title-label horizontally centered when the
# user resizes a select-style sub-window (TypeSelect, StatSelect, JSelect,
# SaltSelect, DiagramSelect, DatumSelect).  These UI files use absolute
# QRect positioning (x=210, button width 421, designed for an 800-px-wide
# window) so the buttons drift left when the window is resized larger.
# HomePage UI uses QHBoxLayout/addStretch already → this helper skips it.
def _make_select_page_responsive(window):
    """For each big QPushButton / QLabel in centralwidget, recompute its x
    so it stays horizontally centered when the window resizes.  No-op if
    centralwidget already has a layout (assume that layout handles it)."""
    cw = window.centralWidget()
    if cw is None or cw.layout() is not None:
        return

    def _targets():
        ts = []
        for w in cw.findChildren(QtWidgets.QPushButton):
            if w.geometry().width() > 100:
                ts.append(w)
        for w in cw.findChildren(QtWidgets.QLabel):
            if w.geometry().width() > 100:
                ts.append(w)
        return ts

    def _recenter():
        w_total = cw.width()
        if w_total <= 0:
            return
        for widget in _targets():
            geo = widget.geometry()
            widget.move((w_total - geo.width()) // 2, geo.y())

    _orig_resize = window.resizeEvent
    def _on_resize(event):
        _orig_resize(event)
        _recenter()
    window.resizeEvent = _on_resize
    # Deferred initial recenter — runs after Qt has done its first layout pass
    QtCore.QTimer.singleShot(0, _recenter)


# v3.8.6: shared help dialog used by DiagramPlot SH page + AutoPipeline window.
# Content focuses on what each displayed number means and which formula / paper
# it comes from — so users can defend the numbers in a paper / meeting.
def _show_diagram_plot_help(parent):
    """Open a tabbed Help dialog covering plateau / isochron / MSWD / age math."""
    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("pyADR — Formulas & References")
    dlg.resize(820, 640)
    lay = QtWidgets.QVBoxLayout(dlg)

    tabs = QtWidgets.QTabWidget()
    lay.addWidget(tabs)

    def _add_tab(title, html):
        w = QtWidgets.QTextBrowser()
        w.setOpenExternalLinks(True)
        w.setHtml(html)
        tabs.addTab(w, title)

    _add_tab("Plateau / WMA", _HELP_PLATEAU_HTML)
    _add_tab("Isochron",      _HELP_ISOCHRON_HTML)
    _add_tab("MSWD",          _HELP_MSWD_HTML)
    _add_tab("Age formula",   _HELP_AGE_HTML)
    _add_tab("Ar components", _HELP_AR_COMP_HTML)
    _add_tab("3D Plane Fit",  _HELP_PLANE3D_HTML)
    _add_tab("References",    _HELP_REFS_HTML)

    btn_close = QtWidgets.QPushButton("Close")
    btn_close.clicked.connect(dlg.accept)
    lay.addWidget(btn_close, 0, QtCore.Qt.AlignRight)
    dlg.exec_()


_HELP_PLATEAU_HTML = """
<h2>Weighted Mean Age (WMA) &amp; Plateau</h2>
<p>The plateau age summarises a contiguous block of step ages that are
mutually consistent within their analytical uncertainties.</p>
<h3>Weighted Mean Formula</h3>
<p style="margin-left:20px"><b>WMA = &Sigma;(T<sub>i</sub> / &sigma;<sub>i</sub><sup>2</sup>) /
&Sigma;(1 / &sigma;<sub>i</sub><sup>2</sup>)</b></p>
<p style="margin-left:20px"><b>&sigma;<sub>WMA, internal</sub> = 1 / &radic;&Sigma;(1/&sigma;<sub>i</sub><sup>2</sup>)</b></p>
<p>Equivalent to maximum-likelihood estimator under Gaussian errors.
Vermeesch (2018) IsoplotR Eq. 5; Schaen et al. (2021) GSA Bull. p.470.</p>
<h3>External &sigma; (Wendt &amp; Carl 1991)</h3>
<p>When MSWD &gt; 1, expand the internal &sigma; to capture excess scatter:</p>
<p style="margin-left:20px"><b>&sigma;<sub>WMA, external</sub> = &sigma;<sub>WMA, internal</sub> &middot; &radic;MSWD</b>
&nbsp;&nbsp;(only when MSWD &gt; 1)</p>
<p>If MSWD &le; 1, just use the internal &sigma;.</p>
<h3>Total Fusion Age</h3>
<p>Treat the whole sample as if degassed in one step.  Sum all radiogenic
<sup>40</sup>Ar and all K-derived <sup>39</sup>Ar:</p>
<p style="margin-left:20px"><b>F<sub>total</sub> = &Sigma;<sup>40</sup>Ar*<sub>i</sub> / &Sigma;<sup>39</sup>Ar<sub>K,i</sub></b></p>
<p style="margin-left:20px"><b>T<sub>total</sub> = ln(1 + J &middot; F<sub>total</sub>) / &lambda;</b></p>
<p>Equivalent to a K/Ar age — ignores step structure.  Useful as a
cross-check against plateau age.</p>
"""

_HELP_ISOCHRON_HTML = """
<h2>Isochron Regression</h2>
<p>An isochron is a mixing line between two end-members on a ratio plot.
Two parametrisations are common in Ar/Ar:</p>
<table border="1" cellpadding="6" cellspacing="0">
<tr><th></th><th>Normal isochron (DFN)</th><th>Inverse isochron (DFI)</th></tr>
<tr><td>X axis</td><td><sup>39</sup>Ar / <sup>36</sup>Ar</td><td><sup>39</sup>Ar / <sup>40</sup>Ar</td></tr>
<tr><td>Y axis</td><td><sup>40</sup>Ar / <sup>36</sup>Ar</td><td><sup>36</sup>Ar / <sup>40</sup>Ar</td></tr>
<tr><td>Y-intercept</td><td>(<sup>40</sup>/<sup>36</sup>)<sub>trapped</sub></td><td>(<sup>36</sup>/<sup>40</sup>)<sub>trapped</sub> = 1/(<sup>40</sup>/<sup>36</sup>)<sub>trapped</sub></td></tr>
<tr><td>Slope</td><td>F = <sup>40</sup>Ar* / <sup>39</sup>Ar<sub>K</sub></td><td>&minus;F &middot; (<sup>36</sup>/<sup>40</sup>)<sub>trapped</sub></td></tr>
<tr><td>F formula</td><td>F = slope</td><td><b>F = &minus;slope / intercept</b></td></tr>
</table>
<p>For Y = a + bX (York convention, a = intercept, b = slope):</p>
<p style="margin-left:20px">Normal:&nbsp;&nbsp; F = b</p>
<p style="margin-left:20px">Inverse: F = &minus;b / a&nbsp;&nbsp;(Vermeesch 2024 Eq. 2; Li &amp; Vermeesch 2021 Eq. 5)</p>
<h3>Regression methods (toggle in Plot Controls)</h3>
<p><b>OLS (Ordinary Least Squares)</b> &mdash; <code>scipy.curve_fit(linear, x, y)</code>.
Assumes &sigma;<sub>x</sub> = 0 (all error in Y).  Older Ar/Ar convention.</p>
<p><b>York 2004</b> &mdash; Bivariate weighted regression: accounts for
&sigma;<sub>x</sub>, &sigma;<sub>y</sub>, and their correlation per point.
Iteratively solves slope until convergence.  Schaen et al. (2021) Ar/Ar standard;
IsoplotR default.</p>
<p>York generally gives smaller-magnitude slope (when &sigma;<sub>x</sub> is
non-trivial) than OLS, so F and the resulting age can differ.  Toggle to compare.</p>
<h3>&sigma;<sub>F</sub> for inverse isochron</h3>
<p>F = &minus;b/a, so by Gaussian error propagation including
slope-intercept covariance:</p>
<p style="margin-left:20px"><b>&sigma;<sub>F</sub><sup>2</sup> = (&sigma;<sub>b</sub>/a)<sup>2</sup>
+ (b &middot; &sigma;<sub>a</sub> / a<sup>2</sup>)<sup>2</sup>
&minus; 2 (b/a<sup>3</sup>) &middot; cov(a, b)</b></p>
<p>cov(a, b) is typically negative for inverse isochrons (when slope steepens,
intercept drops), so the cross-term reduces &sigma;<sub>F</sub>.  pyADR computes
this from <code>pcov</code> (OLS) or York's analytical formula (Mahon 1996, Schaen 2021 Eq. 14b).</p>
"""

_HELP_MSWD_HTML = """
<h2>MSWD &mdash; two flavours, not interchangeable</h2>
<p>pyADR reports two MSWD numbers that look similar but measure different
things.  They can diverge for hetero / disturbed samples.</p>
<h3>Plateau MSWD &nbsp;<i>(right-panel stats)</i></h3>
<p style="margin-left:20px"><b>MSWD<sub>plateau</sub> = &Sigma;((T<sub>i</sub> &minus; WMA) /
&sigma;<sub>T,i</sub>)<sup>2</sup> / (N &minus; 1)</b></p>
<p>Measures the spread of step <i>ages</i> around the weighted-mean age.
Reflects age homogeneity (sample coherence in time).
df = N&minus;1 (one free parameter: the mean).</p>
<h3>Regression MSWD &nbsp;<i>(persistent label above DFN/DFI diagram)</i></h3>
<p style="margin-left:20px"><b>MSWD<sub>regression</sub> = &Sigma;((y<sub>i</sub> &minus; a &minus; b&middot;x<sub>i</sub>) /
&sigma;<sub>y,i</sub>)<sup>2</sup> / (N &minus; 2)</b></p>
<p>Measures the scatter of <i>data points</i> around the isochron line.
Reflects how well the linear mixing model fits the data.
df = N&minus;2 (slope + intercept).</p>
<h3>What different combinations imply</h3>
<table border="1" cellpadding="6" cellspacing="0">
<tr><th></th><th>MSWD<sub>plateau</sub> &asymp; 1</th><th>MSWD<sub>plateau</sub> &gt; 1</th></tr>
<tr><th>MSWD<sub>reg</sub> &asymp; 1</th><td>Ideal &mdash; well-behaved sample</td><td>Ages disagree but points fall on isochron line &mdash; trapped composition consistent, but ages dispersed (partial reset?)</td></tr>
<tr><th>MSWD<sub>reg</sub> &gt; 1</th><td>Step ages agree but points scatter on isochron &mdash; trapped composition varies between steps</td><td>Both spread &mdash; significant geological complexity (excess Ar, hetero, partial loss)</td></tr>
</table>
<h3>Critical MSWD</h3>
<p>Schaen et al. (2021) Eq. 2: <b>MSWD<sub>crit</sub> &asymp; 1 + 2&radic;(2/df)</b>.
For df = 8, MSWD<sub>crit</sub> &asymp; 2.0.  MSWD beyond this rejects the
assumption that scatter is purely analytical.</p>
<p>When MSWD &gt; 1, pyADR (per Wendt &amp; Carl 1991) expands the
internal &sigma; by &radic;MSWD to give an &ldquo;external&rdquo; &sigma; that
captures the excess dispersion.</p>
"""

_HELP_AGE_HTML = """
<h2>Ar/Ar Age Formula</h2>
<p>From the radioactive decay of <sup>40</sup>K to <sup>40</sup>Ar:</p>
<p style="margin-left:20px"><b>T = (1/&lambda;) &middot; ln(1 + J &middot; F)</b></p>
<table border="1" cellpadding="6" cellspacing="0">
<tr><th>Symbol</th><th>Meaning</th><th>Where it comes from</th></tr>
<tr><td>T</td><td>Age (yr)</td><td>What we want</td></tr>
<tr><td>&lambda;</td><td>Total <sup>40</sup>K decay constant (1/yr)</td><td>Read from <code>parameters.csv</code> &lsquo;&lambda; for age calculation&rsquo;.  pyADR default 5.49e-10 (between Steiger-J&auml;ger 1977 = 5.543e-10 and Renne 2010 = 5.5305e-10).</td></tr>
<tr><td>J</td><td>Irradiation parameter</td><td>From co-irradiated standards (J Calculation page).</td></tr>
<tr><td>F</td><td><sup>40</sup>Ar* / <sup>39</sup>Ar<sub>K</sub></td><td>From step (plateau path) or isochron slope (DFN/DFI).</td></tr>
</table>
<h3>&sigma;<sub>T</sub> propagation (Renne 2010 partial derivatives)</h3>
<p style="margin-left:20px"><b>&sigma;<sub>T</sub><sup>2</sup> = ((J &middot; &sigma;<sub>F</sub>)<sup>2</sup>
+ (F &middot; &sigma;<sub>J</sub>)<sup>2</sup>) / (&lambda;(1+JF))<sup>2</sup></b></p>
<p>pyADR does <i>not</i> include &sigma;<sub>&lambda;</sub> by default (typically &lt; 0.5% for
geologically young samples).</p>
<h3>Decay constants used elsewhere</h3>
<ul>
<li><b><sup>37</sup>Ar half-life</b> = 35.011 d (LAMBDA_37 in AutoPipeline).
  Used to back-correct interfering <sup>37</sup>Ar between irradiation and analysis.</li>
<li><b><sup>39</sup>Ar half-life</b> = 269 yr (LAMBDA_39).  Same purpose, much
  slower decay so usually negligible over months but corrected anyway.</li>
</ul>
"""

_HELP_AR_COMP_HTML = """
<h2>Ar isotope component breakdown</h2>
<p>From measured <sup>36, 37, 38, 39, 40</sup>Ar, pyADR deconvolves trapped,
production-related, and radiogenic components using <code>parameters.csv</code>
production ratios.</p>
<h3>Order of corrections (calcAge in Utilities.py)</h3>
<ol>
<li><b><sup>37</sup>Ar(Ca)</b> = measured <sup>37</sup>Ar &mdash; from Ca interference, decay-corrected to irradiation midpoint.</li>
<li><b><sup>36</sup>Ar(Ca)</b> = <sup>37</sup>Ar(Ca) &times; PR(<sup>36</sup>/<sup>37</sup>Ca)</li>
<li><b><sup>36</sup>Ar(air)</b> = measured <sup>36</sup>Ar &minus; <sup>36</sup>Ar(Ca).  (NTNU lab: <sup>36</sup>Ar(Cl) treated as negligible.)</li>
<li><b><sup>39</sup>Ar(Ca)</b> = <sup>37</sup>Ar(Ca) &times; PR(<sup>39</sup>/<sup>37</sup>Ca)</li>
<li><b><sup>39</sup>Ar(K)</b> = measured <sup>39</sup>Ar &minus; <sup>39</sup>Ar(Ca)</li>
<li><b><sup>40</sup>Ar(air)</b> = <sup>36</sup>Ar(air) &times; R(<sup>40</sup>/<sup>36</sup>)<sub>atm</sub>  &nbsp;(R = 298.56 by default)</li>
<li><b><sup>40</sup>Ar(K)</b> = <sup>39</sup>Ar(K) &times; PR(<sup>40</sup>/<sup>39</sup>K)</li>
<li><b><sup>40</sup>Ar*</b> = measured <sup>40</sup>Ar &minus; <sup>40</sup>Ar(air) &minus; <sup>40</sup>Ar(K)</li>
</ol>
<p>F = <sup>40</sup>Ar* / <sup>39</sup>Ar(K).  Age T = ln(1 + JF)/&lambda;.</p>
<h3>Ca/K ratio</h3>
<p style="margin-left:20px"><b>Ca/K = (<sup>37</sup>Ar(Ca) / <sup>39</sup>Ar(K)) &middot; R<sub>Ca/K</sub></b></p>
<p>R<sub>Ca/K</sub> = 0.52 in pyADR (NTNU reactor calibration, hardcoded).
Literature standard is 1.83 (McDougall &amp; Harrison 1999 Eq. 4.30) but
that's for a different reactor.</p>
"""

_HELP_PLANE3D_HTML = """
<h2>3D Plane Fit (PlaneFit3D.py)</h2>
<p>Alternative to 2D isochron projection: regress the data directly in
(³⁶Ar, ³⁹Ar, ⁴⁰Ar) space.  Avoids error accumulation from ratio computation
and lets you see the spatial structure of isotope systems within a sample.</p>
<p><b>Reference</b>: Kent et al. (1990) maximum-likelihood plane regression,
implemented per Wu C.-Y. (2007) NTU MSc thesis (R94224113, advisor Ching-Hua Lo).
Validation sample SYL31 (Sylhet Trap basalt, 115.4 ± 3.9 Ma).</p>
<h3>Plane equation</h3>
<p style="margin-left:20px">
<b><sup>40</sup>Ar = &alpha; &middot; <sup>36</sup>Ar + &beta; &middot; <sup>39</sup>Ar</b></p>
<ul>
<li><b>&alpha;</b> = (<sup>40</sup>Ar/<sup>36</sup>Ar)<sub>trapped</sub>
    &mdash; initial (air / inherited) composition (&asymp; 298.56 for pure air)</li>
<li><b>&beta;</b> = <sup>40</sup>Ar* / <sup>39</sup>Ar<sub>K</sub> = F &mdash;
    radiogenic-to-K ratio (feeds into the age formula)</li>
</ul>
<p>Age:&nbsp;&nbsp; <b>T = (1/&lambda;) &middot; ln(1 + &beta; &middot; J)</b></p>
<h3>Maximum-likelihood objective</h3>
<p>Each data point x<sub>i</sub> = (<sup>36</sup>Ar, <sup>39</sup>Ar, <sup>40</sup>Ar)
is modelled as N<sub>3</sub>(&mu;<sub>i</sub>, A<sub>i</sub>) where &mu;<sub>i</sub>
lies on the plane.  Define plane normal &gamma; = [&alpha;, &beta;, &minus;1]<sup>T</sup>:</p>
<p style="margin-left:20px">s<sub>i</sub> = &gamma;<sup>T</sup>x<sub>i</sub> = &alpha;&middot;<sup>36</sup>Ar<sub>i</sub> + &beta;&middot;<sup>39</sup>Ar<sub>i</sub> &minus; <sup>40</sup>Ar<sub>i</sub>&nbsp;&nbsp;(signed distance)</p>
<p style="margin-left:20px">q<sub>i</sub> = &gamma;<sup>T</sup>A<sub>i</sub>&gamma;&nbsp;&nbsp;(variance projected onto normal)</p>
<p>After Lagrange-multiplier elimination of &mu;<sub>i</sub> (Wu 2007 eq 3-5 → 3-7),
the <b>profile log-likelihood</b>:</p>
<p style="margin-left:20px"><b>L<sub>p</sub>(&delta;) = &minus;&frac12; &Sigma;<sub>i</sub> s<sub>i</sub>&sup2; / q<sub>i</sub></b>
&nbsp;&nbsp;where &delta; = [&alpha;, &beta;]<sup>T</sup></p>
<p>Maximising L<sub>p</sub> = weighted least squares with weights from all three isotope axes
(no axis preferred over others).</p>
<h3>Per-point covariance matrix A<sub>i</sub> (3×3)</h3>
<table border="1" cellpadding="6" cellspacing="0">
<tr><td>&sigma;<sub>36</sub>&sup2;</td><td>0</td><td>0</td></tr>
<tr><td>0</td><td>&sigma;<sub>39</sub>&sup2;</td><td>&minus;k<sub>0</sub>&middot;&sigma;<sub>39</sub>&sup2;</td></tr>
<tr><td>0</td><td>&minus;k<sub>0</sub>&middot;&sigma;<sub>39</sub>&sup2;</td><td>&sigma;<sub>40</sub>&sup2;</td></tr>
</table>
<p>where k<sub>0</sub> = PR(<sup>40</sup>Ar/<sup>39</sup>Ar)<sub>K</sub> (default 0.025004).
Off-diagonal cov(<sup>39</sup>, <sup>40</sup>) captures the anti-correlation from the
⁴⁰Ar(K) back-correction.</p>
<h3>Newton–Raphson optimisation</h3>
<p>Starting from OLS &delta;<sub>0</sub>, iterate:</p>
<p style="margin-left:20px"><b>&delta;<sub>k+1</sub> = &delta;<sub>k</sub> + H<sup>&minus;1</sup>&middot;g</b></p>
<p>with gradient g = &part;L<sub>p</sub>/&part;&delta; and Hessian H = &minus;&part;&sup2;L<sub>p</sub>/&part;&delta;&part;&delta;<sup>T</sup>
(positive-definite at the MLE, = observed Fisher information).</p>
<p><b>Backtracking line search</b> (pyADR v3.4 addition):
halve step up to 20× until L<sub>p</sub> strictly increases.  Prevents Newton overshoot.
Convergence: |&Delta;&delta;|/|&delta;| &lt; 10<sup>&minus;10</sup>.</p>
<h3>MSWD and 95% CI</h3>
<p style="margin-left:20px"><b>S&sup2; = &Sigma;<sub>i</sub> s<sub>i</sub>&sup2; / q<sub>i</sub>,&nbsp;&nbsp;&nbsp;
df = n &minus; 2,&nbsp;&nbsp;&nbsp; MSWD = S&sup2; / df</b></p>
<p>(Wu 2007 eq 3-24; Mahon 1996.)</p>
<p>95% CI computed exactly via &chi;<sup>2</sup><sub>df</sub> quantiles (scipy.stats.chi2),
not the normal approximation.  If MSWD &gt; upper bound, pyADR applies Wendt-Carl
&sigma;-expansion:</p>
<p style="margin-left:20px">&tau;&sup2; = MSWD,&nbsp;&nbsp; &sigma;<sub>&delta;</sub> &rarr; &radic;&tau;&sup2; &middot; &sigma;<sub>&delta;</sub></p>
<h3>Parameter covariance</h3>
<p style="margin-left:20px"><b>cov(&delta;&#x0302;) = &tau;&sup2; &middot; H<sup>&minus;1</sup></b></p>
<p>1&sigma; uncertainties: &sigma;<sub>&alpha;</sub> = &radic;cov<sub>11</sub>, &sigma;<sub>&beta;</sub> = &radic;cov<sub>22</sub>.</p>
<p style="background:#fff4d0;padding:6px;border:1px solid #c0a020;">
<b>&#9888; Wu (2007) eq 3-27 sign-error correction</b>: the thesis writes
cov(&delta;&#x0302;) = &tau;&sup2; &middot; (&part;&sup2;L<sub>p</sub>/&part;&delta;&part;&delta;<sup>T</sup>)<sup>&minus;1</sup>.
At the MLE, &part;&sup2;L<sub>p</sub> is <i>negative</i>-definite, so its inverse gives
<i>negative variances</i> &mdash; clearly wrong.  The correct ML asymptotic covariance is
&tau;&sup2; &middot; (&minus;&part;&sup2;L<sub>p</sub>/&part;&delta;&part;&delta;<sup>T</sup>)<sup>&minus;1</sup> = &tau;&sup2; &middot; H<sup>&minus;1</sup>.
pyADR uses the corrected form.</p>
<h3>Age error propagation (Renne 1998, Min 2000)</h3>
<p style="margin-left:20px"><b>&sigma;<sub>T</sub>&sup2; = (&part;T/&part;&beta;)&sup2; &sigma;<sub>&beta;</sub>&sup2;
+ (&part;T/&part;J)&sup2; &sigma;<sub>J</sub>&sup2;
+ (&part;T/&part;&lambda;)&sup2; &sigma;<sub>&lambda;</sub>&sup2;</b></p>
<p>with</p>
<ul>
<li>&part;T/&part;&beta; = J / [&lambda;(1 + &beta;J)]</li>
<li>&part;T/&part;J = &beta; / [&lambda;(1 + &beta;J)]</li>
<li>&part;T/&part;&lambda; = &minus;ln(1 + &beta;J) / &lambda;&sup2;</li>
</ul>
<h3>Mahon (1996) σ-cap (optional)</h3>
<p>For background-dominated steps where &sigma;<sub>i</sub>/|x<sub>i</sub>| &gt;&gt; 1, classical
Kent weights give those points outsize influence.  Set per-axis caps to limit:</p>
<p style="margin-left:20px"><b>&sigma;<sub>i,eff</sub> = min(&sigma;<sub>i</sub>, c &middot; |x<sub>i</sub>|)</b></p>
<p>Typical c = 0.2–0.5.  None (default) disables (classical Kent).</p>
<p>See FORMULAS.md §11 for full derivations.</p>
"""


_HELP_REFS_HTML = """
<h2>References</h2>
<h3>3D plane fit (PlaneFit3D.py)</h3>
<ul>
<li>Kent J.T., Watson G.S., Onstott T.C. (1990) <i>Maximum likelihood estimation
of a plane in three dimensions.</i> Statistics 21: 411&ndash;426.</li>
<li>Wu C.-Y. (2007) <i>3-D Plane-fitting Program in 40Ar/39Ar Dating.</i>
MSc thesis, NTU Geosciences (R94224113), advisor Ching-Hua Lo.  Math derivations
in Chapter 3.</li>
<li>Titterington D.M., Halliday A.N. (1979) <i>On the fitting of parallel isochrons
and the method of maximum likelihood.</i> Chem. Geol. 26: 183&ndash;195.</li>
<li>Mahon K.I. (1996) <i>The new "York" regression.</i> Int. Geol. Rev. 38: 293&ndash;303.
(MSWD &amp; modified weighting)</li>
<li>Renne P.R. et al. (1998) <i>Intercalibration of standards, absolute ages and
uncertainties in 40Ar/39Ar dating.</i> Chem. Geol. 145: 117&ndash;152.</li>
<li>Min K. et al. (2000) <i>A test for systematic errors in 40Ar/39Ar
geochronology.</i> GCA 64: 73&ndash;98.</li>
<li>Koppers A.A.P. (2002) <i>ArArCALC &mdash; software for 40Ar/39Ar age calculations.</i>
Comput. Geosci. 28: 605&ndash;619.</li>
</ul>
<h3>Isochron regression</h3>
<ul>
<li>York D., Evensen N.M., Mart&iacute;nez M.L., De Basabe Delgado J. (2004)
<i>Unified equations for the slope, intercept, and standard errors of the best straight line.</i>
Am. J. Phys. 72: 367&ndash;375.</li>
<li>Vermeesch P. (2018) <i>IsoplotR: A free and open toolbox for geochronology.</i>
Geoscience Frontiers 9: 1479&ndash;1493.  doi:10.1016/j.gsf.2018.04.001</li>
<li>Vermeesch P. (2024) <i>Errorchrons and anchored isochrons in IsoplotR.</i>
Geochronology 6: 397&ndash;407.  doi:10.5194/gchron-6-397-2024</li>
<li>Li Y., Vermeesch P. (2021) <i>Short communication: Inverse isochron regression
for Re&ndash;Os, K&ndash;Ca and other chronometers.</i> Geochronology 3: 415&ndash;420.
doi:10.5194/gchron-3-415-2021</li>
<li>Mahon K.I. (1996) <i>The new "York" regression: application of an improved
statistical method to geochemistry.</i> Int. Geol. Rev. 38: 293&ndash;303.
(slope-intercept covariance formula)</li>
</ul>
<h3>MSWD / weighted-mean statistics</h3>
<ul>
<li>Wendt I., Carl C. (1991) <i>The statistical distribution of the mean squared
weighted deviation.</i> Chem. Geol. 86: 275&ndash;285.
(&radic;MSWD external-&sigma; expansion)</li>
<li>Schaen A.J. et al. (2021) <i>Interpreting and reporting <sup>40</sup>Ar/<sup>39</sup>Ar
geochronologic data.</i> GSA Bulletin 133: 461&ndash;487.
doi:10.1130/B35560.1  (Ar/Ar community standard)</li>
</ul>
<h3>Ar/Ar method &amp; decay constants</h3>
<ul>
<li>McDougall I., Harrison T.M. (1999) <i>Geochronology and Thermochronology
by the <sup>40</sup>Ar/<sup>39</sup>Ar Method</i>, 2nd ed., Oxford University Press.
(Ar component math standard)</li>
<li>Renne P.R. et al. (2010) <i>Joint determination of <sup>40</sup>K decay constants and
<sup>40</sup>Ar*/<sup>40</sup>K for the Fish Canyon sanidine standard.</i> GCA 74: 5349&ndash;5367.
(modern &lambda; values)</li>
<li>Renne P.R. et al. (2011) <i>Response to the comment by W.H. Schwarz et al.
on "Joint determination of...".</i> GCA 75: 5097&ndash;5100.</li>
<li>Steiger R.H., J&auml;ger E. (1977) <i>Subcommission on geochronology: Convention
on the use of decay constants in geo- and cosmochronology.</i> EPSL 36: 359&ndash;362.
(historical &lambda; = 5.543e-10/yr)</li>
<li>Kuiper K.F. (2002) <i>The interpretation of inverse isochron diagrams in
<sup>40</sup>Ar/<sup>39</sup>Ar geochronology.</i> EPSL 203: 499&ndash;506.</li>
</ul>
<h3>Atmospheric composition</h3>
<ul>
<li>Lee J.-Y. et al. (2006) <i>A redetermination of the isotopic abundances of
atmospheric Ar.</i> GCA 70: 4507&ndash;4512.  (<sup>40</sup>Ar/<sup>36</sup>Ar = 298.56)</li>
</ul>
"""


# load UI
# ===============================================================================
class HomePage(QtWidgets.QMainWindow, UI.HomePage.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        
    #def resizeEvent(self, event):
        

class TypeSelect(QtWidgets.QMainWindow, UI.TypeSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)

class LinearRegressionPage(QtWidgets.QMainWindow, UI.LinearRegression.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        
    
    def resizeEvent(self, event):
        self.Isize = [100, 230, 670+event.size().width()-800, 450+event.size().height()-700]      
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        

class StatSelect(QtWidgets.QMainWindow, UI.StatSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)

class JStatistics(QtWidgets.QMainWindow, UI.JStatistics.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        
    def resizeEvent(self, event):
        self.Isize = [100, 230, 670+event.size().width()-800, 450+event.size().height()-700]      
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))

class T0Statistics(QtWidgets.QMainWindow, UI.T0Statistics.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)

    def resizeEvent(self, event):
        self.Isize = [150, 175, 600+event.size().width()-800, 250+event.size().height()-700]      
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        self.Tsize =[150, 470+event.size().height()-700, 591, 101]
        self.tableWidget.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        self.numSelectedFiles.setGeometry(QtCore.QRect(150, 580+event.size().height()-700, 200, 31))

class AirRatioStatistics(QtWidgets.QMainWindow, UI.AirRatioStatistics.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        
    def resizeEvent(self, event):
        self.Isize = [200, 200, 350+event.size().width()-800, 275+event.size().height()-700]      
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        self.Tsize =[210, 490+event.size().height()-700, 301, 111]
        self.RatioTable.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        self.numSelectedFiles.setGeometry(QtCore.QRect(150, 580+event.size().height()-700, 200, 31))
        
class MassRatio(QtWidgets.QMainWindow, UI.MassRatio.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)

class JCalculation(QtWidgets.QMainWindow, UI.JCalculation.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)

class JSelect(QtWidgets.QMainWindow, UI.JSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)

class ReselectTable(QtWidgets.QDialog, UI.ReselectDialog.Ui_Dialog):
    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.setupUi(self)

class ParameterSetting(QtWidgets.QMainWindow, UI.ParameterSetting.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        
    
    def resizeEvent(self, event):
        self.Tsize = [220, 200, 351+event.size().width()-800, 391+event.size().height()-700]       
        self.ParameetrTable.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))

class AgeCalculation(QtWidgets.QMainWindow, UI.AgeCalculation.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)

class SaltCalculation(QtWidgets.QMainWindow, UI.SaltCalculation.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
    
    def resizeEvent(self, event):
        self.Tsize =[200, 200, 445+event.size().width()-800, 90+event.size().height()-700]
        self.RatioTableCa.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        self.RatioTableK.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        
class SaltSelect(QtWidgets.QMainWindow, UI.SaltSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)

class SaltStat(QtWidgets.QMainWindow, UI.SaltStat.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        
    def resizeEvent(self, event):
        self.Isize = [150, 175, 600+event.size().width()-800, 250+event.size().height()-700]      
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        
class SaltStatSelect(QtWidgets.QMainWindow, UI.SaltStatSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)

class SmartSpinBox(QtWidgets.QDoubleSpinBox):
    """QDoubleSpinBox that strips trailing zeros from display."""
    def textFromValue(self, val):
        if val == 0.0:
            return "0"
        # g format: removes trailing zeros, switches to sci notation for very large/small
        s = f"{val:.8g}"
        return s

    def valueFromText(self, text):
        try:
            return float(text)
        except ValueError:
            return 0.0

    def validate(self, text, pos):
        # Accept any partial float input
        import re
        if re.fullmatch(r'-?\d*\.?\d*(e[+-]?\d*)?', text.strip(), re.IGNORECASE):
            try:
                float(text)
                return (QtGui.QValidator.Acceptable, text, pos)
            except ValueError:
                return (QtGui.QValidator.Intermediate, text, pos)
        return (QtGui.QValidator.Intermediate, text, pos)


class DiagramPlots_SH(QtWidgets.QMainWindow, UI.DiagramPlots_SH.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        self.photo.setScaledContents(True)  # ensure image fills widget for correct coord mapping
        self.A.setText("Ca/K")  # rename from K-Ca plateau

        # v3.8.6: Main + Help menu bar.  Empty menubar pre-existed (UI.DiagramPlots_SH
        # has setMenuBar but no items).  Populate it here so we don't touch the
        # auto-generated UI file.
        self.menuMain = self.menubar.addMenu("Main")
        self.actionGoHome = QtWidgets.QAction("Return to pyADR Home", self)
        self.menuMain.addAction(self.actionGoHome)
        self.menuHelp = self.menubar.addMenu("Help")
        self.actionHelpFormulas = QtWidgets.QAction("Formulas && References", self)
        self.menuHelp.addAction(self.actionHelpFormulas)
        self.actionHelpFormulas.triggered.connect(
            lambda: _show_diagram_plot_help(self))

        # Info label at top (for mouse hover info)
        self.infoLabel = QtWidgets.QLabel("  ← hover over a step to see info", self.centralwidget)
        self.infoLabel.setObjectName("infoLabel")
        self.infoLabel.setStyleSheet(
            "QLabel { background-color: #f5f5f5; color: #222; "
            "padding: 4px 10px; border: 1px solid #bbb; font-size: 13px; }"
        )
        self.infoLabel.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.infoLabel.setGeometry(QtCore.QRect(100, 148, 620, 32))

        # v3.8.6: regression info is appended onto infoLabel (single grey box)
        # rather than a separate widget.  This string is set in SH_apply_axes
        # and read/concatenated by on_mouse_move_SH and other infoLabel writers.
        self._regression_info_str = ""

        # Plot Controls UI (redesigned, scrollable)
        self.ctrlBox = QtWidgets.QGroupBox("Plot Controls", self.centralwidget)
        self.ctrlBox.setObjectName("ctrlBox")

        # Outer layout holding only a scroll area; inner widget hosts the real vbox
        _outer = QtWidgets.QVBoxLayout(self.ctrlBox)
        _outer.setContentsMargins(2, 4, 2, 4)
        _outer.setSpacing(0)
        self._ctrlScroll = QtWidgets.QScrollArea(self.ctrlBox)
        self._ctrlScroll.setWidgetResizable(True)
        self._ctrlScroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._ctrlScroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self._ctrlScroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        _outer.addWidget(self._ctrlScroll)
        _ctrlInner = QtWidgets.QWidget()
        self._ctrlScroll.setWidget(_ctrlInner)
        vbox = QtWidgets.QVBoxLayout(_ctrlInner)
        vbox.setContentsMargins(8, 6, 8, 8)
        vbox.setSpacing(4)

        def _spin(default=0.0):
            sb = SmartSpinBox()
            sb.setDecimals(2)
            sb.setRange(-1e12, 1e12)
            sb.setSingleStep(1.0)
            sb.setKeyboardTracking(False)
            sb.setValue(default)
            sb.setMinimumWidth(72)
            sb.setButtonSymbols(QtWidgets.QAbstractSpinBox.UpDownArrows)
            return sb

        # ── helpers for visual structure ───────────────────────
        def _mk_header(text):
            lbl = QtWidgets.QLabel(text)
            lbl.setStyleSheet(
                "QLabel { color: #555; font-weight: bold; font-size: 10px; "
                "letter-spacing: 0.5px; padding: 4px 0 1px 0; }"
            )
            return lbl
        def _mk_sep():
            f = QtWidgets.QFrame()
            f.setFrameShape(QtWidgets.QFrame.HLine)
            f.setFrameShadow(QtWidgets.QFrame.Sunken)
            f.setStyleSheet("color:#d0d0d0; background-color:#d0d0d0; max-height:1px;")
            return f

        # Active diagram label
        self.activeDiagramLabel = QtWidgets.QLabel("—")
        self.activeDiagramLabel.setStyleSheet(
            "QLabel { background: #d6e8f7; color: #185fa5; border: 1px solid #b5d4f4;"
            " border-radius: 3px; padding: 1px 6px; font-size: 11px; font-weight: bold; }"
        )
        self.activeDiagramLabel.setFixedHeight(22)
        vbox.addWidget(self.activeDiagramLabel)

        # Style selector
        # styleCombo created here; placed on left sidebar by _place_btn3D timer
        self.styleCombo = QtWidgets.QComboBox(self.centralwidget)
        self.styleCombo.addItems(["pyADR", "Classic (PDF)"])
        self.styleCombo.setToolTip("pyADR: colored fills  |  Classic (PDF): black & white")
        self.styleCombo.hide()  # will be repositioned in _place_btn3D
        self._styleLbl = QtWidgets.QLabel("Style:", self.centralwidget)
        self._styleLbl.hide()

        # Legend
        # Legend (own row, full width) -- per user request, replaces DISPLAY header
        rowLegend = QtWidgets.QHBoxLayout()
        rowLegend.addWidget(QtWidgets.QLabel("<b>Legend:</b>"))
        rowLegend.addSpacing(4)
        self.legendName = QtWidgets.QLineEdit()
        self.legendName.setPlaceholderText("Enter title")
        rowLegend.addWidget(self.legendName, 1)
        vbox.addLayout(rowLegend)
        # Display flags split across 2 rows (panel width is tight)
        # Row A: Show Legend / Show groups
        row0 = QtWidgets.QHBoxLayout()
        self.showLegendCheckbox = QtWidgets.QCheckBox("Show Legend")
        self.showLegendCheckbox.setChecked(True)
        self.showGroupsCheckbox = QtWidgets.QCheckBox("Show groups")
        self.showGroupsCheckbox.setChecked(True)
        row0.addWidget(self.showLegendCheckbox)
        row0.addSpacing(8)
        row0.addWidget(self.showGroupsCheckbox)
        row0.addStretch(1)
        vbox.addLayout(row0)
        # Row B: Group fits / Overall fit
        row0b = QtWidgets.QHBoxLayout()
        self.showGroupFitsCheckbox = QtWidgets.QCheckBox("Group fits")
        self.showGroupFitsCheckbox.setChecked(True)
        self.showGroupFitsCheckbox.setToolTip(
            "Toggle per-group regression lines and colored info boxes\n"
            "in normal/inverse isochron panels (standalone + summary).")
        self.showOverallFitCheckbox = QtWidgets.QCheckBox("Overall fit")
        self.showOverallFitCheckbox.setChecked(True)
        self.showOverallFitCheckbox.setToolTip(
            "Toggle the overall (red dashed) fitted line through ALL valid points\n"
            "in normal/inverse isochron panels (standalone + summary).")
        row0b.addWidget(self.showGroupFitsCheckbox)
        row0b.addSpacing(8)
        row0b.addWidget(self.showOverallFitCheckbox)
        row0b.addStretch(1)
        vbox.addLayout(row0b)
        # v3.8.6 (A2): Isochron regression method dropdown.
        # Only meaningful for DFN / DFI panels.  Visibility toggled with diagram type.
        rowIM = QtWidgets.QHBoxLayout()
        self.isochronMethodLabel = QtWidgets.QLabel("Isochron method:")
        self.isochronMethodCombo = QtWidgets.QComboBox()
        self.isochronMethodCombo.addItem("OLS",      "ols")
        self.isochronMethodCombo.addItem("York 2004", "york")
        self.isochronMethodCombo.setCurrentIndex(0)
        self.isochronMethodCombo.setToolTip(
            "OLS: scipy.curve_fit, assumes σ_x = 0 (older Ar/Ar convention).\n"
            "York 2004: bivariate weighted regression with both σ_x and σ_y\n"
            "(Schaen 2021 GSA Bull standard, IsoplotR default).\n\n"
            "Switch triggers Apply automatically.  The DFI/DFN figure shows\n"
            "the chosen method + its regression MSWD in the upper-right corner.")
        rowIM.addWidget(self.isochronMethodLabel)
        rowIM.addWidget(self.isochronMethodCombo, 1)
        vbox.addLayout(rowIM)

        # Log Y + Show Group Span row
        rowOpt = QtWidgets.QHBoxLayout()
        self.logYCheckbox = QtWidgets.QCheckBox("Log Y")
        self.logYCheckbox.setChecked(False)
        self.showGroupSpanCheckbox = QtWidgets.QCheckBox("Group Span")
        self.showGroupSpanCheckbox.setChecked(False)
        self.showAllCompCheckbox = QtWidgets.QCheckBox("Show all 16")
        self.showAllCompCheckbox.setChecked(False)
        self.showAllCompCheckbox.setVisible(False)  # only visible for DFD
        self.showErrorBarsCheckbox = QtWidgets.QCheckBox("Error bars")
        self.showErrorBarsCheckbox.setChecked(False)
        self.showErrorBarsCheckbox.setVisible(False)  # only visible for DFD
        self.btnDFDComponents = QtWidgets.QPushButton("Components...")
        self.btnDFDComponents.setVisible(False)  # only visible for DFD
        self.btnDFDComponents.setMaximumWidth(110)
        rowOpt.addWidget(self.logYCheckbox)
        rowOpt.addSpacing(8)
        rowOpt.addWidget(self.showGroupSpanCheckbox)
        rowOpt.addStretch(1)
        vbox.addLayout(rowOpt)
        # DFD-specific options on their own row (avoid horizontal cramping)
        rowOptDFD = QtWidgets.QHBoxLayout()
        rowOptDFD.addWidget(self.showAllCompCheckbox)
        rowOptDFD.addSpacing(4)
        rowOptDFD.addWidget(self.showErrorBarsCheckbox)
        rowOptDFD.addSpacing(4)
        rowOptDFD.addWidget(self.btnDFDComponents)
        rowOptDFD.addStretch(1)
        vbox.addLayout(rowOptDFD)

        # ── Stack-plot panel selector (DFS only) ──────────────────────
        rowStack = QtWidgets.QHBoxLayout()
        self.stackPanelLabel = QtWidgets.QLabel("<b>Stack panel:</b>")
        rowStack.addWidget(self.stackPanelLabel)
        rowStack.addSpacing(4)
        self.stackPanelCombo = QtWidgets.QComboBox()
        self.stackPanelCombo.addItems(["Top (Ca/K or Cl/K)", "Bottom (Age)"])
        self.stackPanelCombo.setCurrentIndex(1)  # default to Age (bottom)
        rowStack.addWidget(self.stackPanelCombo, 1)
        vbox.addLayout(rowStack)
        # hide by default; only DFS shows it
        self.stackPanelLabel.setVisible(False)
        self.stackPanelCombo.setVisible(False)

        # X axis with Auto checkbox
        rowXt = QtWidgets.QHBoxLayout()
        self.xLabel = QtWidgets.QLabel("<b>X:</b>")
        rowXt.addWidget(self.xLabel)
        rowXt.addSpacing(4)
        self.xAuto = QtWidgets.QCheckBox("Auto")
        self.xAuto.setChecked(True)
        rowXt.addWidget(self.xAuto)
        rowXt.addStretch(1)
        vbox.addLayout(rowXt)
        rowX = QtWidgets.QHBoxLayout()
        rowX.addWidget(QtWidgets.QLabel("min"))
        rowX.addSpacing(3)
        self.xmin = _spin(0.0)
        rowX.addWidget(self.xmin, 1)
        rowX.addSpacing(6)
        rowX.addWidget(QtWidgets.QLabel("max"))
        rowX.addSpacing(3)
        self.xmax = _spin(100.0)
        rowX.addWidget(self.xmax, 1)
        vbox.addLayout(rowX)

        # Y axis with Auto checkbox
        rowYt = QtWidgets.QHBoxLayout()
        self.yLabel = QtWidgets.QLabel("<b>Y:</b>")
        rowYt.addWidget(self.yLabel)
        rowYt.addSpacing(4)
        self.yAuto = QtWidgets.QCheckBox("Auto")
        self.yAuto.setChecked(True)
        rowYt.addWidget(self.yAuto)
        rowYt.addStretch(1)
        vbox.addLayout(rowYt)
        rowY = QtWidgets.QHBoxLayout()
        rowY.addWidget(QtWidgets.QLabel("min"))
        rowY.addSpacing(3)
        self.ymin = _spin(0.0)
        rowY.addWidget(self.ymin, 1)
        rowY.addSpacing(6)
        rowY.addWidget(QtWidgets.QLabel("max"))
        rowY.addSpacing(3)
        self.ymax = _spin(0.0)
        rowY.addWidget(self.ymax, 1)
        vbox.addLayout(rowY)

        for sb in [self.xmin, self.xmax, self.ymin, self.ymax]:
            sb.setEnabled(False)
        self.xAuto.toggled.connect(lambda on: (
            self.xmin.setEnabled(not on), self.xmax.setEnabled(not on)))
        self.yAuto.toggled.connect(lambda on: (
            self.ymin.setEnabled(not on), self.ymax.setEnabled(not on)))

        # Isochron-specific controls
        row4 = QtWidgets.QHBoxLayout()
        self.showAtmCheckbox = QtWidgets.QCheckBox("⁴⁰Ar/³⁶Ar(atm):")  # FIX#5
        self.showAtmCheckbox.setChecked(True)
        row4.addWidget(self.showAtmCheckbox)
        row4.addSpacing(4)
        self.atmRatio = QtWidgets.QDoubleSpinBox()
        self.atmRatio.setDecimals(2)
        self.atmRatio.setRange(200.0, 400.0)
        self.atmRatio.setSingleStep(0.01)
        self.atmRatio.setValue(298.56)
        self.atmRatio.setMinimumWidth(90)
        self.atmRatio.setKeyboardTracking(False)
        row4.addWidget(self.atmRatio, 1)
        row4.addStretch(1)
        vbox.addLayout(row4)
        row5 = QtWidgets.QHBoxLayout()
        self.showTempCheckbox = QtWidgets.QCheckBox("Temperature")  # FIX#3
        self.showTempCheckbox.setChecked(False)
        row5.addWidget(self.showTempCheckbox)
        row5.addStretch(1)
        vbox.addLayout(row5)

        self.isochron_widgets = [self.showAtmCheckbox, self.atmRatio, self.showTempCheckbox]

        # ── AXES section header ────────────────────────
        # (Insert separator + header here right above the Buttons)
        # Buttons: Apply / Auto / Reset
        vbox.addSpacing(2)
        vbox.addWidget(_mk_sep())
        row3 = QtWidgets.QHBoxLayout()
        self.btnApply = QtWidgets.QPushButton("Apply")
        self.btnAuto  = QtWidgets.QPushButton("Auto")
        self.btnReset = QtWidgets.QPushButton("Reset")
        # Primary button styling
        self.btnApply.setStyleSheet(
            "QPushButton {background-color:#2980b9; color:white; font-weight:bold; "
            "border:1px solid #1f6090; border-radius:4px; padding:5px 8px;} "
            "QPushButton:hover {background-color:#3498db;} "
            "QPushButton:pressed {background-color:#1f6090;}")
        for _b in (self.btnAuto, self.btnReset):
            _b.setStyleSheet(
                "QPushButton {background-color:#ecf0f1; color:#34495e; "
                "border:1px solid #bdc3c7; border-radius:4px; padding:5px 6px;} "
                "QPushButton:hover {background-color:#d6dbdf;} "
                "QPushButton:pressed {background-color:#bdc3c7;}")
        row3.addWidget(self.btnApply, 2)
        row3.addSpacing(4)
        row3.addWidget(self.btnAuto, 1)
        row3.addSpacing(4)
        row3.addWidget(self.btnReset, 1)
        vbox.addLayout(row3)

        # ── DFM (Summary) panel selector + layout (visible when pname='DFM') ──
        self.dfmPanelLabelTitle = QtWidgets.QLabel("Panel:")
        self.dfmPanelLabelTitle.setStyleSheet("font-weight:bold;")
        self.dfmPanelCombo = QtWidgets.QComboBox()
        self.dfmPanelCombo.setToolTip("Select which Summary panel to adjust")
        _row_dfm_p = QtWidgets.QHBoxLayout()
        _row_dfm_p.addWidget(self.dfmPanelLabelTitle)
        _row_dfm_p.addWidget(self.dfmPanelCombo, 1)
        # Insert Panel just under activeDiagramLabel (idx 0 here; grp_row is
        # inserted at 0 later, shifting Layout/Panel below Group + DFM label).
        vbox.insertLayout(1, _row_dfm_p)

        self.dfmLayoutLabel = QtWidgets.QLabel("Layout:")
        self.dfmLayoutLabel.setStyleSheet("font-weight:bold;")
        self.dfmLayoutCombo = QtWidgets.QComboBox()
        self.dfmLayoutCombo.addItems(["Vertical stack", "2-column grid"])
        _row_dfm_l = QtWidgets.QHBoxLayout()
        _row_dfm_l.addWidget(self.dfmLayoutLabel)
        _row_dfm_l.addWidget(self.dfmLayoutCombo, 1)
        # Insert Layout above Panel (also at idx 1, shifting Panel to idx 2).
        vbox.insertLayout(1, _row_dfm_l)

        self.dfm_widgets = [self.dfmPanelLabelTitle, self.dfmPanelCombo,
                            self.dfmLayoutLabel, self.dfmLayoutCombo]
        for w in self.dfm_widgets:
            w.setVisible(False)

        self._update_control_visibility("DFN")
        
        # Enable mouse tracking on photo widget
        self.photo.setMouseTracking(True)
        self.photo.installEventFilter(self)
        
        # Store axes limits and bbox for coordinate transformation
        self.current_xlim = (0, 100)
        self.current_ylim = (0, 10)
        self.current_axes_bbox = None  # (ax_left, ax_bottom, ax_right, ax_top) in PNG-frac coords

        def _place_btn3D():
            ag = self.A.geometry()
            wg = self.W.geometry()
            bw, bh = ag.width(), ag.height()
            bx = ag.x()
            # Match the gap between Age Plateau (W) and Ca/K (A)
            gap = max(ag.y() - (wg.y() + wg.height()), 0)
            # Button order below Ca/K: Cl/K → Degassing → Stack/Summary → 3D Plane Fit
            self.btnCL = QtWidgets.QPushButton("Cl/K", self.centralwidget)
            self.btnCL.setGeometry(bx, ag.y() + bh + gap, bw, bh)
            self.btnCL.show()
            self.btnDeg = QtWidgets.QPushButton("Degassing", self.centralwidget)
            self.btnDeg.setGeometry(bx, ag.y() + (bh + gap) * 2, bw, bh)
            self.btnDeg.show()
            self.btnStack = QtWidgets.QPushButton("Stack / Summary", self.centralwidget)
            self.btnStack.setGeometry(bx, ag.y() + (bh + gap) * 3, bw, bh)
            self.btnStack.show()
            self.btn3D = QtWidgets.QPushButton("3D Plane Fit", self.centralwidget)
            self.btn3D.setGeometry(bx, ag.y() + (bh + gap) * 4, bw, bh)
            self.btn3D.show()
            # V3.5: Excel export button (between 3D Plane Fit and Style selector)
            self.btnExcel = QtWidgets.QPushButton("Excel", self.centralwidget)
            self.btnExcel.setGeometry(bx, ag.y() + (bh + gap) * 5, bw, bh)
            self.btnExcel.show()
            # Style selector: directly below btnExcel
            lbl_w = 38
            style_y = ag.y() + (bh + gap) * 6
            self._styleLbl.setGeometry(bx, style_y, lbl_w, bh)
            self._styleLbl.show()
            self.styleCombo.setGeometry(bx + lbl_w + 2, style_y, bw - lbl_w - 2, bh)
            self.styleCombo.show()
        QtCore.QTimer.singleShot(0, _place_btn3D)

        # FIX#9: Group selector row inside ctrlBox (top, above active diagram label)
        grp_row = QtWidgets.QHBoxLayout()
        _grp_lbl = QtWidgets.QLabel("Group:")
        _grp_lbl.setStyleSheet("font-size:11px; font-weight:bold;")
        grp_row.addWidget(_grp_lbl)
        grp_row.addSpacing(3)
        _gc_colors = ['#FF8C00', '#1E90FF', '#2ECC40', '#FF4136', '#B10DC9']
        self._grp_btns = []
        for _gi, _gc in enumerate(_gc_colors):
            _btn = QtWidgets.QPushButton(str(_gi + 1))
            _btn.setCheckable(True)
            _btn.setChecked(_gi == 0)
            _btn.setFixedSize(26, 22)
            _btn.setStyleSheet(
                f"QPushButton{{background:{_gc};color:white;font-weight:bold;"
                f"border-radius:3px;border:2px solid transparent;}}"
                f"QPushButton:checked{{border:2px solid black;}}"
            )
            grp_row.addWidget(_btn)
            self._grp_btns.append(_btn)
        _btn_clear = QtWidgets.QPushButton("Clear")
        _btn_clear.setFixedSize(42, 22)
        _btn_clear.setStyleSheet(
            "QPushButton{background:#888;color:white;border-radius:3px;}"
            "QPushButton:hover{background:#555;}"
        )
        grp_row.addWidget(_btn_clear)
        grp_row.addStretch(1)
        self._grp_btn_clear = _btn_clear
        vbox.insertLayout(0, grp_row)  # top of Plot Controls
    
    def _update_control_visibility(self, pname):
        """Show/hide isochron controls; update label and Apply button text."""
        is_isochron = pname in ("DFN", "DFI")
        for widget in self.isochron_widgets:
            widget.setVisible(is_isochron)
        # DFM-specific widgets (panel selector + layout)
        is_dfm = (pname == "DFM")
        for w in getattr(self, 'dfm_widgets', []):
            w.setVisible(is_dfm)
        # Apply/Auto/Reset axes not meaningful for 3D (4-panel figure)
        for w in [self.btnApply, self.btnAuto, self.btnReset,
                  self.xAuto, self.xmin, self.xmax,
                  self.yAuto, self.ymin, self.ymax]:
            w.setEnabled(pname != "DF3D")
        _label_map = {
            "DFN": "Normal isochron (DFN)",
            "DFI": "Inverse isochron (DFI)",
            "DFW": "Age spectrum (DFW)",
            "DFA": "Ca/K spectrum (DFA)",
            "DFC": "Cl/K spectrum (DFC)",
            "DFS": "Stack plot (DFS)",
            "DFM": "Summary figure (DFM)",
        }
        self.activeDiagramLabel.setText(_label_map.get(pname, pname))
        # Decimal places: 6 for isochrons (values ~0.002); 4 for Ca/K, Cl/K; 2 otherwise
        if pname in ("DFN", "DFI"):
            _decs, _step = 6, 1e-6
        elif pname in ("DFA", "DFC"):
            _decs, _step = 4, 1e-4
        else:
            _decs, _step = 2, 0.1
        for _sb in [self.xmin, self.xmax, self.ymin, self.ymax]:
            _sb.setDecimals(_decs)
            _sb.setSingleStep(_step)
        # logY meaningful for DFA/DFC, DFS top panel, and DFD;
        # GroupSpan for DFW/DFA/DFC; ShowAllComp only for DFD
        self.logYCheckbox.setVisible(pname in ("DFA", "DFC", "DFS", "DFD"))
        self.showGroupSpanCheckbox.setVisible(pname in ("DFW", "DFA", "DFC"))
        self.showAllCompCheckbox.setVisible(pname == "DFD")
        self.showErrorBarsCheckbox.setVisible(pname == "DFD")
        self.btnDFDComponents.setVisible(pname == "DFD")
        # Stack panel selector: only DFS
        self.stackPanelLabel.setVisible(pname == "DFS")
        self.stackPanelCombo.setVisible(pname == "DFS")
        # X/Y axis description per current page
        _axes = {
            "DFW": ("Cumulative \u00b3\u2079Ar (%)", "Age (Ma)"),
            "DFA": ("Cumulative \u00b3\u2079Ar (%)", "Ca/K"),
            "DFC": ("Cumulative \u00b3\u2079Ar (%)", "Cl/K"),
            "DFN": ("\u00b3\u2079Ar/\u00b3\u2076Ar",   "\u2074\u2070Ar/\u00b3\u2076Ar"),
            "DFI": ("\u00b3\u2079Ar/\u2074\u2070Ar",   "\u00b3\u2076Ar/\u2074\u2070Ar"),
            "DFD": ("Temperature (\u00b0C)",          "Ar amount (V)"),
            "DFM": ("(varies by panel)",                "(varies by panel)"),
            "DFS": ("Cumulative \u00b3\u2079Ar (%)",   "(top: ratio | bottom: Age)"),
        }
        _xd, _yd = _axes.get(pname, ("", ""))
        if hasattr(self, 'xLabel'):
            if _xd:
                self.xLabel.setText(f"<b>X</b> <span style='color:#666'>({_xd})</span>")
            else:
                self.xLabel.setText("<b>X:</b>")
        if hasattr(self, 'yLabel'):
            if _yd:
                self.yLabel.setText(f"<b>Y</b> <span style='color:#666'>({_yd})</span>")
            else:
                self.yLabel.setText("<b>Y:</b>")
        # FIX#6: Apply button stays as 'Apply'
    
    def _pixel_to_data(self, px, py):
        """Convert photo-widget pixel (px,py) to data coordinates.
        Uses current_axes_bbox (axes fraction within the saved PNG) to
        correctly account for matplotlib margins/labels.
        Returns (x_data, y_data) or (None, None) if limits not set.
        """
        xlim = self.current_xlim
        ylim = self.current_ylim
        if xlim is None or ylim is None:
            return None, None
        # Determine effective image dimensions for coordinate mapping
        pm = self.photo.pixmap()
        if self.photo.hasScaledContents() or pm is None or pm.isNull():
            # image fills widget exactly → widget size = image size in fraction space
            w = self.photo.width()
            h = self.photo.height()
        else:
            # image shown at native size (top-left aligned, may be clipped)
            w = pm.width()
            h = pm.height()
        if w <= 0 or h <= 0:
            return None, None
        # Normalized position in the image (x: 0=left→1=right; y: 0=bottom→1=top)
        x_img = px / w
        y_img = 1.0 - py / h
        axes_bbox = getattr(self, 'current_axes_bbox', None)
        if axes_bbox is not None:
            ax_l, ax_b, ax_r, ax_t = axes_bbox
            dw = max(ax_r - ax_l, 1e-6)
            dh = max(ax_t - ax_b, 1e-6)
            x_frac = (x_img - ax_l) / dw
            y_frac = (y_img - ax_b) / dh
        else:
            x_frac = x_img
            y_frac = y_img
        x_data = xlim[0] + x_frac * (xlim[1] - xlim[0])
        y_data = ylim[0] + y_frac * (ylim[1] - ylim[0])
        return x_data, y_data

    def eventFilter(self, obj, event):
        """Event filter to capture mouse movement and clicks on photo widget"""
        if obj == self.photo and event.type() == QtCore.QEvent.MouseButtonPress:
            if hasattr(self, '_click_callback'):
                pos = event.pos()
                xd, yd = self._pixel_to_data(pos.x(), pos.y())
                if xd is not None:
                    xlim = self.current_xlim
                    ylim = self.current_ylim
                    if xlim and ylim:
                        self._click_callback(xd, yd, event.button())

        if obj == self.photo and event.type() == QtCore.QEvent.MouseMove:
            pos = event.pos()
            x_data, y_data = self._pixel_to_data(pos.x(), pos.y())
            if x_data is not None and hasattr(self, '_mouse_move_callback'):
                self._mouse_move_callback(x_data, y_data)

        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        ctrl_h = 420  # taller; QScrollArea handles overflow gracefully
        ctrl_w = 305
        right_margin = 10
        ctrl_x = event.size().width() - ctrl_w - right_margin
        min_y = 135
        ctrl_y = min_y
        
        self.ctrlBox.setGeometry(QtCore.QRect(ctrl_x, ctrl_y, ctrl_w, ctrl_h))
        
        table_y = ctrl_y + ctrl_h + 10
        table_h = event.size().height() - table_y - 30
        self.Tsize = [ctrl_x, table_y, ctrl_w, max(200, table_h)]
        self.tableWidget.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        
        photo_x = 100
        photo_width = ctrl_x - photo_x - 10
        self.Isize = [photo_x, 190, photo_width, 450 + event.size().height() - 700]
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        self.infoLabel.setGeometry(QtCore.QRect(photo_x, 148, photo_width, 32))

                
class DiagramPlots_LS(QtWidgets.QMainWindow, UI.DiagramPlots_LS.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)   
        
    def resizeEvent(self, event):
        self.Isize = [91, 190, 490+event.size().width()-800, 450+event.size().height()-700]     
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        self.Tsize =[580+event.size().width()-800, 190+event.size().height()-700, 220, 419]
        self.tableWidget.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        
class DiagramSelect(QtWidgets.QMainWindow, UI.DiagramSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)

class DatumSelect(QtWidgets.QMainWindow, UI.DatumSelect.Ui_MainWindow):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self, parent)
        self.setupUi(self)
        _add_return_button(self)
        _make_select_page_responsive(self)
        
# main app
# ===============================================================================
class App():
    def __init__(self):
        self.work_dir = os.path.dirname(os.path.realpath(__file__))+'/' # get the absolute path of working directory

        # initilization for GUI
        QtWidgets.QApplication.setStyle('Fusion')
        # v3.8.83: reuse the QApplication created at module load (it already put
        # up the boot splash); only create one if somehow absent.
        self.app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

        # v3.8.4: set taskbar / window icon to pyADR.ico so Windows shows the
        # Ar 40/39 logo instead of the generic Python icon.  On Windows the
        # taskbar groups by AppUserModelID, so without an explicit ID the OS
        # treats us as "Python.exe" and reuses Python's icon.
        try:
            _icon_path = os.path.join(self.work_dir, '.work', 'pyADR.ico')
            if os.path.exists(_icon_path):
                self.app.setWindowIcon(QtGui.QIcon(_icon_path))
            if sys.platform.startswith('win'):
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('NTNU.pyADR.ArAr.v3.8')
        except Exception:
            pass  # icon is cosmetic; never block startup

        # v3.8.4: splash screen during startup.  splash.png is a static
        # template (logo, title, lab, PI, URL all baked).  Version + date
        # are drawn here at runtime from .work/.app_info.txt so they
        # update automatically when .app_info.txt changes — no need to
        # regenerate splash.png on each release.
        self._splash = None
        try:
            _splash_path = os.path.join(self.work_dir, '.work', 'splash.png')
            if os.path.exists(_splash_path):
                _pix_raw = QtGui.QPixmap(_splash_path)

                # v3.8.19: splash.png has a built-in grey footer strip
                # (y=455–480) with a horizontal divider at y=455 that the user
                # wants gone. Crop the pixmap to (W, 455) at load so only the
                # clean white card area shows, then paint Loading… centered
                # below the URL. The grey footer + bottom-right showMessage()
                # are both eliminated.
                _crop_h = 455
                _W = _pix_raw.width()
                _pix = _pix_raw.copy(0, 0, _W, _crop_h)

                # Read version + date from .app_info.txt
                _ver = '?'; _date = '?'
                try:
                    with open(os.path.join(self.work_dir, '.work', '.app_info.txt'),
                              encoding='utf-8') as _f:
                        _lines = [ln.strip() for ln in _f.readlines()]
                    if len(_lines) > 1: _ver = _lines[1]
                    if len(_lines) > 4: _date = _lines[4]
                except Exception:
                    pass

                # Paint v{ver} and "updated {date}" onto pixmap.
                # Position anchors must match the empty slot left by the
                # splash generator (y ~348 for version, y ~376 for date).
                _painter = QtGui.QPainter(_pix)
                _painter.setRenderHint(QtGui.QPainter.Antialiasing)
                _painter.setRenderHint(QtGui.QPainter.TextAntialiasing)

                _font_v = QtGui.QFont('Georgia', 16, QtGui.QFont.Bold)
                _painter.setFont(_font_v)
                _painter.setPen(QtGui.QColor(30, 50, 110))
                _painter.drawText(QtCore.QRect(0, 346, _W, 30),
                                  QtCore.Qt.AlignHCenter,
                                  f'v{_ver}')

                _font_d = QtGui.QFont('Arial', 10)
                _painter.setFont(_font_d)
                _painter.setPen(QtGui.QColor(70, 70, 70))
                _painter.drawText(QtCore.QRect(0, 374, _W, 22),
                                  QtCore.Qt.AlignHCenter,
                                  f'updated {_date}')

                # v3.8.19: "Loading…" centered below github URL (URL renders
                # at ~y=400; place text at y=425, centered horizontally).
                _font_l = QtGui.QFont('Arial', 9, QtGui.QFont.StyleItalic)
                _font_l.setItalic(True)
                _painter.setFont(_font_l)
                _painter.setPen(QtGui.QColor(120, 120, 120))
                _painter.drawText(QtCore.QRect(0, 425, _W, 22),
                                  QtCore.Qt.AlignHCenter,
                                  'Loading…')

                _painter.end()

                # v3.8.83: reuse the boot splash shown at module load (so it
                # appeared instantly, before the heavy imports) — just swap in
                # the version/date/Loading-overlaid pixmap now.
                if _BOOT_SPLASH is not None:
                    self._splash = _BOOT_SPLASH
                    self._splash.setPixmap(_pix)
                    self._splash.setMask(_pix.mask())
                else:
                    self._splash = QtWidgets.QSplashScreen(
                        _pix, QtCore.Qt.WindowStaysOnTopHint)
                    self._splash.setMask(_pix.mask())
                # v3.8.19: showMessage removed — Loading… now baked into pixmap,
                # centered below the URL instead of bottom-right grey strip.
                self._splash.show()
                self.app.processEvents()
                # record show time so run() can enforce minimum splash duration
                import time as _time
                self._splash_t0 = _BOOT_T0 if _BOOT_T0 is not None else _time.monotonic()
        except Exception:
            self._splash = None  # splash is cosmetic; never block startup

        self.HomePage = HomePage()
        self.T0CalculationPage = LinearRegressionPage()
        self.TypeSelect = TypeSelect()
        self.ReselectDialog = ReselectTable()
        self.StatSelectPage = StatSelect()
        self.JStatisticsPage = JStatistics()
        self.T0StatisticsPage = T0Statistics()
        self.AirRatioStatisticsPage = AirRatioStatistics()
        self.SaltStatPage = SaltStat()
        self.MassRatioPage = MassRatio()
        self.JCalculationPage = JCalculation()
        self.JSelectPage = JSelect()
        self.AgeCalculationPage = AgeCalculation()
        self.ParameterSettingPage = ParameterSetting()
        self.SaltCalculationPage = SaltCalculation()
        self.SaltSelectPage = SaltSelect()
        self.SaltStatSelectPage = SaltStatSelect()
        self.DiagramSelectPage = DiagramSelect()
        self.DiagramPlots_LSPage = DiagramPlots_LS()
        self.DatumSelectPage = DatumSelect()
        self.DiagramPlots_SHPage = DiagramPlots_SH()

        self.widget = QtWidgets.QStackedWidget()
        self.widget.addWidget(self.HomePage) #p0
        self.widget.addWidget(self.T0CalculationPage) #p1
        self.widget.addWidget(self.T0StatisticsPage) #p2
        self.widget.addWidget(self.MassRatioPage) #p3
        self.widget.addWidget(self.JCalculationPage) #p4
        self.widget.addWidget(self.ParameterSettingPage) #p5
        self.widget.addWidget(self.AgeCalculationPage) #p6
        self.widget.addWidget(self.TypeSelect) #p7
        self.widget.addWidget(self.SaltCalculationPage) #p8
        self.widget.addWidget(self.JSelectPage) #p9
        self.widget.addWidget(self.StatSelectPage) #p10
        self.widget.addWidget(self.JStatisticsPage) #p11
        self.widget.addWidget(self.SaltSelectPage) #p12
        self.widget.addWidget(self.AirRatioStatisticsPage) #p13
        self.widget.addWidget(self.DiagramSelectPage) #p14
        self.widget.addWidget(self.DiagramPlots_SHPage) #p15
        self.widget.addWidget(self.DiagramPlots_LSPage) #p16
        self.widget.addWidget(self.SaltStatPage) #p17
        self.widget.addWidget(self.SaltStatSelectPage) #p18
        self.widget.addWidget(self.DatumSelectPage) #p19
        self.AutoPipelinePage = AutoPipeline.AutoPipelineWindow()
        self.widget.addWidget(self.AutoPipelinePage)   # p20
        self.AutoPipelinePage.t0Page.returnBtn.clicked.connect(self.toMain)
        # v3.8.85: Parameter button on all three AutoPipeline pages → param page
        try:
            self.AutoPipelinePage.t0Page.paramBtn.clicked.connect(self.toPS_from_pipeline)
            self.AutoPipelinePage.mrPage.paramBtn.clicked.connect(self.toPS_from_pipeline)
            self.AutoPipelinePage.agePage.paramBtn.clicked.connect(self.toPS_from_pipeline)
        except Exception:
            pass
        self.widget.resize(800, 700)
        for i in range(self.widget.count()):
            self.insertLogo(self.widget.widget(i))

        # others
        self.fitting_function_list = ["Linear", "Average"]
        self.mass_pair = ['Ar39/40', 'Ar36/40', 'Ar39/36', 'Ar40/36', 'Ar38/36']
        self.data_folder = 'Data/'
        self.screenshot_folder = 'Figures/'
        with open(self.work_dir+'.work/.app_info.txt', 'r') as f:
            self.app_info = f.readlines()
        # Auto-check for updates on startup (silent, background)
        threading.Thread(target=self._bg_check_update, daemon=True).start()
        self.J_list = [28201000,128100000,523100000]
        self.J_Sigma = [23000,700000,2600000]
        self.toast = Notification(app_id="pyARD", title="Save success!",duration="short")
        self.power = 6
        
        # Plot config storage
        self.plot_cfg = {}
        
        # Step data storage for mouse hover info
        self.step_data = {
            "DFW": [],  # Age spectrum steps: [(x_start, x_end, age, age_std, ar39_amount), ...]
            "DFA": [],  # Ca/K spectrum steps
            "DFC": [],  # Cl/K spectrum steps
            "DFS": [],  # Stack plot steps
            "DFM": []   # Summary figure steps
        }
        # ── Group selection system ────────────────────────────────────────
        self.GROUP_COLORS = ['#FF8C00','#1E90FF','#2ECC40','#FF4136','#B10DC9']
        self.step_groups  = {}   # {step_idx(0-based): group_num(1-5)}
        self.active_group = 1    # currently active group to assign
        self.iso_pts_DFN  = []   # FIX#8: [(x,y,orig_idx),...] for isochron click
        self.iso_pts_DFI  = []
        self._axes_bboxes = {}   # {pname: axes_bbox tuple}
        self._actual_xlims = {} # {pname: (xmin, xmax)}
        self._actual_ylims = {} # {pname: (ymin, ymax)}
    def insertLogo(self, page):
        if page is self.AutoPipelinePage:
            return
        try:
            cw = page.centralwidget
        except AttributeError:
            cw = page.centralWidget()
        if cw is None:
            return
        # FIX: HomePage uses a layout-driven logo placed inside `page.logo_slot`
        # so it stays centered when the user resizes the window. Other pages
        # keep the original absolute-positioned banner across the top.
        if page is self.HomePage and hasattr(page, 'logo_slot'):
            page.logo = QtWidgets.QLabel(page.logo_slot)
            slot_layout = QtWidgets.QHBoxLayout(page.logo_slot)
            slot_layout.setContentsMargins(0, 0, 0, 0)
            slot_layout.addStretch(1)
            slot_layout.addWidget(page.logo)
            slot_layout.addStretch(1)
            page.logo.setFixedSize(500, 80)
            page.logo.setScaledContents(True)
        else:
            page.logo = QtWidgets.QLabel(cw)
            page.logo.setGeometry(QtCore.QRect(50, 25, 700, 75))
            page.logo.setScaledContents(True)
        page.logo.setText("")
        page.logo.setPixmap(QtGui.QPixmap(self.work_dir+".work/logo.png"))
        page.logo.setObjectName("logo")

    def _read_SH_controls(self):
        """FIX: use xAuto/yAuto checkboxes; no (0,0) sentinel."""
        page = self.DiagramPlots_SHPage

        if page.xAuto.isChecked():
            xlim = None
        else:
            xmin = float(page.xmin.value())
            xmax = float(page.xmax.value())
            xlim = (xmin, xmax) if xmax > xmin else None

        if page.yAuto.isChecked():
            ylim = None
        else:
            ymin = float(page.ymin.value())
            ymax = float(page.ymax.value())
            ylim = (ymin, ymax) if ymax > ymin else None

        legend = page.legendName.text().strip()
        legend_name = legend if legend else None

        return xlim, ylim, legend_name

    def _save_SH_config(self, pname, xlim, ylim, legend):
        """FIX: always write xlim/ylim (None=auto) to clear stale values."""
        if pname not in self.plot_cfg:
            self.plot_cfg[pname] = {}
        self.plot_cfg[pname]["xlim"] = xlim
        self.plot_cfg[pname]["ylim"] = ylim
        if legend is not None:
            self.plot_cfg[pname]["legend"] = legend

    def _load_SH_config(self, pname):
        """FIX: blockSignals + reflect xAuto/yAuto toggle state."""
        page = self.DiagramPlots_SHPage
        cfg = self.plot_cfg.get(pname, {})

        xlim = cfg.get("xlim")
        ylim = cfg.get("ylim")
        legend = cfg.get("legend")

        for sb in [page.xmin, page.xmax, page.ymin, page.ymax]:
            sb.blockSignals(True)

        if xlim is not None:
            page.xAuto.setChecked(False)
            page.xmin.setEnabled(True); page.xmax.setEnabled(True)
            page.xmin.setValue(float(xlim[0]))
            page.xmax.setValue(float(xlim[1]))
        else:
            page.xAuto.setChecked(True)
            page.xmin.setEnabled(False); page.xmax.setEnabled(False)
            page.xmin.setValue(0.0)
            page.xmax.setValue(100.0 if pname in ('DFW', 'DFA', 'DFC') else 1.0)

        if ylim is not None:
            page.yAuto.setChecked(False)
            page.ymin.setEnabled(True); page.ymax.setEnabled(True)
            page.ymin.setValue(float(ylim[0]))
            page.ymax.setValue(float(ylim[1]))
        else:
            page.yAuto.setChecked(True)
            page.ymin.setEnabled(False); page.ymax.setEnabled(False)
            page.ymin.setValue(0.0); page.ymax.setValue(0.0)

        for sb in [page.xmin, page.xmax, page.ymin, page.ymax]:
            sb.blockSignals(False)

        if legend:
            page.legendName.setText(str(legend))
        else:
            page.legendName.clear()

    def _calc_auto_range(self, x, y):
        """Calculate optimal axis range from data"""
        x = np.asarray(x, float)
        y = np.asarray(y, float)
        m = np.isfinite(x) & np.isfinite(y)
        x = x[m]
        y = y[m]

        if len(x) < 2:
            return 0.0, 1.0, 0.0, 1.0

        xmin, xmax = np.percentile(x, [1, 99])
        ymin, ymax = np.percentile(y, [1, 99])

        dx = (xmax - xmin) * 0.05 if xmax > xmin else abs(xmax) * 0.05 + 1e-6
        dy = (ymax - ymin) * 0.05 if ymax > ymin else abs(ymax) * 0.05 + 1e-6

        return xmin - dx, xmax + dx, ymin - dy, ymax + dy

    def _get_current_xy_data(self):
        """Get x,y data for current diagram"""
        import pandas as pd

        pname = getattr(self, "pname", "DFN")

        # DF3D axes are fixed (4-panel figure); no manual axis control

        try:
            if pname in ("DFN", "DFI"):
                df = pd.read_csv(self.Dfilename)
                
                # Calculate measured totals
                if "40Ar(m)" in df.columns:
                    a40m = df["40Ar(m)"]
                else:
                    a40m = df["40Ar(r)"] + df["40Ar(a)"] + df["40Ar(c)"] + df["40Ar(k)"]
                
                if "39Ar(m)" in df.columns:
                    a39m = df["39Ar(m)"]
                else:
                    a39m = df["39Ar(k)"] + df["39Ar(ca)"]
                
                if "36Ar(m)" in df.columns:
                    a36m = df["36Ar(m)"]
                else:
                    a36m = df["36Ar(a)"] + df["36Ar(c)"] + df["36Ar(ca)"] + df["36Ar(cl)"]
                
                if pname == "DFN":
                    # Normal: X = 39Ar(m)/36Ar(m), Y = 40Ar(m)/36Ar(m)
                    x = a39m / a36m
                    y = a40m / a36m
                else:  # DFI
                    # Inverse: X = 39Ar(m)/40Ar(m), Y = 36Ar(m)/40Ar(m)
                    x = a39m / a40m
                    y = a36m / a40m
                
                return x.values, y.values
                
            elif pname in ("DFW", "DFA", "DFC"):
                df = pd.read_csv(self.Dfilename)
                x = df["39Ar(k)(%)(step heating)"].values

                if pname == "DFW":
                    y = df["Age(Ma)"].values
                elif pname == "DFA":
                    y = df["Ca/K"].values
                else:  # DFC — Lo et al. (1994): Cl/K = (38Ar_Cl / 39Ar_K) × 0.22
                    ar39k  = df["39Ar(k)"].values
                    ar38cl = df["38Ar(cl)"].values
                    y = np.where(ar39k != 0, 0.22 * ar38cl / ar39k, 0.0)

                return x, y

            elif pname == "DFS":
                # Stack plot: pick top or bottom panel based on combo
                df = pd.read_csv(self.Dfilename)
                x = df["39Ar(k)(%)(step heating)"].values
                page = self.DiagramPlots_SHPage
                panel_idx = page.stackPanelCombo.currentIndex() if hasattr(page, 'stackPanelCombo') else 1
                if panel_idx == 0:
                    # Top panel: Ca/K or Cl/K depending on _dfs_top_type
                    top_type = getattr(self, '_dfs_top_type', 'Ca/K')
                    if top_type == 'Ca/K':
                        y = df["Ca/K"].values
                    else:
                        ar39k  = df["39Ar(k)"].values
                        ar38cl = df["38Ar(cl)"].values
                        y = np.where(ar39k != 0, 0.22 * ar38cl / ar39k, 0.0)
                else:
                    # Bottom panel: Age
                    y = df["Age(Ma)"].values
                return x, y

            elif pname == "DFD":
                # Degassing pattern: x = temperature, y = 39Ar(K) (representative)
                df = pd.read_csv(self.Dfilename)
                # Read deg C column robustly
                if "deg C" in df.columns:
                    x = df["deg C"].values
                else:
                    x = df.iloc[:, 3].values
                # Y representative: 39Ar(K) (degassing-pattern occurrence is later col)
                # Use the LAST '39Ar(k)' column to avoid the 'main' one
                k_cols = [c for c in df.columns if c.strip() == '39Ar(k)']
                if k_cols:
                    y = df[k_cols[-1]].values
                else:
                    y = np.zeros(len(x))
                return x, y

            elif pname == "DFM":
                # Summary panel: pick the active panel via _dfm_active_key
                key = getattr(self, '_dfm_active_key', None)
                df = pd.read_csv(self.Dfilename)
                if key in ("age", "atm", "cak", "clk"):
                    x = df["39Ar(k)(%)(step heating)"].values
                    if key == "age":
                        y = df["Age(Ma)"].values
                    elif key == "atm":
                        y = df["40Ar(r)(%)"].values
                    elif key == "cak":
                        y = df["Ca/K"].values
                    else:  # clk
                        ar39k  = df["39Ar(k)"].values
                        ar38cl = df["38Ar(cl)"].values
                        y = np.where(ar39k != 0, 0.22 * ar38cl / ar39k, 0.0)
                    return x, y
                elif key in ("isn", "iso"):
                    # Build measured totals
                    if "40Ar(m)" in df.columns:
                        a40m = df["40Ar(m)"]
                    else:
                        a40m = df["40Ar(r)"] + df["40Ar(a)"] + df["40Ar(c)"] + df["40Ar(k)"]
                    if "39Ar(m)" in df.columns:
                        a39m = df["39Ar(m)"]
                    else:
                        a39m = df["39Ar(k)"] + df["39Ar(ca)"]
                    if "36Ar(m)" in df.columns:
                        a36m = df["36Ar(m)"]
                    else:
                        a36m = df["36Ar(a)"] + df["36Ar(c)"] + df["36Ar(ca)"] + df["36Ar(cl)"]
                    if key == "isn":
                        x = a39m / a36m
                        y = a40m / a36m
                    else:  # iso
                        x = a39m / a40m
                        y = a36m / a40m
                    return x.values, y.values
                return [], []
        except Exception as e:  # BUG FIX: B6 - Replace bare except with proper exception handling
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(f"Error in data extraction: {e}")
            return [], []
        
        return [], []


    def _get_plot_style(self):
        """Return 'pyADR' or 'classic' based on UI selector."""
        txt = self.DiagramPlots_SHPage.styleCombo.currentText()
        return 'classic' if 'Classic' in txt else 'pyADR'

    def _dfs_load_panel_into_spinboxes(self):
        """DFS only: load the selected panel's saved (xlim, ylim) into the
        right-hand spinboxes so the user can edit them. If a saved limit is
        None (i.e. Auto), check the corresponding xAuto/yAuto box."""
        page = self.DiagramPlots_SHPage
        cfg = getattr(self, '_dfs_config', None) or {}
        panel_idx = page.stackPanelCombo.currentIndex()
        panel_key = 'top' if panel_idx == 0 else 'bot'
        x = cfg.get(f'{panel_key}_xlim')
        y = cfg.get(f'{panel_key}_ylim')
        # block signals to avoid recursive Apply triggers while loading
        for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
            w.blockSignals(True)
        try:
            if x is None:
                page.xAuto.setChecked(True)
            else:
                page.xAuto.setChecked(False)
                page.xmin.setValue(float(x[0]))
                page.xmax.setValue(float(x[1]))
            if y is None:
                page.yAuto.setChecked(True)
            else:
                page.yAuto.setChecked(False)
                page.ymin.setValue(float(y[0]))
                page.ymax.setValue(float(y[1]))
            # propagate enabled state of spinboxes to match Auto state
            page.xmin.setEnabled(not page.xAuto.isChecked())
            page.xmax.setEnabled(not page.xAuto.isChecked())
            page.ymin.setEnabled(not page.yAuto.isChecked())
            page.ymax.setEnabled(not page.yAuto.isChecked())
        finally:
            for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
                w.blockSignals(False)

    def _on_stack_panel_changed(self, idx):
        """Combo box callback: load saved limits for the new panel selection."""
        try:
            self._dfs_load_panel_into_spinboxes()
        except Exception:
            pass

    def SH_apply_axes(self):
        """Apply button: redraw with current axis settings"""
        pname = getattr(self, "pname", "DFN")
        xlim, ylim, legend = self._read_SH_controls()

        self._save_SH_config(pname, xlim, ylim, legend)

        # v3.8.6: default-clear regression info every time a new panel is drawn.
        # Only the DFN/DFI branch below repopulates it.  Without this reset,
        # switching from DFI to DFW (etc.) leaves the previous suffix dangling
        # and appended to the unrelated panel's infoLabel.
        self.DiagramPlots_SHPage._regression_info_str = ""

        # BUG FIX: B2 - Initialize actual_xlim/actual_ylim to avoid NameError
        actual_xlim = xlim if xlim is not None else (0, 100)
        actual_ylim = ylim if ylim is not None else (0, 10)

        try:
            if pname == "DFM":
                _key = getattr(self, '_dfm_active_key', None)
                if _key:
                    plim = getattr(self, '_dfm_panel_limits', {}) or {}
                    plegs = getattr(self, '_dfm_panel_legends', {}) or {}
                    plim[_key] = (xlim, ylim)
                    if legend is not None:
                        plegs[_key] = legend
                    elif _key in plegs:
                        plegs.pop(_key, None)
                    self._dfm_panel_limits  = plim
                    self._dfm_panel_legends = plegs
                _layout = 'grid' if (self.DiagramPlots_SHPage.dfmLayoutCombo.currentIndex() == 1) else 'vertical'
                self._dfm_layout = _layout
                Utilities.getSummaryPlot(
                    self.Dfilename, self.mask, self.parameters,
                    panels=getattr(self, '_dfm_panels', None),
                    legend_name=None, style=self._get_plot_style(),
                    panel_limits=getattr(self, '_dfm_panel_limits', None),
                    panel_legends=getattr(self, '_dfm_panel_legends', None),
                    layout=_layout,
                    step_groups=self._effective_step_groups(),
                    group_colors=self.GROUP_COLORS,
                    show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
)
                QtGui.QPixmapCache.clear()
                self.DiagramPlots_SHPage.photo.setPixmap(
                    QtGui.QPixmap(self.work_dir + ".work/DFM.png"))
                return
            if pname in ("DFN", "DFI"):
                # Read isochron-specific controls
                show_temp = self.DiagramPlots_SHPage.showTempCheckbox.isChecked()
                show_atm = self.DiagramPlots_SHPage.showAtmCheckbox.isChecked()
                atm_ratio = self.DiagramPlots_SHPage.atmRatio.value()
                
                # BUG FIX: A8 - Replace print with logging
                logger.debug(f"SH_apply_axes: pname={pname}, show_temp={show_temp}, show_atm={show_atm}, atm_ratio={atm_ratio}")
                
                # Get actual axis limits from getDFStatistics_sh
                # FIX: pass pname so only target diagram gets xlim/ylim
                _show_leg = self.DiagramPlots_SHPage.showLegendCheckbox.isChecked()
                # v3.8.6 (A2): pass isochron_method from Plot Controls dropdown
                _iso_method = self.DiagramPlots_SHPage.isochronMethodCombo.currentData() or 'ols'
                result, limits = Utilities.getDFStatistics_sh(
                    self.Dfilename, self.mask, self.parameters, 'r', 'o',
                    xlim=xlim, ylim=ylim, legend_name=legend,
                    show_temp=show_temp, show_atm=show_atm, atm_ratio=atm_ratio,
                    return_limits=True, pname=pname, style=self._get_plot_style(),
                    iso_groups=self._effective_step_groups(), group_colors=self.GROUP_COLORS,
                    return_points=True, show_legend=_show_leg,
                    show_group_fits=self.DiagramPlots_SHPage.showGroupFitsCheckbox.isChecked(),
                    show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
                    isochron_method=_iso_method,
)
                # FIX#8: store point data for isochron click detection
                self.iso_pts_DFN = limits.get('DFN_pts', self.iso_pts_DFN)
                self.iso_pts_DFI = limits.get('DFI_pts', self.iso_pts_DFI)

                # v3.8.6: build regression info suffix and stash it on the page.
                # on_mouse_move_SH + other infoLabel writers append this so
                # method + regression MSWD always show in the grey strip.
                try:
                    _reg_method = limits.get('regression_method', _iso_method)
                    _reg_mswd   = limits.get('regression_mswd', float('nan'))
                    _reg_n      = limits.get('regression_n', 0)
                    if pname in ('DFN', 'DFI'):
                        _m_lbl = 'York 2004' if _reg_method == 'york' else 'OLS'
                        _m_str = (f'{_reg_mswd:.2f}'
                                  if _reg_mswd == _reg_mswd else '—')
                        self.DiagramPlots_SHPage._regression_info_str = (
                            f'Method: {_m_lbl}   |   '
                            f'Regression MSWD: {_m_str} (n={_reg_n})')
                    else:
                        self.DiagramPlots_SHPage._regression_info_str = ""
                    # show immediately (before user moves mouse over plot)
                    if self.DiagramPlots_SHPage._regression_info_str:
                        self.DiagramPlots_SHPage.infoLabel.setText(
                            "  " + self.DiagramPlots_SHPage._regression_info_str)
                except Exception:
                    self.DiagramPlots_SHPage._regression_info_str = ""
                
                # Get actual limits for current diagram
                if pname == "DFN" and "DFN" in limits:
                    actual_xlim, actual_ylim = limits["DFN"]
                elif pname == "DFI" and "DFI" in limits:
                    actual_xlim, actual_ylim = limits["DFI"]
                else:
                    actual_xlim = xlim if xlim is not None else (0, 100)
                    actual_ylim = ylim if ylim is not None else (0, 10)
                    
            elif pname in ("DFW", "DFA", "DFC"):
                # FIX: pass target_plot so only active diagram gets limits
                _show_leg  = self.DiagramPlots_SHPage.showLegendCheckbox.isChecked()
                _log_y     = self.DiagramPlots_SHPage.logYCheckbox.isChecked()
                _grp_span  = self.DiagramPlots_SHPage.showGroupSpanCheckbox.isChecked()
                result = Utilities.getSHStatistics(
                    self.Dfilename, self.mask, self.parameters,
                    xlim=xlim, ylim=ylim, legend_name=legend,
                    target_plot=pname, style=self._get_plot_style(),
                    step_groups=self._effective_step_groups(), group_colors=self.GROUP_COLORS,
                    show_legend=_show_leg, log_y=_log_y, show_group_span=_grp_span
                )
                # Store step data, axes_bbox, actual limits for click/hover
                if isinstance(result, dict):
                    self.step_data.update(result.get("step_data", {}))
                    for _pn in ("DFW", "DFA", "DFC"):
                        if _pn in result.get("axes_bbox", {}):
                            self._axes_bboxes[_pn] = result["axes_bbox"][_pn]
                        if _pn in result.get("actual_xlim", {}):
                            self._actual_xlims[_pn] = result["actual_xlim"][_pn]
                        if _pn in result.get("actual_ylim", {}):
                            self._actual_ylims[_pn] = result["actual_ylim"][_pn]
                    if "axes_bbox" in result and pname in result["axes_bbox"]:
                        self.DiagramPlots_SHPage.current_axes_bbox = result["axes_bbox"][pname]

                # Use actual limits from the plot
                actual_xlim = self._actual_xlims.get(pname, xlim if xlim else (0, 100))
                actual_ylim = self._actual_ylims.get(pname, ylim if ylim else (0, 10))
            elif pname == "DFS":
                # === Stack plot (Ca/K or Cl/K + Age) =================
                # Decide which panel the spinboxes are targeting
                page = self.DiagramPlots_SHPage
                panel_idx = page.stackPanelCombo.currentIndex()
                panel_key = 'top' if panel_idx == 0 else 'bot'
                # Persist current spinbox values for the selected panel
                cfg = getattr(self, '_dfs_config', None) or {
                    'top_xlim': None, 'top_ylim': None,
                    'bot_xlim': None, 'bot_ylim': None,
                }
                cfg[f'{panel_key}_xlim'] = xlim
                cfg[f'{panel_key}_ylim'] = ylim
                self._dfs_config = cfg

                # Top-panel log scale: DFS uses logYCheckbox to drive the popup's cb_log equivalent
                self._dfs_log = page.logYCheckbox.isChecked()

                Utilities.getStackPlot(
                    self.Dfilename, self.mask, self.parameters,
                    top=getattr(self, '_dfs_top_type', 'Ca/K'),
                    log_scale=self._dfs_log,
                    h_ratio=getattr(self, '_dfs_hratio', (1, 4)),
                    legend_name=legend or None,
                    style=self._get_plot_style(),
                    xlim_top=cfg.get('top_xlim'),
                    ylim_top=cfg.get('top_ylim'),
                    xlim_bot=cfg.get('bot_xlim'),
                    ylim_bot=cfg.get('bot_ylim'),
                    step_groups=self._effective_step_groups(),
                    group_colors=self.GROUP_COLORS,
                )
                actual_xlim = xlim if xlim is not None else (0, 100)
                actual_ylim = ylim if ylim is not None else (0, 10)
            elif pname == "DFD":
                # === Degassing pattern (per-step Ar component vs temperature)
                page = self.DiagramPlots_SHPage
                _res = Utilities.getDegasPlot(
                    self.Dfilename, self.mask, self.parameters,
                    xlim=xlim, ylim=ylim,
                    legend_name=legend or None,
                    show_legend=page.showLegendCheckbox.isChecked(),
                    log_y=page.logYCheckbox.isChecked(),
                    show_all_components=page.showAllCompCheckbox.isChecked(),
                    components_filter=getattr(self, '_dfd_components_filter', None),
                    show_errorbars=page.showErrorBarsCheckbox.isChecked(),
                    style=self._get_plot_style(),
                )
                if isinstance(_res, dict):
                    self.step_data.update(_res.get("step_data", {}))
                    for k, v in _res.get("actual_xlim", {}).items():
                        self._actual_xlims[k] = v
                    for k, v in _res.get("actual_ylim", {}).items():
                        self._actual_ylims[k] = v
                    for k, v in _res.get("axes_bbox", {}).items():
                        self._axes_bboxes[k] = v
                # use actual rendered limits + bbox for correct hover coord mapping
                actual_xlim = self._actual_xlims.get("DFD", xlim if xlim is not None else (0, 1600))
                actual_ylim = self._actual_ylims.get("DFD", ylim if ylim is not None else (1e-12, 1e-6))
                if "DFD" in self._axes_bboxes:
                    self.DiagramPlots_SHPage.current_axes_bbox = self._axes_bboxes["DFD"]
        except Exception as e:
            import traceback
            print(f"[ERROR] Error in SH_apply_axes: {e}")
            print(f"[ERROR] Full traceback:")
            traceback.print_exc()
            # Re-raise to see the error
            raise

        QtGui.QPixmapCache.clear()
        self.DiagramPlots_SHPage.photo.setPixmap(
            QtGui.QPixmap(self.work_dir + f".work/{pname}.png")
        )
        
        # Set mouse callback and current axis limits for coordinate transformation
        # Use actual limits from the plot, not user input
        self.DiagramPlots_SHPage._mouse_move_callback = self.on_mouse_move_SH
        self.DiagramPlots_SHPage.current_xlim = actual_xlim
        self.DiagramPlots_SHPage.current_ylim = actual_ylim

        # Auto-populate spinbox values with actual data range (smart decimals)
        page = self.DiagramPlots_SHPage
        def _smart_set(sb, val):
            if not np.isfinite(val):
                return
            if val == 0.0:
                sb.setDecimals(2); sb.setValue(0.0); return
            import math
            mag = int(math.floor(math.log10(abs(val))))
            decs = max(1, min(-mag + 3, 9))
            sb.setDecimals(decs)
            sb.setValue(val)
        page.xmin.blockSignals(True); page.xmax.blockSignals(True)
        page.ymin.blockSignals(True); page.ymax.blockSignals(True)
        if page.xAuto.isChecked():
            _smart_set(page.xmin, float(actual_xlim[0]))
            _smart_set(page.xmax, float(actual_xlim[1]))
        if page.yAuto.isChecked():
            _smart_set(page.ymin, float(actual_ylim[0]))
            _smart_set(page.ymax, float(actual_ylim[1]))
        page.xmin.blockSignals(False); page.xmax.blockSignals(False)
        page.ymin.blockSignals(False); page.ymax.blockSignals(False)

    # ── DFM (Summary) per-panel control helpers ────────────────
    def _dfm_load_active_to_controls(self):
        """Load active panel's saved xlim/ylim/legend into Plot Controls."""
        page = self.DiagramPlots_SHPage
        key = getattr(self, '_dfm_active_key', None)
        if not key:
            return
        plim  = getattr(self, '_dfm_panel_limits',  {}) or {}
        plegs = getattr(self, '_dfm_panel_legends', {}) or {}
        lim = plim.get(key)
        xlim = lim[0] if lim else None
        ylim = lim[1] if lim else None
        for sb in [page.xmin, page.xmax, page.ymin, page.ymax]:
            sb.blockSignals(True)
        if xlim is not None:
            page.xAuto.setChecked(False)
            page.xmin.setEnabled(True); page.xmax.setEnabled(True)
            page.xmin.setValue(float(xlim[0])); page.xmax.setValue(float(xlim[1]))
        else:
            page.xAuto.setChecked(True)
            page.xmin.setEnabled(False); page.xmax.setEnabled(False)
        if ylim is not None:
            page.yAuto.setChecked(False)
            page.ymin.setEnabled(True); page.ymax.setEnabled(True)
            page.ymin.setValue(float(ylim[0])); page.ymax.setValue(float(ylim[1]))
        else:
            page.yAuto.setChecked(True)
            page.ymin.setEnabled(False); page.ymax.setEnabled(False)
        for sb in [page.xmin, page.xmax, page.ymin, page.ymax]:
            sb.blockSignals(False)
        page.legendName.setText(plegs.get(key, ''))

    def _dfm_on_panel_changed(self, idx):
        """Combo changed: save current spinbox state to previously active panel,
        then load newly selected panel's settings."""
        if idx < 0:
            return
        page = self.DiagramPlots_SHPage
        prev = getattr(self, '_dfm_active_key', None)
        if prev:
            xlim, ylim, legend = self._read_SH_controls()
            plim  = getattr(self, '_dfm_panel_limits',  {}) or {}
            plegs = getattr(self, '_dfm_panel_legends', {}) or {}
            plim[prev] = (xlim, ylim)
            if legend is not None:
                plegs[prev] = legend
            elif prev in plegs:
                plegs.pop(prev, None)
            self._dfm_panel_limits  = plim
            self._dfm_panel_legends = plegs
        new_key = page.dfmPanelCombo.itemData(idx)
        self._dfm_active_key = new_key
        self._dfm_load_active_to_controls()


    def SH_auto_axes(self):
        """Auto button: calculate optimal range and redraw for CURRENT diagram.

        For DFS/DFM, only the currently selected sub-panel is auto-ranged."""
        pname = getattr(self, "pname", "DFN")
        page = self.DiagramPlots_SHPage

        x, y = self._get_current_xy_data()

        if len(x) < 2:
            return

        # Calculate auto range based on current diagram type
        if pname in ("DFW", "DFA", "DFC"):
            xmin, xmax = 0.0, 100.0
            _, _, ymin, ymax = self._calc_auto_range(x, y)
        elif pname == "DFS":
            # Stack: x is always cumulative %39Ar (0-100); y per selected panel
            xmin, xmax = 0.0, 100.0
            _, _, ymin, ymax = self._calc_auto_range(x, y)
        elif pname == "DFD":
            # Degas: auto both x (temperature) and y (Ar amounts)
            xmin, xmax, ymin, ymax = self._calc_auto_range(x, y)
            # widen y a bit if log scale is on (avoid clipping at min)
            if page.logYCheckbox.isChecked() and ymin > 0:
                ymin = ymin * 0.5
                ymax = ymax * 2
        elif pname == "DFM":
            # Summary: x range depends on active panel type
            key = getattr(self, '_dfm_active_key', None)
            if key in ("age", "atm", "cak", "clk"):
                xmin, xmax = 0.0, 100.0
                _, _, ymin, ymax = self._calc_auto_range(x, y)
            else:
                xmin, xmax, ymin, ymax = self._calc_auto_range(x, y)
        else:
            xmin, xmax, ymin, ymax = self._calc_auto_range(x, y)

        # Update UI controls (uncheck Auto so values are visible/editable)
        for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
            w.blockSignals(True)
        page.xAuto.setChecked(False)
        page.yAuto.setChecked(False)
        page.xmin.setEnabled(True); page.xmax.setEnabled(True)
        page.ymin.setEnabled(True); page.ymax.setEnabled(True)
        page.xmin.setValue(float(xmin))
        page.xmax.setValue(float(xmax))
        page.ymin.setValue(float(ymin))
        page.ymax.setValue(float(ymax))
        for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
            w.blockSignals(False)

        # Persist config in the right place per diagram
        if pname == "DFS":
            cfg = getattr(self, '_dfs_config', None) or {
                'top_xlim': None, 'top_ylim': None,
                'bot_xlim': None, 'bot_ylim': None,
            }
            panel_key = 'top' if page.stackPanelCombo.currentIndex() == 0 else 'bot'
            cfg[f'{panel_key}_xlim'] = (xmin, xmax)
            cfg[f'{panel_key}_ylim'] = (ymin, ymax)
            self._dfs_config = cfg
        elif pname == "DFM":
            key = getattr(self, '_dfm_active_key', None)
            if key:
                plim = getattr(self, '_dfm_panel_limits', {}) or {}
                plim[key] = ((xmin, xmax), (ymin, ymax))
                self._dfm_panel_limits = plim
        else:
            self._save_SH_config(pname, (xmin, xmax), (ymin, ymax), page.legendName.text())

        # Redraw ONLY the current diagram
        self.SH_apply_axes()

    def SH_reset_axes(self):
        """Reset: clear saved config and redraw with auto axes.

        For DFS/DFM, only the currently selected sub-panel is cleared."""
        pname = getattr(self, 'pname', 'DFN')
        page = self.DiagramPlots_SHPage

        if pname == "DFS":
            cfg = getattr(self, '_dfs_config', None) or {
                'top_xlim': None, 'top_ylim': None,
                'bot_xlim': None, 'bot_ylim': None,
            }
            panel_key = 'top' if page.stackPanelCombo.currentIndex() == 0 else 'bot'
            cfg[f'{panel_key}_xlim'] = None
            cfg[f'{panel_key}_ylim'] = None
            self._dfs_config = cfg
            # reset spinboxes to auto
            for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
                w.blockSignals(True)
            page.xAuto.setChecked(True)
            page.yAuto.setChecked(True)
            page.xmin.setEnabled(False); page.xmax.setEnabled(False)
            page.ymin.setEnabled(False); page.ymax.setEnabled(False)
            for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
                w.blockSignals(False)
            self.SH_apply_axes()
            return

        if pname == "DFM":
            key = getattr(self, '_dfm_active_key', None)
            if key:
                plim = getattr(self, '_dfm_panel_limits', {}) or {}
                plim.pop(key, None)
                self._dfm_panel_limits = plim
            for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
                w.blockSignals(True)
            page.xAuto.setChecked(True)
            page.yAuto.setChecked(True)
            page.xmin.setEnabled(False); page.xmax.setEnabled(False)
            page.ymin.setEnabled(False); page.ymax.setEnabled(False)
            for w in [page.xAuto, page.yAuto, page.xmin, page.xmax, page.ymin, page.ymax]:
                w.blockSignals(False)
            self.SH_apply_axes()
            return

        # Default behaviour for DFW/DFA/DFC/DFN/DFI
        self._save_SH_config(pname, None, None, None)
        self._load_SH_config(pname)
        self.SH_apply_axes()

    def on_mouse_move_SH(self, x_mouse, y_mouse):
        """Handle mouse movement over Step Heating diagrams"""
        pname = getattr(self, "pname", "DFN")
        
        # Display coordinate info
        info_text = f"X: {x_mouse:.2f}, Y: {y_mouse:.4f}"
        
        # Check if mouse is over a step in Age or Ca/K spectrum
        if pname == "DFW" and "DFW" in self.step_data:
            for step_info in self.step_data["DFW"]:
                # Format: (step_num, x_start, x_end, ar39_percent, age, age_std,
                #         ar39_amount, temp_c, ar_r_pct, cak_step, cak_step_std)
                step_num, x_start, x_end, ar39_percent, age, age_std, ar39_amount, *_rest = step_info
                temp_c = _rest[0] if len(_rest) >= 1 else float('nan')
                ar_r_pct = _rest[1] if len(_rest) >= 2 else float('nan')
                cak_step = _rest[2] if len(_rest) >= 3 else float('nan')
                if x_start <= x_mouse <= x_end:
                    temp_str = f" | {temp_c:.0f}°C" if temp_c == temp_c else ""
                    ar_r_str = f" | %⁴⁰Ar*: {ar_r_pct:.1f}%" if ar_r_pct == ar_r_pct else ""
                    cak_str  = f" | Ca/K: {cak_step:.4f}" if cak_step == cak_step else ""
                    info_text = (f"Step {step_num}{temp_str} | "
                               f"³⁹Ar(%): {ar39_percent:.1f}% ({x_start:.1f}-{x_end:.1f}%) | "
                               f"Age: {age:.2f} ± {age_std:.2f} Ma{ar_r_str}{cak_str}")
                    break
        
        elif pname == "DFA" and "DFA" in self.step_data:
            for step_info in self.step_data["DFA"]:
                # Format: (step_num, x_start, x_end, ar39_percent, cak, cak_std,
                #         ar39_amount, ar_r_pct)
                step_num, x_start, x_end, ar39_percent, cak, cak_std, ar39_amount, *_rest = step_info
                ar_r_pct = _rest[0] if len(_rest) >= 1 else float('nan')
                if x_start <= x_mouse <= x_end:
                    ar_r_str = f" | %⁴⁰Ar*: {ar_r_pct:.1f}%" if ar_r_pct == ar_r_pct else ""
                    info_text = (f"Step {step_num} | "
                               f"³⁹Ar(%): {ar39_percent:.1f}% ({x_start:.1f}-{x_end:.1f}%) | "
                               f"Ca/K: {cak:.4f} ± {cak_std:.4f}{ar_r_str}")
                    break

        elif pname == "DFC" and "DFC" in self.step_data:
            for step_info in self.step_data["DFC"]:
                # Format: (step_num, x_start, x_end, ar39_percent, clk, clk_std,
                #         ar39_amount, ar_r_pct, cak_step)
                step_num, x_start, x_end, ar39_percent, clk, clk_std, ar39_amount, *_rest = step_info
                ar_r_pct = _rest[0] if len(_rest) >= 1 else float('nan')
                cak_step = _rest[1] if len(_rest) >= 2 else float('nan')
                if x_start <= x_mouse <= x_end:
                    ar_r_str = f" | %⁴⁰Ar*: {ar_r_pct:.1f}%" if ar_r_pct == ar_r_pct else ""
                    cak_str  = f" | Ca/K: {cak_step:.4f}" if cak_step == cak_step else ""
                    info_text = (f"Step {step_num} | "
                               f"³⁹Ar(%): {ar39_percent:.1f}% ({x_start:.1f}-{x_end:.1f}%) | "
                               f"Cl/K: {clk:.5f} ± {clk_std:.5f}{ar_r_str}{cak_str}")
                    break

        elif pname == "DFD" and "DFD" in self.step_data:
            # Find nearest (component, step) point to mouse cursor.
            # IMPORTANT: Ar amounts span many orders of magnitude, so we always
            # use log10 distance for Y (regardless of display mode). This makes
            # hovering work the same in linear mode as in log mode.
            import numpy as _np
            xlim = self.DiagramPlots_SHPage.current_xlim or (600, 1500)
            ylim = self.DiagramPlots_SHPage.current_ylim or (1e-10, 1e-2)
            x_range = max(float(xlim[1] - xlim[0]), 1e-6)

            # log Y range derived from data values (broad fallback)
            y_lo = max(float(ylim[0]), 1e-15) if ylim[0] > 0 else 1e-15
            y_hi = max(float(ylim[1]), y_lo * 10.0)
            log_y_range = max(_np.log10(y_hi) - _np.log10(y_lo), 1.0)

            # Convert mouse y to log10 (clamped to avoid log(0))
            y_mouse_clamped = max(float(y_mouse), y_lo * 0.01) if y_mouse > 0 else y_lo
            ym_log = _np.log10(y_mouse_clamped)

            best = None
            best_d = 1e18
            for entry in self.step_data["DFD"]:
                comp, T_val, V_val, pct, step_num = entry
                if not _np.isfinite(T_val) or not _np.isfinite(V_val) or V_val <= 0:
                    continue
                dx = (T_val - x_mouse) / x_range
                dy = (_np.log10(V_val) - ym_log) / log_y_range
                d = dx * dx + dy * dy
                if d < best_d:
                    best_d = d
                    best = entry

            # Threshold: ~16% of normalized distance — generous so points are easy to hit
            if best is not None and best_d < 0.025:
                comp, T_val, V_val, pct, step_num = best
                pct_str = f"{pct:.2f}%" if pct == pct else "n/a"
                info_text = (f"{comp} | Step {step_num} | "
                           f"T={T_val:.0f}°C | V={V_val:.3e} | "
                           f"{pct_str} of {comp} total")

        # v3.8.6: append regression-info suffix so method + regression MSWD
        # stay visible while user hovers over the diagram.
        _suffix = getattr(self.DiagramPlots_SHPage, '_regression_info_str', '')
        if _suffix:
            info_text = info_text + "   |   " + _suffix
        self.DiagramPlots_SHPage.infoLabel.setText(info_text)

    def _clear_groups(self):
        """Clear all group assignments and redraw."""
        self.step_groups.clear()
        pname = getattr(self, "pname", None)
        if pname in ("DFW", "DFA", "DFC", "DFN", "DFI"):
            self._redraw_with_groups()

    def on_click_SH(self, x_data, y_data, button):
        """Handle click on spectrum or isochron: toggle step/point group assignment."""
        from PyQt5.QtCore import Qt
        pname = getattr(self, "pname", "")
        if pname in ("DFW", "DFA", "DFC"):
            step_key = {"DFW": "DFW", "DFA": "DFA", "DFC": "DFC"}[pname]
            if step_key not in self.step_data:
                return
            for step_info in self.step_data[step_key]:
                step_num, x_start, x_end = step_info[0], step_info[1], step_info[2]
                if x_start <= x_data <= x_end:
                    idx = step_num - 1  # 0-based
                    if button == Qt.RightButton:
                        self.step_groups.pop(idx, None)
                    else:
                        if self.step_groups.get(idx) == self.active_group:
                            del self.step_groups[idx]
                        else:
                            self.step_groups[idx] = self.active_group
                    self._redraw_with_groups()
                    break
        elif pname in ("DFN", "DFI"):
            # FIX#8: click on isochron – find nearest data point within tolerance
            pts = self.iso_pts_DFN if pname == "DFN" else self.iso_pts_DFI
            if not pts:
                return
            xlim = self.DiagramPlots_SHPage.current_xlim
            ylim = self.DiagramPlots_SHPage.current_ylim
            xr = max(xlim[1] - xlim[0], 1e-6) if xlim else 1.0
            yr = max(ylim[1] - ylim[0], 1e-6) if ylim else 1.0
            best_d, best_orig = float('inf'), None
            for (px, py, orig_idx) in pts:
                d = ((x_data - px) / xr) ** 2 + ((y_data - py) / yr) ** 2
                if d < best_d:
                    best_d = d
                    best_orig = orig_idx
            # BUG FIX: B9 - Use constant instead of magic number
            _CLICK_TOL = 0.03  # Click tolerance in normalized coords (3% of axis range)
            if best_orig is None or best_d > _CLICK_TOL ** 2:
                return  # click too far from any data point
            if button == Qt.RightButton:
                self.step_groups.pop(best_orig, None)
            else:
                if self.step_groups.get(best_orig) == self.active_group:
                    del self.step_groups[best_orig]
                else:
                    self.step_groups[best_orig] = self.active_group
            self._redraw_with_groups()

    def _redraw_with_groups(self):
        """Redraw current spectrum or isochron with updated group colors."""
        pname = getattr(self, "pname", "")
        if pname in ("DFW", "DFA", "DFC"):
            xlim, ylim, legend = self._read_SH_controls()
            _st = self._get_plot_style()
            try:
                _show_leg  = self.DiagramPlots_SHPage.showLegendCheckbox.isChecked()
                _log_y     = self.DiagramPlots_SHPage.logYCheckbox.isChecked()
                _grp_span  = self.DiagramPlots_SHPage.showGroupSpanCheckbox.isChecked()
                result = Utilities.getSHStatistics(
                    self.Dfilename, self.mask, self.parameters,
                    xlim=xlim, ylim=ylim, legend_name=legend,
                    target_plot=pname, style=_st,
                    step_groups=self._effective_step_groups(),
                    group_colors=self.GROUP_COLORS,
                    show_legend=_show_leg, log_y=_log_y, show_group_span=_grp_span
                )
                if isinstance(result, dict) and "step_data" in result:
                    self.step_data.update(result["step_data"])
            except Exception:
                pass
            QtGui.QPixmapCache.clear()
            fname = {"DFW": "DFW", "DFA": "DFA", "DFC": "DFC"}.get(pname, pname)
            self.DiagramPlots_SHPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + f".work/{fname}.png"))
        elif pname in ("DFN", "DFI"):
            # FIX#8: Redraw isochron with group regression lines
            xlim, ylim, legend = self._read_SH_controls()
            show_temp = self.DiagramPlots_SHPage.showTempCheckbox.isChecked()
            show_atm  = self.DiagramPlots_SHPage.showAtmCheckbox.isChecked()
            atm_ratio = self.DiagramPlots_SHPage.atmRatio.value()
            try:
                _show_leg = self.DiagramPlots_SHPage.showLegendCheckbox.isChecked()
                result, limits = Utilities.getDFStatistics_sh(
                    self.Dfilename, self.mask, self.parameters, 'r', 'o',
                    xlim=xlim, ylim=ylim, legend_name=legend,
                    show_temp=show_temp, show_atm=show_atm, atm_ratio=atm_ratio,
                    return_limits=True, return_points=True,
                    pname=pname, style=self._get_plot_style(),
                    iso_groups=self._effective_step_groups(), group_colors=self.GROUP_COLORS,
                    show_legend=_show_leg,
                    show_group_fits=self.DiagramPlots_SHPage.showGroupFitsCheckbox.isChecked(),
                    show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
)
                self.iso_pts_DFN = limits.get('DFN_pts', self.iso_pts_DFN)
                self.iso_pts_DFI = limits.get('DFI_pts', self.iso_pts_DFI)
                lims = limits.get(pname, (None, None))
                if lims[0]:
                    self.DiagramPlots_SHPage.current_xlim = lims[0]
                    self._actual_xlims[pname] = lims[0]
                if lims[1]:
                    self.DiagramPlots_SHPage.current_ylim = lims[1]
                    self._actual_ylims[pname] = lims[1]
                _bbox_key = pname + '_bbox'
                if _bbox_key in limits:
                    self._axes_bboxes[pname] = limits[_bbox_key]
                    self.DiagramPlots_SHPage.current_axes_bbox = limits[_bbox_key]
                # Build info string for selected group(s)
                _info_parts = []
                for _gn in sorted(set(self.step_groups.values())):
                    _gsel = [_oi for _oi, _g in self.step_groups.items() if _g == _gn]
                    n_sel = len(_gsel)
                    if n_sel == 0:
                        continue
                    _gc_name = f"G{_gn}"
                    if pname == "DFI":
                        _pts = self.iso_pts_DFI
                    else:
                        _pts = self.iso_pts_DFN
                    _gpts = [(px, py) for (px, py, oi) in _pts if oi in _gsel]
                    if n_sel == 1 and _gpts:
                        _atm_ratio = self.DiagramPlots_SHPage.atmRatio.value()
                        _x0g, _y0g = _gpts[0]
                        if pname == "DFI":
                            _atm_y = 1.0 / _atm_ratio if _atm_ratio else 1.0/298.56
                            _m1g = (_y0g - _atm_y) / _x0g if _x0g != 0 else float('nan')
                            _xintg = -_atm_y / _m1g if _m1g != 0 else float('nan')
                            _atm4036 = 1.0 / _atm_y if _atm_y != 0 else float('nan')
                            _info_parts.append(f"{_gc_name}(1pt): ⁴⁰/³⁶={_atm4036:.0f}(fixed) | X-int={_xintg:.4f}")
                        else:
                            _atm_y = float(_atm_ratio) if _atm_ratio else 298.56
                            _m1g = (_y0g - _atm_y) / _x0g if _x0g != 0 else float('nan')
                            _info_parts.append(f"{_gc_name}(1pt): ⁴⁰/³⁶={_atm_y:.0f}(fixed) | slope={_m1g:.4f}")
                    elif n_sel >= 2 and len(_gpts) >= 2:
                        import numpy as _np
                        _gxs = _np.array([p[0] for p in _gpts])
                        _gys = _np.array([p[1] for p in _gpts])
                        try:
                            _A = _np.vstack([_gxs, _np.ones(len(_gxs))]).T
                            _b_reg, _a_reg = _np.linalg.lstsq(_A, _gys, rcond=None)[0]
                            _xint_g = -_a_reg / _b_reg if _b_reg != 0 else float('nan')
                            _resid = _gys - (_a_reg + _b_reg * _gxs)
                            _mswd_g = float(_np.sum(_resid**2) / max(n_sel - 2, 1))
                            if pname == "DFI":
                                _4036 = 1.0 / _a_reg if _a_reg != 0 else float('nan')
                                _info_parts.append(
                                    f"{_gc_name}({n_sel}pts): ⁴⁰/³⁶={_4036:.1f} | X-int={_xint_g:.4f} | MSWD={_mswd_g:.2f}")
                            else:
                                _4036 = _a_reg
                                _info_parts.append(
                                    f"{_gc_name}({n_sel}pts): ⁴⁰/³⁶={_4036:.1f} | slope={_b_reg:.4f} | MSWD={_mswd_g:.2f}")
                        except Exception:
                            pass
                # v3.8.6: tack on the regression-info suffix
                _suffix = getattr(self.DiagramPlots_SHPage, '_regression_info_str', '')
                if _suffix:
                    _info_parts.append(_suffix)
                if _info_parts:
                    self.DiagramPlots_SHPage.infoLabel.setText("  " + "   |   ".join(_info_parts))
            except Exception:
                import traceback; traceback.print_exc()
            QtGui.QPixmapCache.clear()
            fname = "DFN" if pname == "DFN" else "DFI"
            self.DiagramPlots_SHPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + f".work/{fname}.png"))

    # ===============================================================================
    def run(self):
        # load parameters
        self.loadParameterSeting()

        # deal with click or keyin events
        # click button on Homepage
        self.HomePage.LRP.clicked.connect(self.toTS)
        self.HomePage.T0S.clicked.connect(self.toSS)
        self.HomePage.MR.clicked.connect(self.toMR)
        self.HomePage.JV.clicked.connect(self.toJS)
        self.HomePage.AC.clicked.connect(self.toAC)
        self.HomePage.SC.clicked.connect(self.toSCS)
        self.HomePage.DF.clicked.connect(self.toDS)
        self.HomePage.DP.clicked.connect(self.toDPS)
        self.HomePage.AP.clicked.connect(self.toAP)
        self.HomePage.PS_button.clicked.connect(self.toPS)
        self.HomePage.actionParameter_Setting.triggered.connect(self.toPS)
        self.HomePage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.HomePage.actionCheck_Update.triggered.connect(self.checkVersion)

        # click button on TypeSelect
        self.TypeSelect.MB.clicked.connect(self.toLRP_MB)
        self.TypeSelect.PBa.clicked.connect(self.toLRP_PBa)
        self.TypeSelect.AS.clicked.connect(self.toLRP_AS)
        self.TypeSelect.PBs.clicked.connect(self.toLRP_PBs)
        self.TypeSelect.SP.clicked.connect(self.toLRP_SP)
        self.TypeSelect.TP.clicked.connect(self.toLRP_TP)
        self.TypeSelect.ST.clicked.connect(self.toLRP_ST)
        self.TypeSelect.actionParameter_Setting.triggered.connect(self.toPS)
        self.TypeSelect.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.TypeSelect.actionCheck_Update.triggered.connect(self.checkVersion)
        self.TypeSelect.goHome.triggered.connect(self.toMain)

        # click button on Linear Regression Page
        self.T0CalculationPage.return_2.clicked.connect(self.toMain)
        self.T0CalculationPage.save.clicked.connect(self.LRP_save)
        self.T0CalculationPage.reselect.clicked.connect(self.LRP_reselect)
        self.T0CalculationPage.linear.clicked.connect(self.LRP_useLinear)
        self.T0CalculationPage.average.clicked.connect(self.LRP_useAverage)
        self.T0CalculationPage.new_2.clicked.connect(self.toTS)
        
        # click button on Stat Select
        self.StatSelectPage.T0.clicked.connect(self.toT0S)
        self.StatSelectPage.J.clicked.connect(self.toJSS)
        self.StatSelectPage.ARS.clicked.connect(self.toARS)
        self.StatSelectPage.Salt.clicked.connect(self.toSSS)
        self.StatSelectPage.actionParameter_Setting.triggered.connect(self.toPS)
        self.StatSelectPage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.StatSelectPage.actionCheck_Update.triggered.connect(self.checkVersion)
        self.StatSelectPage.goHome.triggered.connect(self.toMain)
        
        # click button on T0 statistics page
        self.T0StatisticsPage.return_2.clicked.connect(self.toMain)
        self.T0StatisticsPage.save.clicked.connect(self.T0S_save)
        self.T0StatisticsPage.new_2.clicked.connect(self.toSS)
        self.T0StatisticsPage.reselect.clicked.connect(self.T0_reselect)
        
        # click button on Salt statistics select page
        self.SaltStatSelectPage.Ca36.clicked.connect(self.toS36Ca)
        self.SaltStatSelectPage.Ca39.clicked.connect(self.toS39Ca)
        self.SaltStatSelectPage.K40.clicked.connect(self.toS40K)
        self.SaltStatSelectPage.K38.clicked.connect(self.toS38K)
        self.SaltStatSelectPage.K39.clicked.connect(self.toS39K)
        self.SaltStatSelectPage.actionParameter_Setting.triggered.connect(self.toPS)
        self.SaltStatSelectPage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.SaltStatSelectPage.actionCheck_Update.triggered.connect(self.checkVersion)
        self.SaltStatSelectPage.goHome.triggered.connect(self.toMain)
        
        # click button on Salt statistics page
        self.SaltStatPage.return_2.clicked.connect(self.toMain)
        self.SaltStatPage.save.clicked.connect(self.SSC_save)
        self.SaltStatPage.new_2.clicked.connect(self.toSS)
        self.SaltStatPage.reselect.clicked.connect(self.Salt_reselect)
        
        # click button on J statistics page
        self.JStatisticsPage.return_2.clicked.connect(self.toMain)
        self.JStatisticsPage.save.clicked.connect(self.JSS_save)
        self.JStatisticsPage.new_2.clicked.connect(self.toSS)
        self.JStatisticsPage.reselect.clicked.connect(self.J_reselect)
        
        # click button on Air Ratio Statistics page
        self.AirRatioStatisticsPage.return_2.clicked.connect(self.toMain)
        self.AirRatioStatisticsPage.save.clicked.connect(self.ARS_save)
        self.AirRatioStatisticsPage.new_2.clicked.connect(self.toSS)

        # click button on Mass Ratio page
        self.MassRatioPage.return_2.clicked.connect(self.toMain)
        self.MassRatioPage.save.clicked.connect(self.MR_save)
        self.MassRatioPage.new_2.clicked.connect(self.toMR)

        # click button on J Volume Calculation page
        self.JCalculationPage.return_2.clicked.connect(self.toMain)
        self.JCalculationPage.save.clicked.connect(self.JV_save)
        self.JCalculationPage.new_2.clicked.connect(self.toJS)
        
         # click button on JSelect
        self.JSelectPage.FSC.clicked.connect(self.toJV_FSC)
        self.JSelectPage.LP6.clicked.connect(self.toJV_LP6)
        self.JSelectPage.MMHB.clicked.connect(self.toJV_MMHB)
        self.JSelectPage.actionParameter_Setting.triggered.connect(self.toPS)
        self.JSelectPage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.JSelectPage.actionCheck_Update.triggered.connect(self.checkVersion)
        self.JSelectPage.goHome.triggered.connect(self.toMain)

        # click button on Parameter Setting page
        self.ParameterSettingPage.return_2.clicked.connect(self.PS_return)
        self.ParameterSettingPage.change.clicked.connect(self.PS_change)
        self.ParameterSettingPage.save.clicked.connect(self.PS_save)
        self.ParameterSettingPage.raw.clicked.connect(self.PS_raw)
        self.ParameterSettingPage.cancel.clicked.connect(self.PS_cancel)

        # click button on Age Calculation page
        self.AgeCalculationPage.return_2.clicked.connect(self.toMain)
        self.AgeCalculationPage.save.clicked.connect(self.AC_save)
        self.AgeCalculationPage.new_2.clicked.connect(self.toAC)

        # v3.8.4: enforce a minimum splash display so users can read it. Uses
        # QEventLoop + QTimer so the splash keeps painting during the wait (a
        # plain time.sleep would freeze it).
        # v3.8.81: 3000 → 1000 ms. On a warm start the whole app loads in ~2-3s,
        # so the old 3s floor WAS the startup bottleneck; 1s is enough to read
        # the version/credits without holding the window back.
        _splash_min_ms = 1000
        if getattr(self, '_splash', None) is not None and \
           getattr(self, '_splash_t0', None) is not None:
            import time as _time
            _elapsed_ms = int((_time.monotonic() - self._splash_t0) * 1000)
            _remaining = _splash_min_ms - _elapsed_ms
            if _remaining > 0:
                _loop = QtCore.QEventLoop()
                QtCore.QTimer.singleShot(_remaining, _loop.quit)
                _loop.exec_()

        self.widget.show()
        # v3.8.4: dismiss splash once main window is visible
        if getattr(self, '_splash', None) is not None:
            try:
                self._splash.finish(self.widget)
            except Exception:
                pass
            self._splash = None
        # FIX: center window on screen — use frameGeometry to include title bar
        QtWidgets.QApplication.processEvents()
        _sg  = QtWidgets.QApplication.primaryScreen().availableGeometry()
        _fg  = self.widget.frameGeometry()
        self.widget.move(
            _sg.x() + (_sg.width()  - _fg.width())  // 2,
            _sg.y() + (_sg.height() - _fg.height()) // 2,
        )

         # click button on Salt Calculation page
        self.SaltCalculationPage.return_2.clicked.connect(self.toMain)
        self.SaltCalculationPage.save.clicked.connect(self.SC_save)
        self.SaltCalculationPage.new_2.clicked.connect(self.toSCS)
        
         # click button on SaltSelect
        self.SaltSelectPage.Ca.clicked.connect(self.toSCa)
        self.SaltSelectPage.K.clicked.connect(self.toSK)
        self.SaltSelectPage.actionParameter_Setting.triggered.connect(self.toPS)
        self.SaltSelectPage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.SaltSelectPage.actionCheck_Update.triggered.connect(self.checkVersion)
        self.SaltSelectPage.goHome.triggered.connect(self.toMain)
        
        # click button on Diagram Plots SH Page
        self.DiagramPlots_SHPage.return_2.clicked.connect(self.toMain)
        # v3.8.6: Main menu item → home
        self.DiagramPlots_SHPage.actionGoHome.triggered.connect(self.toMain)
        self.DiagramPlots_SHPage.save.clicked.connect(self.DFSH_save)
        # V3.5 merged: Excel export button connection
        self.DiagramPlots_SHPage.btnExcel.clicked.connect(self.DFSH_export_excel)
        self.DiagramPlots_SHPage.new_2.clicked.connect(self.toDS)
        self.DiagramPlots_SHPage.reselect.clicked.connect(self.SH_reselect)
        self.DiagramPlots_SHPage.N.clicked.connect(self.DF_SN)
        self.DiagramPlots_SHPage.I.clicked.connect(self.DF_SI)
        self.DiagramPlots_SHPage.W.clicked.connect(self.DF_SW)
        self.DiagramPlots_SHPage.A.clicked.connect(self.DF_SA)
        self.DiagramPlots_SHPage.btn3D.clicked.connect(self.DF_S3D)
        self.DiagramPlots_SHPage.btnCL.clicked.connect(self.DF_SCL)
        self.DiagramPlots_SHPage.btnDeg.clicked.connect(self.DF_SDeg)
        self.DiagramPlots_SHPage.btnStack.clicked.connect(self.DF_SSTACK)
        # Group selector button connections
        def _make_grp_handler(n):
            def _h():
                self.active_group = n
                for j, b in enumerate(self.DiagramPlots_SHPage._grp_btns):
                    b.setChecked(j == n-1)
            return _h
        QtCore.QTimer.singleShot(50, lambda: [
            self.DiagramPlots_SHPage._grp_btns[i].clicked.connect(_make_grp_handler(i+1))
            for i in range(len(self.DiagramPlots_SHPage._grp_btns))
        ])
        QtCore.QTimer.singleShot(50, lambda:
            self.DiagramPlots_SHPage._grp_btn_clear.clicked.connect(self._clear_groups)
        )
        # Wire click-to-select for spectra (set once at startup)
        QtCore.QTimer.singleShot(60, lambda: setattr(
            self.DiagramPlots_SHPage, "_click_callback", self.on_click_SH))
        self.DiagramPlots_SHPage.btnApply.clicked.connect(self.SH_apply_axes)
        # v3.8.6 (A2): dropdown change auto-triggers Apply
        self.DiagramPlots_SHPage.isochronMethodCombo.currentIndexChanged.connect(
            self.SH_apply_axes)
        self.DiagramPlots_SHPage.dfmPanelCombo.currentIndexChanged.connect(self._dfm_on_panel_changed)
        self.DiagramPlots_SHPage.btnAuto.clicked.connect(self.SH_auto_axes)
        self.DiagramPlots_SHPage.btnReset.clicked.connect(self.SH_reset_axes)
        self.DiagramPlots_SHPage.box.currentIndexChanged.connect(self.show_SH)
        self.DiagramPlots_SHPage.box2.currentIndexChanged.connect(self.show_SH)
        # FIX#3,5: instant redraw on checkbox/atm toggle
        self.DiagramPlots_SHPage.showTempCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showAtmCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.atmRatio.valueChanged.connect(self.SH_apply_axes)
        # FIX#7: Enter key in spinboxes/legend triggers redraw
        for _sb in [self.DiagramPlots_SHPage.xmin, self.DiagramPlots_SHPage.xmax,
                    self.DiagramPlots_SHPage.ymin, self.DiagramPlots_SHPage.ymax,
                    self.DiagramPlots_SHPage.atmRatio]:
            _sb.editingFinished.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.legendName.returnPressed.connect(self.SH_apply_axes)
        # DFS stack-panel combo: load saved limits when user switches panel
        self.DiagramPlots_SHPage.stackPanelCombo.currentIndexChanged.connect(
            self._on_stack_panel_changed)
        self.DiagramPlots_SHPage.showLegendCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showGroupsCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showGroupFitsCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showOverallFitCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.styleCombo.currentIndexChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.logYCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showGroupSpanCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showAllCompCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.showErrorBarsCheckbox.stateChanged.connect(self.SH_apply_axes)
        self.DiagramPlots_SHPage.btnDFDComponents.clicked.connect(self._dfd_open_components_dialog)
        # Reset custom filter when user toggles "Show all 16 components"
        self.DiagramPlots_SHPage.showAllCompCheckbox.stateChanged.connect(
            lambda _s: setattr(self, '_dfd_components_filter', None))
        
        # click button on Diagram Plots LS Page
        self.DiagramPlots_LSPage.return_2.clicked.connect(self.toMain)
        self.DiagramPlots_LSPage.save.clicked.connect(self.DFLS_save)
        self.DiagramPlots_LSPage.new_2.clicked.connect(self.toDS)
        self.DiagramPlots_LSPage.reselect.clicked.connect(self.LS_reselect)
        self.DiagramPlots_LSPage.N.clicked.connect(self.DF_SN)
        self.DiagramPlots_LSPage.I.clicked.connect(self.DF_SI)
        self.DiagramPlots_LSPage.K.clicked.connect(self.DF_SK)
        self.DiagramPlots_LSPage.P.clicked.connect(self.DF_P)
        self.DiagramPlots_LSPage.box.currentIndexChanged.connect(self.show_LS)
        self.DiagramPlots_LSPage.box2.currentIndexChanged.connect(self.show_LS)
        
        # click button on Diagram Plots Select Page
        self.DiagramSelectPage.SH.clicked.connect(self.toDF_SH)
        self.DiagramSelectPage.LS.clicked.connect(self.toDF_LS)
        self.DiagramSelectPage.actionParameter_Setting.triggered.connect(self.toPS)
        self.DiagramSelectPage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.DiagramSelectPage.actionCheck_Update.triggered.connect(self.checkVersion)
        self.DiagramSelectPage.goHome.triggered.connect(self.toMain)
        # v3.8.7: select pages got a Return button added by _add_return_button().
        # Wire each one to toMain (same pattern as the existing return_2 buttons
        # on the calculation / statistics pages).
        self.TypeSelect.return_2.clicked.connect(self.toMain)
        self.StatSelectPage.return_2.clicked.connect(self.toMain)
        self.JSelectPage.return_2.clicked.connect(self.toMain)
        self.SaltSelectPage.return_2.clicked.connect(self.toMain)
        self.SaltStatSelectPage.return_2.clicked.connect(self.toMain)
        self.DiagramSelectPage.return_2.clicked.connect(self.toMain)
        self.DatumSelectPage.return_2.clicked.connect(self.toMain)
        
        # click button on Datum Select Pag
        self.DatumSelectPage.TT.clicked.connect(self.toDP)
        self.DatumSelectPage.isor.clicked.connect(self.toDPR)
        self.DatumSelectPage.actionParameter_Setting.triggered.connect(self.toPS)
        self.DatumSelectPage.actionAbout_pyADR.triggered.connect(self.systemInfo)
        self.DatumSelectPage.actionCheck_Update.triggered.connect(self.checkVersion)
        self.DatumSelectPage.goHome.triggered.connect(self.toMain)
        
        # close program when pressing x(esc)
        sys.exit(self.app.exec_())
    
    # methods added for UI operation
    # ===============================================================================
    # back to Homepage
    def toMain(self):
        # v3.8.60/63: leave maximized/full-screen (set by toAP) before restoring
        # the normal Home-page window size. showNormal() must come first or the
        # resize is swallowed by the maximized/full-screen state.
        if self.widget.isMaximized() or self.widget.isFullScreen():
            self.widget.showNormal()
        # FIX: restore normal window size when leaving AutoPipeline
        self.widget.resize(800, 700)
        QtWidgets.QApplication.processEvents()
        _sg = QtWidgets.QApplication.primaryScreen().availableGeometry()
        _fg = self.widget.frameGeometry()
        self.widget.move(
            _sg.x() + (_sg.width()  - _fg.width())  // 2,
            _sg.y() + (_sg.height() - _fg.height()) // 2,
        )
        self.widget.setCurrentIndex(0)

    # popup message box
    def Popup(self, msg_type, msg_title, msg_content):
        '''
        msg_type:
        0 NoIcon
        1 Information
        2 Warning
        3 Critical
        4 Question
        '''
        msg = QtWidgets.QMessageBox()
        msg.setIcon(msg_type)
        msg.setText("<font size = 10> {} </font> ".format(msg_title))
        msg.setInformativeText("<font size = 5> {} </font> ".format(msg_content.replace('\n', '<br>')))
        msg.setWindowTitle("")
        msg.exec_()

    # adjust table column and row size
    def TableAdjust(self, table):
        header = table.horizontalHeader()
        for i in range(table.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        header = table.verticalHeader()
        for i in range(table.rowCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

    # display system info
    def systemInfo(self):
        self.Popup(1, "System Info", "".join(self.app_info))

    # Background update check on startup (silent, no popup if up-to-date)
    def _bg_check_update(self):
        """Run on startup in a thread. Show Windows toast if new version exists."""
        try:
            import time
            time.sleep(2)  # let UI finish loading first
            app_info_url = 'https://raw.githubusercontent.com/FormosaRes/pyADR/main/.work/.app_info.txt'
            page = requests.get(app_info_url, timeout=5)
            if not page.ok:
                return
            latest_version = page.text.split('\n')[1].rstrip()
            current_version = self.app_info[1].rstrip()
            if current_version == latest_version:
                return  # already up-to-date, silent
            # New version available — show Windows toast notification
            try:
                from winotify import Notification, audio
                logo_path = os.path.abspath(self.work_dir + '.work/logo.png')
                n = Notification(
                    app_id="pyADR",
                    title=f"pyADR Update Available: v{latest_version}",
                    msg=f"You're on v{current_version}. Click to view release on GitHub.",
                    icon=logo_path if os.path.exists(logo_path) else None,
                    duration="long",
                )
                n.set_audio(audio.Default, loop=False)
                n.add_actions(
                    label="Open GitHub",
                    launch="https://github.com/FormosaRes/pyADR/releases"
                )
                n.show()
            except Exception:
                pass  # winotify failed (non-Windows or import error) — silent
        except Exception:
            pass  # network failure — silent (don't bother user)

    # check if current app is up to date (manual: Menu -> Check Update)
    def checkVersion(self):
        app_info_url = 'https://raw.githubusercontent.com/FormosaRes/pyADR/main/.work/.app_info.txt'
        try:
            page = requests.get(app_info_url)
            if page.ok:
                latest_version = page.text.split('\n')[1].rstrip()
                current_version = self.app_info[1].rstrip()
                version_msg = "Installed Version: {}\nLatest Version: {}\n".format(current_version, latest_version)
                if current_version == latest_version:
                    self.Popup(1, "No updates available at this time", version_msg)
                else:
                    git_repo_url = "https://github.com/FormosaRes/pyADR.git"
                    self.Popup(1, "There are updates available at this time", version_msg+"Please go to {} to update to the latest version!\n".format(git_repo_url))
            else:
                self.Popup(2, "HTTP request failed!", "HTTP status {}".format(page.status_code))
        except:
            self.Popup(2, "No internet connection!", "Please check your internet connection!")

    # methods for parameters setting page
    # ===============================================================================
    def loadParameterSeting(self):
        with open(self.work_dir+'.work/setting.csv', 'r') as f:
            data = f.readlines()

        self.numParamters = int(data[1].split(',')[1])
        self.parameters = []
        self.parameters_name = []
        # first row is header and second row is # of parameters
        for i in range(self.numParamters):
            self.parameters_name.append(data[i+2].split(',')[0].rstrip())
            self.parameters.append(data[i+2].split(',')[1].rstrip())
        f.close()
        
        with open(self.work_dir+'.work/rawpath.txt', 'r') as f:
            self.rawpath = str(f.readline())
        f.close()


    def toPS_from_pipeline(self):
        """v3.8.85: Parameter button on the AutoPipeline pages → leave the
        maximized/full-screen pipeline window, restore the normal window size,
        then open the Parameter Settings page (same target as toPS)."""
        if self.widget.isMaximized() or self.widget.isFullScreen():
            self.widget.showNormal()
        self.widget.resize(800, 700)
        QtWidgets.QApplication.processEvents()
        _sg = QtWidgets.QApplication.primaryScreen().availableGeometry()
        _fg = self.widget.frameGeometry()
        self.widget.move(
            _sg.x() + (_sg.width()  - _fg.width())  // 2,
            _sg.y() + (_sg.height() - _fg.height()) // 2)
        self.toPS()
        self._ps_from_ap = True   # v3.8.86: Return from param → back to Argon Pipeline

    def PS_return(self):
        """v3.8.86: Parameter page Return. If we arrived from AutoPipeline, go
        back THERE (the AutoPipeline pages are never destroyed, so the loaded
        session — .dat, T₀, computed ages — is preserved; toAP also re-pushes
        any params you edited). Otherwise go Home, as before."""
        if getattr(self, '_ps_from_ap', False):
            self._ps_from_ap = False
            self.toAP()
        else:
            self.toMain()

    def toPS(self):
        # v3.8.86: normal entry (Home / menu) → Return goes Home;
        # toPS_from_pipeline overrides _ps_from_ap to True after calling this.
        self._ps_from_ap = False
        # fill the table and set the item as disabled
        for i in range(self.numParamters):
            item = QtWidgets.QTableWidgetItem(self.parameters[i])
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.ParameterSettingPage.ParameetrTable.setItem(i, 0, item)
            
        # show the page
        self.TableAdjust(self.ParameterSettingPage.ParameetrTable)
        self.ParameterSettingPage.change.show()
        self.ParameterSettingPage.cancel.hide()
        self.ParameterSettingPage.save.hide()
        self.widget.setCurrentIndex(5)

    def PS_change(self):
        # show the save and cancel button, hide the change button
        self.ParameterSettingPage.cancel.show()
        self.ParameterSettingPage.save.show()
        self.ParameterSettingPage.change.hide()

        # enable edit (need better way to implement)
        for i in range(self.numParamters):
            item = QtWidgets.QTableWidgetItem(self.parameters[i])
            self.ParameterSettingPage.ParameetrTable.setItem(i, 0, item) # make cell editable

    def PS_save(self):
        error_msg = ''
        changed = 0
        invalid = 0
        

        for i in range(self.numParamters):
            item = self.ParameterSettingPage.ParameetrTable.item(i, 0)
            content = item.text().rstrip()

            # value changed
            if content != self.parameters[i]:
                error_type = 0
                # check if valid
                try:
                    if self.ParameterSettingPage.ParameetrTable.verticalHeaderItem(i).text() == 'numCycle':
                        if int(content) <= 0:
                            error_type = 1
                    else:
                        if float(content) < 0:
                            error_type = 2
                except:
                    error_type = 1 if i > 9 else 2
                
                # new valid value
                if error_type == 0:
                    self.parameters[i] = content # update the parameter
                    changed = 1 # need rewrite setting.csv

                # restore the value
                else:
                    item.setText(self.parameters[i]) 
                    invalid = 1
                    error_msg += '{} should be a {}.\n\n'.format(self.parameters_name[i], 
                    'positive integer' if error_type == 1 else 'non-negative number')

            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit

        self.ParameterSettingPage.change.show()
        self.ParameterSettingPage.cancel.hide()
        self.ParameterSettingPage.save.hide()

        # rewite setting.csv with update parameters value if necessary
        if changed:
            new_ps = ['parameter,value\n', 'numParameters,{}\n'.format(self.numParamters)]
            for i in range(self.numParamters):
                new_ps.append('{},{}\n'.format(self.parameters_name[i], self.parameters[i]))

            with open(self.work_dir+'.work/setting.csv', 'w') as f:
                f.writelines(new_ps)

        if invalid:
            self.Popup(2, 'Invalid Typed Parameters!', error_msg)
        
    def PS_raw(self):
        dir = QtWidgets.QFileDialog.getExistingDirectory(self.widget,"Open Directory",)
        self.rawpath = dir
        with open(self.work_dir+'.work/rawpath.txt', 'w') as f:
            f.write(dir)
        f.close()

    def PS_cancel(self):
        # restore to previous value
        for i in range(self.numParamters):
            item = self.ParameterSettingPage.ParameetrTable.item(i, 0)
            item.setText(self.parameters[i])
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit

        self.ParameterSettingPage.change.show()
        self.ParameterSettingPage.cancel.hide()
        self.ParameterSettingPage.save.hide()


    # methods for age calculation page
    # ===============================================================================
    def toAC(self):

        measurement, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select measurement file (csv)" , self.data_folder, "(*.csv)")
        
        if len(measurement) > 0:
                J = float(self.parameters[self.parameters_name.index('J value')])
                J_std = float(self.parameters[self.parameters_name.index('J std')])
                J_int = float(self.parameters[self.parameters_name.index('J int')])
                self.AgeCalculation_result = Utilities.calcAge(measurement, J, J_std,J_int, [float(x) for x in self.parameters[:]])
            
                # fill the table
                for i in range(55):
                    item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.AgeCalculation_result[i]))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.AgeCalculationPage.tableWidget.setItem(i//2 if i < 48 else i-24, i%2 if i < 48 else 0, item)

                self.AgeCalculationPage.age.setAlignment(QtCore.Qt.AlignLeft)
                self.AgeCalculationPage.age.setText('Age = {:.5} Ma +- {:.5}'.format(self.AgeCalculation_result[46]/10**6,self.AgeCalculation_result[47]/10**6))
                self.AgeCalculationPage.age.setFont(QtGui.QFont('Times', 20))

                # show the page
                self.TableAdjust(self.AgeCalculationPage.tableWidget)
                self.widget.setCurrentIndex(6)
           
    def AC_save(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Age Calculation result" , self.data_folder+'Agecalc/', "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("Samp#,t,Min,iradiation PK 90%,Variable,Value,Sigma\n")
            for i in range(self.AgeCalculationPage.tableWidget.rowCount()):
                f.write('{},{},{},{},{},{},{},\n'.format(self.AgeCalculation_result[55],self.AgeCalculation_result[56],self.AgeCalculation_result[57],self.AgeCalculation_result[58],self.AgeCalculationPage.tableWidget.verticalHeaderItem(i).text(),
                self.AgeCalculation_result[2*i] if i < 24 else self.AgeCalculation_result[i + 24],
                self.AgeCalculation_result[2*i+1] if i < 24 else 'N/A'))    
            f.close()



    # methods for J
    # ===============================================================================
    def toJS(self):             
        self.widget.setCurrentIndex(9)
    
    def toJV_FSC(self):
        index = 0
        self.jt = 'FSC/'
        self.measurement, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select measurement file (csv)" , self.data_folder+'/MassRatio/Standerd/FSC/', "(*.csv)")
        
        if len(self.measurement) > 0:
            try:
                # set the cell of the table of the T0 statistics
                self.J_Calculation_result = Utilities.getJVolumeStatistics(self.measurement, self.J_list[index],self.J_Sigma[index],[float(x) for x in self.parameters[:]])
                
                for i in range(5):
                    item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_Calculation_result[i]))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.JCalculationPage.RatioTable.setItem(0, i, item)
                    item2 = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_Calculation_result[i+5]))
                    item2.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.JCalculationPage.RatioTable2.setItem(0, i, item2)


                # show the page
                self.TableAdjust(self.JCalculationPage.RatioTable)
                self.widget.setCurrentIndex(4)
            except:
                self.Popup(2, "Error!", "Please check the selected data format!")
                
    def toJV_LP6(self):
        index = 1
        self.jt = 'LP6/'
        self.measurement, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select measurement file (csv)" , self.data_folder+'/MassRatio/Standerd/LP6/', "(*.csv)")
        
        if len(self.measurement) > 0:
            try:
                # set the cell of the table of the T0 statistics
                self.J_Calculation_result = Utilities.getJVolumeStatistics(self.measurement, self.J_list[index],self.J_Sigma[index],[float(x) for x in self.parameters[:]])
                
                for i in range(5):
                    item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_Calculation_result[i]))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.JCalculationPage.RatioTable.setItem(0, i, item)
                    item2 = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_Calculation_result[i+5]))
                    item2.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.JCalculationPage.RatioTable2.setItem(0, i, item2)

                # show the page
                self.TableAdjust(self.JCalculationPage.RatioTable)
                self.widget.setCurrentIndex(4)
            except:
                self.Popup(2, "Error!", "Please check the selected data format!")
    
    def toJV_MMHB(self):
        index = 2
        self.jt = 'MMHB/'
        self.measurement, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select measurement file (csv)" , self.data_folder+'/MassRatio/Standerd/MMHB/', "(*.csv)")
        
        if len(self.measurement) > 0:
            try:
                # set the cell of the table of the T0 statistics
                self.J_Calculation_result = Utilities.getJVolumeStatistics(self.measurement, self.J_list[index],self.J_Sigma[index],[float(x) for x in self.parameters[:]])
                
                for i in range(5):
                    item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_Calculation_result[i]))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.JCalculationPage.RatioTable.setItem(0, i, item)
                    item2 = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_Calculation_result[i+5]))
                    item2.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.JCalculationPage.RatioTable2.setItem(0, i, item2)


                # show the page
                self.TableAdjust(self.JCalculationPage.RatioTable)
                self.TableAdjust(self.JCalculationPage.RatioTable2)
                self.widget.setCurrentIndex(4)
            except:
                self.Popup(2, "Error!", "Please check the selected data format!")
    
    def JV_save(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save J value Calculation result" , self.data_folder+'/J value/'+self.jt, "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("file name,36Ar(a)[V],37Ar(ca)[V],39Ar(k)[V],40Ar(r)[V],40Ar(r)(%),39Ar(k)(%),K/Ca,K/Ca Sigma,J value,J Sigma,J Sigma int\n")
            f.write("{},{},{},{},{},{},{},{},{},{},{},{}\n".format(self.measurement,self.J_Calculation_result[0], self.J_Calculation_result[1],self.J_Calculation_result[2],self.J_Calculation_result[3],self.J_Calculation_result[4],self.J_Calculation_result[5],self.J_Calculation_result[6],self.J_Calculation_result[7],self.J_Calculation_result[8],self.J_Calculation_result[9],self.J_Calculation_result[10]))
            f.close()

    # methods for Mass Ratio
    # ===============================================================================
    def toMR(self):
        # select mass and preline
        mass, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select mass file (csv)" , self.data_folder, "(*.csv)")
        bg, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select preline file (csv)" , self.data_folder, "(*.csv)")

        if len(mass) > 0 and len(bg) > 0:
            try:
                self.ratio_result = Utilities.calculateMassRatio(mass, bg, self.parameters[self.parameters_name.index('OG Date')])

                for i in range(5):
                    for j in range(5):
                        item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.ratio_result[i][j]))
                       
                        item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                        if i < 3:
                            self.MassRatioPage.ValueTable.setItem(j, i, item)
                        else:
                            self.MassRatioPage.RatioTable.setItem(j, i-3, item)

                self.TableAdjust(self.MassRatioPage.ValueTable)
                self.TableAdjust(self.MassRatioPage.RatioTable)
                self.widget.setCurrentIndex(3)
            except:
                self.Popup(2, "Error!", "Please check the selected data format!")
        else:
            self.Popup(2, "Wrong Usage!", "Please select exactly one mass file first and then eactly one preline file")

    def MR_save(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Measurement T0 result" , self.data_folder+'/MassRatio/', "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("Samp#,t,Min,iradiation PK 90%,Mass,Raw,Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma\n")
            f.writelines(["{},{},{},{},Ar{},{},{},{},{},{},{}\n".format(self.ratio_result[5],self.ratio_result[6],self.ratio_result[7],self.ratio_result[8],i+36, self.ratio_result[0][i], self.ratio_result[1][i], self.ratio_result[2][i],self.mass_pair[i], self.ratio_result[3][i], self.ratio_result[4][i]) for i in range(5)])
            f.close()
    
    # methods for Salt Calculation
    # ===============================================================================
    def toSC(self):
        if self.salt == 'Ca':
            salt, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select Salt file (csv)" , self.data_folder+'MassRatio/Salt/CaF/', "(*.csv)")
            if len(salt) > 0:
                
                    self.salt_result,self.info = Utilities.calculateSlatCa(salt)

                    for i in range(2):
                        for j in range(2):
                            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.salt_result[i][j]))
                            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                            self.SaltCalculationPage.RatioTableCa.setItem(i, j, item)
                            
                    self.TableAdjust(self.SaltCalculationPage.RatioTableCa)
                    self.widget.setCurrentIndex(8)
                
        if self.salt == 'K':
            salt, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select Salt file (csv)" , self.data_folder+'MassRatio/Salt/Ksalt/', "(*.csv)")
            if len(salt) > 0:
                    self.salt_result,self.info = Utilities.calculateSlatK(salt)

                    for i in range(3):
                        for j in range(2):
                            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.salt_result[i][j]))
                            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                            self.SaltCalculationPage.RatioTableK.setItem(i, j, item)
                            
                    self.TableAdjust(self.SaltCalculationPage.RatioTableK)
                    self.widget.setCurrentIndex(8)
                
        
        
    def SC_save(self):
        if self.salt == 'Ca':
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Measurement T0 result" , self.data_folder+'SaltRatio/CaF/', "(*.csv)")
            if len(filename) > 0:
                f = open(filename, 'w')
                f.write("Samp#,,Ratio,Sigma\n")
                f.writelines(["{},[36Ar/37Ar]Ca,{},{}\n".format(self.info,self.salt_result[0][0], self.salt_result[1][0])])
                f.writelines(["{},[39Ar/37Ar]Ca,{},{}\n".format(self.info,self.salt_result[0][1], self.salt_result[1][1])])
                f.close()
        if self.salt == 'K':
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Measurement T0 result" , self.data_folder+'SaltRatio/Ksalt/', "(*.csv)")
            if len(filename) > 0:
                f = open(filename, 'w')
                f.write("Samp#,,Ratio,Sigma\n")
                f.writelines(["{},[40Ar/39Ar]K,{},{}\n".format(self.info,self.salt_result[0,0], self.salt_result[0,1])])
                f.writelines(["{},[38Ar/39Ar]K,{},{}\n".format(self.info,self.salt_result[1,0], self.salt_result[1,1])])
                f.writelines(["{},[39Ar/37Ar]K,{},{}\n".format(self.info,self.salt_result[2,0], self.salt_result[2,1])])
                f.close()
        
    def toSCa(self):
        self.salt = "Ca"
        self.SaltCalculationPage.RatioTableK.setVisible(False)
        self.SaltCalculationPage.RatioTableCa.setVisible(True)
        self.toSC()


    def toSK(self):
        self.salt = "K"
        self.SaltCalculationPage.RatioTableCa.setVisible(False)
        self.SaltCalculationPage.RatioTableK.setVisible(True)
        self.toSC()

    def toSCS(self):
       self.widget.setCurrentIndex(12)

    # methods for Statistics
    # ===============================================================================
    def toSS(self):             
        self.widget.setCurrentIndex(10)
    
    def T0_setReselectTable(self):
        w = self.ReselectDialog.frameGeometry().width()
        h = self.ReselectDialog.frameGeometry().height()
        self.ReselectDialog.ReselectTable = QtWidgets.QTableWidget(self.ReselectDialog)
        self.ReselectDialog.ReselectTable.setGeometry(QtCore.QRect(int(0.1*w), int(0.2*h), int(0.8*w), int(0.5*h)))
        self.ReselectDialog.ReselectTable.setObjectName("ReselectTable")
        self.ReselectDialog.ReselectTable.setColumnCount(len(self.T0filename))
        self.ReselectDialog.ReselectTable.setRowCount(1)
        self.ReselectDialog.ReselectTable.setVerticalHeaderLabels(['T0'])
        self.ReselectDialog.ReselectTable.setHorizontalHeaderLabels(['{}'.format(i) for i in range(1, self.numCycle+1)])
        
        header = self.ReselectDialog.ReselectTable.horizontalHeader()
        for i in range(self.ReselectDialog.ReselectTable.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        header = self.ReselectDialog.ReselectTable.verticalHeader()
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                item = QtWidgets.QTableWidgetItem()
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked)
                self.ReselectDialog.ReselectTable.setItem(i, j, item)

    def T0_reselect(self):
        self.ReselectDialog.show()
        self.ReselectDialog.buttonBox.accepted.connect(self.T0_checkReselectTable)
    
    def T0_checkReselectTable(self):
        for j in range(self.ReselectDialog.ReselectTable.columnCount()):
            item = self.ReselectDialog.ReselectTable.item(0,j)
            if item.checkState() == QtCore.Qt.Unchecked:
                self.mask[j] = 0
            else:
                self.mask[j] = 1
        
        self.T0_statistics_result,re_n = Utilities.REgetT0Statistics(self.T0filename,self.mask)
        for i in range(5):
                    for j in range(2):
                        item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.T0_statistics_result[i, j]))
                        item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                        self.T0StatisticsPage.tableWidget.setItem(j+2, i, item)

                # set # of selected files
        self.T0StatisticsPage.numSelectedFiles.setText("n={} RE n={}".format(len(self.T0filename),re_n))
        self.T0StatisticsPage.numSelectedFiles.setFont(QtGui.QFont('Times', 12))

        # set image
        self.T0StatisticsPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/T0S.png"))
               
        # show the page
        self.TableAdjust(self.T0StatisticsPage.tableWidget)

      
    
    def J_setReselectTable(self):
        w = self.ReselectDialog.frameGeometry().width()
        h = self.ReselectDialog.frameGeometry().height()
        self.ReselectDialog.ReselectTable = QtWidgets.QTableWidget(self.ReselectDialog)
        self.ReselectDialog.ReselectTable.setGeometry(QtCore.QRect(int(0.1*w), int(0.2*h), int(0.8*w), int(0.5*h)))
        self.ReselectDialog.ReselectTable.setObjectName("ReselectTable")
        self.ReselectDialog.ReselectTable.setColumnCount(len(self.Jfilename))
        self.ReselectDialog.ReselectTable.setRowCount(1)
        self.ReselectDialog.ReselectTable.setVerticalHeaderLabels(['J'])
        self.ReselectDialog.ReselectTable.setHorizontalHeaderLabels(['{}'.format(i) for i in range(1, self.numCycle+1)])
        
        header = self.ReselectDialog.ReselectTable.horizontalHeader()
        for i in range(self.ReselectDialog.ReselectTable.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        header = self.ReselectDialog.ReselectTable.verticalHeader()
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                item = QtWidgets.QTableWidgetItem()
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked)
                self.ReselectDialog.ReselectTable.setItem(i, j, item)

    def J_reselect(self):
        self.ReselectDialog.show()
        self.ReselectDialog.buttonBox.accepted.connect(self.J_checkReselectTable)
        
    def J_checkReselectTable(self):
        for j in range(self.ReselectDialog.ReselectTable.columnCount()):
            item = self.ReselectDialog.ReselectTable.item(0,j)
            if item.checkState() == QtCore.Qt.Unchecked:
                self.mask[j] = 0
            else:
                self.mask[j] = 1
            
        # set the cell of the table of the J statistics
        self.J_statistics_result = Utilities.REgetJStatistics(self.Jfilename,self.mask)
        for i in range(4):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_statistics_result[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.JStatisticsPage.tableWidget.setItem(0, i, item)
            
        # set image
        self.JStatisticsPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/J.png"))
            
        # show the page
        self.TableAdjust(self.JStatisticsPage.tableWidget)
        
    def toT0S(self):

        self.T0filename, _ = QtWidgets.QFileDialog.getOpenFileNames(self.widget, "Select files (csv) to get T0 statistics" , self.data_folder+'T0/', "(*.csv)") # select list of files

        if len(self.T0filename) > 0:
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])
            self.T0_setReselectTable()  # setup the reselect table here
            self.mask = np.ones(len(self.T0filename))
                   
                # set the cell of the table of the T0 statistics
            self.T0_statistics_result,self.mask,og_result,re_n = Utilities.getT0Statistics(self.T0filename,self.mask)
                
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                if self.mask[j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(0,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
                
                for i in range(5):
                    for j in range(2):
                        item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(og_result[i, j]))
                        item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                        self.T0StatisticsPage.tableWidget.setItem(j, i, item)
                    for j in range(2):
                        item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.T0_statistics_result[i, j]))
                        item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                        self.T0StatisticsPage.tableWidget.setItem(j+2, i, item)

                # set # of selected files
                self.T0StatisticsPage.numSelectedFiles.setText("n={} RE n={}".format(len(self.T0filename),re_n))
                self.T0StatisticsPage.numSelectedFiles.setFont(QtGui.QFont('Times', 12))

                # set image
                self.T0StatisticsPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/T0S.png"))

                # show the page
                self.TableAdjust(self.T0StatisticsPage.tableWidget)
                self.widget.setCurrentIndex(2)
            

    def toJSS(self):

        self.Jfilename, _ = QtWidgets.QFileDialog.getOpenFileNames(self.widget, "Select files (csv) to get J statistics" , self.data_folder+'J value/', "(*.csv)") # select list of files

        if len(self.Jfilename) > 0:
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])
            self.J_setReselectTable()  # setup the reselect table here
            self.mask = np.ones(len(self.Jfilename))
            
            # set the cell of the table of the J statistics
            self.J_statistics_result,self.madk = Utilities.getJStatistics(self.Jfilename,self.mask)
            
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                if self.mask[j] == 0:
                    item = self.ReselectDialog.ReselectTable.item(0,j)
                    item.setCheckState(QtCore.Qt.Unchecked)
            
            for i in range(4):
                item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.J_statistics_result[i]))
                item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                self.JStatisticsPage.tableWidget.setItem(0, i, item)
            
           

            # set image
            self.JStatisticsPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/J.png"))

            # show the page
            self.TableAdjust(self.JStatisticsPage.tableWidget)
            self.widget.setCurrentIndex(11)
            

    def T0S_save(self):
        
        # save statistics
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save T0 Statistics result" , self.data_folder+'Statistics/T0/', "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("Mass,Mean,STD\n")
            f.writelines(["Ar{},{},{}\n".format(i+36, self.T0_statistics_result[i,0], self.T0_statistics_result[i,1]) for i in range(5)])
            f.close()

    def JSS_save(self):
        # save statistics
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save J Statistics result" , self.data_folder+'Statistics/J/', "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("Avg,STD,Wmean,Wmean STD\n")
            f.writelines(["{},{},{},{}\n".format(self.J_statistics_result[0], self.J_statistics_result[1], self.J_statistics_result[2], self.J_statistics_result[3])])
            f.close()
    
    # methods for Air Ratio Statistics
    # ===============================================================================
    def toARS(self):

        filelist, _ = QtWidgets.QFileDialog.getOpenFileNames(self.widget, "Select files (csv) to get Air Ratio statistics" , self.data_folder+'MassRatio/AirRatio/', "(*.csv)") # select list of files

        if len(filelist) > 0:
            try:
                # set the cell of the table of the T0 statistics
                self.AirRatio_statistics_result,n = Utilities.getAirRatioStatistics(filelist)
                for i in range(2):
                    for j in range(2):
                        item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.AirRatio_statistics_result[i, j]))
                        item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                        self.AirRatioStatisticsPage.RatioTable.setItem(j, i, item)

                # set # of selected files
                self.AirRatioStatisticsPage.numSelectedFiles.setText("n = {}".format(n))
                self.AirRatioStatisticsPage.numSelectedFiles.setFont(QtGui.QFont('Times', 20))

                # set image
                self.AirRatioStatisticsPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/ARS.png"))

                # show the page
                self.TableAdjust(self.AirRatioStatisticsPage.RatioTable)
                self.widget.setCurrentIndex(13)
            except:
                self.Popup(2, "Error!", "Please check the selected data format!")

    def ARS_save(self):
        # save statistics
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Air Ratio Statistics result" , self.data_folder+'Statistics/AS/', "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("Air Ratio,Mean,STD\n")
            f.write("Ar 40/36,{},{}\n".format(self.AirRatio_statistics_result[0, 0], self.AirRatio_statistics_result[0, 1]))
            f.write("Ar 38/36,{},{}\n".format(self.AirRatio_statistics_result[1, 0], self.AirRatio_statistics_result[1, 1]))
            f.close()

    # methods for Salt Statistics
    # ===============================================================================
    def toSSS(self):
        
        self.widget.setCurrentIndex(18)
    
    def toS36Ca(self):
        
        self.salt=36
        self.toSSC()
    
    def toS39Ca(self):
        
        self.salt=39
        self.toSSC()
    
    def toS40K(self):
        
        self.salt=40
        self.toSSC()
        
    def toS38K(self):
        
        self.salt=38
        self.toSSC()
        
    def toS39K(self):
         
        self.salt=37
        self.toSSC()
        
    def toSSC(self):

        self.Saltfilename, _ = QtWidgets.QFileDialog.getOpenFileNames(self.widget, "Select files (csv) to get Salt statistics" , self.data_folder+'SaltRatio/', "(*.csv)") # select list of files

        if len(self.Saltfilename) > 0:
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])
            self.Salt_setReselectTable()  # setup the reselect table here
            self.mask = np.ones(len(self.Saltfilename))
                   
            # set the cell of the table of the J statistics
            self.Salt_statistics_result,self.madk = Utilities.getSaltStatistics(self.Saltfilename,self.mask,self.salt)
           
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                if self.mask[j] == 0:
                    item = self.ReselectDialog.ReselectTable.item(0,j)
                    item.setCheckState(QtCore.Qt.Unchecked)
            
            for i in range(4):
                item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.Salt_statistics_result[i]))
                item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                self.SaltStatPage.tableWidget.setItem(0, i, item)
            
           

            # set image
            self.SaltStatPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/Salt.png"))

            # show the page
            self.TableAdjust(self.SaltStatPage.tableWidget)
            self.widget.setCurrentIndex(17)
                
    def Salt_setReselectTable(self):
        w = self.ReselectDialog.frameGeometry().width()
        h = self.ReselectDialog.frameGeometry().height()
        self.ReselectDialog.ReselectTable = QtWidgets.QTableWidget(self.ReselectDialog)
        self.ReselectDialog.ReselectTable.setGeometry(QtCore.QRect(int(0.1*w), int(0.2*h), int(0.8*w), int(0.5*h)))
        self.ReselectDialog.ReselectTable.setObjectName("ReselectTable")
        self.ReselectDialog.ReselectTable.setColumnCount(len(self.Saltfilename))
        self.ReselectDialog.ReselectTable.setRowCount(1)
        self.ReselectDialog.ReselectTable.setVerticalHeaderLabels(['Salt'])
        self.ReselectDialog.ReselectTable.setHorizontalHeaderLabels(['{}'.format(i) for i in range(1, self.numCycle+1)])
        
        header = self.ReselectDialog.ReselectTable.horizontalHeader()
        for i in range(self.ReselectDialog.ReselectTable.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        header = self.ReselectDialog.ReselectTable.verticalHeader()
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                item = QtWidgets.QTableWidgetItem()
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked)
                self.ReselectDialog.ReselectTable.setItem(i, j, item)

    def Salt_reselect(self):
        self.ReselectDialog.show()
        self.ReselectDialog.buttonBox.accepted.connect(self.Salt_checkReselectTable)
        
    def Salt_checkReselectTable(self):
        for j in range(self.ReselectDialog.ReselectTable.columnCount()):
            item = self.ReselectDialog.ReselectTable.item(0,j)
            if item.checkState() == QtCore.Qt.Unchecked:
                self.mask[j] = 0
            else:
                self.mask[j] = 1
            
        # set the cell of the table of the Salt statistics
        self.Salt_statistics_result = Utilities.REgetSaltStatistics(self.Saltfilename,self.mask,self.salt)
        for i in range(4):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.Salt_statistics_result[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.SaltStatPage.tableWidget.setItem(0, i, item)
            
        # set image
        self.SaltStatPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/Salt.png"))
            
        # show the page
        self.TableAdjust(self.SaltStatPage.tableWidget)    
        
    def SSC_save(self):
        # save statistics
        if(self.salt == 36):
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Salt Statistics result" , self.data_folder+'Statistics/Salt/[36Ar37Ar]Ca/', "(*.csv)")
        elif(self.salt == 39):    
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Salt Statistics result" , self.data_folder+'Statistics/Salt/[39Ar37Ar]Ca/', "(*.csv)")
        elif(self.salt == 40):    
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Salt Statistics result" , self.data_folder+'Statistics/Salt/[40Ar39Ar]K/', "(*.csv)")
        elif(self.salt == 38):    
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Salt Statistics result" , self.data_folder+'Statistics/Salt/[38Ar39Ar]K/', "(*.csv)")
        elif(self.salt == 37):    
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save Salt Statistics result" , self.data_folder+'Statistics/Salt/[39Ar37Ar]K/', "(*.csv)")
        if len(filename) > 0:
            f = open(filename, 'w')
            f.write("Avg,STD,Wmean,Wmean STD\n")
            f.writelines(["{},{},{},{}\n".format(self.Salt_statistics_result[0], self.Salt_statistics_result[1], self.Salt_statistics_result[2], self.Salt_statistics_result[3])])
            f.close()

    # methods for T0 Calculation Page
    # ===============================================================================
    def toTS(self):             
        self.widget.setCurrentIndex(7)

    def toLRP_MB(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                            self.rawpath+"/MB/", "")  # select file
        self.rawfilename = filename.replace(self.rawpath+"/MB/", '')
        if len(filename) > 0:
            self.T0type = 'MB'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return

            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)

    def toLRP_PBa(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                            self.rawpath+"/PBa/", "")  # select file
        self.rawfilename = filename.replace(self.rawpath+'/PBa/', '')

        if len(filename) > 0:
            self.T0type = 'PBa'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return

            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)

    def toLRP_AS(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                            self.rawpath+"/AS/", "")  # select file
        self.rawfilename = filename.replace(self.rawpath+'/AS/', '')

        if len(filename) > 0:
            self.T0type = 'AS'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return

            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)

    def toLRP_PBs(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                            self.rawpath+"/PBs/", "")  # select file
        self.rawfilename = filename.replace(self.rawpath+'/PBs/', '')

        if len(filename) > 0:
            self.T0type = 'PBs'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return

            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)

    def toLRP_SP(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                           self.rawpath+"/Sample/", "")  # select file

        if len(filename) > 0:
            self.T0type = 'Sample'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return
                     
            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)

    def toLRP_TP(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                            self.rawpath+"/Standerd/", "")  # select file

        if len(filename) > 0:
            self.T0type = 'Standerd'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return

            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)
            
    def toLRP_ST(self):

        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select file to calculate T0",
                                                            self.rawpath+"/Salt/", "")  # select file

        if len(filename) > 0:
            self.T0type = 'Salt'
            self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])

            self.LRP_setReselectTable()  # setup the reselect table here

            # collect the raw data
            if not self.LRP_loadRawData(filename):
                return

            self.T0_fitting_function = 0  # default fitting function is linear
            self.mask = np.ones((5, self.numCycle))  # 1 means select this data point

            result,self.mask = Utilities.calculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)  # make LRP
            for i in range(5):
                for j in range(self.numCycle):
                    if self.mask[i,j] == 0:
                        item = self.ReselectDialog.ReselectTable.item(i,j)
                        item.setCheckState(QtCore.Qt.Unchecked)
            [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:]
            self.T0CalculationPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/LR.png"))  # set image in the page
            self.T0CalculationPage.current_fit_func.setText(
                "Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

            # show the page
            self.widget.setCurrentIndex(1)
            
    def LRP_loadRawData(self, filename):
        try:
            with open(filename, 'r') as f:
                data = f.readlines()

            # find the starting line of meaningful data
            for i in reversed(range(len(data))):
                stl = i
                if len(data[i].split()) == 4:
                    break
            stl -= (6*self.numCycle-2)

            # extract the data
            self.info = [0,0,0,0,0]
            if (data[2].rstrip()) == "":
                self.info[0] = ((data[17].split())[2])+" "+((data[4].split())[3])
                self.info[1] = ((data[18].split())[2])
                self.info[2] = ((data[0].split())[1])
                self.info[3] = ((data[21].split())[2])
                self.info[4] = ((data[23].split())[2])
            else:
                self.info[0] = ((data[15].split())[2])
                self.info[1] = ((data[16].split())[2])
                self.info[2] = ((data[0].split())[1])
                self.info[3] = ((data[19].split())[2])
                self.info[4] = ((data[21].split())[2])
            self.v_t = np.zeros((5, self.numCycle, 2))
            for i in range(self.numCycle):
                for j in range(5):
                    self.v_t[j, i, 0] = float((data[stl + 6*i + j].split())[2])
                    self.v_t[j, i, 1] = float((data[stl + 6*i + j].split())[3])
            return 1

        except:
            self.Popup(2, "Error!", "Please check the selected data format or the parameter numCycle!")
            return 0


    def LRP_save(self):
        pn = self.work_dir+self.screenshot_folder+'T0/'+self.T0type+'/'
        sn = self.data_folder+'T0/'+self.T0type+'/'
        # save screenshot
        if self.T0type == 'MB' or self.T0type == 'PBa' or self.T0type == 'AS' or self.T0type == 'PBs':
            shutil.copyfile(self.work_dir + '.work/LR.png', pn+self.rawfilename+'.png')
            f = open(sn+self.rawfilename+'.csv', 'w')
            f.write("Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2\n")
            f.writelines(["{},{},{},{},{},Ar{},{},{},{}\n".format(self.info[0],self.info[1],self.info[2],self.info[3],self.info[4],i+36, self.tmp_T0[i], self.tmp_T0_SIGMA[i], self.R[i]) for i in range(5)])
            f.close()
            self.toast.show()
        else:    
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save T0 Calculation result" , pn, "Images (*.png *.jpg *.jpeg)")
            if len(filename) > 0:
                shutil.copyfile(self.work_dir + '.work/LR.png', filename)

            # save T0
            filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save T0 Calculation result" , sn, "(*.csv)")
            if len(filename) > 0:
                f = open(filename, 'w')
                f.write("Samp#,Min,T,Date,iradiation PK 90%,Mass,T0,T0_SIGMA,R^2\n")
                f.writelines(["{},{},{},{},{},Ar{},{},{},{}\n".format(self.info[0],self.info[1],self.info[2],self.info[3],self.info[4],i+36, self.tmp_T0[i], self.tmp_T0_SIGMA[i], self.R[i]) for i in range(5)])
                f.close()
                
    def LRP_setReselectTable(self):
        w = self.ReselectDialog.frameGeometry().width()
        h = self.ReselectDialog.frameGeometry().height()
        self.ReselectDialog.ReselectTable = QtWidgets.QTableWidget(self.ReselectDialog)
        self.ReselectDialog.ReselectTable.setGeometry(QtCore.QRect(int(0.1*w), int(0.2*h), int(0.8*w), int(0.5*h)))
        self.ReselectDialog.ReselectTable.setObjectName("ReselectTable")
        self.ReselectDialog.ReselectTable.setColumnCount(self.numCycle)
        self.ReselectDialog.ReselectTable.setRowCount(5)
        self.ReselectDialog.ReselectTable.setVerticalHeaderLabels(['Ar {}'.format(i) for i in range(36, 41)])
        self.ReselectDialog.ReselectTable.setHorizontalHeaderLabels(['{}'.format(i) for i in range(1, self.numCycle+1)])
        
        header = self.ReselectDialog.ReselectTable.horizontalHeader()
        for i in range(self.ReselectDialog.ReselectTable.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        header = self.ReselectDialog.ReselectTable.verticalHeader()
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                item = QtWidgets.QTableWidgetItem()
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked)
                self.ReselectDialog.ReselectTable.setItem(i, j, item)

    def LRP_reselect(self):
        self.ReselectDialog.show()
        self.ReselectDialog.buttonBox.accepted.connect(self.LRP_checkReselectTable)

    def LRP_checkReselectTable(self):
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                item = self.ReselectDialog.ReselectTable.item(i, j)
                if item.checkState() == QtCore.Qt.Unchecked:
                    self.mask[i, j] = 0
                else:
                    self.mask[i, j] = 1

        result = Utilities.REcalculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle)
        [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:4]
        self.T0CalculationPage.photo.setPixmap(QtGui.QPixmap(".work/LR.png")) # set image in the page
        self.ReselectDialog.close()

        if result[0] == 1:
            self.Popup(2, "Fitting Error!", "Unable to fit the manually selected data with {} fucntion!".format(self.fitting_function_list[self.T0_fitting_function]))

    def LRP_useLinear(self):
        self.LRP_switch_fitting_func(0)
    
    def LRP_useAverage(self):
        self.LRP_switch_fitting_func(1)

    def LRP_switch_fitting_func(self, fit_func_type):
        
        self.T0_fitting_function = fit_func_type
        result = Utilities.REcalculateT0(self.T0_fitting_function, self.v_t, self.mask,self.numCycle) # make LRP
        [self.tmp_T0, self.tmp_T0_SIGMA, self.R] = result[1:4]
        self.T0CalculationPage.photo.setPixmap(QtGui.QPixmap(".work/LR.png")) # set image in the page
        self.T0CalculationPage.current_fit_func.setText("Current fitting function: {}".format(self.fitting_function_list[self.T0_fitting_function]))

        if result[0] == 1:
            self.Popup(2, "Fitting Error!", "Unable to fit the data with {} fucntion after manually removing the outliers!".format(self.fitting_function_list[self.T0_fitting_function]))
    
    # methods for Diagram Plots Page
    # ===============================================================================
    def toDS(self):             
        self.widget.setCurrentIndex(14)
    
    def toDF_LS(self):
        self.Dfilename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select Datum file (csv)" , self.data_folder+"Publish/", "(*.csv)")
        if len(self.Dfilename) > 0:
            
                self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])
                with open(self.Dfilename, 'r') as f:
                    self.data = f.readlines()
                # Normalize V2.0 (88-col K/Ca) to V3.7 (98-col Ca/K) in memory
                self.data = Utilities.normalize_csv_to_v37(self.data)
                # Now the header should be V3.7 form; only check column count loosely
                _hdr_cols = self.data[0].rstrip().split(',') if self.data else []
                if len(_hdr_cols) not in (88, 98):
                    raise Exception(f"Wrong data format! Expected 88 or 98 cols, got {len(_hdr_cols)}")
                j = 0
                for i in range (len(self.data)-2):
                    if float(self.data[i+1-j].split(',')[46])/float(self.data[i+1-j].split(',')[7]) < 0 or float(self.data[i+1-j].split(',')[61])/float(self.data[i+1-j].split(',')[7]) < 0 :
                        self.data.pop(i-j)
                        j=j+1  
                    if self.data[i+1-j].split(',')[17] == "nan":
                        self.data.pop(i-j)
                        j=j+1    
                
                self.DF_setReselectTable()  # setup the reselect table here
                self.mask = np.ones(len(self.data)-2)
                self.DF_result = Utilities.getDFStatistics_ls(self.Dfilename, self.mask, self.parameters, 'r','o')
                Utilities.getDFStatistics_t(self.Dfilename, self.mask,self.power)
                
                for i in range(3):
                    item = QtWidgets.QTableWidgetItem('{}'.format(self.data[1].split(',')[i]))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.DiagramPlots_LSPage.tableWidget.setItem(0, i, item)  
                    
                for i in range(2):
                    item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(float(self.data[1].split(',')[4+i])))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.DiagramPlots_LSPage.tableWidget.setItem(0, i+3, item)    
                
                for i in range(8):
                    item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.DF_result[i]))
                    item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
                    self.DiagramPlots_LSPage.tableWidget.setItem(0, i+5, item)
                    
                self.DiagramPlots_LSPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/DFN.png"))  # set image in the page    
                self.pname = "DFN"
                self.TableAdjust(self.DiagramPlots_LSPage.tableWidget)
                
                self.widget.setCurrentIndex(16)
                f.close()
                
    def show_LS(self):
        self.DLSC = self.DiagramPlots_LSPage.box.currentText()
        self.DLSS = self.DiagramPlots_LSPage.box2.currentText()
        Utilities.getDFStatistics_ls(self.Dfilename, self.mask, self.parameters, self.DLSC, self.DLSS)
        if(self.pname == "DFN"):
            self.DiagramPlots_LSPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/DFN.png"))  # set image in the page    
            self.pname = "DFN"
            self.TableAdjust(self.DiagramPlots_LSPage.tableWidget)
        if(self.pname == "DFI"):
            self.DiagramPlots_LSPage.photo.setPixmap(
                    QtGui.QPixmap(self.work_dir + ".work/DFI.png"))  # set image in the page 
            self.pname = "DFI"
       
    def toDF_SH(self):
            import traceback
            
            try:
                print("\n" + "="*60)
                print("toDF_SH: Starting...")
                print("="*60)
                
                self.Dfilename, _ = QtWidgets.QFileDialog.getOpenFileName(self.widget, "Select Datum file (csv)" , self.data_folder+"Publish/", "(*.csv)")
                print(f"Selected file: {self.Dfilename}")
                
                if len(self.Dfilename) > 0:
                    print("File selected, proceeding...")
                    
                    self.numCycle = int(self.parameters[self.parameters_name.index("numCycle")])
                    print(f"numCycle: {self.numCycle}")
                    
                    with open(self.Dfilename, 'r', encoding='utf-8') as f:
                        self.data = f.readlines()
                    # Normalize V2.0 (88-col K/Ca) to V3.7 (98-col Ca/K) in memory
                    self.data = Utilities.normalize_csv_to_v37(self.data)
                    print(f"File read: {len(self.data)} lines")
                    
                    # Header check - accept both 88 and 98 column formats
                    base_header = "Samp#,Min,IRR,deg C,J,J_std,J_int,36Ar(a),36Ar(a)_std,37Ar(ca),37Ar(ca)_std,38Ar(cl),38Ar(cl)_std,39Ar(k),39Ar(k)_std,40Ar(r),40Ar(r)_std,Age(Ma),Age_std(Ma),40Ar(r)(%),39Ar(k)(%),40Ar(r)(%)(step heating),39Ar(k)(%)(step heating),Ca/K,Ca/K_std,Degassing Patterns,36Ar(a),36Ar(a)_std,36Ar(c),36Ar(c)_std,36Ar(ca),36Ar(ca)_std,36Ar(cl),36Ar(cl)_std,37Ar(ca),37Ar(ca)_std,38Ar(a),38Ar(a)_std,38Ar(c),38Ar(c)_std,38Ar(k),38Ar(k)_std,38Ar(ca),38Ar(ca)_std,38Ar(cl),38Ar(cl)_std,39Ar(k),39Ar(k)_std,39Ar(ca),39Ar(ca)_std,40Ar(r),40Ar(r)_std,40Ar(a),40Ar(a)_std,40Ar(c),40Ar(c)_std,40Ar(k),40Ar(k)_std,Additional Parameters,40(r)/39(k),40(r)/39(k)_std,40(r+a),40(r+a)_std,40Ar/39Ar,40Ar/39Ar_std,37Ar/39Ar,37Ar/39Ar_std,36Ar/39Ar,36Ar/39Ar_std,Parameters,39Ar/37Ar(ca),39Ar/37Ar(ca)_std,36Ar/37Ar(ca),36Ar/37Ar(ca)_std,40Ar/39Ar(k),40Ar/39Ar(k)_std,38Ar/39Ar(k),38Ar/39Ar(k)_std,39Ar/37Ar(k),39Ar/37Ar(k)_std,36Ar/38Ar(cl),36Ar/38Ar(cl)_std,40Ar/36Ar(a),40Ar/36Ar(a)_std,38Ar/36Ar(a),38Ar/36Ar(a)_std,Lambda,numCycle"
                    extended_header = base_header + ",normal isochron,40Ar(m)/36Ar(m),40Ar(m)/36Ar(m)_std,39Ar(m)/36Ar(m),39Ar(m)/36Ar(m)_std,inverse isochron,36Ar(m)/40Ar(m),36Ar(m)/40Ar(m)_std,39Ar(m)/40Ar(m),39Ar(m)/40Ar(m)_std"
                    
                    actual_header = self.data[0].rstrip()
                    actual_col_count = len(actual_header.split(','))
                    
                    print(f"\nHeader check:")
                    print(f"Actual columns: {actual_col_count}")
                    
                    # Accept both 88-column (old) and 98-column (new) formats
                    if actual_header == base_header:
                        print(f"✓ OLD format (88 columns)")
                    elif actual_header == extended_header:
                        print(f"✓ NEW format (98 columns)")
                    elif actual_col_count == 88 or actual_col_count == 98:
                        print(f"⚠ Header text differs but column count OK ({actual_col_count})")
                        print(f"  Proceeding anyway...")
                    else:
                        print("\n*** HEADER MISMATCH ***")
                        print(f"Expected: 88 or 98 columns")
                        print(f"Actual: {actual_col_count} columns")
                        print(f"First 100 chars: {actual_header[:100]}")
                        
                        error_msg = f"Header mismatch!\n\n"
                        error_msg += f"Expected: 88 or 98 columns\n"
                        error_msg += f"Actual: {actual_col_count} columns\n"
                        
                        print(error_msg)
                        self.Popup(2, "Header Error", error_msg)
                        raise Exception("Wrong data format!")
                    
                    # Remove nan rows (reverse iterate to keep indices valid)
                    print("\nRemoving nan Age rows...")
                    i = 1
                    while i < len(self.data):
                        age_val = self.data[i].split(',')[17]
                        if age_val == "nan" or age_val.strip() == "":
                            print(f"  Removing row {i}: Age = '{age_val}'")
                            self.data.pop(i)
                        else:
                            i += 1

                    print(f"Remaining data rows: {len(self.data)-1}")

                    # Setup
                    print("\nSetting up reselect table...")
                    self.DF_setReselectTable()

                    self.mask = np.ones(len(self.data)-1)  # FIX: -1 not -2 (data[0] is header)
                    print(f"Mask size: {len(self.mask)}")
                    
                    # Call getDFStatistics_sh with default parameters
                    # v3.8.1 FIX: pass return_limits/return_points=True so iso_pts_DFN/DFI
                    # are populated on initial display — required for click-to-group.
                    # Previously these stayed empty until the user pressed Apply, so clicks
                    # on data points in DFN/DFI silently no-op'd.
                    print("\nCalling getDFStatistics_sh...")
                    _df_call = Utilities.getDFStatistics_sh(
                        self.Dfilename, self.mask, self.parameters, 'r', 'o',
                        show_temp=False, show_atm=True, atm_ratio=298.56,
                        style=self._get_plot_style(),
                        return_limits=True, return_points=True,
                        show_group_fits=self.DiagramPlots_SHPage.showGroupFitsCheckbox.isChecked(),
                        show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
)
                    if isinstance(_df_call, tuple) and len(_df_call) == 2:
                        self.DF_result, _df_limits = _df_call
                        self.iso_pts_DFN = _df_limits.get('DFN_pts', self.iso_pts_DFN)
                        self.iso_pts_DFI = _df_limits.get('DFI_pts', self.iso_pts_DFI)
                        for _pn in ('DFN', 'DFI'):
                            if _pn in _df_limits and _df_limits[_pn][0]:
                                self._actual_xlims[_pn] = _df_limits[_pn][0]
                                self._actual_ylims[_pn] = _df_limits[_pn][1]
                            if f'{_pn}_bbox' in _df_limits:
                                self._axes_bboxes[_pn] = _df_limits[f'{_pn}_bbox']
                    else:
                        self.DF_result = _df_call
                    print(f"getDFStatistics_sh result: {self.DF_result}")
                    
                    # Call getSHStatistics
                    print("\nCalling getSHStatistics...")
                    result = Utilities.getSHStatistics(self.Dfilename, self.mask, self.parameters,
                                           style=self._get_plot_style())
                    print(f"getSHStatistics result: {result}")
                    
                    # Extract statistics, step data, axes_bbox, actual limits
                    if isinstance(result, dict):
                        self.sh_result = result.get("statistics", [0, 0])
                        self.step_data.update(result.get("step_data", {}))
                        for _pn in ("DFW", "DFA", "DFC"):
                            if _pn in result.get("axes_bbox", {}):
                                self._axes_bboxes[_pn] = result["axes_bbox"][_pn]
                            if _pn in result.get("actual_xlim", {}):
                                self._actual_xlims[_pn] = result["actual_xlim"][_pn]
                            if _pn in result.get("actual_ylim", {}):
                                self._actual_ylims[_pn] = result["actual_ylim"][_pn]
                    else:
                        # Fallback for old format
                        self.sh_result = result
                    
                    # Fill table
                    print("\nFilling table...")

                    def _set_item(row, col, text, align_right=True):
                        item = QtWidgets.QTableWidgetItem(text)
                        item.setFlags(QtCore.Qt.ItemIsEnabled)
                        if align_right:
                            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
                        self.DiagramPlots_SHPage.tableWidget.setItem(row, col, item)

                    def _fmt_age(v):
                        # Age in Ma: keep 2–3 decimals (use 3)
                        try:
                            return f"{float(v):.3f}"
                        except Exception:
                            return str(v)

                    def _fmt_ratio(v):
                        # Ratios/intercepts: keep 4–6 decimals (use 6)
                        try:
                            return f"{float(v):.6f}"
                        except Exception:
                            return str(v)

                    def _fmt_generic(v):
                        # MSWD etc.
                        try:
                            return f"{float(v):.3f}"
                        except Exception:
                            return str(v)

                    # Sample / Min / IRR (text-like)
                    for i in range(3):
                        _set_item(0, i, f"{self.data[1].split(',')[i]}", align_right=False)

                    # J, J_std (ratio-like)
                    for i in range(2):
                        _set_item(0, i+3, _fmt_ratio(float(self.data[1].split(',')[4+i])))

                    # Weighted plateau age, Total fusion age (age-like)
                    for i in range(2):
                        _set_item(0, i+5, _fmt_age(self.sh_result[i]))

                    # DF results: [n, n_std, iv, iv_std, mswd, wma, int_age, int_age_std]
                    for i in range(8):
                        v = self.DF_result[i]
                        if i in (0, 1, 2, 3):          # intercepts
                            txt = _fmt_ratio(v)
                        elif i in (6, 7, 5):           # ages: int age, int age std, WMA
                            txt = _fmt_age(v)
                        else:                           # MSWD etc.
                            txt = _fmt_generic(v)
                        _set_item(0, i+7, txt)

                    print("Table filled OK")

                    # Pre-compute 3D plane fit in background (populates row 1)
                    print("\nPre-computing 3D plane fit...")
                    try:
                        import pandas as pd, matplotlib
                        matplotlib.use('Agg')
                        import matplotlib.pyplot as plt

                        # V3.4.1 optimization: load only needed columns (84% I/O reduction)
                        df3 = pd.read_csv(self.Dfilename, usecols=[
                            "Samp#", "Min", "Age(Ma)", "deg C", "J", "J_std",
                            "36Ar(a)", "36Ar(a)_std", "39Ar(k)", "39Ar(k)_std",
                            "40Ar(r)", "40Ar(r)_std", "40Ar(a)", "40Ar(a)_std"
                        ])
                        df3 = df3[df3['Age(Ma)'].notna()].reset_index(drop=True)
                        # Align mask to df3 row count (pad with 1 or truncate) - V3.5 BUG FIX
                        _m3 = np.asarray(self.mask, dtype=float).copy()
                        _n3 = len(df3)
                        if _m3.size < _n3:
                            _m3 = np.concatenate([_m3, np.ones(_n3 - _m3.size)])
                        elif _m3.size > _n3:
                            _m3 = _m3[:_n3]
                        m3 = _m3.astype(bool)
                        # V3.4.1 early skip: avoid expensive 3D fit if too few points
                        if m3.sum() < 3:
                            print("  -> 3D fit skipped: too few masked points")
                            raise ValueError("Skipped: insufficient masked points (need >= 3)")
                        x36 = df3["36Ar(a)"].values[m3]
                        s36 = df3["36Ar(a)_std"].values[m3]
                        x39 = df3["39Ar(k)"].values[m3]
                        s39 = df3["39Ar(k)_std"].values[m3]
                        x40 = (df3["40Ar(r)"] + df3["40Ar(a)"]).values[m3]
                        # v3.8.6 fix (FORMULAS.md §11.10):
                        # 40Ar(r) and 40Ar(a) are anti-correlated through the
                        # 40Ar(r) = 40Ar(m) − 40Ar(a) − 40Ar(K) decomposition.
                        # cov(40r, 40a) = −σ²_40a, so var(40r + 40a) = σ²_40r − σ²_40a,
                        # NOT σ²_40r + σ²_40a (which double-counts σ_40a).
                        # Equivalent to var(40Ar(m) − 40Ar(K)) when independent assumption holds.
                        _v40r = df3["40Ar(r)_std"].values ** 2
                        _v40a = df3["40Ar(a)_std"].values ** 2
                        s40 = np.sqrt(np.maximum(_v40r - _v40a, 0.0))[m3]
                        J3  = float(df3["J"].iloc[0])
                        sJ3 = float(df3["J_std"].iloc[0])
                        T_labels3 = [f"{int(t)}°C" for t in df3["deg C"].values[m3]]

                        self.plane3d_result = PlaneFit3D.fit_plane(
                            x36, s36, x39, s39, x40, s40,
                            J=J3, s_J=sJ3, k0=0.025004
                        )
                        fig3 = PlaneFit3D.plot_result(
                            self.plane3d_result,
                            title=(f"{df3['Samp#'].iloc[0]} / {df3['Min'].iloc[0]}"
                                   f" — 3D Plane Fit"),
                            labels=T_labels3,
                            save_path=self.work_dir + ".work/DF3D.png"
                        )
                        plt.close(fig3)
                        print(f"3D pre-compute OK: α={self.plane3d_result['alpha']:.2f}, "
                              f"MSWD={self.plane3d_result['mswd']:.3f}, "
                              f"Age={self.plane3d_result['age_Ma']:.2f} Ma")
                    except Exception as e3:
                        print(f"3D pre-compute skipped: {e3}")

                    # Set image (DFN default)
                    print("\nSetting image...")
                    self.DiagramPlots_SHPage.photo.setPixmap(
                    QtGui.QPixmap(self.work_dir + ".work/DFN.png"))
                    self.pname = "DFN"
                    self.DiagramPlots_SHPage._mouse_move_callback = self.on_mouse_move_SH
                    # v3.8.1 FIX: wire click callback on initial display so click-to-group
                    # works in DFN/DFI without needing to press Apply first. Also push the
                    # DFN xlim/ylim so _pixel_to_data can translate clicks correctly.
                    self.DiagramPlots_SHPage._click_callback = self.on_click_SH
                    if 'DFN' in self._actual_xlims:
                        self.DiagramPlots_SHPage.current_xlim = self._actual_xlims['DFN']
                    if 'DFN' in self._actual_ylims:
                        self.DiagramPlots_SHPage.current_ylim = self._actual_ylims['DFN']
                    self.TableAdjust(self.DiagramPlots_SHPage.tableWidget)

                    self.widget.setCurrentIndex(15)
                    # BUG FIX: B8 - Remove f.close(), already closed by 'with' statement

                    print("\n" + "="*60)
                    print("toDF_SH: SUCCESS!")
                    print("="*60 + "\n")
                    
            except Exception as e:
                error_detail = f"{type(e).__name__}: {str(e)}"
                trace = traceback.format_exc()
                
                print("\n" + "="*60)
                print("*** EXCEPTION in toDF_SH ***")
                print("="*60)
                print(error_detail)
                print("\nFull traceback:")
                print(trace)
                print("="*60 + "\n")
                
                # Show detailed error in MessageBox
                self.Popup(2, "Error Details", f"{error_detail}\n\nSee console for full traceback")
                
                raise

    def show_SH(self):
            self.DHSC = self.DiagramPlots_SHPage.box.currentText()
            self.DHSS = self.DiagramPlots_SHPage.box2.currentText()

            xlim, ylim, legend = self._read_SH_controls()

            # Read isochron-specific controls
            show_temp = self.DiagramPlots_SHPage.showTempCheckbox.isChecked()
            show_atm = self.DiagramPlots_SHPage.showAtmCheckbox.isChecked()
            atm_ratio = self.DiagramPlots_SHPage.atmRatio.value()

            _iso_result = Utilities.getDFStatistics_sh(
                self.Dfilename, self.mask, self.parameters, self.DHSC, self.DHSS,
                xlim=xlim, ylim=ylim, legend_name=legend,
                show_temp=show_temp, show_atm=show_atm, atm_ratio=atm_ratio,
                style=self._get_plot_style(),
                return_limits=True, return_points=True,
                show_group_fits=self.DiagramPlots_SHPage.showGroupFitsCheckbox.isChecked(),
                show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
)
            if isinstance(_iso_result, tuple) and len(_iso_result) == 2:
                _iso_limits = _iso_result[1]
                self.iso_pts_DFN = _iso_limits.get('DFN_pts', self.iso_pts_DFN)
                self.iso_pts_DFI = _iso_limits.get('DFI_pts', self.iso_pts_DFI)
                if 'DFN' in _iso_limits and _iso_limits['DFN'][0]:
                    self._actual_xlims['DFN'] = _iso_limits['DFN'][0]
                    self._actual_ylims['DFN'] = _iso_limits['DFN'][1]
                if 'DFI' in _iso_limits and _iso_limits['DFI'][0]:
                    self._actual_xlims['DFI'] = _iso_limits['DFI'][0]
                    self._actual_ylims['DFI'] = _iso_limits['DFI'][1]
                if 'DFN_bbox' in _iso_limits:
                    self._axes_bboxes['DFN'] = _iso_limits['DFN_bbox']
                if 'DFI_bbox' in _iso_limits:
                    self._axes_bboxes['DFI'] = _iso_limits['DFI_bbox']
            _st = self._get_plot_style()
            result = Utilities.getSHStatistics(
                self.Dfilename, self.mask, self.parameters, style=_st,
                step_groups=self._effective_step_groups(), group_colors=self.GROUP_COLORS)
            # Store step_data, axes_bbox, actual limits for click/hover accuracy
            if isinstance(result, dict):
                self.step_data.update(result.get("step_data", {}))
                for _pn in ("DFW", "DFA", "DFC"):
                    if _pn in result.get("axes_bbox", {}):
                        self._axes_bboxes[_pn] = result["axes_bbox"][_pn]
                    if _pn in result.get("actual_xlim", {}):
                        self._actual_xlims[_pn] = result["actual_xlim"][_pn]
                    if _pn in result.get("actual_ylim", {}):
                        self._actual_ylims[_pn] = result["actual_ylim"][_pn]
            # Wire click and hover handlers
            self.DiagramPlots_SHPage._click_callback = self.on_click_SH
            self.DiagramPlots_SHPage._mouse_move_callback = self.on_mouse_move_SH
            # Apply limits for currently visible diagram
            _cur_pn = self.pname
            if _cur_pn in self._actual_xlims:
                self.DiagramPlots_SHPage.current_xlim = self._actual_xlims[_cur_pn]
            if _cur_pn in self._actual_ylims:
                self.DiagramPlots_SHPage.current_ylim = self._actual_ylims[_cur_pn]
            if _cur_pn in self._axes_bboxes:
                self.DiagramPlots_SHPage.current_axes_bbox = self._axes_bboxes[_cur_pn]

            if(self.pname == "DFN"):
                QtGui.QPixmapCache.clear()
                self.DiagramPlots_SHPage.photo.setPixmap(
                    QtGui.QPixmap(self.work_dir + ".work/DFN.png"))
                self.pname = "DFN"
                self.TableAdjust(self.DiagramPlots_SHPage.tableWidget)
            if(self.pname == "DFI"):
                QtGui.QPixmapCache.clear()
                self.DiagramPlots_SHPage.photo.setPixmap(
                        QtGui.QPixmap(self.work_dir + ".work/DFI.png"))
                self.pname = "DFI"

    # BUG FIX: A4 - Unified _show_diagram method to replace 5 duplicate methods
    # Diagram configuration: default xlim, ylim
    _DIAG_DEFAULTS = {
        "DFN": {"xlim": (0, 1), "ylim": (0, 1000)},
        "DFI": {"xlim": (0, 1), "ylim": (0, 0.004)},
        "DFW": {"xlim": (0, 100), "ylim": (0, 35)},
        "DFA": {"xlim": (0, 100), "ylim": (0, 1)},
        "DFC": {"xlim": (0, 100), "ylim": (0, 0.01)},
    }

    def _effective_step_groups(self):
        """Return self.step_groups when 'Show groups' is checked, else empty dict.
        This gates group COLOR display only; click-to-toggle behaviour is unaffected."""
        try:
            page = self.DiagramPlots_SHPage
            if hasattr(page, 'showGroupsCheckbox') and not page.showGroupsCheckbox.isChecked():
                return {}
        except Exception:
            pass
        return self.step_groups

    def _show_diagram(self, pname):
        """Show diagram with fallback defaults"""
        self.pname = pname
        self._load_SH_config(pname)
        self._ensure_click_callback()
        self.DiagramPlots_SHPage._mouse_move_callback = self.on_mouse_move_SH

        # Use stored limits or fallback to defaults
        defaults = self._DIAG_DEFAULTS.get(pname, {})
        self.DiagramPlots_SHPage.current_axes_bbox = self._axes_bboxes.get(pname)
        self.DiagramPlots_SHPage.current_xlim = self._actual_xlims.get(pname, defaults.get("xlim", (0, 100)))
        self.DiagramPlots_SHPage.current_ylim = self._actual_ylims.get(pname, defaults.get("ylim", (0, 10)))
        self.DiagramPlots_SHPage._update_control_visibility(pname)

        QtGui.QPixmapCache.clear()
        self.DiagramPlots_SHPage.photo.setPixmap(
            QtGui.QPixmap(self.work_dir + f".work/{pname}.png"))

    def DF_SN(self):
        # BUG FIX: A4 - Wrapper calling unified _show_diagram method
        self._show_diagram("DFN")
        # Also sync to LS page
        QtGui.QPixmapCache.clear()
        self.DiagramPlots_LSPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/DFN.png"))

    def DF_SI(self):
        # BUG FIX: A4 - Wrapper calling unified _show_diagram method
        self._show_diagram("DFI")
        # Also sync to LS page
        QtGui.QPixmapCache.clear()
        self.DiagramPlots_LSPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/DFI.png"))
        
    def DF_SK(self):
        Utilities.getDFStatistics_t(self.Dfilename, self.mask,self.power)
        self.DiagramPlots_LSPage.photo.setPixmap(
                QtGui.QPixmap(self.work_dir + ".work/DFK.png"))  # set image in the page 
        self.pname = "DFK"
    
    def submit(self):
        self.power = self.entry.get()
    
    def DF_P(self):
        self.window = Tk()
        self.window.title("Power")
        self.entry = Entry()
        self.entry.pack()
        self.submit = Button(self.window,text="submit",command=self.submit)
        self.submit.pack(side = RIGHT)
        self.window.mainloop()
        
    def _ensure_click_callback(self):
        """Make sure the click-to-select handler is always wired."""
        self.DiagramPlots_SHPage._click_callback = self.on_click_SH

    def DF_SW(self):
        # BUG FIX: A4 - Wrapper calling unified _show_diagram method
        self._show_diagram("DFW")

    def DF_SA(self):
        # BUG FIX: A4 - Wrapper calling unified _show_diagram method
        self._show_diagram("DFA")

    def DF_SCL(self):
        # BUG FIX: A4 - Wrapper calling unified _show_diagram method
        self._show_diagram("DFC")

    def _dfd_open_components_dialog(self):
        """Popup with checkboxes for 5 Ar(m) sums + 16 individual components.
        OK -> sets self._dfd_components_filter (set of label strings) and re-draws."""
        dlg = QtWidgets.QDialog(self.widget)
        dlg.setWindowTitle("Degassing — select components")
        dlg.setMinimumWidth(380)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        vbox = QtWidgets.QVBoxLayout(dlg)

        sums_labels  = ['³⁶Ar(m)', '³⁷Ar(m)', '³⁸Ar(m)', '³⁹Ar(m)', '⁴⁰Ar(m)']
        indiv_labels = [
            '³⁶Ar(a)', '³⁶Ar(c)', '³⁶Ar(ca)', '³⁶Ar(cl)',
            '³⁷Ar(ca)',
            '³⁸Ar(a)', '³⁸Ar(c)', '³⁸Ar(k)', '³⁸Ar(ca)', '³⁸Ar(cl)',
            '³⁹Ar(k)', '³⁹Ar(ca)',
            '⁴⁰Ar(r)', '⁴⁰Ar(a)', '⁴⁰Ar(c)', '⁴⁰Ar(k)',
        ]

        # Determine pre-checked set
        cur = getattr(self, '_dfd_components_filter', None)
        if cur is None:
            page = self.DiagramPlots_SHPage
            if hasattr(page, 'showAllCompCheckbox') and page.showAllCompCheckbox.isChecked():
                cur = set(indiv_labels)
            else:
                cur = set(sums_labels)
        cur = set(cur)

        # Quick-preset buttons
        h_pre = QtWidgets.QHBoxLayout()
        btn_5 = QtWidgets.QPushButton("5 sums")
        btn_16 = QtWidgets.QPushButton("16 individual")
        btn_all = QtWidgets.QPushButton("All 21")
        btn_none = QtWidgets.QPushButton("None")
        h_pre.addWidget(btn_5); h_pre.addWidget(btn_16)
        h_pre.addWidget(btn_all); h_pre.addWidget(btn_none)
        vbox.addLayout(h_pre)

        # Sums group
        grp_sums = QtWidgets.QGroupBox("Ar(m) sums")
        gs = QtWidgets.QGridLayout(grp_sums)
        cb_sums = {}
        for i, lbl in enumerate(sums_labels):
            cb = QtWidgets.QCheckBox(lbl)
            cb.setChecked(lbl in cur)
            cb_sums[lbl] = cb
            gs.addWidget(cb, i // 3, i % 3)
        vbox.addWidget(grp_sums)

        # Individual group
        grp_ind = QtWidgets.QGroupBox("Individual components")
        gi = QtWidgets.QGridLayout(grp_ind)
        cb_indiv = {}
        for i, lbl in enumerate(indiv_labels):
            cb = QtWidgets.QCheckBox(lbl)
            cb.setChecked(lbl in cur)
            cb_indiv[lbl] = cb
            gi.addWidget(cb, i // 4, i % 4)
        vbox.addWidget(grp_ind)

        all_cbs = {**cb_sums, **cb_indiv}
        def _set_only(labels_set):
            for lbl, cb in all_cbs.items():
                cb.setChecked(lbl in labels_set)
        btn_5.clicked.connect(lambda: _set_only(set(sums_labels)))
        btn_16.clicked.connect(lambda: _set_only(set(indiv_labels)))
        btn_all.clicked.connect(lambda: _set_only(set(sums_labels + indiv_labels)))
        btn_none.clicked.connect(lambda: _set_only(set()))

        # OK / Cancel
        h_btn = QtWidgets.QHBoxLayout(); h_btn.addStretch(1)
        btn_ok = QtWidgets.QPushButton("OK"); btn_ok.setDefault(True)
        btn_cancel = QtWidgets.QPushButton("Cancel")
        h_btn.addWidget(btn_ok); h_btn.addWidget(btn_cancel)
        vbox.addLayout(h_btn)
        btn_cancel.clicked.connect(dlg.reject)

        def _accept():
            sel = {lbl for lbl, cb in all_cbs.items() if cb.isChecked()}
            self._dfd_components_filter = sel if sel else None
            dlg.accept()
            # Trigger redraw via SH_apply_axes (uses current pname)
            try:
                self.SH_apply_axes()
            except Exception:
                pass
        btn_ok.clicked.connect(_accept)

        dlg.exec_()

    def DF_SDeg(self):
        """Show Degassing pattern diagram (per-step Ar components vs temperature)."""
        page = self.DiagramPlots_SHPage
        try:
            _res = Utilities.getDegasPlot(
                self.Dfilename, self.mask, self.parameters,
                log_y=page.logYCheckbox.isChecked() if hasattr(page, 'logYCheckbox') else True,
                show_all_components=page.showAllCompCheckbox.isChecked()
                    if hasattr(page, 'showAllCompCheckbox') else False,
                components_filter=getattr(self, '_dfd_components_filter', None),
                show_errorbars=page.showErrorBarsCheckbox.isChecked()
                    if hasattr(page, 'showErrorBarsCheckbox') else False,
                show_legend=page.showLegendCheckbox.isChecked()
                    if hasattr(page, 'showLegendCheckbox') else True,
                legend_name=(page.legendName.text() or None)
                    if hasattr(page, 'legendName') else None,
                style=self._get_plot_style(),
            )
            if isinstance(_res, dict):
                self.step_data.update(_res.get("step_data", {}))
                for k, v in _res.get("actual_xlim", {}).items():
                    self._actual_xlims[k] = v
                for k, v in _res.get("actual_ylim", {}).items():
                    self._actual_ylims[k] = v
                for k, v in _res.get("axes_bbox", {}).items():
                    self._axes_bboxes[k] = v
        except Exception as _e:
            import traceback; traceback.print_exc()
        self._show_diagram("DFD")


    def DF_SSTACK(self):
        """Open Stack / Summary figure dialog."""
        import os
        dlg = QtWidgets.QDialog(self.widget)
        dlg.setWindowTitle("Stack / Summary Figure")
        dlg.setMinimumWidth(340)
        dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        vbox = QtWidgets.QVBoxLayout(dlg)
        vbox.setSpacing(8)

        # ── Mode ────────────────────────────────────────────────
        grp_mode = QtWidgets.QGroupBox("Mode")
        # Fixed vertical size so it doesn't balloon when bottom group hides
        grp_mode.setSizePolicy(
            QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        hm = QtWidgets.QHBoxLayout(grp_mode)
        rb_stack   = QtWidgets.QRadioButton("Stack (2-panel)")
        rb_summary = QtWidgets.QRadioButton("Summary (multi-panel)")
        rb_stack.setChecked(True)
        hm.addWidget(rb_stack)
        hm.addWidget(rb_summary)
        vbox.addWidget(grp_mode)

        # ── Stack options ────────────────────────────────────────
        grp_stack = QtWidgets.QGroupBox("Stack Options")
        vs = QtWidgets.QVBoxLayout(grp_stack)
        # top ratio selector
        h_top = QtWidgets.QHBoxLayout()
        h_top.addWidget(QtWidgets.QLabel("Top ratio:"))
        rb_cak = QtWidgets.QRadioButton("Ca/K")
        rb_clk = QtWidgets.QRadioButton("Cl/K")
        rb_cak.setChecked(True)
        h_top.addWidget(rb_cak)
        h_top.addWidget(rb_clk)
        h_top.addStretch(1)
        vs.addLayout(h_top)
        # log scale
        cb_log = QtWidgets.QCheckBox("Log scale for ratio panel")
        cb_log.setChecked(True)
        vs.addWidget(cb_log)
        # height ratio
        h_ratio = QtWidgets.QHBoxLayout()
        h_ratio.addWidget(QtWidgets.QLabel("Height ratio (top : bottom):"))
        sb_top = QtWidgets.QSpinBox(); sb_top.setRange(1, 10); sb_top.setValue(1)
        sb_bot = QtWidgets.QSpinBox(); sb_bot.setRange(1, 10); sb_bot.setValue(4)
        h_ratio.addWidget(sb_top)
        h_ratio.addWidget(QtWidgets.QLabel(":"))
        h_ratio.addWidget(sb_bot)
        h_ratio.addStretch(1)
        vs.addLayout(h_ratio)

        # Axis ranges removed: now handled by the right-hand Plot Controls
        # (Stack panel selector + X/Y spinboxes + Apply/Auto/Reset).
        vbox.addWidget(grp_stack)

        # ── Summary options ──────────────────────────────────────
        grp_sum = QtWidgets.QGroupBox("Summary Panels")
        vsum = QtWidgets.QVBoxLayout(grp_sum)
        grid = QtWidgets.QGridLayout()
        panels_def = [
            ("age", "Age spectrum",     0, 0),
            ("atm", "%⁴⁰Ar* spectrum", 0, 1),
            ("cak", "Ca/K spectrum",    1, 0),
            ("clk", "Cl/K spectrum",    1, 1),
            ("isn", "Normal isochron",  2, 0),
            ("iso", "Inverse isochron", 2, 1),
        ]
        cbs = {}
        for key, label, row, col in panels_def:
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(True)
            cbs[key] = cb
            grid.addWidget(cb, row, col)
        vsum.addLayout(grid)

        # Layout radios
        vsum.addSpacing(4)
        hlay = QtWidgets.QHBoxLayout()
        hlay.addWidget(QtWidgets.QLabel("Layout:"))
        rb_lay_v = QtWidgets.QRadioButton("Vertical stack")
        rb_lay_g = QtWidgets.QRadioButton("2-column grid")
        rb_lay_v.setChecked(True)
        _bg_lay = QtWidgets.QButtonGroup(grp_sum)
        _bg_lay.addButton(rb_lay_v); _bg_lay.addButton(rb_lay_g)
        hlay.addWidget(rb_lay_v); hlay.addWidget(rb_lay_g); hlay.addStretch(1)
        vsum.addLayout(hlay)

        vbox.addWidget(grp_sum)
        grp_sum.setVisible(False)
        # Bottom stretch absorbs leftover vertical space so the Mode group
        # does not balloon when Stack mode (less content) is selected.
        vbox.addStretch(1)

        # show/hide option groups based on mode + resize dialog to fit content
        def _on_mode_toggled(on):
            grp_stack.setVisible(on)
            grp_sum.setVisible(not on)
            dlg.adjustSize()
        rb_stack.toggled.connect(_on_mode_toggled)

        # ── Buttons ──────────────────────────────────────────────
        hbtn = QtWidgets.QHBoxLayout()
        btn_gen = QtWidgets.QPushButton("Generate")
        btn_gen.setDefault(True)
        btn_can = QtWidgets.QPushButton("Cancel")
        hbtn.addStretch(1)
        hbtn.addWidget(btn_gen)
        hbtn.addWidget(btn_can)
        vbox.addLayout(hbtn)
        btn_can.clicked.connect(dlg.reject)

        def _generate():
            try:
                legend = getattr(self, 'Dlegend', '') or ''
                _plot_style = self._get_plot_style()
                if rb_stack.isChecked():
                    top    = 'Ca/K' if rb_cak.isChecked() else 'Cl/K'
                    log_sc = cb_log.isChecked()
                    h_r    = (sb_top.value(), sb_bot.value())
                    # Inherit ranges from the corresponding standalone pages
                    _top_pname = 'DFA' if top == 'Ca/K' else 'DFC'
                    _xlim_top  = self._actual_xlims.get(_top_pname)
                    _ylim_top  = self._actual_ylims.get(_top_pname)
                    _xlim_bot  = self._actual_xlims.get('DFW')
                    _ylim_bot  = self._actual_ylims.get('DFW')
                    Utilities.getStackPlot(
                        self.Dfilename, self.mask, self.parameters,
                        top=top, log_scale=log_sc, h_ratio=h_r,
                        legend_name=legend or None, style=_plot_style,
                        xlim_top=_xlim_top, ylim_top=_ylim_top,
                        xlim_bot=_xlim_bot, ylim_bot=_ylim_bot,
                        step_groups=self._effective_step_groups(),
                        group_colors=self.GROUP_COLORS,
                    )
                    # Remember DFS state so the right-hand Plot Controls can re-render
                    self._dfs_top_type = top
                    self._dfs_log      = log_sc
                    self._dfs_hratio   = h_r
                    self._dfs_config   = {
                        'top_xlim': _xlim_top, 'top_ylim': _ylim_top,
                        'bot_xlim': _xlim_bot, 'bot_ylim': _ylim_bot,
                    }
                    # sync logYCheckbox to the popup-chosen state for DFS
                    try:
                        self.DiagramPlots_SHPage.logYCheckbox.blockSignals(True)
                        self.DiagramPlots_SHPage.logYCheckbox.setChecked(log_sc)
                        self.DiagramPlots_SHPage.logYCheckbox.blockSignals(False)
                    except Exception:
                        pass
                    self.pname = "DFS"
                    self.DiagramPlots_SHPage._update_control_visibility("DFS")
                    # populate spinboxes from current panel selection
                    try:
                        self._dfs_load_panel_into_spinboxes()
                    except Exception:
                        pass
                    QtGui.QPixmapCache.clear()
                    self.DiagramPlots_SHPage.photo.setPixmap(
                        QtGui.QPixmap(self.work_dir + ".work/DFS.png"))
                else:
                    sel = [k for k, cb in cbs.items() if cb.isChecked()]
                    if not sel:
                        self.Popup(2, "Stack/Summary", "Please select at least one panel.")
                        return
                    _layout = 'grid' if rb_lay_g.isChecked() else 'vertical'
                    self._dfm_panels = list(sel)
                    self._dfm_layout = _layout
                    if not hasattr(self, '_dfm_panel_limits'):
                        self._dfm_panel_limits = {}
                    if not hasattr(self, '_dfm_panel_legends'):
                        self._dfm_panel_legends = {}
                    # Inherit each panel's range from the corresponding standalone page,
                    # but ONLY for keys not already explicitly customised by the user.
                    _key_to_pname = {'age':'DFW','cak':'DFA','clk':'DFC',
                                     'isn':'DFN','iso':'DFI','atm':None}
                    for _k in sel:
                        if _k in self._dfm_panel_limits:
                            continue  # don't overwrite user's customisation
                        _pn = _key_to_pname.get(_k)
                        if not _pn:
                            continue
                        _xl = self._actual_xlims.get(_pn)
                        _yl = self._actual_ylims.get(_pn)
                        if _xl is not None or _yl is not None:
                            self._dfm_panel_limits[_k] = (_xl, _yl)
                    self._dfm_active_key = sel[0]
                    Utilities.getSummaryPlot(
                        self.Dfilename, self.mask, self.parameters,
                        panels=sel, legend_name=None, style=_plot_style,
                        panel_limits=self._dfm_panel_limits,
                        panel_legends=self._dfm_panel_legends,
                        layout=_layout,
                        step_groups=self._effective_step_groups(),
                        group_colors=self.GROUP_COLORS,
                        show_group_fits=self.DiagramPlots_SHPage.showGroupFitsCheckbox.isChecked(),
                        show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
)
                    self.pname = "DFM"
                    _pg = self.DiagramPlots_SHPage
                    _pg.dfmPanelCombo.blockSignals(True)
                    _pg.dfmPanelCombo.clear()
                    _label_map = {'age':'Age','atm':'%40Ar*','cak':'Ca/K','clk':'Cl/K','isn':'Normal isochron','iso':'Inverse isochron'}
                    for k in sel:
                        _pg.dfmPanelCombo.addItem(_label_map.get(k, k), k)
                    _pg.dfmPanelCombo.setCurrentIndex(0)
                    _pg.dfmLayoutCombo.setCurrentIndex(1 if _layout=='grid' else 0)
                    _pg.dfmPanelCombo.blockSignals(False)
                    self.DiagramPlots_SHPage._update_control_visibility("DFM")
                    self._dfm_load_active_to_controls()
                    QtGui.QPixmapCache.clear()
                    self.DiagramPlots_SHPage.photo.setPixmap(
                        QtGui.QPixmap(self.work_dir + ".work/DFM.png"))
                dlg.accept()
            except Exception as e:
                import traceback; traceback.print_exc()
                self.Popup(2, "Stack/Summary Error", str(e))

        btn_gen.clicked.connect(_generate)
        dlg.exec_()

    # ── 3D plane fit ────────────────────────────────────────────
    def DF_S3D(self):
        """Open interactive 3D plane-fit dialog (rotatable/zoomable).

        Group-aware: if step_groups has assignments, fit each group's plane
        separately and overlay them on the same 3D / isochron / summary panels.
        Otherwise fall back to a single fit on the masked data.
        """
        import pandas as pd, traceback
        try:
            df = pd.read_csv(self.Dfilename)
            df = df[df['Age(Ma)'].notna()].reset_index(drop=True)
            # Align mask to df row count
            _m = np.asarray(self.mask, dtype=float).copy()
            _ndf = len(df)
            if _m.size < _ndf:
                _m = np.concatenate([_m, np.ones(_ndf - _m.size)])
            elif _m.size > _ndf:
                _m = _m[:_ndf]
            mask = _m.astype(bool)

            # Full per-step arrays after applying the user mask
            x36_a = df["36Ar(a)"].values[mask]
            s36_a = df["36Ar(a)_std"].values[mask]
            x39_a = df["39Ar(k)"].values[mask]
            s39_a = df["39Ar(k)_std"].values[mask]
            x40_a = (df["40Ar(r)"] + df["40Ar(a)"]).values[mask]
            # v3.8.6 fix: same σ_40 double-counting fix as L4003 (see FORMULAS.md §11.10).
            _v40r_g = df["40Ar(r)_std"].values ** 2
            _v40a_g = df["40Ar(a)_std"].values ** 2
            s40_a = np.sqrt(np.maximum(_v40r_g - _v40a_g, 0.0))[mask]
            T_a   = [f"{int(t)}°C" for t in df["deg C"].values[mask]]
            J  = float(df["J"].iloc[0])
            sJ = float(df["J_std"].iloc[0])
            samp_title = f"{df['Samp#'].iloc[0]} / {df['Min'].iloc[0]} — 3D Plane Fit"

            # Map step_groups (keys are df-row indices, set via on-isochron
            # clicks in DFN/DFI — same row order as the Age(Ma)-filtered df)
            # into the masked-array index space used above.
            orig_to_masked = {orig: mi for mi, orig in
                              enumerate(np.where(mask)[0])}
            valid_groups = {}
            for orig_idx, gn in (self.step_groups or {}).items():
                mi = orig_to_masked.get(int(orig_idx))
                if mi is not None:
                    valid_groups.setdefault(int(gn), []).append(mi)

            from matplotlib.backends.backend_qt5agg import (
                FigureCanvasQTAgg, NavigationToolbar2QT)
            import matplotlib.pyplot as plt

            fittable = {gn: idxs for gn, idxs in valid_groups.items()
                        if len(idxs) >= 3}

            if fittable:
                results_per_group = {}
                labels_per_group  = {}
                for gn, idxs in sorted(fittable.items()):
                    idxs = np.asarray(idxs, dtype=int)
                    results_per_group[gn] = PlaneFit3D.fit_plane(
                        x36_a[idxs], s36_a[idxs],
                        x39_a[idxs], s39_a[idxs],
                        x40_a[idxs], s40_a[idxs],
                        J=J, s_J=sJ, k0=0.025004)
                    labels_per_group[gn] = [T_a[i] for i in idxs]
                self.plane3d_result = results_per_group
                fig = PlaneFit3D.plot_result_grouped(
                    results_per_group, title=samp_title,
                    labels_per_group=labels_per_group,
                    group_colors=self.GROUP_COLORS, save_path=None)
                skipped = [gn for gn, idxs in valid_groups.items()
                           if len(idxs) < 3]
                if skipped:
                    print(f"[3D Plane Fit] skipped groups (n<3): {skipped}")
            else:
                self.plane3d_result = PlaneFit3D.fit_plane(
                    x36_a, s36_a, x39_a, s39_a, x40_a, s40_a,
                    J=J, s_J=sJ, k0=0.025004)
                fig = PlaneFit3D.plot_result(
                    self.plane3d_result, title=samp_title,
                    labels=T_a, save_path=None)

            dlg = QtWidgets.QDialog(self.widget)
            dlg.setWindowTitle(samp_title)
            dlg.resize(1280, 860)
            dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
            lay = QtWidgets.QVBoxLayout(dlg)
            lay.setContentsMargins(4, 4, 4, 4)
            lay.setSpacing(4)
            canvas  = FigureCanvasQTAgg(fig)
            toolbar = NavigationToolbar2QT(canvas, dlg)
            lay.addWidget(toolbar)
            lay.addWidget(canvas)
            dlg.finished.connect(lambda _: plt.close(fig))
            dlg.show()
        except Exception as e:
            traceback.print_exc()
            self.Popup(2, "3D Plane Fit Error", str(e))


    def _fill_3D_table_row(self):
        """Populate tableWidget rows with 3D-plane-fit results.

        Single fit  → one extra row labeled "3D".
        Multi-group → one row per group labeled "3D-G1", "3D-G2", ...
        """
        res = self.plane3d_result
        tw = self.DiagramPlots_SHPage.tableWidget

        # Normalize to a list of (row_label, result_dict) pairs
        if isinstance(res, dict) and ('alpha' not in res):
            pairs = [(f"3D-G{gn}", r) for gn, r in sorted(res.items())]
        else:
            pairs = [("3D", res)]

        target_rows = 1 + len(pairs)
        if tw.rowCount() < target_rows:
            tw.setRowCount(target_rows)
        for i, (lbl, _) in enumerate(pairs, start=1):
            tw.setVerticalHeaderItem(i, QtWidgets.QTableWidgetItem(lbl))

        def _si(row, col, text, color=None):
            item = QtWidgets.QTableWidgetItem(str(text))
            item.setFlags(QtCore.Qt.ItemIsEnabled)
            item.setTextAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            if color:
                item.setBackground(QtGui.QColor(color))
            tw.setItem(row, col, item)

        for ri, (_, r) in enumerate(pairs, start=1):
            # Reuse sample / Min / IRR / J / J_std from row 0
            for col in range(5):
                src = tw.item(0, col)
                if src:
                    _si(ri, col, src.text())

            mswd_ok = r['mswd_lo95'] <= r['mswd'] <= r['mswd_hi95']
            color_mswd = "#d0edda" if mswd_ok else "#fde8e8"

            _si(ri, 5,  f"n={r['n']}")
            _si(ri, 6,  f"{r['mswd']:.3f}", color_mswd)
            _si(ri, 7,  f"{r['mswd_lo95']:.2f}")
            _si(ri, 8,  f"{r['mswd_hi95']:.2f}")
            _si(ri, 9,  f"{r['alpha']:.4f}")
            _si(ri, 10, f"±{r['s_alpha']:.4f}")
            _si(ri, 11, f"{r['beta']:.6f}")
            _si(ri, 12, f"±{r['s_beta']:.6f}")
            age_str = (f"{r['age_Ma']:.3f}" if r['J'] is not None
                       and not __import__('math').isnan(r['age_Ma']) else "—")
            _si(ri, 13, age_str)
            sage_str = (f"±{r['s_age_Ma']:.3f}" if r['J'] is not None
                        and not __import__('math').isnan(r['s_age_Ma']) else "—")
            _si(ri, 14, sage_str)

    def DFLS_save(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save DF plot result" , self.screenshot_folder+'Publish/LaserOB/', "Images (*.png *.jpg *.jpeg)")
        if len(filename) > 0:
            shutil.copyfile(self.work_dir + '.work/DFN.png', filename)
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save DF plot result" , self.screenshot_folder+'Publish/LaserOB/', "Images (*.png *.jpg *.jpeg)")
        if len(filename) > 0:
            shutil.copyfile(self.work_dir + '.work/DFI.png', filename)
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save DF plot result" , self.screenshot_folder+'Publish/LaserOB/', "Images (*.png *.jpg *.jpeg)")
        if len(filename) > 0:
            shutil.copyfile(self.work_dir + '.work/DFK.png', filename)
        
        file, _ = QtWidgets.QFileDialog.getSaveFileName(self.widget, "Save plot result" , self.data_folder+'Publish/LaserOB/', "(*.csv)")
        if len(file) > 0:
            f = open(file, 'w')
            f.write("Weighted Plateau,Total Fusion Age,39/36 Int,39/36 Int std,36/40 Int,36/40 Int std,MSWD,WMA,Int age,Int age std\n")

            def _fmt_age(v):
                try:
                    return f"{float(v):.3f}"
                except Exception:
                    return str(v)

            def _fmt_ratio(v):
                try:
                    return f"{float(v):.6f}"
                except Exception:
                    return str(v)

            def _fmt_generic(v):
                try:
                    return f"{float(v):.3f}"
                except Exception:
                    return str(v)

            # two ages: weighted plateau, total fusion
            for i in range(2):
                f.write(f"{_fmt_age(self.sh_result[i])},")

            # DF results: [n, n_std, iv, iv_std, mswd, wma, int_age, int_age_std]
            for i in range(8):
                v = self.DF_result[i]
                if i in (0, 1, 2, 3):
                    f.write(f"{_fmt_ratio(v)},")
                elif i in (5, 6, 7):
                    f.write(f"{_fmt_age(v)},")
                else:
                    f.write(f"{_fmt_generic(v)},")

            f.close()
    
    def DFSH_save(self):
        # BUG FIX: A3 - Select folder once, auto-name all outputs
        out_dir = QtWidgets.QFileDialog.getExistingDirectory(
            self.widget, "Select output folder for Step Heating diagrams",
            self.screenshot_folder + 'Publish/StepHeating/'
        )
        if not out_dir:
            return

        # Dictionary of files to save: {filename: description/source}
        _files_to_save = {
            'DFN.png': 'Normal isochron',
            'DFI.png': 'Inverse isochron',
            'DFW.png': '40Ar*/39Ar K vs 39Ar K/40Ar* (Waage-Cassignol)',
            'DFA.png': 'Ca/K vs 39Ar K/40Ar*',
            'DFC.png': 'Cl/K vs 39Ar K/40Ar*',
        }

        # Save core diagrams
        for filename, desc in _files_to_save.items():
            src = self.work_dir + f'.work/{filename}'
            dst = os.path.join(out_dir, filename)
            if os.path.exists(src):
                try:
                    shutil.copyfile(src, dst)
                except Exception as e:
                    print(f"Error copying {filename}: {e}")

        # Save optional plots if they exist
        for optional_file in ['DFS.png', 'DFM.png']:
            src = self.work_dir + f'.work/{optional_file}'
            dst = os.path.join(out_dir, optional_file)
            if os.path.exists(src):
                try:
                    shutil.copyfile(src, dst)
                except Exception as e:
                    print(f"Error copying {optional_file}: {e}")

        # Save summary CSV with same auto-naming
        csv_path = os.path.join(out_dir, 'summary.csv')
        try:
            # BUG FIX B3: CSV format - use csv module and proper newline handling
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Weighted Plateau","Total Fusion Age","39/36 Int","39/36 Int std","36/40 Int","36/40 Int std","MSWD","WMA","Int age","Int age std"])
                row_data = [self.sh_result[i] for i in range(2)] + [self.DF_result[i] for i in range(8)]
                writer.writerow(row_data)
        except Exception as e:
            print(f"Error writing summary.csv: {e}")


    def DFSH_export_excel(self):
        """Export step heating diagrams to Excel by embedding GUI PNGs + data + summary (V3.5 PNG-embed edition)."""
        try:
            msg = QtWidgets.QMessageBox(self.widget)
            msg.setWindowTitle("Export to Excel")
            msg.setText("Export 6 step-heating diagrams to Excel?\n\n"
                       "Diagrams: DFN, DFI, DFW, DFA, DFC, DFM (same as GUI).\n"
                       "PNGs from .work/ will be embedded; raw data + summary tables included.")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if msg.exec_() != QtWidgets.QMessageBox.Yes:
                return

            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.widget,
                "Export to Excel",
                self.data_folder + 'Publish/StepHeating/pyADR_Export.xlsx',
                "Excel Workbook (*.xlsx)"
            )
            if not filename:
                return

            # Build stats dict from current state
            stats = {
                'sh_result': list(getattr(self, 'sh_result', []) or []),
                'DF_result': list(getattr(self, 'DF_result', []) or []),
            }

            exporter = ExcelChartExporter.ExcelChartExporter(
                self.Dfilename,
                self.mask,
                self.parameters,
                filename,
                work_dir=getattr(self, 'work_dir', None),
                stats=stats,
            )
            exporter.export(diagrams=['DFN', 'DFI', 'DFW', 'DFA', 'DFC', 'DFM'])

            self.Popup(1, "Success!", f"Excel file saved:\n{filename}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.Popup(2, "Error!", f"Export failed:\n{str(e)}")

    def DF_setReselectTable(self):
        w = self.ReselectDialog.frameGeometry().width()
        h = self.ReselectDialog.frameGeometry().height()
        self.ReselectDialog.ReselectTable = QtWidgets.QTableWidget(self.ReselectDialog)
        self.ReselectDialog.ReselectTable.setGeometry(QtCore.QRect(int(0.1*w), int(0.2*h), int(0.8*w), int(0.5*h)))
        self.ReselectDialog.ReselectTable.setObjectName("ReselectTable")
        self.ReselectDialog.ReselectTable.setColumnCount(len(self.data)-2)
        self.ReselectDialog.ReselectTable.setRowCount(1)
        self.ReselectDialog.ReselectTable.setVerticalHeaderLabels(['J'])
        self.ReselectDialog.ReselectTable.setHorizontalHeaderLabels(['{}'.format(i) for i in range(1, self.numCycle+1)])
        
        header = self.ReselectDialog.ReselectTable.horizontalHeader()
        for i in range(self.ReselectDialog.ReselectTable.columnCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)

        header = self.ReselectDialog.ReselectTable.verticalHeader()
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            header.setSectionResizeMode(i, QtWidgets.QHeaderView.Stretch)
        
        for i in range(self.ReselectDialog.ReselectTable.rowCount()):
            for j in range(self.ReselectDialog.ReselectTable.columnCount()):
                item = QtWidgets.QTableWidgetItem()
                item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.Checked)
                self.ReselectDialog.ReselectTable.setItem(i, j, item)

    def LS_reselect(self):
        self.ReselectDialog.show()
        self.ReselectDialog.buttonBox.accepted.connect(self.LS_checkReselectTable)
        
    def LS_checkReselectTable(self):
        for j in range(self.ReselectDialog.ReselectTable.columnCount()):
            item = self.ReselectDialog.ReselectTable.item(0,j)
            if item.checkState() == QtCore.Qt.Unchecked:
                self.mask[j] = 0
            else:
                self.mask[j] = 1
        
        self.DF_result = Utilities.getDFStatistics_ls(self.Dfilename, self.mask, self.parameters)
        Utilities.getDFStatistics_t(self.Dfilename, self.mask,self.power)
                
        for i in range(3):
            item = QtWidgets.QTableWidgetItem('{}'.format(self.data[1].split(',')[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_LSPage.tableWidget.setItem(0, i, item)  
            
        for i in range(2):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(float(self.data[1].split(',')[4+i])))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_LSPage.tableWidget.setItem(0, i+3, item)    
                
        for i in range(8):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.DF_result[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_LSPage.tableWidget.setItem(0, i+5, item)
        
        # set image
        self.DiagramPlots_LSPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/"+self.pname+".png"))
            
        # show the page
        self.TableAdjust(self.DiagramPlots_LSPage.tableWidget)
    
    def SH_reselect(self):
        self.ReselectDialog.show()
        self.ReselectDialog.buttonBox.accepted.connect(self.SH_checkReselectTable)
        
    def SH_checkReselectTable(self):
        for j in range(self.ReselectDialog.ReselectTable.columnCount()):
            item = self.ReselectDialog.ReselectTable.item(0,j)
            if item.checkState() == QtCore.Qt.Unchecked:
                self.mask[j] = 0
            else:
                self.mask[j] = 1
        
        self.DF_result = Utilities.getDFStatistics_sh(
            self.Dfilename, self.mask, self.parameters, 'r', 'o',
            show_temp=False, show_atm=True, atm_ratio=298.56,
            style=self._get_plot_style(),
            show_group_fits=self.DiagramPlots_SHPage.showGroupFitsCheckbox.isChecked(),
            show_overall_fit=self.DiagramPlots_SHPage.showOverallFitCheckbox.isChecked(),
)
        result = Utilities.getSHStatistics(self.Dfilename, self.mask, self.parameters,
                                           style=self._get_plot_style())
        
        # Extract statistics, step data, axes_bbox, actual limits
        if isinstance(result, dict):
            self.sh_result = result.get("statistics", [0, 0])
            self.step_data.update(result.get("step_data", {}))
            for _pn in ("DFW", "DFA", "DFC"):
                if _pn in result.get("axes_bbox", {}):
                    self._axes_bboxes[_pn] = result["axes_bbox"][_pn]
                if _pn in result.get("actual_xlim", {}):
                    self._actual_xlims[_pn] = result["actual_xlim"][_pn]
                if _pn in result.get("actual_ylim", {}):
                    self._actual_ylims[_pn] = result["actual_ylim"][_pn]
        else:
            self.sh_result = result
                
        for i in range(3):
            item = QtWidgets.QTableWidgetItem('{}'.format(self.data[1].split(',')[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_SHPage.tableWidget.setItem(0, i, item)  
            
        for i in range(2):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(float(self.data[1].split(',')[4+i])))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_SHPage.tableWidget.setItem(0, i+3, item)    
                
        for i in range(2):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.sh_result[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_SHPage.tableWidget.setItem(0, i+5, item)
                
        for i in range(8):
            item = QtWidgets.QTableWidgetItem('{:0.5e}'.format(self.DF_result[i]))
            item.setFlags(QtCore.Qt.ItemIsEnabled) # disable edit
            self.DiagramPlots_SHPage.tableWidget.setItem(0, i+7, item)
        
        # set image
        self.DiagramPlots_SHPage.photo.setPixmap(QtGui.QPixmap(self.work_dir+".work/"+self.pname+".png"))

        # show the page
        self.TableAdjust(self.DiagramPlots_SHPage.tableWidget)

    # methods for Datum Publication Page
    # ===============================================================================
    def toDPS(self):
        self.widget.setCurrentIndex(19)
    def toAP(self):
        self.AutoPipelinePage.set_context(
            self.parameters, self.parameters_name,
            int(self.parameters[self.parameters_name.index('numCycle')])
        )
        # v3.8.60: open AutoPipeline big. v3.8.63: use showMaximized() not
        # showFullScreen() — full-screen hides the title bar, so the min /
        # max / close buttons vanished. Maximized fills the work area but
        # keeps the title bar + window controls (and doesn't cover the taskbar).
        self.widget.setCurrentIndex(20)
        self.widget.showMaximized()

    def toDPR(self):
        """ISOr export — produce 8-column isochron-ratio table from MassRatio CSVs.

        Output header: 39/40,err[39/40],36/40,err[36/40],39/36,err[39/36],39,Samp#

        Restored in v3.7.2: was lost in earlier refactor that mis-bound the ISOr
        button to toDP (Publish Table). Logic ported from v2.0 toDPR.
        """
        filelist, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self.widget,
            "Select files (csv) to get Datum statistics",
            self.data_folder + 'MassRatio/',
            "(*.csv)"
        )
        if len(filelist) <= 0:
            return

        f = None
        try:
            outfile, _ = QtWidgets.QFileDialog.getSaveFileName(
                self.widget,
                "Save ISOr result",
                self.data_folder + 'Publish/',
                "(*.csv)"
            )
            if len(outfile) <= 0:
                return

            f = open(outfile, 'w', encoding="utf-8")
            f.write("39/40,err[39/40],36/40,err[36/40],39/36,err[39/36],39,Samp#\n")

            expected_header = ("Samp#,t,Min,iradiation PK 90%,Mass,Raw,"
                               "Measurment,Measurement's Sigma,Ratio,Value,Ratio's Sigma")
            for filename in filelist:
                with open(filename, 'r', encoding="utf-8", errors="ignore") as d:
                    data = d.readlines()
                if data[0].rstrip() != expected_header:
                    raise Exception("Wrong data format in {}".format(filename))
                ar3940    = float(data[1].split(',')[9])
                ar3940std = float(data[1].split(',')[10])
                ar3640    = float(data[2].split(',')[9])
                ar3640std = float(data[2].split(',')[10])
                ar3936    = float(data[3].split(',')[9])
                ar3936std = float(data[3].split(',')[10])
                ar39      = float(data[4].split(',')[6])
                samp      = data[1].split(',')[0]
                f.write("{},{},{},{},{},{},{},{}\n".format(
                    ar3940, ar3940std, ar3640, ar3640std,
                    ar3936, ar3936std, ar39, samp
                ))
        except Exception as e:
            import traceback
            traceback.print_exc()
            try:
                self.Popup(2, "ISOr Error",
                           "Please check the selected data format!\n{}".format(e))
            except Exception:
                pass
        finally:
            if f is not None:
                try:
                    f.close()
                except Exception:
                    pass
    def toDP(self):
            filelist, _ = QtWidgets.QFileDialog.getOpenFileNames(
                self.widget,
                "Select files (csv) to get Datum statistics",
                self.data_folder + 'Agecalc/',
                "(*.csv)"
            )
            if len(filelist) <= 0:
                return

            f = None
            try:
                outfile, _ = QtWidgets.QFileDialog.getSaveFileName(
                    self.widget,
                    "Save Datum result",
                    self.data_folder + 'Publish/',
                    "(*.csv)"
                )
                if len(outfile) <= 0:
                    return

                import csv
                # 使用 utf-8-sig 可以讓 Excel 正確讀取中文或特殊符號
                f = open(outfile, 'w', newline='', encoding="utf-8")
                writer = csv.writer(f, lineterminator="\n")

                # 1. 寫入標頭 (88 欄, v3.7.3 — 對齊老師格式; isochron 改用 ISOr 工具獨立輸出)
                writer.writerow([
                    "Samp#","Min","IRR","deg C","J","J_std","J_int",
                    "36Ar(a)","36Ar(a)_std","37Ar(ca)","37Ar(ca)_std",
                    "38Ar(cl)","38Ar(cl)_std","39Ar(k)","39Ar(k)_std",
                    "40Ar(r)","40Ar(r)_std","Age(Ma)","Age_std(Ma)",
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
                    "Lambda","numCycle"
                ])

                # 2. First pass: calculate totals for step heating %
                # Helper function to read variables by name (needed for first pass)
                def read_var_from_file(filepath, var_name):
                    """Read variable value from AgeCalc CSV file"""
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            for line in f:
                                parts = line.strip().split(',')
                                if len(parts) >= 7 and parts[4].strip() == var_name:
                                    val = parts[5].strip()
                                    if val not in ['N/A', 'NA', '', 'nan', 'NaN']:
                                        return float(val)
                    except:
                        pass
                    return 0.0
                
                sum_39K = 0.0
                sum_40r = 0.0
                for filename in filelist:
                    try:
                        # Read Ar_39_K directly by variable name
                        ar39k = read_var_from_file(filename, "Ar_39_K")
                        sum_39K += ar39k
                        
                        # Read Ar_40_r directly by variable name
                        ar40r = read_var_from_file(filename, "Ar_40_r")
                        sum_40r += ar40r
                    except Exception as e:
                        print(f"Warning: Skipping file {filename} in first pass due to error: {e}")
                        continue

                # Avoid division by zero
                if sum_39K == 0:
                    sum_39K = 1e-30
                if sum_40r == 0:
                    sum_40r = 1e-30
                # Get atmospheric ratios from parameters
                try:
                    ratio_38_36_a = float(self.parameters[self.parameters_name.index("Atmospheric Ratio 38/36(a)")])
                    ratio_38_36_a_std = float(self.parameters[self.parameters_name.index("Atmospheric Ratio 38/36(a) std")])
                    ratio_38_39_k = float(self.parameters[self.parameters_name.index("Production Ratio 38Ar/39Ar(k)")])
                    ratio_38_39_k_std = float(self.parameters[self.parameters_name.index("Production Ratio 38Ar/39Ar(k) std")])
                    pr_ratio = float(self.parameters[self.parameters_name.index("Production Ratio 39Ar/37Ar(ca)")])
                except:
                    ratio_38_36_a, ratio_38_36_a_std = 0.1885, 0.000347
                    ratio_38_39_k, ratio_38_39_k_std = 0.0126288, 0.000010529
                    pr_ratio = 0.0007

                # --- Second pass: write rows ---
                for filename in filelist:
                    with open(filename, 'r', encoding="utf-8", errors="ignore") as d:
                        lines = d.readlines()

                    # Helper function: extract values with error handling
                    def g(row_idx, col_idx=5):
                        try:
                            val = lines[row_idx].split(',')[col_idx].strip()
                            if val in ['N/A', 'NA', '', 'nan', 'NaN']:
                                return "0"
                            return val
                        except:
                            return "0"
                    # Helper function to read variables by name from AgeCalc CSV
                    def get_variable(var_name, col_idx=5):
                        """Read value from AgeCalc CSV by Variable name"""
                        try:
                            for line in lines:
                                parts = line.strip().split(',')
                                if len(parts) >= 7 and parts[4].strip() == var_name:
                                    val = parts[col_idx].strip()
                                    if val in ['N/A', 'NA', '', 'nan', 'NaN']:
                                        return 0.0
                                    return float(val)
                        except:
                            pass
                        return 0.0
                    # Calculate intermediate values - use get_variable
                    ar39k_raw = get_variable("Ar_39_K", 5)
                    ar40r_raw = get_variable("Ar_40_r", 5)
                    
                    # Calculate step heating percentages
                    ar39k_step_per = round(ar39k_raw / sum_39K * 100, 4) if sum_39K != 0 else 0
                    ar40r_step_per = round(ar40r_raw / sum_40r * 100, 4) if sum_40r != 0 else 0


                    # Recalculate 38Ar components (Datum Publication端重算)
                    ar36a = float(g(2))
                    ar36a_std = float(g(2, 6))
                    ar39k = float(g(10))
                    ar39k_std = float(g(10, 6))
                    ar38m = float(g(6))
                    ar38m_std = float(g(6, 6))
                    
                    # 38Ar(air) = 36Ar(a) * (38/36)(a)
                    ar38air = ar36a * ratio_38_36_a
                    if ar36a != 0 and ratio_38_36_a != 0:
                        ar38air_std = abs(ar38air) * ((ar36a_std / ar36a) + (ratio_38_36_a_std / ratio_38_36_a))
                    else:
                        ar38air_std = 0
                    
                    # 38Ar(K) = 39Ar(K) * (38/39)(k)
                    ar38k = ar39k * ratio_38_39_k
                    if ar39k != 0 and ratio_38_39_k != 0:
                        ar38k_std = abs(ar38k) * ((ar39k_std / ar39k) + (ratio_38_39_k_std / ratio_38_39_k))
                    else:
                        ar38k_std = 0
                    
                    # 38Ar(cl) = 38m - 38air - 38K
                    ar38cl = ar38m - ar38air - ar38k
                    ar38cl_std = (ar38m_std**2 + ar38air_std**2 + ar38k_std**2)**0.5

                    # Build row (88 columns, v3.7.3 — isochron section removed; use ISOr tool instead)
                    row = ["0"] * 88
                    
                    # [0-6] Basic info
                    row[0] = lines[1].split(',')[0]  # Samp#
                    row[1] = lines[1].split(',')[2]  # Min
                    row[2] = lines[1].split(',')[3]  # IRR
                    row[3] = lines[1].split(',')[1]  # deg C
                    row[4] = g(23)                   # J
                    row[5] = g(23, 6)                # J_std
                    row[6] = g(25)                   # J_int

                    # [7-16] Core isotopes
                    row[7], row[8] = g(2), g(2, 6)    # 36Ar(a)
                    row[9], row[10] = g(5), g(5, 6)   # 37Ar(ca)
                    row[11], row[12] = ar38cl, ar38cl_std  # 38Ar(cl) - RECALCULATED
                    row[13], row[14] = g(10), g(10, 6)     # 39Ar(k)
                    row[15], row[16] = g(13), g(13, 6)     # 40Ar(r)

                    # [17-18] Age (Ma)
                    row[17] = float(g(24)) / 1000000
                    row[18] = float(g(24, 6)) / 1000000

                    # [19-20] 40Ar(r)(%) and 39Ar(k)(%) - CORRECTED FORMULA
                    ar40m = float(g(12))  # 40Ar(m)
                    ar40r = float(g(13))  # 40Ar(r)
                    row[19] = round(ar40r / ar40m * 100, 4) if ar40m != 0 else 0  # 40Ar(r)(%)
                    
                    ar39m = float(g(9))   # 39Ar(m)
                    ar39k = float(g(10))  # 39Ar(k)
                    row[20] = round(ar39k / ar39m * 100, 4) if ar39m != 0 else 0  # 39Ar(k)(%)

                    # [21-22] Step heating %
                    row[21] = ar40r_step_per
                    row[22] = ar39k_step_per
                    
                    # [23-24] Ca/K (FIXED in V3.0.1: was inverted and used wrong constant)
                    # Ca/K = 37Ar(ca) × R / 39Ar(k), R=0.52 (lab calibration, same as getJVolumeStatistics)
                    # 原本用 pr_ratio(39/37_ca=0.000377) 當 R，且分子分母接反 → 錯誤
                    _ar37 = float(g(5))
                    _ar39 = float(g(10))
                    _ar37_std = float(g(5, 6))
                    _ar39_std = float(g(10, 6))
                    if _ar39 != 0 and _ar37 != 0:
                        CaK = (_ar37 * 0.52) / _ar39
                        CaK_std = CaK * ((_ar37_std / _ar37) + (_ar39_std / _ar39))
                    elif _ar39 != 0:
                        CaK = 0.0
                        CaK_std = 0.0
                    else:
                        CaK = 0.0
                        CaK_std = 0.0
                    row[23] = CaK
                    row[24] = CaK_std

                    # [25] Degassing Patterns (empty)
                    row[25] = ""

                    # [26-57] Detailed isotope breakdown - use get_variable for accuracy
                    # 36Ar components
                    row[26] = get_variable("Ar_36_air", 5)
                    if row[26] == 0:
                        row[26] = get_variable("Ar_36_a", 5)
                    row[27] = get_variable("Ar_36_air", 6)
                    if row[27] == 0:
                        row[27] = get_variable("Ar_36_a", 6)
                    
                    row[28], row[29] = 0.0, 0.0  # 36Ar(c) - placeholder
                    
                    row[30] = get_variable("Ar_36_Ca", 5)
                    if row[30] == 0:
                        row[30] = get_variable("Ar_36_ca", 5)
                    row[31] = get_variable("Ar_36_Ca", 6)
                    if row[31] == 0:
                        row[31] = get_variable("Ar_36_ca", 6)
                    
                    # 36Ar(cl) - calculate from 38Ar(cl)
                    try:
                        pr_36_38_cl = float(self.parameters[self.parameters_name.index("Production Ratio 36Ar/38Ar(cl)")])
                    except:
                        pr_36_38_cl = 0.0
                    row[32] = pr_36_38_cl * ar38cl
                    row[33] = abs(pr_36_38_cl) * ar38cl_std
                    
                    # 37Ar components
                    row[34] = get_variable("Ar_37_ca", 5)
                    if row[34] == 0:
                        row[34] = get_variable("Ar_37_Ca", 5)
                    row[35] = get_variable("Ar_37_ca", 6)
                    if row[35] == 0:
                        row[35] = get_variable("Ar_37_Ca", 6)
                    
                    # 38Ar components
                    row[36], row[37] = ar38air, ar38air_std  # 38Ar(a) - RECALCULATED
                    row[38], row[39] = 0.0, 0.0  # 38Ar(c) - placeholder
                    row[40], row[41] = ar38k, ar38k_std   # 38Ar(k) - RECALCULATED
                    row[42], row[43] = 0.0, 0.0  # 38Ar(ca) - placeholder
                    row[44], row[45] = ar38cl, ar38cl_std # 38Ar(cl) - RECALCULATED
                    
                    # 39Ar components
                    row[46] = get_variable("Ar_39_K", 5)
                    row[47] = get_variable("Ar_39_K", 6)
                    row[48] = get_variable("Ar_39_Ca", 5)
                    row[49] = get_variable("Ar_39_Ca", 6)
                    
                    # 40Ar components
                    row[50] = get_variable("Ar_40_r", 5)
                    row[51] = get_variable("Ar_40_r", 6)
                    
                    row[52] = get_variable("Ar_40_air", 5)
                    if row[52] == 0:
                        row[52] = get_variable("Ar_40_a", 5)
                    row[53] = get_variable("Ar_40_air", 6)
                    if row[53] == 0:
                        row[53] = get_variable("Ar_40_a", 6)
                    
                    row[54], row[55] = 0.0, 0.0  # 40Ar(c) - placeholder
                    
                    row[56] = get_variable("Ar_40_K", 5)
                    row[57] = get_variable("Ar_40_K", 6)

                    # [58] Additional Parameters separator
                    row[58] = "Additional Parameters"
                    
                    # [59-68] Additional ratio parameters - READ FROM AGECALC CSV
                    # 40(r)/39(k) and std - Variable: F(Ar_40_r/Ar_39_K)
                    row[59] = get_variable("F(Ar_40_r/Ar_39_K)", 5)
                    row[60] = get_variable("F(Ar_40_r/Ar_39_K)", 6)
                    
                    # 40(r+a) and std - use get_variable to read from CSV
                    ar40r_val = get_variable("Ar_40_r", 5)
                    ar40r_std_val = get_variable("Ar_40_r", 6)
                    ar40a_val = get_variable("Ar_40_air", 5)
                    if ar40a_val == 0:
                        ar40a_val = get_variable("Ar_40_a", 5)
                    ar40a_std_val = get_variable("Ar_40_air", 6)
                    if ar40a_std_val == 0:
                        ar40a_std_val = get_variable("Ar_40_a", 6)
                    row[61] = ar40r_val + ar40a_val  # 40(r+a)
                    row[62] = (ar40r_std_val**2 + ar40a_std_val**2)**0.5  # std
                    
                    # 40Ar/39Ar and std - Variable: G(Ar_40_m/Ar_39_m)
                    row[63] = get_variable("G(Ar_40_m/Ar_39_m)", 5)
                    row[64] = get_variable("G(Ar_40_m/Ar_39_m)", 6)
                    
                    # 37Ar/39Ar and std - Variable: D(Ar_37_m/Ar_39_m)
                    row[65] = get_variable("D(Ar_37_m/Ar_39_m)", 5)
                    row[65] = get_variable("D(Ar_37_m/Ar_39_m)", 5)
                    row[66] = get_variable("D(Ar_37_m/Ar_39_m)", 6)

                    # 36Ar/39Ar and std - Variable: B(Ar_36_m/Ar_39_M)
                    # FIX v3.7.4-hotfix: AgeCalc UI writes 'B(Ar_36_m/Ar_39_M)' (B prefix,
                    # capital M); old lookup used 'E(Ar_36_m/Ar_39_m)' → returned 0.0.
                    row[67] = get_variable("B(Ar_36_m/Ar_39_M)", 5)
                    row[68] = get_variable("B(Ar_36_m/Ar_39_M)", 6)

                    # [69] Parameters separator
                    row[69] = "Parameters"

                    # [70-85] IRR / atmospheric production-ratio constants
                    # FIX v3.7.4-hotfix: previously row[70..87] left as default "0".
                    # Order must match header at line 4548-4552.
                    pkeys = [
                        "Production Ratio 39Ar/37Ar(ca)", "Production Ratio 39Ar/37Ar(ca) std",
                        "Production Ratio 36Ar/37Ar(ca)", "Production Ratio 36Ar/37Ar(ca) std",
                        "Production Ratio 40Ar/39Ar(k)", "Production Ratio 40Ar/39Ar(k) std",
                        "Production Ratio 38Ar/39Ar(k)", "Production Ratio 38Ar/39Ar(k) std",
                        "Production Ratio 39Ar/37Ar(k)", "Production Ratio 39Ar/37Ar(k) std",
                        "Production Ratio 36Ar/38Ar(cl)", "Production Ratio 36Ar/38Ar(cl) std",
                        "Atmospheric Ratio 40/36(a)", "Atmospheric Ratio 40/36(a) std",
                        "Atmospheric Ratio 38/36(a)", "Atmospheric Ratio 38/36(a) std",
                    ]
                    for idx, key in enumerate(pkeys):
                        try:
                            row[70 + idx] = self.parameters[self.parameters_name.index(key)]
                        except (ValueError, IndexError):
                            row[70 + idx] = "0"

                    # [86] Lambda (decay constant) — key uses λ (UTF-8)
                    try:
                        row[86] = self.parameters[self.parameters_name.index("λ for age calculation")]
                    except (ValueError, IndexError):
                        row[86] = "5.49e-10"

                    # [87] numCycle
                    try:
                        row[87] = self.parameters[self.parameters_name.index("numCycle")]
                    except (ValueError, IndexError):
                        row[87] = "10"

                    writer.writerow(row)

            except Exception as e:
                import traceback
                traceback.print_exc()
                try:
                    self.Popup(2, "Datum Export Error", str(e))
                except Exception:
                    pass
            finally:
                if f is not None:
                    try:
                        f.close()
                    except Exception:
                        pass


if __name__ == '__main__':
    App().run()
