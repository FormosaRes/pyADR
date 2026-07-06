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

  E      activation energy                    (J/mol; UI takes kJ/mol)
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
            self.setMinimumSize(920, 620)
            self._building = True
            self._build()
            self._building = False
            self._load_preset(DEFAULT_PRESET)

        # ── layout ──────────────────────────────────────────────────────────
        def _build(self):
            root = QtWidgets.QHBoxLayout(self)
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

            self.eEdit = self._num_edit()
            frm.addRow('Activation energy E (kJ/mol)', self.eEdit)

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
            self.table.setMaximumHeight(38 + 30 * len(TABLE_RATES))
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
            btnRow.addStretch(1)
            closeBtn = QtWidgets.QPushButton('Close')
            closeBtn.setMinimumWidth(90)
            closeBtn.clicked.connect(self.accept)
            btnRow.addWidget(closeBtn)
            right.addLayout(btnRow)

            for e in (self.eEdit, self.d0Edit, self.radiusEdit, self.rateEdit):
                e.textChanged.connect(self._on_manual_edit)

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

        def _load_preset(self, idx):
            m = MINERAL_DB[idx]
            self._building = True
            self.presetCombo.setCurrentIndex(idx)
            self.eEdit.setText(f"{m['E']:g}")
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
            E = self._read(self.eEdit)
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

    print('\nALL PASS' if (all_ok and mono and nan_ok) else '\nSOME CHECKS FAILED')
