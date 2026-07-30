#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
野外相机数据分类工具 (WildCam Sorter)
======================================
功能：快速浏览野外相机拍摄的视频和截图（1视频+3截图为一组），
      将其分类复制到对应的物种文件夹或空拍文件夹中。

界面布局（上下排列）：
    +--------------------------------------------+      ---
    |              显示区 (5/6 高度)              |       |
    |  +------------------+------------------+    |       |
    |  |                  |                  |    |       |
    |  |    🎬 视频       |   📷 截图1       |    |       |
    |  |   (3:2 比例)    |   (3:2 比例)     |    |       |
    |  |                  |                  |    |       |
    |  +------------------+------------------+    |       | 窗口
    |  |                  |                  |    |       | 高度
    |  |   📷 截图2       |   📷 截图3       |    |       |
    |  |   (3:2 比例)    |   (3:2 比例)     |    |       |
    |  |                  |                  |    |       |
    |  +------------------+------------------+    |       |
    +--------------------------------------------+      ---
    |  操作区 (1/6 高度)                         |       |
    |  [A空拍] [F牛] [G马] ... [D新物种]  ◀ ▶   |       |
    +--------------------------------------------+      ---

键盘快捷键：
    1/2/3/4 : 切换对应文件的选中状态（默认全选）
    A       : 分类为"空拍"
    D       : 输入新物种名称并分类
    F~L     : 快速选择已有物种分类
    ←/→     : 上一组 / 下一组
    空格    : 播放/暂停视频

文件操作：仅复制（shutil.copy2），原始数据保持不变。
"""

import os
import sys
import json
import re
import csv
import shutil
from pathlib import Path
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk
import cv2
import numpy as np


# ==================== 全局常量 ====================

# 视频扩展名集合（小写）
VIDEO_EXTENSIONS = {'.avi', '.mp4', '.mov', '.mkv', '.wmv', '.webm', '.mts', '.m2ts', '.flv', '.3gp'}

# 图片扩展名集合（小写）
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.gif', '.webp'}

# 媒体文件的宽高比（3:2 = 1.5），用于显示区域的缩放计算
MEDIA_ASPECT_RATIO = 3.0 / 2.0

# 键盘映射
KEY_EMPTY = 'a'                 # 空拍
KEY_NEW_SPECIES = 'd'           # 新物种
KEY_SPECIES_KEYS = ['f', 'g', 'h', 'j', 'k', 'l', 'semicolon']  # 动态物种键
KEY_TOGGLE_FILES = ['1', '2', '3', '4']  # 切换选中状态
KEY_PLAY_PAUSE = 'space'        # 播放/暂停视频

# 颜色主题（深色护眼风格）
COLOR_BG = '#1E1E1E'
COLOR_PANEL_BG = '#252525'
COLOR_SELECTED_BORDER = '#4CAF50'    # 绿色边框 = 已选中
COLOR_UNSELECTED_BORDER = '#F44336'  # 红色边框 = 未选中
COLOR_TEXT = '#E0E0E0'
COLOR_TEXT_DIM = '#888888'
COLOR_BUTTON_EMPTY = '#546E7A'       # 蓝灰色 - 空拍按钮
COLOR_BUTTON_SPECIES = '#2E7D32'     # 深绿色 - 物种按钮
COLOR_BUTTON_NEW = '#E65100'         # 深橙色 - 新物种按钮
COLOR_BUTTON_NAV = '#424242'         # 灰色 - 导航按钮
COLOR_PROGRESS = '#1565C0'           # 蓝色 - 进度条
COLOR_TOOLBAR = '#111111'


# ==================== 辅助函数 ====================

def natural_sort_key(filename: str) -> list:
    """
    自然排序键函数。
    使字符串中的数字按数值排序而非字典序（例如 'IMG_2.JPG' 排在 'IMG_10.JPG' 之前）。
    
    参数：
        filename: 文件名
    返回：
        排序键列表，交替包含小写字符串片段和整数值
    """
    parts = re.split(r'(\d+)', filename)
    key = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return key


def is_video_file(filename: str) -> bool:
    """根据扩展名判断文件是否为视频"""
    return os.path.splitext(filename)[1].lower() in VIDEO_EXTENSIONS


def is_image_file(filename: str) -> bool:
    """根据扩展名判断文件是否为图片"""
    return os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS


def is_media_file(filename: str) -> bool:
    """判断文件是否为可处理的媒体文件"""
    return is_video_file(filename) or is_image_file(filename)


def scan_and_group_files(source_dir: str) -> list:
    """
    扫描源文件夹，自动识别视频和其对应的截图并分组。
    
    分组规则（智能识别）：
        - 找到所有视频文件（.AVI/.MP4/.MOV等）
        - 每个视频与它之后、下一个视频之前的所有照片归为一组
        - 例如：111.MOV(视频), 112.JPG, 113.JPG, 114.JPG, 115.JPG, 116.AVI(视频)
          → 组1: [111.MOV, 112.JPG, 113.JPG, 114.JPG, 115.JPG]
          → 组2: [116.AVI, ...]
        - 第一个视频之前的照片（如果有）单独成组（纯照片组）
    
    参数：
        source_dir: 源文件夹路径
    返回：
        分组列表，每组是一个文件路径列表
    """
    all_files = []
    try:
        for entry in os.listdir(source_dir):
            full_path = os.path.join(source_dir, entry)
            if os.path.isfile(full_path) and is_media_file(entry):
                all_files.append(full_path)
    except FileNotFoundError:
        return []

    # 按文件名自然排序（确保 001, 002, ... 顺序正确）
    all_files.sort(key=lambda f: natural_sort_key(os.path.basename(f)))

    if not all_files:
        return []

    # 找出所有视频文件的索引位置
    video_indices = []
    for i, file_path in enumerate(all_files):
        if is_video_file(os.path.basename(file_path)):
            video_indices.append(i)

    # 如果没有视频文件，所有照片作为一组
    if not video_indices:
        return [all_files]

    # 按视频分组：每个视频 + 它之后直到下一个视频之前的照片
    groups = []
    for vi, video_idx in enumerate(video_indices):
        group = [all_files[video_idx]]  # 视频本身
        # 下一个视频的索引（如果当前是最后一个视频，则到文件列表末尾）
        next_idx = video_indices[vi + 1] if vi + 1 < len(video_indices) else len(all_files)
        # 收集视频后面的照片（直到下一个视频之前）
        for j in range(video_idx + 1, next_idx):
            group.append(all_files[j])
        groups.append(group)

    # 处理第一个视频之前的照片（如果有的话，如纯照片开头）
    if video_indices[0] > 0:
        prefix_group = all_files[:video_indices[0]]
        groups.insert(0, prefix_group)

    return groups


def find_existing_species_folders(parent_dir: str, source_dir: str) -> list:
    """
    扫描目标父文件夹中已有的物种子文件夹。
    排除源文件夹自身、"空拍"文件夹、隐藏文件夹。

    参数：
        parent_dir: 目标父文件夹路径
        source_dir: 源文件夹路径（需要排除）
    返回：
        物种名称列表
    """
    species = []
    if not os.path.isdir(parent_dir):
        return species

    source_basename = os.path.basename(source_dir)
    exclude_names = {source_basename, '空拍', '__pycache__'}

    for entry in os.listdir(parent_dir):
        full_path = os.path.join(parent_dir, entry)
        if os.path.isdir(full_path) and entry not in exclude_names:
            if not entry.startswith('.'):
                species.append(entry)

    species.sort()
    return species


def extract_gps_from_file(file_path: str) -> dict:
    """
    从图片或视频文件中提取GPS坐标、海拔和拍摄时间（EXIF元数据）。
    
    参数：
        file_path: 媒体文件路径
    返回：
        字典，包含 longitude(经度), latitude(纬度), altitude(海拔), datetime(拍摄时间)
        如果读取失败，对应字段为 None
    """
    result = {
        'longitude': None,   # 十进制度数（东正西负）
        'latitude': None,    # 十进制度数（北正南负）
        'altitude': None,    # 米
        'datetime': None     # datetime 对象
    }
    
    try:
        img = Image.open(file_path)
        
        # 获取EXIF数据（兼容PIL新旧版本）
        try:
            exif = img.getexif()  # PIL >= 9.0
        except AttributeError:
            try:
                exif = img._getexif()  # 旧版PIL
            except Exception:
                return result
        
        if not exif:
            return result
        
        # ---- 提取拍摄时间 ----
        # EXIF标签：36867=DateTimeOriginal, 36868=DateTimeDigitized, 306=DateTime
        for tag_id in [36867, 36868, 306]:
            dt_str = exif.get(tag_id)
            if dt_str and isinstance(dt_str, str):
                try:
                    # 格式: "YYYY:MM:DD HH:MM:SS"
                    result['datetime'] = datetime.strptime(dt_str, '%Y:%m:%d %H:%M:%S')
                    break
                except ValueError:
                    pass
        
        # ---- 提取GPS信息 ----
        try:
            gps_ifd = exif.get_ifd(0x8825)  # GPSInfo IFD
        except Exception:
            gps_ifd = None
        
        if gps_ifd:
            # GPS纬度 (tag 2) 和 纬度参考 (tag 1: N/S)
            gps_lat = gps_ifd.get(2)
            gps_lat_ref = gps_ifd.get(1, 'N')
            if gps_lat and len(gps_lat) >= 3:
                lat_dd = _dms_to_decimal(gps_lat, gps_lat_ref)
                if lat_dd is not None:
                    result['latitude'] = lat_dd
            
            # GPS经度 (tag 4) 和 经度参考 (tag 3: E/W)
            gps_lon = gps_ifd.get(4)
            gps_lon_ref = gps_ifd.get(3, 'E')
            if gps_lon and len(gps_lon) >= 3:
                lon_dd = _dms_to_decimal(gps_lon, gps_lon_ref)
                if lon_dd is not None:
                    result['longitude'] = lon_dd
            
            # GPS海拔 (tag 6) — 通常以米为单位
            gps_alt = gps_ifd.get(6)
            if gps_alt is not None:
                try:
                    # 海拔可能是 IFDRational 对象或普通float
                    result['altitude'] = float(gps_alt)
                except (TypeError, ValueError):
                    pass
        
        img.close()
        
    except Exception:
        pass  # 非图片文件或EXIF读取失败，静默返回空值
    
    return result


def _dms_to_decimal(dms: tuple, ref: str) -> float:
    """
    将EXIF中的度分秒(DMS)格式转换为十进制度数(DD)。
    
    参数：
        dms: (degrees, minutes, seconds) 元组，值可能是float或IFDRational
        ref: 方向参考 ('N'/'S' 或 'E'/'W')
    返回：
        十进制度数（float），失败返回 None
    """
    try:
        deg = float(dms[0])
        min_val = float(dms[1])
        sec = float(dms[2])
        dd = deg + min_val / 60.0 + sec / 3600.0
        if ref in ('S', 'W'):
            dd = -dd
        return round(dd, 7)  # 7位小数 ≈ 1cm精度
    except (TypeError, ValueError, IndexError):
        return None


# ==================== 媒体面板组件 ====================

class MediaPanel:
    """
    单个媒体显示面板（视频或图片）。
    封装了显示 Label、文件名标签、选中状态指示器的创建和更新逻辑。
    
    用于2x2网格中的每一个格子：
        - 左上：视频面板（支持播放）
        - 右上/左下/右下：截图面板（静态图片）
    """
    
    def __init__(self, parent, index: int, label_text: str):
        """
        参数：
            parent: 父容器 Frame
            index: 在组内的索引（0=视频, 1=截图1, 2=截图2, 3=截图3）
            label_text: 面板标题（如 "🎬 视频"、"📷 截图1"）
        """
        self.parent = parent
        self.index = index
        self.label_text = label_text
        self.file_path = None          # 当前显示的文件路径
        self.is_selected = (index < 4)  # 默认选中（后面会被覆盖）
        self._photo = None             # 保持 PhotoImage 引用防止 GC
        
        # 创建面板框架
        self.frame = tk.Frame(
            parent,
            bg=COLOR_PANEL_BG,
            highlightthickness=3,      # 边框粗细
            highlightbackground=COLOR_SELECTED_BORDER  # 默认绿色（选中）
        )
        
        # 面板标题（顶部居中，缩小padding减少黑边）
        self.title_label = tk.Label(
            self.frame,
            text=label_text,
            font=("微软雅黑", 10, "bold"),
            bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT
        )
        self.title_label.pack(side=tk.TOP, pady=(2, 0))
        
        # 媒体显示标签（占据主要空间）
        self.media_label = tk.Label(
            self.frame,
            bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT_DIM,
            text="等待加载...",
            font=("微软雅黑", 12)
        )
        self.media_label.pack(fill=tk.BOTH, expand=True, padx=2, pady=1)
        
        # 文件名标签（底部）
        self.name_label = tk.Label(
            self.frame,
            text="",
            font=("微软雅黑", 8),
            bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT_DIM,
            anchor=tk.W
        )
        self.name_label.pack(side=tk.BOTTOM, fill=tk.X, padx=4, pady=1)
        
        # 右上角切换按钮（明显的按钮样式，点击切换选中/取消选中）
        self.select_btn = tk.Button(
            self.frame,
            text="✓ 已选",
            font=("微软雅黑", 9, "bold"),
            bg=COLOR_SELECTED_BORDER, fg='white',
            activebackground='#66BB6A',
            relief=tk.RAISED, bd=2,
            cursor='hand2',
            command=self._on_toggle_btn,
            padx=6, pady=1
        )
        self.select_btn.place(relx=0.97, rely=0.02, anchor='ne')
        
        # 绑定事件：点击图片/标题 → 打开全分辨率窗口
        self.media_label.bind('<Button-1>', self._on_fullscreen)
        self.title_label.bind('<Button-1>', self._on_fullscreen)
    
    def _on_fullscreen(self, event):
        """点击媒体区域 → 打开全分辨率查看窗口"""
        if hasattr(self, 'on_fullscreen_callback') and self.on_fullscreen_callback:
            self.on_fullscreen_callback(self.index)
    
    def _on_toggle_btn(self):
        """点击右上角切换按钮 → 切换选中状态"""
        if hasattr(self, 'on_toggle_callback') and self.on_toggle_callback:
            self.on_toggle_callback(self.index)
    
    def set_toggle_callback(self, callback):
        """设置切换选中状态的回调函数"""
        self.on_toggle_callback = callback
    
    def set_fullscreen_callback(self, callback):
        """设置打开全分辨率查看的回调函数"""
        self.on_fullscreen_callback = callback
    
    def set_selected(self, selected: bool):
        """设置选中状态并更新按钮样式"""
        self.is_selected = selected
        if selected:
            self.frame.config(highlightbackground=COLOR_SELECTED_BORDER)
            self.select_btn.config(text="✓ 已选", bg=COLOR_SELECTED_BORDER,
                                   activebackground='#66BB6A')
        else:
            self.frame.config(highlightbackground=COLOR_UNSELECTED_BORDER)
            self.select_btn.config(text="✗ 取消", bg=COLOR_UNSELECTED_BORDER,
                                   activebackground='#EF5350')
    
    def display_image(self, image_path: str):
        """
        显示静态图片，按3:2比例缩放后居中显示。
        
        参数：
            image_path: 图片文件路径
        """
        self.file_path = image_path
        self.name_label.config(text=f"📷 {os.path.basename(image_path)}")
        
        try:
            pil_img = Image.open(image_path)
            photo = self._resize_and_center(pil_img)
            if photo:
                self._photo = photo
                self.media_label.config(image=photo, text='')
            else:
                self.media_label.config(image='', text="等待渲染...")
        except Exception as e:
            self.media_label.config(image='', text=f"⚠ 加载失败\n{os.path.basename(image_path)}")
            self.name_label.config(text=f"❌ {e}")
    
    def display_placeholder(self, text: str = "(无文件)"):
        """显示占位文本（当没有对应文件时）"""
        self.file_path = None
        self._photo = None
        self.media_label.config(image='', text=text)
        self.name_label.config(text="")
        self.set_selected(False)
    
    def _calc_display_size(self):
        """计算当前面板内媒体的最佳显示尺寸（保持3:2比例），返回 (宽, 高) 或 (0,0)"""
        panel_w = self.frame.winfo_width()
        panel_h = self.frame.winfo_height()
        if panel_w <= 10:
            panel_w = self.frame.winfo_reqwidth()
        if panel_h <= 30:
            panel_h = self.frame.winfo_reqheight()
        if panel_w <= 20 or panel_h <= 40:
            return (0, 0)
        # 扣除标题栏(~18px) + 文件名栏(~14px) + 极小padding，最大化媒体显示面积
        available_w = panel_w - 6
        available_h = panel_h - 30
        if available_w <= 0 or available_h <= 0:
            return (0, 0)
        available_ratio = available_w / available_h
        if available_ratio > MEDIA_ASPECT_RATIO:
            new_h = available_h
            new_w = int(new_h * MEDIA_ASPECT_RATIO)
        else:
            new_w = available_w
            new_h = int(new_w / MEDIA_ASPECT_RATIO)
        return (max(new_w, 1), max(new_h, 1))
    
    def _resize_and_center(self, pil_img: Image.Image) -> ImageTk.PhotoImage:
        """
        将 PIL 图像按3:2比例缩放，适配当前面板大小。
        使用 BILINEAR（快速）替代 LANCZOS（慢速），预览场景差异极小。
        """
        new_w, new_h = self._calc_display_size()
        if new_w <= 0:
            return None
        # BILINEAR 高质量缩放（静态图片只加载一次，质量优先于速度）
        pil_resized = pil_img.resize((new_w, new_h), Image.LANCZOS)
        return ImageTk.PhotoImage(pil_resized)


# ==================== 全分辨率查看器 ====================

class FullScreenViewer:
    """
    全分辨率媒体查看器（独立弹窗）。
    
    功能：
        - 以原始分辨率显示图片/视频帧（不压缩）
        - 鼠标滚轮缩放（10%~500%）
        - 鼠标拖动平移（放大后）
        - 空格键播放/暂停视频
        - ESC 或返回按钮关闭
    """
    
    MIN_SCALE = 0.1   # 最小缩放10%
    MAX_SCALE = 5.0   # 最大缩放500%
    SCALE_STEP = 0.1  # 滚轮每次变化10%
    
    def __init__(self, parent, file_path: str, is_video: bool = False):
        """
        参数：
            parent: 父窗口（tk.Tk 或 tk.Toplevel）
            file_path: 媒体文件路径
            is_video: 是否为视频文件
        """
        self.file_path = file_path
        self.is_video = is_video
        self.scale_factor = 1.0       # 当前缩放比例（1.0=100%原始大小）
        self._orig_image = None       # PIL.Image：原始图片（静态）或当前视频帧
        self._display_photo = None    # PhotoImage：当前显示的图像
        self._video_cap = None        # cv2.VideoCapture（视频用）
        self._video_playing = False   # 视频播放状态
        self._video_after_id = None   # after ID
        self._drag_start = None       # 拖动起始坐标
        self._canvas_img_id = None    # Canvas中图片的ID
        
        # 创建顶层窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"🔍 {os.path.basename(file_path)}")
        self.window.geometry("1400x950")
        self.window.configure(bg='#111111')
        self.window.minsize(600, 400)
        
        # ESC关闭
        self.window.bind('<Escape>', lambda e: self._close())
        self.window.protocol("WM_DELETE_WINDOW", self._close)
        
        # ---- 顶部工具栏 ----
        toolbar = tk.Frame(self.window, bg='#1A1A1A', height=36)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        toolbar.pack_propagate(False)
        
        tk.Label(toolbar, text=f"  {os.path.basename(file_path)}",
                font=("微软雅黑", 10), bg='#1A1A1A', fg='#CCCCCC').pack(side=tk.LEFT, pady=6)
        
        self.label_zoom = tk.Label(toolbar, text="100%", font=("微软雅黑", 10),
                                   bg='#1A1A1A', fg='#AAAAAA')
        self.label_zoom.pack(side=tk.LEFT, padx=15, pady=6)
        
        # 返回按钮（右上角）
        btn_close = tk.Button(toolbar, text="✕ 返回 [ESC]", font=("微软雅黑", 9),
                              bg='#555555', fg='white', relief=tk.FLAT, cursor='hand2',
                              command=self._close, padx=10, pady=2)
        btn_close.pack(side=tk.RIGHT, padx=8, pady=4)
        
        # ---- Canvas显示区（可滚动）----
        canvas_frame = tk.Frame(self.window, bg='#111111')
        canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)
        
        # 水平滚动条
        self.h_scroll = tk.Scrollbar(canvas_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        
        # 垂直滚动条
        self.v_scroll = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Canvas
        self.canvas = tk.Canvas(canvas_frame, bg='#111111',
                                xscrollcommand=self.h_scroll.set,
                                yscrollcommand=self.v_scroll.set,
                                highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.h_scroll.config(command=self.canvas.xview)
        self.v_scroll.config(command=self.canvas.yview)
        
        # ---- 底部控制栏 ----
        bottom_bar = tk.Frame(self.window, bg='#1A1A1A', height=40)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)
        
        # 缩小按钮
        btn_zoom_out = tk.Button(bottom_bar, text="🔍− 缩小", font=("微软雅黑", 10),
                                 bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                 command=lambda: self._zoom(-self.SCALE_STEP), padx=8, pady=3)
        btn_zoom_out.pack(side=tk.LEFT, padx=8, pady=4)
        
        # 放大按钮
        btn_zoom_in = tk.Button(bottom_bar, text="🔍+ 放大", font=("微软雅黑", 10),
                                bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                command=lambda: self._zoom(self.SCALE_STEP), padx=8, pady=3)
        btn_zoom_in.pack(side=tk.LEFT, padx=2, pady=4)
        
        # 适合窗口按钮
        btn_fit = tk.Button(bottom_bar, text="📐 适合窗口", font=("微软雅黑", 10),
                            bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                            command=self._fit_to_window, padx=8, pady=3)
        btn_fit.pack(side=tk.LEFT, padx=8, pady=4)
        
        # 100%按钮
        btn_100 = tk.Button(bottom_bar, text="1:1 原始", font=("微软雅黑", 10),
                            bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                            command=lambda: self._set_scale(1.0), padx=8, pady=3)
        btn_100.pack(side=tk.LEFT, padx=2, pady=4)
        
        # 播放/暂停按钮（仅视频）
        if is_video:
            self.btn_play = tk.Button(bottom_bar, text="⏯ 暂停", font=("微软雅黑", 10),
                                      bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                      command=self._toggle_video, padx=10, pady=3)
            self.btn_play.pack(side=tk.RIGHT, padx=8, pady=4)
        
        # ---- 绑定事件 ----
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)     # Windows滚轮
        self.canvas.bind('<Button-4>', self._on_mousewheel_up)    # Linux滚轮上
        self.canvas.bind('<Button-5>', self._on_mousewheel_down)  # Linux滚轮下
        self.canvas.bind('<ButtonPress-1>', self._on_drag_start)
        self.canvas.bind('<B1-Motion>', self._on_drag_move)
        self.window.bind('<space>', lambda e: self._toggle_video() if is_video else None)
        
        # ---- 加载媒体 ----
        if is_video:
            self._load_video()
        else:
            self._load_image()
        # 默认50%显示（标准大小），用户可滚轮缩放调整
        self._set_scale(0.5)
    
    # ==================== 图片加载 ====================
    
    def _load_image(self):
        """加载静态图片（原始分辨率）"""
        try:
            self._orig_image = Image.open(self.file_path)
            self._update_display()
        except Exception as e:
            self.canvas.create_text(700, 400, text=f"无法加载图片: {e}",
                                    fill='#FF6B6B', font=("微软雅黑", 14))
    
    # ==================== 视频播放 ====================
    
    def _load_video(self):
        """加载并开始播放视频（全分辨率）"""
        self._video_cap = cv2.VideoCapture(self.file_path)
        if not self._video_cap.isOpened():
            self.canvas.create_text(700, 400, text="无法打开视频",
                                    fill='#FF6B6B', font=("微软雅黑", 14))
            return
        
        fps = self._video_cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 25
        self._video_fps = fps
        self._video_frame_delay = max(25, int(1000 / min(fps, 25)))
        
        # 先读取第一帧作为初始显示（让_set_scale能立即生效）
        ret, frame = self._video_cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._orig_image = Image.fromarray(frame_rgb)
            self._update_display()
        
        self._video_playing = True
        self._update_video_frame()
    
    def _update_video_frame(self):
        """更新视频帧（全分辨率，按scale缩放）"""
        if not self._video_playing or self._video_cap is None:
            return
        
        ret, frame = self._video_cap.read()
        if not ret:
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._video_cap.read()
            if not ret:
                self._video_playing = False
                return
        
        # 原始帧 BGR → RGB → PIL Image
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._orig_image = Image.fromarray(frame_rgb)
        self._update_display()
        
        self._video_after_id = self.window.after(self._video_frame_delay, self._update_video_frame)
    
    def _toggle_video(self):
        """播放/暂停视频"""
        if self._video_cap is None:
            return
        self._video_playing = not self._video_playing
        if self._video_playing:
            if hasattr(self, 'btn_play'):
                self.btn_play.config(text="⏯ 暂停")
            self._update_video_frame()
        else:
            if hasattr(self, 'btn_play'):
                self.btn_play.config(text="▶ 播放")
            if self._video_after_id:
                self.window.after_cancel(self._video_after_id)
                self._video_after_id = None
    
    # ==================== 显示更新 ====================
    
    def _update_display(self):
        """根据当前scale_factor更新Canvas中的显示图像"""
        if self._orig_image is None:
            return
        
        orig_w, orig_h = self._orig_image.size
        new_w = max(1, int(orig_w * self.scale_factor))
        new_h = max(1, int(orig_h * self.scale_factor))
        
        # 缩放图像（LANCZOS高质量）
        if new_w != orig_w or new_h != orig_h:
            display_img = self._orig_image.resize((new_w, new_h), Image.LANCZOS)
        else:
            display_img = self._orig_image.copy()
        
        self._display_photo = ImageTk.PhotoImage(display_img)
        
        # 更新Canvas
        if self._canvas_img_id:
            self.canvas.delete(self._canvas_img_id)
        
        # 居中放置图片
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        x = max(new_w // 2, canvas_w // 2)
        y = max(new_h // 2, canvas_h // 2)
        
        self._canvas_img_id = self.canvas.create_image(x, y, anchor=tk.CENTER,
                                                        image=self._display_photo)
        
        # 更新scrollregion（支持滚动）
        self.canvas.config(scrollregion=(0, 0, max(new_w, canvas_w), max(new_h, canvas_h)))
        
        # 更新缩放标签
        pct = int(self.scale_factor * 100)
        self.label_zoom.config(text=f"{pct}%")
    
    # ==================== 缩放 ====================
    
    def _zoom(self, delta: float):
        """改变缩放比例"""
        new_scale = self.scale_factor + delta
        self._set_scale(new_scale)
    
    def _set_scale(self, scale: float):
        """设置缩放比例（限制在MIN~MAX范围内）"""
        self.scale_factor = max(self.MIN_SCALE, min(self.MAX_SCALE, scale))
        self._update_display()
    
    def _fit_to_window(self):
        """缩放至适合窗口（图片完整可见）"""
        if self._orig_image is None:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 10 or canvas_h <= 10:
            return
        
        orig_w, orig_h = self._orig_image.size
        fit_scale = min(canvas_w / orig_w, canvas_h / orig_h) * 0.95
        self._set_scale(fit_scale)
    
    def _on_mousewheel(self, event):
        """Windows鼠标滚轮缩放"""
        if event.delta > 0:
            self._zoom(self.SCALE_STEP)
        else:
            self._zoom(-self.SCALE_STEP)
    
    def _on_mousewheel_up(self, event):
        """Linux滚轮上（放大）"""
        self._zoom(self.SCALE_STEP)
    
    def _on_mousewheel_down(self, event):
        """Linux滚轮下（缩小）"""
        self._zoom(-self.SCALE_STEP)
    
    # ==================== 拖动平移 ====================
    
    def _on_drag_start(self, event):
        """记录拖动起始位置"""
        self._drag_start = (event.x, event.y)
        self.canvas.config(cursor='fleur')  # 移动光标
    
    def _on_drag_move(self, event):
        """拖动平移图片"""
        if self._drag_start is None:
            return
        dx = self._drag_start[0] - event.x
        dy = self._drag_start[1] - event.y
        self.canvas.xview_scroll(dx, 'units')
        self.canvas.yview_scroll(dy, 'units')
        self._drag_start = (event.x, event.y)
    
    # ==================== 关闭 ====================
    
    def _close(self):
        """关闭查看器，释放资源"""
        self._video_playing = False
        if self._video_after_id:
            self.window.after_cancel(self._video_after_id)
        if self._video_cap:
            self._video_cap.release()
        self.window.destroy()


# ==================== 主应用类 ====================

class WildCamSorter:
    """
    野外相机数据分类工具。
    
    界面结构（上下排列）：
        ┌──────────────────────────────────────┐
        │         显示区 (5/6 高度)             │
        │  ┌──────────┐  ┌──────────┐         │
        │  │  视频     │  │  截图1   │         │
        │  │ (3:2)    │  │ (3:2)    │         │
        │  ├──────────┤  ├──────────┤         │
        │  │  截图2    │  │  截图3   │         │
        │  │ (3:2)    │  │ (3:2)    │         │
        │  └──────────┘  └──────────┘         │
        ├──────────────────────────────────────┤
        │         操作区 (1/6 高度)             │
        │ [A空拍] [F牛] [G马] ... [D新物种]    │
        └──────────────────────────────────────┘
    """
    
    def __init__(self, source_dir: str = None):
        # ===== 数据状态 =====
        self.source_dir = None            # 源文件夹路径
        self.parent_dir = None            # 目标父文件夹（源文件夹的父目录）
        self.groups = []                  # 文件分组列表
        self.current_group_index = -1     # 当前组索引
        self.current_group_files = []     # 当前组文件路径列表
        self.selected_flags = [True, True, True, True]  # 选中状态
        self.species_list = []            # 物种名称列表
        self.species_buttons = {}         # {物种名: Button}
        self.processed_groups = set()     # 已处理组标识集合
        self.class_history = {}           # 分类历史 {rel_path: {species, dest_files}}
        self.progress_file = None         # 进度文件路径
        
        # ===== 视频播放状态 =====
        self.video_cap = None             # cv2.VideoCapture 对象
        self.video_playing = False        # 是否正在播放
        self.video_fps = 25               # 视频帧率
        self.video_frame_delay = 40       # 帧间延迟（毫秒）
        self.video_after_id = None        # after() 调度 ID
        self.video_photo = None           # 保持视频帧 PhotoImage 引用
        
        # ===== UI 状态 =====
        self._panels = []                 # MediaPanel 列表（4个）
        self._resize_after_id = None      # 窗口调整大小时的防抖 ID
        self._panels_ready = False        # 面板是否已完成首次渲染
        
        # ===== 创建主窗口 =====
        self.root = tk.Tk()
        self.root.title("WildCam Sorter - 野外相机数据分类工具")
        self.root.geometry("1800x1000")    # 默认窗口大小
        self.root.configure(bg=COLOR_BG)
        self.root.minsize(1000, 700)
        
        # 窗口关闭时清理
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # ===== 配置根窗口 grid 权重 =====
        # row 0: toolbar (固定38px), row 1: 显示区 (expand), row 2: 操作区 (固定130px), row 3: 状态栏 (固定28px)
        self.root.grid_rowconfigure(0, weight=0)   # toolbar - 不伸缩
        self.root.grid_rowconfigure(1, weight=1)   # 显示区 - 占据所有剩余空间
        self.root.grid_rowconfigure(2, weight=0)   # 操作区 - 不伸缩
        self.root.grid_rowconfigure(3, weight=0)   # 状态栏 - 不伸缩
        self.root.grid_columnconfigure(0, weight=1)  # 唯一列 - 横向填满
        
        # ===== 构建界面 =====
        self._setup_toolbar()
        self._setup_display_area()
        self._setup_control_area()
        self._setup_statusbar()
        
        # ===== 绑定键盘事件 =====
        self._bind_keys()
        
        # ===== 初始化数据 =====
        if source_dir and os.path.isdir(source_dir):
            self._init_from_source(source_dir)
        else:
            # 启动后提示打开文件夹
            self.root.after(200, self._prompt_open_folder)
    
    # ==================== UI：顶部工具栏 ====================
    
    def _setup_toolbar(self):
        """构建顶部工具栏"""
        toolbar = tk.Frame(self.root, bg=COLOR_TOOLBAR, height=38)
        toolbar.grid(row=0, column=0, sticky='ew')
        toolbar.grid_propagate(False)
        
        # 打开文件夹按钮
        self.btn_open = tk.Button(
            toolbar, text="📂 打开文件夹", font=("微软雅黑", 10),
            bg='#0D7377', fg='white', activebackground='#14919B',
            relief=tk.FLAT, cursor='hand2',
            command=self._prompt_open_folder, padx=12, pady=3
        )
        self.btn_open.pack(side=tk.LEFT, padx=8, pady=3)
        
        # 文件夹路径显示
        self.label_folder = tk.Label(
            toolbar, text="未打开文件夹", font=("微软雅黑", 10),
            bg=COLOR_TOOLBAR, fg='#AAAAAA', anchor=tk.W
        )
        self.label_folder.pack(side=tk.LEFT, padx=10, pady=3, fill=tk.X, expand=True)
        
        # 统计信息（右侧）
        self.label_stats = tk.Label(
            toolbar, text="", font=("微软雅黑", 10),
            bg=COLOR_TOOLBAR, fg='#888888'
        )
        self.label_stats.pack(side=tk.RIGHT, padx=12, pady=3)
    
    # ==================== UI：显示区 ====================
    
    def _setup_display_area(self):
        """
        构建显示区（占窗口上部 5/6）。
        2x2 网格：4个 MediaPanel 等大排列。
        """
        self.display_frame = tk.Frame(self.root, bg=COLOR_BG)
        self.display_frame.grid(row=1, column=0, sticky='nsew')
        
        # 配置2x2网格权重：行列均等分
        for row in range(2):
            self.display_frame.grid_rowconfigure(row, weight=1, uniform='row')
        for col in range(2):
            self.display_frame.grid_columnconfigure(col, weight=1, uniform='col')
        
        # 创建4个媒体面板
        panel_configs = [
            (0, 0, 0, "🎬 视频"),      # 左上：视频
            (0, 1, 1, "📷 截图 ①"),    # 右上：截图1
            (1, 0, 2, "📷 截图 ②"),    # 左下：截图2
            (1, 1, 3, "📷 截图 ③"),    # 右下：截图3
        ]
        
        for row, col, idx, title in panel_configs:
            panel = MediaPanel(self.display_frame, idx, title)
            panel.frame.grid(row=row, column=col, sticky='nsew', padx=2, pady=2)
            panel.set_toggle_callback(self._toggle_file_selection)
            panel.set_fullscreen_callback(self._open_fullscreen)
            self._panels.append(panel)
    
    # ==================== UI：操作区 ====================
    
    def _setup_control_area(self):
        """
        构建操作区（占窗口下部 1/6）。
        按钮横向排列：空拍 | 物种1 | 物种2 | ... | 新物种 | 导航
        """
        self.control_frame = tk.Frame(self.root, bg='#1A1A1A', height=130)
        self.control_frame.grid(row=2, column=0, sticky='ew')
        self.control_frame.grid_propagate(False)  # 固定高度约130px
        
        # 使用内部 frame 来居中排列按钮
        inner = tk.Frame(self.control_frame, bg='#1A1A1A')
        inner.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
        # --- 左侧：分类按钮 ---
        left_frame = tk.Frame(inner, bg='#1A1A1A')
        left_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # 空拍按钮
        self.btn_empty = tk.Button(
            left_frame, text="🟦  空拍 [A]", font=("微软雅黑", 11, "bold"),
            bg=COLOR_BUTTON_EMPTY, fg='white', activebackground='#78909C',
            relief=tk.FLAT, cursor='hand2', padx=14, pady=8,
            command=self._on_empty
        )
        self.btn_empty.pack(side=tk.LEFT, padx=4)
        
        # 物种按钮容器
        self.species_frame = tk.Frame(left_frame, bg='#1A1A1A')
        self.species_frame.pack(side=tk.LEFT, padx=4)
        
        # 新物种按钮
        self.btn_new = tk.Button(
            left_frame, text="🟧  新物种 [D]", font=("微软雅黑", 11, "bold"),
            bg=COLOR_BUTTON_NEW, fg='white', activebackground='#FF8A00',
            relief=tk.FLAT, cursor='hand2', padx=14, pady=8,
            command=self._on_new_species
        )
        self.btn_new.pack(side=tk.LEFT, padx=4)
        
        # --- 右侧：导航 + 信息 ---
        right_frame = tk.Frame(inner, bg='#1A1A1A')
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 组信息
        self.label_group_info = tk.Label(
            right_frame, text="等待加载...", font=("微软雅黑", 10),
            bg='#1A1A1A', fg=COLOR_TEXT
        )
        self.label_group_info.pack(side=tk.LEFT, padx=10)
        
        # 上一组
        self.btn_prev = tk.Button(
            right_frame, text="◀ 上一组 [←]", font=("微软雅黑", 10),
            bg=COLOR_BUTTON_NAV, fg='white', activebackground='#616161',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._prev_group
        )
        self.btn_prev.pack(side=tk.LEFT, padx=3)
        
        # 下一组
        self.btn_next = tk.Button(
            right_frame, text="下一组 [→] ▶", font=("微软雅黑", 10),
            bg=COLOR_BUTTON_NAV, fg='white', activebackground='#616161',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._next_group
        )
        self.btn_next.pack(side=tk.LEFT, padx=3)
        
        # 跳至未处理按钮
        self.btn_jump = tk.Button(
            right_frame, text="⏭ 跳至未处理", font=("微软雅黑", 10),
            bg='#1565C0', fg='white', activebackground='#1E88E5',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._jump_to_unprocessed
        )
        self.btn_jump.pack(side=tk.LEFT, padx=3)
        
        # --- 选中状态提示 ---
        self.label_select_hint = tk.Label(
            inner, text="已选 4/4", font=("微软雅黑", 9),
            bg='#1A1A1A', fg=COLOR_TEXT_DIM
        )
        self.label_select_hint.pack(side=tk.RIGHT, padx=15)
        
        # 初始化物种按钮占位
        self._rebuild_species_buttons()
    
    # ==================== UI：状态栏 ====================
    
    def _setup_statusbar(self):
        """构建底部状态栏（进度条 + 状态文字）"""
        self.status_frame = tk.Frame(self.root, bg=COLOR_TOOLBAR, height=28)
        self.status_frame.grid(row=3, column=0, sticky='ew')
        self.status_frame.grid_propagate(False)
        
        # 进度条 Canvas
        self.progress_canvas = tk.Canvas(
            self.status_frame, bg=COLOR_TOOLBAR, height=5,
            highlightthickness=0
        )
        self.progress_canvas.pack(fill=tk.X)
        
        # 状态文字
        self.label_status = tk.Label(
            self.status_frame, text="就绪", font=("微软雅黑", 8),
            bg=COLOR_TOOLBAR, fg='#AAAAAA', anchor=tk.W
        )
        self.label_status.pack(side=tk.LEFT, padx=10)
        
        # 已处理计数
        self.label_count = tk.Label(
            self.status_frame, text="", font=("微软雅黑", 8),
            bg=COLOR_TOOLBAR, fg='#AAAAAA', anchor=tk.E
        )
        self.label_count.pack(side=tk.RIGHT, padx=10)
    
    # ==================== 键盘绑定 ====================
    
    def _bind_keys(self):
        """绑定全局键盘快捷键（使用 bind_all 确保在任何焦点下都能响应）"""
        # 数字键1-4：切换选中
        for key_char in KEY_TOGGLE_FILES:
            self.root.bind_all(f'<KeyPress-{key_char}>', self._on_key_toggle)
        # 注意：bind_all 的优先级低于各 widget 自己的绑定，但高于 bind
        # 我们使用 bind_all 确保键盘快捷键始终有效
        
        # 字母键
        self.root.bind_all(f'<KeyPress-{KEY_EMPTY}>', lambda e: self._on_empty())
        self.root.bind_all(f'<KeyPress-{KEY_EMPTY.upper()}>', lambda e: self._on_empty())
        self.root.bind_all(f'<KeyPress-{KEY_NEW_SPECIES}>', lambda e: self._on_new_species())
        self.root.bind_all(f'<KeyPress-{KEY_NEW_SPECIES.upper()}>', lambda e: self._on_new_species())
        
        # 动态物种键
        for key_char in KEY_SPECIES_KEYS:
            if key_char != 'semicolon':
                self.root.bind_all(f'<KeyPress-{key_char}>', self._on_key_species)
                self.root.bind_all(f'<KeyPress-{key_char.upper()}>', self._on_key_species)
            else:
                self.root.bind_all(f'<KeyPress-;>', self._on_key_species)
        
        # 导航键
        self.root.bind_all('<Left>', lambda e: self._prev_group())
        self.root.bind_all('<Right>', lambda e: self._next_group())
        
        # 空格：播放/暂停
        self.root.bind_all('<space>', lambda e: self._toggle_play_pause())
    
    def _on_key_toggle(self, event):
        """处理数字键1-4（切换选中状态）"""
        key_char = event.char
        if key_char in KEY_TOGGLE_FILES:
            idx = KEY_TOGGLE_FILES.index(key_char)
            self._toggle_file_selection(idx)
    
    def _on_key_species(self, event):
        """处理动态物种快捷键（F/G/H/J/K/L/;）"""
        key_char = event.char.lower() if event.char else ''
        if not key_char and event.keysym.lower() == 'semicolon':
            key_char = 'semicolon'
        
        species_names = list(self.species_buttons.keys())
        for i, name in enumerate(species_names):
            if i < len(KEY_SPECIES_KEYS) and KEY_SPECIES_KEYS[i] == key_char:
                self._on_species_click(name)
                return
    
    # ==================== 数据初始化 ====================
    
    def _init_from_source(self, source_dir: str):
        """从源文件夹初始化数据"""
        self.source_dir = os.path.abspath(source_dir)
        self.parent_dir = os.path.dirname(self.source_dir)
        
        self.label_folder.config(text=f"📁 {self.source_dir}")
        
        # 扫描文件分组
        self.groups = scan_and_group_files(self.source_dir)
        
        if not self.groups:
            messagebox.showwarning(
                "未找到媒体文件",
                f"在选定文件夹中未找到可识别的视频或图片文件。\n\n"
                f"支持的视频格式：AVI, MP4, MOV, MKV, WMV 等\n"
                f"支持的图片格式：JPG, JPEG, PNG, BMP 等"
            )
            self.label_stats.config(text="无媒体文件")
            return
        
        total_files = sum(len(g) for g in self.groups)
        self.label_stats.config(text=f"共 {len(self.groups)} 组 / {total_files} 个文件")
        
        # 扫描已有物种文件夹
        self._scan_species_folders()
        
        # 加载进度记录
        self._load_progress()
        
        # 找到第一个未处理的组
        first_unprocessed = 0
        skipped_count = 0
        for i in range(len(self.groups)):
            rel = self._get_group_rel_path(i)
            if rel not in self.processed_groups:
                first_unprocessed = i
                break
            skipped_count += 1
        
        self.current_group_index = -1
        self._panels_ready = False
        
        # 延迟加载首组：等待布局完成后渲染
        self.root.after(400, lambda: self._on_panels_ready(first_unprocessed, skipped_count))
    
    def _on_panels_ready(self, group_index: int, skipped: int = 0):
        """面板渲染完成后加载首组"""
        self._panels_ready = True
        self._load_group(group_index)
        if skipped > 0:
            self.label_status.config(
                text=f"⏭ 已跳过 {skipped} 个已处理组，从第 {group_index + 1} 组开始",
                fg='#FFB74D'
            )
        self._update_progress_bar()
        self._update_status()
    
    def _prompt_open_folder(self):
        """弹出文件夹选择对话框"""
        initial = self.source_dir if self.source_dir else os.path.expanduser("~")
        folder = filedialog.askdirectory(title="选择包含野外相机数据的文件夹", initialdir=initial)
        if folder:
            self._stop_video()
            self._init_from_source(folder)
    
    def _scan_species_folders(self):
        """扫描父文件夹中已有的物种文件夹并重建按钮"""
        if not self.parent_dir:
            return
        existing = find_existing_species_folders(self.parent_dir, self.source_dir)
        for sp in existing:
            if sp not in self.species_list:
                self.species_list.append(sp)
        self._rebuild_species_buttons()
    
    # ==================== 进度追踪 ====================
    
    def _load_progress(self):
        """读取进度文件（.wildcam_progress.json），含分类历史记录"""
        if not self.parent_dir:
            self.processed_groups = set()
            self.class_history = {}
            return
        
        self.progress_file = os.path.join(self.parent_dir, '.wildcam_progress.json')
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.processed_groups = set(data.get('processed', []))
                # class_history: {rel_path: {"species": "牛", "dest_files": ["完整目标路径", ...]}}
                self.class_history = data.get('history', {})
            except (json.JSONDecodeError, IOError):
                self.processed_groups = set()
                self.class_history = {}
        else:
            self.processed_groups = set()
            self.class_history = {}
    
    def _save_progress(self):
        """保存进度文件（含分类历史）"""
        if not self.progress_file:
            return
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'processed': list(self.processed_groups),
                    'history': self.class_history
                }, f, ensure_ascii=False, indent=2)
        except IOError:
            pass
    
    def _get_group_rel_path(self, group_index: int = None) -> str:
        """获取当前组的标识（第一个文件的相对路径），用于进度追踪"""
        if group_index is None:
            group_index = self.current_group_index
        if 0 <= group_index < len(self.groups) and self.groups[group_index]:
            return os.path.relpath(self.groups[group_index][0], self.parent_dir)
        return ""
    
    def _mark_group_processed(self, group_index: int, species: str = None, dest_files: list = None):
        """
        标记某组为已处理，同时记录分类详情（用于后续撤销）。
        
        参数：
            group_index: 组索引
            species: 物种名称（None=空拍）
            dest_files: 复制到的目标文件完整路径列表
        """
        if 0 <= group_index < len(self.groups) and self.groups[group_index]:
            rel_path = self._get_group_rel_path(group_index)
            self.processed_groups.add(rel_path)
            if dest_files is not None:
                self.class_history[rel_path] = {
                    'species': species or '空拍',
                    'dest_files': dest_files
                }
            self._save_progress()
    
    def _undo_group_copies(self, group_index: int) -> int:
        """
        撤销指定组的分类：删除之前复制的目标文件。
        
        参数：
            group_index: 组索引
        返回：
            成功删除的文件数量
        """
        rel_path = self._get_group_rel_path(group_index)
        if not rel_path or rel_path not in self.class_history:
            return 0
        
        dest_files = self.class_history[rel_path].get('dest_files', [])
        deleted_count = 0
        for dest_path in dest_files:
            try:
                if os.path.exists(dest_path):
                    os.remove(dest_path)
                    deleted_count += 1
            except OSError:
                pass  # 文件可能已被手动删除，静默跳过
        
        # 清理历史记录和已处理标记
        del self.class_history[rel_path]
        self.processed_groups.discard(rel_path)
        self._save_progress()
        
        return deleted_count
    
    # ==================== 组加载 ====================
    
    def _load_group(self, group_index: int):
        """
        加载指定索引的文件组。
        如果该组之前已处理，显示之前的分类信息，允许重新分类（自动撤销旧文件）。
        """
        if group_index < 0 or group_index >= len(self.groups):
            return
        
        # 停止旧视频
        self._stop_video()
        
        self.current_group_index = group_index
        self.current_group_files = self.groups[group_index]
        
        # 重置选中状态（默认全选，长度=实际文件数）
        self.selected_flags = [True] * len(self.current_group_files)
        
        # 检查该组是否已处理过
        rel_path = self._get_group_rel_path(group_index)
        is_processed = rel_path in self.processed_groups
        prev_species = ""
        if is_processed and rel_path in self.class_history:
            prev_species = self.class_history[rel_path].get('species', '')
        
        # 遍历4个面板位置（超过4个文件的部分不显示但参与分类）
        for panel_idx in range(4):
            panel = self._panels[panel_idx]
            
            if panel_idx < len(self.current_group_files):
                file_path = self.current_group_files[panel_idx]
                filename = os.path.basename(file_path)
                
                if panel_idx == 0 and is_video_file(filename):
                    # 左上角：视频文件 → 启动视频播放
                    panel.file_path = file_path
                    panel.name_label.config(text=f"🎬 {filename}")
                    self._load_video(file_path, panel)
                else:
                    # 显示为静态图片
                    panel.display_image(file_path)
            else:
                # 该位置无文件
                panel.display_placeholder()
        
        # 更新所有面板的选中状态
        self._update_all_panel_selections()
        
        # 更新UI信息（已处理的组显示黄色标记）
        if is_processed:
            self.label_group_info.config(
                text=f"📦 第 {group_index + 1}/{len(self.groups)} 组  ⚠ 已处理({prev_species})",
                fg='#FFB74D'
            )
            self.label_status.config(
                text=f"⚠ 该组已分类为「{prev_species}」。重新分类将自动删除旧文件。",
                fg='#FFB74D'
            )
        else:
            self.label_group_info.config(
                text=f"📦 第 {group_index + 1}/{len(self.groups)} 组",
                fg=COLOR_TEXT
            )
            self.label_status.config(text="", fg='#AAAAAA')
        
        # 选中提示（超过4个文件时特别标注）
        n_files = len(self.current_group_files)
        n_selected = sum(self.selected_flags)
        if n_files > 4:
            self.label_select_hint.config(
                text=f"已选 {n_selected}/{n_files} (界面仅显示前4个，+{n_files - 4}个未显示)"
            )
        else:
            self.label_select_hint.config(
                text=f"已选 {n_selected}/{n_files}"
            )
        
        # 更新导航按钮
        self.btn_prev.config(state=tk.NORMAL if group_index > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if group_index < len(self.groups) - 1 else tk.DISABLED)
        
        self._update_progress_bar()
        self._update_status()
    
    # ==================== 视频播放 ====================
    
    def _load_video(self, video_path: str, panel: MediaPanel):
        """
        加载视频文件并开始播放。
        尝试多种opencv后端以提高兼容性（特别是MOV/ProRes等格式）。
        
        参数：
            video_path: 视频文件路径
            panel: 用于显示视频的 MediaPanel（左上角）
        """
        # 释放旧视频
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        
        # 尝试多种后端打开视频（按优先级：FFMPEG → DSHOW → ANY）
        backends = [cv2.CAP_FFMPEG, cv2.CAP_DSHOW, cv2.CAP_ANY]
        opened = False
        for backend in backends:
            try:
                cap = cv2.VideoCapture(video_path, backend)
                if cap.isOpened():
                    self.video_cap = cap
                    opened = True
                    break
                else:
                    cap.release()
            except Exception:
                continue
        
        # 如果以上都失败，尝试默认方式 + Windows短路径名后备
        if not opened:
            self.video_cap = cv2.VideoCapture(video_path)
            if not self.video_cap.isOpened():
                try:
                    import ctypes
                    buf = ctypes.create_unicode_buffer(512)
                    ctypes.windll.kernel32.GetShortPathNameW(video_path, buf, 512)
                    short_path = buf.value
                    if short_path and short_path != video_path:
                        self.video_cap = cv2.VideoCapture(short_path)
                except Exception:
                    pass
        
        if not self.video_cap or not self.video_cap.isOpened():
            ext = os.path.splitext(video_path)[1].lower()
            panel.media_label.config(
                image='', text=f"⚠ 无法播放{ext}视频\n编码格式可能不支持\n(可点击查看截图)",
                fg='#FFB74D'
            )
            panel.name_label.config(text=f"❌ {os.path.basename(video_path)}")
            self.video_playing = False
            # 回退：尝试当作静态图片显示（某些"视频"文件可能是图片）
            try:
                panel.display_image(video_path)
            except Exception:
                pass
            return
        
        # 限制目标帧率：相机陷阱视频通常15-30fps，预览用20fps足够流畅
        fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 25
        # 目标20fps（50ms间隔），如果原视频帧率更低则用原帧率
        target_fps = min(fps, 20)
        self.video_frame_delay = max(25, int(1000 / target_fps))
        
        # 保存视频面板引用
        self.video_panel = panel
        # 缓存视频面板的显示尺寸（在_update_video_frame中更新）
        self._cached_video_dims = (0, 0)
        
        # 开始播放
        self.video_playing = True
        self._update_video_frame()
    
    def _update_video_frame(self):
        """
        定时更新视频帧（高度优化版本）。
        
        性能策略：
            1. 全部图像处理用cv2（BGR空间），避免PIL转换开销
            2. cv2.INTER_NEAREST 缩放（最快，预览场景几乎无差别）
            3. 只在最后一步转RGB + PhotoImage
            4. 目标帧率20fps（50ms间隔），剩余时间留给UI响应
            5. 缓存面板尺寸，避免每帧获取widget尺寸
            6. 跳帧：如果渲染跟不上，丢弃中间帧
        """
        if not self.video_playing or self.video_cap is None:
            return
        
        # --- 跳帧机制：读取直到最新帧 ---
        ret = True
        frame = None
        grab_count = 0
        while ret and grab_count < 5:  # 最多连读5帧防止死循环
            ret, f = self.video_cap.read()
            if ret:
                frame = f
                grab_count += 1
            else:
                break
        
        if frame is None:
            # 播放完毕，循环
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.video_cap.read()
            if not ret:
                self.video_playing = False
                return
        
        # --- 获取视频面板 ---
        panel = getattr(self, 'video_panel', None)
        if panel is None:
            panel = self._panels[0] if self._panels else None
            if panel is None:
                self.video_playing = False
                return
        
        # --- 获取/刷新缓存的面板显示尺寸 ---
        # 每30帧重新获取一次面板尺寸（适应窗口大小变化）
        if not hasattr(self, '_frame_count'):
            self._frame_count = 0
        self._frame_count += 1
        
        if self._frame_count % 30 == 0:
            self._cached_video_dims = panel._calc_display_size()
        new_w, new_h = self._cached_video_dims
        if new_w <= 0:
            new_w, new_h = panel._calc_display_size()
            self._cached_video_dims = (new_w, new_h)
        
        # --- 渲染帧 ---
        if new_w > 0 and new_h > 0:
            # 性能关键路径：cv2.resize(BGR→小图) → cv2.cvtColor(BGR→RGB) → Image.fromarray → PhotoImage
            # 用cv2.INTER_LINEAR缩放（速度与质量的最佳平衡点，比NEAREST清晰很多）
            frame_small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(frame_rgb)
            self.video_photo = ImageTk.PhotoImage(pil_img)
            panel.media_label.config(image=self.video_photo, text='')
        
        # --- 调度下一帧 ---
        self.video_after_id = self.root.after(self.video_frame_delay, self._update_video_frame)
    
    def _toggle_play_pause(self):
        """切换视频播放/暂停状态"""
        if self.video_cap is None:
            return
        self.video_playing = not self.video_playing
        if self.video_playing:
            self._update_video_frame()
        else:
            if self.video_after_id:
                self.root.after_cancel(self.video_after_id)
                self.video_after_id = None
    
    def _stop_video(self):
        """停止视频播放并释放资源"""
        self.video_playing = False
        if self.video_after_id:
            self.root.after_cancel(self.video_after_id)
            self.video_after_id = None
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        self.video_photo = None
        self.video_panel = None
    
    # ==================== 选中状态管理 ====================
    
    def _toggle_file_selection(self, index: int):
        """切换指定文件（面板）的选中状态"""
        if index < 0 or index >= len(self.current_group_files):
            return
        
        self.selected_flags[index] = not self.selected_flags[index]
        self._update_all_panel_selections()
        
        n_files = len(self.current_group_files)
        n_selected = sum(1 for i, flag in enumerate(self.selected_flags) if flag and i < n_files)
        if n_files > 4:
            self.label_select_hint.config(
                text=f"已选 {n_selected}/{n_files} (界面仅显示前4个，+{n_files - 4}个未显示)"
            )
        else:
            self.label_select_hint.config(
                text=f"已选 {n_selected}/{n_files}"
            )
    
    def _update_all_panel_selections(self):
        """同步所有面板的选中状态视觉样式"""
        for panel_idx in range(4):
            panel = self._panels[panel_idx]
            if panel_idx < len(self.current_group_files):
                panel.set_selected(self.selected_flags[panel_idx])
            else:
                panel.set_selected(False)
    
    def _open_fullscreen(self, panel_index: int):
        """
        打开全分辨率查看窗口。
        
        参数：
            panel_index: 面板索引（0=视频, 1/2/3=截图）
        """
        if panel_index < 0 or panel_index >= len(self.current_group_files):
            return
        
        file_path = self.current_group_files[panel_index]
        is_video = (panel_index == 0 and is_video_file(os.path.basename(file_path)))
        
        # 暂停主窗口视频（避免两个窗口同时播放）
        if self.video_playing:
            self._toggle_play_pause()
        
        # 创建并打开全分辨率查看器（模态窗口，阻塞直到关闭）
        viewer = FullScreenViewer(self.root, file_path, is_video=is_video)
        # 等待查看器窗口关闭
        self.root.wait_window(viewer.window)
        
        # 查看器关闭后恢复主窗口视频
        if not self.video_playing and is_video:
            self._toggle_play_pause()
    
    # ==================== 分类操作 ====================
    
    def _on_empty(self):
        """空拍按钮：全部文件→空拍文件夹"""
        if not self.current_group_files:
            return
        self._classify_files(target_species=None)
    
    def _on_species_click(self, species_name: str):
        """物种按钮：选中的→物种文件夹，未选中的→空拍文件夹"""
        if not self.current_group_files:
            return
        self._classify_files(target_species=species_name)
    
    def _on_new_species(self):
        """新物种按钮：弹出输入框"""
        if not self.current_group_files:
            return
        
        species_name = simpledialog.askstring(
            "新建物种分类",
            "请输入物种名称（如：牛、马、野猪...）：\n\n"
            "将自动在目标文件夹下创建对应的子文件夹。",
            parent=self.root
        )
        
        if not species_name or not species_name.strip():
            return
        
        species_name = species_name.strip()
        
        # 添加到物种列表并重建按钮
        if species_name not in self.species_list:
            self.species_list.append(species_name)
            self._rebuild_species_buttons()
        
        self._classify_files(target_species=species_name)
    
    def _classify_files(self, target_species: str = None):
        """
        执行文件复制操作。
        
        逻辑：
            - 如果该组之前已处理，先删除旧的目标文件（撤销），再重新分类
            - target_species=None → 全部文件复制到"空拍"文件夹
            - target_species=物种名 → 选中的→物种文件夹，未选中的→空拍文件夹
        
        所有操作都是复制（shutil.copy2），原始文件保留不动。
        """
        if not self.current_group_files or not self.parent_dir:
            return
        
        # ---- 撤销旧分类（如果该组之前已处理）----
        rel_path = self._get_group_rel_path()
        if rel_path and rel_path in self.processed_groups:
            undone = self._undo_group_copies(self.current_group_index)
            if undone > 0:
                self.label_status.config(
                    text=f"🗑 已删除旧分类的 {undone} 个文件，正在重新分类...",
                    fg='#FFB74D'
                )
                self.root.update_idletasks()  # 立即刷新UI
        
        # ---- 执行新的分类复制 ----
        empty_dir = os.path.join(self.parent_dir, "空拍")
        species_dir = os.path.join(self.parent_dir, target_species) if target_species else None
        
        # 确保目标文件夹存在
        os.makedirs(empty_dir, exist_ok=True)
        if species_dir:
            os.makedirs(species_dir, exist_ok=True)
        
        copied_species = 0
        copied_empty = 0
        errors = []
        dest_files_record = []  # 记录所有复制到的目标路径（用于后续撤销）
        
        for i, file_path in enumerate(self.current_group_files):
            # 确定目标文件夹
            if target_species is None:
                dest_dir = empty_dir  # 全部→空拍
            elif i < len(self.selected_flags) and self.selected_flags[i]:
                dest_dir = species_dir  # 选中→物种
            else:
                dest_dir = empty_dir  # 未选中→空拍
            
            filename = os.path.basename(file_path)
            dest_path = os.path.join(dest_dir, filename)
            
            try:
                # 如果目标已有同名文件（来自其他组的相同文件名），添加数字后缀
                if os.path.exists(dest_path):
                    base, ext = os.path.splitext(filename)
                    counter = 1
                    while os.path.exists(os.path.join(dest_dir, f"{base}_{counter}{ext}")):
                        counter += 1
                    dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                
                shutil.copy2(file_path, dest_path)
                dest_files_record.append(dest_path)  # 记录目标路径
                
                if dest_dir == species_dir:
                    copied_species += 1
                else:
                    copied_empty += 1
                    
            except Exception as e:
                errors.append(f"  {filename}: {e}")
        
        # 标记为已处理（带分类详情）
        self._mark_group_processed(
            self.current_group_index,
            species=target_species,
            dest_files=dest_files_record
        )
        
        # ---- CSV记录（所有分类均记录：空拍 + 物种）----
        self._write_csv_record(target_species if target_species else "空拍")
        
        # 状态栏反馈
        parts = []
        if target_species:
            parts.append(f"✅「{target_species}」{copied_species}个")
        if copied_empty > 0:
            parts.append(f"📭 空拍 {copied_empty}个")
        if errors:
            parts.append(f"⚠ 失败 {len(errors)}")
        
        self.label_status.config(
            text=" | ".join(parts),
            fg='#4CAF50' if not errors else '#FF9800'
        )
        # 恢复组信息标签颜色（之前可能被设为黄色警告色）
        self.label_group_info.config(
            text=f"📦 第 {self.current_group_index + 1}/{len(self.groups)} 组",
            fg=COLOR_TEXT
        )
        
        self._update_progress_bar()
        self._update_status()
        
        # 自动跳转下一组
        self.root.after(250, self._auto_advance)
    
    def _auto_advance(self):
        """分类完成后自动跳转到下一组"""
        if self.current_group_index + 1 < len(self.groups):
            self._load_group(self.current_group_index + 1)
        else:
            self.label_status.config(text="🎉 所有数据已处理完毕！", fg='#4CAF50')
            self.label_group_info.config(text="✨ 全部完成！")
    
    def _write_csv_record(self, species_name: str):
        """
        将非空拍分类记录写入CSV文件。
        
        CSV列：经度, 纬度, 海拔高度(m), 物种名, 拍摄时间, 点位名称
        
        参数：
            species_name: 物种名称
        """
        if not self.parent_dir:
            return
        
        # CSV文件路径：保存在目标父文件夹下
        csv_path = os.path.join(self.parent_dir, 'wildcam_records.csv')
        
        # ---- 从当前组文件中提取GPS和时间 ----
        gps_data = {'longitude': None, 'latitude': None, 'altitude': None, 'datetime': None}
        
        # 遍历当前组文件，优先从JPG图片中读取EXIF（图片通常有完整GPS数据）
        for file_path in self.current_group_files:
            ext = os.path.splitext(file_path)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                gps_data = extract_gps_from_file(file_path)
                if gps_data['latitude'] is not None or gps_data['datetime'] is not None:
                    break  # 成功读取到有效数据
        
        # 如果图片中没有GPS，再尝试视频文件
        if gps_data['latitude'] is None and gps_data['datetime'] is None:
            for file_path in self.current_group_files:
                if is_video_file(os.path.basename(file_path)):
                    gps_data = extract_gps_from_file(file_path)
                    if gps_data['latitude'] is not None or gps_data['datetime'] is not None:
                        break
        
        # ---- 准备CSV行数据 ----
        lon = f"{gps_data['longitude']:.6f}" if gps_data['longitude'] is not None else ""
        lat = f"{gps_data['latitude']:.6f}" if gps_data['latitude'] is not None else ""
        alt = f"{gps_data['altitude']:.1f}" if gps_data['altitude'] is not None else ""
        dt_str = gps_data['datetime'].strftime('%Y-%m-%d %H:%M:%S') if gps_data['datetime'] else ""
        point_name = os.path.basename(self.source_dir) if self.source_dir else ""
        
        row = [lon, lat, alt, species_name, dt_str, point_name]
        
        # ---- 写入CSV（追加模式）----
        try:
            file_exists = os.path.exists(csv_path)
            with open(csv_path, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 新文件写表头
                if not file_exists or os.path.getsize(csv_path) == 0:
                    writer.writerow(['经度', '纬度', '海拔高度(m)', '物种名', '拍摄时间', '点位名称'])
                writer.writerow(row)
        except IOError as e:
            print(f"警告：无法写入CSV记录 - {e}")
    
    # ==================== 物种按钮管理 ====================
    
    def _rebuild_species_buttons(self):
        """重建物种按钮（当物种列表变化时）"""
        # 清除旧按钮
        for widget in self.species_frame.winfo_children():
            widget.destroy()
        self.species_buttons.clear()
        
        if not self.species_list:
            lbl = tk.Label(
                self.species_frame, text="(暂无)", font=("微软雅黑", 10),
                bg='#1A1A1A', fg=COLOR_TEXT_DIM
            )
            lbl.pack(side=tk.LEFT, padx=4)
            return
        
        # 物种emoji图标池
        icons = ["🐾", "🦌", "🐗", "🐻", "🐺", "🦊", "🐵", "🐮", "🐴", "🐑",
                 "🐰", "🦃", "🦅", "🦉", "🐍", "🦎", "🐢", "🦔", "🐿", "🦡"]
        
        for i, name in enumerate(self.species_list):
            key_label = f" [{KEY_SPECIES_KEYS[i].upper()}]" if i < len(KEY_SPECIES_KEYS) else ""
            icon = icons[i % len(icons)]
            
            btn = tk.Button(
                self.species_frame,
                text=f"{icon} {name}{key_label}",
                font=("微软雅黑", 11),
                bg=COLOR_BUTTON_SPECIES, fg='white',
                activebackground='#43A047',
                relief=tk.FLAT, cursor='hand2',
                padx=12, pady=7,
                command=lambda n=name: self._on_species_click(n)
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.species_buttons[name] = btn
    
    # ==================== 导航 ====================
    
    def _prev_group(self):
        """跳转上一组"""
        if self.current_group_index > 0:
            self._load_group(self.current_group_index - 1)
    
    def _next_group(self):
        """跳转下一组"""
        if self.current_group_index + 1 < len(self.groups):
            self._load_group(self.current_group_index + 1)
    
    def _jump_to_unprocessed(self):
        """跳转到第一个未处理的组"""
        for i in range(len(self.groups)):
            rel = self._get_group_rel_path(i)
            if rel not in self.processed_groups:
                if i != self.current_group_index:
                    self._load_group(i)
                    self.label_status.config(
                        text=f"⏭ 已跳至第 {i + 1} 组（首个未处理）",
                        fg='#4CAF50'
                    )
                else:
                    self.label_status.config(
                        text="✅ 当前已是第一个未处理组",
                        fg='#4CAF50'
                    )
                return
        # 全部处理完毕
        self.label_status.config(text="🎉 所有组已全部处理完毕！", fg='#4CAF50')
    
    # ==================== 状态更新 ====================
    
    def _update_progress_bar(self):
        """更新进度条"""
        if not self.groups:
            return
        
        self.progress_canvas.delete("all")
        canvas_w = self.progress_canvas.winfo_width()
        if canvas_w < 10:
            canvas_w = 1800
        
        total = len(self.groups)
        processed = len(self.processed_groups)
        
        # 背景
        self.progress_canvas.create_rectangle(0, 0, canvas_w, 5, fill='#333333', outline='')
        # 进度
        if total > 0:
            ratio = min(processed / total, 1.0)
            self.progress_canvas.create_rectangle(
                0, 0, int(canvas_w * ratio), 5,
                fill=COLOR_PROGRESS, outline=''
            )
        
        self.label_count.config(text=f"已处理: {processed}/{total} 组")
    
    def _update_status(self):
        """更新状态栏"""
        if not self.groups:
            return
        remaining = len(self.groups) - len(self.processed_groups)
        if remaining > 0:
            self.label_status.config(text=f"📋 剩余 {remaining} 组待处理", fg='#AAAAAA')
        else:
            self.label_status.config(text="🎉 全部完成！", fg='#4CAF50')
    
    # ==================== 窗口事件 ====================
    
    def _on_close(self):
        """关闭窗口清理"""
        self._stop_video()
        self.root.destroy()
    
    def run(self):
        """启动应用主循环"""
        # 窗口大小变化时重新渲染（带防抖）
        def on_configure(event):
            if event.widget == self.root:
                if self._resize_after_id:
                    self.root.after_cancel(self._resize_after_id)
                self._resize_after_id = self.root.after(800, self._reload_on_resize)
        
        # resize防抖延迟800ms（之前400ms，现在更保守以减少不必要的重渲染）
        self.root.bind('<Configure>', on_configure)
        self.root.mainloop()
    
    def _reload_on_resize(self):
        """
        窗口大小变化后刷新媒体显示（不重启视频，只重新缩放静态截图）。
        视频会在下一帧自动适配新尺寸（通过_cached_video_dims刷新）。
        """
        if self.current_group_index < 0 or not self._panels_ready:
            self._update_progress_bar()
            return
        # 强制刷新视频面板尺寸缓存（下一帧即生效）
        self._cached_video_dims = (0, 0)
        # 只重新缩放3个静态截图面板（索引1-3）
        for panel_idx in range(1, min(4, len(self.current_group_files))):
            panel = self._panels[panel_idx]
            if panel.file_path:
                try:
                    pil_img = Image.open(panel.file_path)
                    new_w, new_h = panel._calc_display_size()
                    if new_w > 0:
                        pil_resized = pil_img.resize((new_w, new_h), Image.LANCZOS)
                        photo = ImageTk.PhotoImage(pil_resized)
                        # 保持引用
                        if not hasattr(self, '_shot_resize_photos'):
                            self._shot_resize_photos = [None, None, None]
                        self._shot_resize_photos[panel_idx - 1] = photo
                        panel.media_label.config(image=photo, text='')
                        panel._photo = photo
                except Exception:
                    pass
        self._update_progress_bar()


# ==================== 程序入口 ====================

def main():
    """主入口：支持命令行参数指定源文件夹"""
    source_dir = None
    if len(sys.argv) > 1:
        arg_path = sys.argv[1]
        if os.path.isdir(arg_path):
            source_dir = arg_path
        else:
            print(f"警告：指定的路径不存在 - {arg_path}")
    
    app = WildCamSorter(source_dir=source_dir)
    app.run()


if __name__ == '__main__':
    main()
