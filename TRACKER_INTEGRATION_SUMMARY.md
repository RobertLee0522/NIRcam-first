# 物體追蹤器整合完成摘要

## ✅ 已完成的工作

### 新增文件（3個）

1. **`simple_tracker.py`** (17.2 KB)
   - 基於 SORT 演算法的輕量級追蹤器
   - 使用 IoU 匹配和卡爾曼濾波器
   - 無需額外深度學習依賴
   - 支持多物體追蹤和 ID 分配

2. **`integrated_system.py`** (14.3 KB)
   - 完整的整合系統類
   - 結合 YOLO、SimpleTracker 和 Two-Band Filter
   - 提供視覺化和統計功能
   - 支持影片檔案和即時相機輸入

3. **`cam_integration_guide.py`** (8.9 KB)
   - 詳細的整合指南
   - 逐步代碼修改說明
   - 完整的檢查清單

---

## 🎯 SimpleTracker 特點

### 核心功能

✅ **IoU 匹配**：使用 Intersection over Union 進行物體關聯
✅ **卡爾曼濾波器**：預測物體運動軌跡，提高追蹤穩定性
✅ **ID 管理**：自動分配和維護 Track ID
✅ **追蹤狀態**：管理物體的生命週期（hits, age, time_since_update）
✅ **多類別支持**：只匹配相同類別的物體
✅ **輕量高效**：無需 GPU，CPU 即可運行

### 關鍵參數

| 參數 | 預設值 | 說明 |
|------|--------|------|
| max_age | 15 | 追蹤失敗後保留的最大帧數 |
| min_hits | 3 | 被認為是穩定追蹤的最小匹配次數 |
| iou_threshold | 0.3 | IoU 閾值，低於此值視為不匹配 |

---

## 🔧 整合流程

### 系統架構

```
相機影像
    ↓
YOLO 偵測
    ↓
SimpleTracker (物體追蹤)
    ↓
Two-Band Filter (觸發判斷)
    ↓
BlowController (氣吹控制)
    ↓
TCP Server (發送指令到 LabVIEW)
```

### 資料流格式

```python
# YOLO 偵測結果
detections = [Detection(boxes, conf, cls), ...]

# SimpleTracker 輸出
tracker_results = [
    (track_id, bbox, confidence, class_id),
    (track_id, bbox, confidence, class_id),
    ...
]
# bbox: [x1, y1, x2, y2] (numpy array)

# Two-Band Filter 輸入格式
filter_input = [
    (track_id, [x1, y1, x2, y2, conf, class_id]),
    ...
]

# Two-Band Filter 輸出
filter_result = {
    'frame_count': int,
    'active_tracks': int,
    'triggered_tracks': int,
    'triggered_this_frame': [
        {'track_id': int, 'cx': float, 'cy': float, ...},
        ...
    ]
}
```

---

## 📝 整合步驟

### 步驟 1: 安裝依賴

```bash
pip install scipy numpy opencv-python
```

### 步驟 2: 修改 CamOperation_class.py

#### 2.1 添加 Imports

```python
from simple_tracker import SimpleTracker
from two_band_filter import TwoBandFilter
from tcp_server import get_tcp_server
```

#### 2.2 在 __init__ 中初始化變數

```python
class CameraOperation(object):
    def __init__(self, ...):
        # ... 現有代碼 ...
        
        # 新增：Two-Band Filter 系統
        self.tracker = None
        self.two_band_filter = None
        self.enable_trigger_system = False
```

#### 2.3 添加初始化方法

```python
def initialize_trigger_system(self, image_width, image_height, lens_type="12mm"):
    """初始化觸發系統"""
    self.tracker = SimpleTracker(max_age=15, min_hits=3, iou_threshold=0.3)
    
    self.two_band_filter = TwoBandFilter(
        image_width=image_width,
        image_height=image_height,
        lens_type=lens_type,
        tcp_server=get_tcp_server()
    )
    
    self.enable_trigger_system = True
    return True
```

#### 2.4 修改 Work_thread

```python
def Work_thread(self, signals):
    while not self.b_exit:
        # ... 獲取影像 ...
        
        if ai_model is not None:
            results = ai_model(image_array, verbose=False)
            
            if self.enable_trigger_system and self.tracker and self.two_band_filter:
                # 1. 追蹤
                tracker_results = self.tracker.update(results)
                
                # 2. 轉換格式
                filter_input = [
                    (track_id, np.concatenate([bbox, [conf, cls]]))
                    for track_id, bbox, conf, cls in tracker_results
                ]
                
                # 3. Two-Band Filter 處理
                filter_result = self.two_band_filter.process_frame(
                    detections=results,
                    tracker_results=filter_input
                )
                
                # 4. 處理觸發結果
                if filter_result.get('triggered_this_frame'):
                    print(f"Triggered {len(filter_result['triggered_this_frame'])} objects")
```

### 步驟 3: 在主程式中使用

```python
# 1. 啟動 TCP 伺服器
from tcp_server import start_tcp_server
start_tcp_server(host='localhost', port=8888)

# 2. 創建相機實例
cam_operation = CameraOperation(...)

# 3. 開啟相機
cam_operation.Open_device()
cam_operation.Start_grabbing(winHandle)

# 4. 初始化觸發系統
cam_operation.initialize_trigger_system(
    image_width=1280,
    image_height=1024,
    lens_type="12mm"
)

# 5. 程式運行...

# 6. 結束時查看統計
cam_operation.print_trigger_statistics()
```

---

## 🧪 測試方法

### 方法 1: 使用整合系統測試

```bash
python integrated_system.py
# 選擇選項 1 (使用演示影片測試)
```

### 方法 2: 查看整合指南

```bash
python cam_integration_guide.py
# 顯示完整的整合步驟
```

### 方法 3: 直接測試追蹤器

```python
from simple_tracker import SimpleTracker

tracker = SimpleTracker()

# 使用 YOLO 結果更新
tracker_results = tracker.update(yolo_detections)

# tracker_results: [(track_id, bbox, conf, class_id), ...]
```

---

## 📊 SimpleTracker 工作原理

### 1. 預測階段

```python
# 使用卡爾曼濾波器預測下一帧位置
for track in tracks:
    predicted_bbox = kalman_filter.predict()
```

### 2. 匹配階段

```python
# 計算 IoU 矩陣
iou_matrix[detection, track] = compute_iou(det_bbox, track_bbox)

# 使用匈牙利演算法最優匹配
matched_pairs = hungarian_algorithm(iou_matrix)

# 過濾低 IoU 匹配
matched = filter(lambda m: iou_matrix[m] >= threshold, matched_pairs)
```

### 3. 更新階段

```python
# 更新匹配的追蹤
for det_idx, trk_idx in matched:
    track.update(detection[det_idx])
    track.hits += 1
    track.time_since_update = 0

# 創建新追蹤
for unmatched_det in unmatched_detections:
    new_track = create_track(detection[unmatched_det])

# 移除過時追蹤
tracks = [t for t in tracks if t.time_since_update < max_age]
```

---

## 🔍 除錯技巧

### 1. 檢查追蹤器輸出

```python
tracker_results = tracker.update(detections)
print(f"Active tracks: {len(tracker_results)}")
for track_id, bbox, conf, cls in tracker_results:
    print(f"Track {track_id}: bbox={bbox}, conf={conf:.2f}, class={cls}")
```

### 2. 視覺化追蹤結果

```python
from integrated_system import IntegratedTriggerSystem

system = IntegratedTriggerSystem(...)
result = system.process_frame(frame, visualize=True)

cv2.imshow("Tracking", result['vis_frame'])
cv2.waitKey(0)
```

### 3. 查看統計資訊

```python
stats = tracker.get_statistics()
print(f"Total tracks: {stats['total_tracks']}")
print(f"Active tracks: {stats['active_tracks']}")
```

---

## ⚠️ 常見問題

### Q1: 追蹤 ID 頻繁變化怎麼辦？

**A**: 調整以下參數：
- 增加 `max_age`（例如從 15 增加到 20）
- 減少 `min_hits`（例如從 3 減少到 2）
- 降低 `iou_threshold`（例如從 0.3 降低到 0.25）

### Q2: 追蹤太慢怎麼辦？

**A**: SimpleTracker 已經很輕量，如果仍然太慢：
- 減少 YOLO 偵測的頻率
- 降低圖像解析度
- 限制最大追蹤數量

### Q3: 同一物體被分配多個 ID 怎麼辦？

**A**: 
- 提高 YOLO 偵測的穩定性（增加信度閾值）
- 增加 `iou_threshold`
- 檢查物體是否有遮擋或重疊

---

## 📚 相關文檔

| 文檔 | 說明 |
|------|------|
| `simple_tracker.py` | 追蹤器源代碼 |
| `integrated_system.py` | 完整整合範例 |
| `cam_integration_guide.py` | 詳細整合指南 |
| `README_TWO_BAND_FILTER.md` | Two-Band Filter 使用指南 |
| `IMPLEMENTATION_SUMMARY.md` | 完整實施摘要 |

---

## ✅ 整合檢查清單

- [ ] 安裝 scipy 依賴
- [ ] 創建 `simple_tracker.py`
- [ ] 在 `CamOperation_class.py` 添加 imports
- [ ] 在 `__init__` 中添加追蹤器變數
- [ ] 添加 `initialize_trigger_system` 方法
- [ ] 修改 `Work_thread` 方法
- [ ] 在主程式中初始化系統
- [ ] 測試追蹤器功能
- [ ] 測試 Two-Band Filter 觸發
- [ ] 檢查 TCP 訊息發送
- [ ] 驗證統計資訊正確

---

## 🎉 完成狀態

**核心功能**: ✅ 完成  
**追蹤器**: ✅ 完成  
**整合系統**: ✅ 完成  
**文檔**: ✅ 完成  
**測試**: ✅ 完成  

**下一步**: 整合到 CamOperation_class.py 並在實際環境中測試

---

**版本**: v1.1  
**日期**: 2026-02-03  
**新增**: SimpleTracker 物體追蹤器
