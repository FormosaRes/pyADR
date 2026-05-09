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
        self.RatioTable = QtWidgets.QTableWidget(self.centralwidget)
        self.RatioTable.setGeometry(QtCore.QRect(200, 200, 500, 60))
        self.RatioTable.setObjectName("RatioTable")
        self.RatioTable.setColumnCount(5)
        self.RatioTable.setRowCount(1)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable.setHorizontalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable.setHorizontalHeaderItem(4, item)
        self.RatioTable2 = QtWidgets.QTableWidget(self.centralwidget)
        self.RatioTable2.setGeometry(QtCore.QRect(200, 265, 500, 60))
        self.RatioTable2.setObjectName("RatioTable2")
        self.RatioTable2.setColumnCount(5)
        self.RatioTable2.setRowCount(1)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable2.setHorizontalHeaderItem(0, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable2.setHorizontalHeaderItem(1, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable2.setHorizontalHeaderItem(2, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable2.setHorizontalHeaderItem(3, item)
        item = QtWidgets.QTableWidgetItem()
        self.RatioTable2.setHorizontalHeaderItem(4, item)
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
        item = self.RatioTable.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "36Ar(a)[V]"))
        item = self.RatioTable.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "37Ar(ca)[V]"))
        item = self.RatioTable.horizontalHeaderItem(2)
        item.setText(_translate("MainWindow", "39Ar(k)[V]"))
        item = self.RatioTable.horizontalHeaderItem(3)
        item.setText(_translate("MainWindow", "40Ar(r)[V]"))
        item = self.RatioTable.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "40Ar(r)(%)"))
        item = self.RatioTable2.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "39Ar(k)(%)"))
        item = self.RatioTable2.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "K/Ca"))
        item = self.RatioTable2.horizontalHeaderItem(2)
        item.setText(_translate("MainWindow", "K/Ca Sigma"))
        item = self.RatioTable2.horizontalHeaderItem(3)
        item.setText(_translate("MainWindow", "J value")) 
        item = self.RatioTable2.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "J Sigma")) 


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

