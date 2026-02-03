# Two-Band Filter 快速參考卡

## 📦 已創建的文件

### 核心模組 (3個)
```
✅ track_manager.py       (9.5 KB)  - 追蹤狀態管理
✅ blow_controller.py     (9.2 KB)  - 氣吹控制
✅ two_band_filter.py     (17.5 KB) - 主控系統
```

### 配置與範例 (2個)
```
✅ config_two_band_filter.py    (13.6 KB) - 參數配置
✅ example_two_band_filter.py   (8.9 KB)  - 使用範例
```

### 文檔 (3個)
```
✅ claude.md                    (16.0 KB) - 設計文檔
✅ README_TWO_BAND_FILTER.md    (8.1 KB)  - 使用指南
✅ IMPLEMENTATION_SUMMARY.md    (10.8 KB) - 實施摘要
```

**總計**: 8 個新文件，83.6 KB 代碼和文檔

---

## ⚡ 5 分鐘快速上手

### 1️⃣ 最簡單的使用方式

```python
from two_band_filter import TwoBandFilter
from tcp_server import get_tcp_server, start_tcp_server

# 啟動 TCP
start_tcp_server()

# 初始化
filter_system = TwoBandFilter(
    image_width=1280,
    image_height=1024,
    lens_type="12mm",
    tcp_server=get_tcp_server()
)

# 處理每一帧（在相機迴圈中）
result = filter_system.process_frame(detections, tracker_results)
```

### 2️⃣ 查看統計

```python
filter_system.print_statistics()
```

### 3️⃣ 測試範例

```bash
python example_two_band_filter.py
```

---

## 🎯 核心觸發邏輯

```python
觸發條件（必須全部滿足）:
1. cy 在 Trigger Zone (37.5% ~ 62.5%)
2. triggered == False
3. confidence >= 0.75
4. 中心點飄移 < 2× 容差
5. 信度穩定
```

---

## 🔧 重要參數

| 參數 | 12mm | 8mm |
|------|------|-----|
| 中心點容差 | ±5px | ±8px |
| 飄移閾值 | ±10px | ±16px |

| 參數 | 值 |
|------|-----|
| Trigger Zone | 37.5% ~ 62.5% |
| 信度閾值 | 0.75 |
| 追蹤超時 | 15 帧 |
| ACK 超時 | 200ms |

---

## 📊 視野分區

```
Y=0% ┌──────────────────┐
     │   ENTRY ZONE     │  開始追蹤
Y=38%├──────────────────┤
     │  TRIGGER ZONE ★  │  唯一觸發區
Y=62%├──────────────────┤
     │   EXIT ZONE      │  清除追蹤
Y=100%└──────────────────┘
```

---

## ⚠️ 必須實現

- [ ] **物體追蹤器** (ByteTrack/DeepSORT)
- [ ] **整合到 CamOperation_class.py**
- [ ] **確保 TCP 伺服器運行**

---

## 📖 詳細文檔

1. **設計文檔**: `claude.md`
2. **使用指南**: `README_TWO_BAND_FILTER.md`
3. **實施摘要**: `IMPLEMENTATION_SUMMARY.md`

---

## 🚀 下一步

1. 整合物體追蹤器 (ByteTrack 推薦)
2. 修改 `CamOperation_class.py` 的 `Work_thread`
3. 在實際傳帶上測試
4. 根據成功率調整參數

---

**版本**: v1.0 | **日期**: 2026-02-03 | **狀態**: ✅ 完成
