# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'UI/T0Statistics.ui'
#
# Created by: PyQt5 UI code generator 5.9.2
#
# WARNING! All changes made in this file will be lost!

from PyQt5 import QtCore, QtGui, QtWidgets

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(800, 703)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.label = QtWidgets.QLabel(self.centralwidget)
        self.label.setGeometry(QtCore.QRect(5, 102, 791, 61))
        self.label.setObjectName("label")
        self.numSelectedFiles = QtWidgets.QLabel(self.centralwidget)
        self.numSelectedFiles.setGeometry(QtCore.QRect(150, 580, 200, 31))
        self.numSelectedFiles.setObjectName("numSelectedFiles")
        self.return_2 = QtWidgets.QPushButton(self.centralwidget)
        self.return_2.setGeometry(QtCore.QRect(0, 190, 91, 51))
        self.return_2.setObjectName("return_2")
        self.save = QtWidgets.QPushButton(self.centralwidget)
        self.save.setGeometry(QtCore.QRect(0, 240, 91, 51))
        self.save.setObjectName("save")
        self.new_2 = QtWidgets.QPushButton(self.centralwidget)
        self.new_2.setGeometry(QtCore.QRect(0, 290, 91, 51))
        self.new_2.setObjectName("new_2")
        self.reselect = QtWidgets.QPushButton(self.centralwidget)
        self.reselect.setGeometry(QtCore.QRect(0, 340, 91, 51))
        self.reselect.setObjectName("reselect")
        
        self.tableWidget = QtWidgets.QTableWidget(self.centralwidget)
        self.Tsize =[150, 470, 591, 101]
        self.tableWidget.setGeometry(QtCore.QRect(self.Tsize[0], self.Tsize[1], self.Tsize[2], self.Tsize[3]))
        self.tableWidget.setObjectName("tableWidget")
        self.tableWidget.setColumnCount(5)
        self.tableWidget.setRowCount(4)
        item = QtWidgets.QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(0, item)
        self.tableWidget.setVerticalHeaderItem(1, item)
        self.tableWidget.setVerticalHeaderItem(2, item)
        self.tableWidget.setVerticalHeaderItem(3, item)
        self.tableWidget.setHorizontalHeaderItem(0, item)
        self.tableWidget.setHorizontalHeaderItem(1, item)
        self.tableWidget.setHorizontalHeaderItem(2, item)
        self.tableWidget.setHorizontalHeaderItem(3, item)
        self.tableWidget.setHorizontalHeaderItem(4, item)
        
        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 24))
        self.menubar.setObjectName("menubar")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)
        self.Isize =[150, 175, 600, 250]
        self.photo = QtWidgets.QLabel(self.centralwidget)
        self.photo.setGeometry(QtCore.QRect(self.Isize[0], self.Isize[1], self.Isize[2], self.Isize[3]))
        self.photo.setScaledContents(True)
        self.photo.setObjectName("photo")

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.label.setText(_translate("MainWindow", "<html><head/><body><p align=\"center\"><span style=\" font-size:36pt; font-weight:600;\">T</span><span style=\" font-size:36pt; font-weight:600; vertical-align:sub;\">0</span><span style=\" font-size:36pt; font-weight:600;\"> Statistics</span></p></body></html>"))
        self.numSelectedFiles.setText(_translate("MainWindow", "<html><head/><body><p><span style=\" font-size:24pt;\">TextLabel</span></p></body></html>"))
        self.return_2.setText(_translate("MainWindow", "Return"))
        self.save.setText(_translate("MainWindow", "Save"))
        self.new_2.setText(_translate("MainWindow", "New"))
        self.reselect.setText(_translate("MainWindow", "Reselect"))
        item = self.tableWidget.verticalHeaderItem(0)
        item.setText(_translate("MainWindow", "OG_mean"))
        item = self.tableWidget.verticalHeaderItem(1)
        item.setText(_translate("MainWindow", "OG_STD"))
        item = self.tableWidget.verticalHeaderItem(2)
        item.setText(_translate("MainWindow", "mean"))
        item = self.tableWidget.verticalHeaderItem(3)
        item.setText(_translate("MainWindow", "STD"))
        item = self.tableWidget.horizontalHeaderItem(0)
        item.setText(_translate("MainWindow", "Ar 36"))
        item = self.tableWidget.horizontalHeaderItem(1)
        item.setText(_translate("MainWindow", "Ar 37"))
        item = self.tableWidget.horizontalHeaderItem(2)
        item.setText(_translate("MainWindow", "Ar 38"))
        item = self.tableWidget.horizontalHeaderItem(3)
        item.setText(_translate("MainWindow", "Ar 39"))
        item = self.tableWidget.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "Ar 40"))


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

