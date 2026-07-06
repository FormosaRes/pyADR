# -*- coding: utf-8 -*-
"""
ClosureTemperature.py  —  pyADR mineral closure-temperature calculator
======================================================================
Dodson (1973) closure temperature for volume-diffusion thermochronometers,
seeded with the ⁴⁰Ar/³⁹Ar diffusion-parameter compilation of Schaen et al.
(2021), Table 5.

Dodson (1973), Contrib. Mineral. Petrol. 40, 259–274:

        Tc = E / [ R · ln( A · τ · D0 / a² ) ]

    with the cooling time constant
        τ = R · Tc² / ( E · |dT/dt| )

so Tc appears on both sides and is solved by fixed-point iteration.

  E      activation energy                    (J/mol; UI takes kJ/mol or
                                               kcal/mol, selectable)
  D0     pre-exponential (frequency) factor   (m²/s)
  a      effective diffusion radius           (m; UI takes µm)
  A      geometry factor  55 sphere / 27 cylinder / 8.7 plane sheet
  dT/dt  cooling rate                         (K/s; UI takes °C/Myr)
  R      gas constant                         8.314462618 J/mol/K

The math (`closure_temperature`, `MINERAL_DB`) has no Qt dependency and is
unit-tested at the bottom of this file (`python ClosureTemperature.py`). The
`ClosureTempDialog` is opened from the pyADR Home-page menu and from the
AgeCalc/Datum sidebar in AutoPipeline.

Diffusion parameters (all editable in the UI) are the "nominal bulk closure
temperature" compilation for commonly used ⁴⁰Ar/³⁹Ar thermochronometers:

  Schaen, A.J., Jicha, B.R., Hodges, K.V., Vermeesch, P., Stelten, M.E.,
  Mercer, C.M., et al. (2021). Interpreting and reporting ⁴⁰Ar/³⁹Ar
  geochronologic data. GSA Bulletin 133 (3–4), 461–487, Table 5.

Primary sources per mineral (as cited in that table): Cassata et al. (2011),
Blereau et al. (2019), Harrison (1981), Harrison et al. (2009), Giletti
(1974), Cassata & Renne (2013), Grove & Harrison (1996), Wartho et al.
(1999), Foland (1994). Their nominal T_cb assume a = 100 µm and
dT/dt = 10 °C/Myr, rounded to the nearest 10 °C.
"""

import math

# ── physical constants ──────────────────────────────────────────────────────
R_GAS = 8.314462618            # J mol⁻¹ K⁻¹
KJ_TO_J = 1000.0
KCAL_TO_KJ = 4.184             # thermochemical calorie
SEC_PER_MYR = 1.0e6 * 365.25 * 24 * 3600   # seconds in 1 Myr

# Dodson (1973) geometry factor A (slow-cooling limit).
GEOMETRY_FACTORS = {'sphere': 55.0, 'cylinder': 27.0, 'plane sheet': 8.7}

# Schaen et al. (2021) Table 5 — E in kJ/mol, D0 in m²/s (units as published).
# 'tcb' is the nominal bulk closure temperature (°C) they report for
# a = 100 µm, dT/dt = 10 °C/Myr (rounded to nearest 10 °C); it is used by the
# self-test below, not by the calculator itself.
MINERAL_DB = [
    {'name': 'Clinopyroxene',
     'E': 379.0, 'D0': 1.4e-4, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 730, 'ref': 'Cassata et al. (2011)'},
    {'name': 'Orthopyroxene',
     'E': 370.0, 'D0': 5.7e-2, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 600, 'ref': 'Cassata et al. (2011)'},
    {'name': 'Osumilite',
     'E': 461.0, 'D0': 8.3e4, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 580, 'ref': 'Blereau et al. (2019)'},
    {'name': 'Hornblende',
     'E': 268.0, 'D0': 2.4e-6, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 510, 'ref': 'Harrison (1981)'},
    {'name': 'Muscovite',
     'E': 264.0, 'D0': 2.0e-3, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 390, 'ref': 'Harrison et al. (2009)'},
    {'name': 'Phlogopite',
     'E': 242.0, 'D0': 7.5e-5, 'geometry': 'cylinder', 'radius': 100.0,
     'tcb': 390, 'ref': 'Giletti (1974)'},
    # Anorthoclase in Cassata & Renne (2013) is strongly non-Arrhenian
    # (kinked Arrhenius array); the tabulated E/D0 describe the high-T
    # segment and single-domain Dodson with them gives ~750 °C, NOT the
    # nominal 380 °C listed in Table 5. Kept as published, flagged so the
    # self-test and the UI treat it as an exception.
    {'name': 'K-feldspar (anorthoclase)',
     'E': 400.0, 'D0': 4.4e-3, 'geometry': 'plane sheet', 'radius': 100.0,
     'tcb': 380, 'nonarrhenian': True, 'ref': 'Cassata & Renne (2013)'},
    {'name': 'K-feldspar (sanidine)',
     'E': 220.0, 'D0': 4.5e-5, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 330, 'ref': 'Cassata & Renne (2013)'},
    {'name': 'Biotite (X_phl = 0.29)',
     'E': 211.0, 'D0': 4.0e-5, 'geometry': 'cylinder', 'radius': 100.0,
     'tcb': 320, 'ref': 'Grove & Harrison (1996)'},
    {'name': 'Plagioclase (albite/oligoclase)',
     'E': 209.0, 'D0': 3.1e-5, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 310, 'ref': 'Cassata & Renne (2013)'},
    {'name': 'K-feldspar (cryptoperthite)',
     'E': 197.0, 'D0': 3.7e-6, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 300, 'ref': 'Wartho et al. (1999)'},
    {'name': 'Plagioclase (anorthite)',
     'E': 196.0, 'D0': 2.2e-6, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 300, 'ref': 'Cassata & Renne (2013)'},
    {'name': 'Biotite (X_phl = 0.46)',
     'E': 186.0, 'D0': 1.5e-6, 'geometry': 'cylinder', 'radius': 100.0,
     'tcb': 290, 'ref': 'Grove & Harrison (1996)'},
    {'name': 'K-feldspar (orthoclase)',
     'E': 183.0, 'D0': 9.8e-7, 'geometry': 'sphere', 'radius': 100.0,
     'tcb': 280, 'ref': 'Foland (1994)'},
]

TABLE5_CITATION = ('Schaen et al. (2021) GSA Bulletin 133, 461–487, Table 5')

# Muscovite is the default preset (the phase pyADR reduces most often).
DEFAULT_PRESET = next(i for i, m in enumerate(MINERAL_DB)
                      if m['name'] == 'Muscovite')

# Nominal closure temperatures for non-⁴⁰Ar/³⁹Ar thermochronometers, offered
# in the cooling-history tab so a T–t path can mix Ar/Ar mineral ages with
# fission-track, (U-Th)/He and U-Pb ages (as in published cooling curves).
# These systems are NOT volume-diffusion-modelled here — 'tc' is the widely
# cited nominal bulk closure temperature; 'half' is a rough ± band half-width
# for the plot only. Compilation: Reiners & Brandon (2006) Annu. Rev. Earth
# Planet. Sci. 34, 419–466 and references therein.
OTHER_CHRONOMETERS = [
    {'name': 'Zircon U–Pb',            'method': 'U–Pb',        'tc': 900.0, 'half': 0,  'ref': 'Pb in zircon, effectively crystallization'},
    {'name': 'Monazite U–Th–Pb',       'method': 'U–Th–Pb',     'tc': 700.0, 'half': 25, 'ref': 'Reiners & Brandon (2006)'},
    {'name': 'Titanite U–Pb',          'method': 'U–Pb',        'tc': 600.0, 'half': 30, 'ref': 'Cherniak (1993)'},
    {'name': 'Rutile U–Pb',            'method': 'U–Pb',        'tc': 600.0, 'half': 40, 'ref': 'Cherniak (2000)'},
    {'name': 'Muscovite Rb–Sr',        'method': 'Rb–Sr',       'tc': 500.0, 'half': 30, 'ref': 'Jäger (1979)'},
    {'name': 'Biotite Rb–Sr',          'method': 'Rb–Sr',       'tc': 300.0, 'half': 25, 'ref': 'Jäger (1979)'},
    {'name': 'Zircon fission track',   'method': 'fission track','tc': 240.0, 'half': 20, 'ref': 'Reiners & Brandon (2006)'},
    {'name': 'Zircon (U-Th)/He',       'method': '(U-Th)/He',   'tc': 180.0, 'half': 20, 'ref': 'Reiners & Brandon (2006)'},
    {'name': 'Apatite fission track',  'method': 'fission track','tc': 110.0, 'half': 15, 'ref': 'Reiners & Brandon (2006)'},
    {'name': 'Apatite (U-Th)/He',      'method': '(U-Th)/He',   'tc': 70.0,  'half': 15, 'ref': 'Reiners & Brandon (2006)'},
]

# Method label for the Ar/Ar minerals in MINERAL_DB.
ARAR_METHOD = '⁴⁰Ar/³⁹Ar'

# Plot band half-width (°C) for Ar/Ar minerals (which have no tabulated range).
DEFAULT_BAND_HALF = 12.0

# Default cycle of Tᴄ-band colours (editable per row in the cooling-history
# table). Muted so the data points/path stay readable on top.
BAND_PALETTE = ['#d7ead1', '#f6dbe6', '#fce3cf', '#d6e8f7',
                '#e8dcf2', '#d9efe9', '#f2ead0', '#e3e3e3']

# Short labels for the Tᴄ reference bands on the plot (mineral abbreviations
# after Whitney & Evans 2010; FT/He systems by their standard acronyms).
ABBR = {
    'Clinopyroxene': 'Cpx', 'Orthopyroxene': 'Opx', 'Osumilite': 'Osm',
    'Hornblende': 'Hbl', 'Muscovite': 'Ms', 'Phlogopite': 'Phl',
    'K-feldspar (anorthoclase)': 'Kfs-anor',
    'K-feldspar (sanidine)': 'Kfs-san',
    'K-feldspar (cryptoperthite)': 'Kfs-cp',
    'K-feldspar (orthoclase)': 'Kfs-or',
    'Biotite (X_phl = 0.29)': 'Bt(29)', 'Biotite (X_phl = 0.46)': 'Bt(46)',
    'Plagioclase (albite/oligoclase)': 'Pl-ab', 'Plagioclase (anorthite)': 'Pl-an',
    'Zircon U–Pb': 'Zrn U–Pb', 'Monazite U–Th–Pb': 'Mnz',
    'Titanite U–Pb': 'Ttn', 'Rutile U–Pb': 'Rt',
    'Muscovite Rb–Sr': 'Ms Rb–Sr', 'Biotite Rb–Sr': 'Bt Rb–Sr',
    'Zircon fission track': 'ZFT', 'Zircon (U-Th)/He': 'ZHe',
    'Apatite fission track': 'AFT', 'Apatite (U-Th)/He': 'AHe',
}


def closure_temperature(E_kJ, D0_m2s, radius_um, geometry,
                        cooling_C_per_Myr, max_iter=200, tol=1e-9):
    """Dodson (1973) closure temperature, in °C.

    Units follow Schaen et al. (2021) Table 5: E in kJ/mol, D0 in m²/s,
    radius in µm, cooling rate in °C/Myr.

    Solves Tc = E/(R·ln(A·τ·D0/a²)) with τ = R·Tc²/(E·|dT/dt|) by fixed-point
    iteration. Returns float('nan') if inputs are non-physical (non-positive
    parameters, or the log argument falls to ≤1, which means the grain never
    closes at that cooling rate / size).
    """
    if (E_kJ <= 0 or D0_m2s <= 0 or radius_um <= 0
            or cooling_C_per_Myr <= 0 or geometry not in GEOMETRY_FACTORS):
        return float('nan')

    E = E_kJ * KJ_TO_J             # J/mol
    a = radius_um * 1.0e-6         # µm → m
    A = GEOMETRY_FACTORS[geometry]
    dTdt = cooling_C_per_Myr / SEC_PER_MYR   # K/s (cooling magnitude)

    T = 600.0                       # K, initial guess
    for _ in range(max_iter):
        tau = R_GAS * T * T / (E * dTdt)
        arg = A * tau * D0_m2s / (a * a)
        if arg <= 1.0:              # ln ≤ 0 → no closure / non-physical
            return float('nan')
        T_new = E / (R_GAS * math.log(arg))
        if abs(T_new - T) < tol:
            T = T_new
            break
        T = T_new
    if not math.isfinite(T) or T <= 0:
        return float('nan')
    return T - 273.15               # K → °C


def cooling_segments(points):
    """Segment-by-segment cooling rates for a T–t (cooling history) path.

    `points` is an iterable of (age_Ma, temp_C). Points are sorted oldest →
    youngest (descending age); between each adjacent pair the cooling rate is

        rate = (T_older - T_younger) / (age_older - age_younger)   [°C/Myr]

    which is positive for a monotonically cooling sample (older, deeper
    chronometers closed hotter). Returns a list of dicts, one per segment:
    {age0, t0, age1, t1, rate}. A segment with zero/negative Δt (two dates
    equal or out of order) gets rate = nan.
    """
    pts = sorted(points, key=lambda p: p[0], reverse=True)   # old → young
    segs = []
    for (a0, t0), (a1, t1) in zip(pts, pts[1:]):
        dt = a0 - a1
        rate = (t0 - t1) / dt if dt > 0 else float('nan')
        segs.append({'age0': a0, 't0': t0, 'age1': a1, 't1': t1, 'rate': rate})
    return segs


# =============================================================================
#  Qt dialog (imported lazily; math above works without PyQt5)
# =============================================================================
def _build_dialog_class():
    from PyQt5 import QtWidgets, QtCore

    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigCanvas
    from matplotlib.figure import Figure

    # cooling rates (°C/Myr) shown in the summary table
    TABLE_RATES = [1, 3, 10, 30, 100, 300]

    class ClosureTempDialog(QtWidgets.QDialog):
        """Interactive Dodson (1973) closure-temperature calculator."""

        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle('Closure Temperature — Dodson (1973)')
            self.setMinimumSize(1050, 680)
            self._building = True
            self._build()
            self._building = False
            self._load_preset(DEFAULT_PRESET)

        # ── layout ──────────────────────────────────────────────────────────
        def _build(self):
            # v3.8.97: two tabs — the single-mineral calculator and a
            # multi-mineral cooling-history (T–t) plot.
            outer = QtWidgets.QVBoxLayout(self)
            outer.setContentsMargins(0, 0, 0, 0)
            self.tabs = QtWidgets.QTabWidget()
            outer.addWidget(self.tabs)

            single = QtWidgets.QWidget()
            root = QtWidgets.QHBoxLayout(single)
            root.setContentsMargins(14, 14, 14, 14)
            root.setSpacing(14)

            # LEFT: inputs + result + table
            left = QtWidgets.QVBoxLayout()
            left.setSpacing(10)
            root.addLayout(left, 0)

            title = QtWidgets.QLabel('Mineral closure temperature')
            title.setStyleSheet('font-size:16px;font-weight:bold;color:#1a5fb4;')
            left.addWidget(title)

            # preset picker
            frm = QtWidgets.QFormLayout()
            frm.setLabelAlignment(QtCore.Qt.AlignRight)
            frm.setSpacing(7)

            self.presetCombo = QtWidgets.QComboBox()
            for m in MINERAL_DB:
                self.presetCombo.addItem(m['name'])
            self.presetCombo.addItem('Custom…')
            self.presetCombo.currentIndexChanged.connect(self._on_preset)
            frm.addRow('Mineral preset', self.presetCombo)

            # v3.8.96: E unit selectable (kJ/mol or kcal/mol); DB stores kJ.
            self.eEdit = self._num_edit()
            self.eUnitCombo = QtWidgets.QComboBox()
            self.eUnitCombo.addItems(['kJ/mol', 'kcal/mol'])
            self.eUnitCombo.currentIndexChanged.connect(self._on_e_unit)
            eRow = QtWidgets.QHBoxLayout()
            eRow.setSpacing(4)
            eRow.addWidget(self.eEdit)
            eRow.addWidget(self.eUnitCombo)
            frm.addRow('Activation energy E', eRow)

            self.d0Edit = self._num_edit()
            frm.addRow('Frequency factor D₀ (m²/s)', self.d0Edit)

            self.geomCombo = QtWidgets.QComboBox()
            self.geomCombo.addItems(list(GEOMETRY_FACTORS.keys()))
            self.geomCombo.currentIndexChanged.connect(self._on_manual_edit)
            frm.addRow('Diffusion geometry', self.geomCombo)

            self.radiusEdit = self._num_edit()
            frm.addRow('Effective radius a (µm)', self.radiusEdit)

            self.rateEdit = self._num_edit()
            frm.addRow('Cooling rate (°C/Myr)', self.rateEdit)

            left.addLayout(frm)

            # result card
            self.resultLbl = QtWidgets.QLabel('—')
            self.resultLbl.setAlignment(QtCore.Qt.AlignCenter)
            self.resultLbl.setStyleSheet(
                'font-size:30px;font-weight:bold;color:#1a5fb4;'
                'background:#d6e8f7;border:1px solid #a8cbe8;'
                'border-radius:6px;padding:14px;')
            left.addWidget(self.resultLbl)

            self.formulaLbl = QtWidgets.QLabel(
                'Tᴄ = E / [ R · ln( A · τ · D₀ / a² ) ],   '
                'τ = R·Tᴄ² / (E · dT/dt)')
            self.formulaLbl.setStyleSheet('font-size:11px;color:#666;')
            self.formulaLbl.setAlignment(QtCore.Qt.AlignCenter)
            left.addWidget(self.formulaLbl)

            # summary table across cooling rates
            self.table = QtWidgets.QTableWidget(len(TABLE_RATES), 2)
            self.table.setHorizontalHeaderLabels(['Cooling °C/Myr', 'Tᴄ (°C)'])
            self.table.verticalHeader().setVisible(False)
            self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
            self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
            hh = self.table.horizontalHeader()
            hh.setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
            # show all rows, no scrollbar: fix row height and size the table to
            # exactly header + N rows.
            _rowh = 30
            self.table.verticalHeader().setDefaultSectionSize(_rowh)
            hh.setFixedHeight(28)
            self.table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.table.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.table.setFixedHeight(28 + _rowh * len(TABLE_RATES) + 4)
            for r, rate in enumerate(TABLE_RATES):
                it = QtWidgets.QTableWidgetItem(str(rate))
                it.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(r, 0, it)
            left.addWidget(self.table)

            left.addStretch(1)

            self.refLbl = QtWidgets.QLabel('')
            self.refLbl.setWordWrap(True)
            self.refLbl.setStyleSheet('font-size:10px;color:#888;')
            left.addWidget(self.refLbl)

            # RIGHT: plot Tc vs cooling rate
            right = QtWidgets.QVBoxLayout()
            right.setSpacing(6)
            root.addLayout(right, 1)

            self.fig = Figure(figsize=(5.2, 4.6), dpi=100)
            self.fig.patch.set_facecolor('white')
            self.ax = self.fig.add_subplot(111)
            self.canvas = FigCanvas(self.fig)
            right.addWidget(self.canvas, 1)

            note = QtWidgets.QLabel(
                'Curve: Tᴄ vs cooling rate for the current parameters; '
                'the dot marks your chosen rate.\n'
                'Diffusion parameters: ' + TABLE5_CITATION + ' (their nominal '
                'T_cb assume a = 100 µm, dT/dt = 10 °C/Myr).\n'
                'K-feldspar has multiple diffusion domains (Lovera et al. 1989); '
                'a single-domain Tᴄ is only a rough bulk estimate.')
            note.setWordWrap(True)
            note.setStyleSheet('font-size:10px;color:#888;')
            right.addWidget(note)

            btnRow = QtWidgets.QHBoxLayout()
            addChBtn = QtWidgets.QPushButton('Add to cooling history →')
            addChBtn.setToolTip('Send the current mineral + Tᴄ to the '
                                'Cooling history (T–t) tab as a new row')
            addChBtn.clicked.connect(self._add_single_to_cooling)
            btnRow.addWidget(addChBtn)
            btnRow.addStretch(1)
            closeBtn = QtWidgets.QPushButton('Close')
            closeBtn.setMinimumWidth(90)
            closeBtn.clicked.connect(self.accept)
            btnRow.addWidget(closeBtn)
            right.addLayout(btnRow)

            for e in (self.eEdit, self.d0Edit, self.radiusEdit, self.rateEdit):
                e.textChanged.connect(self._on_manual_edit)

            self.tabs.addTab(single, 'Single mineral')
            self.tabs.addTab(self._build_cooling_tab(), 'Cooling history (T–t)')

        # ── cooling-history (T–t) tab ───────────────────────────────────────
        def _build_cooling_tab(self):
            w = QtWidgets.QWidget()
            root = QtWidgets.QHBoxLayout(w)
            root.setContentsMargins(14, 14, 14, 14)
            root.setSpacing(14)

            left = QtWidgets.QVBoxLayout()
            left.setSpacing(8)
            lw = QtWidgets.QWidget()
            lw.setLayout(left)
            lw.setFixedWidth(540)
            root.addWidget(lw, 0)

            title = QtWidgets.QLabel('Cooling history (T–t path)')
            title.setStyleSheet('font-size:16px;font-weight:bold;color:#1a5fb4;')
            left.addWidget(title)

            desc = QtWidgets.QLabel(
                'Enter each dated chronometer: pick a mineral (its Dodson Tᴄ '
                'is filled from the assumed cooling rate below, and stays '
                'editable) and type the age. The plot connects (age, Tᴄ) into '
                'a cooling path and labels each segment’s cooling rate.')
            desc.setWordWrap(True)
            desc.setStyleSheet('font-size:10px;color:#666;')
            left.addWidget(desc)

            rrow = QtWidgets.QHBoxLayout()
            rrow.addWidget(QtWidgets.QLabel('Tᴄ assumed cooling rate (°C/Myr):'))
            self.chRateEdit = QtWidgets.QLineEdit('10')
            self.chRateEdit.setMaximumWidth(70)
            self.chRateEdit.textChanged.connect(self._ch_refill_tc)
            rrow.addWidget(self.chRateEdit)
            rrow.addStretch(1)
            left.addLayout(rrow)

            self.chTable = QtWidgets.QTableWidget(0, 8)
            self.chTable.setHorizontalHeaderLabels(
                ['Show', 'Mineral', 'Age (Ma)', '± (Ma)', 'Tᴄ (°C)', '± (°C)',
                 'Method', 'Band'])
            self.chTable.verticalHeader().setVisible(False)
            chh = self.chTable.horizontalHeader()
            chh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            chh.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            for c in range(2, 8):
                chh.setSectionResizeMode(c, QtWidgets.QHeaderView.ResizeToContents)
            self._ch_updating = False
            self.chTable.itemChanged.connect(self._ch_on_item_changed)
            left.addWidget(self.chTable, 1)

            brow = QtWidgets.QHBoxLayout()
            addBtn = QtWidgets.QPushButton('Add row')
            addBtn.clicked.connect(lambda: self._ch_add_row())
            rmBtn = QtWidgets.QPushButton('Remove row')
            rmBtn.clicked.connect(self._ch_remove_row)
            upBtn = QtWidgets.QPushButton('↑')
            upBtn.setToolTip('Move selected mineral up')
            upBtn.setMaximumWidth(34)
            upBtn.clicked.connect(lambda: self._ch_move_row(-1))
            downBtn = QtWidgets.QPushButton('↓')
            downBtn.setToolTip('Move selected mineral down')
            downBtn.setMaximumWidth(34)
            downBtn.clicked.connect(lambda: self._ch_move_row(+1))
            plotBtn = QtWidgets.QPushButton('Plot')
            plotBtn.clicked.connect(self._ch_plot)
            saveBtn = QtWidgets.QPushButton('Save PNG')
            saveBtn.setToolTip('Save the cooling-history figure (PNG / PDF / SVG)')
            saveBtn.clicked.connect(self._ch_save)
            for b in (addBtn, rmBtn, upBtn, downBtn, plotBtn, saveBtn):
                brow.addWidget(b)
            brow.addStretch(1)
            left.addLayout(brow)

            self.chBands = QtWidgets.QCheckBox(
                'Show Tᴄ reference bands for the chronometers used')
            self.chBands.setChecked(True)
            self.chBands.stateChanged.connect(self._ch_plot)
            left.addWidget(self.chBands)

            # RIGHT: T–t plot
            right = QtWidgets.QVBoxLayout()
            right.setSpacing(6)
            root.addLayout(right, 1)

            self.chFig = Figure(figsize=(5.2, 4.6), dpi=100)
            self.chFig.patch.set_facecolor('white')
            self.chAx = self.chFig.add_subplot(111)
            self.chCanvas = FigCanvas(self.chFig)
            right.addWidget(self.chCanvas, 1)

            self.chInfo = QtWidgets.QLabel('')
            self.chInfo.setWordWrap(True)
            self.chInfo.setStyleSheet('font-size:10px;color:#666;')
            right.addWidget(self.chInfo)

            # seed a worked example: Ar/Ar minerals + an apatite fission-track
            # age (mid-crustal rock cooling through to the near-surface).
            self._ch_add_row(preset_name='Hornblende', age='40', age_sig='1')
            self._ch_add_row(preset_name='Muscovite', age='34', age_sig='0.8')
            self._ch_add_row(preset_name='Biotite (X_phl = 0.29)',
                             age='30', age_sig='0.7')
            self._ch_add_row(preset_name='K-feldspar (orthoclase)',
                             age='26', age_sig='0.6')
            self._ch_add_row(preset_name='Apatite fission track',
                             age='12', age_sig='1.5')
            self._ch_plot()
            return w

        def _ch_tc_for_name(self, name):
            """Nominal Tᴄ (°C) for a chronometer by name, and whether it is
            cooling-rate-dependent. Ar/Ar minerals → Dodson Tᴄ at the tab's
            assumed rate (a = 100 µm); other systems → tabulated nominal Tᴄ.
            Returns (tc_or_None, rate_dependent)."""
            for m in MINERAL_DB:
                if m['name'] == name:
                    rate = self._read(self.chRateEdit)
                    if rate is None:
                        rate = 10.0
                    return closure_temperature(m['E'], m['D0'], 100.0,
                                               m['geometry'], rate), True
            for o in OTHER_CHRONOMETERS:
                if o['name'] == name:
                    return o['tc'], False
            return None, False

        def _ch_band_half(self, name):
            """± band half-width (°C) for the Tᴄ reference band of `name`."""
            for o in OTHER_CHRONOMETERS:
                if o['name'] == name:
                    return o['half']
            return DEFAULT_BAND_HALF

        def _ch_method_for_name(self, name):
            """Dating method label for a chronometer name (Ar/Ar minerals →
            ⁴⁰Ar/³⁹Ar; other systems → their own method; else '')."""
            for m in MINERAL_DB:
                if m['name'] == name:
                    return ARAR_METHOD
            for o in OTHER_CHRONOMETERS:
                if o['name'] == name:
                    return o.get('method', '')
            return ''

        def _ch_add_row(self, preset_name=None, age='', age_sig='',
                        tc='', tc_sig=''):
            from PyQt5 import QtWidgets as _Q
            self._ch_updating = True
            r = self.chTable.rowCount()
            self.chTable.insertRow(r)

            combo = _Q.QComboBox()
            for m in MINERAL_DB:
                combo.addItem(m['name'])
            combo.insertSeparator(combo.count())        # Ar/Ar │ other systems
            for o in OTHER_CHRONOMETERS:
                combo.addItem(o['name'])
            combo.addItem('Custom…')
            if preset_name is not None:
                i = combo.findText(preset_name)
                if i >= 0:
                    combo.setCurrentIndex(i)
            else:
                combo.setCurrentIndex(combo.count() - 1)   # Custom
            combo.currentIndexChanged.connect(
                lambda _i, row=combo: self._ch_on_mineral_changed(row))
            # col 0 = Show checkbox (whether this chronometer is drawn)
            self.chTable.setCellWidget(r, 0, self._ch_make_show_chk())
            self.chTable.setCellWidget(r, 1, combo)

            # auto-fill Tc from the chosen chronometer unless caller supplied one
            if not tc:
                t, _rd = self._ch_tc_for_name(combo.currentText())
                if t is not None and not math.isnan(t):
                    tc = f'{t:.0f}'

            for c, val in ((2, age), (3, age_sig), (4, tc), (5, tc_sig)):
                it = _Q.QTableWidgetItem(str(val))
                it.setTextAlignment(QtCore.Qt.AlignCenter)
                self.chTable.setItem(r, c, it)

            # Method (col 6): read-only, auto-filled from the chosen chronometer
            mit = _Q.QTableWidgetItem(self._ch_method_for_name(combo.currentText()))
            mit.setTextAlignment(QtCore.Qt.AlignCenter)
            mit.setFlags(mit.flags() & ~QtCore.Qt.ItemIsEditable)
            self.chTable.setItem(r, 6, mit)

            # per-row Tᴄ-band colour (col 7, click to change)
            self.chTable.setCellWidget(
                r, 7, self._ch_make_color_btn(BAND_PALETTE[r % len(BAND_PALETTE)]))
            self._ch_updating = False

        def _ch_make_show_chk(self):
            from PyQt5 import QtWidgets as _Q
            w = _Q.QWidget()
            lay = _Q.QHBoxLayout(w)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setAlignment(QtCore.Qt.AlignCenter)
            chk = _Q.QCheckBox()
            chk.setChecked(True)
            chk.setToolTip('Show this chronometer on the T–t plot')
            chk.stateChanged.connect(lambda _s: self._ch_plot())
            lay.addWidget(chk)
            w._chk = chk
            return w

        def _ch_make_color_btn(self, hexcol):
            from PyQt5 import QtWidgets as _Q
            b = _Q.QPushButton()
            b.setFixedSize(30, 20)
            b._color = hexcol
            b.setStyleSheet(f'background:{hexcol};border:1px solid #888;')
            b.setToolTip('Click to choose this chronometer’s Tᴄ band colour')
            b.clicked.connect(lambda _=None, bb=b: self._ch_pick_color(bb))
            return b

        def _ch_pick_color(self, btn):
            from PyQt5 import QtWidgets as _Q, QtGui as _G
            c = _Q.QColorDialog.getColor(_G.QColor(btn._color), self,
                                         'Tᴄ band colour')
            if c.isValid():
                btn._color = c.name()
                btn.setStyleSheet(f'background:{c.name()};border:1px solid #888;')
                self._ch_plot()

        def _ch_row_of_combo(self, combo):
            for r in range(self.chTable.rowCount()):
                if self.chTable.cellWidget(r, 1) is combo:
                    return r
            return -1

        def _ch_on_mineral_changed(self, combo):
            r = self._ch_row_of_combo(combo)
            if r < 0:
                return
            t, _rd = self._ch_tc_for_name(combo.currentText())
            if t is not None and not math.isnan(t):
                self._ch_set_cell(r, 4, f'{t:.0f}')
            self._ch_set_cell(r, 6, self._ch_method_for_name(combo.currentText()))
            self._ch_plot()

        def _ch_set_cell(self, r, c, text):
            from PyQt5 import QtWidgets as _Q
            self._ch_updating = True
            it = self.chTable.item(r, c)
            if it is None:
                it = _Q.QTableWidgetItem()
                it.setTextAlignment(QtCore.Qt.AlignCenter)
                self.chTable.setItem(r, c, it)
            it.setText(text)
            self._ch_updating = False

        def _ch_on_item_changed(self, _item):
            if self._ch_updating:
                return
            self._ch_plot()

        def _ch_refill_tc(self):
            # Assumed-cooling-rate changed: refill Tᴄ only on rate-dependent
            # (Ar/Ar) rows. Fixed-Tᴄ systems (FT / He / U-Pb) and Custom rows
            # keep their value.
            if self._ch_updating:
                return
            for r in range(self.chTable.rowCount()):
                combo = self.chTable.cellWidget(r, 0)
                if combo is None:
                    continue
                t, rate_dep = self._ch_tc_for_name(combo.currentText())
                if rate_dep and t is not None and not math.isnan(t):
                    self._ch_set_cell(r, 3, f'{t:.0f}')
            self._ch_plot()

        def _ch_remove_row(self):
            r = self.chTable.currentRow()
            if r < 0:
                r = self.chTable.rowCount() - 1
            if r >= 0:
                self.chTable.removeRow(r)
                self._ch_plot()

        def _ch_move_row(self, delta):
            """Move the selected row up (delta=-1) or down (+1). Reorders the
            table only; the cooling path is drawn sorted by age regardless, so
            this is for tidying the input list, not the plot order."""
            r = self.chTable.currentRow()
            if r < 0:
                return
            t = r + delta
            if t < 0 or t >= self.chTable.rowCount():
                return
            self._ch_swap_rows(r, t)
            col = self.chTable.currentColumn()
            self.chTable.setCurrentCell(t, col if col >= 1 else 1)
            self._ch_plot()

        def _ch_swap_rows(self, a, b):
            from PyQt5 import QtWidgets as _Q
            self._ch_updating = True
            # mineral combos: swap the selection without firing the change
            # handler (which would recompute/overwrite an edited Tᴄ).
            ca = self.chTable.cellWidget(a, 1)
            cb = self.chTable.cellWidget(b, 1)
            ia, ib = ca.currentIndex(), cb.currentIndex()
            ca.blockSignals(True); cb.blockSignals(True)
            ca.setCurrentIndex(ib); cb.setCurrentIndex(ia)
            ca.blockSignals(False); cb.blockSignals(False)
            # text cells (Age / ± / Tᴄ / ± / Method): swap the raw text
            for c in range(2, 7):
                ta = self.chTable.item(a, c)
                tb = self.chTable.item(b, c)
                sa = ta.text() if ta is not None else ''
                sb = tb.text() if tb is not None else ''
                for r, s in ((a, sb), (b, sa)):
                    it = self.chTable.item(r, c)
                    if it is None:
                        it = _Q.QTableWidgetItem()
                        it.setTextAlignment(QtCore.Qt.AlignCenter)
                        self.chTable.setItem(r, c, it)
                    it.setText(s)
            # band colour swatches (col 7): swap their colour value in place
            ba = self.chTable.cellWidget(a, 7)
            bb = self.chTable.cellWidget(b, 7)
            if ba is not None and bb is not None:
                ba._color, bb._color = bb._color, ba._color
                ba.setStyleSheet(f'background:{ba._color};border:1px solid #888;')
                bb.setStyleSheet(f'background:{bb._color};border:1px solid #888;')
            # Show checkboxes (col 0): swap their checked state
            sa = self.chTable.cellWidget(a, 0)
            sb = self.chTable.cellWidget(b, 0)
            if sa is not None and sb is not None:
                va, vb = sa._chk.isChecked(), sb._chk.isChecked()
                sa._chk.blockSignals(True); sb._chk.blockSignals(True)
                sa._chk.setChecked(vb); sb._chk.setChecked(va)
                sa._chk.blockSignals(False); sb._chk.blockSignals(False)
            self._ch_updating = False

        def _ch_read_rows(self, only_shown=False):
            rows = []
            for r in range(self.chTable.rowCount()):
                schk = self.chTable.cellWidget(r, 0)
                show = schk._chk.isChecked() if schk is not None else True
                if only_shown and not show:
                    continue
                combo = self.chTable.cellWidget(r, 1)
                name = combo.currentText() if combo is not None else ''
                age = self._ch_cell_float(r, 2)
                asig = self._ch_cell_float(r, 3)
                tc = self._ch_cell_float(r, 4)
                tsig = self._ch_cell_float(r, 5)
                mit = self.chTable.item(r, 6)
                method = mit.text() if mit is not None else ''
                cbtn = self.chTable.cellWidget(r, 7)
                color = getattr(cbtn, '_color', None) if cbtn else None
                if age is None or tc is None:
                    continue
                rows.append({'name': name, 'age': age, 'age_sig': asig,
                             'tc': tc, 'tc_sig': tsig, 'method': method,
                             'color': color, 'show': show})
            return rows

        def _ch_cell_float(self, r, c):
            it = self.chTable.item(r, c)
            if it is None:
                return None
            try:
                return float(it.text())
            except (ValueError, TypeError):
                return None

        def _ch_plot(self):
            self.chAx.clear()
            rows = self._ch_read_rows(only_shown=True)
            if len(rows) == 0:
                self.chAx.set_xlabel('Age (Ma)', fontsize=10)
                self.chAx.set_ylabel('Temperature (°C)', fontsize=10)
                self.chAx.grid(True, ls=':', alpha=0.4)
                self.chInfo.setText('Add at least one chronometer '
                                    '(age + Tᴄ) to draw a cooling path.')
                self.chFig.subplots_adjust(left=0.12, right=0.80,
                                           top=0.96, bottom=0.12)
                self.chCanvas.draw_idle()
                return

            ages = [r['age'] for r in rows]
            tcs = [r['tc'] for r in rows]
            xerr = [r['age_sig'] if r['age_sig'] is not None else 0.0
                    for r in rows]
            yerr = [r['tc_sig'] if r['tc_sig'] is not None else 0.0
                    for r in rows]

            # Tᴄ reference bands (one per distinct chronometer in the table),
            # drawn behind the data — echoes the horizontal Tᴄ bands used in
            # published T–t paths. The band half-width follows the row's own
            # ± (°C) when given, so the band and the Tᴄ error bar match; it
            # falls back to the tabulated nominal half-width otherwise. The
            # band colour is the row's editable colour swatch.
            if self.chBands.isChecked():
                seen = {}
                for r in rows:
                    if r['name'] in seen:
                        continue
                    if r['tc_sig'] is not None and r['tc_sig'] > 0:
                        half = r['tc_sig']
                    else:
                        half = self._ch_band_half(r['name'])
                    seen[r['name']] = (r['tc'], half, r['color'])
                for i, (nm, (tcv, half, color)) in enumerate(seen.items()):
                    col = color or BAND_PALETTE[i % len(BAND_PALETTE)]
                    if half > 0:
                        self.chAx.axhspan(tcv - half, tcv + half,
                                          color=col, alpha=0.75, zorder=0)
                    self.chAx.axhline(tcv, color='#bbbbbb', lw=0.6, zorder=0)
                    self.chAx.annotate(
                        ABBR.get(nm, nm.split(' (')[0]) + ' Tᴄ', xy=(1.0, tcv),
                        xycoords=self.chAx.get_yaxis_transform(),
                        xytext=(4, 0), textcoords='offset points',
                        va='center', ha='left', fontsize=7, color='#555',
                        annotation_clip=False)

            # cooling path: connect points sorted old → young
            order = sorted(range(len(rows)), key=lambda i: ages[i], reverse=True)
            self.chAx.plot([ages[i] for i in order], [tcs[i] for i in order],
                           '-', color='#1a5fb4', lw=1.6, zorder=2)
            self.chAx.errorbar(ages, tcs, xerr=xerr, yerr=yerr, fmt='o',
                               ms=7, color='#b41a1a', ecolor='#b41a1a',
                               elinewidth=1, capsize=3, zorder=3)
            # (no per-point labels — the chronometers are identified by the
            # Tᴄ reference bands on the right and the Method column.)

            # segment cooling rates
            segs = cooling_segments(list(zip(ages, tcs)))
            for s in segs:
                if math.isnan(s['rate']):
                    continue
                xm = 0.5 * (s['age0'] + s['age1'])
                ym = 0.5 * (s['t0'] + s['t1'])
                self.chAx.annotate(f"{s['rate']:.0f} °C/Myr", (xm, ym),
                                   textcoords='offset points', xytext=(6, -12),
                                   fontsize=8, color='#1a5fb4')

            self.chAx.set_xlabel('Age (Ma)', fontsize=10)
            self.chAx.set_ylabel('Temperature (°C)', fontsize=10)
            self.chAx.grid(True, ls=':', alpha=0.4)
            # y-range driven by the data points (not the bands), with padding
            lo = min(t - e for t, e in zip(tcs, yerr))
            hi = max(t + e for t, e in zip(tcs, yerr))
            pad = max(20.0, 0.08 * (hi - lo))
            self.chAx.set_ylim(lo - pad, hi + pad)
            if max(ages) > min(ages):
                self.chAx.invert_xaxis()   # older left → younger (present) right
            # leave room on the right for the Tᴄ band labels
            self.chFig.subplots_adjust(left=0.12, right=0.80,
                                       top=0.96, bottom=0.12)
            self.chCanvas.draw_idle()

            parts = []
            for s in segs:
                if math.isnan(s['rate']):
                    continue
                parts.append(f"{s['age0']:g}→{s['age1']:g} Ma: "
                             f"{s['rate']:.1f} °C/Myr")
            self.chInfo.setText(('Segment cooling rates — ' + '  |  '.join(parts))
                                if parts else 'Need ≥2 chronometers for a rate.')

        def _ch_save(self):
            from PyQt5 import QtWidgets as _Q
            if not self._ch_read_rows(only_shown=True):
                _Q.QMessageBox.information(
                    self, 'Save figure',
                    'Nothing to save yet — tick at least one chronometer and '
                    'Plot first.')
                return
            path, _f = _Q.QFileDialog.getSaveFileName(
                self, 'Save cooling-history figure', 'cooling_history.png',
                'PNG image (*.png);;PDF document (*.pdf);;SVG image (*.svg)')
            if not path:
                return
            try:
                self.chFig.savefig(path, dpi=300, bbox_inches='tight',
                                   facecolor='white')
            except Exception as e:
                _Q.QMessageBox.warning(
                    self, 'Save figure', f'Could not save figure:\n{e}')

        def _add_single_to_cooling(self):
            """Send the Single-mineral tab's current mineral + computed Tᴄ to
            the Cooling history tab as a new row (age left blank to fill in)."""
            from PyQt5 import QtWidgets as _Q
            E = self._e_kj()
            D0 = self._read(self.d0Edit)
            a = self._read(self.radiusEdit)
            rate = self._read(self.rateEdit)
            geom = self.geomCombo.currentText()
            tc = None
            if None not in (E, D0, a, rate):
                t = closure_temperature(E, D0, a, geom, rate)
                if not math.isnan(t):
                    tc = f'{t:.0f}'
            if tc is None:
                _Q.QMessageBox.information(
                    self, 'Add to cooling history',
                    'Enter valid parameters (a finite Tᴄ) first.')
                return
            name = self.presetCombo.currentText()
            if name == 'Custom…':
                name = None
            self._ch_add_row(preset_name=name, tc=tc)
            self.tabs.setCurrentIndex(1)
            self.chTable.setCurrentCell(self.chTable.rowCount() - 1, 1)
            self._ch_plot()

        def _num_edit(self):
            e = QtWidgets.QLineEdit()
            e.setMaximumWidth(160)
            return e

        # ── preset / edit handling ──────────────────────────────────────────
        def _on_preset(self, idx):
            if idx < len(MINERAL_DB):
                self._load_preset(idx)
            else:
                self._recompute()   # Custom: keep current fields

        # ── E unit handling (DB stores kJ/mol) ─────────────────────────────
        def _e_is_kcal(self):
            return self.eUnitCombo.currentIndex() == 1

        def _e_kj(self):
            """Displayed E converted to kJ/mol (None if unparseable)."""
            v = self._read(self.eEdit)
            if v is None:
                return None
            return v * KCAL_TO_KJ if self._e_is_kcal() else v

        def _on_e_unit(self):
            # Unit toggle re-expresses the same physical E: convert the
            # displayed number in place, without flipping the preset to
            # Custom (the underlying parameters are unchanged).
            if self._building:
                return
            v = self._read(self.eEdit)
            if v is not None:
                factor = (1.0 / KCAL_TO_KJ) if self._e_is_kcal() else KCAL_TO_KJ
                self._building = True
                self.eEdit.setText(f'{v * factor:g}')
                self._building = False
            self._recompute()

        def _load_preset(self, idx):
            m = MINERAL_DB[idx]
            self._building = True
            self.presetCombo.setCurrentIndex(idx)
            e_val = m['E'] / KCAL_TO_KJ if self._e_is_kcal() else m['E']
            self.eEdit.setText(f'{e_val:g}')
            self.d0Edit.setText(f"{m['D0']:g}")
            self.radiusEdit.setText(f"{m['radius']:g}")
            self.geomCombo.setCurrentText(m['geometry'])
            if not self.rateEdit.text().strip():
                self.rateEdit.setText('10')
            self._building = False
            self._recompute()

        def _on_manual_edit(self):
            if self._building:
                return
            # Editing a value by hand may no longer match the cited preset,
            # so flip the selector to Custom (clears the reference label).
            if self.presetCombo.currentIndex() < len(MINERAL_DB):
                self._building = True
                self.presetCombo.setCurrentIndex(self.presetCombo.count() - 1)
                self._building = False
            self._recompute()

        # ── compute + render ────────────────────────────────────────────────
        def _read(self, widget, default=None):
            try:
                return float(widget.text())
            except (ValueError, TypeError):
                return default

        def _recompute(self):
            if self._building:
                return
            E = self._e_kj()
            D0 = self._read(self.d0Edit)
            a = self._read(self.radiusEdit)
            rate = self._read(self.rateEdit)
            geom = self.geomCombo.currentText()

            ref = ''
            idx = self.presetCombo.currentIndex()
            if idx < len(MINERAL_DB):
                ref = ('Diffusion data: ' + MINERAL_DB[idx]['ref']
                       + ', compiled in ' + TABLE5_CITATION)
                if MINERAL_DB[idx].get('nonarrhenian'):
                    ref += ('\n⚠ Non-Arrhenian diffusion: these E/D₀ describe '
                            'the high-T Arrhenius segment only; the Dodson Tᴄ '
                            'shown here exceeds the nominal T_cb of Table 5 '
                            f"({MINERAL_DB[idx]['tcb']} °C).")
            self.refLbl.setText(ref)

            if None in (E, D0, a, rate):
                self.resultLbl.setText('—')
            else:
                tc = closure_temperature(E, D0, a, geom, rate)
                if math.isnan(tc):
                    self.resultLbl.setText('n/a')
                else:
                    self.resultLbl.setText(f'Tᴄ = {tc:.0f} °C')

            # summary table
            for r, trate in enumerate(TABLE_RATES):
                val = '—'
                if None not in (E, D0, a):
                    tcr = closure_temperature(E, D0, a, geom, trate)
                    val = '—' if math.isnan(tcr) else f'{tcr:.0f}'
                it = QtWidgets.QTableWidgetItem(val)
                it.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(r, 1, it)

            self._render_plot(E, D0, a, geom, rate)

        def _render_plot(self, E, D0, a, geom, rate):
            self.ax.clear()
            if None not in (E, D0, a):
                rates = [10 ** (x / 20.0) for x in range(-20, 61)]  # 0.1–1000
                tcs = [closure_temperature(E, D0, a, geom, rr) for rr in rates]
                xs = [rr for rr, t in zip(rates, tcs) if not math.isnan(t)]
                ys = [t for t in tcs if not math.isnan(t)]
                if xs:
                    self.ax.plot(xs, ys, color='#1a5fb4', lw=2)
                if rate is not None:
                    tc = closure_temperature(E, D0, a, geom, rate)
                    if not math.isnan(tc):
                        self.ax.plot([rate], [tc], 'o', ms=9,
                                     color='#b41a1a', zorder=5)
                        self.ax.annotate(
                            f'{tc:.0f} °C @ {rate:g}',
                            (rate, tc), textcoords='offset points',
                            xytext=(8, 8), fontsize=9, color='#b41a1a')
                self.ax.set_xscale('log')
            self.ax.set_xlabel('Cooling rate (°C/Myr)', fontsize=10)
            self.ax.set_ylabel(r'Closure temperature $T_c$ (°C)', fontsize=10)
            self.ax.grid(True, which='both', ls=':', alpha=0.4)
            self.fig.tight_layout()
            self.canvas.draw_idle()

    return ClosureTempDialog


# Public factory so callers don't need to know about the lazy Qt build.
def ClosureTempDialog(parent=None):
    return _build_dialog_class()(parent)


# =============================================================================
#  self-test:  python ClosureTemperature.py
# =============================================================================
if __name__ == '__main__':
    # Validate every preset against the nominal T_cb of Schaen et al. (2021)
    # Table 5 (a = 100 µm, dT/dt = 10 °C/Myr, rounded to nearest 10 °C →
    # tolerance ±6 °C covers the rounding).
    print(f"{'chronometer':34s}{'Tc calc':>9s}{'Table 5':>9s}  ok")
    all_ok = True
    for m in MINERAL_DB:
        tc = closure_temperature(m['E'], m['D0'], 100.0, m['geometry'], 10.0)
        if m.get('nonarrhenian'):
            # Known exception (see MINERAL_DB comment): Dodson with the
            # high-T segment E/D0 gives ~750 °C, not the nominal 380 °C.
            ok = abs(tc - 750.0) <= 6.0
            note = '✓ (non-Arrhenian, expected ≠ Table 5)' if ok else '✗ FAIL'
        else:
            ok = abs(tc - m['tcb']) <= 6.0
            note = '✓' if ok else '✗ FAIL'
        all_ok &= ok
        print(f"{m['name']:34s}{tc:8.1f}C{m['tcb']:8d}C   {note}")

    # monotonicity: faster cooling → higher Tc
    slow = closure_temperature(264.0, 2.0e-3, 100, 'sphere', 1)
    fast = closure_temperature(264.0, 2.0e-3, 100, 'sphere', 100)
    mono = fast > slow
    print(f"\nfaster cooling raises Tc: {slow:.0f} → {fast:.0f} °C  "
          f"{'✓' if mono else '✗ FAIL'}")

    # non-physical inputs return NaN
    nan_ok = all(math.isnan(closure_temperature(*args)) for args in [
        (-1, 2.0e-3, 100, 'sphere', 10),
        (264, 0, 100, 'sphere', 10),
        (264, 2.0e-3, 100, 'sphere', 0),
    ])
    print(f"non-physical inputs → NaN: {'✓' if nan_ok else '✗ FAIL'}")

    # cooling_segments: old→young ordering + rate = ΔT/Δt, order-independent
    segs = cooling_segments([(30, 300), (40, 500), (34, 390)])
    seg_ok = (len(segs) == 2
              and segs[0]['age0'] == 40 and segs[0]['age1'] == 34
              and abs(segs[0]['rate'] - (500 - 390) / (40 - 34)) < 1e-9
              and abs(segs[1]['rate'] - (390 - 300) / (34 - 30)) < 1e-9)
    # degenerate segment (equal ages) → NaN rate
    seg_nan = math.isnan(cooling_segments([(10, 300), (10, 350)])[0]['rate'])
    print(f"cooling_segments rates + ordering: {'✓' if seg_ok else '✗ FAIL'}")
    print(f"cooling_segments Δt≤0 → NaN: {'✓' if seg_nan else '✗ FAIL'}")

    ok_all = all_ok and mono and nan_ok and seg_ok and seg_nan
    print('\nALL PASS' if ok_all else '\nSOME CHECKS FAILED')
