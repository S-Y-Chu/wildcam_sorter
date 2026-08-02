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
import logging
import traceback
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler

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
            highlightthickness=1,      # 细边框（减少黑边）
            highlightbackground=COLOR_SELECTED_BORDER  # 默认绿色（选中）
        )
        
        # 面板标题（顶部，显示标题+文件名，节省一行空间给图片）
        self.title_label = tk.Label(
            self.frame,
            text=label_text,
            font=("微软雅黑", 9, "bold"),
            bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT,
            anchor=tk.W
        )
        self.title_label.pack(side=tk.TOP, fill=tk.X, pady=(1, 0))
        
        # 媒体显示标签（占据主要空间，图片顶部对齐向下延伸）
        self.media_label = tk.Label(
            self.frame,
            bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT_DIM,
            text="等待加载...",
            font=("微软雅黑", 12),
            anchor='n'  # 图片顶部对齐：上边界不动，下边界随高度下移
        )
        self.media_label.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        
        # 文件名标签：不再单独占一行，文件名合并进标题行
        self.name_label = tk.Label(
            self.frame,
            text="",
            font=("微软雅黑", 7),
            bg=COLOR_PANEL_BG,
            fg=COLOR_TEXT_DIM,
            anchor=tk.W
        )
        # 不 pack，节省高度给图片
        
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
    
    def display_image(self, image_path: str, retry: int = 0):
        """
        显示静态图片，按3:2比例缩放后居中显示。
        如果面板尚未渲染导致尺寸无效，自动重试最多3次。
        
        参数：
            image_path: 图片文件路径
            retry: 当前重试次数（内部使用）
        """
        self.file_path = image_path
        # 文件名合并到标题行显示
        self.title_label.config(text=f"{self.label_text} | {os.path.basename(image_path)}")
        
        try:
            pil_img = Image.open(image_path)
            photo = self._resize_and_center(pil_img)
            if photo:
                self._photo = photo
                self.media_label.config(image=photo, text='')
            elif retry < 3:
                # 面板尚未渲染完成，延迟后重试
                self.media_label.config(image='', text="")
                self.frame.after(150, lambda: self.display_image(image_path, retry + 1))
            else:
                self.media_label.config(image='', text="等待渲染...")
        except Exception as e:
            self.media_label.config(image='', text=f"⚠ 加载失败\n{os.path.basename(image_path)}")
            self.title_label.config(text=f"{self.label_text} | ❌ {e}")
    
    def display_placeholder(self, text: str = "(无文件)"):
        """显示占位文本（当没有对应文件时）"""
        self.file_path = None
        self._photo = None
        self.media_label.config(image='', text=text)
        self.title_label.config(text=self.label_text)
        self.set_selected(False)
    
    def _calc_display_size(self):
        """
        计算当前面板内媒体的最佳显示尺寸（保持3:2比例），返回 (宽, 高) 或 (0,0)。
        基于 frame 尺寸减去标题栏估算（文件名已合并进标题，不占高度）。
        """
        panel_w = self.frame.winfo_width()
        panel_h = self.frame.winfo_height()
        if panel_w <= 10:
            panel_w = self.frame.winfo_reqwidth()
        if panel_h <= 30:
            panel_h = self.frame.winfo_reqheight()
        if panel_w <= 20 or panel_h <= 40:
            return (0, 0)
        # 仅扣除极小标题空间（~10px），其余全部让给图片：
        # 图片高度≈面板高度，底部必然贴满，无黑边
        available_w = panel_w - 4
        available_h = panel_h - 10
        # 如果迷你标签栏可见（place），再扣除其高度
        try:
            self.mini_frame.place_info()
            available_h -= 55
        except (tk.TclError, AttributeError):
            pass
        if available_w <= 0 or available_h <= 0:
            return (0, 0)
        # 始终高度优先（保持3:2比例），宽度超出部分由Label裁剪：
        # 保证图片上下边界完全贴满，底部无黑边
        # +5px 溢出保险，确保贴满
        new_h = available_h + 5
        new_w = int(new_h * MEDIA_ASPECT_RATIO)
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
    
    # ==================== 迷你操作区（框内独立类别选择）====================
    
    def setup_mini_ops(self, species_list: list, on_select: callable, on_multi: callable):
        """
        创建迷你物种按钮栏（常驻显示，给照片打标签用）。
        
        逻辑：
            - 迷你栏的按钮只是给当前照片「打标签」（选择类别）
            - 真正复制分类由下方主操作区按钮触发
            - 主分类时：有标签的照片按标签去对应文件夹，
              没有标签的照片跟随主操作区选定的类别
        
        参数：
            species_list: 物种名称列表
            on_select: 标签更新回调(file_index, species_set)
            on_multi: 保留参数（未使用）
        """
        # 迷你操作区容器（用place定位，默认隐藏）
        self.mini_frame = tk.Frame(self.frame, bg=COLOR_PANEL_BG, height=55)
        self.mini_frame.pack_propagate(False)
        # 不在 __init__ 中 pack，由 show/hide 用 place 控制显示
        # 第一行：物种按钮
        self.mini_species_row = tk.Frame(self.mini_frame, bg=COLOR_PANEL_BG)
        self.mini_species_row.pack(fill=tk.X)
        # 第二行：功能按钮（多类别/完成分类/刷新）
        self.mini_func_row = tk.Frame(self.mini_frame, bg=COLOR_PANEL_BG)
        self.mini_func_row.pack(fill=tk.X)
        
        self.mini_buttons = {}
        self.mini_multi_on = False
        self.mini_selected = set()       # 多类模式下临时选择
        self._mini_on_select = on_select
        self._mini_on_multi = on_multi
        
        # 创建物种按钮（小字体，紧凑）
        for i, name in enumerate(species_list[:8]):  # 每行最多8个
            btn = tk.Button(
                self.mini_species_row,
                text=name,
                font=("微软雅黑", 8),
                bg=COLOR_BUTTON_SPECIES, fg='white',
                activebackground='#43A047',
                relief=tk.FLAT, cursor='hand2',
                padx=3, pady=0,
                command=lambda n=name: self._on_mini_species(n)
            )
            btn.pack(side=tk.LEFT, padx=1, pady=1)
            self.mini_buttons[name] = btn
        
        # 迷你多类别按钮（进入多类模式后变「完成分类」）
        self.mini_multi_btn = tk.Button(
            self.mini_func_row,
            text="📋 多类别", font=("微软雅黑", 8),
            bg='#6A1B9A', fg='white',
            relief=tk.FLAT, cursor='hand2',
            padx=4, pady=0,
            command=self._on_mini_multi
        )
        self.mini_multi_btn.pack(side=tk.LEFT, padx=1, pady=1)
        
        # 迷你刷新按钮
        self.mini_refresh_btn = tk.Button(
            self.mini_func_row,
            text="🔄", font=("微软雅黑", 8),
            bg='#455A64', fg='white',
            relief=tk.FLAT, cursor='hand2',
            padx=4, pady=0,
            command=self._on_mini_refresh
        )
        self.mini_refresh_btn.pack(side=tk.LEFT, padx=1, pady=1)
        
        # 标签状态标签（显示已选标签，如「已标:牛」）
        self.mini_label_text = tk.Label(
            self.mini_func_row, text="", font=("微软雅黑", 8),
            bg=COLOR_PANEL_BG, fg='#FFB74D'
        )
        self.mini_label_text.pack(side=tk.LEFT, padx=4, pady=1)
    
    def _on_mini_refresh(self):
        """刷新迷你按钮：从主界面重新获取物种列表"""
        if hasattr(self, 'on_refresh_callback') and self.on_refresh_callback:
            self.on_refresh_callback(self.index)
    
    def set_refresh_callback(self, callback):
        """设置刷新回调（从主界面获取最新物种列表）"""
        self.on_refresh_callback = callback
    
    def _on_mini_species(self, name: str):
        """迷你物种按钮点击：单选直接打标签，多类模式toggle选择"""
        if self.mini_multi_on:
            # 多类模式：toggle 临时选择
            if name in self.mini_selected:
                self.mini_selected.discard(name)
            else:
                self.mini_selected.add(name)
            self._update_mini_buttons()
        else:
            # 单选模式：立即打上标签（只这一个）
            self.mini_selected = {name}
            self._update_mini_buttons()
            self._notify_label()
    
    def _on_mini_multi(self):
        """迷你多类别按钮：进入多类模式 / 完成分类提交标签"""
        if self.mini_multi_on:
            # 完成分类：提交标签，迷你栏保持显示
            self.mini_multi_on = False
            self.mini_multi_btn.config(text="📋 多类别", bg='#6A1B9A')
            self._notify_label()
        else:
            # 进入多类模式
            self.mini_multi_on = True
            self.mini_multi_btn.config(text="✅ 完成分类", bg='#E65100')
            self.mini_selected.clear()
            self._update_mini_buttons()
    
    def _notify_label(self):
        """通知主界面当前照片的标签"""
        if self._mini_on_select:
            self._mini_on_select(self.index, set(self.mini_selected))
        # 更新标签状态文字
        if self.mini_selected:
            self.mini_label_text.config(text=f"已标:{'、'.join(list(self.mini_selected)[:3])}")
        else:
            self.mini_label_text.config(text="")
    
    def _update_mini_buttons(self):
        """更新迷你按钮外观（已选标签变橙色）"""
        for name, btn in self.mini_buttons.items():
            if name in self.mini_selected:
                btn.config(bg='#FF6F00')
            else:
                btn.config(bg=COLOR_BUTTON_SPECIES)
    
    def clear_mini_selection(self):
        """清空该照片的标签并隐藏迷你栏（组切换/分类完成时调用）"""
        self.mini_selected.clear()
        self.mini_multi_on = False
        self.mini_multi_btn.config(text="📋 多类别", bg='#6A1B9A')
        self.mini_label_text.config(text="")
        self._update_mini_buttons()
        self.hide_mini_ops()
    
    def show_mini_ops(self):
        """显示迷你标签栏（place定位，绝对可靠）"""
        if not hasattr(self, 'mini_frame'):
            return
        self.mini_frame.place(relx=0, rely=1.0, anchor='sw', relwidth=1.0, y=-2)
        self.mini_frame.lift()
    
    def hide_mini_ops(self):
        """隐藏迷你标签栏"""
        if not hasattr(self, 'mini_frame'):
            return
        self.mini_frame.place_forget()
    
    def set_label(self, species_set: set):
        """从外部设置标签（如重新加载组时恢复）"""
        self.mini_selected = set(species_set)
        self.mini_multi_on = False
        self.mini_multi_btn.config(text="📋 多类别", bg='#6A1B9A')
        self._update_mini_buttons()
        if self.mini_selected:
            self.show_mini_ops()
        self._notify_label()
    
    def rebuild_mini_buttons(self, species_list: list):
        """重建迷你物种按钮（物种列表变化时），保留已有标签"""
        # 记住已有标签
        old_label = set(self.mini_selected)
        for btn in self.mini_buttons.values():
            btn.destroy()
        self.mini_buttons.clear()
        for i, name in enumerate(species_list[:8]):
            btn = tk.Button(
                self.mini_species_row,
                text=name,
                font=("微软雅黑", 8),
                bg=COLOR_BUTTON_SPECIES, fg='white',
                activebackground='#43A047',
                relief=tk.FLAT, cursor='hand2',
                padx=3, pady=0,
                command=lambda n=name: self._on_mini_species(n)
            )
            btn.pack(side=tk.LEFT, padx=1, pady=1)
            self.mini_buttons[name] = btn
        # 恢复标签（只保留仍存在的物种）
        self.mini_selected = old_label & set(species_list)
        self._update_mini_buttons()
        self._notify_label()


# ==================== 全分辨率查看器 ====================

class PathSelectDialog:
    """
    启动路径选择对话框：在一个窗口内同时选择输入文件夹和输出文件夹。
    
    布局：
        ┌──────────────────────────────────────────┐
        │     请选择照片输入和分类输出路径            │
        │  照片输入路径 [输入框.........] [📁按钮]   │
        │  照片输出路径 [输入框.........] [📁按钮]   │
        │              [确定]  [取消]               │
        └──────────────────────────────────────────┘
    输入框支持手打路径，也可以点文件夹按钮浏览选择。
    """
    
    def __init__(self, parent, initial_input: str = ""):
        """
        参数：
            parent: 父窗口
            initial_input: 初始预填的输入路径（可选）
        """
        self.result = None  # (input_path, output_path) 或 None（取消）
        
        self.window = tk.Toplevel(parent)
        self.window.title("路径选择")
        self.window.configure(bg='#1E1E1E')
        self.window.resizable(False, False)
        self.window.transient(parent)  # 关联父窗口
        
        # 模态：阻塞父窗口交互
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # ---- 标题 ----
        tk.Label(
            self.window, text="请选择照片输入和分类输出路径",
            font=("微软雅黑", 12, "bold"),
            bg='#1E1E1E', fg='#E0E0E0'
        ).pack(pady=(15, 10))
        
        # ---- 输入路径行 ----
        input_row = tk.Frame(self.window, bg='#1E1E1E')
        input_row.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(input_row, text="照片输入路径", font=("微软雅黑", 10),
                 bg='#1E1E1E', fg='#E0E0E0', width=10, anchor='w'
                 ).pack(side=tk.LEFT)
        self.entry_input = tk.Entry(input_row, font=("微软雅黑", 10), width=38)
        self.entry_input.pack(side=tk.LEFT, padx=5, ipady=3)
        if initial_input:
            self.entry_input.insert(0, initial_input)
        tk.Button(input_row, text="📁", font=("微软雅黑", 10),
                  bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                  command=lambda: self._browse(self.entry_input)
                  ).pack(side=tk.LEFT, padx=2)
        
        # ---- 输出路径行 ----
        output_row = tk.Frame(self.window, bg='#1E1E1E')
        output_row.pack(fill=tk.X, padx=20, pady=5)
        tk.Label(output_row, text="照片输出路径", font=("微软雅黑", 10),
                 bg='#1E1E1E', fg='#E0E0E0', width=10, anchor='w'
                 ).pack(side=tk.LEFT)
        self.entry_output = tk.Entry(output_row, font=("微软雅黑", 10), width=38)
        self.entry_output.pack(side=tk.LEFT, padx=5, ipady=3)
        tk.Button(output_row, text="📁", font=("微软雅黑", 10),
                  bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                  command=lambda: self._browse(self.entry_output)
                  ).pack(side=tk.LEFT, padx=2)
        
        # ---- 提示文字 ----
        tk.Label(
            self.window, text="提示：输出文件夹不存在时会自动创建",
            font=("微软雅黑", 8), bg='#1E1E1E', fg='#888888'
        ).pack(pady=(2, 8))
        
        # ---- 按钮行 ----
        btn_row = tk.Frame(self.window, bg='#1E1E1E')
        btn_row.pack(pady=(5, 15))
        tk.Button(btn_row, text="确定", font=("微软雅黑", 10),
                  bg='#2E7D32', fg='white', relief=tk.FLAT, cursor='hand2',
                  padx=20, pady=4, command=self._on_ok
                  ).pack(side=tk.LEFT, padx=10)
        tk.Button(btn_row, text="取消", font=("微软雅黑", 10),
                  bg='#555555', fg='white', relief=tk.FLAT, cursor='hand2',
                  padx=20, pady=4, command=self._on_cancel
                  ).pack(side=tk.LEFT, padx=10)
        
        # 回车=确定，ESC=取消
        self.window.bind('<Return>', lambda e: self._on_ok())
        self.window.bind('<Escape>', lambda e: self._on_cancel())
        
        # 居中显示
        self.window.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.window.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.window.winfo_height()) // 3
        self.window.geometry(f"+{max(x, 0)}+{max(y, 0)}")
    
    def _browse(self, entry: tk.Entry):
        """浏览按钮：弹出文件夹选择并填入输入框"""
        initial = entry.get().strip() or os.path.expanduser("~")
        folder = filedialog.askdirectory(
            title="选择文件夹",
            initialdir=initial if os.path.isdir(initial) else os.path.expanduser("~")
        )
        if folder:
            entry.delete(0, tk.END)
            entry.insert(0, folder)
    
    def _on_ok(self):
        """确定按钮：校验路径并返回结果"""
        in_path = self.entry_input.get().strip().strip('"')
        out_path = self.entry_output.get().strip().strip('"')
        
        # 输入路径必须存在
        if not in_path:
            messagebox.showwarning("路径错误", "请输入照片输入路径", parent=self.window)
            return
        if not os.path.isdir(in_path):
            messagebox.showwarning(
                "路径错误",
                f"输入文件夹不存在：\n{in_path}",
                parent=self.window
            )
            return
        
        # 输出路径：不存在则自动创建
        if not out_path:
            messagebox.showwarning("路径错误", "请输入照片输出路径", parent=self.window)
            return
        try:
            os.makedirs(out_path, exist_ok=True)
        except OSError as e:
            messagebox.showerror(
                "路径错误",
                f"无法创建输出文件夹：\n{out_path}\n\n{e}",
                parent=self.window
            )
            return
        
        self.result = (in_path, out_path)
        self.window.destroy()
    
    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.window.destroy()


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
        btn_close = tk.Button(toolbar, text="✕ 返回", font=("微软雅黑", 9),
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
        # 键盘快捷键已全部移除（纯鼠标操作）：播放/暂停用底部按钮
        
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
        self.source_dir = None            # 源文件夹路径（输入）
        self.target_dir = None            # 目标文件夹路径（输出，默认为源文件夹的父目录）
        self.parent_dir = None            # 源文件夹的父目录（用于进度追踪标识）
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
        
        # ===== 日志系统 =====
        self.logger = None
        self._setup_logging()
        
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
            # 命令行传了路径：预填输入框，仍弹对话框选择输出
            self._pending_input = source_dir
        else:
            self._pending_input = ""
        # 启动即弹出输入/输出路径选择对话框
        self.root.after(200, self._show_path_dialog)
    
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
        
        # 目标文件夹按钮
        self.btn_target = tk.Button(
            toolbar, text="📤 输出到", font=("微软雅黑", 10),
            bg='#555555', fg='white', activebackground='#777777',
            relief=tk.FLAT, cursor='hand2',
            command=self._prompt_target_folder, padx=10, pady=3
        )
        self.btn_target.pack(side=tk.LEFT, padx=3, pady=3)
        
        # 目标文件夹路径显示
        self.label_target = tk.Label(
            toolbar, text="", font=("微软雅黑", 10),
            bg=COLOR_TOOLBAR, fg='#888888', anchor=tk.W
        )
        self.label_target.pack(side=tk.LEFT, padx=3, pady=3)
        
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
            panel.frame.grid(row=row, column=col, sticky='nsew', padx=1, pady=1)
            panel.set_toggle_callback(self._toggle_file_selection)
            panel.set_fullscreen_callback(self._open_fullscreen)
            panel.set_refresh_callback(self._on_panel_refresh)
            # 初始化迷你操作区（但隐藏）
            panel.setup_mini_ops(self.species_list, self._on_panel_species_select, None)
            self._panels.append(panel)
        
        # 每文件独立选择记录 {file_index: set(species_names)}
        self.per_file_species = {}
        
        # 溢出文件行（当组内文件>4时显示）
        self.display_frame.grid_rowconfigure(2, weight=0)  # 溢出行的权重为0（默认隐藏）
        self.overflow_frame = tk.Frame(self.display_frame, bg=COLOR_BG)
        self.overflow_panels = []  # 额外的MediaPanel列表
    
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
            left_frame, text="🟦  空拍", font=("微软雅黑", 11, "bold"),
            bg=COLOR_BUTTON_EMPTY, fg='white', activebackground='#78909C',
            relief=tk.FLAT, cursor='hand2', padx=14, pady=8,
            command=self._on_empty
        )
        self.btn_empty.pack(side=tk.LEFT, padx=4)
        
        # 物种按钮容器
        self.species_frame = tk.Frame(left_frame, bg='#1A1A1A')
        self.species_frame.pack(side=tk.LEFT, padx=4)
        
        # 多类别切换按钮
        self.multi_mode = False
        self.multi_selected = set()  # 多类模式下选中的物种集合
        self.btn_multi = tk.Button(
            left_frame, text="📋 多类别", font=("微软雅黑", 11, "bold"),
            bg='#6A1B9A', fg='white', activebackground='#9C27B0',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=8,
            command=self._toggle_multi_mode
        )
        self.btn_multi.pack(side=tk.LEFT, padx=4)
        
        # 新物种按钮
        self.btn_new = tk.Button(
            left_frame, text="🟧  新物种", font=("微软雅黑", 11, "bold"),
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
            right_frame, text="◀ 上一组", font=("微软雅黑", 10),
            bg=COLOR_BUTTON_NAV, fg='white', activebackground='#616161',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._prev_group
        )
        self.btn_prev.pack(side=tk.LEFT, padx=3)
        
        # 下一组
        self.btn_next = tk.Button(
            right_frame, text="下一组 ▶", font=("微软雅黑", 10),
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
        """键盘快捷键已全部移除，所有操作由鼠标点击完成"""
        pass
    
    # ==================== 数据初始化 ====================
    
    def _init_from_source(self, source_dir: str):
        """从输入文件夹初始化数据（只扫描分组，不依赖输出目录）"""
        self.source_dir = os.path.abspath(source_dir)
        self.parent_dir = os.path.dirname(self.source_dir)
        # 注意：不默认设置 target_dir，输出目录必须由用户选择
        
        self._log(f"打开文件夹: {self.source_dir}")
        
        self.label_folder.config(text=f"📁 {self.source_dir}")
        self.label_target.config(text=f"📤 输出到: (未选择)")
        
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
        
        # 输出目录尚未确定，等用户选择后由 _finalize_setup 完成剩余初始化
        self.current_group_index = -1
        self._panels_ready = False
    
    def _finalize_setup(self):
        """输出目录确定后执行完整初始化（物种扫描、进度、预分检测、加载首组）"""
        # 扫描已有物种文件夹（只来自输出目录）
        self._scan_species_folders()
        
        # 加载进度记录
        self._load_progress()
        
        # ---- 检测已手动分好的照片（从输出文件夹中识别）----
        self._detect_presorted_files()
        
        # 找到第一个未处理的组
        first_unprocessed = 0
        skipped_count = 0
        for i in range(len(self.groups)):
            rel = self._get_group_rel_path(i)
            if rel not in self.processed_groups:
                first_unprocessed = i
                break
            skipped_count += 1
        
        # 延迟加载首组：等待布局完成后渲染
        self.root.after(400, lambda: self._on_panels_ready(first_unprocessed, skipped_count))
    
    def _show_path_dialog(self):
        """
        弹出路径选择对话框：一个窗口内同时选择输入和输出文件夹。
        确定后完成初始化，取消则保持空状态（可用工具栏按钮随时开始）。
        """
        dlg = PathSelectDialog(self.root, initial_input=self._pending_input)
        self.root.wait_window(dlg.window)  # 阻塞直到对话框关闭
        
        if dlg.result:
            in_path, out_path = dlg.result
            self._init_from_source(in_path)
            self.target_dir = out_path
            self.label_target.config(text=f"📤 输出到: {self.target_dir}")
            self._log(f"设置输出目录: {self.target_dir}")
            # 完成初始化（物种扫描、进度、预分检测、加载首组）
            self._finalize_setup()
        else:
            # 用户取消：保持空状态，提示可用工具栏按钮
            self.label_status.config(
                text="未选择路径，可点工具栏「📂 打开文件夹」随时开始",
                fg='#FFB74D'
            )
    
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
        """弹出输入文件夹选择对话框（切换输入）"""
        initial = self.source_dir if self.source_dir else os.path.expanduser("~")
        folder = filedialog.askdirectory(title="选择包含野外相机数据的文件夹", initialdir=initial)
        if folder:
            self._stop_video()
            # 清空旧状态
            self.processed_groups = set()
            self.class_history = {}
            self._init_from_source(folder)
            # 保留已选的输出目录（如果有），否则要求选择
            if self.target_dir:
                self._finalize_setup()
            else:
                self.root.after(200, self._prompt_target_folder)
    
    def _prompt_target_folder(self):
        """弹出输出文件夹选择对话框（分类结果输出位置）"""
        initial = self.target_dir if self.target_dir else os.path.expanduser("~")
        folder = filedialog.askdirectory(
            title="选择分类结果的输出文件夹",
            initialdir=initial
        )
        if folder:
            self.target_dir = os.path.abspath(folder)
            self._log(f"设置输出目录: {self.target_dir}")
            self.label_target.config(text=f"📤 输出到: {self.target_dir}")
            # 输出目录确定后完成初始化
            self._finalize_setup()
    
    def _scan_species_folders(self):
        """扫描输出文件夹中已有的物种文件夹并重建按钮（类别只来自输出目录）"""
        if not self.target_dir:
            return
        # 清空旧物种列表，只保留输出目录中实际存在的类别
        self.species_list = []
        existing = find_existing_species_folders(self.target_dir, self.source_dir)
        for sp in existing:
            self.species_list.append(sp)
        # 退出多类模式（物种列表变了，旧选择可能失效）
        if self.multi_mode:
            self.multi_mode = False
            self.multi_selected.clear()
            self.btn_multi.config(text="📋 多类别", bg='#6A1B9A')
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
    
    def _detect_presorted_files(self):
        """
        扫描目标文件夹中已有的物种子文件夹，检测哪些组已经被手动分好。
        如果一组的所有文件都已存在于目标文件夹的某个子目录中，自动标记为已处理。
        """
        if not self.target_dir or not os.path.isdir(self.target_dir):
            return
        
        # 收集目标文件夹中所有已存在的文件名 → 所在子文件夹
        existing_files = {}  # {filename: subfolder_name}
        source_basename = os.path.basename(self.source_dir) if self.source_dir else ""
        
        for entry in os.listdir(self.target_dir):
            sub_path = os.path.join(self.target_dir, entry)
            if os.path.isdir(sub_path) and entry != source_basename and not entry.startswith('.'):
                try:
                    for fname in os.listdir(sub_path):
                        full = os.path.join(sub_path, fname)
                        if os.path.isfile(full) and is_media_file(fname):
                            existing_files[fname] = entry
                except OSError:
                    pass
        
        if not existing_files:
            return
        
        # 检查每个组：如果所有源文件都已存在于目标文件夹中，标记为已处理
        newly_found = 0
        for group_idx, group in enumerate(self.groups):
            rel_path = self._get_group_rel_path(group_idx)
            if rel_path and rel_path in self.processed_groups:
                continue  # 已标记
            
            # 检查组内所有文件是否都已存在于目标文件夹中
            all_found = True
            for file_path in group:
                fname = os.path.basename(file_path)
                if fname not in existing_files:
                    all_found = False
                    break
            
            if all_found and group:
                # 自动标记为已处理
                dest_files = []
                species = None
                for file_path in group:
                    fname = os.path.basename(file_path)
                    sub = existing_files.get(fname, '')
                    if sub:
                        dest_files.append(os.path.join(self.target_dir, sub, fname))
                        if species is None:
                            species = sub
                
                self.processed_groups.add(rel_path)
                if dest_files:
                    self.class_history[rel_path] = {
                        'species': species or '未知',
                        'dest_files': dest_files
                    }
                newly_found += 1
        
        if newly_found > 0:
            self._save_progress()
            self._log(f"检测到 {newly_found} 组已手动分好，自动跳过")
            self.label_status.config(
                text=f"🔍 检测到 {newly_found} 组已手动分好，自动跳过",
                fg='#4CAF50'
            )
    
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
        self._log(f"撤销分类: 第{group_index+1}组, 删除{deleted_count}个文件")
        
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
        self.per_file_species.clear()  # 清除上组的独立选择
        
        # 重置所有面板的迷你标签（进入新组时清空）
        for panel in self._panels:
            if hasattr(panel, 'clear_mini_selection'):
                panel.clear_mini_selection()
        for panel in self.overflow_panels:
            if hasattr(panel, 'clear_mini_selection'):
                panel.clear_mini_selection()
        
        # 重置主操作区多类模式
        if self.multi_mode:
            self.multi_mode = False
            self.multi_selected.clear()
            self.btn_multi.config(text="📋 多类别", bg='#6A1B9A')
            self._update_multi_buttons()
        
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
                    panel.file_path = file_path
                    panel.title_label.config(text=f"{panel.label_text} | 🎬 {filename}")
                    self._load_video(file_path, panel)
                else:
                    panel.display_image(file_path)
            else:
                panel.display_placeholder()
        
        # ---- 溢出文件处理（>4个文件时）----
        n_extra = len(self.current_group_files) - 4
        # 清除旧的溢出面板
        for op in self.overflow_panels:
            op.frame.destroy()
        self.overflow_panels.clear()
        
        if n_extra > 0:
            # 显示溢出行
            self.display_frame.grid_rowconfigure(2, weight=0)
            self.overflow_frame.grid(row=2, column=0, columnspan=2, sticky='ew', padx=2, pady=2)
            self.overflow_frame.grid_propagate(False)
            # 配置溢出行的列权重（等分）
            for c in range(n_extra):
                self.overflow_frame.grid_columnconfigure(c, weight=1)
            
            for i in range(n_extra):
                file_idx = 4 + i
                file_path = self.current_group_files[file_idx]
                op = MediaPanel(self.overflow_frame, file_idx, f"📷 截图 {file_idx + 1}")
                op.frame.grid(row=0, column=i, sticky='nsew', padx=2, pady=2)
                op.set_toggle_callback(self._toggle_file_selection)
                op.set_fullscreen_callback(self._open_fullscreen)
                op.set_refresh_callback(self._on_panel_refresh)
                op.setup_mini_ops(self.species_list, self._on_panel_species_select, None)
                op.display_image(file_path)
                op.set_selected(self.selected_flags[file_idx])
                self.overflow_panels.append(op)
        else:
            # 隐藏溢出行
            self.overflow_frame.grid_forget()
            self.display_frame.grid_rowconfigure(2, weight=0)
        
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
        
        # 选中提示
        n_files = len(self.current_group_files)
        n_selected = sum(self.selected_flags)
        self.label_select_hint.config(text=f"已选 {n_selected}/{n_files}")
        
        # 更新导航按钮
        self.btn_prev.config(state=tk.NORMAL if group_index > 0 else tk.DISABLED)
        self.btn_next.config(state=tk.NORMAL if group_index < len(self.groups) - 1 else tk.DISABLED)
        
        self._update_progress_bar()
        self._update_status()
    
    # ==================== 视频播放 ====================
    
    def _load_video(self, video_path: str, panel: MediaPanel):
        """
        加载视频文件并开始播放。
        先尝试opencv（多种后端），失败则用PyAV后备。
        
        参数：
            video_path: 视频文件路径
            panel: 用于显示视频的 MediaPanel
        """
        # 释放旧视频
        if self.video_cap:
            self.video_cap.release()
            self.video_cap = None
        self._av_container = None    # PyAV 容器（后备方案）
        self._av_frame_iter = None
        self._video_total_frames = 0
        self._video_frame_idx = 0
        
        # ---- 方案1: OpenCV ----
        backends = [cv2.CAP_FFMPEG, cv2.CAP_DSHOW, cv2.CAP_ANY]
        for backend in backends:
            try:
                cap = cv2.VideoCapture(video_path, backend)
                if cap.isOpened():
                    self.video_cap = cap
                    break
                cap.release()
            except Exception:
                continue
        
        if not self.video_cap or not self.video_cap.isOpened():
            # 短路径名后备
            try:
                import ctypes
                buf = ctypes.create_unicode_buffer(512)
                ctypes.windll.kernel32.GetShortPathNameW(video_path, buf, 512)
                short_path = buf.value
                if short_path and short_path != video_path:
                    self.video_cap = cv2.VideoCapture(short_path)
            except Exception:
                pass
        
        # ---- 方案2: PyAV 后备（av.open + frame.to_image，轻量且稳定）----
        if not self.video_cap or not self.video_cap.isOpened():
            try:
                import av
                self._av_container = av.open(video_path)
                # 验证存在视频流
                if not self._av_container.streams.video:
                    self._av_container.close()
                    self._av_container = None
                else:
                    # 预读第一帧验证可解码
                    self._av_frame_iter = self._av_container.decode(video=0)
                    first_frame = next(self._av_frame_iter, None)
                    if first_frame is None:
                        self._av_container.close()
                        self._av_container = None
                    else:
                        self.video_cap = None  # 使用PyAV路径
            except Exception:
                self._av_container = None
        
        # ---- 全部失败 ----
        if (not self.video_cap or not self.video_cap.isOpened()) and self._av_container is None:
            ext = os.path.splitext(video_path)[1].lower()
            self._log(f"无法播放视频: {video_path}", 'warning')
            panel.media_label.config(
                image='', text=f"⚠ 无法播放{ext}视频\n(可点击查看截图)",
                fg='#FFB74D'
            )
            panel.title_label.config(text=f"{panel.label_text} | ❌ {os.path.basename(video_path)}")
            self.video_playing = False
            try:
                panel.display_image(video_path)
            except Exception:
                pass
            return
        
        # ---- 设置帧率 ----
        if self.video_cap and self.video_cap.isOpened():
            fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            if fps <= 0 or fps > 120:
                fps = 25
        else:
            fps = 25  # PyAV默认
        
        target_fps = min(fps, 20)
        self.video_frame_delay = max(25, int(1000 / target_fps))
        self.video_panel = panel
        self._cached_video_dims = (0, 0)
        
        self.video_playing = True
        self._update_video_frame()
    
    def _update_video_frame(self):
        """
        定时更新视频帧（支持opencv和PyAV双源）。
        视频播放完毕后自动循环。
        """
        if not self.video_playing:
            return
        
        frame = None
        
        # ---- 源1: OpenCV ----
        if self.video_cap and self.video_cap.isOpened():
            grab_count = 0
            while grab_count < 5:
                ret, f = self.video_cap.read()
                if ret:
                    frame = f
                    grab_count += 1
                else:
                    break
            if frame is None:
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_cap.read()
                if not ret:
                    self.video_playing = False
                    return
        
        # ---- 源2: PyAV（后备）----
        elif self._av_container is not None:
            try:
                frame = next(self._av_frame_iter, None)
                if frame is None:
                    # 循环：seek到开头重新解码
                    self._av_container.seek(0)
                    self._av_frame_iter = self._av_container.decode(video=0)
                    frame = next(self._av_frame_iter, None)
            except StopIteration:
                self._av_container.seek(0)
                self._av_frame_iter = self._av_container.decode(video=0)
                frame = next(self._av_frame_iter, None)
            except Exception:
                self.video_playing = False
                return
            if frame is not None:
                # VideoFrame → PIL Image（RGB）
                frame = frame.to_image()
        
        else:
            self.video_playing = False
            return
        
        if frame is None:
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
        
        # --- 渲染帧（opencv BGR 或 PyAV RGB）---
        if new_w > 0 and new_h > 0:
            if self.video_cap and self.video_cap.isOpened():
                # OpenCV: BGR → resize → RGB
                frame_small = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
                frame_rgb = cv2.cvtColor(frame_small, cv2.COLOR_BGR2RGB)
            else:
                # PyAV: 已经是PIL Image（RGB），直接缩放
                frame_rgb = np.array(frame.resize((new_w, new_h), Image.LANCZOS))
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
        if self._av_container is not None:
            try:
                self._av_container.close()
            except Exception:
                pass
            self._av_container = None
        self._av_frame_iter = None
        self.video_photo = None
        self.video_panel = None
    
    # ==================== 选中状态管理 ====================
    
    def _toggle_file_selection(self, index: int):
        """切换指定文件（面板）的选中状态：反选后显示迷你标签栏"""
        if index < 0 or index >= len(self.current_group_files):
            return
        
        self.selected_flags[index] = not self.selected_flags[index]
        self._update_all_panel_selections()
        
        # 反选（取消选中）→ 显示该框的迷你标签栏；重新选中 → 隐藏
        if index < 4:
            panel = self._panels[index]
        else:
            overflow_idx = index - 4
            panel = self.overflow_panels[overflow_idx] if overflow_idx < len(self.overflow_panels) else None
        
        if panel:
            if not self.selected_flags[index]:
                panel.show_mini_ops()
            else:
                panel.hide_mini_ops()
                # 重新选中时清除该文件的标签
                panel.clear_mini_selection()
                if index in self.per_file_species:
                    del self.per_file_species[index]
        
        n_files = len(self.current_group_files)
        n_selected = sum(1 for i, flag in enumerate(self.selected_flags) if flag and i < n_files)
        self.label_select_hint.config(text=f"已选 {n_selected}/{n_files}")
    
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
    
    def _on_panel_species_select(self, file_index: int, selected_species: set):
        """
        框内迷你按钮选择回调：记录该文件的独立物种选择。
        """
        if selected_species:
            self.per_file_species[file_index] = selected_species.copy()
        elif file_index in self.per_file_species:
            del self.per_file_species[file_index]
    
    def _on_panel_refresh(self, panel_index: int):
        """
        迷你刷新按钮回调：重新扫描输出文件夹的物种并刷新所有迷你按钮。
        """
        self._scan_species_folders()
        self.label_status.config(
            text="🔄 已刷新物种列表", fg='#4CAF50'
        )
    
    # ==================== 分类操作 ====================
    
    def _on_empty(self):
        """空拍按钮：全部文件→空拍文件夹"""
        if not self.current_group_files:
            return
        self._classify_files(target_species=None)
    
    def _on_species_click(self, species_name: str):
        """物种按钮：多类模式下toggle选中，否则直接分类"""
        if self.multi_mode:
            # 多类模式：切换该物种的选中状态
            if species_name in self.multi_selected:
                self.multi_selected.discard(species_name)
            else:
                self.multi_selected.add(species_name)
            self._update_multi_buttons()
        else:
            # 普通模式：直接分类
            if not self.current_group_files:
                return
            self._classify_files(target_species=species_name)
    
    def _toggle_multi_mode(self):
        """切换多类别模式 / 提交多类别分类"""
        if self.multi_mode:
            # 当前在多类模式 → 提交分类
            if not self.multi_selected:
                self.label_status.config(text="⚠ 请先选择至少一个物种类别", fg='#FFB74D')
                return
            if not self.current_group_files:
                return
            selected_count = len(self.multi_selected)
            # 对每个选中的物种执行分类（不自动跳组，最后统一跳）
            for species in list(self.multi_selected):
                self._classify_files(target_species=species, auto_advance=False)
            # 退出多类模式
            self.multi_mode = False
            self.multi_selected.clear()
            self.btn_multi.config(text="📋 多类别", bg='#6A1B9A')
            self._update_multi_buttons()
            self.label_status.config(
                text=f"✅ 已分类到 {selected_count} 个类别", fg='#4CAF50'
            )
            # 分类完成后自动进入下一组
            self.root.after(300, self._auto_advance)
        else:
            # 进入多类模式
            self.multi_mode = True
            self.multi_selected.clear()
            self.btn_multi.config(text="✅ 完成分类", bg='#E65100')
            self.label_status.config(
                text="📋 多类别模式：点击物种按钮选择，完成后点「完成分类」", fg='#CE93D8'
            )
            self._update_multi_buttons()
    
    def _update_multi_buttons(self):
        """更新物种按钮外观（多类模式下高亮选中的物种）"""
        for name, btn in self.species_buttons.items():
            if self.multi_mode and name in self.multi_selected:
                btn.config(bg='#FF6F00', text=btn.cget('text').replace('  ✓', '') + '  ✓')
            elif self.multi_mode:
                btn.config(bg=COLOR_BUTTON_SPECIES, text=btn.cget('text').replace('  ✓', ''))
            else:
                btn.config(bg=COLOR_BUTTON_SPECIES, text=btn.cget('text').replace('  ✓', ''))
        # 更新新物种按钮（也在多类模式下保持可用）
        if self.multi_mode:
            # 如果通过新物种创建了物种，自动加入选中集合
            pass
    
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
        
        # 多类模式下自动选中新物种
        if self.multi_mode:
            self.multi_selected.add(species_name)
            self._update_multi_buttons()
            self.label_status.config(
                text=f"📋 新物种「{species_name}」已添加并选中", fg='#CE93D8'
            )
            return  # 不立即分类，等用户点「完成分类」
        
        self._classify_files(target_species=species_name)
    
    def _classify_files(self, target_species: str = None, auto_advance: bool = True):
        """
        执行文件复制操作。
        
        逻辑：
            - 如果该组之前已处理，先删除旧的目标文件（撤销），再重新分类
            - target_species=None → 全部文件复制到"空拍"文件夹
            - target_species=物种名 → 选中的→物种文件夹，未选中的→空拍文件夹
            - auto_advance=True → 分类完成后自动跳下一组（多类模式循环时传False）
        
        所有操作都是复制（shutil.copy2），原始文件保留不动。
        """
        if not self.current_group_files or not self.target_dir:
            self.label_status.config(
                text="⚠ 错误：未加载数据或未设置目标文件夹",
                fg='#FF6B6B'
            )
            return
        
        try:
            self._do_classify(target_species, auto_advance)
        except Exception as e:
            self._log(f"分类失败: {e}\n{traceback.format_exc()}", 'error')
            self.label_status.config(
                text=f"❌ 分类失败: {e}",
                fg='#FF6B6B'
            )
            import traceback
            traceback.print_exc()
    
    def _do_classify(self, target_species: str = None, auto_advance: bool = True):
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
        empty_dir = os.path.join(self.target_dir, "空拍")
        species_dir = os.path.join(self.target_dir, target_species) if target_species else None
        
        # 确保目标文件夹存在
        os.makedirs(empty_dir, exist_ok=True)
        if species_dir:
            os.makedirs(species_dir, exist_ok=True)
        
        # ---- 磁盘空间预检 ----
        try:
            # 计算当前组文件总大小
            group_size = sum(os.path.getsize(f) for f in self.current_group_files)
            # 输出文件夹所在磁盘的剩余空间
            free_space = shutil.disk_usage(self.target_dir).free
            if free_space < group_size:
                self._log(f"磁盘空间不足: 需要约{group_size/1024/1024:.1f}MB, 剩余{free_space/1024/1024:.1f}MB", 'warning')
                messagebox.showwarning(
                    "⚠ 磁盘空间可能不足",
                    f"输出文件夹所在磁盘剩余空间约 {free_space/1024/1024:.0f} MB，\n"
                    f"当前组文件约需 {group_size/1024/1024:.0f} MB。\n\n"
                    f"建议清理磁盘空间，或点击「📤 输出到」换一个输出位置。"
                )
        except OSError:
            pass  # 预检失败不影响复制（复制时仍会逐文件报错）
        
        copied_species = 0
        copied_empty = 0
        errors = []
        dest_files_record = []  # 记录所有复制到的目标路径（用于后续撤销）
        
        for i, file_path in enumerate(self.current_group_files):
            # 确定该文件的目标文件夹列表（标签优先）
            dest_dirs = []
            label = self.per_file_species.get(i)  # 迷你栏打上的标签
            is_selected = (i < len(self.selected_flags) and self.selected_flags[i])
            
            if label:
                # 有标签 → 按标签去对应文件夹（标签优先于主按钮）
                for sp in label:
                    sp_dir = os.path.join(self.target_dir, sp)
                    os.makedirs(sp_dir, exist_ok=True)
                    dest_dirs.append(sp_dir)
            elif target_species is None:
                # 主按钮是空拍 + 无标签 → 空拍
                dest_dirs.append(empty_dir)
            elif is_selected:
                # 无标签 + 选中 → 跟随主按钮类别
                dest_dirs.append(species_dir)
            else:
                # 无标签 + 取消选中 → 空拍
                dest_dirs.append(empty_dir)
            
            filename = os.path.basename(file_path)
            
            for dest_dir in dest_dirs:
                dest_path = os.path.join(dest_dir, filename)
                
                try:
                    if os.path.exists(dest_path):
                        base, ext = os.path.splitext(filename)
                        counter = 1
                        while os.path.exists(os.path.join(dest_dir, f"{base}_{counter}{ext}")):
                            counter += 1
                        dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                    
                    shutil.copy2(file_path, dest_path)
                    dest_files_record.append(dest_path)
                    
                    if dest_dir == species_dir:
                        copied_species += 1
                    elif dest_dir == empty_dir:
                        copied_empty += 1
                        
                except Exception as e:
                    # 记录错误详情（区分磁盘满等严重错误）
                    err_msg = str(e)
                    errors.append(f"  {filename}: {err_msg}")
                    self._log(f"复制失败 {filename}: {err_msg}", 'error')
        
        # 标记为已处理（带分类详情）
        self._mark_group_processed(
            self.current_group_index,
            species=target_species,
            dest_files=dest_files_record
        )
        
        # 日志记录
        species_label = target_species if target_species else "空拍"
        self._log(f"分类 第{self.current_group_index+1}组 → 「{species_label}」: 物种{copied_species}个, 空拍{copied_empty}个" + 
                  (f", 错误{len(errors)}个" if errors else ""))
        if errors:
            self._log(f"分类错误详情: {errors}", 'warning')
        
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
        
        # 复制失败时弹窗提醒（磁盘满等严重错误不能只看状态栏）
        if errors:
            error_text = "\n".join(errors)
            # 判断是否磁盘空间不足
            is_disk_full = any(
                ('空间' in e or 'No space' in e or 'ENOSPC' in e or '112' in e) for e in errors
            )
            if is_disk_full:
                messagebox.showerror(
                    "⚠ 输出文件夹空间不足",
                    f"复制文件失败，输出文件夹所在磁盘空间可能已满！\n\n"
                    f"请清理磁盘空间，或点击「📤 输出到」换一个输出位置。\n\n"
                    f"失败详情：\n{error_text}"
                )
            else:
                messagebox.showwarning(
                    "复制部分文件失败",
                    f"有 {len(errors)} 个文件复制失败：\n\n{error_text}\n\n"
                    f"详细原因请查看日志文件 wildcam_sorter.log"
                )
        # 恢复组信息标签颜色（之前可能被设为黄色警告色）
        self.label_group_info.config(
            text=f"📦 第 {self.current_group_index + 1}/{len(self.groups)} 组",
            fg=COLOR_TEXT
        )
        
        self._update_progress_bar()
        self._update_status()
        
        # 自动跳转下一组（多类模式循环时由外层统一调度）
        if auto_advance:
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
        if not self.target_dir:
            return
        
        # CSV文件路径：保存在目标文件夹下
        csv_path = os.path.join(self.target_dir, 'wildcam_records.csv')
        
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
        
        # 自动换行：每行最多7个按钮，超出换到下一行
        MAX_PER_ROW = 7
        # 创建行容器
        row_frames = []
        for i, name in enumerate(self.species_list):
            row_idx = i // MAX_PER_ROW
            if row_idx >= len(row_frames):
                row_frame = tk.Frame(self.species_frame, bg='#1A1A1A')
                row_frame.pack(fill=tk.X, pady=1)
                row_frames.append(row_frame)
            
            btn = tk.Button(
                row_frames[row_idx],
                text=name,
                font=("微软雅黑", 11),
                bg=COLOR_BUTTON_SPECIES, fg='white',
                activebackground='#43A047',
                relief=tk.FLAT, cursor='hand2',
                padx=12, pady=7,
                command=lambda n=name: self._on_species_click(n)
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.species_buttons[name] = btn
        
        # 刷新所有面板的迷你按钮
        for panel in self._panels:
            if hasattr(panel, 'rebuild_mini_buttons'):
                panel.rebuild_mini_buttons(self.species_list)
        for panel in self.overflow_panels:
            if hasattr(panel, 'rebuild_mini_buttons'):
                panel.rebuild_mini_buttons(self.species_list)
    
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
        self._log(f"程序关闭")
        self._stop_video()
        self.root.destroy()
    
    # ==================== 日志系统 ====================
    
    def _setup_logging(self):
        """初始化日志系统：轮转文件处理器，单文件最大5MB，保留3个备份"""
        self.logger = logging.getLogger('WildCamSorter')
        self.logger.setLevel(logging.DEBUG)
        # 日志文件将在首次打开文件夹时创建（需要target_dir）
        self._log_handler = None
    
    def _ensure_log_handler(self):
        """确保日志handler已创建（需要target_dir）"""
        if self._log_handler is not None:
            return
        if not self.target_dir:
            return
        try:
            log_path = os.path.join(self.target_dir, 'wildcam_sorter.log')
            handler = RotatingFileHandler(
                log_path, maxBytes=5*1024*1024, backupCount=3,
                encoding='utf-8'
            )
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self._log_handler = handler
        except Exception:
            pass
    
    def _log(self, msg: str, level: str = 'info'):
        """安全日志记录：不因日志错误影响主程序"""
        try:
            self._ensure_log_handler()
            if level == 'error':
                self.logger.error(msg)
            elif level == 'warning':
                self.logger.warning(msg)
            else:
                self.logger.info(msg)
        except Exception:
            pass  # 日志失败不影响程序运行
    
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
