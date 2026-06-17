# 屏幕区域监控 + OCR + 自动点击 工具 设计文档

**日期**: 2026-06-17
**状态**: 已批准，待实现

## 1. 目标

构建一个 PySide6 GUI 桌面工具，让用户能够：

1. 在屏幕上添加 **多个监控区域**（带名称的矩形区域，定时截图 + OCR 识别）
2. 在屏幕上添加 **多个点击点**（带顺序的屏幕坐标点）
3. 配置 **包含关键词**（命中后触发点击动作）
4. 设置 **定时周期**（每隔 N 秒执行一次扫描循环）
5. 把每次截图保存到 `src/pic/`，把识别结果追加到 `src/csv/YYYYMMDD.csv`
6. 触发命中后，按"点击顺序"依次点击所有点击点

## 2. 适用场景

监控某个程序界面变化，识别到指定关键词时自动执行点击操作。

## 3. 技术栈

| 模块 | 选型 | 说明 |
|------|------|------|
| GUI 框架 | PySide6 | 现代化 Qt 界面，原生信号/槽 |
| 屏幕截图 | mss | 高性能截图库，比 pyautogui.screenshot 快 |
| OCR 引擎 | easyocr | 仅加载 `['ch_sim', 'en']` 模型，平衡精度与体积 |
| 鼠标点击 | pyautogui | 简单可靠的鼠标点击 |
| 全局监听 | pynput | 用于「屏幕坐标拾取」功能 |
| 配置存储 | JSON 文件 | 人类可读、易调试 |
| Python 版本 | 3.10+ | 使用 match-case 等现代语法 |

## 4. 架构

### 4.1 分层

```
┌─────────────────────────────────────────┐
│  UI 层 (ui/)        PySide6 界面        │
│  - MainWindow                           │
│  - RegionPanel / ClickPointPanel        │
│  - 坐标拾取 / 启停控制 / 日志            │
└──────────────┬──────────────────────────┘
               │ Qt 信号/槽 (跨线程安全)
┌──────────────▼──────────────────────────┐
│  调度层 (core/scheduler.py)             │
│  - QTimer 定时器                         │
│  - Worker QThread (截图+OCR)            │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│  业务层 (core/)                          │
│  - config.py     JSON 配置加载/保存      │
│  - capture.py    mss 截图                │
│  - ocr.py        EasyOCR 单例 reader     │
│  - matcher.py    关键词匹配              │
│  - clicker.py    pyautogui 点击          │
│  - storage.py    存图 / 写 CSV           │
└─────────────────────────────────────────┘
```

### 4.2 职责边界

每个模块只做一件事，可独立测试：

- **config.py**: 读写 `config.json`，定义 `Region` / `ClickPoint` 数据类
- **capture.py**: 给定 bbox 字典 `{top, left, width, height}`，返回 PNG bytes
- **ocr.py**: 给定 PNG bytes，返回识别文本字符串（Reader 单例懒加载）
- **matcher.py**: 给定文本和关键词列表，判断是否命中，返回 (命中标志, 命中关键词)
- **clicker.py**: 给定坐标列表，按顺序点击，捕获异常
- **storage.py**: 写图片到 `src/pic/YYYYMMDD/...`，追加一行到 `src/csv/YYYYMMDD.csv`
- **scheduler.py**: QTimer 驱动循环，把 CPU 密集型操作丢给 Worker 线程

## 5. 目录结构

```
jixiechaoren/
├── main.py                    # 入口，启动 QApplication
├── requirements.txt           # 依赖清单
├── README.md                  # 使用说明
├── config.json                # 用户配置（首次运行自动生成）
├── src/
│   ├── pic/                   # 截图输出（按天分子目录）
│   └── csv/                   # 识别结果 CSV
├── docs/
│   └── superpowers/
│       └── specs/
│           └── 2026-06-17-jixiechaoren-design.md
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── capture.py
│   ├── ocr.py
│   ├── matcher.py
│   ├── clicker.py
│   ├── storage.py
│   └── scheduler.py
└── ui/
    ├── __init__.py
    ├── main_window.py
    ├── region_panel.py
    ├── point_panel.py
    └── picker.py              # 屏幕坐标拾取对话框
```

## 6. 数据模型

### 6.1 config.json 结构

```json
{
  "interval_sec": 5,
  "keywords": ["成功", "完成", "已就绪"],
  "regions": [
    {
      "name": "状态栏",
      "bbox": {"top": 100, "left": 200, "width": 400, "height": 50}
    }
  ],
  "click_points": [
    {"name": "确认按钮", "x": 640, "y": 480, "order": 1}
  ]
}
```

### 6.2 CSV 输出格式

文件路径：`src/csv/YYYYMMDD.csv`
编码：UTF-8 **with BOM**（Excel 直接打开不乱码）

| timestamp | region | text | matched_keyword |
|-----------|--------|------|-----------------|
| 2026-06-17 13:25:10 | 状态栏 | 操作成功 | 成功 |
| 2026-06-17 13:25:15 | 状态栏 | 任务完成 | 完成 |

每次扫描命中即追加一行，文件不存在则自动创建并写入表头。

### 6.3 截图文件命名

`src/pic/YYYYMMDD/HHMMSS_<region_name>_<index>.png`
例：`src/pic/20260617/132510_状态栏_1.png`

文件名中的非法字符（`/\:*?"<>|`）替换为 `_`。

## 7. 数据流（一次扫描循环）

1. **QTimer 触发**（默认 5 秒，可配置 `interval_sec`）
2. Worker 线程开始一轮扫描：
   - 遍历所有监控区域：
     a. mss 截图 → PNG bytes
     b. 存盘到 `src/pic/YYYYMMDD/HHMMSS_<region>_<i>.png`
     c. EasyOCR 识别 → 文本
     d. matcher 判定是否包含任一关键词
     e. 如果命中：追加一行到 CSV，记录 `(timestamp, region, text, keyword)`
3. **本轮所有命中区域处理完成后**，按 `order` 升序依次点击所有点击点
4. 通过 Qt 信号把"日志条目"发回主线程，UI 追加到日志面板
5. 若用户点击"停止"按钮：QTimer.stop() + Worker 置 `stop_event`，下个循环开头退出

## 8. 关键设计决策

### 8.1 OCR 必须异步

EasyOCR 推理耗时 0.5~3 秒（取决于图片大小），必须放 `QThread`，否则 GUI 会冻结。Worker 通过 `pyqtSignal` 把结果发回主线程。

### 8.2 Reader 单例

`easyocr.Reader` 首次构造耗时 10~30 秒（加载模型），所以用模块级单例懒加载：

```python
_reader: easyocr.Reader | None = None

def get_reader() -> easyocr.Reader:
    global _reader
    if _reader is None:
        _reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
    return _reader
```

### 8.3 坐标拾取实现

「拾取坐标」按钮：
1. 主窗口 `hide()`
2. 弹出半透明全屏遮罩（显示「请按 ESC 取消，单击确认」）
3. `pynput.mouse.Listener` 监听单击事件
4. 单击 → 拿到 `(x, y)` → 关闭窗口 → 主窗口 `show()` → 填入坐标
5. 按 ESC → 取消拾取

遮罩用 `QWidget` + `setWindowOpacity(0.3)` + `Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint`。

### 8.4 配置文件防抖

UI 控件 `textChanged` → 500ms 防抖 → 写 JSON。避免每次按键都 IO。

### 8.5 停止按钮语义

点击"停止"：
- QTimer.stop()：不再触发新一轮
- Worker 线程检查 `stop_event` 标志：当前循环跑完后退出
- 不强制 kill 线程（避免半截状态）

## 9. GUI 布局

```
┌─────────────────────────────────────────────────────────────┐
│  [开始] [停止]  周期(秒): [5]  关键词: [成功|完成|已就绪]    │
├──────────────────────────┬──────────────────────────────────┤
│  监控区域                 │  点击点 (按顺序)                 │
│  ┌────────────────────┐  │  ┌────────────────────────┐    │
│  │ # | 名称 | 区域     │  │  │ # | 名称 | 坐标        │    │
│  │ 1 | 状态栏| 200,...│  │  │ 1 | 确认 | 640,480    │    │
│  └────────────────────┘  │  └────────────────────────┘    │
│  [+ 添加] [拾取区域]      │  [+ 添加] [拾取坐标]            │
├──────────────────────────┴──────────────────────────────────┤
│  日志                                                      │
│  [13:25:10] 状态栏 → 命中「成功」: 操作成功                 │
│  [13:25:10] 已点击 1 个点                                   │
└─────────────────────────────────────────────────────────────┘
```

## 10. 错误处理

| 场景 | 处理 |
|------|------|
| 截图失败（屏幕锁屏/权限） | 记录日志，跳过该区域，继续下一个 |
| OCR 异常 | 识别文本记为 `[ERROR: <msg>]`，不视为命中 |
| 点击失败 (pyautogui FailSafe) | 记录日志，继续下一个点 |
| 配置文件 JSON 损坏 | 自动备份为 `config.json.bak`，重新生成默认配置 |
| 配置文件不存在 | 首次运行自动生成空配置 |
| `src/pic/` 或 `src/csv/` 不存在 | 自动创建 |

## 11. 依赖

```
PySide6>=6.6.0
easyocr>=1.7.0
mss>=9.0.0
pyautogui>=0.9.54
pynput>=1.7.6
numpy>=1.24.0
```

## 12. 范围与非目标

**包含**：
- 多个区域 / 多个点击点
- 包含关键词触发
- 中文 + 英文 OCR
- 截图归档 + CSV 归档
- 坐标拾取 UI

**不包含**（YAGNI）：
- 不包含「不包含关键词」反向触发
- 不包含正则匹配
- 不包含托盘 / 全局热键
- 不包含多窗口/多屏幕适配（仅主屏幕）
- 不包含 GPU 加速选项（默认 CPU）
- 不包含打包为 exe（后续可选）

## 13. 验收标准

1. 双击 `main.py` 启动 GUI，看到默认布局
2. 点击「拾取坐标」能在屏幕上拾取一个点
3. 添加一个区域 + 一个点击点 + 关键词"成功"
4. 点击「开始」，5 秒后日志显示截图保存路径和 OCR 结果
5. 当 OCR 文本含"成功"时，日志显示「命中」，CSV 文件出现新行
6. 点击点按顺序被点击
7. 点击「停止」后定时器不再触发
8. 重启程序后配置仍存在
