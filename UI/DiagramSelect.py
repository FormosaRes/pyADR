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
        MainWindow.resize(800, 696)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(8, 132, 781, 91))
        self.label.setMinimumSize(QtCore.QSize(519, 43))
        self.label.setObjectName("label")
        self.SH = QtWidgets.QPushButton(self.centralwidget)
        self.SH.setGeometry(QtCore.QRect(210, 230, 421, 51))
        self.SH.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.SH.setObjectName("SH")
        self.LS = QtWidgets.QPushButton(self.centralwidget)
        self.LS.setGeometry(QtCore.QRect(210, 290, 421, 51))
        self.LS.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.LS.setObjectName("LS")
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
        self.goHome = QtWidgets.QAction(MainWindow)
        self.goHome.setObjectName("goHome")
        self.actionAbout_pyADR = QtWidgets.QAction(MainWindow)
        self.actionAbout_pyADR.setObjectName("actionAbout_pyADR")
        self.actionCheck_Update = QtWidgets.QAction(MainWindow)
        self.actionCheck_Update.setObjectName("actionCheck_Update")
        self.menuMenu.addAction(self.actionAbout_pyADR)
        self.menuMenu.addAction(self.actionCheck_Update)
        self.menuMenu.addSeparator()
        self.menuMenu.addAction(self.actionParameter_Setting)
        self.menuMenu.addAction(self.goHome)
        self.menubar.addAction(self.menuMenu.menuAction())

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.label.setText(_translate("MainWindow", "<html><head/><body><p align=\"center\"><span style=\" font-size:48pt; font-weight:600;\">pyADR</span></p></body></html>"))
        self.SH.setText(_translate("MainWindow", "Step Heating"))
        self.LS.setText(_translate("MainWindow", "LaserOB"))
        self.menuMenu.setTitle(_translate("MainWindow", "Menu"))
        self.actionParameter_Setting.setText(_translate("MainWindow", " Parameter Setting"))
        self.goHome.setText(_translate("MainWindow", "Main Menu"))
        self.actionAbout_pyADR.setText(_translate("MainWindow", " About pyADR"))
        self.actionCheck_Update.setText(_translate("MainWindow", " Check Update"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

