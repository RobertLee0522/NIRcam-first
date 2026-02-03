# example_two_band_filter.py
"""
Two-Band Filter 使用範例
展示如何整合 YOLO、追蹤器和 Two-Band Filter 進行自動觸發
"""

import cv2
import numpy as np
import time
from two_band_filter import TwoBandFilter
from tcp_server import get_tcp_server, start_tcp_server


def simulate_tracker_results():
    """
    模擬追蹤器結果（用於測試）
    實際應用中應該使用真實的 YOLO + ByteTrack/DeepSORT
    
    Returns:
        List: 追蹤結果 [(track_id, [x1, y1, x2, y2, conf, class_id]), ...]
    """
    # 模擬一個物體從上往下移動
    results = []
    
    # Track 1: 從 Y=100 移動到 Y=500
    track_id = 1
    x1, x2 = 300, 400  # 固定 X 位置
    y_positions = [100, 150, 200, 250, 300, 350, 400, 450, 500]
    
    for i, y_center in enumerate(y_positions):
        y1 = y_center - 50
        y2 = y_center + 50
        conf = 0.85
        class_id = 0
        
        results.append([
            (track_id, [x1, y1, x2, y2, conf, class_id])
        ])
    
    return results


def example_with_real_camera():
    """
    實際相機範例
    需要配合 CamOperation_class.py 和 YOLO 模型使用
    """
    print("\n" + "="*60)
    print("TWO-BAND FILTER - REAL CAMERA EXAMPLE")
    print("="*60 + "\n")
    
    # 1. 啟動 TCP 伺服器
    print("Starting TCP server...")
    start_tcp_server(host='localhost', port=8888)
    tcp_server = get_tcp_server()
    time.sleep(1)
    
    # 2. 初始化 Two-Band Filter
    # 這些參數應該從相機獲取
    image_width = 1280
    image_height = 1024
    lens_type = "12mm"  # 或 "8mm"
    
    filter_system = TwoBandFilter(
        image_width=image_width,
        image_height=image_height,
        lens_type=lens_type,
        confidence_threshold=0.75,
        tracking_timeout_frames=15,
        tcp_server=tcp_server
    )
    
    # 3. 主處理迴圈（偽代碼）
    print("Processing frames...")
    print("Press Ctrl+C to stop\n")
    
    try:
        frame_count = 0
        
        # 這裡應該是從相機取得影像的迴圈
        # while camera.is_grabbing():
        #     # 獲取影像
        #     frame = camera.get_frame()
        #     
        #     # YOLO 偵測
        #     detections = yolo_model(frame)
        #     
        #     # 物體追蹤
        #     tracker_results = tracker.update(detections)
        #     
        #     # Two-Band Filter 處理
        #     result = filter_system.process_frame(detections, tracker_results)
        #     
        #     # 視覺化（可選）
        #     vis_frame = filter_system.visualize_zones(frame)
        #     vis_frame = filter_system.draw_tracks(vis_frame, tracker_results)
        #     cv2.imshow("Two-Band Filter", vis_frame)
        #     
        #     frame_count += 1
        #     
        #     if cv2.waitKey(1) & 0xFF == ord('q'):
        #         break
        
        # 模擬處理
        simulated_results = simulate_tracker_results()
        
        for frame_idx, tracker_result in enumerate(simulated_results):
            print(f"\n--- Frame {frame_idx + 1} ---")
            
            # 處理這一帧
            result = filter_system.process_frame(None, tracker_result)
            
            # 顯示結果
            print(f"Active Tracks: {result['active_tracks']}")
            print(f"Triggered: {len(result['triggered_this_frame'])} objects")
            
            for trigger in result['triggered_this_frame']:
                print(f"  → Track {trigger['track_id']}: "
                      f"Class={trigger['class_id']}, "
                      f"Pos=({trigger['cx']:.1f}, {trigger['cy']:.1f}), "
                      f"Conf={trigger['confidence']:.2f}")
            
            time.sleep(0.5)  # 模擬帧間隔
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    
    finally:
        # 4. 顯示統計資訊
        filter_system.print_statistics()
        
        # 5. 清理
        if tcp_server:
            tcp_server.stop_server()


def example_integration_code():
    """
    整合到現有系統的範例代碼
    展示如何修改 CamOperation_class.py 中的 Work_thread
    """
    
    integration_code = '''
# 在 CamOperation_class.py 中的修改範例

# 1. 在文件頂部添加 import
from two_band_filter import TwoBandFilter
from tcp_server import get_tcp_server

# 2. 在 CameraOperation.__init__ 中初始化 Two-Band Filter
class CameraOperation:
    def __init__(self, ...):
        # ... 現有代碼 ...
        
        # 初始化 Two-Band Filter
        self.two_band_filter = None
        
    def initialize_two_band_filter(self, image_width, image_height, lens_type="12mm"):
        """初始化 Two-Band Filter"""
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

# 3. 在 Work_thread 中使用 Two-Band Filter
def Work_thread(self, signals):
    """相機取圖線程函數"""
    
    # 初始化追蹤器（如果尚未初始化）
    # tracker = ByteTrack(...)  # 或 DeepSORT
    
    while not self.b_exit:
        # ... 獲取影像的代碼 ...
        
        # AI 辨識
        if ai_model is not None:
            try:
                results = ai_model(image_array)
                
                # 物體追蹤
                # tracker_results = tracker.update(results)
                
                # 使用 Two-Band Filter 處理
                if self.two_band_filter is not None:
                    filter_result = self.two_band_filter.process_frame(
                        detections=results,
                        tracker_results=tracker_results  # 需要實現追蹤器
                    )
                    
                    # 視覺化（可選）
                    if filter_result['triggered_this_frame']:
                        print(f"[TwoBandFilter] Triggered {len(filter_result['triggered_this_frame'])} objects")
                
                # 發送辨識結果到 LabVIEW
                # tcp_server 發送會由 blow_controller 自動處理
                
            except Exception as e:
                print(f"Error in Two-Band Filter: {e}")
        
        # ... 其他代碼 ...

# 4. 在主程式中初始化
# 在相機開始取圖後
cam_operation.initialize_two_band_filter(
    image_width=1280,
    image_height=1024,
    lens_type="12mm"
)
'''
    
    print("\n" + "="*60)
    print("INTEGRATION CODE EXAMPLE")
    print("="*60)
    print(integration_code)
    print("="*60 + "\n")


def example_visualization():
    """
    視覺化範例
    展示如何繪製區域和追蹤結果
    """
    print("\n" + "="*60)
    print("TWO-BAND FILTER - VISUALIZATION EXAMPLE")
    print("="*60 + "\n")
    
    # 創建一個空白影像
    image_width = 640
    image_height = 480
    image = np.zeros((image_height, image_width, 3), dtype=np.uint8)
    
    # 初始化 filter
    filter_system = TwoBandFilter(
        image_width=image_width,
        image_height=image_height,
        lens_type="12mm"
    )
    
    # 繪製區域
    vis_image = filter_system.visualize_zones(image)
    
    # 顯示
    cv2.imshow("Two-Band Filter Zones", vis_image)
    print("Press any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def main():
    """主函數"""
    print("\n" + "="*80)
    print(" "*20 + "TWO-BAND FILTER EXAMPLES")
    print("="*80 + "\n")
    
    print("Available examples:")
    print("1. Visualization - Show zone boundaries")
    print("2. Simulation - Test with simulated data")
    print("3. Integration Code - Show how to integrate with existing system")
    print("4. Real Camera - Full example (requires camera and YOLO)")
    
    choice = input("\nSelect example (1-4): ").strip()
    
    if choice == "1":
        example_visualization()
    elif choice == "2":
        example_with_real_camera()  # 使用模擬資料
    elif choice == "3":
        example_integration_code()
    elif choice == "4":
        print("\nReal camera example requires:")
        print("- Camera connected via CamOperation_class")
        print("- YOLO model loaded")
        print("- Object tracker (ByteTrack/DeepSORT)")
        print("\nPlease integrate the code shown in option 3.")
    else:
        print("Invalid choice")


if __name__ == "__main__":
    main()
