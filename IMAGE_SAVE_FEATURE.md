# 圖片儲存功能更新說明

## 問題描述
原本程式碼中硬編碼了圖片儲存路徑 `D:\savefile`，當該路徑不存在時會導致錯誤：
```
AI Detection error: [WinError 3] 系統找不到指定的路徑。: 'D:\\'
```

## 解決方案
新增了 UI 介面控制，讓使用者可以：
1. **選擇儲存路徑**：透過資料夾選擇對話框自訂儲存位置
2. **控制是否儲存**：透過勾選框決定是否要儲存圖片

## 修改內容

### 1. CamOperation_class.py
新增了以下全域變數和函數：

#### 全域變數
```python
image_save_enabled = False  # 是否啟用圖片儲存
image_save_path = ""  # 圖片儲存路徑
```

#### 控制函數
```python
def set_image_save_enabled(enabled):
    """設定是否啟用圖片儲存"""
    
def set_image_save_path(path):
    """設定圖片儲存路徑"""
    
def get_image_save_settings():
    """獲取圖片儲存設定"""
```

#### Work_thread 修改
將原本硬編碼的儲存邏輯改為：
```python
# 儲存圖像（根據設定決定是否儲存）
if image_save_enabled and image_save_path:
    try:
        today = datetime.datetime.now().strftime("%Y%m%d")
        save_dir = os.path.join(image_save_path, today)
        os.makedirs(save_dir, exist_ok=True)
        
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S_%f")[:-3]
        filename = os.path.join(save_dir, f"image_{timestamp}.jpg")
        cv2.imwrite(filename, cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR))
    except Exception as e:
        print(f"[圖片儲存] 儲存失敗: {e}")
```

### 2. BasicDemo.py
在 TCP 控制頁面的右側控制面板中新增「圖片儲存設定」區塊。

#### UI 元件
- **啟用開關**：`chkImageSaveEnabled` - 勾選框控制是否啟用儲存
- **選擇路徑按鈕**：`bnSelectSavePath` - 開啟資料夾選擇對話框
- **路徑顯示標籤**：`lblSavePath` - 顯示目前選擇的儲存路徑
- **狀態標籤**：`lblImageSaveStatus` - 顯示儲存功能狀態（啟用/停用）

#### 事件處理函數
```python
def select_save_path():
    """選擇圖片儲存路徑"""
    # 開啟資料夾選擇對話框
    # 設定路徑並更新 UI 顯示

def toggle_image_save():
    """切換圖片儲存功能"""
    # 檢查是否已設定路徑
    # 啟用/停用儲存功能
    # 更新狀態顯示
```

## 使用方式

### 步驟 1：選擇儲存路徑
1. 在「TCP 控制與辨識結果」頁面右側找到「圖片儲存設定」區塊
2. 點擊「選擇路徑」按鈕
3. 在對話框中選擇要儲存圖片的資料夾
4. 選擇後路徑會顯示在下方

### 步驟 2：啟用儲存功能
1. 勾選「啟用圖片儲存」核取方塊
2. 系統會顯示確認訊息，說明儲存路徑和分類方式
3. 狀態標籤會變成綠色「儲存: 啟用」

### 步驟 3：停用儲存（可選）
1. 取消勾選「啟用圖片儲存」核取方塊
2. 系統會停止儲存圖片
3. 狀態標籤會變成紅色「儲存: 停用」

## 儲存規則

### 檔案結構
```
選擇的路徑/
├── 20260206/           # 按日期分類（YYYYMMDD）
│   ├── image_20260206_094530_123.jpg
│   ├── image_20260206_094530_456.jpg
│   └── ...
├── 20260207/
│   └── ...
```

### 檔名格式
`image_YYYYMMDD_HHMMSS_mmm.jpg`
- YYYYMMDD：年月日
- HHMMSS：時分秒
- mmm：毫秒

## 注意事項

1. **必須先選擇路徑**：如果未選擇路徑就嘗試啟用儲存，系統會顯示警告訊息
2. **自動建立資料夾**：系統會自動建立日期資料夾，無需手動建立
3. **錯誤處理**：如果儲存失敗（例如磁碟空間不足），會在 Console 顯示錯誤訊息，但不會中斷程式執行
4. **效能考量**：儲存圖片會佔用一些處理時間，如果不需要儲存建議停用此功能

## 優點

✅ **靈活性**：使用者可自由選擇儲存位置  
✅ **可控性**：可隨時啟用/停用儲存功能  
✅ **安全性**：避免硬編碼路徑不存在導致的錯誤  
✅ **組織性**：自動按日期分類，方便管理  
✅ **使用者友善**：透過 UI 操作，無需修改程式碼
