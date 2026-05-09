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
        self.Ca36 = QtWidgets.QPushButton(self.centralwidget)
        self.Ca36.setGeometry(QtCore.QRect(210, 230, 421, 51))
        self.Ca36.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.Ca36.setObjectName("36Ca")
        self.Ca39 = QtWidgets.QPushButton(self.centralwidget)
        self.Ca39.setGeometry(QtCore.QRect(210, 290, 421, 51))
        self.Ca39.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.Ca39.setObjectName("39Ca")
        self.K40 = QtWidgets.QPushButton(self.centralwidget)
        self.K40.setGeometry(QtCore.QRect(210, 350, 421, 51))
        self.K40.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.K40.setObjectName("40K")
        self.K38 = QtWidgets.QPushButton(self.centralwidget)
        self.K38.setGeometry(QtCore.QRect(210, 410, 421, 51))
        self.K38.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.K38.setObjectName("38K")
        self.K39 = QtWidgets.QPushButton(self.centralwidget)
        self.K39.setGeometry(QtCore.QRect(210, 470, 421, 51))
        self.K39.setStyleSheet("font: 20pt \".AppleSystemUIFont\";")
        self.K39.setObjectName("39K")
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
        self.Ca36.setText(_translate("MainWindow", "[36Ar/37Ar]Ca"))
        self.Ca39.setText(_translate("MainWindow", "[39Ar/37Ar]Ca"))
        self.K40.setText(_translate("MainWindow", "[40Ar/39Ar]K"))
        self.K38.setText(_translate("MainWindow", "[38Ar/39Ar]K"))
        self.K39.setText(_translate("MainWindow", "[39Ar/37Ar]K"))
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

