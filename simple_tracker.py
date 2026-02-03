# simple_tracker.py
"""
簡化版物體追蹤器（基於 SORT 演算法）
使用 IoU 匹配和卡爾曼濾波器進行物體追蹤
不需要額外的深度學習依賴，輕量且快速
"""

import numpy as np
from typing import List, Tuple, Optional, Any
from dataclasses import dataclass
from scipy.optimize import linear_sum_assignment


@dataclass
class TrackState:
    """追蹤物體的狀態"""
    track_id: int           # 追蹤 ID
    bbox: np.ndarray        # 邊界框 [x1, y1, x2, y2]
    confidence: float       # 信度
    class_id: int          # 類別 ID
    age: int = 1           # 追蹤持續時間（帧數）
    hits: int = 1          # 成功匹配次數
    time_since_update: int = 0  # 自上次更新以來的帧數
    
    # 卡爾曼濾波器狀態
    kalman_state: Optional[np.ndarray] = None
    kalman_covariance: Optional[np.ndarray] = None


class KalmanBoxTracker:
    """
    使用卡爾曼濾波器追蹤單一物體的邊界框
    狀態向量: [x_center, y_center, area, aspect_ratio, dx, dy, da, dr]
    """
    
    def __init__(self, bbox: np.ndarray):
        """
        初始化卡爾曼濾波器
        
        Parameters:
            bbox: 初始邊界框 [x1, y1, x2, y2]
        """
        # 狀態轉移矩陣（等速模型）
        self.F = np.eye(8)
        for i in range(4):
            self.F[i, i+4] = 1
        
        # 觀測矩陣
        self.H = np.eye(4, 8)
        
        # 過程噪聲協方差
        self.Q = np.eye(8)
        self.Q[4:, 4:] *= 0.01  # 速度的不確定性較小
        
        # 測量噪聲協方差
        self.R = np.eye(4) * 1.0
        
        # 初始狀態協方差
        self.P = np.eye(8)
        self.P[4:, 4:] *= 1000  # 初始速度不確定性大
        
        # 初始化狀態
        self.x = np.zeros(8)
        self.x[:4] = self._bbox_to_state(bbox)
    
    def _bbox_to_state(self, bbox: np.ndarray) -> np.ndarray:
        """
        將邊界框轉換為狀態向量 [x_center, y_center, area, aspect_ratio]
        
        Parameters:
            bbox: [x1, y1, x2, y2]
            
        Returns:
            狀態向量
        """
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        x = bbox[0] + w / 2
        y = bbox[1] + h / 2
        area = w * h
        aspect_ratio = w / (h + 1e-6)
        return np.array([x, y, area, aspect_ratio])
    
    def _state_to_bbox(self, state: np.ndarray) -> np.ndarray:
        """
        將狀態向量轉換為邊界框 [x1, y1, x2, y2]
        
        Parameters:
            state: 狀態向量
            
        Returns:
            邊界框
        """
        x, y, area, aspect_ratio = state
        w = np.sqrt(area * aspect_ratio)
        h = area / (w + 1e-6)
        
        return np.array([
            x - w/2,
            y - h/2,
            x + w/2,
            y + h/2
        ])
    
    def predict(self) -> np.ndarray:
        """
        預測下一時刻的狀態
        
        Returns:
            預測的邊界框
        """
        # 狀態預測
        self.x = self.F @ self.x
        
        # 協方差預測
        self.P = self.F @ self.P @ self.F.T + self.Q
        
        return self._state_to_bbox(self.x[:4])
    
    def update(self, bbox: np.ndarray) -> None:
        """
        使用觀測更新狀態
        
        Parameters:
            bbox: 觀測到的邊界框 [x1, y1, x2, y2]
        """
        z = self._bbox_to_state(bbox)
        
        # 計算卡爾曼增益
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)
        
        # 更新狀態
        y = z - self.H @ self.x
        self.x = self.x + K @ y
        
        # 更新協方差
        self.P = (np.eye(8) - K @ self.H) @ self.P
    
    def get_state(self) -> np.ndarray:
        """獲取當前狀態的邊界框"""
        return self._state_to_bbox(self.x[:4])


class SimpleTracker:
    """
    簡化版物體追蹤器
    基於 SORT (Simple Online and Realtime Tracking) 演算法
    """
    
    def __init__(self, 
                 max_age: int = 15,
                 min_hits: int = 3,
                 iou_threshold: float = 0.3):
        """
        初始化追蹤器
        
        Parameters:
            max_age: 追蹤失敗後保留的最大帧數
            min_hits: 被認為是穩定追蹤需要的最小匹配次數
            iou_threshold: IoU 閾值，低於此值視為不匹配
        """
        self.max_age = max_age
        self.min_hits = min_hits
        self.iou_threshold = iou_threshold
        
        self.tracks: List[TrackState] = []
        self.next_id = 1
        self.frame_count = 0
        
        print(f"[SimpleTracker] Initialized with max_age={max_age}, min_hits={min_hits}, iou_threshold={iou_threshold}")
    
    def update(self, detections: Any) -> List[Tuple[int, np.ndarray, float, int]]:
        """
        更新追蹤器
        
        Parameters:
            detections: YOLO 偵測結果
            
        Returns:
            List[Tuple]: [(track_id, bbox, confidence, class_id), ...]
                        bbox 格式: [x1, y1, x2, y2]
        """
        self.frame_count += 1
        
        # 解析偵測結果
        det_bboxes, det_confs, det_classes = self._parse_detections(detections)
        
        # 預測所有現有追蹤的位置
        for track in self.tracks:
            if track.kalman_state is not None:
                kalman_tracker = KalmanBoxTracker(track.bbox)
                kalman_tracker.x = track.kalman_state
                kalman_tracker.P = track.kalman_covariance
                predicted_bbox = kalman_tracker.predict()
                track.bbox = predicted_bbox
                track.kalman_state = kalman_tracker.x
                track.kalman_covariance = kalman_tracker.P
        
        # 匹配偵測和追蹤
        matched, unmatched_dets, unmatched_trks = self._associate_detections_to_tracks(
            det_bboxes, det_confs, det_classes
        )
        
        # 更新匹配的追蹤
        for det_idx, trk_idx in matched:
            track = self.tracks[trk_idx]
            
            # 更新卡爾曼濾波器
            if track.kalman_state is None:
                kalman_tracker = KalmanBoxTracker(det_bboxes[det_idx])
                track.kalman_state = kalman_tracker.x
                track.kalman_covariance = kalman_tracker.P
            else:
                kalman_tracker = KalmanBoxTracker(track.bbox)
                kalman_tracker.x = track.kalman_state
                kalman_tracker.P = track.kalman_covariance
                kalman_tracker.update(det_bboxes[det_idx])
                track.kalman_state = kalman_tracker.x
                track.kalman_covariance = kalman_tracker.P
            
            # 更新追蹤資訊
            track.bbox = det_bboxes[det_idx]
            track.confidence = det_confs[det_idx]
            track.class_id = det_classes[det_idx]
            track.hits += 1
            track.time_since_update = 0
            track.age += 1
        
        # 創建新追蹤（未匹配的偵測）
        for det_idx in unmatched_dets:
            new_track = TrackState(
                track_id=self.next_id,
                bbox=det_bboxes[det_idx],
                confidence=det_confs[det_idx],
                class_id=det_classes[det_idx]
            )
            
            # 初始化卡爾曼濾波器
            kalman_tracker = KalmanBoxTracker(det_bboxes[det_idx])
            new_track.kalman_state = kalman_tracker.x
            new_track.kalman_covariance = kalman_tracker.P
            
            self.tracks.append(new_track)
            self.next_id += 1
        
        # 更新未匹配的追蹤
        for trk_idx in unmatched_trks:
            self.tracks[trk_idx].time_since_update += 1
            self.tracks[trk_idx].age += 1
        
        # 移除過時的追蹤
        self.tracks = [
            track for track in self.tracks
            if track.time_since_update < self.max_age
        ]
        
        # 返回活躍的追蹤（已經穩定的追蹤）
        results = []
        for track in self.tracks:
            # 至少需要 min_hits 次匹配，或者是新追蹤（age < min_hits）
            if track.hits >= self.min_hits or track.age < self.min_hits:
                results.append((
                    track.track_id,
                    track.bbox,
                    track.confidence,
                    track.class_id
                ))
        
        return results
    
    def _parse_detections(self, detections: Any) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        解析 YOLO 偵測結果
        
        Parameters:
            detections: YOLO 偵測結果
            
        Returns:
            Tuple: (bboxes, confidences, class_ids)
        """
        if detections is None or len(detections) == 0:
            return np.empty((0, 4)), np.empty(0), np.empty(0, dtype=int)
        
        try:
            # 假設是 Ultralytics YOLO 格式
            detection = detections[0]
            
            if hasattr(detection, 'boxes') and detection.boxes is not None:
                boxes = detection.boxes
                
                # 獲取邊界框
                bboxes = boxes.xyxy.cpu().numpy()
                
                # 獲取信度
                confs = boxes.conf.cpu().numpy()
                
                # 獲取類別
                classes = boxes.cls.cpu().numpy().astype(int)
                
                return bboxes, confs, classes
        except Exception as e:
            print(f"[SimpleTracker] Error parsing detections: {e}")
        
        return np.empty((0, 4)), np.empty(0), np.empty(0, dtype=int)
    
    def _associate_detections_to_tracks(self, 
                                       det_bboxes: np.ndarray,
                                       det_confs: np.ndarray,
                                       det_classes: np.ndarray) -> Tuple[List, List, List]:
        """
        使用 IoU 匹配偵測和追蹤
        
        Parameters:
            det_bboxes: 偵測的邊界框
            det_confs: 偵測的信度
            det_classes: 偵測的類別
            
        Returns:
            Tuple: (matched, unmatched_detections, unmatched_tracks)
        """
        if len(self.tracks) == 0:
            return [], list(range(len(det_bboxes))), []
        
        if len(det_bboxes) == 0:
            return [], [], list(range(len(self.tracks)))
        
        # 計算 IoU 矩陣
        iou_matrix = np.zeros((len(det_bboxes), len(self.tracks)))
        
        for d, det_bbox in enumerate(det_bboxes):
            for t, track in enumerate(self.tracks):
                # 只匹配相同類別的物體
                if det_classes[d] == track.class_id:
                    iou_matrix[d, t] = self._compute_iou(det_bbox, track.bbox)
        
        # 使用匈牙利演算法進行最優匹配
        # linear_sum_assignment 最小化成本，所以我們用 (1 - IoU)
        if min(iou_matrix.shape) > 0:
            row_ind, col_ind = linear_sum_assignment(1 - iou_matrix)
            matched_indices = np.array(list(zip(row_ind, col_ind)))
        else:
            matched_indices = np.empty((0, 2), dtype=int)
        
        # 過濾低 IoU 的匹配
        matched = []
        for m in matched_indices:
            if iou_matrix[m[0], m[1]] >= self.iou_threshold:
                matched.append(m.tolist())
        
        # 找出未匹配的偵測和追蹤
        matched = np.array(matched) if matched else np.empty((0, 2), dtype=int)
        
        unmatched_detections = []
        for d in range(len(det_bboxes)):
            if len(matched) == 0 or d not in matched[:, 0]:
                unmatched_detections.append(d)
        
        unmatched_tracks = []
        for t in range(len(self.tracks)):
            if len(matched) == 0 or t not in matched[:, 1]:
                unmatched_tracks.append(t)
        
        return matched, unmatched_detections, unmatched_tracks
    
    def _compute_iou(self, bbox1: np.ndarray, bbox2: np.ndarray) -> float:
        """
        計算兩個邊界框的 IoU (Intersection over Union)
        
        Parameters:
            bbox1: [x1, y1, x2, y2]
            bbox2: [x1, y1, x2, y2]
            
        Returns:
            float: IoU 值 (0~1)
        """
        # 計算交集
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        
        # 計算聯集
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        union = area1 + area2 - intersection
        
        # 計算 IoU
        iou = intersection / (union + 1e-6)
        
        return iou
    
    def get_statistics(self) -> dict:
        """獲取追蹤器統計資訊"""
        return {
            'total_tracks': self.next_id - 1,
            'active_tracks': len(self.tracks),
            'frame_count': self.frame_count
        }
    
    def reset(self) -> None:
        """重置追蹤器"""
        self.tracks.clear()
        self.next_id = 1
        self.frame_count = 0
        print("[SimpleTracker] Reset")


if __name__ == "__main__":
    # 測試追蹤器
    print("Testing SimpleTracker...")
    
    tracker = SimpleTracker(max_age=15, min_hits=3, iou_threshold=0.3)
    
    # 模擬偵測結果
    print("\nFrame 1:")
    # 模擬一個物體
    fake_det = type('Detection', (), {
        'boxes': type('Boxes', (), {
            'xyxy': type('Tensor', (), {
                'cpu': lambda: type('Array', (), {
                    'numpy': lambda: np.array([[100, 100, 200, 200]])
                })()
            })(),
            'conf': type('Tensor', (), {
                'cpu': lambda: type('Array', (), {
                    'numpy': lambda: np.array([0.9])
                })()
            })(),
            'cls': type('Tensor', (), {
                'cpu': lambda: type('Array', (), {
                    'numpy': lambda: np.array([0])
                })()
            })()
        })()
    })()
    
    results = tracker.update([fake_det])
    print(f"Results: {len(results)} tracks")
    for track_id, bbox, conf, cls in results:
        print(f"  Track {track_id}: bbox={bbox}, conf={conf:.2f}, class={cls}")
    
    print("\nTracker statistics:")
    print(tracker.get_statistics())
