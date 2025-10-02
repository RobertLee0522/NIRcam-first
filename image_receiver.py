"""
共享內存接收端程式 (配合 SharedMemorySender 使用)
- 透過 TCP 接收 metadata (共享內存名稱、shape、dtype、trigger_num)
- attach 到共享內存讀取影像
"""

import socket
import numpy as np
import cv2
from multiprocessing import shared_memory
from datetime import datetime

class SharedMemoryReceiver:
    def __init__(self, host='127.0.0.1', port=9999):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.is_running = False
        self.received_count = 0

    def start(self):
        """啟動接收服務器，等待發送端連線"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.is_running = True

            print(f"✅ 接收器已啟動")
            print(f"📡 監聽地址: {self.host}:{self.port}")
            print(f"⏳ 等待發送端連接...\n")

            self.client_socket, addr = self.server_socket.accept()
            print(f"✅ 發送端已連接: {addr}\n")
            print("=" * 60)

            return True

        except Exception as e:
            print(f"❌ 啟動失敗: {e}")
            return False

    def receive_image(self):
        """接收圖像"""
        try:
            # 接收數據（增加緩衝區大小）
            data = self.client_socket.recv(4096).decode("utf-8").strip()
            if not data:
                return None, None
    
            # 解析 metadata: shm_name,trigger_num,shape_str,dtype_str
            parts = data.split(",")
            if len(parts) < 4:
                print(f"⚠️ Invalid metadata format: {data}")
                return None, None
    
            shm_name = parts[0]
            trigger_num = int(parts[1])
            
            # 解析 shape（例如 "480x640x3" -> (480, 640, 3)）
            shape_str = parts[2]
            shape = tuple(map(int, shape_str.split('x')))
            
            dtype = np.dtype(parts[3])
    
            # Attach 到共享內存
            shm = shared_memory.SharedMemory(name=shm_name)
            image = np.ndarray(shape, dtype=dtype, buffer=shm.buf).copy()
            shm.close()
    
            self.received_count += 1
    
            print(f"📥 接收第 {self.received_count} 幀")
            print(f"   觸發計數: {trigger_num}")
            print(f"   圖像尺寸: {shape}")
            print(f"   dtype: {dtype}")
            print(f"   時間戳: {datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print("-" * 60)
    
            return image, trigger_num
    
        except Exception as e:
            print(f"❌ 接收失敗: {e}")
            import traceback
            traceback.print_exc()
            return None, None

    def close(self):
        """關閉連接"""
        self.is_running = False
        if self.client_socket:
            self.client_socket.close()
            print("✅ 客戶端連接已關閉")
        if self.server_socket:
            self.server_socket.close()
            print("✅ 服務器已關閉")
        print(f"📊 總共接收: {self.received_count} 幀")

def main():
    HOST = "127.0.0.1"
    PORT = 9999
    DISPLAY_IMAGES = True

    receiver = SharedMemoryReceiver(HOST, PORT)
    if not receiver.start():
        return

    print("🎯 開始接收圖像 (按 q 退出)\n")

    try:
        while receiver.is_running:
            image, trigger_num = receiver.receive_image()
            if image is None:
                print("⚠️ 連接中斷")
                break

            if DISPLAY_IMAGES:
                display_image = cv2.resize(image, (640, 480))
                cv2.putText(display_image, f"Frame {trigger_num}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                cv2.imshow("Shared Memory Receiver", display_image)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    finally:
        receiver.close()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    main()