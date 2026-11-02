# ImageTool · 简单图片工具

基于 **OpenCV + Tkinter** 的图片识别与编辑工具，提供命令行和图形界面两种用法。所有编辑结果都保存为**新文件**，不会覆盖原图。

## 功能

| 功能 | 说明 |
|------|------|
| 识图 | 显示格式（按文件头魔数识别）、宽高、颜色模式、文件大小 |
| 缩放 | 指定宽高，INTER_AREA 插值 |
| 裁剪 | 命令行按坐标裁剪；GUI 支持拖动四角交互式裁剪 |
| 旋转 | 任意角度（逆时针），自动扩展画布避免裁切；GUI 支持鼠标拖动旋转 |
| 翻转 | 水平 / 垂直 |
| 灰度化 | 转单通道灰度图 |
| 颜色调节 | 亮度（-100~100）、对比度、饱和度（百分比，100 为不变），GUI 滑条实时预览 |
| 格式转换 | jpg / png / bmp / webp / gif / tiff 互转，透明图转 JPG 自动合成白底 |

## 文件结构

```
image tool/
├── image_tool.py     # 核心库 + 命令行入口（图像处理逻辑都在这里）
├── image_gui.py      # 图形界面版（依赖 image_tool.py）
├── ImageTool.spec    # PyInstaller 打包配置
└── dist/
    └── ImageTool.exe # 打包好的 Windows 可执行文件（双击即用，无需装 Python）
```

## 环境要求

- Python 3.x
- 依赖安装：

```bash
python -m pip install opencv-python numpy
```

（GUI 使用标准库 tkinter，无需额外安装）

## 使用方法

### 图形界面

```bash
python image_gui.py
```

或直接双击 `dist/ImageTool.exe`。

操作流程：**打开图片 → 编辑（效果先叠加到预览，可 Ctrl+Z 撤回）→ 应用并保存新图**。

- 裁剪：点【裁剪模式】，拖动四个白角调整区域，点【确认裁剪】
- 旋转：点【旋转模式】，按住左键绕中心拖动，松开即生效
- 颜色：拖动滑条实时预览，点数值可直接输入；松手记为一步，可撤回

### 命令行

```bash
python image_tool.py info 图片.png                       # 识图：显示图片信息
python image_tool.py resize 图片.png 800 600              # 缩放到 800x600
python image_tool.py crop 图片.png 100 50 400 300         # 裁剪 (left top right bottom)
python image_tool.py rotate 图片.png 90                   # 逆时针旋转 90 度
python image_tool.py flip 图片.png h                      # 水平翻转（v 为垂直）
python image_tool.py gray 图片.png                        # 灰度化
python image_tool.py color 图片.png --brightness 20 --contrast 120 --saturation 80
python image_tool.py convert 图片.png jpg                 # 转换为 jpg
```

编辑命令都支持 `--out 目录` 指定输出位置，默认保存在原图同目录，文件名形如 `原名_动作.扩展名`。

## 实现要点

- **中文路径兼容**：读图用 `cv2.imdecode + np.fromfile`，保存用 `cv2.imencode + tofile`，绕开 OpenCV 不支持中文路径的问题
- **透明通道保留**：以 `IMREAD_UNCHANGED` 读入；旋转补透明、转 JPG 合成白底
- **格式识别**：不依赖扩展名，通过文件头魔数判断真实格式
- **GUI 无需 PIL**：OpenCV 图像转 PPM 数据直接构造 `tk.PhotoImage`

## 打包 exe

```bash
python -m pip install pyinstaller
pyinstaller ImageTool.spec
```

产物在 `dist/ImageTool.exe`。
