# tcp_server.py
import socket
import threading
import json
import time

class TCPServer:
    def __init__(self, host='localhost', port=8888):
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_socket = None
        self.client_address = None
        self.is_running = False
        self.is_connected = False
        self.server_thread = None
        self.trigger_count = 0  # 觸發計數器
        
    def start_server(self):
        """啟動TCP伺服器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(1)
            self.is_running = True
            
            print(f"TCP Server started on {self.host}:{self.port}")
            print("Waiting for LabVIEW client connection...")
            
            # 在新線程中等待連接
            self.server_thread = threading.Thread(target=self._wait_for_connection)
            self.server_thread.daemon = True
            self.server_thread.start()
            
            return True
            
        except Exception as e:
            print(f"Failed to start TCP server: {e}")
            return False
    
    def _wait_for_connection(self):
        """等待客戶端連接"""
        while self.is_running:
            try:
                self.client_socket, self.client_address = self.server_socket.accept()
                self.is_connected = True
                print(f"LabVIEW client connected from {self.client_address}")
                
                # 發送連線成功訊息
                welcome_message = "TCP_CONNECTION_SUCCESS\n"
                self.send_message(welcome_message)
                
                # 保持連接活躍
                self._keep_connection_alive()
                
            except socket.error as e:
                if self.is_running:
                    print(f"Connection error: {e}")
                break
    
    def _keep_connection_alive(self):
        """保持連接活躍"""
        while self.is_connected and self.is_running:
            try:
                # 每5秒發送一次心跳
                time.sleep(5)
                if self.is_connected:
                    heartbeat = "HEARTBEAT\n"
                    print(f"{heartbeat}")
                    #self.send_message(heartbeat)
            except:
                break
    
    def send_message(self, message):
        """發送訊息到LabVIEW"""
        if self.is_connected and self.client_socket:
            try:
                self.client_socket.send(message.encode('utf-8'))
                return True
            except socket.error as e:
                print(f"Failed to send message: {e}")
                self.is_connected = False
                return False
        return False
    
    def send_detection_result(self, detections, image_width, image_height):
        """發送辨識結果到LabVIEW
        
        新格式: trigger_num,照片寬度,照片高度,物件數量,label1,x1_pixel,y1_pixel,x2_pixel,y2_pixel,label2,x2,y2,x2,y2,...,結尾4個點(0,0,0,0)
        """
        self.trigger_count += 1
        
        if not self.is_connected:
            print("No LabVIEW client connected")
            return False
        
        try:
            detection_data = []
            object_count = 0
            
            if detections and len(detections) > 0:
                # 有檢測到物件
                for detection in detections:
                    if hasattr(detection, 'boxes') and detection.boxes is not None:
                        boxes = detection.boxes.xyxy.cpu().numpy()  # 已經是像素座標格式 (x1, y1, x2, y2)
                        confs = detection.boxes.conf.cpu().numpy()
                        classes = detection.boxes.cls.cpu().numpy()
                        
                        for (box, conf, cls) in zip(boxes, confs, classes):
                            x1, y1, x2, y2 = box
                            
                            # 確保座標在圖像範圍內
                            x1 = max(0, min(int(x1), image_width - 1))
                            y1 = max(0, min(int(y1), image_height - 1))
                            x2 = max(0, min(int(x2), image_width - 1))
                            y2 = max(0, min(int(y2), image_height - 1))
                            
                            # 添加物件資料: label,x1_pixel,y1_pixel,x2_pixel,y2_pixel
                            detection_data.extend([
                                int(cls),      # label
                                x1,            # x1_pixel (左上角x座標)
                                y1,            # y1_pixel (左上角y座標)
                                x2,            # x2_pixel (右下角x座標)
                                y2             # y2_pixel (右下角y座標)
                            ])
                            object_count += 1
            
            # 構建訊息: trigger_num,照片寬度,照片高度,物件數量,物件資料...,結尾4個點
            message_parts = [
                ";",
                self.trigger_count,     # 觸發編號
                image_width,            # 照片寬度(像素)
                image_height,           # 照片高度(像素) 
                object_count            # 物件數量
            ]
            message_parts.extend(detection_data)    # 物件資料
            message_parts.extend([0, 0, 0, 0])      # 結尾4個點
            
            # 轉換成字串
            message = ",".join(map(str, message_parts)) + "\n"
            
            if self.send_message(message):
                if object_count > 0:
                    print(f"Sent to LabVIEW1122: Trigger {self.trigger_count}, Image({image_width}x{image_height}), {object_count} objects detected")
                    # 顯示每個物件的像素座標
                    for i in range(object_count):
                        idx = 5 + i * 5  # 跳過trigger_num, width, height, count
                        label = message_parts[idx]
                        x1, y1, x2, y2 = message_parts[idx+1:idx+5]
                        print(f"  Object {i+1}: Label={label}, BBox=({x1},{y1})-({x2},{y2}) pixels")
                else:
                    print(f"Sent to LabVIEW0099: Trigger {self.trigger_count}, Image({image_width}x{image_height}), no objects detected")
                print(f"Raw message: {message.strip()}")
                return True
            else:
                return False
                    
        except Exception as e:
            print(f"Error sending detection result: {e}")
            return False
    
    def send_detection_result_with_center_and_size(self, detections, image_width, image_height):
        """發送辨識結果到LabVIEW (中心點+寬高格式)
        
        格式: trigger_num,照片寬度,照片高度,物件數量,label1,center_x,center_y,width,height,label2,center_x,center_y,width,height,...,結尾4個點(0,0,0,0)
        """
        self.trigger_count += 1
        
        if not self.is_connected:
            print("No LabVIEW client connected")
            return False
        
        try:
            detection_data = []
            object_count = 0
            
            if detections and len(detections) > 0:
                # 有檢測到物件
                for detection in detections:
                    if hasattr(detection, 'boxes') and detection.boxes is not None:
                        boxes = detection.boxes.xyxy.cpu().numpy()  # (x1, y1, x2, y2)
                        confs = detection.boxes.conf.cpu().numpy()
                        classes = detection.boxes.cls.cpu().numpy()
                        
                        for (box, conf, cls) in zip(boxes, confs, classes):
                            x1, y1, x2, y2 = box
                            
                            # 計算中心點和寬高 (像素座標)
                            center_x = int((x1 + x2) / 2)
                            center_y = int((y1 + y2) / 2)
                            width = int(x2 - x1)
                            height = int(y2 - y1)
                            
                            # 確保座標在圖像範圍內
                            center_x = max(0, min(center_x, image_width - 1))
                            center_y = max(0, min(center_y, image_height - 1))
                            
                            # 添加物件資料: label,center_x,center_y,width,height
                            detection_data.extend([
                                int(cls),      # label
                                center_x,      # 中心點x座標(像素)
                                center_y,      # 中心點y座標(像素)
                                width,         # 寬度(像素)
                                height         # 高度(像素)
                            ])
                            object_count += 1
            
            # 構建訊息
            message_parts = [
                self.trigger_count,     # 觸發編號
                image_width,            # 照片寬度(像素)
                image_height,           # 照片高度(像素) 
                object_count            # 物件數量
            ]
            message_parts.extend(detection_data)    # 物件資料
            message_parts.extend([0, 0, 0, 0])      # 結尾4個點
            
            # 轉換成字串
            message = ",".join(map(str, message_parts)) + "\n"
            
            if self.send_message(message):
                if object_count > 0:
                    print(f"Sent to LabVIEW1234: Trigger {self.trigger_count}, Image({image_width}x{image_height}), {object_count} objects detected")
                    # 顯示每個物件的像素座標
                    for i in range(object_count):
                        idx = 4 + i * 5  # 跳過trigger_num, width, height, count
                        label = message_parts[idx]
                        center_x, center_y, width, height = message_parts[idx+1:idx+5]
                        print(f"  Object {i+1}: Label={label}, Center=({center_x},{center_y}), Size={width}x{height} pixels")
                else:
                    print(f"Sent to LabVIEW5678: Trigger {self.trigger_count}, Image({image_width}x{image_height}), no objects detected")
                print(f"Raw message: {message.strip()}")
                return True
            else:
                return False
                    
        except Exception as e:
            print(f"Error sending detection result: {e}")
            return False
    
    def get_connection_status(self):
        """獲取連接狀態"""
        return {
            'server_running': self.is_running,
            'client_connected': self.is_connected,
            'trigger_count': self.trigger_count
        }
    
    def stop_server(self):
        """停止TCP伺服器"""
        self.is_running = False
        self.is_connected = False
        
        try:
            if self.client_socket:
                self.client_socket.close()
                
            if self.server_socket:
                self.server_socket.close()
                
            print("TCP Server stopped")
            
        except Exception as e:
            print(f"Error stopping server: {e}")

# 全域TCP伺服器實例
tcp_server = None

def start_tcp_server(host='localhost', port=8888):
    """啟動TCP伺服器"""
    global tcp_server
    if tcp_server is None:
        tcp_server = TCPServer(host, port)
    return tcp_server.start_server()

def get_tcp_server():
    """獲取TCP伺服器實例"""
    global tcp_server
    return tcp_server

def stop_tcp_server():
    """停止TCP伺服器"""
    global tcp_server
    if tcp_server:
        tcp_server.stop_server()
        tcp_server = None