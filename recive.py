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
                
                print(f"Raw data received: '{data}'")
                print(f"Data length: {len(data)}")
                
                # 將資料分割成 shm_name 和 trigger_num
                try:
                    parts = data.split(',')
                    print(f"Split into {len(parts)} parts: {parts}")
                    
                    if len(parts) >= 2:
                        shm_name = parts[0].strip()
                        trigger_num = int(parts[1].strip())
                        print(f"Received shared memory name: {shm_name}")
                        print(f"Received trigger number: {trigger_num}")
                    else:
                        print(f"Error: Expected at least 2 parts, got {len(parts)}")
                        continue
                except ValueError as e:
                    print(f"Error parsing data: {e}")
                    continue
                
                return shm_name, trigger_num  # 返回共享記憶體名稱和 trigger_num 並退出循環


def process_image_from_shared_memory(shm_name, image_shape, output_filename='sharedmemory.jpg'):
    try:
        print(f"Attempting to connect to shared memory: {shm_name[0]}")
        existing_shm = shared_memory.SharedMemory(name=shm_name[0])
        print(f"Successfully connected to shared memory '{shm_name[0]}'")
        print(f"Shared memory size: {existing_shm.size} bytes")
        
        image_flatten = np.ndarray(existing_shm.size, dtype=np.uint8, buffer=existing_shm.buf)
        
        # 檢查尺寸是否匹配，如果不匹配則嘗試自動計算
        expected_size = np.prod(image_shape)
        if image_flatten.size != expected_size:
            print(f"Warning: Size mismatch. Expected {expected_size}, got {image_flatten.size}")
            
            # 嘗試自動計算可能的圖像尺寸（假設是3通道RGB）
            if image_flatten.size % 3 == 0:
                total_pixels = image_flatten.size // 3
                print(f"Total pixels (assuming 3 channels): {total_pixels}")
                
                # 嘗試找到合理的寬高比
                height = int(np.sqrt(total_pixels / (2200/2048)))  # 使用原始比例估算
                width = total_pixels // height
                
                if height * width * 3 == image_flatten.size:
                    image_shape = (height, width, 3)
                    print(f"Auto-detected image shape: {image_shape}")
                else:
                    # 如果計算不精確，直接使用實際大小
                    print(f"Trying to reshape with actual size...")
                    # 嘗試常見的解析度
                    possible_shapes = [
                        (2048, image_flatten.size // (2048 * 3), 3),
                        (2176, image_flatten.size // (2176 * 3), 3),
                        (2200, image_flatten.size // (2200 * 3), 3),
                    ]
                    for shape in possible_shapes:
                        if np.prod(shape) == image_flatten.size:
                            image_shape = shape
                            print(f"Found matching shape: {image_shape}")
                            break
            else:
                print(f"Error: Image size is not divisible by 3 (not RGB)")
                existing_shm.close()
                return False

        # 將一維數組重新變形為圖片
        try:
            image = image_flatten.reshape(image_shape)
            
            # 儲存圖片而不是顯示
            cv2.imwrite(output_filename, image)
            print(f"Image saved to '{output_filename}'. Shape: {image.shape}, Trigger number: {shm_name[1]}")
            
        except Exception as e:
            print(f"Error reshaping/saving image: {e}")
            existing_shm.close()
            return False

        # 釋放共享記憶體
        existing_shm.close()
        return True
        
    except FileNotFoundError:
        print(f"Shared memory '{shm_name[0]}' not found.")
        return False
    except Exception as e:
        print(f"Error connecting to shared memory: {e}")
        return False


# 使用範例
image_shape = (2048, 2448, 3)  # 根據實際檢測到的圖像尺寸
output_filename = 'sharedmemory.jpg'

print(f"Starting image receiver. Images will be saved to '{output_filename}' and continuously updated.")
print("Press Ctrl+C to exit.")

try:
    while True:
        shm_name = receive_shared_memory_name_via_tcpip()
        if shm_name:
            success = process_image_from_shared_memory(shm_name, image_shape, output_filename)
            
            if not success:
                print("Failed to process image, but continuing to listen...")
        else:
            print("No shared memory name received.")
            break
            
except KeyboardInterrupt:
    print("\nKeyboard interrupt received. Exiting...")
finally:
    print("Program terminated.")