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
from CamOperation_class import set_ai_model, set_ai_parameters_func
from shared_memory_sender import SharedMemorySender # 引入共享內存發送器
from CamOperation_class import set_shared_memory_sender, set_auto_share

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

# 新增全域變數用於控制 AI 檢測參數
ai_conf_thres = 0.4  # 默認信心指數閾值
ai_imgsz = 1280      # 默認影像大小

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
    # 新增全局變量用於共享內存發送器
    global global_sender
    global_sender = None
    global shared_trigger_count
    shared_trigger_count = 0
    # 配置共享內存的目標 (請根據您的接收端程式調整)
    global RECEIVER_HOST
    global RECEIVER_PORT
    RECEIVER_HOST = '127.0.0.1' 
    RECEIVER_PORT = 9999

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

    def update_ai_parameters():
        """更新AI檢測參數"""
        global ai_conf_thres, ai_imgsz
        
        try:
            # 獲取信心指數閾值 (0.0 - 1.0)
            conf_value = float(ui.edtConfThres.text())
            if 0.0 <= conf_value <= 1.0:
                ai_conf_thres = conf_value
            else:
                QMessageBox.warning(mainWindow, "參數錯誤", "信心指數必須介於 0.0 到 1.0 之間！")
                ui.edtConfThres.setText(str(ai_conf_thres))
                return
            
            # 獲取影像大小 (建議值: 320, 640, 1280)
            imgsz_value = int(ui.edtImgSize.text())
            if imgsz_value > 0 and imgsz_value % 32 == 0:  # YOLO要求是32的倍數
                ai_imgsz = imgsz_value
            else:
                QMessageBox.warning(mainWindow, "參數錯誤", "影像大小必須是正數且為32的倍數！\n建議值: 320, 640, 1280")
                ui.edtImgSize.setText(str(ai_imgsz))
                return
                
            QMessageBox.information(mainWindow, "參數更新", 
                f"AI檢測參數已更新：\n信心指數: {ai_conf_thres}\n影像大小: {ai_imgsz}")
            
            # 更新顯示的當前參數
            update_ai_param_display()
            
        except ValueError:
            QMessageBox.warning(mainWindow, "參數錯誤", "請輸入有效的數值！")

    def reset_ai_parameters():
        """重設AI檢測參數為預設值"""
        global ai_conf_thres, ai_imgsz
        ai_conf_thres = 0.4
        ai_imgsz = 1280
        ui.edtConfThres.setText(str(ai_conf_thres))
        ui.edtImgSize.setText(str(ai_imgsz))
        update_ai_param_display()
        QMessageBox.information(mainWindow, "參數重設", "AI檢測參數已重設為預設值！")

    def update_ai_param_display():
        """更新顯示目前的AI參數"""
        ui.lblCurrentParams.setText(f"目前參數 - 信心指數: {ai_conf_thres}, 影像大小: {ai_imgsz}")

    def get_ai_parameters():
        """供其他模組使用的函數，回傳目前的AI參數"""
        return ai_conf_thres, ai_imgsz

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

    def update_shared_memory_ui():
        """更新共享記憶體連接狀態"""
        global global_sender, shared_trigger_count
        
        if global_sender is not None:
            # 檢查 trigger_count 屬性
            try:
                count = getattr(global_sender, 'trigger_count', 0)
                ui.lblSharedMemStatus.setText(f"共享記憶體: 已啟動 (已傳送 {count} 幀)")
                ui.lblSharedMemStatus.setStyleSheet("color: green; font-weight: bold;")
            except Exception as e:
                ui.lblSharedMemStatus.setText(f"共享記憶體: 已啟動 (狀態未知)")
                ui.lblSharedMemStatus.setStyleSheet("color: orange; font-weight: bold;")
        else:
            ui.lblSharedMemStatus.setText("共享記憶體: 未啟動")
            ui.lblSharedMemStatus.setStyleSheet("color: red; font-weight: bold;")

    def start_shared_memory():
       """啟動共享記憶體發送器"""
       global global_sender, shared_trigger_count

       try:
           host = ui.edtSharedMemHost.text() or '127.0.0.1'
           port = int(ui.edtSharedMemPort.text() or '9999')
           print(f"嘗試連接到 {host}:{port}") 
           if global_sender is None:
               # 創建發送器實例
               global_sender = SharedMemorySender(host, port)
               if not global_sender.is_connected():
                   QMessageBox.warning(mainWindow, "連接失敗", 
                        "無法連接到接收端！\n請確認：\n"
                        "1. 接收端程式 (receiver.py) 已啟動\n"
                        "2. IP 和端口設置正確")
                   global_sender = None
                   return
 
               # 初始化計數器
               if not hasattr(global_sender, 'trigger_count'):
                   global_sender.trigger_count = 0
               shared_trigger_count = 0

               # 將發送器設置到 CamOperation_class
               set_shared_memory_sender(global_sender)

               QMessageBox.information(mainWindow, "共享記憶體", 
                   f"共享記憶體已啟動！\n\n"
                   f"目標位址: {host}:{port}\n"
                   f"請確保接收端程式 (receiver.py) 已在運行\n\n"
                   f"提示: 可在「共享記憶體控制」頁籤中\n"
                   f"啟用「自動分享」或使用「手動分享」")

               ui.bnStartSharedMem.setEnabled(False)
               ui.bnStopSharedMem.setEnabled(True)
               ui.chkAutoShare.setEnabled(True)
               ui.bnManualShare.setEnabled(True)

               # 更新UI狀態
               update_shared_memory_ui()
           else:
               QMessageBox.warning(mainWindow, "共享記憶體", "發送器已在運行中！")

       except Exception as e:
           QMessageBox.critical(mainWindow, "共享記憶體", f"啟動失敗:\n{str(e)}")
           import traceback
           traceback.print_exc()

    def stop_shared_memory():
        """停止共享記憶體發送器"""
        global global_sender

        try:
            if global_sender is not None:
                # 停用自動分享
                set_auto_share(False)
                ui.chkAutoShare.setChecked(False)

                # 清除發送器引用
                set_shared_memory_sender(None)

                # 關閉連接
                try:
                    global_sender.close()
                except Exception as e:
                    print(f"關閉發送器時出錯: {e}")

                global_sender = None

                QMessageBox.information(mainWindow, "共享記憶體", "共享記憶體已停止")
                ui.bnStartSharedMem.setEnabled(True)
                ui.bnStopSharedMem.setEnabled(False)
                ui.chkAutoShare.setEnabled(False)
                ui.bnManualShare.setEnabled(False)

                # 更新UI狀態
                update_shared_memory_ui()
            else:
                QMessageBox.information(mainWindow, "共享記憶體", "共享記憶體未在運行")

        except Exception as e:
            QMessageBox.critical(mainWindow, "共享記憶體", f"停止失敗:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def toggle_auto_share():
        """切換自動分享模式"""
        global global_sender

        enabled = ui.chkAutoShare.isChecked()

        if enabled and global_sender is None:
            QMessageBox.warning(mainWindow, "自動分享", "請先啟動共享記憶體！")
            ui.chkAutoShare.setChecked(False)
            return

        if not isGrabbing:
            QMessageBox.warning(mainWindow, "自動分享", "請先開始取像！")
            ui.chkAutoShare.setChecked(False)
            return

        set_auto_share(enabled)

        if enabled:
            QMessageBox.information(mainWindow, "自動分享", 
                "✅ 已啟用自動分享\n\n"
                "每一幀圖像都會自動發送到共享記憶體\n"
                "接收端可實時接收圖像數據")
        else:
            QMessageBox.information(mainWindow, "自動分享", 
                "⏸ 已停用自動分享\n\n"
                "可使用「手動分享」按鈕手動發送圖像")

    def manual_share_current_frame():
        """手動分享當前幀"""
        global global_sender, shared_trigger_count

        if not isGrabbing:
            QMessageBox.warning(mainWindow, "錯誤", "請先開始取像！")
            return

        if global_sender is None:
            QMessageBox.warning(mainWindow, "錯誤", "請先啟動共享記憶體！")
            return

        try:
            # 調用原有的手動分享函數
            transfer_image_and_flip()

            # 獲取當前計數
            count = getattr(global_sender, 'trigger_count', shared_trigger_count)

            QMessageBox.information(mainWindow, "手動分享", 
                f"✅ 已發送圖像\n\n"
                f"觸發次數: {count}\n"
                f"接收端應已收到數據")

        except Exception as e:
            QMessageBox.critical(mainWindow, "手動分享", f"發送失敗:\n{str(e)}")
            import traceback
            traceback.print_exc()
    def transfer_image_and_flip():
        """
        手動觸發：獲取當前幀，處理並共享
        這個函數用於手動分享按鈕
        """
        global obj_cam_operation, global_sender, shared_trigger_count

        if not isGrabbing or obj_cam_operation.buf_save_image is None:
            raise Exception("相機未在取像或緩衝區為空")

        try:
            # 獲取緩衝區鎖，防止取圖線程同時寫入
            obj_cam_operation.buf_lock.acquire() 

            # 1. 從 C 緩衝區創建 NumPy 數組
            st_info = obj_cam_operation.st_frame_info

            if st_info is None:
                raise Exception("幀信息為空")

            # 創建原始圖像數組
            raw_data = np.ctypeslib.as_array(
                obj_cam_operation.buf_save_image, 
                shape=(st_info.nHeight, st_info.nWidth)
            )

            # 複製數據
            image_bayer = raw_data.copy()
            obj_cam_operation.buf_lock.release()

            # 2. 轉換圖像格式
            if st_info.enPixelType == PixelType_Gvsp_BayerRG8:
                image_bgr = cv2.cvtColor(image_bayer, cv2.COLOR_BAYER_RG2BGR)
            elif st_info.enPixelType == PixelType_Gvsp_BayerGR8:
                image_bgr = cv2.cvtColor(image_bayer, cv2.COLOR_BAYER_GR2BGR)
            elif st_info.enPixelType == PixelType_Gvsp_BayerGB8:
                image_bgr = cv2.cvtColor(image_bayer, cv2.COLOR_BAYER_GB2BGR)
            elif st_info.enPixelType == PixelType_Gvsp_BayerBG8:
                image_bgr = cv2.cvtColor(image_bayer, cv2.COLOR_BAYER_BG2BGR)
            elif st_info.enPixelType == PixelType_Gvsp_Mono8:
                image_bgr = cv2.cvtColor(image_bayer, cv2.COLOR_GRAY2BGR)
            else:
                raise Exception(f"不支援的像素格式: {st_info.enPixelType}")

        except Exception as e:
            # 確保在異常情況下釋放鎖
            if obj_cam_operation.buf_lock.locked():
                obj_cam_operation.buf_lock.release()
            raise e

        # 3. 圖像處理：執行翻轉操作
        image_bgr = cv2.flip(image_bgr, 1)  # 左右翻轉

        # 4. 發送到共享記憶體
        shared_trigger_count += 1
        global_sender.send_image(image_bgr, shared_trigger_count)

        # 同步計數器
        if hasattr(global_sender, 'trigger_count'):
            global_sender.trigger_count = shared_trigger_count

        print(f"[手動分享] 已發送圖像，觸發次數: {shared_trigger_count}")


    def open_device():
        global deviceList, nSelCamIndex, obj_cam_operation, isOpen
        #共享記憶體全域變數
        global global_sender
        global shared_trigger_count # 確保可以訪問
        
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
        # 修改: 傳送 signals 物件，而不是 winId
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
        global obj_cam_operation
        global global_sender # 確保可以訪問
        if isGrabbing:
            stop_grabbing()
        if isOpen:
            obj_cam_operation.Close_device()
            isOpen = False
        # **【新增邏輯】** 清理共享內存資源
        if global_sender is not None:
            global_sender.close()
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
        # 共享記憶體控制
        # 只有在取像且共享記憶體已啟動時才能手動分享
        ui.bnManualShare.setEnabled(isOpen and isGrabbing and global_sender is not None)
            # 自動分享只有在共享記憶體啟動時才能勾選
        if global_sender is None:
            ui.chkAutoShare.setEnabled(False)
            ui.chkAutoShare.setChecked(False)
        elif not isGrabbing:
            # 如果停止取像，自動取消自動分享
            if ui.chkAutoShare.isChecked():
                ui.chkAutoShare.setChecked(False)
                set_auto_share(False)

    # --- 新增: 更新 UI 的槽函式 ---
    def update_display(image_array, display_label):
        """將 numpy array 轉換為 QPixmap 並顯示在 QLabel 上"""
        try:
            height, width, channel = image_array.shape
            bytes_per_line = 3 * width
            q_image = QImage(image_array.data, width, height, bytes_per_line, QImage.Format_RGB888)
            #q_image = QImage(cv2.cvtColor(image_array, cv2.COLOR_BGR2RGB).data, width, height, bytes_per_line, QImage.Format_RGB888)
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

    # === 新增 AI 檢測參數控制區 ===
    ai_param_group = QGroupBox("AI 檢測參數設定")
    ai_param_layout = QVBoxLayout()
    
    # 參數輸入區
    param_input_layout = QHBoxLayout()
    param_input_layout.addWidget(QLabel("信心指數 (0.0-1.0):"))
    ui.edtConfThres = QLineEdit(str(ai_conf_thres))
    ui.edtConfThres.setMaximumWidth(80)
    param_input_layout.addWidget(ui.edtConfThres)
    
    param_input_layout.addWidget(QLabel("影像大小:"))
    ui.edtImgSize = QLineEdit(str(ai_imgsz))
    ui.edtImgSize.setMaximumWidth(80)
    param_input_layout.addWidget(ui.edtImgSize)
    
    ui.bnUpdateAIParams = QPushButton("更新參數")
    ui.bnResetAIParams = QPushButton("重設預設值")
    param_input_layout.addWidget(ui.bnUpdateAIParams)
    param_input_layout.addWidget(ui.bnResetAIParams)
    param_input_layout.addStretch()
    
    ai_param_layout.addLayout(param_input_layout)
    
    # 目前參數顯示
    ui.lblCurrentParams = QLabel(f"目前參數 - 信心指數: {ai_conf_thres}, 影像大小: {ai_imgsz}")
    ui.lblCurrentParams.setStyleSheet("color: blue; font-weight: bold;")
    ai_param_layout.addWidget(ui.lblCurrentParams)
    
    # 參數說明
    param_info = QLabel("說明: 信心指數越低檢測越敏感，影像大小影響檢測精度和速度\n建議影像大小: 320 (快速), 640 (平衡), 1280 (精確)")
    param_info.setStyleSheet("color: gray; font-size: 10px;")
    ai_param_layout.addWidget(param_info)
    
    ai_param_group.setLayout(ai_param_layout)
    main_tcp_layout.addWidget(ai_param_group)

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
    
    # === 新增 AI 參數控制按鈕事件 ===
    ui.bnUpdateAIParams.clicked.connect(update_ai_parameters)
    ui.bnResetAIParams.clicked.connect(reset_ai_parameters)

    # --- 新增: 連接訊號與槽 ---
    signals.original_image_ready.connect(update_original_display)
    signals.processed_image_ready.connect(update_processed_display)
    signals.detection_results_ready.connect(update_detection_text)
        # === 共享記憶體控制區塊 ===
    shared_mem_group = QGroupBox("共享記憶體控制（原始圖像分享）")
    shared_mem_layout = QVBoxLayout()
    
    # 連接設定
    connection_layout = QHBoxLayout()
    connection_layout.addWidget(QLabel("接收端 IP:"))
    ui.edtSharedMemHost = QLineEdit("127.0.0.1")
    connection_layout.addWidget(ui.edtSharedMemHost)
    connection_layout.addWidget(QLabel("埠號:"))
    ui.edtSharedMemPort = QLineEdit("9999")
    connection_layout.addWidget(ui.edtSharedMemPort)
    shared_mem_layout.addLayout(connection_layout)
    
    # 控制按鈕
    button_layout = QHBoxLayout()
    ui.bnStartSharedMem = QPushButton("啟動共享記憶體")
    ui.bnStopSharedMem = QPushButton("停止共享記憶體")
    ui.bnStopSharedMem.setEnabled(False)
    ui.bnManualShare = QPushButton("手動分享當前圖像")
    ui.bnManualShare.setEnabled(False)
    button_layout.addWidget(ui.bnStartSharedMem)
    button_layout.addWidget(ui.bnStopSharedMem)
    button_layout.addWidget(ui.bnManualShare)
    shared_mem_layout.addLayout(button_layout)
    
    # 自動分享選項
    ui.chkAutoShare = QCheckBox("自動分享每一幀（實時傳輸）")
    ui.chkAutoShare.setChecked(False)
    ui.chkAutoShare.setEnabled(False)
    shared_mem_layout.addWidget(ui.chkAutoShare)
    
    # 狀態顯示
    ui.lblSharedMemStatus = QLabel("共享記憶體: 未啟動")
    ui.lblSharedMemStatus.setStyleSheet("color: red; font-weight: bold;")
    shared_mem_layout.addWidget(ui.lblSharedMemStatus)
    
    info_label = QLabel("說明: 共享記憶體用於將原始圖像傳送給其他本機程式（如 LabVIEW）")
    info_label.setStyleSheet("color: gray; font-size: 10px;")
    shared_mem_layout.addWidget(info_label)
    
    shared_mem_group.setLayout(shared_mem_layout)
    main_tcp_layout.addWidget(shared_mem_group)

    # 連接共享記憶體相關信號
    ui.bnStartSharedMem.clicked.connect(start_shared_memory)
    ui.bnStopSharedMem.clicked.connect(stop_shared_memory)
    ui.bnManualShare.clicked.connect(manual_share_current_frame)
    ui.chkAutoShare.stateChanged.connect(toggle_auto_share)
    shared_mem_timer = QTimer()
    shared_mem_timer.timeout.connect(update_shared_memory_ui)
    shared_mem_timer.start(1000)  # 每秒更新一次

    # --- 顯示與清理 ---
    mainWindow.show()
    # 設置AI參數函數參考
    set_ai_parameters_func(get_ai_parameters)
    
    def cleanup():
        print("Cleaning up resources...")
        # 停止 TCP 服務器
        try:
            stop_tcp_server()
        except:
            pass
        
        # 停止共享記憶體
        try:
            stop_shared_memory()
        except:
            pass
        
        # 關閉相機
        try:
            close_device()
        except:
            pass
        print("Cleanup finished.")
    
    app.aboutToQuit.connect(cleanup)
    
    sys.exit(app.exec_())