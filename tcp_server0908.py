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
        
        新格式: trigger_num,物件數量,class_id,center_x,center_y,width,height,class_id2,center_x2,center_y2,width2,height2,...,0,0,0,0
        保持YOLO原始格式：正規化座標(0-1)和中心點座標
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
                        boxes = detection.boxes.xyxy.cpu().numpy()
                        confs = detection.boxes.conf.cpu().numpy()
                        classes = detection.boxes.cls.cpu().numpy()
                        
                        for (box, conf, cls) in zip(boxes, confs, classes):
                            x1, y1, x2, y2 = box
                            
                            # 計算中心點和寬高 (正規化到0-1)
                            center_x = ((x1 + x2) / 2) / image_width
                            center_y = ((y1 + y2) / 2) / image_height
                            width = (x2 - x1) / image_width
                            height = (y2 - y1) / image_height
                            
                            # 添加物件資料: class_id,center_x,center_y,width,height
                            detection_data.extend([
                                int(cls),              # class_id
                                f"{center_x:.6f}",     # center_x (6位小數)
                                f"{center_y:.6f}",     # center_y (6位小數)
                                f"{width:.6f}",        # width (6位小數)
                                f"{height:.6f}"        # height (6位小數)
                            ])
                            object_count += 1
            
            # 構建訊息: trigger_num,物件數量,物件資料...,結尾4個點
            message_parts = [self.trigger_count, object_count]
            message_parts.extend(detection_data)
            message_parts.extend([0, 0, 0, 0])  # 結尾4個點
            
            # 轉換成字串
            message = ",".join(map(str, message_parts)) + "\n"
            
            if self.send_message(message):
                if object_count > 0:
                    print(f"Sent to LabVIEW: Trigger {self.trigger_count}, {object_count} objects detected")
                else:
                    print(f"Sent to LabVIEW: Trigger {self.trigger_count}, no objects detected")
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