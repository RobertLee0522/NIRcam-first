# two_band_filter.py
"""
Two-Band Filter 觸發系統
用於傳帶上 PET 廢料的自動分選，透過視野分區確保觸發精度與效率
"""

import numpy as np
import logging
from typing import List, Tuple, Dict, Optional, Any
from track_manager import TrackManager
from blow_controller import BlowController


class TwoBandFilter:
    """Two-Band Filter 主控類"""
    
    def __init__(self, 
                 image_width: int,
                 image_height: int,
                 lens_type: str = "12mm",
                 confidence_threshold: float = 0.75,
                 tracking_timeout_frames: int = 15,
                 tcp_server=None):
        """
        初始化 Two-Band Filter
        
        Parameters:
            image_width: 圖像寬度（像素）
            image_height: 圖像高度（像素）
            lens_type: 鏡頭類型（"12mm" 或 "8mm"）
            confidence_threshold: 信度閾值
            tracking_timeout_frames: 追蹤超時帧數
            tcp_server: TCP 伺服器實例
        """
        self.image_width = image_width
        self.image_height = image_height
        self.lens_type = lens_type
        self.confidence_threshold = confidence_threshold
        
        # 初始化追蹤管理器
        self.track_manager = TrackManager(
            image_height=image_height,
            lens_type=lens_type,
            tracking_timeout_frames=tracking_timeout_frames,
            confidence_threshold=confidence_threshold
        )
        
        # 初始化氣吹控制器
        self.blow_controller = BlowController(
            tcp_server=tcp_server,
            ack_timeout_ms=200,
            blow_delay_ms=(80, 120)
        )
        
        # 區域邊界
        self.trigger_zone_top = image_height * 0.375
        self.trigger_zone_bottom = image_height * 0.625
        
        # 統計資訊
        self.frame_count = 0
        self.detection_count = 0
        self.trigger_count = 0
        self.skip_count = 0  # 因各種原因跳過的次數
        
        # 設置日誌
        self.logger = logging.getLogger("TwoBandFilter")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(name)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        print("\n" + "="*60)
        print("TWO-BAND FILTER INITIALIZED")
        print("="*60)
        print(f"Image Size:      {image_width} x {image_height} pixels")
        print(f"Lens Type:       {lens_type}")
        print(f"Confidence:      ≥ {confidence_threshold}")
        print(f"Trigger Zone:    Y = {self.trigger_zone_top:.1f} ~ {self.trigger_zone_bottom:.1f}")
        print(f"Zone Coverage:   {(self.trigger_zone_bottom - self.trigger_zone_top) / image_height * 100:.1f}% of FOV")
        print("="*60 + "\n")
    
    def set_tcp_server(self, tcp_server) -> None:
        """
        設置 TCP 伺服器實例
        
        Parameters:
            tcp_server: TCP 伺服器實例
        """
        self.blow_controller.set_tcp_server(tcp_server)
    
    def process_frame(self, detections: Any, tracker_results: List[Tuple]) -> Dict:
        """
        處理單帧
        
        Parameters:
            detections: YOLO 偵測結果
            tracker_results: 追蹤器結果 [(track_id, bbox), ...]
                            bbox 格式: [x1, y1, x2, y2] 或 [x1, y1, x2, y2, conf, class_id]
        
        Returns:
            dict: 包含處理結果的字典
        """
        self.frame_count += 1
        self.track_manager.increment_frame()
        
        # 更新所有追蹤狀態
        current_track_ids = set()
        triggered_this_frame = []
        
        for track_result in tracker_results:
            if len(track_result) >= 2:
                track_id = int(track_result[0])
                bbox = track_result[1]
                
                # 處理不同的 bbox 格式
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    
                    # 計算中心點
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    
                    # 獲取信度和類別（從追蹤結果或偵測結果）
                    if len(bbox) >= 6:
                        confidence = float(bbox[4])
                        class_id = int(bbox[5])
                    else:
                        # 從偵測結果中找到對應的信度和類別
                        confidence, class_id = self._find_detection_info(
                            bbox, detections
                        )
                    
                    current_track_ids.add(track_id)
                    
                    # 更新追蹤狀態
                    self.track_manager.update_track(
                        track_id, cx, cy, confidence, class_id
                    )
                    
                    # 檢查是否應該移除（進入 Exit Zone）
                    if self.track_manager.should_remove(track_id):
                        self.track_manager.remove_track(track_id)
                        continue
                    
                    # 檢查觸發條件
                    should_trigger, reason = self._should_trigger(
                        track_id, cx, cy, confidence
                    )
                    
                    if should_trigger:
                        # 發送氣吹指令
                        success = self.blow_controller.send_blow_command(
                            cx=cx,
                            cy=cy,
                            class_id=class_id,
                            track_id=track_id,
                            confidence=confidence,
                            image_width=self.image_width,
                            image_height=self.image_height
                        )
                        
                        if success:
                            self.track_manager.tracks[track_id].triggered = True
                            self.trigger_count += 1
                            triggered_this_frame.append({
                                'track_id': track_id,
                                'cx': cx,
                                'cy': cy,
                                'class_id': class_id,
                                'confidence': confidence
                            })
                    else:
                        if reason != "already_triggered":
                            self.skip_count += 1
        
        # 標記未在當前帧出現的追蹤為 missing
        for track_id in list(self.track_manager.tracks.keys()):
            if track_id not in current_track_ids:
                self.track_manager.mark_missing(track_id)
                
                # 檢查是否超時
                if self.track_manager.should_remove(track_id):
                    self.track_manager.remove_track(track_id)
        
        # 檢查氣吹超時
        timeout_blows = self.blow_controller.check_timeouts()
        
        # 返回處理結果
        return {
            'frame_count': self.frame_count,
            'active_tracks': self.track_manager.get_active_tracks_count(),
            'triggered_tracks': self.track_manager.get_triggered_tracks_count(),
            'triggered_this_frame': triggered_this_frame,
            'timeout_blows': timeout_blows
        }
    
    def _should_trigger(self, 
                       track_id: int, 
                       cx: float, 
                       cy: float, 
                       confidence: float) -> Tuple[bool, str]:
        """
        綜合判斷是否應該觸發
        
        Parameters:
            track_id: 追蹤 ID
            cx, cy: 中心點座標
            confidence: 信度
            
        Returns:
            Tuple[bool, str]: (是否觸發, 原因)
        """
        state = self.track_manager.tracks.get(track_id)
        if not state:
            return False, "no_track_state"
        
        # 條件 1: 在 Trigger Zone 內
        if not self.track_manager.is_in_trigger_zone(cy):
            return False, "not_in_trigger_zone"
        
        # 條件 2: 尚未觸發
        if state.triggered:
            return False, "already_triggered"
        
        # 條件 3: 信度達標
        if confidence < self.confidence_threshold:
            return False, "low_confidence"
        
        # 額外檢查: 中心點穩定性
        if not self.track_manager.check_center_drift(track_id):
            return False, "center_drift"
        
        # 額外檢查: 信度穩定性
        if not self.track_manager.check_confidence_stable(track_id, confidence):
            return False, "confidence_unstable"
        
        return True, "ok"
    
    def _find_detection_info(self, 
                            bbox: List[float], 
                            detections: Any) -> Tuple[float, int]:
        """
        從偵測結果中找到對應的信度和類別
        
        Parameters:
            bbox: Bounding box [x1, y1, x2, y2]
            detections: YOLO 偵測結果
            
        Returns:
            Tuple[float, int]: (信度, 類別 ID)
        """
        if not detections or len(detections) == 0:
            return 0.0, 0
        
        # 嘗試從第一個偵測結果中獲取
        try:
            detection = detections[0]
            if hasattr(detection, 'boxes') and detection.boxes is not None:
                boxes = detection.boxes.xyxy.cpu().numpy()
                confs = detection.boxes.conf.cpu().numpy()
                classes = detection.boxes.cls.cpu().numpy()
                
                # 找到最接近的 bbox
                x1, y1, x2, y2 = bbox[:4]
                bbox_center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
                
                min_dist = float('inf')
                best_idx = 0
                
                for i, box in enumerate(boxes):
                    box_center = np.array([(box[0] + box[2]) / 2, (box[1] + box[3]) / 2])
                    dist = np.linalg.norm(bbox_center - box_center)
                    
                    if dist < min_dist:
                        min_dist = dist
                        best_idx = i
                
                if len(confs) > best_idx and len(classes) > best_idx:
                    return float(confs[best_idx]), int(classes[best_idx])
        except Exception as e:
            self.logger.warning(f"Error finding detection info: {e}")
        
        return 0.0, 0
    
    def get_statistics(self) -> Dict:
        """
        獲取統計資訊
        
        Returns:
            dict: 統計資訊
        """
        blow_stats = self.blow_controller.get_statistics()
        
        return {
            'frame_count': self.frame_count,
            'detection_count': self.detection_count,
            'trigger_count': self.trigger_count,
            'skip_count': self.skip_count,
            'active_tracks': self.track_manager.get_active_tracks_count(),
            'triggered_tracks': self.track_manager.get_triggered_tracks_count(),
            'blow_stats': blow_stats
        }
    
    def print_statistics(self) -> None:
        """列印統計資訊"""
        stats = self.get_statistics()
        
        print("\n" + "="*60)
        print("TWO-BAND FILTER STATISTICS")
        print("="*60)
        print(f"Frames Processed:    {stats['frame_count']}")
        print(f"Active Tracks:       {stats['active_tracks']}")
        print(f"Triggered Tracks:    {stats['triggered_tracks']}")
        print(f"Total Triggers:      {stats['trigger_count']}")
        print(f"Skipped (Reasons):   {stats['skip_count']}")
        print("-"*60)
        
        self.blow_controller.print_statistics()
    
    def reset_statistics(self) -> None:
        """重置統計資訊"""
        self.frame_count = 0
        self.detection_count = 0
        self.trigger_count = 0
        self.skip_count = 0
        self.blow_controller.reset_statistics()
        self.logger.info("Statistics reset")
    
    def visualize_zones(self, image: np.ndarray) -> np.ndarray:
        """
        在圖像上繪製區域邊界（用於除錯）
        
        Parameters:
            image: 輸入圖像
            
        Returns:
            np.ndarray: 帶有區域標記的圖像
        """
        import cv2
        
        img_copy = image.copy()
        h, w = img_copy.shape[:2]
        
        # 繪製 Trigger Zone
        cv2.rectangle(
            img_copy,
            (0, int(self.trigger_zone_top)),
            (w, int(self.trigger_zone_bottom)),
            (0, 255, 0),  # 綠色
            2
        )
        
        # 添加文字標記
        cv2.putText(
            img_copy,
            "ENTRY ZONE",
            (10, int(self.trigger_zone_top) - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2
        )
        
        cv2.putText(
            img_copy,
            "TRIGGER ZONE",
            (10, int((self.trigger_zone_top + self.trigger_zone_bottom) / 2)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2
        )
        
        cv2.putText(
            img_copy,
            "EXIT ZONE",
            (10, int(self.trigger_zone_bottom) + 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 0),
            2
        )
        
        return img_copy
    
    def draw_tracks(self, 
                    image: np.ndarray, 
                    tracker_results: List[Tuple]) -> np.ndarray:
        """
        在圖像上繪製追蹤結果
        
        Parameters:
            image: 輸入圖像
            tracker_results: 追蹤器結果
            
        Returns:
            np.ndarray: 帶有追蹤標記的圖像
        """
        import cv2
        
        img_copy = image.copy()
        
        for track_result in tracker_results:
            if len(track_result) >= 2:
                track_id = int(track_result[0])
                bbox = track_result[1]
                
                if len(bbox) >= 4:
                    x1, y1, x2, y2 = bbox[:4]
                    cx = (x1 + x2) / 2
                    cy = (y1 + y2) / 2
                    
                    # 獲取追蹤狀態
                    track_info = self.track_manager.get_track_info(track_id)
                    
                    if track_info:
                        # 根據狀態選擇顏色
                        if track_info['triggered']:
                            color = (0, 0, 255)  # 紅色 - 已觸發
                        elif self.track_manager.is_in_trigger_zone(cy):
                            color = (0, 255, 0)  # 綠色 - 在觸發區
                        else:
                            color = (255, 255, 0)  # 黃色 - 其他區域
                        
                        # 繪製 bounding box
                        cv2.rectangle(
                            img_copy,
                            (int(x1), int(y1)),
                            (int(x2), int(y2)),
                            color,
                            2
                        )
                        
                        # 繪製中心點
                        cv2.circle(
                            img_copy,
                            (int(cx), int(cy)),
                            5,
                            color,
                            -1
                        )
                        
                        # 繪製軌跡
                        if len(track_info.get('center_history', [])) > 1:
                            state = self.track_manager.tracks[track_id]
                            for i in range(1, len(state.center_history)):
                                pt1 = tuple(map(int, state.center_history[i-1]))
                                pt2 = tuple(map(int, state.center_history[i]))
                                cv2.line(img_copy, pt1, pt2, color, 2)
                        
                        # 繪製資訊文字
                        label = f"ID:{track_id}"
                        if track_info['triggered']:
                            label += " [TRIGGERED]"
                        label += f" {track_info['confidence']:.2f}"
                        
                        cv2.putText(
                            img_copy,
                            label,
                            (int(x1), int(y1) - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            color,
                            2
                        )
        
        return img_copy
