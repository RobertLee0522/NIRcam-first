import cv2
import numpy as np
from multiprocessing import shared_memory
import socket

def receive_shared_memory_name_via_tcpip(host='127.0.0.1', port=65432):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        print(f"Listening for connection on {host}:{port}...")
        while True:
            print("Waiting for a connection...")
            conn, addr = s.accept()
            print(f"Connected by {addr}")
            with conn:
                # 接收合併後的資料
                data = conn.recv(1024).decode()
                if not data:
                    print("Failed to receive data.")
                    continue
                
                # 將資料分割成 shm_name 和 trigger_num
                try:
                    shm_name, trigger_num_str = data.split(',')
                    trigger_num = int(trigger_num_str)
                    print(f"Received shared memory name: {shm_name}")
                    print(f"Received trigger number: {trigger_num}")
                except ValueError as e:
                    print(f"Error parsing data: {e}")
                    continue
                
                return shm_name, trigger_num  # 返回共享記憶體名稱和 trigger_num 並退出循環


def process_image_from_shared_memory(shm_name, image_shape):
    try:

        print(f"Attempting to connect to shared memory: {shm_name[0]}")
        existing_shm = shared_memory.SharedMemory(name=shm_name[0])
        print(f"Successfully connected to shared memory '{shm_name[0]}'")
        
        image_flatten = np.ndarray(existing_shm.size, dtype=np.uint8, buffer=existing_shm.buf)
        if image_flatten.size != np.prod(image_shape):
            print(f"Error: Flattened image size {image_flatten.size} does not match expected size {np.prod(image_shape)}.")
            return

        # 將一維數組重新變形為圖片
        try:
            image = image_flatten.reshape(image_shape)
            cv2.imshow('Received Image', image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
            
        except Exception as e:
            print(f"Error reshaping image: {e}")

        # 釋放共享記憶體
        existing_shm.close()
    except FileNotFoundError:
        print(f"Shared memory '{shm_name[0]}' not found.")
    except Exception as e:
        print(f"Error connecting to shared memory: {e}")


# 使用範例
image_shape = (2048, 2200, 3)  # 替換為實際圖像尺寸
while True:
    shm_name = receive_shared_memory_name_via_tcpip()
    if shm_name:
        process_image_from_shared_memory(shm_name, image_shape)
                # 檢查按鍵事件以退出
        key = cv2.waitKey(1)  # 等待1毫秒
        if key == ord('c') or key == ord('C'):
            print("Exit command received. Exiting...")
            cv2.destroyAllWindows()
            break
    else:
        print("No shared memory name received, exiting.")
        break
# 確保程序退出時釋放所有資源
cv2.destroyAllWindows()