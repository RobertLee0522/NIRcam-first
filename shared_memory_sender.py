import numpy as np
from multiprocessing import shared_memory
import socket
import time

class SharedMemorySender:
    """
    獨立的共享內存發送器，負責將 NumPy 圖像數據寫入共享內存，
    並通過 Socket 發送名稱和元數據給接收端。
    """
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.shm = None
        self.shm_name = None
        self.trigger_count = 0  # 添加這行
        self.socket = None
        self.connect()  # 啟動時就連線
        print(f"SharedMemorySender initialized. Target: {self.host}:{self.port}")
    def connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            print(f"✅ Connected to receiver at {self.host}:{self.port}")
        except Exception as e:
            print(f"❌ Failed to connect to receiver: {e}")
            self.socket = None
    def is_connected(self):
        """檢查是否已連接"""
        return self.socket is not None  # 添加這個方法    

    def send_image(self, image: np.ndarray, trigger_num: int):
        """發送圖像到共享內存"""
        self.trigger_num = trigger_num
        
        # 1. 清理舊共享內存
        if self.shm is not None:
            try:
                self.shm.close()
                self.shm.unlink()
            except:
                pass
            self.shm = None
            self.shm_name = None
    
        try:
            # 2. 確保圖像是連續的內存塊
            if not image.flags['C_CONTIGUOUS']:
                image = np.ascontiguousarray(image)
            
            # 3. 創建共享內存
            self.shm = shared_memory.SharedMemory(create=True, size=image.nbytes)
            self.shm_name = self.shm.name
            
            # 4. 寫入數據
            shm_array = np.ndarray(image.shape, dtype=image.dtype, buffer=self.shm.buf)
            shm_array[:] = image[:]
            
            # 5. 發送 metadata
            self._send_shared_memory_name(self.shm_name, trigger_num, image.shape, image.dtype)
            
            return self.shm_name
    
        except Exception as e:
            print(f"❌ Error during shared memory operations: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _send_shared_memory_name(self, shm_name: str, trigger_num: int, shape, dtype):
        """發送 metadata"""
        if not self.is_connected():
            print("⚠️ Not connected, retrying...")
            self.connect()
            if not self.is_connected():
                return
    
        try:
            # 將 shape 轉換為字符串，用逗號分隔
            shape_str = 'x'.join(map(str, shape))  # 例如: "480x640x3"
            dtype_str = str(dtype)
            message = f"{shm_name},{trigger_num},{shape_str},{dtype_str}\n"  # 加換行符
            
            self.socket.sendall(message.encode('utf-8'))
            print(f"📤 Sent metadata: trigger={trigger_num}, shape={shape}, dtype={dtype}")
            
        except Exception as e:
            print(f"❌ Socket send failed: {e}")
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

    def close(self):
        """
        在程式結束時調用，釋放和刪除共享內存。
        """
        if self.shm is not None:
            try:
                self.shm.close()
                self.shm.unlink()
                print(f"Shared memory {self.shm_name} successfully closed and unlinked.")
            except Exception as e:
                pass # 忽略清理時的錯誤
            self.shm = None
            self.shm_name = None

# end of shared_memory_sender.py