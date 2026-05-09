# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'UI/AirRatioStatistics.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 697)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(0, 110, 791, 71))
        self.label.setObjectName("label")
        self.return_2 = QtWidgets.QPushButton(self.centralwidget)
        self.return_2.setGeometry(QtCore.QRect(0, 200, 91, 51))
        self.return_2.setObjectName("return_2")
        self.save = QtWidgets.QPushButton(self.centralwidget)
        self.save.setGeometry(QtCore.QRect(0, 250, 91, 51))
        self.save.setObjectName("save")
        self.new_2 = QtWidgets.QPushButton(self.centralwidget)
        self.new_2.setGeometry(QtCore.QRect(0, 300, 91, 51))
        self.new_2.setObjectName("new_2")
        self.RatioTableCa = QtWidgets.QTableWidget(self.centralwidget)
        self.RatioTableCa.setGeometry(QtCore.QRect(200, 200, 445, 90))
        self.RatioTableCa.setObjectName("RatioTable")
        self.RatioTableCa.setColumnCount(2)
        self.RatioTableCa.setRowCount(2)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableCa.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableCa.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableCa.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableCa.setVerticalHeaderItem(1, item)
        self.RatioTableCa.setVisible(False)
        self.RatioTableK = QtWidgets.QTableWidget(self.centralwidget)
        self.RatioTableK.setGeometry(QtCore.QRect(200, 200, 445, 90))
        self.RatioTableK.setObjectName("RatioTable")
        self.RatioTableK.setColumnCount(2)
        self.RatioTableK.setRowCount(3)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableK.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableK.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableK.setVerticalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableK.setVerticalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTableK.setVerticalHeaderItem(2, item)
        self.RatioTableK.setVisible(False)
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 24))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.return_2.setText(_translate("MainWindow", "Return"))
        self.save.setText(_translate("MainWindow", "Save"))
        self.new_2.setText(_translate("MainWindow", "New"))
        item = self.RatioTableCa.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "Ratio"))
        item = self.RatioTableCa.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "Sigma"))
        item = self.RatioTableCa.verticalHeaderItem(0)
        item.setText(_translate("MainWindow", "[36Ar/37Ar]Ca"))
        item = self.RatioTableCa.verticalHeaderItem(1)
        item.setText(_translate("MainWindow", "[39Ar/37Ar]Ca"))
        item = self.RatioTableK.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "Ratio"))
        item = self.RatioTableK.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "Sigma"))
        item = self.RatioTableK.verticalHeaderItem(0)
        item.setText(_translate("MainWindow", "[40Ar/39Ar]K"))
        item = self.RatioTableK.verticalHeaderItem(1)
        item.setText(_translate("MainWindow", "[38Ar/39Ar]K"))
        item = self.RatioTableK.verticalHeaderItem(2)
        item.setText(_translate("MainWindow", "[39Ar/37Ar]K"))

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

