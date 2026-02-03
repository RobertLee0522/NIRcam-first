# blow_controller.py
"""
氣吹控制器
用於發送氣吹指令到 LabVIEW 控制系統，並處理 ACK 確認與超時
"""

import logging
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class BlowCommand:
    """氣吹指令資料"""
    blow_id: str                # 氣吹 ID
    track_id: int              # 追蹤 ID
    cx: float                  # 中心點 X 座標
    cy: float                  # 中心點 Y 座標
    class_id: int              # 類別 ID
    confidence: float          # 信度
    timestamp: datetime        # 時間戳記
    ack_received: bool = False # 是否收到 ACK
    
    def to_message(self, trigger_count: int, image_width: int, image_height: int) -> str:
        """
        轉換為 TCP 訊息格式
        格式: trigger_num,照片寬度,照片高度,物件數量,label,center_x,center_y,width,height,結尾4個點
        
        Returns:
            str: TCP 訊息
        """
        # 單一物體的訊息
        message_parts = [
            ";",
            trigger_count,
            image_width,
            image_height,
            1,  # 單一物體
            int(self.class_id),
            int(self.cx),
            int(self.cy),
            0,  # width (可選)
            0,  # height (可選)
            0, 0, 0, 0  # 結尾標記
        ]
        return ",".join(map(str, message_parts)) + "\n"


class BlowController:
    """氣吹控制器"""
    
    def __init__(self, 
                 tcp_server=None,
                 ack_timeout_ms: int = 200,
                 blow_delay_ms: tuple = (80, 120)):
        """
        初始化氣吹控制器
        
        Parameters:
            tcp_server: TCP 伺服器實例
            ack_timeout_ms: ACK 超時時間（毫秒）
            blow_delay_ms: 氣吹延遲範圍（毫秒）
        """
        self.tcp_server = tcp_server
        self.ack_timeout_ms = ack_timeout_ms
        self.blow_delay_ms = blow_delay_ms
        self.pending_blows: Dict[str, BlowCommand] = {}  # blow_id -> BlowCommand
        self.failed_blows: List[Dict] = []               # 未收到 ACK 的氣吹記錄
        self.successful_blows: List[BlowCommand] = []    # 成功的氣吹記錄
        self.blow_count = 0
        
        # 設置日誌
        self.logger = logging.getLogger("BlowController")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(name)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        print(f"[BlowController] Initialized with ACK timeout={ack_timeout_ms}ms")
    
    def set_tcp_server(self, tcp_server) -> None:
        """
        設置 TCP 伺服器實例
        
        Parameters:
            tcp_server: TCP 伺服器實例
        """
        self.tcp_server = tcp_server
        print(f"[BlowController] TCP server connected")
    
    def send_blow_command(self, 
                          cx: float, 
                          cy: float, 
                          class_id: int, 
                          track_id: int,
                          confidence: float,
                          image_width: int,
                          image_height: int) -> bool:
        """
        發送氣吹指令
        
        Parameters:
            cx, cy: 中心點座標
            class_id: 類別 ID
            track_id: 追蹤 ID
            confidence: 信度
            image_width: 圖像寬度
            image_height: 圖像高度
            
        Returns:
            bool: 是否成功發送
        """
        if not self.tcp_server:
            self.logger.warning("TCP server not available, cannot send blow command")
            return False
        
        if not hasattr(self.tcp_server, 'is_connected') or not self.tcp_server.is_connected:
            self.logger.warning("TCP server not connected, cannot send blow command")
            return False
        
        # 生成氣吹 ID
        blow_id = self._generate_blow_id()
        self.blow_count += 1
        
        # 創建氣吹指令
        command = BlowCommand(
            blow_id=blow_id,
            track_id=track_id,
            cx=cx,
            cy=cy,
            class_id=class_id,
            confidence=confidence,
            timestamp=datetime.now()
        )
        
        # 轉換為 TCP 訊息
        message = command.to_message(self.blow_count, image_width, image_height)
        
        # 發送到 TCP 伺服器
        try:
            if self.tcp_server.send_message(message):
                self.pending_blows[blow_id] = command
                self.logger.info(
                    f"Blow #{self.blow_count}: Track={track_id}, "
                    f"Class={class_id}, Pos=({cx:.1f},{cy:.1f}), "
                    f"Conf={confidence:.2f}"
                )
                return True
            else:
                self.logger.error(f"Failed to send blow command: {blow_id}")
                return False
        except Exception as e:
            self.logger.error(f"Error sending blow command: {e}")
            return False
    
    def receive_ack(self, blow_id: str) -> None:
        """
        接收氣吹控制器的 ACK
        
        Parameters:
            blow_id: 氣吹 ID
        """
        if blow_id in self.pending_blows:
            command = self.pending_blows[blow_id]
            command.ack_received = True
            self.successful_blows.append(command)
            del self.pending_blows[blow_id]
            
            elapsed_ms = (datetime.now() - command.timestamp).total_seconds() * 1000
            self.logger.info(f"ACK received for blow: {blow_id} (elapsed: {elapsed_ms:.1f}ms)")
    
    def check_timeouts(self) -> List[str]:
        """
        檢查超時的氣吹指令
        超時未收到 ACK 的記錄為未處理，交由後端人工分選
        
        Returns:
            List[str]: 超時的氣吹 ID 列表
        """
        current_time = datetime.now()
        timeout_ids = []
        
        for blow_id, command in list(self.pending_blows.items()):
            elapsed_ms = (current_time - command.timestamp).total_seconds() * 1000
            
            if elapsed_ms > self.ack_timeout_ms:
                timeout_ids.append(blow_id)
                
                # 記錄失敗的氣吹
                self.failed_blows.append({
                    'blow_id': blow_id,
                    'track_id': command.track_id,
                    'cx': command.cx,
                    'cy': command.cy,
                    'class_id': command.class_id,
                    'confidence': command.confidence,
                    'reason': 'ACK_TIMEOUT',
                    'timestamp': current_time,
                    'elapsed_ms': elapsed_ms
                })
                
                self.logger.warning(
                    f"Blow timeout: {blow_id}, Track={command.track_id}, "
                    f"elapsed={elapsed_ms:.1f}ms > {self.ack_timeout_ms}ms"
                )
                
                del self.pending_blows[blow_id]
        
        return timeout_ids
    
    def _generate_blow_id(self) -> str:
        """
        生成唯一的氣吹 ID
        
        Returns:
            str: 氣吹 ID
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"BLOW_{timestamp}_{self.blow_count}"
    
    def get_statistics(self) -> Dict:
        """
        獲取統計資訊
        
        Returns:
            dict: 統計資訊
        """
        total = self.blow_count
        successful = len(self.successful_blows)
        failed = len(self.failed_blows)
        pending = len(self.pending_blows)
        
        success_rate = (successful / total * 100) if total > 0 else 0
        
        return {
            'total_blows': total,
            'successful': successful,
            'failed': failed,
            'pending': pending,
            'success_rate': success_rate
        }
    
    def print_statistics(self) -> None:
        """列印統計資訊"""
        stats = self.get_statistics()
        print("\n" + "="*60)
        print("BLOW CONTROLLER STATISTICS")
        print("="*60)
        print(f"Total Blows:     {stats['total_blows']}")
        print(f"Successful:      {stats['successful']} ({stats['success_rate']:.1f}%)")
        print(f"Failed (Timeout):{stats['failed']}")
        print(f"Pending:         {stats['pending']}")
        print("="*60 + "\n")
    
    def reset_statistics(self) -> None:
        """重置統計資訊"""
        self.successful_blows.clear()
        self.failed_blows.clear()
        self.blow_count = 0
        self.logger.info("Statistics reset")
