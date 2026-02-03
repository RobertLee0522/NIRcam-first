# track_manager.py
"""
追蹤狀態管理器
用於管理物體追蹤狀態，包括中心點歷史、信度歷史、觸發狀態等
"""

from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional
import numpy as np


@dataclass
class TrackState:
    """單一物體的追蹤狀態"""
    track_id: int                                       # 追蹤 ID
    triggered: bool = False                             # 是否已觸發氣吹
    missing_frames: int = 0                             # 連續未偵測到的帧數
    last_center: Optional[Tuple[float, float]] = None   # 上一帧的中心點
    center_history: List[Tuple[float, float]] = field(default_factory=list)  # 最近 3 帧中心點歷史
    confidence_history: List[float] = field(default_factory=list)            # 信度歷史
    class_id: Optional[int] = None                      # 類別 ID
    first_seen_frame: int = 0                           # 第一次出現的帧號
    last_seen_frame: int = 0                            # 最後一次出現的帧號


class TrackManager:
    """追蹤狀態管理器"""
    
    def __init__(self, 
                 image_height: int,
                 lens_type: str = "12mm",
                 tracking_timeout_frames: int = 15,
                 confidence_threshold: float = 0.75):
        """
        初始化追蹤管理器
        
        Parameters:
            image_height: 圖像高度（像素）
            lens_type: 鏡頭類型（"12mm" 或 "8mm"）
            tracking_timeout_frames: 追蹤超時帧數
            confidence_threshold: 信度閾值
        """
        self.tracks: Dict[int, TrackState] = {}
        self.lens_type = lens_type
        self.image_height = image_height
        self.tracking_timeout_frames = tracking_timeout_frames
        self.confidence_threshold = confidence_threshold
        self.current_frame = 0
        
        # 根據鏡頭類型設置容差
        self.center_tolerance = 5 if lens_type == "12mm" else 8
        
        # 區域邊界
        self.entry_zone_bottom = image_height * 0.375
        self.trigger_zone_top = image_height * 0.375
        self.trigger_zone_bottom = image_height * 0.625
        self.exit_zone_top = image_height * 0.625
        
        print(f"[TrackManager] Initialized with {lens_type} lens")
        print(f"[TrackManager] Image height: {image_height}px")
        print(f"[TrackManager] Center tolerance: ±{self.center_tolerance}px")
        print(f"[TrackManager] Trigger Zone: Y={self.trigger_zone_top:.1f} ~ {self.trigger_zone_bottom:.1f}")
    
    def update_track(self, 
                     track_id: int, 
                     cx: float, 
                     cy: float, 
                     confidence: float,
                     class_id: int) -> None:
        """
        更新追蹤狀態
        
        Parameters:
            track_id: 追蹤 ID
            cx, cy: 中心點座標
            confidence: 類別信度
            class_id: 類別 ID
        """
        if track_id not in self.tracks:
            # 新追蹤物體
            self.tracks[track_id] = TrackState(
                track_id=track_id,
                class_id=class_id,
                first_seen_frame=self.current_frame
            )
            print(f"[TrackManager] New track ID={track_id}, class={class_id}, pos=({cx:.1f}, {cy:.1f})")
        
        state = self.tracks[track_id]
        state.missing_frames = 0
        state.last_center = (cx, cy)
        state.last_seen_frame = self.current_frame
        state.class_id = class_id
        
        # 維護最近 3 帧的歷史
        state.center_history.append((cx, cy))
        if len(state.center_history) > 3:
            state.center_history.pop(0)
        
        state.confidence_history.append(confidence)
        if len(state.confidence_history) > 3:
            state.confidence_history.pop(0)
    
    def mark_missing(self, track_id: int) -> None:
        """
        標記物體在當前帧未被偵測到
        
        Parameters:
            track_id: 追蹤 ID
        """
        if track_id in self.tracks:
            self.tracks[track_id].missing_frames += 1
    
    def should_remove(self, track_id: int) -> bool:
        """
        判斷是否應該移除追蹤
        
        Parameters:
            track_id: 追蹤 ID
            
        Returns:
            bool: 是否應該移除
        """
        if track_id not in self.tracks:
            return False
        
        state = self.tracks[track_id]
        
        # 條件 1: 進入 Exit Zone
        if state.last_center:
            cy = state.last_center[1]
            in_exit_zone = cy > self.exit_zone_top
            
            if in_exit_zone:
                return True
        
        # 條件 2: 連續超過閾值帧數未偵測到
        timeout = state.missing_frames > self.tracking_timeout_frames
        
        return timeout
    
    def remove_track(self, track_id: int) -> None:
        """
        移除追蹤狀態
        
        Parameters:
            track_id: 追蹤 ID
        """
        if track_id in self.tracks:
            state = self.tracks[track_id]
            reason = "Exit Zone" if state.last_center and state.last_center[1] > self.exit_zone_top else "Timeout"
            print(f"[TrackManager] Removed track ID={track_id}, reason={reason}, frames={state.last_seen_frame - state.first_seen_frame}")
            del self.tracks[track_id]
    
    def check_center_drift(self, track_id: int) -> bool:
        """
        檢查中心點是否在連續 3 帧內飄移過大
        
        Parameters:
            track_id: 追蹤 ID
            
        Returns:
            bool: True 表示穩定，可以觸發；False 表示飄移過大，暫停觸發
        """
        state = self.tracks.get(track_id)
        if not state or len(state.center_history) < 3:
            return True  # 歷史不足，假設穩定
        
        # 計算連續帧之間的位移
        drift_threshold = self.center_tolerance * 2  # 容差的兩倍
        
        for i in range(1, len(state.center_history)):
            prev = state.center_history[i-1]
            curr = state.center_history[i]
            drift = np.sqrt((curr[0] - prev[0])**2 + (curr[1] - prev[1])**2)
            
            if drift > drift_threshold:
                print(f"[TrackManager] Track ID={track_id} drift={drift:.1f}px > threshold={drift_threshold}px")
                return False  # 飄移過大
        
        return True
    
    def check_confidence_stable(self, track_id: int, current_confidence: float) -> bool:
        """
        檢查信度是否穩定
        如果信度在閾值附近反覆波動，跳過該帧但不清除追蹤
        
        Parameters:
            track_id: 追蹤 ID
            current_confidence: 當前帧信度
            
        Returns:
            bool: True 表示可以觸發；False 表示應跳過該帧
        """
        # 當前帧信度未達標
        if current_confidence < self.confidence_threshold:
            return False
        
        state = self.tracks.get(track_id)
        if not state or len(state.confidence_history) < 2:
            return True
        
        # 檢查是否有劇烈波動（上一帧低於閾值，這一帧高於）
        prev_conf = state.confidence_history[-1] if state.confidence_history else current_confidence
        
        # 如果前一帧低於閾值，等待一帧確認穩定
        if prev_conf < self.confidence_threshold:
            print(f"[TrackManager] Track ID={track_id} confidence unstable: {prev_conf:.2f} -> {current_confidence:.2f}")
            return False
        
        return True
    
    def is_in_trigger_zone(self, cy: float) -> bool:
        """
        判斷中心點是否在 Trigger Zone 內
        
        Parameters:
            cy: Y 座標
            
        Returns:
            bool: 是否在 Trigger Zone
        """
        return self.trigger_zone_top <= cy <= self.trigger_zone_bottom
    
    def get_track_info(self, track_id: int) -> Optional[Dict]:
        """
        獲取追蹤資訊
        
        Parameters:
            track_id: 追蹤 ID
            
        Returns:
            dict: 追蹤資訊，包含中心點、信度、類別等
        """
        if track_id not in self.tracks:
            return None
        
        state = self.tracks[track_id]
        return {
            'track_id': track_id,
            'center': state.last_center,
            'confidence': state.confidence_history[-1] if state.confidence_history else 0.0,
            'class_id': state.class_id,
            'triggered': state.triggered,
            'frames': state.last_seen_frame - state.first_seen_frame
        }
    
    def increment_frame(self) -> None:
        """增加帧計數器"""
        self.current_frame += 1
    
    def get_active_tracks_count(self) -> int:
        """獲取活動追蹤數量"""
        return len(self.tracks)
    
    def get_triggered_tracks_count(self) -> int:
        """獲取已觸發追蹤數量"""
        return sum(1 for state in self.tracks.values() if state.triggered)
