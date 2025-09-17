import cv2
import numpy as np
from ultralytics import YOLO
import math
import traceback

def load_model(weights):
    """載入YOLOv11模型"""
    try:
        model = YOLO(weights)
        print("YOLOv11 model loaded successfully")
        return model
    except Exception as e:
        print(f"Error loading model: {e}")
        traceback.print_exc()
        return None

def detect_objects(model, img, conf_thres=0.25, iou_thres=0.45, imgsz=1280):
    """使用YOLOv11進行物件偵測"""
    try:
        results = model(img, imgsz=imgsz, conf=conf_thres, iou=iou_thres)
        return results
    except Exception as e:
        print(f"Error detecting objects: {e}")
        traceback.print_exc()
        return None

def calculate_diagonal_length(x1, y1, x2, y2):
    """計算邊界框的斜邊長度"""
    width = x2 - x1
    height = y2 - y1
    diagonal = math.sqrt(width**2 + height**2)
    return diagonal

def draw_custom_boxes(frame, results):
    """自定義繪製邊界框，包含斜邊長度資訊"""
    annotated_frame = frame.copy()
    
    if results and results[0].boxes is not None:
        boxes = results[0].boxes.xyxy.cpu().numpy()
        confs = results[0].boxes.conf.cpu().numpy()
        classes = results[0].boxes.cls.cpu().numpy()
        names = results[0].names
        
        for (box, conf, cls) in zip(boxes, confs, classes):
            x1, y1, x2, y2 = map(int, box)
            diagonal = calculate_diagonal_length(x1, y1, x2, y2)
            class_name = names[int(cls)]
            
            cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{class_name} {conf:.2f} Diag:{diagonal:.1f}"
            
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            (text_width, text_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
            cv2.rectangle(annotated_frame, 
                         (x1, y1 - text_height - baseline - 5), 
                         (x1 + text_width, y1), 
                         (0, 255, 0), -1)
            cv2.putText(annotated_frame, label, 
                       (x1, y1 - baseline - 2), 
                       font, font_scale, (0, 0, 0), thickness)
    
    return annotated_frame
