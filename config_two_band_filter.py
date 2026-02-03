# config_two_band_filter.py
"""
Two-Band Filter 配置文件
集中管理所有參數，方便調整和維護
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class ZoneConfig:
    """視野分區配置"""
    entry_zone_ratio: float = 0.375      # Entry Zone 下邊界比例
    trigger_zone_top: float = 0.375      # Trigger Zone 上邊界比例
    trigger_zone_bottom: float = 0.625   # Trigger Zone 下邊界比例
    exit_zone_ratio: float = 0.625       # Exit Zone 上邊界比例
    
    def get_boundaries(self, image_height: int) -> dict:
        """
        計算實際的像素邊界
        
        Parameters:
            image_height: 圖像高度（像素）
            
        Returns:
            dict: 各區域邊界的像素值
        """
        return {
            'entry_zone_bottom': int(image_height * self.entry_zone_ratio),
            'trigger_zone_top': int(image_height * self.trigger_zone_top),
            'trigger_zone_bottom': int(image_height * self.trigger_zone_bottom),
            'exit_zone_top': int(image_height * self.exit_zone_ratio)
        }


@dataclass
class LensConfig:
    """鏡頭配置"""
    lens_type: str = "12mm"              # 鏡頭類型: "12mm" 或 "8mm"
    center_tolerance_12mm: int = 5       # 12mm 鏡頭中心點容差（像素）
    center_tolerance_8mm: int = 8        # 8mm 鏡頭中心點容差（像素）
    
    @property
    def center_tolerance(self) -> int:
        """獲取當前鏡頭的容差"""
        return self.center_tolerance_12mm if self.lens_type == "12mm" else self.center_tolerance_8mm


@dataclass
class DetectionConfig:
    """偵測配置"""
    confidence_threshold: float = 0.75   # 類別信度閾值
    iou_threshold: float = 0.45          # IoU 閾值（用於 NMS）
    max_det: int = 100                   # 最大偵測數量


@dataclass
class TrackingConfig:
    """追蹤配置"""
    tracking_timeout_frames: int = 15    # 追蹤超時帧數
    center_history_length: int = 3       # 中心點歷史長度
    confidence_history_length: int = 3   # 信度歷史長度
    drift_multiplier: float = 2.0        # 飄移閾值倍數（相對於容差）


@dataclass
class BlowConfig:
    """氣吹配置"""
    blow_delay_min_ms: int = 80          # 氣吹延遲最小值（毫秒）
    blow_delay_max_ms: int = 120         # 氣吹延遲最大值（毫秒）
    ack_timeout_ms: int = 200            # ACK 超時時間（毫秒）
    
    @property
    def blow_delay_range(self) -> Tuple[int, int]:
        """獲取氣吹延遲範圍"""
        return (self.blow_delay_min_ms, self.blow_delay_max_ms)


@dataclass
class TCPConfig:
    """TCP 通訊配置"""
    host: str = 'localhost'              # TCP 伺服器主機
    port: int = 8888                     # TCP 伺服器埠號
    heartbeat_interval_s: float = 5.0   # 心跳間隔（秒）


@dataclass
class ImageConfig:
    """影像配置"""
    image_width: int = 1280              # 圖像寬度（像素）
    image_height: int = 1024             # 圖像高度（像素）
    
    # 根據不同的相機型號調整
    CAMERA_PRESETS = {
        "MV-CA016": {"width": 1280, "height": 1024},
        "MV-CA050": {"width": 2448, "height": 2048},
        "CUSTOM": {"width": 640, "height": 480}
    }
    
    def set_from_preset(self, camera_model: str) -> None:
        """
        從預設值設定影像尺寸
        
        Parameters:
            camera_model: 相機型號
        """
        if camera_model in self.CAMERA_PRESETS:
            preset = self.CAMERA_PRESETS[camera_model]
            self.image_width = preset["width"]
            self.image_height = preset["height"]
            print(f"[ImageConfig] Set from preset '{camera_model}': {self.image_width}x{self.image_height}")
        else:
            print(f"[ImageConfig] Unknown camera model: {camera_model}")


@dataclass
class MonitoringConfig:
    """監控配置"""
    # 警戒閾值
    min_success_rate: float = 0.95       # 最低成功率（95%）
    max_duplicate_rate: float = 0.0      # 最高重複觸發率（0%）
    max_tracking_loss_rate: float = 0.1  # 最高追蹤丟失率（10%）
    min_avg_confidence: float = 0.85     # 最低平均信度（0.85）
    
    # 統計輸出
    print_stats_interval_frames: int = 100  # 每 N 帧列印一次統計
    log_to_file: bool = True                # 是否記錄到文件
    log_file_path: str = "two_band_filter_log.txt"


class TwoBandFilterConfig:
    """Two-Band Filter 總配置類"""
    
    def __init__(self):
        self.zone = ZoneConfig()
        self.lens = LensConfig()
        self.detection = DetectionConfig()
        self.tracking = TrackingConfig()
        self.blow = BlowConfig()
        self.tcp = TCPConfig()
        self.image = ImageConfig()
        self.monitoring = MonitoringConfig()
    
    def update_for_12mm_lens(self) -> None:
        """更新為 12mm 鏡頭配置"""
        self.lens.lens_type = "12mm"
        print("[Config] Updated for 12mm lens")
    
    def update_for_8mm_lens(self) -> None:
        """更新為 8mm 鏡頭配置"""
        self.lens.lens_type = "8mm"
        print("[Config] Updated for 8mm lens")
    
    def update_for_high_speed(self) -> None:
        """
        更新為高速傳帶配置（> 2 m/s）
        - 減少追蹤超時帧數
        - 縮小觸發區域
        """
        self.tracking.tracking_timeout_frames = 10
        self.zone.trigger_zone_top = 0.40
        self.zone.trigger_zone_bottom = 0.60
        print("[Config] Updated for high-speed conveyor (> 2 m/s)")
    
    def update_for_low_speed(self) -> None:
        """
        更新為低速傳帶配置（< 1.5 m/s）
        - 增加追蹤超時帧數
        - 放大觸發區域
        """
        self.tracking.tracking_timeout_frames = 20
        self.zone.trigger_zone_top = 0.35
        self.zone.trigger_zone_bottom = 0.65
        print("[Config] Updated for low-speed conveyor (< 1.5 m/s)")
    
    def update_for_strict_mode(self) -> None:
        """
        更新為嚴格模式
        - 提高信度閾值
        - 縮小觸發區域
        - 增加穩定性要求
        """
        self.detection.confidence_threshold = 0.85
        self.zone.trigger_zone_top = 0.425
        self.zone.trigger_zone_bottom = 0.575
        self.tracking.drift_multiplier = 1.5
        print("[Config] Updated for strict mode (higher precision)")
    
    def update_for_permissive_mode(self) -> None:
        """
        更新為寬鬆模式
        - 降低信度閾值
        - 放大觸發區域
        - 放寬穩定性要求
        """
        self.detection.confidence_threshold = 0.65
        self.zone.trigger_zone_top = 0.35
        self.zone.trigger_zone_bottom = 0.65
        self.tracking.drift_multiplier = 2.5
        print("[Config] Updated for permissive mode (higher coverage)")
    
    def print_config(self) -> None:
        """列印當前配置"""
        print("\n" + "="*60)
        print("TWO-BAND FILTER CONFIGURATION")
        print("="*60)
        
        print("\n[ZONE CONFIG]")
        print(f"  Trigger Zone: {self.zone.trigger_zone_top:.3f} ~ {self.zone.trigger_zone_bottom:.3f}")
        print(f"  Coverage: {(self.zone.trigger_zone_bottom - self.zone.trigger_zone_top) * 100:.1f}%")
        
        print("\n[LENS CONFIG]")
        print(f"  Type: {self.lens.lens_type}")
        print(f"  Center Tolerance: ±{self.lens.center_tolerance} pixels")
        
        print("\n[DETECTION CONFIG]")
        print(f"  Confidence Threshold: {self.detection.confidence_threshold}")
        print(f"  IoU Threshold: {self.detection.iou_threshold}")
        print(f"  Max Detections: {self.detection.max_det}")
        
        print("\n[TRACKING CONFIG]")
        print(f"  Timeout Frames: {self.tracking.tracking_timeout_frames}")
        print(f"  History Length: {self.tracking.center_history_length}")
        print(f"  Drift Multiplier: {self.tracking.drift_multiplier}x")
        
        print("\n[BLOW CONFIG]")
        print(f"  Blow Delay: {self.blow.blow_delay_min_ms}~{self.blow.blow_delay_max_ms} ms")
        print(f"  ACK Timeout: {self.blow.ack_timeout_ms} ms")
        
        print("\n[TCP CONFIG]")
        print(f"  Server: {self.tcp.host}:{self.tcp.port}")
        
        print("\n[IMAGE CONFIG]")
        print(f"  Resolution: {self.image.image_width} x {self.image.image_height}")
        
        print("\n[MONITORING CONFIG]")
        print(f"  Min Success Rate: {self.monitoring.min_success_rate * 100:.1f}%")
        print(f"  Max Tracking Loss: {self.monitoring.max_tracking_loss_rate * 100:.1f}%")
        print(f"  Min Avg Confidence: {self.monitoring.min_avg_confidence}")
        
        print("="*60 + "\n")
    
    def save_to_file(self, filepath: str = "config_saved.txt") -> None:
        """
        儲存配置到文件
        
        Parameters:
            filepath: 文件路徑
        """
        import json
        from dataclasses import asdict
        
        config_dict = {
            'zone': asdict(self.zone),
            'lens': asdict(self.lens),
            'detection': asdict(self.detection),
            'tracking': asdict(self.tracking),
            'blow': asdict(self.blow),
            'tcp': asdict(self.tcp),
            'image': {
                'image_width': self.image.image_width,
                'image_height': self.image.image_height
            },
            'monitoring': asdict(self.monitoring)
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=4, ensure_ascii=False)
        
        print(f"[Config] Saved to {filepath}")
    
    def load_from_file(self, filepath: str = "config_saved.txt") -> None:
        """
        從文件載入配置
        
        Parameters:
            filepath: 文件路徑
        """
        import json
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                config_dict = json.load(f)
            
            # 更新各配置
            for key, value in config_dict.get('zone', {}).items():
                setattr(self.zone, key, value)
            
            for key, value in config_dict.get('lens', {}).items():
                setattr(self.lens, key, value)
            
            for key, value in config_dict.get('detection', {}).items():
                setattr(self.detection, key, value)
            
            for key, value in config_dict.get('tracking', {}).items():
                setattr(self.tracking, key, value)
            
            for key, value in config_dict.get('blow', {}).items():
                setattr(self.blow, key, value)
            
            for key, value in config_dict.get('tcp', {}).items():
                setattr(self.tcp, key, value)
            
            for key, value in config_dict.get('image', {}).items():
                setattr(self.image, key, value)
            
            for key, value in config_dict.get('monitoring', {}).items():
                setattr(self.monitoring, key, value)
            
            print(f"[Config] Loaded from {filepath}")
            
        except FileNotFoundError:
            print(f"[Config] File not found: {filepath}")
        except Exception as e:
            print(f"[Config] Error loading config: {e}")


# 預設配置實例
default_config = TwoBandFilterConfig()


# 範例：不同場景的配置
def get_config_for_scenario(scenario: str) -> TwoBandFilterConfig:
    """
    根據場景獲取配置
    
    Parameters:
        scenario: 場景名稱
            - "default": 預設配置
            - "12mm_high_speed": 12mm 鏡頭 + 高速傳帶
            - "8mm_low_speed": 8mm 鏡頭 + 低速傳帶
            - "strict": 嚴格模式（高精度）
            - "permissive": 寬鬆模式（高覆蓋）
    
    Returns:
        TwoBandFilterConfig: 配置實例
    """
    config = TwoBandFilterConfig()
    
    if scenario == "12mm_high_speed":
        config.update_for_12mm_lens()
        config.update_for_high_speed()
    elif scenario == "8mm_low_speed":
        config.update_for_8mm_lens()
        config.update_for_low_speed()
    elif scenario == "strict":
        config.update_for_strict_mode()
    elif scenario == "permissive":
        config.update_for_permissive_mode()
    elif scenario == "default":
        pass
    else:
        print(f"[Config] Unknown scenario: {scenario}, using default")
    
    return config


if __name__ == "__main__":
    # 測試配置
    print("Testing configuration system...\n")
    
    # 1. 預設配置
    config = TwoBandFilterConfig()
    config.print_config()
    
    # 2. 12mm + 高速
    print("\n" + "-"*60)
    config_12mm = get_config_for_scenario("12mm_high_speed")
    config_12mm.print_config()
    
    # 3. 嚴格模式
    print("\n" + "-"*60)
    config_strict = get_config_for_scenario("strict")
    config_strict.print_config()
    
    # 4. 儲存和載入
    print("\n" + "-"*60)
    config.save_to_file("test_config.json")
    
    new_config = TwoBandFilterConfig()
    new_config.load_from_file("test_config.json")
    new_config.print_config()
