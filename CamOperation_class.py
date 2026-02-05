# -- coding: utf-8 --
import sys
import threading
import msvcrt
import numpy as np
import time
import sys, os
import datetime
import inspect
import ctypes
import random
from ctypes import *
import cv2
from shared_memory_sender import SharedMemorySender

sys.path.append("../MvImport")

from MvImport.CameraParams_header import *
from MvImport.MvCameraControl_class import *

# 匯入 YOLO 偵測功能
try:
    from detect import detect_objects, draw_custom_boxes
except ImportError:
    print("Warning: detect module not found. AI detection will be disabled.")
    detect_objects = None
    draw_custom_boxes = None

# 匯入 TCP 伺服器功能
try:
    from tcp_server import get_tcp_server
except ImportError:
    print("Warning: tcp_server module not found. TCP functionality will be disabled.")
    get_tcp_server = None

# 匯入 Two-Band Filter 觸發系統
try:
    from simple_tracker import SimpleTracker
    from two_band_filter import TwoBandFilter
except ImportError:
    print("Warning: Two-Band Filter system not found. Trigger system will be disabled.")
    SimpleTracker = None
    TwoBandFilter = None

ai_model = None  # 在這邊先定義一個全域變數

# 在類的開頭添加全局變量引用
shared_memory_sender = None
auto_share_enabled = False

# 新增：獲取AI參數的函數參考
get_ai_parameters_func = None

# 新增：邊界線過濾參數 (比例，0.0 ~ 1.0)
boundary_line_top = 0.25      # 上邊界線位置 (從上往下的比例，預設在上緣 1/4 處)
boundary_line_bottom = 0.75   # 下邊界線位置 (從上往下的比例，預設在下緣 1/4 處)
boundary_filter_enabled = True  # 是否啟用邊界線過濾

def set_boundary_line_positions(top_ratio, bottom_ratio):
    """設定上下邊界線的位置（比例值 0.0 ~ 1.0）"""
    global boundary_line_top, boundary_line_bottom
    boundary_line_top = max(0.0, min(1.0, top_ratio))
    boundary_line_bottom = max(0.0, min(1.0, bottom_ratio))
    print(f"[邊界線] 已更新 - 上線: {boundary_line_top:.2%}, 下線: {boundary_line_bottom:.2%}")

def get_boundary_line_positions():
    """獲取上下邊界線的位置"""
    return boundary_line_top, boundary_line_bottom

def set_boundary_filter_enabled(enabled):
    """設定是否啟用邊界線過濾"""
    global boundary_filter_enabled
    boundary_filter_enabled = enabled
    print(f"[邊界線] 過濾功能: {'啟用' if enabled else '停用'}")

def is_boundary_filter_enabled():
    """檢查邊界線過濾是否啟用"""
    return boundary_filter_enabled

def check_box_touches_boundary_lines(y1, y2, image_height):
    """
    檢查邊界框是否觸碰到上下邊界線
    
    Args:
        y1: 邊界框的上邊緣 y 座標
        y2: 邊界框的下邊緣 y 座標  
        image_height: 影像高度
    
    Returns:
        bool: 如果邊界框觸碰到上線或下線，則回傳 True
    """
    top_line_y = int(image_height * boundary_line_top)
    bottom_line_y = int(image_height * boundary_line_bottom)
    
    touches_top_line = (y1 <= top_line_y <= y2)
    touches_bottom_line = (y1 <= bottom_line_y <= y2)
    
    return touches_top_line or touches_bottom_line

def filter_detections_by_boundary(detections, image_height):
    """
    過濾辨識結果，只保留觸碰到邊界線的物件
    
    Args:
        detections: YOLO 辨識結果
        image_height: 影像高度
    
    Returns:
        list: 過濾後的邊界框資訊 [(class_id, x1, y1, x2, y2, conf), ...]
    """
    filtered_boxes = []
    
    if not detections or len(detections) == 0:
        return filtered_boxes
    
    for detection in detections:
        if hasattr(detection, 'boxes') and detection.boxes is not None:
            boxes = detection.boxes.xyxy.cpu().numpy()
            confs = detection.boxes.conf.cpu().numpy()
            classes = detection.boxes.cls.cpu().numpy()
            
            for (box, conf, cls) in zip(boxes, confs, classes):
                x1, y1, x2, y2 = box
                
                if check_box_touches_boundary_lines(y1, y2, image_height):
                    filtered_boxes.append((int(cls), int(x1), int(y1), int(x2), int(y2), float(conf)))
    
    return filtered_boxes


def set_ai_parameters_func(func):
    """設定獲取AI參數的函數參考"""
    global get_ai_parameters_func
    get_ai_parameters_func = func

def set_ai_model(model):
    global ai_model
    ai_model = model

# 強制關閉執行緒
def Async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")

def Stop_thread(thread):
    Async_raise(thread.ident, SystemExit)

def To_hex_str(num):
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

# 是否是Mono圖像
def Is_mono_data(enGvspPixelType):
    if (PixelType_Gvsp_Mono8 == enGvspPixelType or 
        PixelType_Gvsp_Mono10 == enGvspPixelType or
        PixelType_Gvsp_Mono10_Packed == enGvspPixelType or 
        PixelType_Gvsp_Mono12 == enGvspPixelType or
        PixelType_Gvsp_Mono12_Packed == enGvspPixelType):
        return True
    else:
        return False

# 是否是彩色圖像
def Is_color_data(enGvspPixelType):
    if (PixelType_Gvsp_BayerGR8 == enGvspPixelType or 
        PixelType_Gvsp_BayerRG8 == enGvspPixelType or
        PixelType_Gvsp_BayerGB8 == enGvspPixelType or 
        PixelType_Gvsp_BayerBG8 == enGvspPixelType or
        PixelType_Gvsp_BayerGR10 == enGvspPixelType or 
        PixelType_Gvsp_BayerRG10 == enGvspPixelType or
        PixelType_Gvsp_BayerGB10 == enGvspPixelType or 
        PixelType_Gvsp_BayerBG10 == enGvspPixelType or
        PixelType_Gvsp_BayerGR12 == enGvspPixelType or 
        PixelType_Gvsp_BayerRG12 == enGvspPixelType or
        PixelType_Gvsp_BayerGB12 == enGvspPixelType or 
        PixelType_Gvsp_BayerBG12 == enGvspPixelType or
        PixelType_Gvsp_BayerGR10_Packed == enGvspPixelType or 
        PixelType_Gvsp_BayerRG10_Packed == enGvspPixelType or
        PixelType_Gvsp_BayerGB10_Packed == enGvspPixelType or 
        PixelType_Gvsp_BayerBG10_Packed == enGvspPixelType or
        PixelType_Gvsp_BayerGR12_Packed == enGvspPixelType or 
        PixelType_Gvsp_BayerRG12_Packed == enGvspPixelType or
        PixelType_Gvsp_BayerGB12_Packed == enGvspPixelType or 
        PixelType_Gvsp_BayerBG12_Packed == enGvspPixelType or
        PixelType_Gvsp_YUV422_Packed == enGvspPixelType or 
        PixelType_Gvsp_YUV422_YUYV_Packed == enGvspPixelType):
        return True
    else:
        return False

# Mono圖像轉為python數組
def Mono_numpy(data, nWidth, nHeight):
    data_ = np.frombuffer(data, count=int(nWidth * nHeight), dtype=np.uint8, offset=0)
    data_mono_arr = data_.reshape(nHeight, nWidth)
    numArray = np.zeros([nHeight, nWidth, 1], "uint8")
    numArray[:, :, 0] = data_mono_arr
    return numArray

# 彩色圖像轉為python數組
def Color_numpy(data, nWidth, nHeight):
    data_ = np.frombuffer(data, count=int(nWidth * nHeight * 3), dtype=np.uint8, offset=0)
    data_r = data_[0:nWidth * nHeight * 3:3]
    data_g = data_[1:nWidth * nHeight * 3:3]
    data_b = data_[2:nWidth * nHeight * 3:3]

    data_r_arr = data_r.reshape(nHeight, nWidth)
    data_g_arr = data_g.reshape(nHeight, nWidth)
    data_b_arr = data_b.reshape(nHeight, nWidth)
    numArray = np.zeros([nHeight, nWidth, 3], "uint8")

    numArray[:, :, 0] = data_r_arr
    numArray[:, :, 1] = data_g_arr
    numArray[:, :, 2] = data_b_arr
    return numArray
def set_shared_memory_sender(sender):
    """設置共享記憶體發送器"""
    global shared_memory_sender
    shared_memory_sender = sender

def set_auto_share(enabled):
    """設置是否自動分享圖像"""
    global auto_share_enabled
    auto_share_enabled = enabled

class CameraOperation:
    def __init__(self, obj_cam, st_device_list, n_connect_num=0,
                 b_open_device=False, b_start_grabbing=False,
                 h_thread_handle=None, b_thread_closed=False,
                 st_frame_info=None, b_exit=False, b_save_bmp=False,
                 b_save_jpg=False, buf_save_image=None,
                 n_save_image_size=0, n_win_gui_id=0, frame_rate=0,
                 exposure_time=0, gain=0):
        
        self.obj_cam = obj_cam
        self.st_device_list = st_device_list
        self.n_connect_num = n_connect_num
        self.b_open_device = b_open_device
        self.b_start_grabbing = b_start_grabbing
        self.b_thread_closed = b_thread_closed
        self.st_frame_info = st_frame_info
        self.b_exit = b_exit
        self.b_save_bmp = b_save_bmp
        self.b_save_jpg = b_save_jpg
        self.buf_grab_image = None
        self.buf_grab_image_size = 0
        self.buf_save_image = buf_save_image
        self.n_save_image_size = n_save_image_size
        self.h_thread_handle = h_thread_handle
        self.frame_rate = frame_rate
        self.exposure_time = exposure_time
        self.gain = gain
        self.buf_lock = threading.Lock()
        
        # ========== Two-Band Filter 觸發系統 ==========
        self.tracker = None
        self.two_band_filter = None
        self.enable_trigger_system = False  # 是否啟用觸發系統
        # ==============================================

    def Open_device(self):
        if not self.b_open_device:
            if self.n_connect_num < 0:
                return MV_E_CALLORDER
    
            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(self.st_device_list.pDeviceInfo[int(nConnectionNum)],
                                POINTER(MV_CC_DEVICE_INFO)).contents
            self.obj_cam = MvCamera()
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                return ret
    
            ret = self.obj_cam.MV_CC_OpenDevice()
            if ret != 0:
                return ret
            print("open device successfully!")
            self.b_open_device = True
            self.b_thread_closed = False
    
            # ====== 開啟設備成功後，建議加在這裡 ======
            # 設置白平衡 (1=自動)
            ret = self.obj_cam.MV_CC_SetEnumValue("BalanceWhiteAuto", 1)
            if ret != 0:
                print("set BalanceWhiteAuto failed:", ret)
    
            # 設置 Gamma (1.0 = 標準)
            ret = self.obj_cam.MV_CC_SetFloatValue("Gamma", 1.0)
            if ret != 0:
                print("set Gamma failed:", ret)
            # =======================================
    
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
    
            self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            return MV_OK


    def Start_grabbing(self, winHandle):
        if not self.b_start_grabbing and self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                return ret
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            self.h_thread_handle = threading.Thread(target=CameraOperation.Work_thread, args=(self, winHandle))
            self.h_thread_handle.start()
            self.b_thread_closed = True
            return MV_OK
        return MV_E_CALLORDER

    def Stop_grabbing(self):
        """停止取圖"""
        if self.b_start_grabbing and self.b_open_device:
            # 退出線程
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                return ret
            print("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_exit = True
            return MV_OK
        else:
            return MV_E_CALLORDER

    def Close_device(self):
        """關閉相機"""
        if self.b_open_device:
            # 退出線程
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                return ret

        # 銷毀句柄
        self.obj_cam.MV_CC_DestroyHandle()
        self.b_open_device = False
        self.b_start_grabbing = False
        self.b_exit = True
        print("close device successfully!")
        return MV_OK

    def Set_trigger_mode(self, is_trigger_mode, source="Line0"):
        """設置觸發模式"""
        if not self.b_open_device:
            return MV_E_CALLORDER
    
        if not is_trigger_mode:
            # 關閉觸發（FreeRun）
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 0)
            if ret != 0:
                return ret
        else:
            # 開啟觸發模式
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", 1)
            if ret != 0:
                return ret
    
            # 用字串來設定觸發來源 → 保證對應正確
            if source == "Software":
                ret = self.obj_cam.MV_CC_SetEnumValueByString("TriggerSource", "Software")
            elif source == "Line0":
                ret = self.obj_cam.MV_CC_SetEnumValueByString("TriggerSource", "Line0")
            elif source == "Line1":
                ret = self.obj_cam.MV_CC_SetEnumValueByString("TriggerSource", "Line1")
            else:
                ret = self.obj_cam.MV_CC_SetEnumValueByString("TriggerSource", "Software")
    
            if ret != 0:
                return ret
    
        return MV_OK


    def Trigger_once(self):
        """軟觸發一次"""
        if self.b_open_device:
            return self.obj_cam.MV_CC_SetCommandValue("TriggerSoftware")

    def Get_parameter(self):
        """獲取參數"""
        if self.b_open_device:
            stFloatParam_FrameRate = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_FrameRate), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_exposureTime = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_exposureTime), 0, sizeof(MVCC_FLOATVALUE))
            stFloatParam_gain = MVCC_FLOATVALUE()
            memset(byref(stFloatParam_gain), 0, sizeof(MVCC_FLOATVALUE))

            ret = self.obj_cam.MV_CC_GetFloatValue("AcquisitionFrameRate", stFloatParam_FrameRate)
            if ret != 0:
                return ret
            self.frame_rate = stFloatParam_FrameRate.fCurValue

            ret = self.obj_cam.MV_CC_GetFloatValue("ExposureTime", stFloatParam_exposureTime)
            if ret != 0:
                return ret
            self.exposure_time = stFloatParam_exposureTime.fCurValue

            ret = self.obj_cam.MV_CC_GetFloatValue("Gain", stFloatParam_gain)
            if ret != 0:
                return ret
            self.gain = stFloatParam_gain.fCurValue

            return MV_OK

    def Set_parameter(self, frameRate, exposureTime, gain):
        """設置參數"""
        if '' == frameRate or '' == exposureTime or '' == gain:
            print('show info', 'please type in the text box !')
            return MV_E_PARAMETER
            
        if self.b_open_device:
            ret = self.obj_cam.MV_CC_SetFloatValue("ExposureTime", float(exposureTime))
            if ret != 0:
                print('show error', 'set exposure time fail! ret = ' + To_hex_str(ret))
                return ret
    
            ret = self.obj_cam.MV_CC_SetFloatValue("Gain", float(gain))
            if ret != 0:
                print('show error', 'set gain fail! ret = ' + To_hex_str(ret))
                return ret
    
            ret = self.obj_cam.MV_CC_SetFloatValue("AcquisitionFrameRate", float(frameRate))
            if ret != 0:
                print('show error', 'set acquistion frame rate fail! ret = ' + To_hex_str(ret))
                return ret
    
            print('show info', 'set parameter success!')
            return MV_OK
    
    # ========== Two-Band Filter 觸發系統方法 ==========
    
    def initialize_trigger_system(self, image_width, image_height, lens_type="12mm"):
        """
        初始化 Two-Band Filter 觸發系統
        
        Parameters:
            image_width: 圖像寬度（像素）
            image_height: 圖像高度（像素）
            lens_type: 鏡頭類型 ("12mm" 或 "8mm")
            
        Returns:
            bool: 是否成功初始化
        """
        if SimpleTracker is None or TwoBandFilter is None:
            print("[Camera] Two-Band Filter system not imported. Cannot initialize.")
            return False
        
        try:
            # 初始化追蹤器
            self.tracker = SimpleTracker(
                max_age=15,           # 追蹤失敗後保留 15 帧
                min_hits=3,           # 至少匹配 3 次才視為穩定追蹤
                iou_threshold=0.3     # IoU 閾值
            )
            print("[Camera] SimpleTracker initialized")
            
            # 初始化 Two-Band Filter
            tcp_server = get_tcp_server() if get_tcp_server is not None else None
            
            self.two_band_filter = TwoBandFilter(
                image_width=image_width,
                image_height=image_height,
                lens_type=lens_type,
                confidence_threshold=0.75,
                tracking_timeout_frames=15,
                tcp_server=tcp_server
            )
            print("[Camera] Two-Band Filter initialized")
            
            self.enable_trigger_system = True
            print(f"[Camera] Trigger system initialized successfully ({lens_type}, {image_width}x{image_height})")
            
            return True
            
        except Exception as e:
            print(f"[Camera] Error initializing trigger system: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def disable_trigger_system(self):
        """停用觸發系統"""
        self.enable_trigger_system = False
        print("[Camera] Trigger system disabled")
    
    def enable_trigger_system_func(self):
        """啟用觸發系統"""
        if self.tracker is not None and self.two_band_filter is not None:
            self.enable_trigger_system = True
            print("[Camera] Trigger system enabled")
        else:
            print("[Camera] Trigger system not initialized. Call initialize_trigger_system() first.")
    
    def get_trigger_statistics(self):
        """獲取觸發系統統計資訊"""
        if self.two_band_filter is not None:
            return self.two_band_filter.get_statistics()
        return None
    
    def print_trigger_statistics(self):
        """列印觸發系統統計資訊"""
        if self.two_band_filter is not None:
            self.two_band_filter.print_statistics()
        else:
            print("[Camera] Trigger system not initialized")
    
    # =================================================

    def Work_thread(self, signals):
        """
        相機取圖線程函數 - 完整版本
        包含：
        1. 影像獲取與轉換
        2. AI 辨識處理
        3. 共享記憶體自動發送
        4. 信號發送（更新UI）
        """
        stFrameInfo = MV_FRAME_OUT_INFO_EX()
    
        # 獲取 Payload 大小
        stPayloadSize = MVCC_INTVALUE_EX()
        ret_temp = self.obj_cam.MV_CC_GetIntValueEx("PayloadSize", stPayloadSize)
        if ret_temp != MV_OK:
            print("Get PayloadSize failed!")
            return
        NeedBufSize = int(stPayloadSize.nCurValue)
    
        print("Work thread started...")
    
        while not self.b_exit:
            try:
                # 確保緩衝區足夠大
                if self.buf_grab_image_size < NeedBufSize:
                    self.buf_grab_image = (c_ubyte * NeedBufSize)()
                    self.buf_grab_image_size = NeedBufSize
    
                # 獲取一幀圖像數據
                ret = self.obj_cam.MV_CC_GetOneFrameTimeout(
                    self.buf_grab_image, 
                    self.buf_grab_image_size, 
                    stFrameInfo, 
                    1000  # 超時時間 1000ms
                )
    
                if ret == 0:  # 成功獲取圖像
                    # 更新幀信息
                    self.st_frame_info = stFrameInfo
    
                    # 獲取緩存鎖，保護共享數據
                    self.buf_lock.acquire()
                    try:
                        # 確保保存緩衝區足夠大
                        if (self.buf_save_image is None or 
                            self.n_save_image_size < self.st_frame_info.nFrameLen):
                            self.buf_save_image = (c_ubyte * self.st_frame_info.nFrameLen)()
                            self.n_save_image_size = self.st_frame_info.nFrameLen
    
                        # 複製圖像數據到保存緩衝區
                        cdll.msvcrt.memcpy(
                            byref(self.buf_save_image), 
                            self.buf_grab_image, 
                            self.st_frame_info.nFrameLen
                        )
                    finally:
                        self.buf_lock.release()
    
                    # 打印幀信息
                    print(f"Frame: {self.st_frame_info.nFrameNum}, "
                          f"Size: {self.st_frame_info.nWidth}x{self.st_frame_info.nHeight}, "
                          f"PixelType: {self.st_frame_info.enPixelType}")
    
                    # ========================================
                    # 第一步：影像格式轉換（從 Bayer/Mono 轉為 BGR）
                    # ========================================
                    try:
                        raw_image = np.asarray(self.buf_grab_image).reshape(
                            (self.st_frame_info.nHeight, self.st_frame_info.nWidth)
                        )
                        
                        # 根據像素格式進行轉換
                        if Is_color_data(self.st_frame_info.enPixelType):
                            # 彩色圖像 - 從 Bayer 格式轉換為 BGR
                            if self.st_frame_info.enPixelType == PixelType_Gvsp_BayerRG8:
                                image_bgr = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_RG2BGR)
                            elif self.st_frame_info.enPixelType == PixelType_Gvsp_BayerGR8:
                                image_bgr = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_GR2BGR)
                            elif self.st_frame_info.enPixelType == PixelType_Gvsp_BayerGB8:
                                image_bgr = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_GB2BGR)
                            elif self.st_frame_info.enPixelType == PixelType_Gvsp_BayerBG8:
                                image_bgr = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_BG2BGR)
                            else:
                                # 默認使用 RG8
                                image_bgr = cv2.cvtColor(raw_image, cv2.COLOR_BAYER_RG2BGR)
                        elif Is_mono_data(self.st_frame_info.enPixelType):
                            # 單色影像轉換為 3 通道供後續處理
                            mono_array = Mono_numpy(
                                self.buf_save_image, 
                                self.st_frame_info.nWidth, 
                                self.st_frame_info.nHeight
                            )
                            image_bgr = cv2.cvtColor(mono_array.squeeze(), cv2.COLOR_GRAY2BGR)
                        else:
                            # 未知格式，跳過此幀
                            print(f"Unsupported pixel format: {self.st_frame_info.enPixelType}")
                            continue
                        
                    except Exception as e:
                        print(f"Image conversion error: {e}")
                        continue
                    
                    # ========================================
                    # 第二步：共享記憶體自動發送（如果啟用）
                    # ========================================
                    if auto_share_enabled and shared_memory_sender is not None:
                        try:
                            # 複製圖像以避免干擾後續處理
                            image_for_sharing = image_bgr.copy()
                            
                            # 執行您需要的預處理（例如翻轉）
                            # 注意：這裡的翻轉是針對共享記憶體的，不影響AI辨識
                            image_for_sharing = cv2.flip(image_for_sharing, 1)  # 左右翻轉
                            
                            # 發送到共享記憶體
                            if hasattr(shared_memory_sender, 'trigger_count'):
                                shared_memory_sender.trigger_count += 1
                                trigger_count = shared_memory_sender.trigger_count
                            else:
                                shared_memory_sender.trigger_count = 1
                                trigger_count = 1
                            
                            shared_memory_sender.send_image(image_for_sharing, trigger_count)
                            
                            print(f"[共享記憶體] 已自動發送第 {trigger_count} 幀")
                            
                        except Exception as e:
                            print(f"[共享記憶體] 發送失敗: {e}")
    
                    # ========================================
                    # 第三步：AI 辨識處理（如果啟用）
                    # ========================================
                    if ai_model is not None and detect_objects is not None:
                        try:
                            # 轉換為 RGB 供 YOLO 使用
                            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                            
                            # 執行左右翻轉（針對 AI 辨識）
                            image_rgb = cv2.flip(image_rgb, 1)
                            
                            # 儲存圖像（可選）
                            save_dir = r"D:\savefile"
                            today = datetime.datetime.now().strftime("%Y%m%d")
                            save_dir = os.path.join(save_dir, today)
                            os.makedirs(save_dir, exist_ok=True)
                            
                            now = datetime.datetime.now()
                            timestamp = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
                            filename = os.path.join(save_dir, f"image_{timestamp}.jpg")
                            cv2.imwrite(filename, cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
                            
                            # 獲取當前的AI參數
                            conf_thres = 0.4  # 默認值
                            imgsz = 1280      # 默認值
                            
                            if get_ai_parameters_func is not None:
                                try:
                                    conf_thres, imgsz = get_ai_parameters_func()
                                except Exception as e:
                                    print(f"Error getting AI parameters, using defaults: {e}")
                            
                            # 執行 AI 辨識
                            results = detect_objects(ai_model, image_rgb, conf_thres=conf_thres, imgsz=imgsz)
                            
                            # ========================================
                            # Two-Band Filter 觸發系統處理
                            # ========================================
                            if self.enable_trigger_system and self.tracker is not None and self.two_band_filter is not None:
                                try:
                                    # 1. 物體追蹤
                                    tracker_results = self.tracker.update(results)
                                    
                                    # 2. 轉換格式給 Two-Band Filter
                                    # tracker_results: [(track_id, bbox, confidence, class_id), ...]
                                    # 轉換為: [(track_id, [x1, y1, x2, y2, conf, class_id]), ...]
                                    filter_input = [
                                        (track_id, np.concatenate([bbox, [conf, cls]]))
                                        for track_id, bbox, conf, cls in tracker_results
                                    ]
                                    
                                    # 3. Two-Band Filter 處理（觸發判斷）
                                    filter_result = self.two_band_filter.process_frame(
                                        detections=results,
                                        tracker_results=filter_input
                                    )
                                    
                                    # 4. 檢查觸發結果
                                    if filter_result.get('triggered_this_frame'):
                                        triggered_count = len(filter_result['triggered_this_frame'])
                                        print(f"[TriggerSystem] Triggered {triggered_count} objects this frame")
                                        
                                        # 列印每個觸發物體的詳細資訊
                                        for trigger in filter_result['triggered_this_frame']:
                                            print(f"  → Track {trigger['track_id']}: "
                                                  f"Class={trigger['class_id']}, "
                                                  f"Pos=({trigger['cx']:.1f}, {trigger['cy']:.1f}), "
                                                  f"Conf={trigger['confidence']:.2f}")
                                    
                                    # 注意：氣吹指令已經由 blow_controller 自動發送到 TCP
                                    # 不需要在這裡再次發送
                                    
                                except Exception as e:
                                    print(f"[TriggerSystem] Error in Two-Band Filter processing: {e}")
                                    import traceback
                                    traceback.print_exc()
                            
                            else:
                                # ========================================
                                # 原有的 TCP 發送方式（不使用觸發系統）
                                # ========================================
                                # 發送辨識結果到 TCP 服務器
                                if get_tcp_server is not None:
                                    tcp_server = get_tcp_server()
                                    if tcp_server:
                                        tcp_server.send_detection_result(
                                            results, 
                                            self.st_frame_info.nWidth, 
                                            self.st_frame_info.nHeight
                                        )

                            # 準備辨識結果文字
                            detection_text_result = f"Frame: {self.st_frame_info.nFrameNum}\n"
                            detection_text_result += f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n"
                            detection_text_result += "------------------------------------\n"
    
                            if results and hasattr(results[0], 'boxes') and len(results[0].boxes) > 0:
                                # 在影像上繪製檢測框
                                if draw_custom_boxes is not None:
                                    processed_image = draw_custom_boxes(image_rgb.copy(), results)
                                else:
                                    processed_image = image_rgb.copy()
    
                                # 準備文字輸出結果
                                detection_text_result += f"檢測到 {len(results[0].boxes)} 個物件:\n"
                                for i, box in enumerate(results[0].boxes):
                                    class_id = int(box.cls.item())
                                    conf = box.conf.item()
                                    # 獲取邊界框座標
                                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                                    detection_text_result += (
                                        f"  - 物件 {i+1}: Class ID={class_id}, "
                                        f"信心度={conf:.3f}, "
                                        f"位置=({x1:.0f},{y1:.0f})-({x2:.0f},{y2:.0f})\n"
                                    )
                            else:
                                processed_image = image_rgb.copy()
                                detection_text_result += "未檢測到任何物件。\n"
    
                            # 發送處理後的影像信號（帶辨識框的）
                            if hasattr(signals, 'processed_image_ready'):
                                # 轉回 BGR 供 Qt 顯示
                                processed_image_bgr = cv2.cvtColor(processed_image, cv2.COLOR_RGB2BGR)
                                signals.processed_image_ready.emit(processed_image_bgr)
    
                            # 發送原始影像信號（用於相機控制頁面顯示）
                            if hasattr(signals, 'original_image_ready'):
                                # 發送翻轉後的 BGR 圖像
                                original_display = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                                signals.original_image_ready.emit(original_display)
    
                            # 發送文字結果信號
                            if hasattr(signals, 'detection_results_ready'):
                                signals.detection_results_ready.emit(detection_text_result)
    
                        except Exception as e:
                            print(f"AI Detection error: {e}")
                            if hasattr(signals, 'detection_results_ready'):
                                error_text = f"Frame: {self.st_frame_info.nFrameNum}\n"
                                error_text += f"AI 辨識時發生錯誤: {str(e)}\n"
                                signals.detection_results_ready.emit(error_text)
                    
                    else:
                        # ========================================
                        # AI 模型未載入時的處理
                        # ========================================
                        # 僅發送原始影像
                        if hasattr(signals, 'original_image_ready'):
                            # 翻轉後發送
                            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
                            image_rgb = cv2.flip(image_rgb, 1)
                            display_image = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR)
                            signals.original_image_ready.emit(display_image)
                        
                        if hasattr(signals, 'detection_results_ready'):
                            no_ai_text = f"Frame: {self.st_frame_info.nFrameNum}\n"
                            no_ai_text += "AI 模型未載入。\n"
                            signals.detection_results_ready.emit(no_ai_text)
    
                else:
                    # ========================================
                    # 獲取圖像失敗的處理
                    # ========================================
                    print(f"Get frame failed, ret = {To_hex_str(ret)}")
    
                    if ret == MV_E_NODATA:
                        print("No data available")
                    elif ret == MV_E_TIMEOUT:
                        print("Get frame timeout")
                    else:
                        print(f"Unknown error: {ret}")
    
                    time.sleep(0.01)  # 短暫休眠避免 CPU 佔用過高
                    continue
                
            except Exception as e:
                print(f"Work thread exception: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(0.01)
                continue
            
        # ========================================
        # 線程結束清理
        # ========================================
        print("Work thread finished.")
        if hasattr(self, 'buf_grab_image') and self.buf_grab_image is not None:
            del self.buf_grab_image
        if hasattr(self, 'buf_save_image') and self.buf_save_image is not None:
            del self.buf_save_image

    def Save_jpg(self):
        """保存 JPG 圖像"""
        if self.buf_save_image is None:
            return

        # 獲取緩存鎖
        self.buf_lock.acquire()

        file_path = str(self.st_frame_info.nFrameNum) + ".jpg"

        stSaveParam = MV_SAVE_IMG_TO_FILE_PARAM()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType
        stSaveParam.nWidth = self.st_frame_info.nWidth
        stSaveParam.nHeight = self.st_frame_info.nHeight
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Jpeg
        stSaveParam.nQuality = 80
        stSaveParam.pImagePath = file_path.encode('ascii')
        stSaveParam.iMethodValue = 2
        ret = self.obj_cam.MV_CC_SaveImageToFile(stSaveParam)

        self.buf_lock.release()
        return ret

    def Save_Bmp(self):
        """保存 BMP 圖像"""
        if self.buf_save_image is None:
            return

        # 獲取緩存鎖
        self.buf_lock.acquire()

        file_path = str(self.st_frame_info.nFrameNum) + ".bmp"

        stSaveParam = MV_SAVE_IMG_TO_FILE_PARAM()
        stSaveParam.enPixelType = self.st_frame_info.enPixelType
        stSaveParam.nWidth = self.st_frame_info.nWidth
        stSaveParam.nHeight = self.st_frame_info.nHeight
        stSaveParam.nDataLen = self.st_frame_info.nFrameLen
        stSaveParam.pData = cast(self.buf_save_image, POINTER(c_ubyte))
        stSaveParam.enImageType = MV_Image_Bmp
        stSaveParam.nQuality = 8
        stSaveParam.pImagePath = file_path.encode('ascii')
        stSaveParam.iMethodValue = 2
        ret = self.obj_cam.MV_CC_SaveImageToFile(stSaveParam)

        self.buf_lock.release()
        return ret