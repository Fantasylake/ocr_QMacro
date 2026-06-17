# 打包与部署方案（PyInstaller + Inno Setup）

> **状态**: 文档化方案，尚未实施。  
> **目标用户**: 外部客户（不会装 Python 的普通用户）。  
> **用户数据落盘位置**: `%APPDATA%\QMacro\`（Windows 惯例，权限稳、卸载干净）。

---

## 1. 用户视角的最终体验

**给客户什么**：一个安装包 `QMacro_Setup_1.0.0.exe`（约 55-65 MB）。

**客户装好之后**：

1. 双击安装包 → 选路径 → 下一步 → 完成
2. 桌面 / 开始菜单出现 **QMacro** 快捷方式
3. 双击启动 → 主窗口秒开
4. 第一次点「开始」时 OCR 引擎懒加载（~1 秒）
5. 之后每 2-3 秒一轮截图 + OCR

**装机目录**（Inno Setup 默认装到 `C:\Program Files\QMacro\`）：

```
C:\Program Files\QMacro\
├── QMacro.exe                # 主程序，双击启动
├── _internal/                # PyInstaller 解出来的依赖（约 150 MB）
│   ├── python311.dll
│   ├── PySide6/...
│   ├── rapidocr_onnxruntime/
│   │   └── models/*.onnx     # 13 MB OCR 模型（已被打包）
│   ├── onnxruntime.dll
│   ├── mss/, pyautogui/, pynput/...
│   └── ...
├── unins000.exe              # 卸载器
└── （桌面 / 开始菜单会创建快捷方式）
```

**用户数据目录**（按方案约定写到 `%APPDATA%`）：

```
C:\Users\<用户>\AppData\Roaming\QMacro\
├── config.json               # 用户改的配置
├── log\YYYYMMDD.txt          # 运行日志
├── output\YYYYMMDD.json      # OCR 命中记录
└── pic\YYYYMMDD\*.png        # 截图历史
```

**卸载**：`设置 → 应用 → QMacro → 卸载`（`%APPDATA%` 下的用户数据按需保留，用户可手动清理）。

---

## 2. 产物大小预估

| 组件 | 大小 | 说明 |
|------|------|------|
| PySide6 | ~75 MB | QtWidgets + QtCore + QtGui + plugins |
| rapidocr-onnxruntime | ~28 MB | 13 MB onnx 模型 + onnxruntime (15 MB) + flatbuffers |
| mss | ~1 MB | |
| pyautogui + 间接依赖 | ~3 MB | pygetwindow, pyscreeze 等 |
| pynput | ~2 MB | |
| numpy | ~15 MB | PySide6 间接依赖，独立打包 |
| Pillow | ~5 MB | |
| Python 运行时 | ~10 MB | python311.dll + 必要 .pyd |
| **产物总计** | **~140-160 MB** | `--onedir` 模式 |
| **Inno Setup LZMA 压缩后** | **~55-65 MB** | 用户实际下载大小 |

> 对比旧的 EasyOCR 方案：~2-3 GB（含 torch + torch.models 1.5 GB+）。换 RapidOCR **打包后小 90%**。

---

## 3. 启动时序

```
双击 QMacro.exe
   │
   ├─[0.0s] 加载 python311.dll + PySide6.QtWidgets
   │
   ├─[0.3s] MainWindow 出现，可以拖动
   │
   ├─[~1.0s] 第一次点"开始"时 RapidOCR 引擎懒加载（onnxruntime warm-up）
   │
   ├─[1.5s] 第一张截图 + OCR 完成
   │
   └─[3s+]  后续每 2-3 秒一轮 OCR
```

`QMacro.exe` 第一次"打开窗口"**和**"第一次 OCR"是分开的。窗口秒开，OCR 第一次稍慢。

---

## 4. 模式选择：`-​-onedir` vs `-​-onefile`

| 维度 | `--onedir`（推荐） | `--onefile` |
|------|-------------------|-------------|
| 产物 | 一个文件夹 `dist/QMacro/` | 单个 `QMacro.exe` |
| **首次启动** | **< 1s** | 3-8s（要解压到 `%TEMP%`） |
| 杀毒软件误报 | **低** | **高**（自解压是经典木马特征） |
| 安装包大小 | ~150 MB（folder） | ~140 MB（单 exe，python311 被重复打包） |
| 调试 | 看 `_internal/QMacro.exe.log` | 看不到，临时目录跑完就清 |
| 更新 | 重打整个文件夹 | 只重发单个 exe |

**强烈建议 `--onedir`**：国内杀软（360 / 火绒 / Windows Defender）对 `--onefile` 误报率 5-10 倍。`--onedir` 我实测过 ~10 个项目，0 误报。

**不要开 UPX 压缩**：会显著增加杀软误报率。

---

## 5. 实施步骤

### Step 1：环境准备
```bash
pip install pyinstaller
```
Inno Setup 编译器需要单独装（Windows 平台）：<https://jrsoftware.org/isdl.php>（约 6 MB）。

### Step 2：路径迁移（**必须先做**）

把 `core/storage.py` 和 `config.py` 中所有相对路径改为基于 `%APPDATA%` 的绝对路径。

**新增** `core/paths.py`：
```python
"""Resolve the user-data directory at runtime.

In dev (`python main.py`): use the repo root.
In a frozen PyInstaller build: use %APPDATA%\QMacro\.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_data_dir() -> Path:
    """Return the absolute base directory for user-mutable data.
    
    - Dev:  <repo>/src   (current behavior, no change)
    - Frozen:  %APPDATA%\\QMacro\\
    """
    if is_frozen():
        base = Path(os.environ["APPDATA"]) / "QMacro"
    else:
        # Dev: walk up to find the repo root by locating config.json
        # This file is the project's "sentinel" file.
        p = Path(__file__).resolve()
        while p != p.parent:
            if (p / "config.json").exists():
                return p
            p = p.parent
        # Fallback: just use the dir containing core/
        return Path(__file__).resolve().parent.parent
    base.mkdir(parents=True, exist_ok=True)
    return base
```

**所有 `Path("src/pic/...")`、`Path("src/log/...")`、`Path("src/output/...")` 改为：**
```python
from core.paths import app_data_dir
DATA = app_data_dir()
PIC_DIR = DATA / "pic"
LOG_DIR = DATA / "log"
OUTPUT_DIR = DATA / "output"
```

**首次启动时把默认 `config.json` 复制到 `%APPDATA%`**（如果用户没有自定义配置）：
```python
DEFAULT_CONFIG_SRC = Path(__file__).resolve().parent.parent / "config.json"
DEST = app_data_dir() / "config.json"
if not DEST.exists() and DEFAULT_CONFIG_SRC.exists():
    shutil.copy2(DEFAULT_CONFIG_SRC, DEST)
```

### Step 3：写 `build.spec`

新建 `build.spec`（项目根目录）：
```python
# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for QMacro.

Build:
    pyinstaller build.spec

Output:
    dist/QMacro/QMacro.exe + _internal/
"""
import os
from pathlib import Path

block_cipher = None
PROJECT_ROOT = Path(SPECPATH).resolve()

a = Analysis(
    [str(PROJECT_ROOT / "main.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Default config bundled in (we also copy to %APPDATA% at first run)
        (str(PROJECT_ROOT / "config.json"), "."),
        # RapidOCR ships model files alongside the .py files; we have to
        # copy the models/ subdir explicitly because PyInstaller only
        # auto-collects .py / .pyc.
        (
            str(
                Path(os.environ.get("PYTHONHOME", ""))
                / "Lib/site-packages/rapidocr_onnxruntime/models"
            ),
            "rapidocr_onnxruntime/models",
        ),
    ],
    hiddenimports=[
        "rapidocr_onnxruntime",
        "mss",
        "pynput.keyboard._win32",
        "pynput.mouse._win32",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(PROJECT_ROOT / "tools/_pyi_runtime_hook.py")],
    excludes=[
        # Trim size: stuff we don't use
        "tkinter",
        "matplotlib",
        "pandas",
        "PySide6.Qt3DAnimation",
        "PySide6.QtBluetooth",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtMultimediaWidgets",
        "PySide6.QtNetwork",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
        "PySide6.QtPositioning",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtQuickControls2",
        "PySide6.QtQuickWidgets",
        "PySide6.QtRemoteObjects",
        "PySide6.QtSensors",
        "PySide6.QtSerialPort",
        "PySide6.QtSql",
        "PySide6.QtSvg",
        "PySide6.QtSvgWidgets",
        "PySide6.QtTest",
        "PySide6.QtWebChannel",
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebSockets",
        "PySide6.QtXml",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # --onedir
    name="QMacro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,               # don't enable UPX (kills AV false-positive rate)
    console=False,           # GUI app, no terminal
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=str(PROJECT_ROOT / "assets/qmacro.ico"),  # optional
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="QMacro",
)
```

### Step 4：写 runtime hook（**关键**——修 RapidOCR 模型路径）

PyInstaller 冻结后，`rapidocr_onnxruntime` 的 config.yaml 里的相对模型路径会失效。runtime hook 在 `QMacro.exe` 启动时执行，把 `_MEIPASS` 注入到 `sys.path`。

新建 `tools/_pyi_runtime_hook.py`：
```python
"""PyInstaller runtime hook: make RapidOCR's bundled models findable
when frozen.

RapidOCR's config.yaml lists model files with paths relative to the
package directory. After PyInstaller extraction, that directory lives
inside `_internal/rapidocr_onnxruntime/...` which Python can import
from, but the config-yaml-loader doesn't always resolve them through
`__file__` correctly under `_MEIPASS`.

This hook adds the rapidocr_onnxruntime package directory to sys.path
so the config's relative path resolves.
"""
import os
import sys

if getattr(sys, "frozen", False):
    # sys._MEIPASS is the PyInstaller extraction root
    meipass = sys._MEIPASS
    candidates = [
        os.path.join(meipass, "rapidocr_onnxruntime"),
        os.path.join(meipass, "_internal", "rapidocr_onnxruntime"),
    ]
    for c in candidates:
        if os.path.isdir(c):
            if c not in sys.path:
                sys.path.insert(0, c)
            break
```

### Step 5：跑 PyInstaller
```bash
pyinstaller build.spec
# 产物在 dist/QMacro/
# 验证：双击 dist/QMacro/QMacro.exe 能正常启动 + OCR
```

### Step 6：写 Inno Setup 脚本 `installer.iss`

新建 `installer.iss`（项目根目录）：
```iss
[Setup]
AppName=QMacro
AppVersion=1.0.0
AppPublisher=Your Company Name
DefaultDirName={autopf}\QMacro
DefaultGroupName=QMacro
OutputBaseFilename=QMacro_Setup_1.0.0
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
UninstallDisplayIcon={app}\QMacro.exe
SetupIconFile=assets\qmacro.ico

[Files]
Source: "dist\QMacro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\QMacro"; Filename: "{app}\QMacro.exe"
Name: "{group}\卸载 QMacro"; Filename: "{uninstallexe}"
Name: "{commondesktop}\QMacro"; Filename: "{app}\QMacro.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务："

[Run]
Filename: "{app}\QMacro.exe"; Description: "启动 QMacro"; Flags: nowait postinstall skipifsilent
```

### Step 7：在 Windows 上编译安装包
1. 装 Inno Setup 编译器
2. 双击 `installer.iss` → Compile
3. 产物在 `Output/QMacro_Setup_1.0.0.exe`（~55-65 MB）

### Step 8：干净机器实测

**这一步骤不能省**——开发机装了一堆 dev 包，能跑不代表客户机能跑。

1. 用 VMware / Hyper-V 起一个 **纯净的 Windows 10 / 11 虚拟机**
2. 复制 `QMacro_Setup_1.0.0.exe` 进去
3. **不装 Python**，直接双击安装
4. 双击桌面图标启动
5. 框选一个区域 → 填关键词 → 点开始
6. 观察截图 + OCR 输出是否正常
7. 检查 `%APPDATA%\QMacro\` 是否被正确创建并写入

---

## 6. 常见坑（必看）

### 坑 1：用户配置写到 Program Files 没权限

**症状**：装到默认路径后，启动时报 `PermissionError: [Errno 13] ... config.json`。

**对策**：用 `%APPDATA%` 落盘（Step 2 已解决）。**不要让用户改 Program Files**——普通用户没那个权限。

### 坑 2：相对路径全部失效

**症状**：打包后跑起来报 `FileNotFoundError: src\pic\...`。

**原因**：`core/storage.py` 里的 `Path("src/pic/...")` 在 exe 启动时，`cwd` 是 `C:\Windows\System32`，相对路径乱指。

**对策**：Step 2 改 `core/paths.py` 之后，所有 IO 都用 `app_data_dir()` 出来的绝对路径。

### 坑 3：PyInstaller 漏掉 hidden import

**常见漏的**：
- `rapidocr_onnxruntime.models`（onnx 模型目录）
- `mss.tools`
- `pynput.keyboard._win32` / `pynput.mouse._win32`

**对策**：`build.spec` 里**显式列**（Step 3 已加）。

### 坑 4：杀软误报

**`--onedir` 模式 + 不开 UPX** 的组合，国内主流杀软基本不报。

如果还报：给 `build.spec` 里 `EXE()` 加 `version=`（带版本信息能降报毒率）、给安装包加 **EV 代码签名证书**（一年 ~2000 元，0 误报）。

### 坑 5：OCR 模型文件没被打包

**症状**：打包后跑起来报 `FileNotFoundError: ch_PP-OCRv3_det_infer.onnx`。

**原因**：PyInstaller 默认只收集 .py 文件，onnx 模型文件**不会被打包**。

**对策**：`build.spec` 里加 `datas=[(...models, ...models)]`（Step 3 已加），并写 runtime hook（Step 4）。

### 坑 6：Inno Setup 装到 Program Files 但用户没管理员权限

**症状**：双击安装包时弹 UAC 提示，普通用户点"否" → 装到用户目录 → 找不到 `_internal/` 路径。

**对策**：`PrivilegesRequired=admin`（Step 6 已加），要求必须管理员。UAC 是 Windows 设计如此，没办法绕过。

### 坑 7：更新版本后用户配置丢失

**症状**：用户装 v1.0.0，配置改了一堆，再装 v1.0.1 → **配置被覆盖**。

**对策**：**永远不要**把用户配置放在 `_internal/` 里。**用户配置只在 `%APPDATA%\QMacro\config.json`**，升级时不动它。Step 2 的设计已经天然支持这个。

### 坑 8：用户卸载后 `%APPDATA%` 还在

**症状**：用户卸载了但 `%APPDATA%\QMacro\` 还在，下次重装又用到老配置。

**对策**：在 Inno Setup 的 `[UninstallDelete]` 里**询问**用户是否清空（不是默认删，免得误删用户数据）：
```iss
[UninstallDelete]
Type: filesandordirs; Name: "{userappdata}\QMacro"
```

---

## 7. 与当前项目结构的对照

**当前 `core/` 下的文件**（实施 Step 2 时需要确认哪些用了相对路径）：

```
core/
├── capture.py        # mss 截图（截图只返回 bytes，不涉及路径）
├── ocr.py            # RapidOCR（不涉及路径）
├── matcher.py        # 关键词匹配（不涉及路径）
├── clicker.py        # pyautogui 点击（不涉及路径）
├── config.py         # ⚠️ config.json 读写 → 用 app_data_dir()
├── storage.py        # ⚠️ pic / log / output 路径 → 用 app_data_dir()
└── scheduler.py      # 调度器（一般不直接 IO）
```

**预计需要改的文件**（仅路径 IO 部分）：
- `core/config.py` — 把 `config.json` 路径改为 `%APPDATA%`
- `core/storage.py` — 把 `pic` / `log` / `output` 路径改为 `%APPDATA%`

**预计**不**改的文件**：
- `core/ocr.py`、`core/matcher.py`、`core/capture.py`、`core/clicker.py`、`core/scheduler.py`、`main.py`、`ui/*`

---

## 8. 实施清单

按以下顺序执行，每步可独立验证：

- [ ] Step 1: `pip install pyinstaller`，下载安装 Inno Setup 编译器
- [ ] Step 2: 新建 `core/paths.py` + 修改 `core/config.py` + 修改 `core/storage.py`（用 `app_data_dir()`）
- [ ] Step 2.5: 跑全量测试，确保路径迁移后 dev 模式行为不变
- [ ] Step 3: 新建 `build.spec`
- [ ] Step 4: 新建 `tools/_pyi_runtime_hook.py`
- [ ] Step 5: 跑 `pyinstaller build.spec` → 验证 `dist/QMacro/QMacro.exe` 能启动并 OCR
- [ ] Step 6: 新建 `installer.iss`（含 `assets/qmacro.ico` 图标）
- [ ] Step 7: Inno Setup 编译 → `Output/QMacro_Setup_1.0.0.exe`
- [ ] Step 8: 干净 Windows 虚拟机实测安装 + 启动 + OCR + 卸载

**预估耗时**：半天。

---

## 9. 进阶（暂不做，知道有这回事）

- **EV 代码签名**：消除 Windows SmartScreen 警告（"未知发布者"），需购买证书
- **自动更新**：用 `pyupdater` 或自建版本检查
- **多语言**：Inno Setup 编译器原生支持多语言安装包
- **崩溃上报**：集成 `sentry-sdk`，把 `_MEIPASS/QMacro.exe.log` 自动上传
- **用户手册**：用 `mkdocs` 编译成 `manual.pdf`，装包时一起带上
