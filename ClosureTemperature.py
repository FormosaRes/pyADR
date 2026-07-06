# -*- coding: utf-8 -*-
"""
ClosureTemperature.py  —  pyADR mineral closure-temperature calculator
======================================================================
Dodson (1973) closure temperature for volume-diffusion thermochronometers,
applied to the ⁴⁰Ar/³⁹Ar systems pyADR reduces (hornblende, muscovite,
biotite, K-feldspar).

Dodson (1973), Contrib. Mineral. Petrol. 40, 259–274:

        Tc = E / [ R · ln( A · τ · D0 / a² ) ]

    with the cooling time constant
        τ = R · Tc² / ( E · |dT/dt| )

so Tc appears on both sides and is solved by fixed-point iteration.

  E      activation energy                    (J/mol; DB stores kcal/mol)
  D0     pre-exponential (frequency) factor   (cm²/s)
  a      effective diffusion radius           (cm; UI takes µm)
  A      geometry factor  55 sphere / 27 cylinder / 8.7 plane sheet
  dT/dt  cooling rate                         (K/s; UI takes °C/Myr)
  R      gas constant                         8.314462618 J/mol/K

The math (`closure_temperature`, `MINERAL_DB`) has no Qt dependency and is
unit-tested at the bottom of this file (`python ClosureTemperature.py`). The
`ClosureTempDialog` is opened from AutoPipeline's Tools menu.

References for the seeded diffusion parameters (all editable in the UI):
  Hornblende  Harrison (1981) Contrib. Mineral. Petrol. 78, 324–331
  Muscovite   Harrison, Célérier, Aikman, Hermann & Heizler (2009)
              Geochim. Cosmochim. Acta 73, 1039–1051
  Biotite     Harrison, Duncan & McDougall (1985) GCA 49, 2461–2468
  Biotite Fe  Grove & Harrison (1996) Am. Mineral. 81, 940–951
  K-feldspar  Foland (1974) GCA 38, 151–166  (single-domain bulk estimate;
              real K-fsp is multi-domain, Lovera et al. 1989 — see note)
"""

import math

# ── physical constants ──────────────────────────────────────────────────────
R_GAS = 8.314462618            # J mol⁻¹ K⁻¹
KCAL_TO_J = 4184.0             # 1 kcal = 4184 J
SEC_PER_MYR = 1.0e6 * 365.25 * 24 * 3600   # seconds in 1 Myr

# Dodson (1973) geometry factor A (slow-cooling limit).
GEOMETRY_FACTORS = {'sphere': 55.0, 'cylinder': 27.0, 'plane sheet': 8.7}

# Seeded Ar diffusion parameters. E in kcal/mol (as reported in the primary
# literature), D0 in cm²/s, radius in µm. All overridable in the dialog.
MINERAL_DB = [
    {'name': 'Hornblende',
     'E': 64.1, 'D0': 0.024, 'geometry': 'sphere', 'radius': 80.0,
     'ref': 'Harrison (1981) CMP 78, 324'},
    {'name': 'Muscovite',
     'E': 63.0, 'D0': 2.3, 'geometry': 'sphere', 'radius': 100.0,
     'ref': 'Harrison et al. (2009) GCA 73, 1039'},
    {'name': 'Biotite',
     'E': 47.0, 'D0': 0.077, 'geometry': 'cylinder', 'radius': 150.0,
     'ref': 'Harrison et al. (1985) GCA 49, 2461'},
    {'name': 'Biotite (Fe-rich)',
     'E': 47.1, 'D0': 0.40, 'geometry': 'cylinder', 'radius': 150.0,
     'ref': 'Grove & Harrison (1996) Am. Min. 81, 940'},
    {'name': 'K-feldspar (orthoclase)',
     'E': 43.8, 'D0': 0.0098, 'geometry': 'sphere', 'radius': 100.0,
     'ref': 'Foland (1974) GCA 38, 151 — bulk, see note'},
]


def closure_temperature(E_kcal, D0_cm2s, radius_um, geometry,
                        cooling_C_per_Myr, max_iter=200, tol=1e-9):
    """Dodson (1973) closure temperature, in °C.

    Solves Tc = E/(R·ln(A·τ·D0/a²)) with τ = R·Tc²/(E·|dT/dt|) by fixed-point
    iteration. Returns float('nan') if inputs are non-physical (non-positive
    parameters, or the log argument falls to ≤1, which means the grain never
    closes at that cooling rate / size).
    """
    if (E_kcal <= 0 or D0_cm2s <= 0 or radius_um <= 0
            or cooling_C_per_Myr <= 0 or geometry not in GEOMETRY_FACTORS):
        return float('nan')

    E = E_kcal * KCAL_TO_J          # J/mol
    a = radius_um * 1.0e-4          # µm → cm
    A = GEOMETRY_FACTORS[geometry]
    dTdt = cooling_C_per_Myr / SEC_PER_MYR   # K/s (cooling magnitude)

    T = 600.0                       # K, initial guess
    for _ in range(max_iter):
        tau = R_GAS * T * T / (E * dTdt)
        arg = A * tau * D0_cm2s / (a * a)
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
            self._load_preset(0)

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
            frm.addRow('Activation energy E (kcal/mol)', self.eEdit)

            self.d0Edit = self._num_edit()
            frm.addRow('Frequency factor D₀ (cm²/s)', self.d0Edit)

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
                ref = 'Diffusion data: ' + MINERAL_DB[idx]['ref']
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
    # Validate against published closure temperatures (100–150 µm, 10 °C/Myr).
    checks = [
        # name, E, D0, radius, geom, rate, expected_C, tol_C
        ('Hornblende', 64.1, 0.024, 80, 'sphere', 10, 500, 20),
        ('Muscovite', 63.0, 2.3, 100, 'sphere', 10, 425, 15),
        ('Biotite', 47.0, 0.077, 150, 'cylinder', 10, 310, 20),
        ('K-feldspar', 43.8, 0.0098, 100, 'sphere', 10, 280, 25),
    ]
    print(f"{'mineral':16s}{'Tc calc':>9s}{'expected':>10s}  ok")
    all_ok = True
    for name, E, D0, a, g, r, exp, tol in checks:
        tc = closure_temperature(E, D0, a, g, r)
        ok = abs(tc - exp) <= tol
        all_ok &= ok
        print(f"{name:16s}{tc:8.1f}C{exp:8d}C   {'✓' if ok else '✗ FAIL'}")

    # monotonicity: faster cooling → higher Tc
    slow = closure_temperature(63.0, 2.3, 100, 'sphere', 1)
    fast = closure_temperature(63.0, 2.3, 100, 'sphere', 100)
    mono = fast > slow
    print(f"\nfaster cooling raises Tc: {slow:.0f} → {fast:.0f} °C  "
          f"{'✓' if mono else '✗ FAIL'}")

    # non-physical inputs return NaN
    nan_ok = all(math.isnan(closure_temperature(*args)) for args in [
        (-1, 2.3, 100, 'sphere', 10),
        (63, 0, 100, 'sphere', 10),
        (63, 2.3, 100, 'sphere', 0),
    ])
    print(f"non-physical inputs → NaN: {'✓' if nan_ok else '✗ FAIL'}")

    print('\nALL PASS' if (all_ok and mono and nan_ok) else '\nSOME CHECKS FAILED')
