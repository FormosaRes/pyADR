# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'UI/HomePage.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 750)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")

        # FIX: outer layout keeps `self.content` horizontally centered when
        # the user resizes the window.
        outer = QtWidgets.QHBoxLayout(self.centralwidget)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        # Fixed-width content column. NTNU_DataReduction.py adds the NTNU logo
        # into `page.content` (not centralwidget), so the logo also stays centered.
        self.content = QtWidgets.QWidget(self.centralwidget)
        self.content.setObjectName("content")
        self.content.setFixedWidth(520)
        outer.addWidget(self.content, 0, QtCore.Qt.AlignTop)
        outer.addStretch(1)

        col = QtWidgets.QVBoxLayout(self.content)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        # Logo placeholder — NTNU_DataReduction.py will reparent the NTNU logo
        # QLabel into `self.logo_slot` for the HomePage. Reserve vertical space
        # so the layout doesn't jump when the logo is added.
        self.logo_slot = QtWidgets.QWidget(self.content)
        self.logo_slot.setFixedHeight(85)
        col.addWidget(self.logo_slot)

        # pyADR title
        self.label = QtWidgets.QLabel(self.content)
        self.label.setMinimumHeight(34)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")
        col.addWidget(self.label)

        # Small gap before buttons
        col.addSpacing(8)

        # 10 buttons in a sub-layout. Negative spacing makes the native
        # PushButton borders overlap so the column reads as one stack
        # while keeping the original rounded/gradient look.
        btn_box = QtWidgets.QVBoxLayout()
        btn_box.setContentsMargins(0, 0, 0, 0)
        btn_box.setSpacing(6)
        col.addLayout(btn_box)

        button_specs = [
            ("LRP", "Calculate T0"),
            ("MR", "Mass Ratio"),
            ("JV", "J Calculation"),
            ("SC", "Salt Calculation"),
            ("PS_button", "Parameter Setting"),
            ("AC", "Age Calculation"),
            ("T0S", "Statistics"),
            ("DF", "Diagram Plots"),
            ("DP", "Datum Publication"),
            ("AP", "Argon Pipeline"),
        ]
        for name, _text in button_specs:
            btn = QtWidgets.QPushButton(self.content)
            btn.setObjectName(name)
            btn.setMinimumHeight(52)
            # FIX: keep native PushButton look (rounded gradient); only override font size.
            btn.setStyleSheet("font: 22pt \".AppleSystemUIFont\";")
            btn_box.addWidget(btn)
            setattr(self, name, btn)

        col.addStretch(1)

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 24))
        self.menubar.setObjectName("menubar")
        self.menuMenu = QtWidgets.QMenu(self.menubar)
        self.menuMenu.setObjectName("menuMenu")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.actionParameter_Setting = QtWidgets.QAction(MainWindow)
        self.actionParameter_Setting.setObjectName("actionParameter_Setting")
        self.actionAbout_pyADR = QtWidgets.QAction(MainWindow)
        self.actionAbout_pyADR.setObjectName("actionAbout_pyADR")
        self.actionCheck_Update = QtWidgets.QAction(MainWindow)
        self.actionCheck_Update.setObjectName("actionCheck_Update")
        # v3.8.95: Dodson (1973) closure-temperature calculator
        # (ClosureTemperature.py); wired in NTNU_DataReduction like
        # actionParameter_Setting.
        self.actionClosure_Temperature = QtWidgets.QAction(MainWindow)
        self.actionClosure_Temperature.setObjectName("actionClosure_Temperature")
        self.menuMenu.addAction(self.actionAbout_pyADR)
        self.menuMenu.addAction(self.actionCheck_Update)
        self.menuMenu.addSeparator()
        self.menuMenu.addAction(self.actionParameter_Setting)
        self.menuMenu.addAction(self.actionClosure_Temperature)
        self.menubar.addAction(self.menuMenu.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.label.setText(_translate("MainWindow", "<html><head/><body><p align=\"center\"><span style=\" font-size:18pt; font-weight:600;\">pyADR</span></p></body></html>"))
        self.LRP.setToolTip(_translate("MainWindow", "<html><head/><body><p>T0 Calculation:</p><p>Please select the raw data file for which you want to calculate the T<span style=\" vertical-align:sub;\">0</span> with valid data format (refer to the example in README)!</p></body></html>"))
        self.LRP.setWhatsThis(_translate("MainWindow", "<html><head/><body><p>what is this</p></body></html>"))
        self.LRP.setText(_translate("MainWindow", "Calculate T0"))
        self.T0S.setToolTip(_translate("MainWindow", "<html><head/><body><p>T0 Statistics:</p><p>Please select all the files (the raw files output by the <span style=\" font-style:italic;\">Calculate T0 page</span>) for which you want to compute the statistics of the T<span style=\" vertical-align:sub;\">0</span> values.</p></body></html>"))
        self.T0S.setWhatsThis(_translate("MainWindow", "<html><head/><body><p>what is this</p></body></html>"))
        self.T0S.setText(_translate("MainWindow", "Statistics"))
        self.MR.setToolTip(_translate("MainWindow", "<html><head/><body><p>Mass Ratio Calculation:</p><p>Please select one mass file first and then one preline file. Both files are the raw files output by <span style=\" font-style:italic;\">Calculate T0 page</span>.</p></body></html>"))
        self.MR.setWhatsThis(_translate("MainWindow", "<html><head/><body><p>what is this</p></body></html>"))
        self.MR.setText(_translate("MainWindow", "Mass Ratio"))
        self.JV.setText(_translate("MainWindow", "J Calculation"))
        self.SC.setText(_translate("MainWindow", "Salt Calculation"))
        self.DF.setText(_translate("MainWindow", "Diagram Plots"))
        self.DP.setText(_translate("MainWindow", "Datum Publication"))
        self.AP.setText(_translate("MainWindow", "Argon Pipeline"))
        self.AC.setToolTip(_translate("MainWindow", "<html><head/><body><p>Age Calculation:</p><p>Please select one file (the measurement file output by the <span style=\" font-style:italic;\">Mass Ratio Page</span>) that you want to calculate the age for.</p></body></html>"))
        self.AC.setWhatsThis(_translate("MainWindow", "<html><head/><body><p>what is this</p></body></html>"))
        self.AC.setText(_translate("MainWindow", "Age Calculation"))
        self.PS_button.setToolTip(_translate("MainWindow", "<html><head/><body><p>Production Ratio 39Ar/37Ar(ca)</p><p>Production Ratio 36Ar/37Ar(ca)</p><p>Production Ratio 40Ar/39Ar(k)</p><p>Production Ratio 38Ar/39Ar(k)</p><p>Production Ratio 36Ar/38Ar(cl)</p><p>Atmospheric Ratio 40/36(a)</p><p>Atmospheric Ratio 38/36(a)</p><p>λ</p><p>J value</p><p>J std</p><p>numCycle</p></body></html>"))
        self.PS_button.setWhatsThis(_translate("MainWindow", "<html><head/><body><p>what is this</p></body></html>"))
        self.PS_button.setText(_translate("MainWindow", "Parameter Setting"))
        self.menuMenu.setTitle(_translate("MainWindow", "Menu"))
        self.actionParameter_Setting.setText(_translate("MainWindow", " Parameter Setting"))
        self.actionAbout_pyADR.setText(_translate("MainWindow", " About pyADR"))
        self.actionCheck_Update.setText(_translate("MainWindow", " Check Update"))
        self.actionClosure_Temperature.setText(_translate("MainWindow", " Closure Temperature"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
