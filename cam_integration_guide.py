# cam_integration_guide.py
"""
整合指南：如何將 SimpleTracker 和 Two-Band Filter 整合到 CamOperation_class.py

這個檔案包含了詳細的整合步驟和修改範例
"""

# ============================================================================
# 步驟 1: 在 CamOperation_class.py 開頭添加 imports
# ============================================================================

IMPORT_CODE = '''
# 在 CamOperation_class.py 的 import 區域添加:

from simple_tracker import SimpleTracker
from two_band_filter import TwoBandFilter
from tcp_server import get_tcp_server
'''

# ============================================================================
# 步驟 2: 在 CameraOperation.__init__ 中添加初始化
# ============================================================================

INIT_CODE = '''
# 在 CameraOperation 類的 __init__ 方法中添加:

class CameraOperation(object):
    def __init__(self, obj_cam, st_device_list, n_connect_num=0,
                 b_open_device=False, b_start_grabbing=False,
                 h_thread_handle=None, b_thread_closed=False,
                 st_frame_info=None, b_exit=False, b_save_bmp=False,
                 b_save_jpg=False, buf_save_image=None,
                 n_save_image_size=0, n_win_gui_id=0, frame_rate=0,
                 exposure_time=0, gain=0):
        
        # ... 現有的初始化代碼 ...
        
        # ========== 新增：Two-Band Filter 系統 ==========
        self.tracker = None
        self.two_band_filter = None
        self.enable_trigger_system = False  # 是否啟用觸發系統
        # ================================================
'''

# ============================================================================
# 步驟 3: 添加初始化方法
# ============================================================================

INITIALIZATION_METHOD = '''
# 在 CameraOperation 類中添加初始化方法:

def initialize_trigger_system(self, image_width, image_height, lens_type="12mm"):
    """
    初始化 Two-Band Filter 觸發系統
    
    Parameters:
        image_width: 圖像寬度（像素）
        image_height: 圖像高度（像素）
        lens_type: 鏡頭類型 ("12mm" 或 "8mm")
    """
    try:
        # 初始化追蹤器
        self.tracker = SimpleTracker(
            max_age=15,
            min_hits=3,
            iou_threshold=0.3
        )
        print("[Camera] SimpleTracker initialized")
        
        # 初始化 Two-Band Filter
        tcp_server = get_tcp_server()
        
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
        
        return True
        
    except Exception as e:
        print(f"[Camera] Error initializing trigger system: {e}")
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
        print("[Camera] Trigger system not initialized")

def get_trigger_statistics(self):
    """獲取觸發系統統計資訊"""
    if self.two_band_filter is not None:
        return self.two_band_filter.get_statistics()
    return None

def print_trigger_statistics(self):
    """列印觸發系統統計資訊"""
    if self.two_band_filter is not None:
        self.two_band_filter.print_statistics()
'''

# ============================================================================
# 步驟 4: 修改 Work_thread 方法
# ============================================================================

WORK_THREAD_MODIFICATION = '''
# 在 Work_thread 方法中，找到 AI 辨識的部分並修改:

def Work_thread(self, signals):
    """相機取圖線程函數"""
    
    # ... 前面的代碼保持不變 ...
    
    while not self.b_exit:
        # ... 獲取影像的代碼 ...
        
        # ========== AI 辨識與觸發系統 ==========
        if ai_model is not None:
            try:
                # YOLO 偵測
                results = ai_model(image_array, verbose=False)
                
                # 如果啟用觸發系統，使用 Two-Band Filter
                if self.enable_trigger_system and self.tracker is not None and self.two_band_filter is not None:
                    
                    # 1. 物體追蹤
                    tracker_results = self.tracker.update(results)
                    
                    # 2. 轉換格式給 Two-Band Filter
                    # tracker_results: [(track_id, bbox, confidence, class_id), ...]
                    # 轉換為: [(track_id, [x1, y1, x2, y2, conf, class_id]), ...]
                    filter_input = [
                        (track_id, np.concatenate([bbox, [conf, cls]]))
                        for track_id, bbox, conf, cls in tracker_results
                    ]
                    
                    # 3. Two-Band Filter 處理
                    filter_result = self.two_band_filter.process_frame(
                        detections=results,
                        tracker_results=filter_input
                    )
                    
                    # 4. 檢查觸發結果
                    if filter_result.get('triggered_this_frame'):
                        triggered_count = len(filter_result['triggered_this_frame'])
                        print(f"[TriggerSystem] Triggered {triggered_count} objects")
                        
                        # 可以在這裡添加額外的處理
                        for trigger in filter_result['triggered_this_frame']:
                            print(f"  - Track {trigger['track_id']}: "
                                  f"Class={trigger['class_id']}, "
                                  f"Pos=({trigger['cx']:.1f}, {trigger['cy']:.1f})")
                    
                    # 5. 使用追蹤結果發送到 TCP（如果需要顯示）
                    # 注意：氣吹指令已經由 blow_controller 自動發送
                    # 這裡只發送用於顯示的資料
                    
                else:
                    # 原有的處理方式（不使用觸發系統）
                    if get_tcp_server is not None:
                        tcp_instance = get_tcp_server()
                        if tcp_instance and tcp_instance.is_connected:
                            tcp_instance.send_detection_result_with_center_and_size(
                                results, image_array.shape[1], image_array.shape[0]
                            )
                
                # 發送信號更新 UI（如果有）
                if signals and hasattr(signals, 'ai_result'):
                    signals.ai_result.emit(results)
                    
            except Exception as e:
                print(f"[Camera] AI processing error: {e}")
                import traceback
                traceback.print_exc()
        
        # ... 後面的代碼保持不變 ...
'''

# ============================================================================
# 步驟 5: 在主程式中使用
# ============================================================================

MAIN_USAGE = '''
# 在主程式中（例如 BasicDemo.py 或 GUI 程式）:

# 1. 確保 TCP 伺服器已啟動
from tcp_server import start_tcp_server, get_tcp_server

start_tcp_server(host='localhost', port=8888)

# 2. 創建相機操作實例（現有代碼）
cam_operation = CameraOperation(...)

# 3. 開啟相機並開始取圖（現有代碼）
cam_operation.Open_device()
cam_operation.Start_grabbing(winHandle)

# 4. 初始化觸發系統（新增）
# 在相機開始取圖後立即初始化
cam_operation.initialize_trigger_system(
    image_width=1280,      # 根據實際相機設定
    image_height=1024,     # 根據實際相機設定
    lens_type="12mm"       # 或 "8mm"
)

# 5. 程式運行...

# 6. 結束時查看統計（可選）
cam_operation.print_trigger_statistics()
'''

# ============================================================================
# 完整的整合檢查清單
# ============================================================================

CHECKLIST = '''
整合檢查清單：

□ 1. 安裝必要的依賴
    pip install scipy numpy opencv-python

□ 2. 確認文件已創建
    ✓ simple_tracker.py
    ✓ track_manager.py
    ✓ blow_controller.py
    ✓ two_band_filter.py

□ 3. 修改 CamOperation_class.py
    □ 添加 imports
    □ 在 __init__ 中添加追蹤器和 Two-Band Filter 變數
    □ 添加 initialize_trigger_system 方法
    □ 修改 Work_thread 方法

□ 4. 修改主程式
    □ 啟動 TCP 伺服器
    □ 在開始取圖後初始化觸發系統

□ 5. 測試
    □ 測試 SimpleTracker 是否正常運作
    □ 測試 Two-Band Filter 觸發邏輯
    □ 檢查 TCP 訊息是否正確發送
    □ 檢查統計資訊是否正確

□ 6. 調優（根據實際情況）
    □ 調整追蹤器參數（max_age, min_hits, iou_threshold）
    □ 調整觸發區域（修改 config_two_band_filter.py）
    □ 調整信度閾值
'''

# ============================================================================
# 主函數
# ============================================================================

def print_integration_guide():
    """列印完整的整合指南"""
    
    print("=" * 80)
    print(" " * 25 + "整合指南")
    print("=" * 80)
    
    print("\n" + "步驟 1: 添加 Imports")
    print("-" * 80)
    print(IMPORT_CODE)
    
    print("\n" + "步驟 2: 修改 __init__")
    print("-" * 80)
    print(INIT_CODE)
    
    print("\n" + "步驟 3: 添加初始化方法")
    print("-" * 80)
    print(INITIALIZATION_METHOD)
    
    print("\n" + "步驟 4: 修改 Work_thread")
    print("-" * 80)
    print(WORK_THREAD_MODIFICATION)
    
    print("\n" + "步驟 5: 主程式使用")
    print("-" * 80)
    print(MAIN_USAGE)
    
    print("\n" + "=" * 80)
    print(CHECKLIST)
    print("=" * 80)
    
    print("\n提示:")
    print("1. 將以上代碼片段整合到對應的檔案中")
    print("2. 建議先在測試環境中驗證")
    print("3. 詳細文檔請參閱 README_TWO_BAND_FILTER.md")
    print()


if __name__ == "__main__":
    print_integration_guide()
