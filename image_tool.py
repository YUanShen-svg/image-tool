# -*- coding: utf-8 -*-
"""简单图片工具核心库（OpenCV 版）：识图 + 编辑，结果保存为新文件，不覆盖原图"""
# import 的意思是"导入工具箱"：把别人写好的功能拿进来用
import os   # os 模块：和操作系统打交道，这里主要用来处理文件路径、判断文件是否存在
import sys  # sys 模块：Python 系统相关功能，这里用 sys.exit() 提前退出程序

# try/except 结构：先"尝试"执行 try 里的代码，
# 如果报 ImportError（导入失败，说明没装这个库），就转去执行 except 里的代码。
# 这样没装 OpenCV 的用户会看到一句友好提示，而不是一大堆看不懂的红色报错。
try:
    import cv2          # OpenCV：最常用的开源图像处理库。它读进来的图片就是一个 numpy 数组
    import numpy as np  # numpy：数值计算库，处理数组又快又方便。"as np" 是起外号，后面写 np 就行
except ImportError:
    print("缺少 OpenCV，请先安装：pip install opencv-python")
    sys.exit(1)  # 退出程序。数字 1 表示"因出错退出"（0 表示正常结束）

# 本工具支持的所有图片格式（元组 tuple：一种不可修改的列表，用圆括号）
SUPPORTED_FORMATS = ("jpg", "png", "bmp", "webp", "gif", "tiff")

# 文件头魔数 -> 格式名（OpenCV 不提供格式信息，用魔数识别）
# "魔数"指每种文件格式固定的开头字节，相当于文件的身份证。
# 例如所有 PNG 文件都以 \x89PNG 开头（\x89 表示一个十六进制字节）。
# 看魔数比看扩展名可靠——扩展名可以随便改，魔数改不了。
# 下面的列表里每一项是 (开头的字节, 格式名)，b"..." 表示这是"字节"而不是普通文字。
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
    # with open(...) 打开文件，"rb" 表示以"二进制读取"模式打开（图片不是文字，必须按字节读）。
    # 用 with 的好处：代码块结束后文件会自动关闭，不用手动写 f.close()
    with open(path, "rb") as f:
        head = f.read(12)  # 只读前 12 个字节——所有魔数都没这么长，读这么多足够了
    # 遍历 _MAGIC 列表，每次取出一个 (魔数, 格式名) 对。
    # "for magic, name in ..." 这种写法会同时把元组里的两个值拆给两个变量
    for magic, name in _MAGIC:
        # startswith：判断 head 是不是以 magic 开头
        if head.startswith(magic):
            return name  # return：把结果交回给调用者，函数到此结束
    return "未知"  # 循环走完都没匹配上，说明不是常见格式


def mode_name(img):
    """通道数 -> 颜色模式名称"""
    # 在 OpenCV 里，图片就是一个 numpy 数组：
    #   - 灰度图是二维的（行×列），ndim == 2
    #   - 彩色图是三维的（行×列×通道），shape[2] 就是通道数
    # 通道数含义：1=灰度，3=普通彩色，4=带透明通道（如 PNG）
    ch = 1 if img.ndim == 2 else img.shape[2]
    # 字典.get(键, 默认值)：按键查值，查不到就返回默认值
    return {1: "GRAY", 3: "RGB", 4: "RGBA"}.get(ch, f"{ch}通道")


def load_image(path):
    """读取图片（保留透明通道）；文件不存在或不是有效图片时给出提示"""
    if not os.path.exists(path):  # os.path.exists：判断这个路径上有没有文件
        # raise 主动抛出错误，程序会跳到调用它的 try/except 处，带上我们写的中文说明
        raise FileNotFoundError(f"文件不存在：{path}")
    # 这行是中文路径读图的关键，分三步（从里往外读）：
    #   1. np.fromfile(path, dtype=np.uint8)：把文件按字节读成数组（能正确处理中文路径）
    #   2. cv2.imdecode(...)：把字节数组解码成图片
    #   3. IMREAD_UNCHANGED：原样读入，有透明通道就保留（默认的 imread 会丢掉透明通道，
    #      而且不支持中文路径，所以我们不用它）
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    if img is None:  # 解码失败时 OpenCV 返回 None（空），说明文件内容不是有效图片
        raise ValueError(f"文件不是有效图片：{path}")
    return img


def build_output_path(src_path, action, out_dir=None):
    """生成新文件路径：原文件名_动作.扩展名，保存在原图同目录（或指定目录）"""
    # out_dir=None 是"默认参数"：调用时可以不传，不传就用 None（表示没指定）
    # os.path.abspath：转成完整绝对路径；dirname：取出所在文件夹
    src_dir = os.path.dirname(os.path.abspath(src_path))
    # 三元表达式：如果指定了 out_dir 就用它，否则用原图所在目录
    save_dir = out_dir if out_dir else src_dir
    os.makedirs(save_dir, exist_ok=True)  # 确保目录存在；exist_ok=True 表示已存在也不报错
    # splitext 把文件名拆成 (名字, 扩展名)，如 "照片.png" -> ("照片", ".png")
    name, ext = os.path.splitext(os.path.basename(src_path))
    # os.path.join 用系统正确的斜杠拼接路径；f"..." 是格式化字符串，{} 里的变量会被替换进来
    return os.path.join(save_dir, f"{name}_{action}{ext}")


def file_size_str(path):
    """把字节数格式化成易读的字符串"""
    size = os.path.getsize(path)  # 取文件大小的字节数
    # 从小到大尝试 B、KB、MB：小于 1024 就停在当前单位，否则除以 1024 升到下一级
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            # {:.1f} 表示保留 1 位小数
            return f"{size:.1f} {unit}" if unit != "B" else f"{size} B"
        size /= 1024  # /= 是"除以后再赋值"，等价于 size = size / 1024


def to_bgr(img):
    """带透明通道的图片合成白底 BGR（保存 JPG 前必须转换）"""
    # 小知识：OpenCV 的彩色图默认是 BGR 顺序（蓝绿红），和我们常说的 RGB 正好相反。
    # JPG 格式不支持透明，所以带透明通道的图存 JPG 前，要先把透明部分"垫"上白色。
    if img.ndim == 2:  # 灰度图（二维）：直接转成三通道 BGR
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:  # 带透明通道（BGRA，A 就是透明度 0~255）
        # [:, :, :3] 是数组切片：取所有行、所有列、前 3 个通道（丢掉透明通道）
        # astype(np.float32) 转成小数类型，避免下面乘法时整数溢出或精度丢失
        bgr = img[:, :, :3].astype(np.float32)
        alpha = (img[:, :, 3:4].astype(np.float32)) / 255.0  # 透明度换算到 0.0~1.0
        white = np.full_like(bgr, 255.0)  # 造一张和 bgr 同样大小的纯白图
        # 混合公式：结果 = 图片颜色×透明度 + 白色×(1-透明度)。
        # 越透明的地方白色占比越大，最后转回 uint8（0~255 的整数类型）
        return (bgr * alpha + white * (1 - alpha)).astype(np.uint8)
    return img  # 本来就是 3 通道 BGR，原样返回


# ---------- 编辑核心函数（作用于图像数组，返回新图像） ----------

def resize_img(img, width, height):
    """缩放：宽高必须大于 0"""
    # 先检查参数是否合理，不合理就抛出带说明的错误——这叫"防御式编程"
    if width <= 0 or height <= 0:
        raise ValueError(f"参数不合法：宽高必须大于 0（当前 {width}x{height}）")
    # cv2.resize 缩放图片。注意它要的是 (宽, 高)，和数组的 (行, 列) 顺序相反！
    # INTER_AREA 插值算法适合缩小图片，画质损失小
    return cv2.resize(img, (width, height), interpolation=cv2.INTER_AREA)


def crop_img(img, left, top, right, bottom):
    """裁剪：区域必须在图片范围内且有效"""
    h, w = img.shape[:2]  # shape 是 (高, 宽, 通道数)，[:2] 只取前两个
    # 裁剪区域必须满足：左边界在右边界左边、上边界在下边界下边，且不能是负数
    if left < 0 or top < 0 or right <= left or bottom <= top:
        raise ValueError("参数不合法：裁剪区域应满足 0 <= left < right, 0 <= top < bottom")
    if right > w or bottom > h:
        raise ValueError(f"参数不合法：裁剪区域超出图片范围（{w}x{h}）")
    # numpy 切片裁剪：img[上:下, 左:右]，就像从表格里框选一块矩形。
    # .copy() 把这块内容真正复制出来——不复制的话它和原图共用内存，改它会连累原图
    return img[top:bottom, left:right].copy()


def rotate_img(img, angle):
    """旋转：angle 为角度（正数逆时针），自动扩展画布避免裁切"""
    h, w = img.shape[:2]
    center = (w / 2, h / 2)  # 绕图片中心旋转
    # getRotationMatrix2D 生成一个 2×3 的"旋转矩阵"——数学上描述"每个点转到哪"的变换表
    m = cv2.getRotationMatrix2D(center, angle, 1.0)  # 1.0 表示不缩放
    # 旋转后图片会"斜着"，需要更大的画布才装得下。下面用三角函数算出新画布尺寸：
    cos, sin = abs(m[0, 0]), abs(m[0, 1])
    nw, nh = int(h * sin + w * cos), int(h * cos + w * sin)  # 新宽、新高
    # 调整矩阵里的平移量，让旋转后的图片正好落在新画布中央
    m[0, 2] += nw / 2 - center[0]
    m[1, 2] += nh / 2 - center[1]
    # 透明图旋转后补透明，普通图补白色
    # borderValue 是"画布空出来的地方填什么颜色"
    border = (0, 0, 0, 0) if img.ndim == 3 and img.shape[2] == 4 else (255, 255, 255)
    # warpAffine：按矩阵把每个像素搬到新位置，完成旋转
    return cv2.warpAffine(img, m, (nw, nh), borderValue=border)


def flip_img(img, direction):
    """翻转：h 水平 / v 垂直"""
    # cv2.flip 的第二个参数：1=水平翻转（左右镜像），0=垂直翻转（上下颠倒）
    if direction == "h":
        return cv2.flip(img, 1)
    if direction == "v":
        return cv2.flip(img, 0)
    raise ValueError("参数不合法：direction 只能是 h（水平翻转）或 v（垂直翻转）")


def gray_img(img):
    """灰度化"""
    if img.ndim == 2:      # 已经是灰度图，不用转
        return img.copy()  # 但仍复制一份返回，保证调用者拿到的是独立的新图
    # 根据有没有透明通道选不同的转换代码：BGRA(4通道)和BGR(3通道)转灰度的方法不一样
    code = cv2.COLOR_BGRA2GRAY if img.shape[2] == 4 else cv2.COLOR_BGR2GRAY
    return cv2.cvtColor(img, code)  # cvtColor = convert color，OpenCV 的颜色空间转换函数


def color_img(img, brightness=0, contrast=100, saturation=100):
    """颜色调节：亮度 -100~100，对比度/饱和度为百分比（100 为不变）"""
    if contrast < 0 or saturation < 0:
        raise ValueError("参数不合法：对比度和饱和度不能为负数")
    out = to_bgr(img).astype(np.float32)  # 先统一成 BGR，再转小数类型方便做数学运算
    # 对比度以 128 为中心缩放，亮度整体加减
    # 原理：128 是 0~255 的中间值。对比度>100% 时，比 128 亮的更亮、暗的更暗（差距拉大）；
    # 亮度就是给每个像素统一加/减一个数
    out = (out - 128.0) * (contrast / 100.0) + 128.0 + brightness
    if saturation != 100:  # 在 HSV 空间缩放饱和度通道
        # HSV 把颜色拆成：H色相(什么颜色)、S饱和度(鲜艳程度)、V明度(亮暗)。
        # 调饱和度只需缩放 S 通道，比在 BGR 里硬算简单得多。
        # np.clip(x, 0, 255)：把超出 0~255 的数"夹"回范围内（防止溢出出错）
        hsv = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV).astype(np.float32)
        hsv[:, :, 1] *= saturation / 100.0  # [:, :, 1] 选中所有像素的 S 通道，整体缩放
        out = cv2.cvtColor(np.clip(hsv, 0, 255).astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32)
    return np.clip(out, 0, 255).astype(np.uint8)  # 最后夹回合法范围并转回整数类型


# ---------- 保存 ----------

def save_image(img, out_path, fmt=None):
    """保存图片；转 JPG 时自动把透明通道合成白底"""
    # fmt 没传时，就从输出路径的扩展名里取；lstrip(".") 去掉扩展名前面的点
    ext = (fmt or os.path.splitext(out_path)[1].lstrip(".")).lower()
    if ext in ("jpg", "jpeg"):
        ext = "jpg"
        img = to_bgr(img)  # JPG 不支持透明，先合成白底
    if ext not in SUPPORTED_FORMATS:  # "x not in 列表" 判断 x 是否不在列表里
        raise ValueError(f"参数不合法：不支持的格式 {ext}")
    # 用 imencode + tofile 兼容中文路径（cv2.imwrite 遇到中文路径会悄悄失败）：
    #   1. imencode 先把图片编码成字节存进内存（buf），返回 (是否成功, 字节数据)
    #   2. buf.tofile 再把字节写入文件——这一步由 numpy 完成，不怕中文路径
    ok, buf = cv2.imencode("." + ext, img)
    if not ok:
        raise ValueError(f"保存失败：不支持的格式 {ext}")
    buf.tofile(out_path)


# ---------- 路径版包装：加载 -> 编辑 -> 保存为新文件 ----------

def _edit_and_save(path, action, edit_func, out_dir=None):
    # 函数名以 _ 开头是约定俗成的"内部函数"，表示外面别直接用
    # edit_func 参数是"一个函数"——Python 里函数可以像普通值一样被传递
    img = load_image(path)               # 第 1 步：读图
    result = edit_func(img)              # 第 2 步：交给传进来的编辑函数处理
    out = build_output_path(path, action, out_dir)  # 第 3 步：算出新文件路径
    save_image(result, out)              # 第 4 步：保存
    return out                           # 把新文件路径返回，方便告诉用户存哪了


# 下面这些是"路径版"函数：传入文件路径即可完成 读取->编辑->保存 全流程。
# lambda 是"匿名小函数"：lambda img: resize_img(img, w, h) 的意思是
# "收到一个 img，就用它调用 resize_img"——把具体操作打包传给 _edit_and_save。
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
    new_format = new_format.lower()  # 统一转小写，这样用户输 JPG/jpg/Jpg 都认
    if new_format not in SUPPORTED_FORMATS:
        raise ValueError(f"参数不合法：不支持的格式 {new_format}")
    img = load_image(path)
    name, _ = os.path.splitext(os.path.basename(path))
    # 变量名用 _ 是习惯写法，表示"这个值我拆出来了但用不到"
    save_dir = out_dir if out_dir else os.path.dirname(os.path.abspath(path))
    os.makedirs(save_dir, exist_ok=True)
    out = os.path.join(save_dir, f"{name}.{new_format}")
    if os.path.abspath(out) == os.path.abspath(path):  # 避免覆盖原图
        # 如果算出来的输出路径和原图一模一样（比如 png 转 png），就加个 _converted 后缀
        out = os.path.join(save_dir, f"{name}_converted.{new_format}")
    save_image(img, out, fmt=new_format)
    return out


# ---------- 识图 ----------

def show_info(path):
    """展示图片基本信息"""
    img = load_image(path)
    h, w = img.shape[:2]
    # print 逐行打印信息；"-" * 40 是把字符串重复 40 次，画一条分隔线
    print("-" * 40)
    print(f"文件名   ：{os.path.basename(path)}")   # basename：从完整路径里取出文件名
    print(f"图片格式 ：{detect_format(path)}")
    print(f"宽度×高度：{w} × {h}")
    print(f"颜色模式 ：{mode_name(img)}")
    print(f"文件大小 ：{file_size_str(path)}")
    print("-" * 40)


# ---------- 命令行入口 ----------

def main():
    # argparse 是 Python 自带的"命令行参数解析器"：
    # 用户敲 python image_tool.py resize 图.png 800 600 时，
    # 它负责把命令和参数拆开、检查、放进 args 对象里
    import argparse

    parser = argparse.ArgumentParser(description="简单图片工具（编辑结果保存为新文件）")
    # add_subparsers：注册"子命令"，即 resize、crop 这些跟在工具名后面的动作词
    sub = parser.add_subparsers(dest="command", required=True)  # required=True：必须给一个子命令

    # 每个 add_parser 注册一个子命令；add_argument 给这个子命令添加参数
    p = sub.add_parser("info", help="识图：显示图片信息")
    p.add_argument("file")  # 位置参数：必须按顺序给出，这里是图片路径

    p = sub.add_parser("resize", help="缩放")
    # 一行写多条语句用 ; 分隔（简单场景下可以让代码紧凑些）
    p.add_argument("file"); p.add_argument("width", type=int); p.add_argument("height", type=int)
    # type=int 表示这个参数要转成整数；以 -- 开头的是"可选参数"，可以不写
    p.add_argument("--out", help="输出目录（默认与原图相同）")

    p = sub.add_parser("crop", help="裁剪 (left top right bottom)")
    p.add_argument("file")
    p.add_argument("left", type=int); p.add_argument("top", type=int)
    p.add_argument("right", type=int); p.add_argument("bottom", type=int)
    p.add_argument("--out")

    p = sub.add_parser("rotate", help="旋转（角度，逆时针）")
    p.add_argument("file"); p.add_argument("angle", type=float)  # type=float：角度可以是小数
    p.add_argument("--out")

    p = sub.add_parser("flip", help="翻转：h 水平 / v 垂直")
    # choices 限定用户只能从 ["h", "v"] 里选，输别的会直接报错提示
    p.add_argument("file"); p.add_argument("direction", choices=["h", "v"])
    p.add_argument("--out")

    p = sub.add_parser("gray", help="灰度化")
    p.add_argument("file"); p.add_argument("--out")

    p = sub.add_parser("color", help="颜色调节：--brightness --contrast --saturation")
    p.add_argument("file")
    # default=0：用户不传这个参数时用的默认值
    p.add_argument("--brightness", type=int, default=0)
    p.add_argument("--contrast", type=int, default=100)
    p.add_argument("--saturation", type=int, default=100)
    p.add_argument("--out")

    p = sub.add_parser("convert", help="格式转换，如 jpg / png")
    p.add_argument("file"); p.add_argument("format")
    p.add_argument("--out")

    args = parser.parse_args()  # 真正开始解析用户敲的命令，结果都存进 args

    try:
        if args.command == "info":
            show_info(args.file)  # 识图只打印信息，不产生新文件
        else:
            # 字典的每个值是一个 lambda（打包好的"待执行操作"），
            # 按用户输入的子命令取出对应操作再执行——这样不用写一长串 if/elif
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
            saved = actions[args.command]()  # 先按键取出 lambda，再加 () 执行它
            print(f"保存成功！新文件位置：{os.path.abspath(saved)}")
    except (FileNotFoundError, ValueError) as e:
        # 错误统一提示，不让程序崩溃
        # except 可以一次捕获多种错误；as e 把错误对象存进变量 e，打印它就能看到错误说明
        print(f"错误：{e}")
        sys.exit(1)


# 只有"直接运行这个文件"时才会执行 main()；
# 如果是被别的文件 import（比如 image_gui.py 导入本文件），下面的 main() 不会自动跑。
# 这是 Python 脚本的标准写法。
if __name__ == "__main__":
    main()
