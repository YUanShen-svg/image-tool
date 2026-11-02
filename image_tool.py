# -*- coding: utf-8 -*-
"""简单图片工具核心库（OpenCV 版）：识图 + 编辑，结果保存为新文件，不覆盖原图"""
import os
import sys

try:
    import cv2
    import numpy as np
except ImportError:
    print("缺少 OpenCV，请先安装：pip install opencv-python")
    sys.exit(1)

SUPPORTED_FORMATS = ("jpg", "png", "bmp", "webp", "gif", "tiff")

# 文件头魔数 -> 格式名（OpenCV 不提供格式信息，用魔数识别）
_MAGIC = [
    (b"\xff\xd8\xff", "JPEG"),
    (b"\x89PNG", "PNG"),
    (b"BM", "BMP"),
    (b"GIF8", "GIF"),
    (b"RIFF", "WEBP"),
    (b"II*\x00", "TIFF"),
    (b"MM\x00*", "TIFF"),
]


# ---------- 工具函数 ----------

def detect_format(path):
    """通过文件头魔数识别图片格式"""
    with open(path, "rb") as f:
        head = f.read(12)
    for magic, name in _MAGIC:
        if head.startswith(magic):
            return name
    return "未知"


def mode_name(img):
    """通道数 -> 颜色模式名称"""
    ch = 1 if img.ndim == 2 else img.shape[2]
    return {1: "GRAY", 3: "RGB", 4: "RGBA"}.get(ch, f"{ch}通道")


def load_image(path):
    """读取图片（保留透明通道）；文件不存在或不是有效图片时给出提示"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"文件不存在：{path}")
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"文件不是有效图片：{path}")
    return img


def build_output_path(src_path, action, out_dir=None):
    """生成新文件路径：原文件名_动作.扩展名，保存在原图同目录（或指定目录）"""
    src_dir = os.path.dirname(os.path.abspath(src_path))
    save_dir = out_dir if out_dir else src_dir
    os.makedirs(save_dir, exist_ok=True)
    name, ext = os.path.splitext(os.path.basename(src_path))
    return os.path.join(save_dir, f"{name}_{action}{ext}")


def file_size_str(path):
    """把字节数格式化成易读的字符串"""
    size = os.path.getsize(path)
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024


def to_bgr(img):
    """带透明通道的图片合成白底 BGR（保存 JPG 前必须转换）"""
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:
        bgr = img[:, :, :3].astype(np.float32)
        alpha = (img[:, :, 3:4].astype(np.float32)) / 255.0
        white = np.full_like(bgr, 255.0)
        return (bgr * alpha + white * (1 - alpha)).astype(np.uint8)
    return img


# ---------- 编辑核心函数（作用于图像数组，返回新图像） ----------

def resize_img(img, width, height):
    """缩放：宽高必须大于 0"""
    if width <= 0 or height <= 0:
        raise ValueError(f"参数不合法：宽高必须大于 0（当前 {width}x{height}）")
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def crop_img(img, left, top, right, bottom):
    """裁剪：区域必须在图片范围内且有效"""
    h, w = img.shape[:2]
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("参数不合法：裁剪区域应满足 0 <= left < right, 0 <= top < bottom")
    if right > w or bottom > h:
        raise ValueError(f"参数不合法：裁剪区域超出图片范围（{w}x{h}）")
    return img[top:bottom, left:right].copy()


def rotate_img(img, angle):
    """旋转：angle 为角度（正数逆时针），自动扩展画布避免裁切"""
    h, w = img.shape[:2]
    center = (w / 2, h / 2)
    m = cv2.getRotationMatrix2D(center, angle, 1.0)
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)
    m[0, 2] += nw / 2 - center[0]
    m[1, 2] += nh / 2 - center[1]
    # 透明图旋转后补透明，普通图补白色
    border = (0, 0, 0, 0) if img.ndim == 3 and img.shape[2] == 4 else (255, 255, 255)
    return cv2.warpAffine(img, m, (nw, nh), borderValue=border)


def flip_img(img, direction):
    """翻转：h 水平 / v 垂直"""
    if direction == "h":
        return cv2.flip(img, 1)
    if direction == "v":
        return cv2.flip(img, 0)
    raise ValueError("参数不合法：direction 只能是 h（水平翻转）或 v（垂直翻转）")


def gray_img(img):
    """灰度化"""
    if img.ndim == 2:
        return img.copy()
    code = cv2.COLOR_BGRA2GRAY if img.shape[2] == 4 else cv2.COLOR_BGR2GRAY
    return cv2.cvtColor(img, code)


def color_img(img, brightness=0, contrast=100, saturation=100):
    """颜色调节：亮度 -100~100，对比度/饱和度为百分比（100 为不变）"""
    if contrast < 0 or saturation < 0:
        raise ValueError("参数不合法：对比度和饱和度不能为负数")
    out = to_bgr(img).astype(np.float32)
    # 对比度以 128 为中心缩放，亮度整体加减
    out = (out - 128.0) * (contrast / 100.0) + 128.0 + brightness
    if saturation != 100:  # 在 HSV 空间缩放饱和度通道
        hsv = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= saturation / 100.0
        out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)


# ---------- 保存 ----------

def save_image(img, out_path, fmt=None):
    """保存图片；转 JPG 时自动把透明通道合成白底"""
    ext = (fmt or os.path.splitext(out_path)[1].lstrip(".")).lower()
    if ext in ("jpg", "jpeg"):
        ext = "jpg"
        img = to_bgr(img)
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"参数不合法：不支持的格式 {ext}")
    # 用 imencode + tofile 兼容中文路径
    ok, buf = cv2.imencode("." + ext, img)
    if not ok:
        raise ValueError(f"保存失败：不支持的格式 {ext}")
    buf.tofile(out_path)


# ---------- 路径版包装：加载 -> 编辑 -> 保存为新文件 ----------

def _edit_and_save(path, action, edit_func, out_dir=None):
    img = load_image(path)
    result = edit_func(img)
    out = build_output_path(path, action, out_dir)
    save_image(result, out)
    return out


def resize(path, width, height, out_dir=None):
    return _edit_and_save(path, f"resize_{width}x{height}",
                          lambda img: resize_img(img, width, height), out_dir)


def crop(path, left, top, right, bottom, out_dir=None):
    return _edit_and_save(path, "crop",
                          lambda img: crop_img(img, left, top, right, bottom), out_dir)


def rotate(path, angle, out_dir=None):
    return _edit_and_save(path, f"rotate{angle}",
                          lambda img: rotate_img(img, angle), out_dir)


def flip(path, direction, out_dir=None):
    return _edit_and_save(path, f"flip_{direction}",
                          lambda img: flip_img(img, direction), out_dir)


def to_gray(path, out_dir=None):
    return _edit_and_save(path, "gray", gray_img, out_dir)


def convert_format(path, new_format, out_dir=None):
    """格式转换：保存为新的扩展名"""
    new_format = new_format.lower()
    if new_format not in SUPPORTED_FORMATS:
        raise ValueError(f"参数不合法：不支持的格式 {new_format}")
    img = load_image(path)
    name, _ = os.path.splitext(os.path.basename(path))
    save_dir = out_dir if out_dir else os.path.dirname(os.path.abspath(path))
    os.makedirs(save_dir, exist_ok=True)
    out = os.path.join(save_dir, f"{name}.{new_format}")
    if os.path.abspath(out) == os.path.abspath(path):  # 避免覆盖原图
        out = os.path.join(save_dir, f"{name}_converted.{new_format}")
    save_image(img, out, fmt=new_format)
    return out


# ---------- 识图 ----------

def show_info(path):
    """展示图片基本信息"""
    img = load_image(path)
    h, w = img.shape[:2]
    print("-" * 40)
    print(f"文件名   ：{os.path.basename(path)}")
    print(f"图片格式 ：{detect_format(path)}")
    print(f"宽度×高度：{w} × {h}")
    print(f"颜色模式 ：{mode_name(img)}")
    print(f"文件大小 ：{file_size_str(path)}")
    print("-" * 40)


# ---------- 命令行入口 ----------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="简单图片工具（编辑结果保存为新文件）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("info", help="识图：显示图片信息")
    p.add_argument("file")

    p = sub.add_parser("resize", help="缩放")
    p.add_argument("file"); p.add_argument("width", type=int); p.add_argument("height", type=int)
    p.add_argument("--out", help="输出目录（默认与原图相同）")

    p = sub.add_parser("crop", help="裁剪 (left top right bottom)")
    p.add_argument("file")
    p.add_argument("left", type=int); p.add_argument("top", type=int)
    p.add_argument("right", type=int); p.add_argument("bottom", type=int)
    p.add_argument("--out")

    p = sub.add_parser("rotate", help="旋转（角度，逆时针）")
    p.add_argument("file"); p.add_argument("angle", type=float)
    p.add_argument("--out")

    p = sub.add_parser("flip", help="翻转：h 水平 / v 垂直")
    p.add_argument("file"); p.add_argument("direction", choices=["h", "v"])
    p.add_argument("--out")

    p = sub.add_parser("gray", help="灰度化")
    p.add_argument("file"); p.add_argument("--out")

    p = sub.add_parser("color", help="颜色调节：--brightness --contrast --saturation")
    p.add_argument("file")
    p.add_argument("--brightness", type=int, default=0)
    p.add_argument("--contrast", type=int, default=100)
    p.add_argument("--saturation", type=int, default=100)
    p.add_argument("--out")

    p = sub.add_parser("convert", help="格式转换，如 jpg / png")
    p.add_argument("file"); p.add_argument("format")
    p.add_argument("--out")

    args = parser.parse_args()

    try:
        if args.command == "info":
            show_info(args.file)
        else:
            actions = {
                "resize": lambda: resize(args.file, args.width, args.height, args.out),
                "crop": lambda: crop(args.file, args.left, args.top, args.right, args.bottom, args.out),
                "rotate": lambda: rotate(args.file, args.angle, args.out),
                "flip": lambda: flip(args.file, args.direction, args.out),
                "gray": lambda: to_gray(args.file, args.out),
                "color": lambda: _edit_and_save(
                    args.file, f"color_b{args.brightness}_c{args.contrast}_s{args.saturation}",
                    lambda img: color_img(img, args.brightness, args.contrast, args.saturation), args.out),
                "convert": lambda: convert_format(args.file, args.format, args.out),
            }
            saved = actions[args.command]()
            print(f"保存成功！新文件位置：{os.path.abspath(saved)}")
    except (FileNotFoundError, ValueError) as e:
        # 错误统一提示，不让程序崩溃
        print(f"错误：{e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
