# integrated_system.py
"""
整合系統範例
結合 YOLO、SimpleTracker 和 Two-Band Filter 的完整流程
"""

import cv2
import numpy as np
import time
from typing import Optional
from simple_tracker import SimpleTracker
from two_band_filter import TwoBandFilter
from tcp_server import get_tcp_server, start_tcp_server


class IntegratedTriggerSystem:
    """整合觸發系統"""
    
    def __init__(self,
                 image_width: int,
                 image_height: int,
                 lens_type: str = "12mm",
                 yolo_model = None,
                 tcp_server = None):
        """
        初始化整合系統
        
        Parameters:
            image_width: 圖像寬度
            image_height: 圖像高度
            lens_type: 鏡頭類型 ("12mm" 或 "8mm")
            yolo_model: YOLO 模型實例
            tcp_server: TCP 伺服器實例
        """
        self.image_width = image_width
        self.image_height = image_height
        self.yolo_model = yolo_model
        
        # 初始化追蹤器
        self.tracker = SimpleTracker(
            max_age=15,           # 追蹤失敗後保留 15 帧
            min_hits=3,           # 至少匹配 3 次才視為穩定追蹤
            iou_threshold=0.3     # IoU 閾值
        )
        
        # 初始化 Two-Band Filter
        self.filter_system = TwoBandFilter(
            image_width=image_width,
            image_height=image_height,
            lens_type=lens_type,
            confidence_threshold=0.75,
            tracking_timeout_frames=15,
            tcp_server=tcp_server
        )
        
        print("\n" + "="*60)
        print("INTEGRATED TRIGGER SYSTEM INITIALIZED")
        print("="*60)
        print(f"Image Size: {image_width} x {image_height}")
        print(f"Lens Type: {lens_type}")
        print(f"YOLO Model: {'Loaded' if yolo_model else 'Not loaded'}")
        print(f"TCP Server: {'Connected' if tcp_server else 'Not connected'}")
        print("="*60 + "\n")
    
    def process_frame(self, frame: np.ndarray, visualize: bool = False) -> dict:
        """
        處理單帧影像
        
        Parameters:
            frame: 輸入影像
            visualize: 是否返回視覺化結果
            
        Returns:
            dict: 包含處理結果和視覺化影像（可選）
        """
        result = {
            'detections': None,
            'tracker_results': [],
            'filter_result': {},
            'vis_frame': None
        }
        
        # 1. YOLO 偵測
        if self.yolo_model is not None:
            try:
                detections = self.yolo_model(frame, verbose=False)
                result['detections'] = detections
            except Exception as e:
                print(f"[IntegratedSystem] YOLO detection error: {e}")
                detections = None
        else:
            detections = None
        
        # 2. 物體追蹤
        if detections is not None:
            try:
                tracker_results = self.tracker.update(detections)
                result['tracker_results'] = tracker_results
            except Exception as e:
                print(f"[IntegratedSystem] Tracking error: {e}")
                tracker_results = []
        else:
            tracker_results = []
        
        # 3. Two-Band Filter 觸發處理
        if tracker_results:
            try:
                # 轉換追蹤結果為 Two-Band Filter 格式
                # tracker_results: [(track_id, bbox, confidence, class_id), ...]
                # filter_format: [(track_id, [x1, y1, x2, y2, conf, class_id]), ...]
                filter_input = [
                    (track_id, np.concatenate([bbox, [conf, cls]]))
                    for track_id, bbox, conf, cls in tracker_results
                ]
                
                filter_result = self.filter_system.process_frame(
                    detections=detections,
                    tracker_results=filter_input
                )
                result['filter_result'] = filter_result
            except Exception as e:
                print(f"[IntegratedSystem] Filter processing error: {e}")
                result['filter_result'] = {}
        
        # 4. 視覺化（可選）
        if visualize:
            vis_frame = frame.copy()
            
            # 繪製區域邊界
            vis_frame = self.filter_system.visualize_zones(vis_frame)
            
            # 繪製追蹤結果
            if tracker_results:
                filter_input = [
                    (track_id, np.concatenate([bbox, [conf, cls]]))
                    for track_id, bbox, conf, cls in tracker_results
                ]
                vis_frame = self.filter_system.draw_tracks(vis_frame, filter_input)
            
            # 繪製統計資訊
            vis_frame = self._draw_statistics(vis_frame, result)
            
            result['vis_frame'] = vis_frame
        
        return result
    
    def _draw_statistics(self, frame: np.ndarray, result: dict) -> np.ndarray:
        """
        在影像上繪製統計資訊
        
        Parameters:
            frame: 輸入影像
            result: 處理結果
            
        Returns:
            帶有統計資訊的影像
        """
        h, w = frame.shape[:2]
        
        # 創建半透明背景
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (350, 150), (0, 0, 0), -1)
        frame = cv2.addWeighted(overlay, 0.5, frame, 0.5, 0)
        
        # 繪製統計文字
        y_offset = 35
        line_height = 25
        
        # 追蹤器統計
        tracker_stats = self.tracker.get_statistics()
        cv2.putText(frame, f"Active Tracks: {tracker_stats['active_tracks']}", 
                    (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += line_height
        
        cv2.putText(frame, f"Total Tracks: {tracker_stats['total_tracks']}", 
                    (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += line_height
        
        # Two-Band Filter 統計
        if 'filter_result' in result and result['filter_result']:
            filter_result = result['filter_result']
            triggered = len(filter_result.get('triggered_this_frame', []))
            
            cv2.putText(frame, f"Triggered: {triggered}", 
                        (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 
                        (0, 255, 255) if triggered > 0 else (255, 255, 255), 2)
            y_offset += line_height
            
            cv2.putText(frame, f"Frame: {filter_result.get('frame_count', 0)}", 
                        (20, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame
    
    def run_with_camera(self, camera_operation, visualize: bool = True):
        """
        使用相機運行系統（整合到 CamOperation_class）
        
        Parameters:
            camera_operation: CamOperation 實例
            visualize: 是否顯示視覺化
        """
        print("\n[IntegratedSystem] Running with camera...")
        print("Press 'q' to quit, 's' to show statistics\n")
        
        try:
            while True:
                # 從相機獲取影像（假設有 get_latest_frame 方法）
                if hasattr(camera_operation, 'get_latest_frame'):
                    frame = camera_operation.get_latest_frame()
                    
                    if frame is not None:
                        # 處理這一帧
                        result = self.process_frame(frame, visualize=visualize)
                        
                        # 顯示視覺化結果
                        if visualize and result['vis_frame'] is not None:
                            cv2.imshow("Integrated Trigger System", result['vis_frame'])
                        
                        # 檢查鍵盤輸入
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            break
                        elif key == ord('s'):
                            self.print_statistics()
                
                time.sleep(0.01)  # 避免 CPU 過載
                
        except KeyboardInterrupt:
            print("\n[IntegratedSystem] Stopped by user")
        finally:
            if visualize:
                cv2.destroyAllWindows()
            self.print_statistics()
    
    def run_with_video(self, video_path: str, visualize: bool = True):
        """
        使用影片檔案運行系統
        
        Parameters:
            video_path: 影片檔案路徑
            visualize: 是否顯示視覺化
        """
        print(f"\n[IntegratedSystem] Running with video: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        
        if not cap.isOpened():
            print(f"[IntegratedSystem] Error: Cannot open video {video_path}")
            return
        
        try:
            frame_count = 0
            
            while True:
                ret, frame = cap.read()
                
                if not ret:
                    print("\n[IntegratedSystem] End of video")
                    break
                
                # 調整影像大小（如果需要）
                if frame.shape[1] != self.image_width or frame.shape[0] != self.image_height:
                    frame = cv2.resize(frame, (self.image_width, self.image_height))
                
                # 處理這一帧
                result = self.process_frame(frame, visualize=visualize)
                
                # 顯示視覺化結果
                if visualize and result['vis_frame'] is not None:
                    cv2.imshow("Integrated Trigger System", result['vis_frame'])
                
                # 檢查鍵盤輸入
                key = cv2.waitKey(30) & 0xFF
                if key == ord('q'):
                    break
                elif key == ord('s'):
                    self.print_statistics()
                
                frame_count += 1
                
        except KeyboardInterrupt:
            print("\n[IntegratedSystem] Stopped by user")
        finally:
            cap.release()
            if visualize:
                cv2.destroyAllWindows()
            self.print_statistics()
    
    def get_statistics(self) -> dict:
        """獲取所有統計資訊"""
        return {
            'tracker': self.tracker.get_statistics(),
            'filter': self.filter_system.get_statistics()
        }
    
    def print_statistics(self) -> None:
        """列印統計資訊"""
        stats = self.get_statistics()
        
        print("\n" + "="*60)
        print("INTEGRATED SYSTEM STATISTICS")
        print("="*60)
        
        print("\n[TRACKER]")
        print(f"  Total Tracks:  {stats['tracker']['total_tracks']}")
        print(f"  Active Tracks: {stats['tracker']['active_tracks']}")
        print(f"  Frames:        {stats['tracker']['frame_count']}")
        
        print("\n[TWO-BAND FILTER]")
        filter_stats = stats['filter']
        print(f"  Frames:        {filter_stats['frame_count']}")
        print(f"  Triggers:      {filter_stats['trigger_count']}")
        print(f"  Active Tracks: {filter_stats['active_tracks']}")
        print(f"  Triggered Trk: {filter_stats['triggered_tracks']}")
        
        if 'blow_stats' in filter_stats:
            blow_stats = filter_stats['blow_stats']
            print(f"\n[BLOW CONTROLLER]")
            print(f"  Total Blows:   {blow_stats['total_blows']}")
            print(f"  Successful:    {blow_stats['successful']} ({blow_stats['success_rate']:.1f}%)")
            print(f"  Failed:        {blow_stats['failed']}")
        
        print("="*60 + "\n")


def create_demo_video():
    """創建一個演示影片用於測試"""
    print("Creating demo video...")
    
    width, height = 640, 480
    fps = 30
    duration = 10  # 秒
    
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out = cv2.VideoWriter('demo_video.mp4', fourcc, fps, (width, height))
    
    # 創建移動的物體
    num_frames = fps * duration
    
    for i in range(num_frames):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        
        # 繪製背景
        frame[:] = (50, 50, 50)
        
        # 繪製一個從上往下移動的矩形
        y = int((i / num_frames) * height)
        x = width // 2 - 25
        
        cv2.rectangle(frame, (x, y), (x + 50, y + 50), (0, 255, 0), -1)
        
        # 添加文字
        cv2.putText(frame, f"Frame {i}", (10, 30), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        out.write(frame)
    
    out.release()
    print("Demo video created: demo_video.mp4")


def main():
    """主函數"""
    print("\n" + "="*80)
    print(" "*20 + "INTEGRATED TRIGGER SYSTEM")
    print("="*80 + "\n")
    
    print("Options:")
    print("1. Test with demo video (no YOLO)")
    print("2. Test with YOLO model")
    print("3. Create demo video")
    
    choice = input("\nSelect option (1-3): ").strip()
    
    if choice == "1":
        # 測試無 YOLO 模型（僅視覺化）
        print("\n[WARNING] Testing without YOLO model (visualization only)")
        
        system = IntegratedTriggerSystem(
            image_width=640,
            image_height=480,
            lens_type="12mm"
        )
        
        # 檢查是否有演示影片
        import os
        if not os.path.exists("demo_video.mp4"):
            create_demo_video()
        
        system.run_with_video("demo_video.mp4", visualize=True)
        
    elif choice == "2":
        # 使用 YOLO 模型
        print("\nLoading YOLO model...")
        
        try:
            from ultralytics import YOLO
            
            model_path = input("Enter YOLO model path (e.g., yolov8n.pt): ").strip()
            if not model_path:
                model_path = "yolov8n.pt"
            
            yolo_model = YOLO(model_path)
            print(f"YOLO model loaded: {model_path}")
            
            # 啟動 TCP 伺服器
            print("Starting TCP server...")
            start_tcp_server(host='localhost', port=8888)
            tcp_server = get_tcp_server()
            
            # 創建系統
            system = IntegratedTriggerSystem(
                image_width=640,
                image_height=480,
                lens_type="12mm",
                yolo_model=yolo_model,
                tcp_server=tcp_server
            )
            
            # 選擇輸入源
            print("\nInput source:")
            print("1. Video file")
            print("2. Webcam")
            
            source_choice = input("Select (1-2): ").strip()
            
            if source_choice == "1":
                video_path = input("Enter video path: ").strip()
                if not video_path:
                    if not os.path.exists("demo_video.mp4"):
                        create_demo_video()
                    video_path = "demo_video.mp4"
                
                system.run_with_video(video_path, visualize=True)
            else:
                # 使用攝像頭
                cap = cv2.VideoCapture(0)
                if cap.isOpened():
                    print("Using webcam...")
                    # 這裡可以添加攝像頭處理邏輯
                    cap.release()
                else:
                    print("Cannot open webcam")
            
        except ImportError:
            print("Error: Ultralytics YOLO not installed")
            print("Install with: pip install ultralytics")
        except Exception as e:
            print(f"Error: {e}")
    
    elif choice == "3":
        create_demo_video()
    
    else:
        print("Invalid option")


if __name__ == "__main__":
    main()
