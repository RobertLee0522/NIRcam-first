# -- coding: utf-8 --

from PyQt5.QtWidgets import *
from PyQt5.QtCore import QTimer, QObject, pyqtSignal, Qt
from PyQt5.QtGui import QImage, QPixmap
from CamOperation_class import CameraOperation
from MvImport.MvCameraControl_class import *
from MvImport.MvErrorDefine_const import *
from MvImport.CameraParams_header import *
from PyUICBasicDemo import Ui_MainWindow
from detect import load_model
from tcp_server import start_tcp_server, get_tcp_server, stop_tcp_server
import sys
import numpy as np
import cv2

# --- 新增: 用於跨執行緒通訊的訊號發射器 ---
class SignalEmitter(QObject):
    original_image_ready = pyqtSignal(np.ndarray)
    processed_image_ready = pyqtSignal(np.ndarray)
    detection_results_ready = pyqtSignal(str)

# --- 全域變數 ---
# 請將此路徑替換為您自己的模型權重檔路徑
ai_model = load_model(r"C:\Users\user1\Desktop\Yolov11\train20\weights\best.pt")
from CamOperation_class import set_ai_model
set_ai_model(ai_model)

def TxtWrapBy(start_str, end, all):
    start = all.find(start_str)
    if start >= 0:
        start += len(start_str)
        end = all.find(end, start)
        if end >= 0:
            return all[start:end].strip()

def ToHexStr(num):
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2 ** 32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr
    return hexStr

if __name__ == "__main__":
    # --- 全域變數 ---
    deviceList = MV_CC_DEVICE_INFO_LIST()
    cam = MvCamera()
    nSelCamIndex = 0
    obj_cam_operation = 0
    isOpen = False
    isGrabbing = False
    isCalibMode = True
    tcp_status_timer = None
    signals = SignalEmitter() # 實例化訊號發射器

    def xFunc(event):
        global nSelCamIndex
        nSelCamIndex = TxtWrapBy("[", "]", ui.ComboDevices.get())

    def enum_devices():
        global deviceList
        global obj_cam_operation

        deviceList = MV_CC_DEVICE_INFO_LIST()
        ret = MvCamera.MV_CC_EnumDevices(MV_GIGE_DEVICE | MV_USB_DEVICE, deviceList)
        if ret != 0:
            strError = "Enum devices fail! ret = :" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            return ret

        if deviceList.nDeviceNum == 0:
            QMessageBox.warning(mainWindow, "Info", "Find no device", QMessageBox.Ok)
            return ret
        print("Find %d devices!" % deviceList.nDeviceNum)

        devList = []
        for i in range(0, deviceList.nDeviceNum):
            mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE:
                chUserDefinedName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName:
                    if 0 == per:
                        break
                    chUserDefinedName += chr(per)
                chModelName = ""
                for per in mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName:
                    if 0 == per:
                        break
                    chModelName += chr(per)
                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                devList.append(
                    f"[{i}]GigE: {chUserDefinedName} {chModelName}({nip1}.{nip2}.{nip3}.{nip4})")
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                chUserDefinedName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName:
                    if per == 0:
                        break
                    chUserDefinedName += chr(per)
                chModelName = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName:
                    if 0 == per:
                        break
                    chModelName += chr(per)
                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber += chr(per)
                devList.append(f"[{i}]USB: {chUserDefinedName} {chModelName}({strSerialNumber})")

        ui.ComboDevices.clear()
        ui.ComboDevices.addItems(devList)
        ui.ComboDevices.setCurrentIndex(0)

    def load_ai_model():
        global ai_model
        weight_path, _ = QFileDialog.getOpenFileName(mainWindow, "選擇 YOLO 權重檔", "", "PyTorch Weights (*.pt)")
        if weight_path:
            ai_model = load_model(weight_path)
            if ai_model:
                set_ai_model(ai_model)
                QMessageBox.information(mainWindow, "AI 模型", "模型載入成功！")
            else:
                QMessageBox.warning(mainWindow, "AI 模型", "模型載入失敗！")

    def start_tcp_server_func():
        """啟動TCP伺服器"""
        try:
            host = ui.edtTcpHost.text() if ui.edtTcpHost.text() else 'localhost'
            port = int(ui.edtTcpPort.text()) if ui.edtTcpPort.text() else 8888
            
            if start_tcp_server(host, port):
                QMessageBox.information(mainWindow, "TCP 伺服器", f"TCP伺服器已啟動\n位址: {host}:{port}\n等待 LabVIEW 連接...")
                ui.bnStartTCP.setEnabled(False)
                ui.bnStopTCP.setEnabled(True)
                
                global tcp_status_timer
                if tcp_status_timer is None:
                    tcp_status_timer = QTimer()
                    tcp_status_timer.timeout.connect(update_tcp_status)
                tcp_status_timer.start(1000)
                
            else:
                QMessageBox.warning(mainWindow, "TCP 伺服器", "TCP伺服器啟動失敗！")
        except Exception as e:
            QMessageBox.warning(mainWindow, "TCP 伺服器", f"啟動失敗: {str(e)}")

    def stop_tcp_server_func():
        """停止TCP伺服器"""
        try:
            stop_tcp_server()
            QMessageBox.information(mainWindow, "TCP 伺服器", "TCP伺服器已停止")
            ui.bnStartTCP.setEnabled(True)
            ui.bnStopTCP.setEnabled(False)
            
            global tcp_status_timer
            if tcp_status_timer:
                tcp_status_timer.stop()
                
            if hasattr(ui, 'lblTcpStatus'):
                ui.lblTcpStatus.setText("TCP: 未連接")
                
        except Exception as e:
            QMessageBox.warning(mainWindow, "TCP 伺服器", f"停止失敗: {str(e)}")

    def update_tcp_status():
        """更新TCP連接狀態"""
        tcp_server = get_tcp_server()
        if tcp_server and hasattr(ui, 'lblTcpStatus'):
            status = tcp_server.get_connection_status()
            if status['client_connected']:
                ui.lblTcpStatus.setText(f"TCP: LabVIEW已連接 (觸發次數: {status['trigger_count']})")
                ui.lblTcpStatus.setStyleSheet("color: green; font-weight: bold;")
            elif status['server_running']:
                ui.lblTcpStatus.setText("TCP: 等待LabVIEW連接...")
                ui.lblTcpStatus.setStyleSheet("color: orange; font-weight: bold;")
            else:
                ui.lblTcpStatus.setText("TCP: 伺服器未啟動")
                ui.lblTcpStatus.setStyleSheet("color: red; font-weight: bold;")

    def open_device():
        global deviceList, nSelCamIndex, obj_cam_operation, isOpen
        if isOpen:
            QMessageBox.warning(mainWindow, "Error", 'Camera is Running!', QMessageBox.Ok)
            return MV_E_CALLORDER
        nSelCamIndex = ui.ComboDevices.currentIndex()
        if nSelCamIndex < 0:
            QMessageBox.warning(mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)
            return MV_E_CALLORDER
        obj_cam_operation = CameraOperation(cam, deviceList, nSelCamIndex)
        ret = obj_cam_operation.Open_device()
        if 0 != ret:
            strError = "Open device failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            isOpen = False
        else:
            set_continue_mode()
            get_param()
            isOpen = True
            enable_controls()

    def start_grabbing():
        global obj_cam_operation, isGrabbing, signals
        # 修改: 傳遞 signals 物件，而不是 winId
        ret = obj_cam_operation.Start_grabbing(signals)
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            isGrabbing = True
            enable_controls()

    def stop_grabbing():
        global obj_cam_operation, isGrabbing
        ret = obj_cam_operation.Stop_grabbing()
        if ret != 0:
            strError = "Stop grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            isGrabbing = False
            enable_controls()

    def close_device():
        global isOpen, isGrabbing, obj_cam_operation
        if isGrabbing:
            stop_grabbing()
        if isOpen:
            obj_cam_operation.Close_device()
            isOpen = False
        isGrabbing = False
        enable_controls()

    def set_continue_mode():
        ret = obj_cam_operation.Set_trigger_mode(False)
        if ret == 0:
            ui.radioContinueMode.setChecked(True)
            ui.radioTriggerMode.setChecked(False)
            ui.bnSoftwareTrigger.setEnabled(False)

    def set_software_trigger_mode():
        ret = obj_cam_operation.Set_trigger_mode(True)
        if ret == 0:
            ui.radioContinueMode.setChecked(False)
            ui.radioTriggerMode.setChecked(True)
            ui.bnSoftwareTrigger.setEnabled(isGrabbing)

    def trigger_once():
        ret = obj_cam_operation.Trigger_once()
        if ret != 0:
            QMessageBox.warning(mainWindow, "Error", "TriggerSoftware failed", QMessageBox.Ok)

    def save_bmp():
        ret = obj_cam_operation.Save_Bmp()
        if ret != MV_OK:
            QMessageBox.warning(mainWindow, "Error", "Save BMP failed", QMessageBox.Ok)

    def get_param():
        ret = obj_cam_operation.Get_parameter()
        if ret == 0:
            ui.edtExposureTime.setText(f"{obj_cam_operation.exposure_time:.2f}")
            ui.edtGain.setText(f"{obj_cam_operation.gain:.2f}")
            ui.edtFrameRate.setText(f"{obj_cam_operation.frame_rate:.2f}")

    def set_param():
        ret = obj_cam_operation.Set_parameter(ui.edtFrameRate.text(), ui.edtExposureTime.text(), ui.edtGain.text())
        return ret

    def enable_controls():
        ui.groupGrab.setEnabled(isOpen)
        ui.groupParam.setEnabled(isOpen)
        ui.bnOpen.setEnabled(not isOpen)
        ui.bnClose.setEnabled(isOpen)
        ui.bnStart.setEnabled(isOpen and (not isGrabbing))
        ui.bnStop.setEnabled(isOpen and isGrabbing)
        ui.bnSoftwareTrigger.setEnabled(isGrabbing and ui.radioTriggerMode.isChecked())
        ui.bnSaveImage.setEnabled(isOpen and isGrabbing)

    # --- 新增: 更新 UI 的槽函式 ---
    def update_display(image_array, display_label):
        """將 numpy array 轉換為 QPixmap 並顯示在 QLabel 上"""
        try:
            height, width, channel = image_array.shape
            bytes_per_line = 3 * width
            q_image = QImage(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB).data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            display_label.setPixmap(pixmap.scaled(display_label.size(), aspectRatioMode=Qt.KeepAspectRatio, transformMode=Qt.SmoothTransformation))
        except Exception as e:
            print(f"Error updating display: {e}")

    def update_original_display(image_array):
        """更新「相機控制」頁面的原始影像"""
        if ui.originalDisplayLabel.isVisible():
            update_display(image_array, ui.originalDisplayLabel)

    def update_processed_display(image_array):
        """更新「TCP控制」頁面的辨識後影像"""
        if ui.processedDisplayLabel.isVisible():
            update_display(image_array, ui.processedDisplayLabel)

    def update_detection_text(result_string):
        """更新「TCP控制」頁面的辨識結果文字"""
        ui.detectionResultText.setText(result_string)

    # --- 主程式 ---
    app = QApplication(sys.argv)
    mainWindow = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(mainWindow)
    mainWindow.setWindowTitle("工業相機 AI 檢測應用")

    # --- 修改 UI 佈局 ---
    
    # 1. 在「相機控制」頁面新增一個 QLabel 用於顯示原始影像
    #    我們將它放在原本的 widgetDisplay 內部
    ui.originalDisplayLabel = QLabel(ui.widgetDisplay)
    ui.originalDisplayLabel.setObjectName("originalDisplayLabel")
    ui.originalDisplayLabel.setText("相機影像將顯示於此")
    ui.originalDisplayLabel.setAlignment(Qt.AlignCenter)
    display_layout = QVBoxLayout(ui.widgetDisplay)
    display_layout.addWidget(ui.originalDisplayLabel)

    # 2. 建立新的 TCP 控制頁面佈局
    original_widget = mainWindow.centralWidget()
    tabs = QTabWidget()
    tabs.addTab(original_widget, "相機控制")

    tcp_widget = QWidget()
    main_tcp_layout = QVBoxLayout(tcp_widget)

    # 辨識結果顯示區 (上方)
    detection_display_group = QGroupBox("模型辨識結果")
    detection_display_layout = QVBoxLayout()
    
    ui.processedDisplayLabel = QLabel()
    ui.processedDisplayLabel.setObjectName("processedDisplayLabel")
    ui.processedDisplayLabel.setText("AI 辨識影像將顯示於此")
    ui.processedDisplayLabel.setAlignment(Qt.AlignCenter)
    ui.processedDisplayLabel.setMinimumSize(640, 480) # 設定最小尺寸
    detection_display_layout.addWidget(ui.processedDisplayLabel, 1) # 影像佔用更大空間

    ui.detectionResultText = QTextEdit()
    ui.detectionResultText.setObjectName("detectionResultText")
    ui.detectionResultText.setReadOnly(True)
    ui.detectionResultText.setText("辨識結果文字...")
    ui.detectionResultText.setMaximumHeight(150) # 限制文字區塊高度
    detection_display_layout.addWidget(ui.detectionResultText)

    detection_display_group.setLayout(detection_display_layout)
    main_tcp_layout.addWidget(detection_display_group)

    # TCP 伺服器控制區 (下方)
    tcp_control_group = QGroupBox("TCP 伺服器控制")
    tcp_control_layout = QVBoxLayout()
    
    ip_layout = QHBoxLayout()
    ip_layout.addWidget(QLabel("主機:"))
    ui.edtTcpHost = QLineEdit("192.168.1.3")#localhost
    ip_layout.addWidget(ui.edtTcpHost)
    ip_layout.addWidget(QLabel("埠號:"))
    ui.edtTcpPort = QLineEdit("8888")
    ip_layout.addWidget(ui.edtTcpPort)
    tcp_control_layout.addLayout(ip_layout)
    
    button_layout = QHBoxLayout()
    ui.bnStartTCP = QPushButton("啟動 TCP 伺服器")
    ui.bnStopTCP = QPushButton("停止 TCP 伺服器")
    ui.bnStopTCP.setEnabled(False)
    button_layout.addWidget(ui.bnStartTCP)
    button_layout.addWidget(ui.bnStopTCP)
    tcp_control_layout.addLayout(button_layout)
    
    ui.lblTcpStatus = QLabel("TCP: 未連接")
    ui.lblTcpStatus.setStyleSheet("color: red; font-weight: bold;")
    tcp_control_layout.addWidget(ui.lblTcpStatus)
    
    format_label = QLabel("傳送格式: class_id,center_x,center_y,width,height,trigger_index")
    format_label.setStyleSheet("color: blue; font-size: 10px;")
    tcp_control_layout.addWidget(format_label)
    
    tcp_control_group.setLayout(tcp_control_layout)
    main_tcp_layout.addWidget(tcp_control_group)

    tabs.addTab(tcp_widget, "TCP 控制與辨識結果")
    mainWindow.setCentralWidget(tabs)


    # --- 連接按鈕事件 ---
    ui.bnEnum.clicked.connect(enum_devices)
    ui.bnOpen.clicked.connect(open_device)
    ui.bnClose.clicked.connect(close_device)
    ui.bnStart.clicked.connect(start_grabbing)
    ui.bnStop.clicked.connect(stop_grabbing)
    ui.bnSoftwareTrigger.clicked.connect(trigger_once)
    ui.radioTriggerMode.clicked.connect(set_software_trigger_mode)
    ui.radioContinueMode.clicked.connect(set_continue_mode)
    ui.bnGetParam.clicked.connect(get_param)
    ui.bnSetParam.clicked.connect(set_param)
    ui.bnSaveImage.clicked.connect(save_bmp)
    ui.bnLoadModel.clicked.connect(load_ai_model)
    ui.bnStartTCP.clicked.connect(start_tcp_server_func)
    ui.bnStopTCP.clicked.connect(stop_tcp_server_func)

    # --- 新增: 連接訊號與槽 ---
    signals.original_image_ready.connect(update_original_display)
    signals.processed_image_ready.connect(update_processed_display)
    signals.detection_results_ready.connect(update_detection_text)

    # --- 顯示與清理 ---
    mainWindow.show()
    
    def cleanup():
        print("Cleaning up resources...")
        stop_tcp_server()
        close_device()
        print("Cleanup finished.")
    
    app.aboutToQuit.connect(cleanup)
    
    sys.exit(app.exec_())