# -*- coding: utf-8 -*-
"""图片工具图形界面版：圆角浅蓝科技风，交互式裁剪/旋转，颜色实时预览，预览后应用保存"""
import math
import os
import tkinter as tk
from tkinter import filedialog, messagebox

import cv2

from image_tool import (
    load_image, save_image, build_output_path, file_size_str, detect_format, mode_name,
    resize_img, crop_img, rotate_img, flip_img, gray_img, color_img, to_bgr,
    SUPPORTED_FORMATS,
)

# ---------- 浅蓝主题配色 ----------
BG = "#12233F"        # 星空蓝背景
CARD = "#FFFFFF"
ACCENT = "#2196F3"
ACCENT_DARK = "#1565C0"
BORDER = "#BBDEFB"
TEXT = "#16324A"
MUTED = "#6E8AA3"
FONT = "Microsoft YaHei UI"

PREVIEW_W, PREVIEW_H = 560, 440
HANDLE = 7
RADIUS = 12  # 全局圆角半径


def round_poly(canvas, x1, y1, x2, y2, r, **kw):
    """用平滑多边形画圆角矩形（单对象，支持描边）"""
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
           x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return canvas.create_polygon(pts, smooth=True, splinesteps=12, **kw)


class RoundedButton(tk.Canvas):
    """圆角扁平按钮"""

    def __init__(self, master, text, command=None, primary=True,
                 width=76, height=32, font=(FONT, 10)):
        super().__init__(master, width=width, height=height, bd=0,
                         bg=master.cget("bg"), highlightthickness=0, cursor="hand2")
        self._text, self._command, self._primary = text, command, primary
        self._font, self._hover = font, False
        self.bind("<Configure>", lambda e: self._paint())
        self.bind("<Enter>", lambda e: (setattr(self, "_hover", True), self._paint()))
        self.bind("<Leave>", lambda e: (setattr(self, "_hover", False), self._paint()))
        if command:
            self.bind("<Button-1>", lambda e: command())
        self._paint()

    def _paint(self):
        w, h = self.winfo_width() or 76, self.winfo_height() or 32
        self.delete("all")
        if self._primary:
            fill = ACCENT_DARK if self._hover else ACCENT
            fg = "white"
        else:
            fill = "#E3F2FD" if self._hover else CARD
            fg = ACCENT_DARK if self._hover else ACCENT
        round_poly(self, 1, 1, w - 1, h - 1, min(RADIUS, h // 2), fill=fill, outline="")
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self._font)


class RoundedEntry(tk.Canvas):
    """圆角输入框"""

    def __init__(self, master, width=6, default="", height=30):
        super().__init__(master, height=height, bd=0,
                         bg=master.cget("bg"), highlightthickness=0)
        self.entry = tk.Entry(self, width=width, font=(FONT, 10), fg=TEXT, bg=CARD,
                              relief="flat", highlightthickness=0,
                              insertbackground=ACCENT, justify="center")
        if default:
            self.entry.insert(0, default)
        self._win = self.create_window(8, height // 2, anchor="w", window=self.entry)
        self.bind("<Configure>", self._paint)
        self.entry.bind("<KeyRelease>", lambda e: self._paint())
        self._autosize()

    def _autosize(self):
        self.entry.update_idletasks()
        self.configure(width=self.entry.winfo_reqwidth() + 18)

    def _paint(self, ev=None):
        w, h = self.winfo_width() or 60, self.winfo_height() or 30
        tk.Canvas.delete(self, "bg")  # 注意：self.delete 已被重写为 Entry 的接口
        round_poly(self, 1, 1, w - 1, h - 1, min(RADIUS, h // 2),
                   fill=CARD, outline=BORDER, width=1, tags="bg")
        self.tag_raise(self._win)

    def get(self):
        return self.entry.get()

    def delete(self, a, b=None):
        self.entry.delete(a, b)

    def insert(self, a, s):
        self.entry.insert(a, s)


class RoundedCard(tk.Canvas):
    """圆角白色卡片容器，子控件放进 .inner"""

    def __init__(self, master, title=None):
        super().__init__(master, bd=0, bg=master.cget("bg"), highlightthickness=0)
        self.inner = tk.Frame(self, bg=CARD)
        self._win = self.create_window(1, 1, anchor="nw", window=self.inner)
        self.bind("<Configure>", self._on_cfg)
        self.inner.bind("<Configure>", self._on_inner)
        if title:
            tk.Label(self.inner, text=title, font=(FONT, 10, "bold"),
                     fg=ACCENT_DARK, bg=CARD).pack(anchor="w", padx=14, pady=(12, 4))

    def _on_cfg(self, ev):
        self.itemconfig(self._win, width=max(ev.width - 2, 10))
        self._paint(ev.width, ev.height)

    def _on_inner(self, ev):
        h = self.inner.winfo_reqheight() + 2
        if h != self.winfo_height():
            self.configure(height=h)
        self._paint(self.winfo_width(), h)

    def _paint(self, w, h):
        self.delete("bg")
        round_poly(self, 1, 1, w - 1, h - 1, RADIUS, fill=CARD,
                   outline=BORDER, width=1, tags="bg")
        self.tag_raise(self._win)


class RoundedScale(tk.Canvas):
    """圆角滑条：圆形滑块 + 实时数值"""

    def __init__(self, master, label, var, lo, hi, width=170, height=28, on_commit=None):
        super().__init__(master, width=width, height=height, bd=0,
                         bg=master.cget("bg"), highlightthickness=0, cursor="hand2")
        self.var, self.lo, self.hi, self._label = var, lo, hi, label
        self._pad, self._val_x = 52, width - 34
        self._editing = False
        self.on_commit = on_commit or (lambda: None)
        var.trace_add("write", lambda *a: self._paint())
        self.bind("<Configure>", lambda e: self._paint())  # 布局完成后按真实高度重绘
        self.bind("<Button-1>", self._drag)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<ButtonRelease-1>", lambda e: self.on_commit())  # 松手记为一步编辑
        # 点击数值可直接输入
        self.tag_bind("val", "<Button-1>", lambda e: self._start_edit())
        self._paint()

    def _start_edit(self):
        if self._editing:
            return
        self._editing = True
        cy = self.winfo_height() // 2
        self._edit = tk.Entry(self, width=4, font=(FONT, 9, "bold"), fg=ACCENT_DARK,
                              bg="white", relief="flat", justify="center",
                              highlightthickness=1, highlightbackground=BORDER,
                              highlightcolor=ACCENT)
        self._edit.insert(0, str(self.var.get()))
        self._edit_win = self.create_window(self._val_x, cy, anchor="w", window=self._edit)
        self._edit.select_range(0, "end")
        self._edit.focus_set()
        self._edit.bind("<Return>", lambda e: self._commit())
        self._edit.bind("<Escape>", lambda e: self._cancel())
        self._edit.bind("<FocusOut>", lambda e: self._commit())

    def _commit(self):
        if not self._editing:
            return
        try:
            v = int(self._edit.get())
        except ValueError:
            v = self.var.get()
        self._cancel()
        self.var.set(min(max(v, self.lo), self.hi))  # 限制在合法范围
        self.on_commit()  # 输入确认也记为一步编辑

    def _cancel(self):
        if not self._editing:
            return
        self._editing = False
        self.delete(self._edit_win)
        self._edit.destroy()

    def _x_for(self, v):
        frac = (v - self.lo) / (self.hi - self.lo)
        return self._pad + frac * (self._val_x - self._pad - 10)

    def _drag(self, ev):
        if self._editing:
            return
        if ev.x >= self._val_x - 2:  # 数值区域只响应点击输入，不拖动
            return
        frac = (ev.x - self._pad) / (self._val_x - self._pad - 10)
        frac = min(max(frac, 0.0), 1.0)
        self.var.set(int(round(self.lo + frac * (self.hi - self.lo))))

    def _paint(self):
        if self._editing:
            return  # 输入框打开时不重绘，避免删掉输入框
        w, h = self.winfo_width() or 170, self.winfo_height() or 28
        cy = h // 2
        self.delete("all")
        self.create_text(2, cy, text=self._label, anchor="w", font=(FONT, 9), fill=TEXT)
        round_poly(self, self._pad, cy - 3, self._val_x - 10, cy + 3, 3,
                   fill="#D9ECFB", outline="")
        x = self._x_for(self.var.get())
        self.create_oval(x - 7, cy - 7, x + 7, cy + 7, fill=ACCENT, outline="white", width=2)
        self.create_text(self._val_x, cy, text=str(self.var.get()), anchor="w",
                         font=(FONT, 9, "bold"), fill=ACCENT_DARK, tags="val")


def make_photo(img):
    """OpenCV BGR 图像 -> tkinter PhotoImage（PPM 数据，无需 PIL）"""
    bgr = to_bgr(img) if (img.ndim == 2 or img.shape[2] == 4) else img
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    h, w = rgb.shape[:2]
    return tk.PhotoImage(width=w, height=h, data=b"P6\n%d %d\n255\n" % (w, h) + rgb.tobytes())


def thumb(img, max_w, max_h):
    """等比缩放到预览区内，返回 (图像, 缩放比)"""
    h, w = img.shape[:2]
    scale = min(max_w / w, max_h / h, 1.0)
    if scale < 1.0:
        img = cv2.resize(img, (max(1, int(w * scale)), max(1, int(h * scale))),
                         interpolation=cv2.INTER_AREA)
    return img, scale


class ImageApp:
    def __init__(self, root):
        self.root = root
        root.title("ImageTool · 图片工具")
        root.configure(bg=BG)
        root.geometry("1020x800")
        root.minsize(940, 740)
        self.path = None
        self.current_img = None
        self.pending = []
        self.history = []          # 与 pending 平行：("geom", 图像) 或 ("color", 参数)
        self.color_step_params = (0, 100, 100)  # 上一次颜色步骤提交时的滑条值
        self.save_fmt = None
        self.pending_var = tk.StringVar(value="无")
        self.fmt_var = tk.StringVar(value="未选择")
        self.disp = None
        self.disp_scale = 1.0
        self.ox = self.oy = 0
        self.mode = None
        self.crop_rect = None
        self.drag_corner = None
        self.rot_start = None
        self.rot_delta = 0.0
        self.rot_base = None

        self._build_header()
        self._build_body()
        self._build_footer()
        root.bind("<Control-z>", lambda e: self.do_undo())

    # ---------- 界面搭建 ----------

    def _build_header(self):
        header = tk.Frame(self.root, bg=ACCENT, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="◈ ImageTool", font=(FONT, 14, "bold"),
                 bg=ACCENT, fg="white").pack(side="left", padx=16)
        tk.Label(header, text="识图 · 交互编辑 · 预览", font=(FONT, 9),
                 bg=ACCENT, fg="#D7ECFC").pack(side="left")
        open_wrap = tk.Frame(header, bg=ACCENT)
        open_wrap.pack(side="right", padx=16)
        RoundedButton(open_wrap, "打开图片", self.open_file, primary=False,
                      width=96, font=(FONT, 10, "bold")).pack(pady=8)

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=10)

        left = tk.Frame(body, bg=BG)
        left.pack(side="left", fill="both", expand=True)
        preview_card = RoundedCard(left, "预览")
        preview_card.pack(fill="both", expand=True)

        bar = tk.Frame(preview_card.inner, bg=CARD)
        bar.pack(fill="x", padx=14)
        RoundedButton(bar, "裁剪模式", self.enter_crop).pack(side="left", padx=(0, 6))
        RoundedButton(bar, "旋转模式", self.enter_rotate).pack(side="left", padx=(0, 6))
        self.crop_ok_btn = RoundedButton(bar, "✓ 确认裁剪", self.confirm_crop)
        RoundedButton(bar, "退出模式", self.exit_mode, primary=False).pack(side="left", padx=(6, 0))

        self.hint_var = tk.StringVar(value="打开图片后在此预览")
        tk.Label(preview_card.inner, textvariable=self.hint_var, font=(FONT, 9),
                 bg=CARD, fg=MUTED).pack(anchor="w", padx=14, pady=(8, 6))

        self.canvas = tk.Canvas(preview_card.inner, width=PREVIEW_W, height=PREVIEW_H,
                                bg=CARD, highlightthickness=0, bd=0)
        self.canvas.pack(padx=14, pady=(0, 14))
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_motion)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)

        # ---- 颜色设置：滑条实时生效，点数值可直接输入 ----
        color_card = RoundedCard(left, "颜色设置（拖动滑条实时预览，点数值可输入）")
        color_card.pack(fill="x", pady=(10, 0))
        cinner = tk.Frame(color_card.inner, bg=CARD)
        cinner.pack(fill="x", padx=14, pady=(0, 12))
        self.bri_var = tk.IntVar(value=0)
        self.con_var = tk.IntVar(value=100)
        self.sat_var = tk.IntVar(value=100)
        self.color_scales = []
        for var, label, lo, hi in [(self.bri_var, "亮度", -100, 100),
                                   (self.con_var, "对比度", 10, 200),
                                   (self.sat_var, "饱和度", 0, 200)]:
            s = RoundedScale(cinner, label, var, lo, hi,
                             on_commit=self._on_color_commit)
            s.pack(side="left", padx=(0, 16))
            self.color_scales.append(s)
            var.trace_add("write", self._on_color_change)

        # ---- 右列 ----
        right = tk.Frame(body, bg=BG, width=330)
        right.pack(side="right", fill="y", padx=(10, 0))
        right.pack_propagate(False)

        info_card = RoundedCard(right, "图片信息")
        info_card.pack(fill="x")
        self.info_var = tk.StringVar(value="尚未打开图片")
        tk.Label(info_card.inner, textvariable=self.info_var, font=(FONT, 9),
                 fg=TEXT, bg=CARD, justify="left").pack(anchor="w", padx=14, pady=(0, 12))

        edit_card = RoundedCard(right, "编辑（保存为新文件，不覆盖原图）")
        edit_card.pack(fill="x", pady=(10, 0))
        inner = tk.Frame(edit_card.inner, bg=CARD)
        inner.pack(fill="x", padx=14, pady=(0, 14))

        def op_row(label_text):
            row = tk.Frame(inner, bg=CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=label_text, font=(FONT, 9), fg=TEXT,
                     bg=CARD, width=8, anchor="w").pack(side="left")
            return row

        r = op_row("缩放")
        self.w_entry = RoundedEntry(r); self.w_entry.pack(side="left", padx=(0, 4))
        tk.Label(r, text="×", font=(FONT, 9), fg=MUTED, bg=CARD).pack(side="left")
        self.h_entry = RoundedEntry(r); self.h_entry.pack(side="left", padx=(4, 8))
        RoundedButton(r, "预览", self.do_resize).pack(side="left")

        r = op_row("裁剪")
        tk.Label(r, text="在预览区进入裁剪模式拖四角", font=(FONT, 8),
                 fg=MUTED, bg=CARD).pack(side="left")

        r = op_row("旋转")
        tk.Label(r, text="在预览区进入旋转模式拖动", font=(FONT, 8),
                 fg=MUTED, bg=CARD).pack(side="left")

        r = op_row("翻转")
        RoundedButton(r, "水平", lambda: self.do_flip("h")).pack(side="left", padx=(0, 6))
        RoundedButton(r, "垂直", lambda: self.do_flip("v")).pack(side="left", padx=(0, 8))
        RoundedButton(r, "灰度化", self.do_gray).pack(side="left")

        r = op_row("格式")
        self.fmt_btn = RoundedButton(r, "选择转换格式", self._show_fmt_menu, width=104)
        self.fmt_btn.pack(side="left", padx=(0, 8))
        tk.Label(r, textvariable=self.fmt_var, font=(FONT, 9, "bold"),
                 fg=ACCENT_DARK, bg=CARD).pack(side="left")

        pend_row = tk.Frame(inner, bg=CARD)
        pend_row.pack(fill="x", pady=(10, 2))
        tk.Label(pend_row, text="待应用效果：", font=(FONT, 9), fg=MUTED, bg=CARD).pack(side="left")
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
        footer = tk.Frame(self.root, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        footer.pack(fill="x", side="bottom")
        self.status_var = tk.StringVar(value="就绪")
        tk.Label(footer, textvariable=self.status_var, font=(FONT, 9),
                 fg=MUTED, bg=CARD, anchor="w").pack(fill="x", padx=14, pady=6)

    # ---------- 颜色实时层 ----------

    def _color_params(self):
        return self.bri_var.get(), self.con_var.get(), self.sat_var.get()

    def _color_active(self):
        return self._color_params() != (0, 100, 100)

    def _reset_color_vars(self):
        self.bri_var.set(0)
        self.con_var.set(100)
        self.sat_var.set(100)

    def _on_color_change(self, *args):
        """滑条变动：只重画预览（在缩略图上实时调色，速度快）"""
        if self.disp is None:
            return
        self._draw()
        self.hint_var.set("颜色实时预览（松手后记为一步，可撤回）" if self._color_active()
                          else f"编辑效果预览（未保存，共 {len(self.pending)} 步）")

    def _on_color_commit(self):
        """松手/输入确认：把本次颜色调整记为一步可撤回的编辑（滑条保留数值）"""
        if self.current_img is None:
            return
        params = self._color_params()
        if params == self.color_step_params:  # 数值没变，不记步骤
            return
        b, c, s = params
        self.pending.append(f"color_b{b}_c{c}_s{s}")
        self.history.append(("color", self.color_step_params))
        self.color_step_params = params
        self._update_pending_label()
        self.hint_var.set(f"编辑效果预览（未保存，共 {len(self.pending)} 步）")
        self.status_var.set("颜色调整已记为一步编辑，可撤回；点【应用并保存新图】才会保存")

    # ---------- 预览绘制 ----------

    def refresh_display(self):
        if self.current_img is None:
            return
        self.disp, self.disp_scale = thumb(self.current_img, PREVIEW_W - 20, PREVIEW_H - 20)
        self._draw()

    def _draw(self, override=None):
        self.canvas.delete("all")
        # 圆角预览底
        round_poly(self.canvas, 1, 1, PREVIEW_W - 1, PREVIEW_H - 1, 14,
                   fill="#F4FAFF", outline=BORDER, width=1)
        img = override if override is not None else self.disp
        if img is None:
            return
        img = color_img(img, *self._color_params()) if self._color_active() else img
        ih, iw = img.shape[:2]
        self.ox = (PREVIEW_W - iw) // 2
        self.oy = (PREVIEW_H - ih) // 2
        if self.mode == "crop" and override is None and self.crop_rect is not None:
            # 原图变灰作底，裁剪区域内贴彩色原图（裁剪框保持直角）
            base = to_bgr(img)
            gray = cv2.cvtColor(base, cv2.COLOR_BGR2GRAY)
            gray = (gray.astype("float32") * 0.75).astype("uint8")
            self._photo_base = make_photo(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR))
            self.canvas.create_image(self.ox, self.oy, image=self._photo_base, anchor="nw")
            x1, y1, x2, y2 = self._norm_rect()
            if x2 - x1 > 1 and y2 - y1 > 1:
                self._photo_region = make_photo(img[y1:y2, x1:x2])
                self.canvas.create_image(self.ox + x1, self.oy + y1,
                                         image=self._photo_region, anchor="nw")
            self.canvas.create_rectangle(self.ox + x1, self.oy + y1, self.ox + x2, self.oy + y2,
                                         outline=ACCENT, width=2)
            for cx, cy in self._corners():
                self.canvas.create_rectangle(cx - HANDLE, cy - HANDLE, cx + HANDLE, cy + HANDLE,
                                             fill="white", outline=ACCENT, width=2)
        else:
            self._photo_base = make_photo(img)
            self.canvas.create_image(self.ox, self.oy, image=self._photo_base, anchor="nw")

    def _norm_rect(self):
        x1, y1, x2, y2 = self.crop_rect
        return [min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)]

    def _corners(self):
        x1, y1, x2, y2 = self._norm_rect()
        return [(self.ox + x1, self.oy + y1), (self.ox + x2, self.oy + y1),
                (self.ox + x1, self.oy + y2), (self.ox + x2, self.oy + y2)]

    # ---------- 交互模式 ----------

    def enter_crop(self):
        if not self.require_image():
            return
        self.mode = "crop"
        h, w = self.disp.shape[:2]
        self.crop_rect = [int(w * 0.1), int(h * 0.1), int(w * 0.9), int(h * 0.9)]
        self.crop_ok_btn.pack(side="left", padx=(0, 6))
        self.canvas.configure(cursor="crosshair")
        self.hint_var.set("裁剪模式：按住左键拖动四个白角调整区域（一次拖一角），完成后点【确认裁剪】")
        self._draw()

    def enter_rotate(self):
        if not self.require_image():
            return
        self.mode = "rotate"
        self.crop_ok_btn.pack_forget()
        self.canvas.configure(cursor="fleur")
        self.hint_var.set("旋转模式：按住左键绕图片中心拖动旋转，松开鼠标即记入待应用效果")
        self._draw()

    def exit_mode(self):
        self.mode = None
        self.crop_rect = None
        self.drag_corner = None
        self.rot_start = None
        self.crop_ok_btn.pack_forget()
        self.canvas.configure(cursor="")
        self.hint_var.set("预览")
        self._draw()

    def confirm_crop(self):
        if self.mode != "crop" or self.crop_rect is None:
            return
        x1, y1, x2, y2 = self._norm_rect()
        s = self.disp_scale
        fx1, fy1 = int(round(x1 / s)), int(round(y1 / s))
        fx2, fy2 = int(round(x2 / s)), int(round(y2 / s))
        if fx2 - fx1 < 1 or fy2 - fy1 < 1:
            messagebox.showerror("错误", "参数不合法：裁剪区域太小")
            return
        self.exit_mode()
        self.preview_edit(f"crop{fx1}_{fy1}_{fx2}_{fy2}",
                          lambda img: crop_img(img, fx1, fy1, fx2, fy2))

    # ---------- 鼠标事件 ----------

    def _hit_corner(self, x, y):
        for i, (cx, cy) in enumerate(self._corners()):
            if abs(x - cx) <= HANDLE + 3 and abs(y - cy) <= HANDLE + 3:
                return i
        return None

    def _on_press(self, ev):
        if self.mode == "crop":
            self.drag_corner = self._hit_corner(ev.x, ev.y)
        elif self.mode == "rotate":
            cx, cy = PREVIEW_W / 2, PREVIEW_H / 2
            self.rot_start = math.degrees(math.atan2(ev.y - cy, ev.x - cx))
            self.rot_delta = 0.0
            self.rot_base = self.disp.copy()

    def _on_motion(self, ev):
        if self.mode == "crop" and self.drag_corner is not None:
            i = self.drag_corner
            h, w = self.disp.shape[:2]
            nx = min(max(ev.x - self.ox, 0), w)
            ny = min(max(ev.y - self.oy, 0), h)
            rect = self._norm_rect()
            pairs = [(0, 1), (2, 1), (0, 3), (2, 3)]
            px, py = pairs[i]
            rect[px] = int(nx)
            rect[py] = int(ny)
            self.crop_rect = rect
            self._draw()
        elif self.mode == "rotate" and self.rot_start is not None:
            cx, cy = PREVIEW_W / 2, PREVIEW_H / 2
            ang = math.degrees(math.atan2(ev.y - cy, ev.x - cx))
            self.rot_delta = ang - self.rot_start
            self._draw(override=rotate_img(self.rot_base, self.rot_delta))

    def _on_release(self, ev):
        if self.mode == "crop":
            self.drag_corner = None
        elif self.mode == "rotate" and self.rot_start is not None:
            delta = self.rot_delta
            self.rot_start = None
            if abs(delta) >= 1:
                angle = int(round(delta))
                self.preview_edit(f"rotate{angle}", lambda img: rotate_img(img, delta))

    # ---------- 格式列表 ----------

    def _show_fmt_menu(self):
        """弹出支持格式列表供选择"""
        menu = tk.Menu(self.root, tearoff=0, font=(FONT, 10), bg=CARD, bd=0,
                       relief="flat", activebackground=ACCENT, activeforeground="white",
                       fg=TEXT)
        for f in SUPPORTED_FORMATS:
            menu.add_command(label=f.upper(), command=lambda f=f: self._pick_fmt(f))
        menu.post(self.fmt_btn.winfo_rootx(), self.fmt_btn.winfo_rooty() + self.fmt_btn.winfo_height())

    def _pick_fmt(self, fmt):
        self.save_fmt = fmt
        self.fmt_var.set(fmt.upper())
        self._update_pending_label()
        self.status_var.set(f"保存时将转换为 {fmt} 格式，点【应用并保存新图】生效")

    # ---------- 动作 ----------

    def require_image(self):
        if not self.path:
            messagebox.showwarning("提示", "请先打开一张图片")
            return False
        return True

    def open_file(self):
        path = filedialog.askopenfilename(
            title="选择图片",
            filetypes=[("图片文件", "*.jpg *.jpeg *.png *.bmp *.webp *.tiff"), ("所有文件", "*.*")],
        )
        if not path:
            return
        try:
            img = load_image(path)
        except (FileNotFoundError, ValueError) as e:
            messagebox.showerror("错误", str(e))
            return
        self.path = path
        self.current_img = img
        self.pending = []
        self.history = []
        self.save_fmt = None
        self.fmt_var.set("未选择")
        self._reset_color_vars()
        self.color_step_params = (0, 100, 100)
        self._update_pending_label()
        h, w = img.shape[:2]
        self.info_var.set(
            f"文件名：{os.path.basename(path)}\n"
            f"图片格式：{detect_format(path)}\n"
            f"宽度×高度：{w} × {h}\n"
            f"颜色模式：{mode_name(img)}\n"
            f"文件大小：{file_size_str(path)}"
        )
        self.exit_mode()
        self.refresh_display()
        self.hint_var.set("原图预览")
        self.status_var.set(f"已打开：{path}")

    def _update_pending_label(self):
        parts = list(self.pending)
        if self.save_fmt:
            parts.append(f"转为{self.save_fmt}")
        self.pending_var.set(" → ".join(parts) if parts else "无")

    def preview_edit(self, tag, edit_func):
        """把一步编辑效果叠加到预览图上（只改预览，不保存）"""
        if not self.require_image():
            return
        if self._color_active():
            # 几何编辑基于当前可见的颜色效果：先固化颜色，之前的颜色步骤并入图像
            self.current_img = color_img(self.current_img, *self._color_params())
            self._reset_color_vars()
            self.color_step_params = (0, 100, 100)
            keep = [(t, h) for t, h in zip(self.pending, self.history) if h[0] != "color"]
            self.pending = [t for t, _ in keep]
            self.history = [h for _, h in keep]
        before = self.current_img
        try:
            result = edit_func(self.current_img)
        except (FileNotFoundError, ValueError) as e:
            self.status_var.set(f"错误：{e}")
            messagebox.showerror("错误", str(e))
            return
        self.current_img = result
        self.pending.append(tag)
        self.history.append(("geom", before))
        self._update_pending_label()
        self.refresh_display()
        self.hint_var.set(f"编辑效果预览（未保存，共 {len(self.pending)} 步）")
        self.status_var.set(f"已预览效果：{tag}，点【应用并保存新图】才会保存")

    def do_apply(self):
        """应用：把当前预览的编辑效果保存为新图片"""
        if not self.require_image():
            return
        if self._color_active():  # 还有未提交的颜色调整，先记为一步
            self._on_color_commit()
        if not self.pending and not self.save_fmt:
            messagebox.showwarning("提示", "还没有任何编辑效果，请先预览编辑效果")
            return
        result = color_img(self.current_img, *self._color_params()) if self._color_active() else self.current_img
        tags = list(self.pending) if self.pending else ["edited"]
        action = "_".join(tags)
        if self.save_fmt:
            name, _ = os.path.splitext(os.path.basename(self.path))
            save_dir = os.path.dirname(os.path.abspath(self.path))
            out = os.path.join(save_dir, f"{name}_{action}.{self.save_fmt}")
        else:
            out = build_output_path(self.path, action)
        try:
            save_image(result, out, fmt=self.save_fmt)
        except (FileNotFoundError, ValueError) as e:
            self.status_var.set(f"错误：{e}")
            messagebox.showerror("错误", str(e))
            return
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
        messagebox.showinfo("完成", msg)

    def do_undo(self):
        """撤回上一步编辑效果：恢复编辑前的图像"""
        if not self.require_image():
            return
        if not self.pending:
            messagebox.showwarning("提示", "没有可撤回的编辑效果")
            return
        tag = self.pending.pop()
        kind, payload = self.history.pop()
        if kind == "geom":
            self.current_img = payload
            self.exit_mode()
            self.refresh_display()
        else:  # color：滑条回退到上一步的数值
            self.color_step_params = payload
            b, c, s = payload
            self.bri_var.set(b)
            self.con_var.set(c)
            self.sat_var.set(s)
        self._update_pending_label()
        self.hint_var.set(f"编辑效果预览（未保存，共 {len(self.pending)} 步）" if self.pending else "原图预览")
        self.status_var.set(f"已撤回上一步：{tag}")

    def show_original(self):
        if not self.require_image():
            return
        self.current_img = load_image(self.path)
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
        try:
            w, h = int(self.w_entry.get()), int(self.h_entry.get())
        except ValueError:
            messagebox.showerror("错误", "参数不合法：宽高必须是整数")
            return
        self.preview_edit(f"resize{w}x{h}", lambda img: resize_img(img, w, h))

    def do_flip(self, direction):
        self.preview_edit(f"flip{direction}", lambda img: flip_img(img, direction))

    def do_gray(self):
        self.preview_edit("gray", gray_img)


def main():
    root = tk.Tk()
    ImageApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
