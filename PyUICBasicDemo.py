# -*- coding: utf-8 -*-

from PyQt5 import QtCore, QtGui, QtWidgets


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(747, 540)
        self.centralWidget = QtWidgets.QWidget(MainWindow)
        self.centralWidget.setObjectName("centralWidget")
        
        # 使用水平布局作為主布局
        self.mainHorizontalLayout = QtWidgets.QHBoxLayout(self.centralWidget)
        self.mainHorizontalLayout.setContentsMargins(10, 10, 10, 10)
        self.mainHorizontalLayout.setSpacing(10)
        
        # 左側：顯示區域（設定拉伸因子讓它佔據更多空間）
        self.widgetDisplay = QtWidgets.QWidget()
        self.widgetDisplay.setObjectName("widgetDisplay")
        self.widgetDisplay.setMinimumSize(QtCore.QSize(400, 300))
        self.widgetDisplay.setStyleSheet("background-color: #2b2b2b; border: 1px solid #555;")
        self.mainHorizontalLayout.addWidget(self.widgetDisplay, 3)  # 拉伸因子為3
        
        # 右側：垂直布局包含所有控制區域
        self.rightVerticalLayout = QtWidgets.QVBoxLayout()
        self.rightVerticalLayout.setSpacing(10)
        
        # 設備選擇下拉框
        self.ComboDevices = QtWidgets.QComboBox()
        self.ComboDevices.setObjectName("ComboDevices")
        self.ComboDevices.setMinimumHeight(30)
        self.rightVerticalLayout.addWidget(self.ComboDevices)
        
        # 初始化群組
        self.groupInit = QtWidgets.QGroupBox()
        self.groupInit.setObjectName("groupInit")
        self.groupInit.setMinimumWidth(250)
        self.gridLayoutWidget = QtWidgets.QWidget(self.groupInit)
        self.gridLayout = QtWidgets.QGridLayout(self.groupInit)
        self.gridLayout.setContentsMargins(11, 11, 11, 11)
        self.gridLayout.setSpacing(6)
        self.gridLayout.setObjectName("gridLayout")
        
        self.bnEnum = QtWidgets.QPushButton()
        self.bnEnum.setObjectName("bnEnum")
        self.bnEnum.setMinimumHeight(35)
        self.gridLayout.addWidget(self.bnEnum, 0, 0, 1, 2)
        
        self.bnOpen = QtWidgets.QPushButton()
        self.bnOpen.setObjectName("bnOpen")
        self.bnOpen.setMinimumHeight(35)
        self.gridLayout.addWidget(self.bnOpen, 1, 0, 1, 1)
        
        self.bnClose = QtWidgets.QPushButton()
        self.bnClose.setEnabled(False)
        self.bnClose.setObjectName("bnClose")
        self.bnClose.setMinimumHeight(35)
        self.gridLayout.addWidget(self.bnClose, 1, 1, 1, 1)
        
        self.bnLoadModel = QtWidgets.QPushButton()
        self.bnLoadModel.setObjectName("bnLoadModel")
        self.bnLoadModel.setMinimumHeight(35)
        self.gridLayout.addWidget(self.bnLoadModel, 2, 0, 1, 2)
        
        self.rightVerticalLayout.addWidget(self.groupInit)
        
        # 採集群組
        self.groupGrab = QtWidgets.QGroupBox()
        self.groupGrab.setEnabled(False)
        self.groupGrab.setObjectName("groupGrab")
        self.gridLayout_2 = QtWidgets.QGridLayout(self.groupGrab)
        self.gridLayout_2.setContentsMargins(11, 11, 11, 11)
        self.gridLayout_2.setSpacing(6)
        self.gridLayout_2.setObjectName("gridLayout_2")
        
        self.radioContinueMode = QtWidgets.QRadioButton()
        self.radioContinueMode.setObjectName("radioContinueMode")
        self.gridLayout_2.addWidget(self.radioContinueMode, 0, 0, 1, 1)
        
        self.radioTriggerMode = QtWidgets.QRadioButton()
        self.radioTriggerMode.setObjectName("radioTriggerMode")
        self.gridLayout_2.addWidget(self.radioTriggerMode, 0, 1, 1, 1)
        
        self.bnStart = QtWidgets.QPushButton()
        self.bnStart.setEnabled(False)
        self.bnStart.setObjectName("bnStart")
        self.bnStart.setMinimumHeight(35)
        self.gridLayout_2.addWidget(self.bnStart, 1, 0, 1, 1)
        
        self.bnStop = QtWidgets.QPushButton()
        self.bnStop.setEnabled(False)
        self.bnStop.setObjectName("bnStop")
        self.bnStop.setMinimumHeight(35)
        self.gridLayout_2.addWidget(self.bnStop, 1, 1, 1, 1)
        
        self.bnSoftwareTrigger = QtWidgets.QPushButton()
        self.bnSoftwareTrigger.setEnabled(False)
        self.bnSoftwareTrigger.setObjectName("bnSoftwareTrigger")
        self.bnSoftwareTrigger.setMinimumHeight(35)
        self.gridLayout_2.addWidget(self.bnSoftwareTrigger, 2, 0, 1, 2)
        
        self.bnSaveImage = QtWidgets.QPushButton()
        self.bnSaveImage.setEnabled(False)
        self.bnSaveImage.setObjectName("bnSaveImage")
        self.bnSaveImage.setMinimumHeight(35)
        self.gridLayout_2.addWidget(self.bnSaveImage, 3, 0, 1, 2)
        
        self.rightVerticalLayout.addWidget(self.groupGrab)
        
        # 參數群組
        self.groupParam = QtWidgets.QGroupBox()
        self.groupParam.setEnabled(False)
        self.groupParam.setObjectName("groupParam")
        self.gridLayoutParam = QtWidgets.QGridLayout(self.groupParam)
        self.gridLayoutParam.setContentsMargins(11, 11, 11, 11)
        self.gridLayoutParam.setSpacing(6)
        self.gridLayoutParam.setObjectName("gridLayoutParam")
        
        self.label_4 = QtWidgets.QLabel()
        self.label_4.setObjectName("label_4")
        self.gridLayoutParam.addWidget(self.label_4, 0, 0, 1, 1)
        
        self.edtExposureTime = QtWidgets.QLineEdit()
        self.edtExposureTime.setObjectName("edtExposureTime")
        self.edtExposureTime.setMinimumHeight(30)
        self.gridLayoutParam.addWidget(self.edtExposureTime, 0, 1, 1, 1)
        
        self.label_5 = QtWidgets.QLabel()
        self.label_5.setObjectName("label_5")
        self.gridLayoutParam.addWidget(self.label_5, 1, 0, 1, 1)
        
        self.edtGain = QtWidgets.QLineEdit()
        self.edtGain.setObjectName("edtGain")
        self.edtGain.setMinimumHeight(30)
        self.gridLayoutParam.addWidget(self.edtGain, 1, 1, 1, 1)
        
        self.label_6 = QtWidgets.QLabel()
        self.label_6.setObjectName("label_6")
        self.gridLayoutParam.addWidget(self.label_6, 2, 0, 1, 1)
        
        self.edtFrameRate = QtWidgets.QLineEdit()
        self.edtFrameRate.setObjectName("edtFrameRate")
        self.edtFrameRate.setMinimumHeight(30)
        self.gridLayoutParam.addWidget(self.edtFrameRate, 2, 1, 1, 1)
        
        self.bnGetParam = QtWidgets.QPushButton()
        self.bnGetParam.setObjectName("bnGetParam")
        self.bnGetParam.setMinimumHeight(35)
        self.gridLayoutParam.addWidget(self.bnGetParam, 3, 0, 1, 1)
        
        self.bnSetParam = QtWidgets.QPushButton()
        self.bnSetParam.setObjectName("bnSetParam")
        self.bnSetParam.setMinimumHeight(35)
        self.gridLayoutParam.addWidget(self.bnSetParam, 3, 1, 1, 1)
        
        self.gridLayoutParam.setColumnStretch(0, 2)
        self.gridLayoutParam.setColumnStretch(1, 3)
        
        self.rightVerticalLayout.addWidget(self.groupParam)
        
        # 添加彈性空間，讓控制區域保持在上方
        self.rightVerticalLayout.addStretch(1)
        
        # 將右側布局添加到主布局（拉伸因子為1，較小）
        self.mainHorizontalLayout.addLayout(self.rightVerticalLayout, 1)
        
        MainWindow.setCentralWidget(self.centralWidget)
        self.statusBar = QtWidgets.QStatusBar(MainWindow)
        self.statusBar.setObjectName("statusBar")
        MainWindow.setStatusBar(self.statusBar)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "主視窗"))
        self.groupInit.setTitle(_translate("MainWindow", "初始化,(500GCSS)169.254.93.23"))
        self.bnClose.setText(_translate("MainWindow", "關閉設備"))
        self.bnOpen.setText(_translate("MainWindow", "打開設備"))
        self.bnEnum.setText(_translate("MainWindow", "查找設備"))
        self.bnLoadModel.setText(_translate("MainWindow", "載入模型"))
        self.groupGrab.setTitle(_translate("MainWindow", "採集"))
        self.bnSaveImage.setText(_translate("MainWindow", "保存影像"))
        self.radioContinueMode.setText(_translate("MainWindow", "連續模式"))
        self.radioTriggerMode.setText(_translate("MainWindow", "觸發模式"))
        self.bnStop.setText(_translate("MainWindow", "停止採集"))
        self.bnStart.setText(_translate("MainWindow", "開始採集"))
        self.bnSoftwareTrigger.setText(_translate("MainWindow", "軟觸發一次"))
        self.groupParam.setTitle(_translate("MainWindow", "參數"))
        self.label_6.setText(_translate("MainWindow", "幀率"))
        self.edtGain.setText(_translate("MainWindow", "0"))
        self.label_5.setText(_translate("MainWindow", "增益"))
        self.label_4.setText(_translate("MainWindow", "曝光"))
        self.edtExposureTime.setText(_translate("MainWindow", "0"))
        self.bnGetParam.setText(_translate("MainWindow", "獲取參數"))
        self.bnSetParam.setText(_translate("MainWindow", "設定參數"))
        self.edtFrameRate.setText(_translate("MainWindow", "0"))