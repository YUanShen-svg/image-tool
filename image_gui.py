# -*- coding: utf-8 -*-
"""图片工具图形界面版：圆角浅蓝科技风，交互式裁剪/旋转，颜色实时预览，预览后应用保存"""
# 本文件用 tkinter（Python 自带的图形界面库）搭建窗口界面，
# 所有图像处理逻辑都从 image_tool.py 导入，这里只负责"界面 + 交互"。
import math  # 数学函数，旋转时用 atan2 计算鼠标角度
import os    # 文件路径处理
import tkinter as tk  # tkinter：Python 标准库里的图形界面工具包，"as tk" 起个短外号
# 从 tkinter 的子模块里导入两个现成的对话框：
#   filedialog：打开/保存文件的弹窗；messagebox：提示/报错弹窗
from tkinter import filedialog, messagebox

import cv2  # OpenCV：这里主要用它的颜色转换和缩放

# 从自己写的 image_tool.py 里导入需要的函数和常量（一次导入多个用逗号隔开）
from image_tool import (
    load_image, save_image, build_output_path, file_size_str, detect_format, mode_name,
    resize_img, crop_img, rotate_img, flip_img, gray_img, color_img, to_bgr,
    SUPPORTED_FORMATS,
)

# ---------- 浅蓝主题配色 ----------
# 下面都是界面配色常量：十六进制颜色 "#RRGGBB"（红绿蓝各 00~FF）
BG = "#12233F"        # 星空蓝背景
CARD = "#FFFFFF"      # 卡片白色
ACCENT = "#2196F3"    # 主题蓝（按钮等）
ACCENT_DARK = "#1565C0"  # 深蓝（悬停、文字）
BORDER = "#BBDEFB"    # 浅蓝描边
TEXT = "#16324A"      # 正文深蓝灰
MUTED = "#6E8AA3"     # 次要文字灰蓝
FONT = "Microsoft YaHei UI"  # 全局字体：微软雅黑

PREVIEW_W, PREVIEW_H = 560, 440  # 预览画布的固定宽高（像素）
HANDLE = 7    # 裁剪框四角"小方块把手"的半边长
RADIUS = 12   # 全局圆角半径


def round_poly(canvas, x1, y1, x2, y2, r, **kw):
    """用平滑多边形画圆角矩形（单对象，支持描边）"""
    # tkinter 的画布没有现成的"圆角矩形"，这里用一个技巧：
    # 把矩形四角附近的点密集排列，再让 canvas 用"平滑曲线"把这些点连起来，看起来就是圆角。
    # **kw 表示"接收任意多个关键字参数"（如 fill=颜色、outline=描边色），原样转交给绘图函数。
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, splinesteps=12, **kw)


class RoundedButton(tk.Canvas):
    """圆角扁平按钮"""
    # class（类）是"自定义控件的模板"。这个类继承自 tk.Canvas（画布控件），
    # 意思是"它本质是一块画布，但我们把它画成按钮的样子、赋予按钮的行为"。

    def __init__(self, master, text, command=None, primary=True,
                 width=76, height=32, font=(FONT, 10)):
        # __init__ 是"构造方法"：创建这个按钮时自动执行，负责初始化。
        # self 代表"这个按钮自己"，后面的代码都通过 self.xxx 给它挂属性和行为。
        # master：按钮放在哪个父容器里；text：按钮文字；command：点击后执行哪个函数
        super().__init__(master, width=width, height=height, bd=0,
                         bg=master.cget("bg"), highlightthickness=0, cursor="hand2")
        # super().__init__(...)：先让父类 tk.Canvas 完成它自己的初始化
        # bd=0 无边框；bg 取父容器的背景色（融为一体）；cursor="hand2" 鼠标移上来变小手掌
        self._text, self._command, self._primary = text, command, primary  # 把参数存到自己身上
        self._font, self._hover = font, False  # _hover 记录"鼠标是否悬停在按钮上"
        # bind 是"绑定事件"：某件事发生时执行某个函数。
        # <Configure>=控件尺寸变化时重画；<Enter>=鼠标进入；<Leave>=鼠标离开。
        # lambda e: ... 是临时小函数，e 是事件对象（这里用不到但必须接收）
        self.bind("<Configure>", lambda e: self._paint())
        # 下面这行用了逗号技巧：(表达式1, 表达式2) 会依次执行两个表达式——
        # 先把 _hover 设为 True，再重画按钮（画出"悬停变深色"的效果）
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self._paint()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self._paint()))
        if command:  # 如果创建按钮时传了点击回调
            self.bind("<Button-1>", lambda e: command())  # <Button-1>=鼠标左键按下，点击时执行 command
        self._paint()  # 初始化完立刻画一次

    def _paint(self):
        # 重画按钮：先算出当前该用什么颜色，再画圆角矩形+文字
        w, h = self.winfo_width() or 76, self.winfo_height() or 32
        # winfo_width() 取控件实际宽度；布局未完成时会返回 1 或 0，"or 76" 提供兜底默认值
        self.delete("all")  # 清空画布上所有旧内容（否则每次重画都会叠加）
        if self._primary:  # 主要按钮（蓝底白字）
            fill = ACCENT_DARK if self._hover else ACCENT  # 悬停时用深蓝
            fg = "white"   # fg = foreground 前景色，即文字颜色
        else:              # 次要按钮（白底蓝字）
            fill = "#E3F2FD" if self._hover else CARD
            fg = ACCENT_DARK if self._hover else ACCENT
        # min(RADIUS, h // 2)：圆角半径不能超过高度的一半（// 是整除）
        round_poly(self, 1, 1, w - 1, h - 1, min(RADIUS, h // 2), fill=fill, outline="")
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)  # 文字画在正中央


class RoundedEntry(tk.Canvas):
    """圆角输入框"""
    # 思路：tk 自带的 Entry（输入框）是直角的没法改，
    # 所以用画布画一个圆角"底框"，再把真正的 Entry 嵌在画布中间，视觉上就是圆角输入框。

    def __init__(self, master, width=6, default="", height=30):
        super().__init__(master, height=height, bd=0,
                         bg=master.cget("bg"), highlightthickness=0)
        # 创建真正的输入框控件：justify="center" 文字居中，insertbackground 是光标颜色
        self.entry = tk.Entry(self, width=width, font=(FONT, 10), fg=TEXT, bg=CARD,
                              relief="flat", highlightthickness=0,
                              insertbackground=ACCENT, justify="center")
        if default:  # 如果给了默认文字，就填进去（insert(0, ...) 表示插到最前面）
            self.entry.insert(0, default)
        # create_window：把另一个控件"嵌"进画布指定位置；anchor="w" 表示以西侧（左边中点）对齐
        self._win = self.create_window(8, height // 2, anchor="w", window=self.entry)
        self.bind("<Configure>", self._paint)  # 尺寸变化时重画底框
        # 每次在输入框里敲字（<KeyRelease> 按键松开）就重画，让底框宽度跟着内容自适应
        self.entry.bind("<KeyRelease>", lambda e: self._paint())
        self._autosize()

    def _autosize(self):
        # 根据输入框需要的宽度，自动调整整个画布的宽度
        self.entry.update_idletasks()  # 让 tk 先完成挂起的布局计算，才能取到准确宽度
        self.configure(width=self.entry.winfo_reqwidth() + 18)  # reqwidth=内容需要的宽度，+18 留边距

    def _paint(self, ev=None):
        w, h = self.winfo_width() or 60, self.winfo_height() or 30
        tk.Canvas.delete(self, "bg")  # 注意：self.delete 已被重写为 Entry 的接口
        # ↑ 本类下面的 delete() 被改成了"删输入框文字"，所以这里要指名道姓地
        #   调用"画布原本的 delete"来删除旧的圆角底框（tags="bg" 标记的那个图形）
        round_poly(self, 1, 1, w - 1, h - 1, min(RADIUS, h // 2),
                   fill=CARD, outline=BORDER, width=1, tags="bg")  # tags 给图形起名字，方便后续按名删除
        self.tag_raise(self._win)  # 把嵌入的输入框抬到最上层，别被底框盖住

    # 下面三个方法把调用"转发"给内部的真 Entry——
    # 这样外部代码可以直接对 RoundedEntry 用 .get()/.delete()/.insert()，
    # 就像操作普通输入框一样，不用关心里面套了一层画布。
    def get(self):
        return self.entry.get()  # 取输入框里的文字

    def delete(self, a, b=None):
        self.entry.delete(a, b)  # 删除文字（a 到 b 的范围）

    def insert(self, a, s):
        self.entry.insert(a, s)  # 在位置 a 插入字符串 s


class RoundedCard(tk.Canvas):
    """圆角白色卡片容器，子控件放进 .inner"""
    # 卡片 = 圆角白底 + 一个装内容的 Frame。
    # Frame（框架）是 tkinter 的"容器控件"，本身不可见，专门用来装其他控件做布局。
    # 使用方式：把按钮、文字等 pack 进 card.inner 里。

    def __init__(self, master, title=None):
        super().__init__(master, bd=0, bg=master.cget("bg"), highlightthickness=0)
        self.inner = tk.Frame(self, bg=CARD)  # 内容容器（白底）
        self._win = self.create_window(1, 1, anchor="nw", window=self.inner)
        # anchor="nw" = north west 西北角，即按左上角对齐摆放
        # 两个 <Configure> 绑定：外层画布尺寸变化、或内部内容尺寸变化时，都触发调整
        self.bind("<Configure>", self._on_cfg)
        self.inner.bind("<Configure>", self._on_inner)
        if title:  # 如果传了标题，在卡片顶部放一个加粗蓝字标签
            # tk.Label 是"文字标签"控件；pack 是 tkinter 最常用的布局方式（按顺序堆叠摆放）
            # anchor="w" 靠左；padx/pady 是外边距，(12, 4) 表示"上 12 下 4"
            tk.Label(self.inner, text=title, font=(FONT, 10, "bold"),
                     fg=ACCENT_DARK, bg=CARD).pack(anchor="w", padx=14, pady=(12, 4))

    def _on_cfg(self, ev):
        # 外层画布被拉大/缩小时：让内部 Frame 跟着占满宽度，并重画圆角底
        self.itemconfig(self._win, width=max(ev.width - 2, 10))
        self._paint(ev.width, ev.height)

    def _on_inner(self, ev):
        # 内部内容变高时（比如标签换行）：让外层画布高度跟着内容走
        h = self.inner.winfo_reqheight() + 2  # reqheight=内容需要的高度
        if h != self.winfo_height():
            self.configure(height=h)
        self._paint(self.winfo_width(), h)

    def _paint(self, w, h):
        self.delete("bg")  # 删旧底框（这里 delete 没被重写，就是画布自己的方法）
        round_poly(self, 1, 1, w - 1, h - 1, RADIUS, fill=CARD,
                   outline=BORDER, width=1, tags="bg")
        self.tag_raise(self._win)  # 内容抬到最上层


class RoundedScale(tk.Canvas):
    """圆角滑条：圆形滑块 + 实时数值"""
    # tkinter 自带 Scale 滑条又丑又难定制，这里完全手绘一个：
    # 画一条轨道 + 一个圆形滑块，监听鼠标拖动来改数值，点数值还能弹出输入框直接打字。
    # 数值本身存在 var（tkinter 的 IntVar 变量）里，外部通过 var 读写。

    def __init__(self, master, label, var, lo, hi, width=170, height=28, on_commit=None):
        super().__init__(master, width=width, height=height, bd=0,
                         bg=master.cget("bg"), highlightthickness=0, cursor="hand2")
        self.var, self.lo, self.hi, self._label = var, lo, hi, label
        # lo/hi 是滑条的最小/最大值；label 是左边的文字（如"亮度"）
        self._pad, self._val_x = 52, width - 34
        # _pad：轨道起点 x 坐标（给左边文字留位置）；_val_x：右边数值文字的 x 坐标
        self._editing = False  # 是否正打开着"直接输入数值"的小输入框
        # on_commit or (lambda: None)：没传回调就用一个"什么都不做"的空函数兜底，
        # 后面就能放心调用 self.on_commit() 而不用每次判断是不是 None
        self.on_commit = on_commit or (lambda: None)
        # var.trace_add("write", ...)：给 tkinter 变量装个"监听器"——
        # 每当 var 的值被修改，就自动执行后面的函数（这里是重画滑条）
        var.trace_add("write", lambda *a: self._paint())
        self.bind("<Configure>", lambda e: self._paint())  # 布局完成后按真实高度重绘
        self.bind("<Button-1>", self._drag)     # 按下左键：跳到该位置
        self.bind("<B1-Motion>", self._drag)    # 按住左键拖动：连续跟随
        self.bind("<ButtonRelease-1>", lambda e: self.on_commit())  # 松手记为一步编辑
        # 点击数值可直接输入
        # tag_bind：只给画布上带 "val" 标签的那个图形（数值文字）绑定点击事件，
        # 点其他地方不会触发——这是和 self.bind（整个画布都响应）的区别
        self.tag_bind("val", "<Button-1>", lambda e: self._start_edit())
        self._paint()

    def _start_edit(self):
        # 在数值位置弹出一个临时输入框，让用户直接打字输入数值
        if self._editing:  # 已经打开着就别重复开
            return
        self._editing = True
        cy = self.winfo_height() // 2  # 垂直中心
        self._edit = tk.Entry(self, width=4, font=(FONT, 9, "bold"), fg=ACCENT_DARK,
                              bg="white", relief="flat", justify="center",
                              highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor=ACCENT)
        self._edit.insert(0, str(self.var.get()))  # 预填当前数值，方便修改
        self._edit_win = self.create_window(self._val_x, cy, anchor="w", window=self._edit)
        self._edit.select_range(0, "end")  # 全选文字，一打字就替换
        self._edit.focus_set()             # 让输入框获得键盘焦点
        # 绑定三种"结束输入"的方式：回车确认、Esc 取消、点到别处（失去焦点）算确认
        self._edit.bind("<Return>", lambda e: self._commit())
        self._edit.bind("<Escape>", lambda e: self._cancel())
        self._edit.bind("<FocusOut>", lambda e: self._commit())

    def _commit(self):
        # 确认输入：读取输入框文字，转成整数并限制在合法范围
        if not self._editing:
            return
        try:
            v = int(self._edit.get())  # 尝试把文字转成整数
        except ValueError:             # 输入的不是数字（如 "abc"）会报 ValueError
            v = self.var.get()         # 那就保持原值，不生气
        self._cancel()                 # 收起输入框
        # min(max(v, lo), hi)：经典的"夹逼"写法，把 v 限制在 [lo, hi] 之间
        self.var.set(min(max(v, self.lo), self.hi))  # 限制在合法范围
        self.on_commit()  # 输入确认也记为一步编辑

    def _cancel(self):
        # 收起临时输入框，恢复原样
        if not self._editing:
            return
        self._editing = False
        self.delete(self._edit_win)  # 从画布上移除嵌入的窗口
        self._edit.destroy()         # 销毁输入框控件，释放资源

    def _x_for(self, v):
        # 把数值 v 换算成滑块在画布上的 x 坐标（线性映射）：
        # frac 是 v 在 [lo, hi] 里的比例（0.0~1.0），再映射到轨道的像素范围
        frac = (v - self.lo) / (self.hi - self.lo)
        return self._pad + frac * (self._val_x - self._pad - 10)

    def _drag(self, ev):
        # 鼠标按下/拖动时：把鼠标的 x 坐标反算成数值
        if self._editing:  # 正在打字输入时不响应拖动
            return
        if ev.x >= self._val_x - 2:  # 数值区域只响应点击输入，不拖动
            return
        frac = (ev.x - self._pad) / (self._val_x - self._pad - 10)
        frac = min(max(frac, 0.0), 1.0)  # 拖出轨道外也不会越界
        # int(round(...))：先四舍五入再取整，得到滑条当前应对应的数值
        self.var.set(int(round(self.lo + frac * (self.hi - self.lo))))

    def _paint(self):
        # 重画整个滑条：左边文字 + 圆角轨道 + 圆形滑块 + 右边数值
        if self._editing:
            return  # 输入框打开时不重绘，避免删掉输入框
        w, h = self.winfo_width() or 170, self.winfo_height() or 28
        cy = h // 2
        self.delete("all")
        self.create_text(2, cy, text=self._label, anchor="w", font=(FONT, 9), fill=TEXT)
        # 轨道：一条细圆角长条（上下各 3 像素高）
        round_poly(self, self._pad, cy - 3, self._val_x - 10, cy + 3, 3,
                   fill="#D9ECFB", outline="")
        x = self._x_for(self.var.get())  # 滑块位置由当前数值决定
        # create_oval 画圆（外切矩形定位）；outline="white", width=2 描白边更像"圆钮"
        self.create_oval(x - 7, cy - 7, x + 7, cy + 7, fill=ACCENT, outline="white", width=2)
        # 数值文字带 tags="val"——前面 tag_bind 就是靠这个名字让它可点击输入
        self.create_text(self._val_x, cy, text=str(self.var.get()), anchor="w",
                         font=(FONT, 9, "bold"), fill=ACCENT_DARK, tags="val")


def make_photo(img):
    """OpenCV BGR 图像 -> tkinter PhotoImage（PPM 数据，无需 PIL）"""
    # tkinter 显示图片需要 PhotoImage 对象，但它只认 PPM 等少数格式。
    # PPM 是一种极简的图片文本格式：开头一行描述（P6 宽 高 255），后面直接跟裸像素字节。
    # 这里手动拼出 PPM 数据喂给 PhotoImage，就不用额外安装 PIL 库了。
    bgr = to_bgr(img) if (img.ndim == 2 or img.shape[2] == 4) else img  # 灰度/透明图先统一成 3 通道
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)  # OpenCV 是 BGR，PPM 要求 RGB，得换下顺序
    h, w = rgb.shape[:2]
    # b"P6\n%d %d\n255\n" % (w, h)：老式格式化写法，%d 会被替换成整数（宽、高）
    # rgb.tobytes()：把整个数组变成裸字节串，和描述头拼在一起就是完整 PPM 文件内容
    return tk.PhotoImage(width=w, height=h, data=b"P6\n%d %d\n255\n" % (w, h) + rgb.tobytes())


def thumb(img, max_w, max_h):
    """等比缩放到预览区内，返回 (图像, 缩放比)"""
    # "等比缩放"= 宽高按同一比例缩小，图片不变形。
    # 返回两个值用元组打包：调用方写 a, b = thumb(...) 即可分别接收。
    h, w = img.shape[:2]
    # 取"宽的比例、高的比例、1.0"三者最小值：
    #   - 保证两个方向都塞得进预览区
    #   - min(..., 1.0) 保证小图不会被放大（放大只会变糊）
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:  # 只有确实需要缩小时才动手
        # max(1, int(...))：防止算出 0 尺寸导致报错，最小也要 1 像素
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))),
                         interpolation=cv2.INTER_AREA)
    return img, scale  # 把缩放比也返回去——裁剪时要用它把预览坐标换算回原图坐标


class ImageApp:
    # 主程序类：整个窗口的搭建、所有交互逻辑都在这里。
    # 普通类（不继承任何控件），它"持有" root 窗口并往里面摆控件。

    def __init__(self, root):
        self.root = root  # root 是 tk.Tk() 创建的主窗口
        root.title("ImageTool · 图片工具")   # 窗口标题
        root.configure(bg=BG)                 # 窗口背景色
        root.geometry("1020x800")             # 初始窗口大小：宽1020 × 高800
        root.minsize(940, 740)                # 允许缩小到的最小尺寸，防止界面挤乱
        # ---- 程序状态（当前打开了什么图、做了哪些编辑）----
        self.path = None            # 当前图片的文件路径（None 表示还没打开图）
        self.current_img = None     # 当前图片数组（编辑会直接作用在它上面）
        self.pending = []           # "待应用效果"列表：每步编辑的标签，如 ["resize800x600", "gray"]
        self.history = []          # 与 pending 平行：("geom", 图像) 或 ("color", 参数)
        # ↑ history 和 pending 一一对应，记录"每步编辑之前的状态"，撤回时用。
        #   几何编辑（裁剪/旋转等）存编辑前的整张图；颜色编辑只需存滑条参数，省内存
        self.color_step_params = (0, 100, 100)  # 上一次颜色步骤提交时的滑条值
        self.save_fmt = None        # 用户选择的"另存格式"（None=和原图一致）
        # StringVar：tkinter 的"界面变量"——它一变，绑定它的界面文字自动跟着变，
        # 不用手动去刷新标签，是 tkinter 数据驱动界面的核心机制
        self.pending_var = tk.StringVar(value="无")     # 显示待应用效果的文字
        self.fmt_var = tk.StringVar(value="未选择")      # 显示已选转换格式的文字
        # ---- 预览显示相关 ----
        self.disp = None            # 当前显示在预览区的缩略图
        self.disp_scale = 1.0       # 缩略图相对原图的缩放比（坐标换算用）
        self.ox = self.oy = 0       # 缩略图在画布上的左上角偏移（图是居中摆放的）
        # ---- 交互模式相关（裁剪/旋转）----
        self.mode = None            # 当前模式：None=普通预览 / "crop"=裁剪 / "rotate"=旋转
        self.crop_rect = None       # 裁剪框坐标 [x1, y1, x2, y2]（缩略图坐标系）
        self.drag_corner = None     # 正在拖动的是第几个角（0~3），None=没在拖
        self.rot_start = None       # 旋转起始时鼠标的角度
        self.rot_delta = 0.0        # 本次拖动累计旋转了多少度
        self.rot_base = None        # 旋转开始前的图像快照（拖动中始终基于它旋转，避免误差累积）

        # ---- 搭建界面三大块：顶栏 / 主体 / 底栏 ----
        self._build_header()
        self._build_body()
        self._build_footer()
        # 绑定全局快捷键 Ctrl+Z 到撤回功能
        root.bind("<Control-z>", lambda e: self.do_undo())

    # ---------- 界面搭建 ----------

    def _build_header(self):
        # 顶栏：蓝色横条，左边标题、右边"打开图片"按钮
        header = tk.Frame(self.root, bg=ACCENT, height=52)
        header.pack(fill="x")  # fill="x" 横向撑满窗口
        header.pack_propagate(False)  # 禁止子控件反过来改变 header 的高度（锁定 52 像素）
        tk.Label(header, text="◈ ImageTool", font=(FONT, 14, "bold"),
                 bg=ACCENT, fg="white").pack(side="left", padx=16)  # side="left" 靠左放
        tk.Label(header, text="识图 · 交互编辑 · 预览", font=(FONT, 9),
                 bg=ACCENT, fg="#D7ECFC").pack(side="left")
        open_wrap = tk.Frame(header, bg=ACCENT)
        open_wrap.pack(side="right", padx=16)  # 靠右放
        # 创建自定义圆角按钮，第三个参数 self.open_file 是"点击后执行的函数"
        # （注意传的是函数本身，没加括号——加括号就变成"立刻执行"了）
        RoundedButton(open_wrap, "打开图片", self.open_file, primary=False,
                      width=96, font=(FONT, 10, "bold")).pack(pady=8)

    def _build_body(self):
        # 主体区：左边"预览 + 颜色设置"，右边"图片信息 + 编辑面板"
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)
        # fill="both" 横竖都撑满；expand=True 窗口变大时跟着扩张

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        preview_card = RoundedCard(left, "预览")  # 预览卡片（圆角白底容器）
        preview_card.pack(fill="both", expand=True)

        # 预览卡片顶部的一行小按钮：进入裁剪/旋转模式、确认裁剪、退出模式
        bar = tk.Frame(preview_card.inner, bg=CARD)
        bar.pack(fill="x", padx=14)
        RoundedButton(bar, "裁剪模式", self.enter_crop).pack(side="left", padx=(0, 6))
        RoundedButton(bar, "旋转模式", self.enter_rotate).pack(side="left", padx=(0, 6))
        # 注意这个按钮存到了 self.crop_ok_btn：它平时隐藏，只有进裁剪模式才显示
        self.crop_ok_btn = RoundedButton(bar, "✓ 确认裁剪", self.confirm_crop)
        RoundedButton(bar, "退出模式", self.exit_mode, primary=False).pack(side="left", padx=(6, 0))

        # 提示文字：textvariable 绑定 StringVar，之后改 hint_var 的值，这行字自动更新
        self.hint_var = tk.StringVar(value="打开图片后在此预览")
        tk.Label(preview_card.inner, textvariable=self.hint_var, font=(FONT, 9),
                 bg=CARD, fg=MUTED).pack(anchor="w", padx=14, pady=(8, 6))

        # 预览画布：图片、裁剪框都画在这上面
        self.canvas = tk.Canvas(preview_card.inner, width=PREVIEW_W, height=PREVIEW_H,
                                bg=CARD, highlightthickness=0, bd=0)
        self.canvas.pack(padx=14, pady=(0, 14))
        # 给画布绑定三个鼠标事件：按下 / 按住移动 / 松开——裁剪和旋转全靠它们
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # ---- 颜色设置：滑条实时生效，点数值可直接输入 ----
        color_card = RoundedCard(left, "颜色设置（拖动滑条实时预览，点数值可输入）")
        color_card.pack(fill="x", pady=(10, 0))
        cinner = tk.Frame(color_card.inner, bg=CARD)
        cinner.pack(fill="x", padx=14, pady=(0, 12))
        # IntVar：存整数的界面变量（亮度/对比度/饱和度的当前值）
        self.bri_var = tk.IntVar(value=0)    # 亮度默认 0（不变）
        self.con_var = tk.IntVar(value=100)  # 对比度默认 100（不变）
        self.sat_var = tk.IntVar(value=100)  # 饱和度默认 100（不变）
        self.color_scales = []  # 存三个滑条对象的列表（防止它们被垃圾回收）
        # 用列表批量创建三个滑条：每项是 (变量, 标签文字, 最小值, 最大值)
        for var, label, lo, hi in [(self.bri_var, "亮度", -100, 100),
                                   (self.con_var, "对比度", 10, 200),
                                   (self.sat_var, "饱和度", 0, 200)]:
            s = RoundedScale(cinner, label, var, lo, hi,
                             on_commit=self._on_color_commit)  # 松手时记一步编辑
            s.pack(side="left", padx=(0, 16))  # 三个滑条横向并排
            self.color_scales.append(s)
            # 监听变量变化：值一变就实时刷新预览（拖动过程中也能看到效果）
            var.trace_add("write", self._on_color_change)

        # ---- 右列 ----
        right = tk.Frame(body, bg=BG, width=330)
        right.pack(side="right", fill="y", padx=(10, 0))  # fill="y" 纵向撑满，宽度固定
        right.pack_propagate(False)  # 锁定宽度 330，不被子控件挤压

        # 图片信息卡片：打开图片后显示文件名/格式/尺寸等
        info_card = RoundedCard(right, "图片信息")
        info_card.pack(fill="x")
        self.info_var = tk.StringVar(value="尚未打开图片")
        tk.Label(info_card.inner, textvariable=self.info_var, font=(FONT, 9),
                 fg=TEXT, bg=CARD, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        # 编辑卡片：缩放输入框、翻转/灰度按钮、格式选择、应用/撤回/清空按钮
        edit_card = RoundedCard(right, "编辑（保存为新文件，不覆盖原图）")
        edit_card.pack(fill="x", pady=(10, 0))
        inner = tk.Frame(edit_card.inner, bg=CARD)
        inner.pack(fill="x", padx=14, pady=(0, 14))

        # 函数里定义函数（"嵌套函数"）：op_row 只在 _build_body 里用，
        # 定义在这里可以把"创建一行并返回"的重复代码收拢成一处
        def op_row(label_text):
            row = tk.Frame(inner, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label_text, font=(FONT, 9), fg=TEXT,
                     bg=CARD, width=8, anchor="w").pack(side="left")  # width=8 让各行标签对齐
            return row

        # 缩放行：两个输入框（宽、高）+ 预览按钮
        r = op_row("缩放")
        self.w_entry = RoundedEntry(r); self.w_entry.pack(side="left", padx=(0, 4))
        tk.Label(r, text="×", font=(FONT, 9), fg=MUTED, bg=CARD).pack(side="left")
        self.h_entry = RoundedEntry(r); self.h_entry.pack(side="left", padx=(4, 8))
        RoundedButton(r, "预览", self.do_resize).pack(side="left")

        # 裁剪行：只有说明文字（实际操作在预览区进行）
        r = op_row("裁剪")
        tk.Label(r, text="在预览区进入裁剪模式拖四角", font=(FONT, 8),
                 fg=MUTED, bg=CARD).pack(side="left")

        r = op_row("旋转")
        tk.Label(r, text="在预览区进入旋转模式拖动", font=(FONT, 8),
                 fg=MUTED, bg=CARD).pack(side="left")

        # 翻转行：水平/垂直翻转 + 灰度化按钮
        r = op_row("翻转")
        # lambda: self.do_flip("h")：包一层是为了"带参数地延迟执行"——
        # 按钮点击时不接受参数，用 lambda 把 "h" 提前塞进去
        RoundedButton(r, "水平", lambda: self.do_flip("h")).pack(side="left", padx=(0, 6))
        RoundedButton(r, "垂直", lambda: self.do_flip("v")).pack(side="left", padx=(0, 8))
        RoundedButton(r, "灰度化", self.do_gray).pack(side="left")

        # 格式行：点按钮弹出格式菜单，选好后文字显示在旁边
        r = op_row("格式")
        self.fmt_btn = RoundedButton(r, "选择转换格式", self._show_fmt_menu, width=104)
        self.fmt_btn.pack(side="left", padx=(0, 8))
        tk.Label(r, textvariable=self.fmt_var, font=(FONT, 9, "bold"),
                 fg=ACCENT_DARK, bg=CARD).pack(side="left")

        # 待应用效果展示 + 三个大按钮（应用/撤回/清空）
        pend_row = tk.Frame(inner, bg=CARD)
        pend_row.pack(fill="x", pady=(10, 2))
        tk.Label(pend_row, text="待应用效果：", font=(FONT, 9), fg=MUTED, bg=CARD).pack(side="left")
        # wraplength=200：文字超过 200 像素宽自动换行（效果多了会很长）
        tk.Label(pend_row, textvariable=self.pending_var, font=(FONT, 9, "bold"),
                 fg=ACCENT_DARK, bg=CARD, anchor="w", wraplength=200, justify="left").pack(side="left")
        apply_row = tk.Frame(inner, bg=CARD)
        apply_row.pack(fill="x", pady=(4, 0))
        RoundedButton(apply_row, "✓ 应用并保存新图", self.do_apply, width=260).pack(fill="x")
        undo_row = tk.Frame(inner, bg=CARD)
        undo_row.pack(fill="x", pady=(6, 0))
        RoundedButton(undo_row, "↩ 撤回上一步（Ctrl+Z）", self.do_undo, primary=False,
                      width=260).pack(fill="x")
        reset_row = tk.Frame(inner, bg=CARD)
        reset_row.pack(fill="x", pady=(6, 0))
        RoundedButton(reset_row, "↺ 清空效果并显示原图", self.show_original, primary=False,
                      width=260).pack(fill="x")

    def _build_footer(self):
        # 底栏：一行状态文字，随时告诉用户刚发生了什么
        footer = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")  # side="bottom" 固定在窗口底部
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(footer, textvariable=self.status_var, font=(FONT, 9),
                 fg=MUTED, bg=CARD, anchor="w").pack(fill="x", padx=14, pady=6)

    # ---------- 颜色实时层 ----------

    def _color_params(self):
        # 一次性取出三个滑条的当前值，打包成元组返回
        return self.bri_var.get(), self.con_var.get(), self.sat_var.get()

    def _color_active(self):
        # 判断颜色是否有调整（不等于默认值 (0, 100, 100) 就是"正在调色"）
        return self._color_params() != (0, 100, 100)

    def _reset_color_vars(self):
        # 把三个滑条恢复默认值
        self.bri_var.set(0)
        self.con_var.set(100)
        self.sat_var.set(100)

    def _on_color_change(self, *args):
        """滑条变动：只重画预览（在缩略图上实时调色，速度快）"""
        # *args：接收任意数量的参数但不使用——trace_add 回调会传来 3 个参数，必须能接住
        if self.disp is None:  # 还没打开图片就什么都不做
            return
        self._draw()  # 重画预览（_draw 里会把当前颜色参数实时套在图上）
        # 根据是否有调色，切换提示文字（三元表达式：条件成立取前值，否则取后值）
        self.hint_var.set("颜色实时预览（松手后记为一步，可撤回）" if self._color_active()
                          else f"编辑效果预览（未保存，共 {len(self.pending)} 步）")

    def _on_color_commit(self):
        """松手/输入确认：把本次颜色调整记为一步可撤回的编辑（滑条保留数值）"""
        if self.current_img is None:
            return
        params = self._color_params()
        if params == self.color_step_params:  # 数值没变，不记步骤
            return  # 比如点了一下滑条但没拖动，就不该产生"一步编辑"
        b, c, s = params  # 元组拆包：三个值分别给 b、c、s
        # append 往列表末尾加一项：pending 记标签文字，history 记"这一步之前"的滑条值
        self.pending.append(f"color_b{b}_c{c}_s{s}")
        self.history.append(("color", self.color_step_params))
        self.color_step_params = params  # 更新"上一次提交的值"
        self._update_pending_label()
        self.hint_var.set(f"编辑效果预览（未保存，共 {len(self.pending)} 步）")
        self.status_var.set("颜色调整已记为一步编辑，可撤回；点【应用并保存新图】才会保存")

    # ---------- 预览绘制 ----------

    def refresh_display(self):
        # 根据当前图像重新生成缩略图并绘制（图像被编辑后调用）
        if self.current_img is None:
            return
        # thumb 返回 (缩略图, 缩放比) 两个值，一次赋给两个变量
        self.disp, self.disp_scale = thumb(self.current_img, PREVIEW_W - 20, PREVIEW_H - 20)
        self._draw()

    def _draw(self, override=None):
        # 把图像画到预览画布上。override：临时指定要画的图（旋转拖动中用），默认画 self.disp
        self.canvas.delete("all")  # 先清空，避免旧内容残留
        # 圆角预览底
        round_poly(self.canvas, 1, 1, PREVIEW_W - 1, PREVIEW_H - 1, 14,
                   fill="#F4FAFF", outline=BORDER, width=1)
        img = override if override is not None else self.disp
        if img is None:
            return
        # 如果滑条有调色，先把颜色效果实时套在图上再显示（只影响显示，不改原数据）
        img = color_img(img, *self._color_params()) if self._color_active() else img
        # ↑ *self._color_params() 的 * 是"解包"：把元组 (b, c, s) 拆成三个独立参数传入
        ih, iw = img.shape[:2]
        self.ox = (PREVIEW_W - iw) // 2  # 让图在画布里水平居中：(画布宽-图宽)/2
        self.oy = (PREVIEW_H - ih) // 2  # 垂直居中
        if self.mode == "crop" and override is None and self.crop_rect is not None:
            # ---- 裁剪模式的特殊画法 ----
            # 原图变灰作底，裁剪区域内贴彩色原图（裁剪框保持直角）
            # 效果：框外变暗、框内明亮，用户一眼看清"保留哪块"
            base = to_bgr(img)
            gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)  # 转灰
            gray = (gray.astype("float32") * 0.75).astype("uint8")  # 再压暗 25%
            # 存到 self._photo_base 很重要：PhotoImage 必须一直有变量引用着，
            # 否则会被 Python 垃圾回收，画布上的图会神秘消失（tkinter 经典大坑）
            self._photo_base = make_photo(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
            self.canvas.create_image(self.ox, self.oy, image=self._photo_base, anchor="nw")
            x1, y1, x2, y2 = self._norm_rect()  # 取规范化的裁剪框坐标
            if x2 - x1 > 1 and y2 - y1 > 1:  # 框大于 1 像素才画彩色区域
                self._photo_region = make_photo(img[y1:y2, x1:x2])  # 从彩图上切下框内区域
                self.canvas.create_image(self.ox + x1, self.oy + y1,
                                         image=self._photo_region, anchor="nw")  # 贴回对应位置
            # 画裁剪框边框（蓝色矩形）
            self.canvas.create_rectangle(self.ox + x1, self.oy + y1, self.ox + x2, self.oy + y2,
                                         outline=ACCENT, width=2)
            # 画四角的白色小方块"把手"（用户拖它们调整裁剪区域）
            for cx, cy in self._corners():
                self.canvas.create_rectangle(cx - HANDLE, cy - HANDLE, cx + HANDLE, cy + HANDLE,
                                             fill="white", outline=ACCENT, width=2)
        else:
            # ---- 普通模式：直接把图画上去 ----
            self._photo_base = make_photo(img)
            self.canvas.create_image(self.ox, self.oy, image=self._photo_base, anchor="nw")

    def _norm_rect(self):
        # 用户拖角时坐标可能"拖反"（x1 比 x2 大），这里统一整理成 [左上x, 左上y, 右下x, 右下y]
        x1, y1, x2, y2 = self.crop_rect
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    def _corners(self):
        # 算出裁剪框四个角在"画布坐标系"里的位置（图内坐标 + 图片偏移 ox/oy）
        # 返回顺序：0=左上 1=右上 2=左下 3=右下
        x1, y1, x2, y2 = self._norm_rect()
        return [(self.ox + x1, self.oy + y1), (self.ox + x2, self.oy + y1),
                (self.ox + x1, self.oy + y2), (self.ox + x2, self.oy + y2)]

    # ---------- 交互模式 ----------

    def enter_crop(self):
        # 点【裁剪模式】按钮：进入裁剪状态
        if not self.require_image():  # 没打开图片就提醒并返回
            return
        self.mode = "crop"
        h, w = self.disp.shape[:2]
        # 初始裁剪框：图片四周各留 10%，即框住中间 80% 区域
        self.crop_rect = [int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9)]
        self.crop_ok_btn.pack(side="left", padx=(0, 6))  # 显示【确认裁剪】按钮（之前没 pack 就是隐藏的）
        self.canvas.configure(cursor="crosshair")  # 鼠标变十字准星，提示"可以框选"
        self.hint_var.set("裁剪模式：按住左键拖动四个白角调整区域（一次拖一角），完成后点【确认裁剪】")
        self._draw()

    def enter_rotate(self):
        # 点【旋转模式】按钮：进入旋转状态
        if not self.require_image():
            return
        self.mode = "rotate"
        self.crop_ok_btn.pack_forget()  # pack_forget：把【确认裁剪】按钮藏起来（旋转用不到）
        self.canvas.configure(cursor="fleur")  # 鼠标变四向箭头，提示"可以拖动"
        self.hint_var.set("旋转模式：按住左键绕图片中心拖动旋转，松开鼠标即记入待应用效果")
        self._draw()

    def exit_mode(self):
        # 退出裁剪/旋转模式，回到普通预览，并把相关状态清空
        self.mode = None
        self.crop_rect = None
        self.drag_corner = None
        self.rot_start = None
        self.crop_ok_btn.pack_forget()
        self.canvas.configure(cursor="")  # 恢复默认鼠标指针
        self.hint_var.set("预览")
        self._draw()

    def confirm_crop(self):
        # 点【确认裁剪】：把裁剪框从"缩略图坐标"换算回"原图坐标"，记为一步编辑
        if self.mode != "crop" or self.crop_rect is None:
            return
        x1, y1, x2, y2 = self._norm_rect()
        s = self.disp_scale  # 缩略图相对原图的比例
        # 缩略图上的坐标 ÷ 比例 = 原图上的坐标；round 四舍五入避免小数
        fx1, fy1 = int(round(x1 / s)), int(round(y1 / s))
        fx2, fy2 = int(round(x2 / s)), int(round(y2 / s))
        if fx2 - fx1 < 1 or fy2 - fy1 < 1:  # 换算后不足 1 像素，裁不出东西
            messagebox.showerror("错误", "参数不合法：裁剪区域太小")  # 弹错误提示框
            return
        self.exit_mode()  # 先退出裁剪模式
        # preview_edit 把这步裁剪叠加到预览（还没保存！）
        self.preview_edit(f"crop{fx1}_{fy1}_{fx2}_{fy2}",
                          lambda img: crop_img(img, fx1, fy1, fx2, fy2))

    # ---------- 鼠标事件 ----------

    def _hit_corner(self, x, y):
        # 判断鼠标点 (x, y) 是否落在某个角的把手上：
        # 遍历四个角（enumerate 同时给出序号 i 和角坐标 (cx, cy)），
        # 鼠标与角中心的横纵距离都在把手大小内就算命中，返回角的序号
        for i, (cx, cy) in enumerate(self._corners()):
            if abs(x - cx) <= HANDLE + 3 and abs(y - cy) <= HANDLE + 3:  # +3 让点击判定稍微宽松点
                return i
        return None  # 一个角都没碰到

    def _on_press(self, ev):
        # 鼠标按下。ev 是事件对象：ev.x、ev.y 是鼠标在画布上的坐标
        if self.mode == "crop":
            self.drag_corner = self._hit_corner(ev.x, ev.y)  # 记录按住的是哪个角（可能为 None）
        elif self.mode == "rotate":
            # 旋转原理：算出"按下点相对画布中心的角度"作为起始角。
            # atan2(纵差, 横差) 返回弧度，math.degrees 转成角度
            cx, cy = PREVIEW_W / 2, PREVIEW_H / 2  # 画布中心
            self.rot_start = math.degrees(math.atan2(ev.y - cy, ev.x - cx))
            self.rot_delta = 0.0
            self.rot_base = self.disp.copy()  # 存下旋转前的图，拖动中始终基于它旋转

    def _on_motion(self, ev):
        # 按住鼠标移动（拖动中，会被高频触发）
        if self.mode == "crop" and self.drag_corner is not None:
            # ---- 拖动裁剪框的某个角 ----
            i = self.drag_corner
            h, w = self.disp.shape[:2]
            # 鼠标画布坐标 - 图片偏移 = 图内坐标；再 min/max 夹在图片范围内
            nx = min(max(ev.x - self.ox, 0), w)
            ny = min(max(ev.y - self.oy, 0), h)
            rect = self._norm_rect()
            # pairs 定义"拖动每个角时应该改哪两个坐标"：
            # 角0(左上)改 x1,y1；角1(右上)改 x2,y1；角2(左下)改 x1,y2；角3(右下)改 x2,y2
            # （rect 里 0=x1 1=y1 2=x2 3=y2）
            pairs = [(0, 1), (2, 1), (0, 3), (2, 3)]
            px, py = pairs[i]  # 取出被拖的角对应的两个下标
            rect[px] = int(nx)  # 让这个角跟着鼠标走
            rect[py] = int(ny)
            self.crop_rect = rect
            self._draw()  # 立即重画，视觉上就是"框跟着鼠标动"
        elif self.mode == "rotate" and self.rot_start is not None:
            # ---- 旋转拖动 ----
            cx, cy = PREVIEW_W / 2, PREVIEW_H / 2
            ang = math.degrees(math.atan2(ev.y - cy, ev.x - cx))  # 当前鼠标角度
            self.rot_delta = ang - self.rot_start  # 转过的角度 = 当前角 - 起始角
            # override=...：用"实时旋转后的图"临时覆盖显示（松开鼠标才真正记为一步）
            self._draw(override=rotate_img(self.rot_base, self.rot_delta))

    def _on_release(self, ev):
        # 鼠标松开：结束本次拖动
        if self.mode == "crop":
            self.drag_corner = None  # 松开就不再拖任何角
        elif self.mode == "rotate" and self.rot_start is not None:
            delta = self.rot_delta  # 先把值存到局部变量——下面的 lambda 要用
            self.rot_start = None
            if abs(delta) >= 1:  # 转了至少 1 度才算数（手抖不算）
                angle = int(round(delta))  # 标签里用取整后的角度，好看
                # 注意：实际旋转用的还是精确的 delta（小数角度），不是取整值
                self.preview_edit(f"rotate{angle}", lambda img: rotate_img(img, delta))

    # ---------- 格式列表 ----------

    def _show_fmt_menu(self):
        """弹出支持格式列表供选择"""
        # tk.Menu 是弹出菜单控件；tearoff=0 去掉顶部那条可撕下的虚线
        menu = tk.Menu(self.root, tearoff=0, font=(FONT, 10), bg=CARD, bd=0,
                       relief="flat", activebackground=ACCENT, activeforeground="white",
                       fg=TEXT)
        # 给每种支持的格式添加一个菜单项，点击就选它
        for f in SUPPORTED_FORMATS:
            # lambda f=f: ... 里的 "f=f" 是关键技巧！
            # 不写的话，所有菜单项都会共用循环结束后的最后一个 f（闭包陷阱）；
            # 写成默认参数 f=f，每个 lambda 都会"定格"自己创建时的 f 值
            menu.add_command(label=f.upper(), command=lambda f=f: self._pick_fmt(f))
        # post(x, y)：在屏幕坐标 (x, y) 处弹出菜单。
        # winfo_rootx/rooty 把控件的窗口内坐标换算成屏幕坐标，让菜单正好出现在按钮下方
        menu.post(self.fmt_btn.winfo_rootx(), self.fmt_btn.winfo_rooty() + self.fmt_btn.winfo_height())

    def _pick_fmt(self, fmt):
        # 用户在菜单里选了某个格式：记下来，等点【应用并保存新图】时生效
        self.save_fmt = fmt
        self.fmt_var.set(fmt.upper())  # 界面变量一变，显示格式的文字自动更新
        self._update_pending_label()
        self.status_var.set(f"保存时将转换为 {fmt} 格式，点【应用并保存新图】生效")

    # ---------- 动作 ----------

    def require_image(self):
        # 公共检查：很多操作都需要"先打开图片"，统一在这里判断
        # 返回 True=有图可以继续；False=没图（已经弹过提醒了）
        if not self.path:
            messagebox.showwarning("提示", "请先打开一张图片")  # 弹黄色警告框
            return False
        return True

    def open_file(self):
        # 点【打开图片】：弹出文件选择框，选中后加载并初始化所有状态
        path = filedialog.askopenfilename(
            title="选择图片",
            # filetypes 定义选择框里的文件类型过滤器（两组：图片文件 / 所有文件）
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff"), ("所有文件", "*.*")],
        )
        if not path:  # 用户点了"取消"，path 是空字符串
            return
        try:
            img = load_image(path)
        except (FileNotFoundError, ValueError) as e:  # 文件有问题（不存在/不是图片）
            messagebox.showerror("错误", str(e))  # 弹红色错误框，显示错误说明
            return
        # ---- 打开成功：重置所有状态，就像"新开一局" ----
        self.path = path
        self.current_img = img
        self.pending = []   # 清空待应用效果
        self.history = []   # 清空撤回历史
        self.save_fmt = None
        self.fmt_var.set("未选择")
        self._reset_color_vars()               # 颜色滑条归位
        self.color_step_params = (0, 100, 100)
        self._update_pending_label()
        h, w = img.shape[:2]
        # 更新右侧"图片信息"面板（\n 是换行符，f-string 里 {} 嵌入变量值）
        self.info_var.set(
            f"文件名：{os.path.basename(path)}\n"
            f"图片格式：{detect_format(path)}\n"
            f"宽度×高度：{w} × {h}\n"
            f"颜色模式：{mode_name(img)}\n"
            f"文件大小：{file_size_str(path)}"
        )
        self.exit_mode()       # 确保处于普通预览模式
        self.refresh_display() # 生成缩略图并显示
        self.hint_var.set("原图预览")
        self.status_var.set(f"已打开：{path}")

    def _update_pending_label(self):
        # 把 pending 列表拼成 "步骤1 → 步骤2 → 转为png" 这样的文字显示出来
        parts = list(self.pending)  # list(...) 复制一份，别改到原列表
        if self.save_fmt:
            parts.append(f"转为{self.save_fmt}")
        # " → ".join(列表)：把列表里的字符串用 " → " 连接成一句话；列表为空就是 ""
        self.pending_var.set(" → ".join(parts) if parts else "无")

    def preview_edit(self, tag, edit_func):
        """把一步编辑效果叠加到预览图上（只改预览，不保存）"""
        if not self.require_image():
            return
        if self._color_active():
            # 几何编辑基于当前可见的颜色效果：先固化颜色，之前的颜色步骤并入图像
            # （不然"先调色再裁剪"时，撤回裁剪会把颜色也弄丢，逻辑就乱了）
            self.current_img = color_img(self.current_img, *self._color_params())
            self._reset_color_vars()
            self.color_step_params = (0, 100, 100)
            # 列表推导式 + 过滤：只保留"不是颜色步骤"的记录（颜色已固化进图像，不再单独记）
            # zip 把两个列表逐对组合：[(标签1, 历史1), (标签2, 历史2), ...]
            keep = [(t, h) for t, h in zip(self.pending, self.history) if h[0] != "color"]
            self.pending = [t for t, _ in keep]   # 拆回两个平行列表
            self.history = [h for _, h in keep]
        before = self.current_img  # 记住编辑前的图——撤回时要退回这个状态
        try:
            result = edit_func(self.current_img)  # 执行传进来的编辑操作
        except (FileNotFoundError, ValueError) as e:
            self.status_var.set(f"错误：{e}")
            messagebox.showerror("错误", str(e))
            return
        self.current_img = result          # 编辑结果成为新的当前图
        self.pending.append(tag)           # 记一步"待应用效果"
        self.history.append(("geom", before))  # 记一步历史（几何类：存编辑前的整张图）
        self._update_pending_label()
        self.refresh_display()             # 刷新预览，让用户看到效果
        self.hint_var.set(f"编辑效果预览（未保存，共 {len(self.pending)} 步）")
        self.status_var.set(f"已预览效果：{tag}，点【应用并保存新图】才会保存")

    def do_apply(self):
        """应用：把当前预览的编辑效果保存为新图片"""
        if not self.require_image():
            return
        if self._color_active():  # 还有未提交的颜色调整，先记为一步
            self._on_color_commit()
        if not self.pending and not self.save_fmt:  # 什么效果都没有，保存个啥？
            messagebox.showwarning("提示", "还没有任何编辑效果，请先预览编辑效果")
            return
        # 算出最终图像：如果滑条上还有颜色效果，套上去；否则就是当前图
        result = color_img(self.current_img, *self._color_params()) if self._color_active() else self.current_img
        tags = list(self.pending) if self.pending else ["edited"]  # 没步骤时用个通用名
        action = "_".join(tags)  # 所有步骤标签用 _ 连接，作为新文件名的一部分
        if self.save_fmt:  # 选了转换格式：输出文件用新扩展名
            name, _ = os.path.splitext(os.path.basename(self.path))
            save_dir = os.path.dirname(os.path.abspath(self.path))
            out = os.path.join(save_dir, f"{name}_{action}.{self.save_fmt}")
        else:              # 没选格式：保持原扩展名
            out = build_output_path(self.path, action)
        try:
            save_image(result, out, fmt=self.save_fmt)  # 真正写文件
        except (FileNotFoundError, ValueError) as e:
            self.status_var.set(f"错误：{e}")
            messagebox.showerror("错误", str(e))
            return
        # ---- 保存成功：把结果当成新的"当前图"，清空所有待应用状态 ----
        self.current_img = result
        self.pending = []
        self.history = []
        self.save_fmt = None
        self.fmt_var.set("未选择")
        self._reset_color_vars()
        self.color_step_params = (0, 100, 100)
        self._update_pending_label()
        self.refresh_display()
        msg = f"应用成功！新文件位置：{os.path.abspath(out)}"
        self.status_var.set(msg)
        messagebox.showinfo("完成", msg)  # 弹蓝色信息框告诉用户存哪了

    def do_undo(self):
        """撤回上一步编辑效果：恢复编辑前的图像"""
        if not self.require_image():
            return
        if not self.pending:  # 列表为空说明没有可撤回的步骤
            messagebox.showwarning("提示", "没有可撤回的编辑效果")
            return
        # pop() 取出并删除列表最后一项——正好对应"撤回最近的一步"
        tag = self.pending.pop()
        kind, payload = self.history.pop()  # kind 是 "geom" 或 "color"，payload 是当时存的内容
        if kind == "geom":
            # 几何步骤：直接把图像退回到编辑前存的那张
            self.current_img = payload
            self.exit_mode()
            self.refresh_display()
        else:  # color：滑条回退到上一步的数值
            self.color_step_params = payload  # payload 是 (亮度, 对比度, 饱和度) 元组
            b, c, s = payload
            self.bri_var.set(b)  # set 之后 trace 监听器会自动触发滑条和预览重画
            self.con_var.set(c)
            self.sat_var.set(s)
        self._update_pending_label()
        # 还有剩余步骤就显示步数，撤完了就回到"原图预览"
        self.hint_var.set(f"编辑效果预览（未保存，共 {len(self.pending)} 步）" if self.pending else "原图预览")
        self.status_var.set(f"已撤回上一步：{tag}")

    def show_original(self):
        # 点【清空效果并显示原图】：一切推倒重来，回到刚打开图片时的样子
        if not self.require_image():
            return
        self.current_img = load_image(self.path)  # 从磁盘重新读一遍原图（最干净的做法）
        self.pending = []
        self.history = []
        self.save_fmt = None
        self.fmt_var.set("未选择")
        self._reset_color_vars()
        self.color_step_params = (0, 100, 100)
        self._update_pending_label()
        self.exit_mode()
        self.refresh_display()
        self.hint_var.set("原图预览")
        self.status_var.set("已清空编辑效果，恢复显示原图")

    def do_resize(self):
        # 点缩放行的【预览】按钮：读输入框里的宽高，把缩放记为一步
        try:
            # .get() 取到的是文字，int() 转成整数；输入的不是数字会报 ValueError
            w, h = int(self.w_entry.get()), int(self.h_entry.get())
        except ValueError:
            messagebox.showerror("错误", "参数不合法：宽高必须是整数")
            return
        # lambda 包一层：把用户输入的 w、h 和图像一起传给 resize_img
        self.preview_edit(f"resize{w}x{h}", lambda img: resize_img(img, w, h))

    def do_flip(self, direction):
        # 水平/垂直翻转（direction 是 "h" 或 "v"）
        self.preview_edit(f"flip{direction}", lambda img: flip_img(img, direction))

    def do_gray(self):
        # 灰度化：gray_img 本来就只接收一个图像参数，直接传函数名即可，不用 lambda
        self.preview_edit("gray", gray_img)


def main():
    # 程序入口：创建主窗口，构建界面，进入事件循环
    root = tk.Tk()      # Tk() 创建主窗口（一个程序只能有一个）
    ImageApp(root)      # 创建应用对象，往窗口里搭建所有界面
    root.mainloop()     # 进入"事件循环"：程序停在这里持续监听鼠标键盘事件，
                        # 直到用户关闭窗口才继续往下（也就是结束程序）


# 只有直接运行本文件时才启动界面；被 import 时不会自动弹窗
if __name__ == "__main__":
    main()
