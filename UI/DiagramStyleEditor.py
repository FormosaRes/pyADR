"""DiagramStyleEditor — 診斷圖樣式編輯 QDialog(v3.9.0)

pyADR 的 AgeCalc diagram(DFN/DFI/DFW/DFA/DFC/DFD/DFR)樣式編輯器。
NTNU_DataReduction 的 DiagramPlots_SH sidebar 與 AutoPipeline AgeCalcPage
的 Plot Controls 各掛一顆 ⚙,開啟同一個 dialog、寫同一份中央 style dict
(Utilities.set_style_overrides),兩端不會樣式漂移。

設計:
- 圖表為主體,右側大圖置中(QLabel 顯示 .work/<target>.png,auto-scale)。
- 控件收在左側 QTabWidget(顏色 / 字型 / 線條&Marker / Legend / 軸 / 文字標籤)。
- 頂部 preset 下拉,改任一參數 → 自動切為 custom。
- non-modal 單例;host 提供 on_apply callback,Apply/OK 時呼叫以重畫。

本檔只負責 UI 與把設定收集成 overrides dict;實際重畫走 host 既有的
_refresh_diagrams / SH_apply_axes,不另建繪圖路徑。
"""
import os

from PyQt5 import QtCore, QtGui, QtWidgets

import Utilities


# 對應 Utilities plot function 的 target 代碼與人類可讀名
TARGETS = [
    ('DFW', 'Age Spectrum'),
    ('DFI', 'Inverse Isochron'),
    ('DFN', 'Normal Isochron'),
    ('DFA', 'Ca/K'),
    ('DFC', 'Cl/K'),
    ('DFD', 'Degassing'),
    ('DFR', '⁴⁰Ar(r)%'),
]

# 單一序列色的 key → 顯示名
COLOR_KEYS = [
    ('age', 'Age spectrum / isochron 主色'),
    ('cak', 'Ca/K'),
    ('clk', 'Cl/K'),
    ('atm', '大氣參考'),
    ('atm_marker', '大氣 marker'),
    ('iso_dot', 'Isochron 資料點'),
    ('edge', '邊框'),
    ('mean_color', 'WMA / mean 線'),
]

LEGEND_LOCS = ['best', 'upper left', 'upper right', 'lower left',
               'lower right', 'upper center', 'lower center', 'center']


class _ColorButton(QtWidgets.QPushButton):
    """色塊按鈕,點擊開 QColorDialog。changed(str hex) 訊號。"""
    changed = QtCore.pyqtSignal(str)

    def __init__(self, color='#000000', parent=None):
        super().__init__(parent)
        self.setFixedSize(46, 20)
        self._color = color
        self._apply()
        self.clicked.connect(self._pick)

    def _apply(self):
        self.setStyleSheet(
            f'background:{self._color};border:1px solid #888;border-radius:3px;')
        self.setToolTip(self._color)

    def color(self):
        return self._color

    def setColor(self, c):
        if c and c != self._color:
            self._color = c
            self._apply()

    def _pick(self):
        c = QtGui.QColor(self._color)
        chosen = QtWidgets.QColorDialog.getColor(
            c, self, 'Pick colour',
            QtWidgets.QColorDialog.ShowAlphaChannel)
        if chosen.isValid():
            self._color = chosen.name()
            self._apply()
            self.changed.emit(self._color)


class DiagramStyleEditor(QtWidgets.QDialog):
    """診斷圖樣式編輯器。

    host_get_style : callable → 目前 preset 名('pyADR'/'classic'/...)
    on_apply       : callable(overrides:dict, preset:str)。host 在此把
                     overrides 套進 Utilities.set_style_overrides 並重畫。
    work_dir       : .work 目錄,用來讀預覽 PNG。
    current_target : 開啟時預設顯示的 target code(跟隨主視窗)。
    """

    def __init__(self, parent=None, host_get_style=None, on_apply=None,
                 work_dir=None, current_target='DFW'):
        super().__init__(parent)
        self.setWindowTitle('Diagram Style Editor')
        self.setModal(False)
        self._host_get_style = host_get_style or (lambda: 'pyADR')
        self._on_apply = on_apply
        self._work_dir = work_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), '.work')
        self._preview_target = current_target if any(
            t[0] == current_target for t in TARGETS) else 'DFW'
        self._loading = False          # 抑制載入時的 dirty 標記
        self._color_btns = {}
        self._text_edits = {}          # (target, field) → QLineEdit

        self.resize(1060, 640)
        self._build_ui()
        _preset = self._host_get_style()
        _pi = self.presetCombo.findText(_preset)
        if _pi >= 0:
            self.presetCombo.blockSignals(True)
            self.presetCombo.setCurrentIndex(_pi)
            self.presetCombo.blockSignals(False)
        self._load_from_style(_preset)
        self._refresh_preview()

    # ------------------------------------------------------------------ UI --
    def _build_ui(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(10, 10, 10, 6)
        body.setSpacing(10)
        root.addLayout(body, 1)

        # ── 左側控件欄 ──────────────────────────────────────────────
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)
        body.addLayout(left, 0)

        preset_row = QtWidgets.QHBoxLayout()
        preset_row.addWidget(QtWidgets.QLabel('<b>Preset</b>'))
        self.presetCombo = QtWidgets.QComboBox()
        self._preset_names = Utilities.available_styles() + ['custom']
        self.presetCombo.addItems(self._preset_names)
        self.presetCombo.currentIndexChanged.connect(self._on_preset_changed)
        preset_row.addWidget(self.presetCombo, 1)
        left.addLayout(preset_row)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setFixedWidth(310)
        self.tabs.addTab(self._tab_colors(), '顏色')
        self.tabs.addTab(self._tab_fonts(), '字型')
        self.tabs.addTab(self._tab_lines(), '線條/Marker')
        self.tabs.addTab(self._tab_legend(), 'Legend')
        self.tabs.addTab(self._tab_axes(), '軸')
        self.tabs.addTab(self._tab_text(), '文字標籤')
        left.addWidget(self.tabs, 1)

        # ── 右側預覽(主體)─────────────────────────────────────────
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(6)
        body.addLayout(right, 1)

        prev_bar = QtWidgets.QHBoxLayout()
        prev_bar.addWidget(QtWidgets.QLabel('<b>即時預覽</b>'))
        prev_bar.addStretch(1)
        prev_bar.addWidget(QtWidgets.QLabel('target'))
        self.targetCombo = QtWidgets.QComboBox()
        for code, name in TARGETS:
            self.targetCombo.addItem(f'{name}  ({code})', code)
        _idx = self.targetCombo.findData(self._preview_target)
        if _idx >= 0:
            self.targetCombo.setCurrentIndex(_idx)
        self.targetCombo.currentIndexChanged.connect(self._on_target_changed)
        prev_bar.addWidget(self.targetCombo)
        right.addLayout(prev_bar)

        self.previewLabel = QtWidgets.QLabel('(套用後產生預覽)')
        self.previewLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.previewLabel.setMinimumSize(520, 420)
        self.previewLabel.setStyleSheet(
            'background:#fcfcfb;border:1px solid #ddd;border-radius:4px;')
        right.addWidget(self.previewLabel, 1)

        self.hintLabel = QtWidgets.QLabel(
            'Apply 後以現行 pipeline 重算重畫。圖為 dialog 主體,置中放大。')
        self.hintLabel.setStyleSheet('color:#898781;font-size:11px;')
        right.addWidget(self.hintLabel)

        # ── 底部按鈕 ────────────────────────────────────────────────
        foot = QtWidgets.QHBoxLayout()
        foot.setContentsMargins(10, 4, 10, 8)
        self.resetBtn = QtWidgets.QPushButton('Reset to preset')
        self.resetBtn.clicked.connect(self._on_reset)
        foot.addWidget(self.resetBtn)
        foot.addStretch(1)
        cancelBtn = QtWidgets.QPushButton('Cancel')
        cancelBtn.clicked.connect(self.reject)
        applyBtn = QtWidgets.QPushButton('Apply')
        applyBtn.clicked.connect(self._apply)
        okBtn = QtWidgets.QPushButton('OK')
        okBtn.setDefault(True)
        okBtn.clicked.connect(self._ok)
        for b in (cancelBtn, applyBtn, okBtn):
            foot.addWidget(b)
        root.addLayout(foot, 0)

    def _scroll(self, inner):
        sa = QtWidgets.QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QtWidgets.QFrame.NoFrame)
        sa.setWidget(inner)
        return sa

    def _tab_colors(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        form.setLabelAlignment(QtCore.Qt.AlignRight)
        for key, label in COLOR_KEYS:
            btn = _ColorButton()
            btn.changed.connect(self._mark_dirty)
            self._color_btns[key] = btn
            form.addRow(label, btn)
        form.addRow(QtWidgets.QLabel('<hr>'))
        form.addRow(QtWidgets.QLabel('<b>分組色 GROUP_COLORS</b>'))
        self.groupList = QtWidgets.QListWidget()
        self.groupList.setFixedHeight(150)
        self.groupList.itemDoubleClicked.connect(self._edit_group_color)
        form.addRow(self.groupList)
        gbtns = QtWidgets.QHBoxLayout()
        addb = QtWidgets.QPushButton('+')
        addb.clicked.connect(self._add_group_color)
        rmb = QtWidgets.QPushButton('−')
        rmb.clicked.connect(self._remove_group_color)
        gbtns.addWidget(addb)
        gbtns.addWidget(rmb)
        gbtns.addStretch(1)
        gw = QtWidgets.QWidget()
        gw.setLayout(gbtns)
        form.addRow(gw)
        form.addRow(QtWidgets.QLabel(
            '<span style="color:#888;font-size:10px;">順序=色盲安全機制,'
            '雙擊改色</span>'))
        return self._scroll(w)

    def _spin(self, lo, hi, val, dec=0, step=1.0):
        s = (QtWidgets.QDoubleSpinBox() if dec else QtWidgets.QSpinBox())
        s.setRange(lo, hi)
        if dec:
            s.setDecimals(dec)
            s.setSingleStep(step)
        s.setValue(val)
        s.setSpecialValueText('auto')   # 最小值顯示 auto = 用預設
        return s

    def _tab_fonts(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        # 0 = auto(沿用 matplotlib 預設)
        self.fAxis = self._spin(0, 40, 0)
        self.fTick = self._spin(0, 40, 0)
        self.fTitle = self._spin(0, 40, 0)
        self.fAnnot = self._spin(0, 40, 8)
        self.fGroup = self._spin(0, 40, 7)
        for s in (self.fAxis, self.fTick, self.fTitle, self.fAnnot, self.fGroup):
            s.valueChanged.connect(self._mark_dirty)
        form.addRow('軸標題 pt', self.fAxis)
        form.addRow('刻度 pt', self.fTick)
        form.addRow('圖標題 pt', self.fTitle)
        form.addRow('註記 pt', self.fAnnot)
        form.addRow('分組註記 pt', self.fGroup)
        form.addRow(QtWidgets.QLabel(
            '<span style="color:#888;font-size:10px;">0 = auto,'
            '字型 family 固定 Arial(見 CLAUDE.md §5)</span>'))
        return self._scroll(w)

    def _tab_lines(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        self.lwFit = self._spin(0.1, 6.0, 2.0, dec=1, step=0.1)
        self.lwLink = self._spin(0.1, 6.0, 0.5, dec=1, step=0.1)
        self.lwWma = self._spin(0.1, 6.0, 1.5, dec=1, step=0.1)
        self.lwSpine = self._spin(0.1, 6.0, 1.0, dec=1, step=0.1)
        self.lwBar = self._spin(0.1, 6.0, 0.5, dec=1, step=0.1)
        for s in (self.lwFit, self.lwLink, self.lwWma, self.lwSpine, self.lwBar):
            s.valueChanged.connect(self._mark_dirty)
        form.addRow('迴歸線寬', self.lwFit)
        form.addRow('連接線寬', self.lwLink)
        form.addRow('WMA 線寬', self.lwWma)
        form.addRow('邊框線寬', self.lwSpine)
        form.addRow('step box 邊寬', self.lwBar)
        return self._scroll(w)

    def _tab_legend(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        self.legLoc = QtWidgets.QComboBox()
        self.legLoc.addItems(LEGEND_LOCS)
        self.legLoc.currentIndexChanged.connect(self._mark_dirty)
        self.legFs = self._spin(4, 30, 8)
        self.legFs.valueChanged.connect(self._mark_dirty)
        self.legFa = self._spin(0.0, 1.0, 0.85, dec=2, step=0.05)
        self.legFa.setSpecialValueText('')
        self.legFa.valueChanged.connect(self._mark_dirty)
        form.addRow('位置 loc', self.legLoc)
        form.addRow('字級', self.legFs)
        form.addRow('框透明度', self.legFa)
        return self._scroll(w)

    def _tab_axes(self):
        w = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(w)
        self.tickDir = QtWidgets.QComboBox()
        self.tickDir.addItems(['out', 'in', 'inout'])
        self.tickDir.currentIndexChanged.connect(self._mark_dirty)
        self.cbTopRight = QtWidgets.QCheckBox('top + right ticks')
        self.cbMinor = QtWidgets.QCheckBox('minor ticks')
        self.cbGrid = QtWidgets.QCheckBox('grid')
        for cb in (self.cbTopRight, self.cbMinor, self.cbGrid):
            cb.toggled.connect(self._mark_dirty)
        form.addRow('刻度方向', self.tickDir)
        form.addRow(self.cbTopRight)
        form.addRow(self.cbMinor)
        form.addRow(self.cbGrid)
        return self._scroll(w)

    def _tab_text(self):
        w = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(w)
        v.addWidget(QtWidgets.QLabel('每個 diagram 的 title / x / y 標籤覆寫,'
                                     '留空=用預設'))
        v.addWidget(QtWidgets.QLabel(
            '<span style="color:#888;font-size:10px;">下標請用 mathtext,'
            r'例如 $T_0$、$^{40}$Ar(見 CLAUDE.md §5)</span>'))
        for code, name in TARGETS:
            box = QtWidgets.QGroupBox(f'{name} ({code})')
            gf = QtWidgets.QFormLayout(box)
            for field, lbl in [('title', 'title'), ('xlabel', 'x'),
                               ('ylabel', 'y')]:
                ed = QtWidgets.QLineEdit()
                ed.setPlaceholderText('(預設)')
                ed.textEdited.connect(self._mark_dirty)
                self._text_edits[(code, field)] = ed
                gf.addRow(lbl, ed)
            v.addWidget(box)
        v.addStretch(1)
        return self._scroll(w)

    # -------------------------------------------------------------- state --
    def _mark_dirty(self, *args):
        if self._loading:
            return
        # 切到 custom(不觸發 reload)
        idx = self.presetCombo.findText('custom')
        if idx >= 0 and self.presetCombo.currentIndex() != idx:
            self.presetCombo.blockSignals(True)
            self.presetCombo.setCurrentIndex(idx)
            self.presetCombo.blockSignals(False)

    def _load_from_style(self, preset):
        """把某 preset 的合併結果灌進所有控件。"""
        self._loading = True
        try:
            Utilities.set_style_overrides(None)   # 讀乾淨的 preset 值
            st = Utilities._get_style(preset)
        finally:
            pass
        for key, _ in COLOR_KEYS:
            val = st.get(key)
            if isinstance(val, str) and val.startswith('#'):
                self._color_btns[key].setColor(val)
            elif isinstance(val, str):
                # 具名色(white/teal/red…)轉 hex 以利 picker
                qc = QtGui.QColor(val)
                self._color_btns[key].setColor(qc.name() if qc.isValid()
                                               else '#000000')
        self._set_group_list(st.get('group_colors',
                                    Utilities.GROUP_COLORS))
        self.fAxis.setValue(st.get('font_axis') or 0)
        self.fTick.setValue(st.get('font_tick') or 0)
        self.fTitle.setValue(st.get('font_title') or 0)
        self.fAnnot.setValue(st.get('font_annot') or 0)
        self.fGroup.setValue(st.get('font_group') or 0)
        self.lwFit.setValue(st.get('lw_fit', 2.0))
        self.lwLink.setValue(st.get('lw_link', 0.5))
        self.lwWma.setValue(st.get('lw_wma', 1.5))
        self.lwSpine.setValue(st.get('lw_spine', 1.0))
        self.lwBar.setValue(st.get('lw', 0.5))
        self.legLoc.setCurrentText(st.get('legend_loc', 'upper left'))
        self.legFs.setValue(st.get('legend_fontsize', 8))
        self.legFa.setValue(st.get('legend_framealpha', 0.85))
        self.tickDir.setCurrentText(st.get('tick_dir', 'out'))
        self.cbTopRight.setChecked(bool(st.get('ticks_top_right')))
        self.cbMinor.setChecked(bool(st.get('minor')))
        self.cbGrid.setChecked(bool(st.get('grid')))
        for (code, field), ed in self._text_edits.items():
            ed.setText(st.get('text', {}).get(code, {}).get(field, ''))
        self._loading = False

    def _set_group_list(self, colors):
        self.groupList.clear()
        for c in colors:
            it = QtWidgets.QListWidgetItem(c)
            it.setBackground(QtGui.QColor(c))
            it.setForeground(QtGui.QColor('#ffffff'
                             if QtGui.QColor(c).lightness() < 128 else '#000000'))
            self.groupList.addItem(it)

    def _group_colors(self):
        return [self.groupList.item(i).text()
                for i in range(self.groupList.count())]

    def _edit_group_color(self, item):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor(item.text()), self)
        if c.isValid():
            item.setText(c.name())
            item.setBackground(c)
            self._mark_dirty()

    def _add_group_color(self):
        c = QtWidgets.QColorDialog.getColor(QtGui.QColor('#888888'), self)
        if c.isValid():
            it = QtWidgets.QListWidgetItem(c.name())
            it.setBackground(c)
            self.groupList.addItem(it)
            self._mark_dirty()

    def _remove_group_color(self):
        row = self.groupList.currentRow()
        if row >= 0:
            self.groupList.takeItem(row)
            self._mark_dirty()

    def _on_preset_changed(self, _idx):
        name = self.presetCombo.currentText()
        if name == 'custom':
            return                       # 停在使用者當前設定
        self._load_from_style(name)
        self._apply()

    def _on_reset(self):
        name = self.presetCombo.currentText()
        base = 'pyADR' if name == 'custom' else name
        self.presetCombo.blockSignals(True)
        self.presetCombo.setCurrentText(base)
        self.presetCombo.blockSignals(False)
        self._load_from_style(base)
        self._apply()

    def _on_target_changed(self, _idx):
        self._preview_target = self.targetCombo.currentData()
        self._refresh_preview()

    # -------------------------------------------------------------- output --
    def _collect_overrides(self):
        """把控件狀態收集成 Utilities overrides dict。"""
        ov = {}
        for key, _ in COLOR_KEYS:
            ov[key] = self._color_btns[key].color()
        ov['group_colors'] = self._group_colors()
        ov['font_axis'] = self.fAxis.value() or None
        ov['font_tick'] = self.fTick.value() or None
        ov['font_title'] = self.fTitle.value() or None
        ov['font_annot'] = self.fAnnot.value() or None
        ov['font_group'] = self.fGroup.value() or None
        ov['lw_fit'] = self.lwFit.value()
        ov['lw_link'] = self.lwLink.value()
        ov['lw_wma'] = self.lwWma.value()
        ov['lw_spine'] = self.lwSpine.value()
        ov['lw'] = self.lwBar.value()
        ov['legend_loc'] = self.legLoc.currentText()
        ov['legend_fontsize'] = self.legFs.value()
        ov['legend_framealpha'] = self.legFa.value()
        ov['tick_dir'] = self.tickDir.currentText()
        ov['ticks_top_right'] = self.cbTopRight.isChecked()
        ov['minor'] = self.cbMinor.isChecked()
        ov['grid'] = self.cbGrid.isChecked()
        text = {}
        for (code, field), ed in self._text_edits.items():
            val = ed.text().strip()
            if val:
                text.setdefault(code, {})[field] = val
        if text:
            ov['text'] = text
        return ov

    def current_preset(self):
        return self.presetCombo.currentText()

    def _apply(self):
        overrides = self._collect_overrides()
        preset = self.current_preset()
        if self._on_apply:
            try:
                self._on_apply(overrides, preset)
            except Exception as e:            # host 重畫失敗不該炸掉 dialog
                self.hintLabel.setText(f'重畫失敗: {e}')
                self.hintLabel.setStyleSheet('color:#c0392b;font-size:11px;')
                return
        self._refresh_preview()

    def _ok(self):
        self._apply()
        self.accept()

    def _refresh_preview(self):
        path = os.path.join(self._work_dir, f'{self._preview_target}.png')
        if os.path.exists(path):
            pm = QtGui.QPixmap(path)
            if not pm.isNull():
                self.previewLabel.setPixmap(pm.scaled(
                    self.previewLabel.size(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation))
                return
        self.previewLabel.setText(
            f'{self._preview_target}.png 尚未產生\n(先在主視窗畫一次,或按 Apply)')

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._refresh_preview()
