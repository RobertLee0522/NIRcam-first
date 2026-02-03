# 🎉 CamOperation_class.py 整合完成！

## ✅ 已完成的修改

### 1. 添加 Imports（行 36-44）
```python
# 匯入 Two-Band Filter 觸發系統
try:
    from simple_tracker import SimpleTracker
    from two_band_filter import TwoBandFilter
except ImportError:
    print("Warning: Two-Band Filter system not found. Trigger system will be disabled.")
    SimpleTracker = None
    TwoBandFilter = None
```

### 2. 在 `__init__` 中添加變數（行 193-198）
```python
# ========== Two-Band Filter 觸發系統 ==========
self.tracker = None
self.two_band_filter = None
self.enable_trigger_system = False  # 是否啟用觸發系統
# ==============================================
```

### 3. 添加初始化和控制方法（行 378-453）
- `initialize_trigger_system(image_width, image_height, lens_type)` - 初始化系統
- `disable_trigger_system()` - 停用觸發系統
- `enable_trigger_system_func()` - 啟用觸發系統
- `get_trigger_statistics()` - 獲取統計資訊
- `print_trigger_statistics()` - 列印統計資訊

### 4. 修改 `Work_thread` 方法（行 620-680）
整合物體追蹤器和 Two-Band Filter 到 AI 處理流程中

---

## 🚀 如何使用

### 方法 1: 在主程式中使用

```python
# 範例：BasicDemo.py 或其他主程式

from CamOperation_class import CameraOperation
from tcp_server import start_tcp_server, get_tcp_server

# 1. 啟動 TCP 伺服器
start_tcp_server(host='localhost', port=8888)

# 2. 創建相機實例（現有代碼）
cam_operation = CameraOperation(
    obj_cam=None,
    st_device_list=device_list,
    n_connect_num=0
)

# 3. 開啟相機
cam_operation.Open_device()

# 4. 開始取圖
cam_operation.Start_grabbing(winHandle)

# 5. 初始化觸發系統（新增步驟）
success = cam_operation.initialize_trigger_system(
    image_width=1280,      # 根據您的相機設定
    image_height=1024,     # 根據您的相機設定
    lens_type="12mm"       # 或 "8mm"
)

if success:
    print("✅ Trigger system initialized successfully!")
else:
    print("❌ Failed to initialize trigger system")

# 6. 開始運行（現有代碼）
# ... 您的主迴圈 ...

# 7. 結束時查看統計（可選）
cam_operation.print_trigger_statistics()

# 8. 停止相機（現有代碼）
cam_operation.Stop_grabbing()
cam_operation.Close_device()
```

### 方法 2: 在 GUI 中使用

```python
# 範例：PyUICBasicDemo.py 或其他 GUI 程式

from PyQt5.QtWidgets import QPushButton

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # ... 現有的 UI 初始化 ...
        
        # 添加初始化觸發系統按鈕
        self.btn_init_trigger = QPushButton("初始化觸發系統", self)
        self.btn_init_trigger.clicked.connect(self.on_init_trigger)
        
        # 添加查看統計按鈕
        self.btn_show_stats = QPushButton("查看統計", self)
        self.btn_show_stats.clicked.connect(self.on_show_stats)
    
    def on_init_trigger(self):
        """初始化觸發系統按鈕事件"""
        if hasattr(self, 'cam_operation'):
            success = self.cam_operation.initialize_trigger_system(
                image_width=1280,
                image_height=1024,
                lens_type="12mm"
            )
            
            if success:
                print("✅ 觸發系統初始化成功！")
            else:
                print("❌ 觸發系統初始化失敗")
    
    def on_show_stats(self):
        """查看統計按鈕事件"""
        if hasattr(self, 'cam_operation'):
            self.cam_operation.print_trigger_statistics()
```

---

## 📊 系統運行流程

```
相機取圖
    ↓
影像轉換（Bayer/Mono → BGR）
    ↓
共享記憶體發送（可選）
    ↓
YOLO 偵測
    ↓
┌─────────────────────────────────────┐
│ 如果啟用觸發系統 (enable_trigger_system=True)
├─────────────────────────────────────┤
│ 1. SimpleTracker 物體追蹤           │
│ 2. Two-Band Filter 觸發判斷         │
│ 3. BlowController 自動發送氣吹指令   │
│ 4. 列印觸發資訊                     │
└─────────────────────────────────────┘
    ↓
UI 更新（辨識結果、影像顯示）
```

---

## 🔧 啟用/停用觸發系統

### 啟用
```python
# 方法1：初始化時自動啟用
cam_operation.initialize_trigger_system(1280, 1024, "12mm")

# 方法2：手動啟用（如果已初始化）
cam_operation.enable_trigger_system_func()
```

### 停用
```python
# 臨時停用（不刪除追蹤器實例）
cam_operation.disable_trigger_system()

# 之後可以再啟用
cam_operation.enable_trigger_system_func()
```

---

## 📈 查看統計資訊

### 方法 1: 列印統計
```python
cam_operation.print_trigger_statistics()
```

輸出範例：
```
============================================================
TWO-BAND FILTER STATISTICS
============================================================
Frames Processed:    1523
Active Tracks:       3
Triggered Tracks:    47
Total Triggers:      47
Skipped (Reasons):   15
------------------------------------------------------------

============================================================
BLOW CONTROLLER STATISTICS
============================================================
Total Blows:     47
Successful:      45 (95.7%)
Failed (Timeout): 2
Pending:         0
============================================================
```

### 方法 2: 獲取統計資料
```python
stats = cam_operation.get_trigger_statistics()

if stats:
    print(f"總帧數: {stats['frame_count']}")
    print(f"觸發次數: {stats['trigger_count']}")
    print(f"活動追蹤: {stats['active_tracks']}")
    
    blow_stats = stats['blow_stats']
    print(f"成功率: {blow_stats['success_rate']:.1f}%")
```

---

## ⚙️ 調整參數

### 修改初始化參數

```python
# 如果需要不同的參數，可以在初始化時調整
cam_operation.initialize_trigger_system(
    image_width=2448,       # 更改影像尺寸
    image_height=2048,
    lens_type="8mm"         # 更改鏡頭類型
)

# 或者直接修改追蹤器參數
if cam_operation.tracker:
    cam_operation.tracker.max_age = 20          # 增加保留時間
    cam_operation.tracker.min_hits = 2          # 降低匹配要求
    cam_operation.tracker.iou_threshold = 0.25  # 降低 IoU 閾值
```

### 使用配置文件

```python
from config_two_band_filter import get_config_for_scenario

# 獲取預設配置
config = get_config_for_scenario("12mm_high_speed")

# 使用配置初始化
cam_operation.initialize_trigger_system(
    image_width=config.image.image_width,
    image_height=config.image.image_height,
    lens_type=config.lens.lens_type
)
```

---

## 🐛 除錯技巧

### 1. 檢查是否成功初始化
```python
if cam_operation.tracker is not None:
    print("✅ 追蹤器已初始化")
else:
    print("❌ 追蹤器未初始化")

if cam_operation.two_band_filter is not None:
    print("✅ Two-Band Filter 已初始化")
else:
    print("❌ Two-Band Filter 未初始化")

print(f"觸發系統狀態: {'已啟用' if cam_operation.enable_trigger_system else '已停用'}")
```

### 2. 監控觸發過程

Work_thread 會自動列印觸發資訊：
```
[TriggerSystem] Triggered 2 objects this frame
  → Track 15: Class=0, Pos=(645.3, 512.7), Conf=0.89
  → Track 18: Class=1, Pos=(892.1, 498.3), Conf=0.82
```

### 3. 檢查錯誤訊息

如果出現錯誤，會顯示詳細的錯誤資訊：
```python
# Work_thread 中已包含錯誤處理
try:
    # 追蹤和觸發邏輯
    ...
except Exception as e:
    print(f"[TriggerSystem] Error: {e}")
    traceback.print_exc()
```

---

## ⚠️ 注意事項

### 1. 初始化時機
**必須在相機開始取圖之後初始化觸發系統**

✅ 正確順序：
```python
cam_operation.Start_grabbing(winHandle)
cam_operation.initialize_trigger_system(1280, 1024, "12mm")
```

❌ 錯誤順序：
```python
cam_operation.initialize_trigger_system(1280, 1024, "12mm")  # 會失敗
cam_operation.Start_grabbing(winHandle)
```

### 2. TCP 伺服器

確保 TCP 伺服器已啟動：
```python
from tcp_server import start_tcp_server

# 在創建相機之前啟動
start_tcp_server(host='localhost', port=8888)
```

### 3. 影像尺寸一致

初始化時的影像尺寸必須與實際相機輸出一致：
```python
# 獲取實際影像尺寸
image_width = cam_operation.st_frame_info.nWidth
image_height = cam_operation.st_frame_info.nHeight

# 使用實際尺寸初始化
cam_operation.initialize_trigger_system(image_width, image_height, "12mm")
```

### 4. 相容性

系統會自動檢測是否成功導入追蹤器：
- 如果導入失敗，會使用原有的 TCP 發送方式
- 不會影響現有功能

---

## 📝 完整範例

```python
# complete_example.py - 完整的使用範例

import sys
import time
from CamOperation_class import CameraOperation, set_ai_model
from tcp_server import start_tcp_server, get_tcp_server
from ultralytics import YOLO

def main():
    # 1. 載入 YOLO 模型
    print("Loading YOLO model...")
    model = YOLO("best.pt")
    set_ai_model(model)
    
    # 2. 啟動 TCP 伺服器
    print("Starting TCP server...")
    start_tcp_server(host='localhost', port=8888)
    
    # 3. 創建相機實例
    print("Creating camera instance...")
    cam_operation = CameraOperation(
        obj_cam=None,
        st_device_list=device_list,  # 假設已經獲取
        n_connect_num=0
    )
    
    # 4. 開啟相機
    print("Opening camera...")
    ret = cam_operation.Open_device()
    if ret != 0:
        print(f"Failed to open camera: {ret}")
        return
    
    # 5. 開始取圖
    print("Starting grabbing...")
    ret = cam_operation.Start_grabbing(None)
    if ret != 0:
        print(f"Failed to start grabbing: {ret}")
        return
    
    # 6. 初始化觸發系統
    print("Initializing trigger system...")
    success = cam_operation.initialize_trigger_system(
        image_width=1280,
        image_height=1024,
        lens_type="12mm"
    )
    
    if success:
        print("✅ Trigger system initialized successfully!")
    else:
        print("❌ Failed to initialize trigger system")
        print("System will continue without trigger system")
    
    # 7. 運行一段時間
    print("\nSystem running... Press Ctrl+C to stop")
    try:
        while True:
            time.sleep(1)
            
            # 可選：每 10 秒查看統計
            if int(time.time()) % 10 == 0:
                if success:
                    cam_operation.print_trigger_statistics()
    
    except KeyboardInterrupt:
        print("\n\nStopping system...")
    
    # 8. 清理
    print("Showing final statistics...")
    cam_operation.print_trigger_statistics()
    
    print("Stopping grabbing...")
    cam_operation.Stop_grabbing()
    
    print("Closing camera...")
    cam_operation.Close_device()
    
    print("Done!")

if __name__ == "__main__":
    main()
```

---

## 🎯 總結

### ✅ 已整合功能
- [x] SimpleTracker 物體追蹤
- [x] Two-Band Filter 觸發判斷
- [x] BlowController 氣吹控制
- [x] 統計資訊收集
- [x] 錯誤處理

### 📖 相關文檔
- `INTEGRATION_COMPLETE.md` - 整合完成報告
- `TRACKER_INTEGRATION_SUMMARY.md` - 追蹤器整合摘要
- `cam_integration_guide.py` - 整合指南
- `README_TWO_BAND_FILTER.md` - 使用手冊

### 🚀 下一步
1. 在測試環境中運行
2. 調整參數以適應您的場景
3. 在實際傳帶上測試
4. 監控成功率並優化

---

**整合完成！** 🎉

現在您可以在主程式中調用 `initialize_trigger_system()` 來啟動觸發系統了！
