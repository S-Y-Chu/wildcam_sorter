#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
野外相机数据分类工具 (WildCam Sorter)
======================================
功能：快速浏览野外相机拍摄的视频和照片（拍摄模式可配置），
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
import queue
import threading
import time
import traceback
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from collections.abc import Sequence

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

# 相机拍摄顺序
ORDER_PHOTOS_FIRST = 'photos_first'
ORDER_VIDEOS_FIRST = 'videos_first'
ORDER_DISPLAY_NAMES = {
    ORDER_PHOTOS_FIRST: '照片在前',
    ORDER_VIDEOS_FIRST: '视频在前',
}

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

# CSV固定列。文件名放在第一列，图片和视频统一按“一个文件一行”记录。
CSV_HEADERS = ['文件名', '经度', '纬度', '海拔高度(m)', '物种名', '拍摄时间', '点位名称']


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


class ScanCancelled(Exception):
    """用户取消大目录扫描。"""


class MediaGroupSequence(Sequence):
    """
    大目录的轻量分组视图。

    内存中只保存文件名；访问某一组时才拼接完整路径并生成该组列表，
    避免几十万文件时重复保存目录前缀和大量子列表。
    """

    def __init__(self, source_dir: str, file_names: list, group_size: int):
        self.source_dir = os.path.abspath(source_dir)
        self.file_names = file_names
        self.group_size = group_size

    @property
    def total_files(self) -> int:
        return len(self.file_names)

    def __len__(self):
        if not self.file_names:
            return 0
        return (len(self.file_names) + self.group_size - 1) // self.group_size

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        start = index * self.group_size
        names = self.file_names[start:start + self.group_size]
        return [os.path.join(self.source_dir, name) for name in names]


def media_sequence_number(filename: str):
    """提取扩展名前最后一段数字作为媒体序号；没有数字时返回 None。"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    matches = re.findall(r'\d+', stem)
    return int(matches[-1]) if matches else None


def search_media_group_chunk(groups: MediaGroupSequence, query: str,
                             start_index: int = 0, chunk_size: int = 20000) -> tuple:
    """
    分批查找序号或文件名，返回 (组索引或None, 下一文件索引, 是否完成)。
    该函数不访问磁盘，可由Tk的after分片调用以保持界面响应。
    """
    query = str(query).strip()
    names = groups.file_names
    end_index = min(len(names), start_index + max(1, chunk_size))
    numeric_query = int(query) if query.isdigit() else None
    query_lower = query.lower()

    for file_index in range(start_index, end_index):
        filename = names[file_index]
        if numeric_query is not None:
            matched = media_sequence_number(filename) == numeric_query
        else:
            stem = os.path.splitext(filename)[0]
            matched = filename.lower() == query_lower or stem.lower() == query_lower
        if matched:
            return file_index // groups.group_size, file_index + 1, True
    return None, end_index, end_index >= len(names)


def validate_capture_mode(photo_count: int, video_count: int, media_order: str) -> tuple:
    """校验并规范化拍摄模式，返回 (照片数, 视频数, 顺序)。"""
    try:
        photo_count = int(photo_count)
        video_count = int(video_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("照片数和视频数必须是整数") from exc

    if photo_count < 0 or video_count < 0:
        raise ValueError("照片数和视频数不能小于 0")
    if photo_count + video_count <= 0:
        raise ValueError("照片数和视频数不能同时为 0")
    if photo_count > 99 or video_count > 99:
        raise ValueError("照片数和视频数不能大于 99")
    if media_order not in ORDER_DISPLAY_NAMES:
        raise ValueError("请选择照片在前或视频在前")
    return photo_count, video_count, media_order


def expected_capture_types(photo_count: int, video_count: int, media_order: str) -> list:
    """返回一组拍摄模式对应的媒体类型序列。"""
    photo_count, video_count, media_order = validate_capture_mode(
        photo_count, video_count, media_order
    )
    photos = ['image'] * photo_count
    videos = ['video'] * video_count
    return photos + videos if media_order == ORDER_PHOTOS_FIRST else videos + photos


def group_matches_capture_pattern(group: list, photo_count: int,
                                  video_count: int, media_order: str) -> bool:
    """判断一组文件是否完整符合所选拍摄模式。末尾不完整组返回 False。"""
    expected = expected_capture_types(photo_count, video_count, media_order)
    if len(group) != len(expected):
        return False
    actual = [
        'video' if is_video_file(os.path.basename(path)) else 'image'
        for path in group
    ]
    return actual == expected


def scan_and_group_files(source_dir: str, photo_count: int = 3,
                         video_count: int = 1,
                         media_order: str = ORDER_VIDEOS_FIRST,
                         progress_callback=None,
                         cancel_event=None) -> MediaGroupSequence:
    """
    按用户指定的相机拍摄模式，将自然排序后的媒体文件固定数量分组。

    例如“3 张照片 + 1 个视频、照片在前”，每 4 个文件为一组；
    最后一组即使数量不足也会保留，确保任何媒体文件都不会被遗漏。
    
    参数：
        source_dir: 源文件夹路径
        photo_count: 每组照片数
        video_count: 每组视频数（可以为 0，表示纯照片模式）
        media_order: photos_first 或 videos_first
    返回：
        分组列表，每组是一个文件路径列表
    """
    photo_count, video_count, media_order = validate_capture_mode(
        photo_count, video_count, media_order
    )
    file_names = []
    visited_count = 0
    try:
        iterator = os.scandir(source_dir)
        try:
            for entry in iterator:
                visited_count += 1
                if cancel_event is not None and visited_count % 256 == 0:
                    if cancel_event.is_set():
                        raise ScanCancelled()
                try:
                    if entry.is_file(follow_symlinks=False) and is_media_file(entry.name):
                        file_names.append(entry.name)
                except OSError:
                    continue
                if progress_callback is not None and visited_count % 1000 == 0:
                    progress_callback('扫描输入文件', visited_count, len(file_names))
        finally:
            iterator.close()
    except (FileNotFoundError, NotADirectoryError):
        return MediaGroupSequence(source_dir, [], photo_count + video_count)

    if cancel_event is not None and cancel_event.is_set():
        raise ScanCancelled()
    if progress_callback is not None:
        progress_callback('排序媒体文件', visited_count, len(file_names))

    # 按文件名自然排序（确保 001, 002, ... 顺序正确）
    file_names.sort(key=natural_sort_key)

    group_size = photo_count + video_count
    return MediaGroupSequence(source_dir, file_names, group_size)


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

    try:
        with os.scandir(parent_dir) as entries:
            for entry in entries:
                try:
                    if (entry.is_dir(follow_symlinks=False)
                            and entry.name not in exclude_names
                            and not entry.name.startswith('.')):
                        species.append(entry.name)
                except OSError:
                    continue
    except OSError:
        return species

    species.sort()
    return species


def load_progress_snapshot(progress_file: str) -> tuple:
    """在线程中安全读取进度快照，损坏或不存在时返回空状态。"""
    if not progress_file or not os.path.exists(progress_file):
        return set(), {}
    try:
        with open(progress_file, 'r', encoding='utf-8') as handle:
            data = json.load(handle)
        return set(data.get('processed', [])), data.get('history', {})
    except (OSError, json.JSONDecodeError, TypeError):
        return set(), {}


def scan_classified_media(target_dir: str, source_basename: str,
                          progress_callback=None, cancel_event=None) -> tuple:
    """扫描输出分类目录，返回物种名列表和“文件名→物种目录”索引。"""
    species = []
    existing_files = {}
    visited = 0
    if not target_dir or not os.path.isdir(target_dir):
        return species, existing_files

    try:
        with os.scandir(target_dir) as root_entries:
            category_dirs = []
            for entry in root_entries:
                try:
                    if (entry.is_dir(follow_symlinks=False)
                            and entry.name != source_basename
                            and not entry.name.startswith('.')):
                        category_dirs.append((entry.name, entry.path))
                except OSError:
                    continue
    except OSError:
        return species, existing_files

    species = sorted(name for name, _ in category_dirs if name != '空拍')
    for category_name, category_path in category_dirs:
        if cancel_event is not None and cancel_event.is_set():
            raise ScanCancelled()
        try:
            with os.scandir(category_path) as entries:
                for entry in entries:
                    visited += 1
                    if cancel_event is not None and visited % 256 == 0:
                        if cancel_event.is_set():
                            raise ScanCancelled()
                    try:
                        if entry.is_file(follow_symlinks=False) and is_media_file(entry.name):
                            existing_files[entry.name] = category_name
                    except OSError:
                        continue
                    if progress_callback is not None and visited % 2000 == 0:
                        progress_callback('核对已有分类', visited, len(existing_files))
        except ScanCancelled:
            raise
        except OSError:
            continue
    return species, existing_files


def merge_presorted_progress(groups: Sequence, parent_dir: str, target_dir: str,
                             existing_files: dict, processed_groups: set,
                             class_history: dict, progress_callback=None,
                             cancel_event=None) -> tuple:
    """用输出目录中的现有文件补充进度；只操作线程内快照。"""
    processed_groups = set(processed_groups)
    class_history = dict(class_history)
    newly_found = 0
    if not existing_files:
        return processed_groups, class_history, newly_found

    for group_idx, group in enumerate(groups):
        if cancel_event is not None and group_idx % 256 == 0:
            if cancel_event.is_set():
                raise ScanCancelled()
        if not group:
            continue
        rel_path = os.path.relpath(group[0], parent_dir)
        if rel_path in processed_groups:
            continue
        names = [os.path.basename(path) for path in group]
        if not all(name in existing_files for name in names):
            continue

        dest_files = []
        species_name = None
        for name in names:
            category = existing_files[name]
            dest_files.append(os.path.join(target_dir, category, name))
            if species_name is None:
                species_name = category
        processed_groups.add(rel_path)
        class_history[rel_path] = {
            'species': species_name or '未知',
            'dest_files': dest_files,
        }
        newly_found += 1
        if progress_callback is not None and group_idx % 2000 == 0:
            progress_callback('匹配已有分类', group_idx + 1, newly_found)

    return processed_groups, class_history, newly_found


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
    
    用于2x2网格和溢出行中的每一个格子；照片、视频可出现在任意位置。
    """
    
    def __init__(self, parent, index: int, label_text: str):
        """
        参数：
            parent: 父容器 Frame
            index: 文件在组内的索引
            label_text: 面板标题（如 "🎬 视频 1"、"📷 照片 1"）
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
            with Image.open(image_path) as pil_img:
                pil_img.load()
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

    def display_video_thumbnail(self, video_path: str, retry: int = 0):
        """显示视频首帧缩略图；点击后仍由全屏视频播放器打开。"""
        self.file_path = video_path
        self.title_label.config(text=f"{self.label_text} | {os.path.basename(video_path)}")
        cap = None
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise OSError("无法读取视频首帧")
            ok, frame = cap.read()
            if not ok:
                raise OSError("无法读取视频首帧")
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            photo = self._resize_and_center(Image.fromarray(frame_rgb))
            if photo:
                self._photo = photo
                self.media_label.config(image=photo, text='')
            elif retry < 3:
                self.media_label.config(image='', text="")
                self.frame.after(150, lambda: self.display_video_thumbnail(video_path, retry + 1))
            else:
                self.media_label.config(image='', text="🎬 视频\n点击打开播放器")
        except Exception:
            self._photo = None
            self.media_label.config(image='', text="🎬 视频\n点击打开播放器")
        finally:
            if cap is not None:
                cap.release()
    
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


# ==================== 大目录扫描进度 ====================

class ScanProgressDialog:
    """非阻塞扫描提示窗；扫描在线程中运行，窗口始终可响应并可取消。"""

    def __init__(self, parent, cancel_callback):
        self.window = tk.Toplevel(parent)
        self.window.title("正在读取大目录")
        self.window.geometry("520x175")
        self.window.resizable(False, False)
        self.window.configure(bg=COLOR_BG)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", cancel_callback)

        tk.Label(
            self.window, text="正在后台读取红外相机数据…",
            font=("微软雅黑", 12, "bold"), bg=COLOR_BG, fg=COLOR_TEXT
        ).pack(pady=(20, 8))
        self.status_label = tk.Label(
            self.window, text="准备扫描", font=("微软雅黑", 9),
            bg=COLOR_BG, fg='#BDBDBD'
        )
        self.status_label.pack(pady=3)
        self.progress = ttk.Progressbar(self.window, mode='indeterminate', length=450)
        self.progress.pack(pady=8)
        self.progress.start(12)
        self.cancel_button = tk.Button(
            self.window, text="取消扫描", font=("微软雅黑", 9),
            bg='#616161', fg='white', relief=tk.FLAT, cursor='hand2',
            command=cancel_callback, padx=16, pady=4
        )
        self.cancel_button.pack(pady=5)

        self.window.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - self.window.winfo_width()) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - self.window.winfo_height()) // 3
        self.window.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    def update_status(self, phase: str, visited: int, media_count: int):
        if self.window.winfo_exists():
            self.status_label.config(
                text=f"{phase}｜已检查 {visited:,} 项，找到 {media_count:,} 个媒体文件"
            )

    def mark_cancelling(self):
        if self.window.winfo_exists():
            self.status_label.config(text="正在安全停止扫描…")
            self.cancel_button.config(state=tk.DISABLED)

    def close(self):
        try:
            self.progress.stop()
            self.window.grab_release()
            self.window.destroy()
        except tk.TclError:
            pass


# ==================== 路径设置与全分辨率查看器 ====================

class PathSelectDialog:
    """
    启动设置对话框：同时选择输入/输出文件夹和相机拍摄模式。
    
    布局：
        ┌──────────────────────────────────────────┐
        │       请选择路径和相机拍摄模式              │
        │  照片输入路径 [输入框.........] [📁按钮]   │
        │  照片输出路径 [输入框.........] [📁按钮]   │
        │  拍摄模式 [3]张照片 + [1]个视频 [视频在前] │
        │              [确定]  [取消]               │
        └──────────────────────────────────────────┘
    输入框支持手打路径，也可以点文件夹按钮浏览选择。
    """
    
    def __init__(self, parent, initial_input: str = "", initial_output: str = "",
                 initial_photo_count: int = 3, initial_video_count: int = 1,
                 initial_order: str = ORDER_VIDEOS_FIRST):
        """
        参数：
            parent: 父窗口
            initial_input/initial_output: 初始预填路径
            initial_photo_count/initial_video_count/initial_order: 初始拍摄模式
        """
        self.result = None  # (input_path, output_path, photo_count, video_count, order)
        
        self.window = tk.Toplevel(parent)
        self.window.title("路径与拍摄模式设置")
        self.window.configure(bg='#1E1E1E')
        self.window.resizable(False, False)
        self.window.transient(parent)  # 关联父窗口
        
        # 模态：阻塞父窗口交互
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # ---- 标题 ----
        tk.Label(
            self.window, text="请选择路径和相机拍摄模式",
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
        if initial_output:
            self.entry_output.insert(0, initial_output)
        tk.Button(output_row, text="📁", font=("微软雅黑", 10),
                  bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                  command=lambda: self._browse(self.entry_output)
                  ).pack(side=tk.LEFT, padx=2)
        
        # ---- 拍摄模式 ----
        mode_box = tk.LabelFrame(
            self.window, text=" 相机拍摄模式 ", font=("微软雅黑", 9, "bold"),
            bg='#1E1E1E', fg='#E0E0E0', padx=10, pady=8
        )
        mode_box.pack(fill=tk.X, padx=20, pady=(10, 4))

        mode_row = tk.Frame(mode_box, bg='#1E1E1E')
        mode_row.pack(fill=tk.X)
        tk.Label(mode_row, text="你的拍摄模式是", font=("微软雅黑", 9),
                 bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)

        self.entry_photo_count = tk.Entry(mode_row, font=("微软雅黑", 10), width=4,
                                          justify=tk.CENTER)
        self.entry_photo_count.pack(side=tk.LEFT, padx=(6, 2), ipady=2)
        self.entry_photo_count.insert(0, str(initial_photo_count))
        tk.Label(mode_row, text="张照片 +", font=("微软雅黑", 9),
                 bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)

        self.entry_video_count = tk.Entry(mode_row, font=("微软雅黑", 10), width=4,
                                          justify=tk.CENTER)
        self.entry_video_count.pack(side=tk.LEFT, padx=(6, 2), ipady=2)
        self.entry_video_count.insert(0, str(initial_video_count))
        tk.Label(mode_row, text="个视频", font=("微软雅黑", 9),
                 bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)

        self.order_var = tk.StringVar(
            value=ORDER_DISPLAY_NAMES.get(initial_order, ORDER_DISPLAY_NAMES[ORDER_VIDEOS_FIRST])
        )
        self.order_combo = ttk.Combobox(
            mode_row, textvariable=self.order_var,
            values=[ORDER_DISPLAY_NAMES[ORDER_PHOTOS_FIRST],
                    ORDER_DISPLAY_NAMES[ORDER_VIDEOS_FIRST]],
            state='readonly', width=9, font=("微软雅黑", 9)
        )
        self.order_combo.pack(side=tk.RIGHT, padx=(8, 0))

        # ---- 提示文字 ----
        tk.Label(
            self.window,
            text="提示：只拍照片时把视频数填 0；输出文件夹不存在会自动创建",
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
        """确定按钮：校验路径和拍摄模式并返回结果"""
        in_path = self.entry_input.get().strip().strip('"')
        out_path = self.entry_output.get().strip().strip('"')

        display_to_order = {display: value for value, display in ORDER_DISPLAY_NAMES.items()}
        try:
            photo_count, video_count, media_order = validate_capture_mode(
                self.entry_photo_count.get().strip(),
                self.entry_video_count.get().strip(),
                display_to_order.get(self.order_var.get())
            )
        except ValueError as exc:
            messagebox.showwarning("拍摄模式错误", str(exc), parent=self.window)
            return
        
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
        
        self.result = (in_path, out_path, photo_count, video_count, media_order)
        self.window.destroy()
    
    def _on_cancel(self):
        """取消按钮"""
        self.result = None
        self.window.destroy()


class FullScreenViewer:
    """
    全分辨率媒体查看器（独立弹窗）。
    
    功能：
        - 打开时自动适合窗口，图片/视频完整可见
        - 鼠标滚轮缩放（10%~500%）
        - 鼠标拖动平移（放大后）
        - 空格键播放/暂停视频
        - ESC 或返回按钮关闭
    """
    
    MIN_SCALE = 0.1   # 最小缩放10%
    MAX_SCALE = 5.0   # 最大缩放500%
    SCALE_STEP = 0.1  # 滚轮每次变化10%
    PLAYBACK_RATES = (0.5, 0.75, 0.8, 0.9, 1.0, 1.1, 1.2, 1.5, 2.0)
    PLAYBACK_RATE_LABELS = ('0.5×', '0.75×', '0.8×', '0.9×', '1.0×',
                            '1.1×', '1.2×', '1.5×', '2×')
    
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
        self._video_fps = 25.0        # 视频原始帧率
        self._video_frame_count = 0   # 视频总帧数
        self._video_duration = 0.0    # 视频时长（秒）
        self._playback_rate = 1.0     # 播放倍速
        self._next_frame_deadline = None  # 下一帧对应的单调时钟时间
        self._seeking = False         # 用户是否正在拖动进度条
        self._updating_progress = False
        self._drag_start = None       # 拖动起始坐标
        self._canvas_img_id = None    # Canvas中图片的ID
        self._canvas_resize_after_id = None
        
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
        # 视频使用独立的播放行和缩放行，避免进度条/倍速控件被缩放按钮挤掉。
        bottom_height = 88 if is_video else 46
        bottom_bar = tk.Frame(self.window, bg='#1A1A1A', height=bottom_height)
        bottom_bar.pack(fill=tk.X, side=tk.BOTTOM)
        bottom_bar.pack_propagate(False)

        if is_video:
            video_row = tk.Frame(bottom_bar, bg='#242424', height=44)
            video_row.pack(side=tk.TOP, fill=tk.X)
            video_row.pack_propagate(False)
        zoom_row = tk.Frame(bottom_bar, bg='#1A1A1A', height=44)
        zoom_row.pack(side=tk.BOTTOM, fill=tk.X)
        zoom_row.pack_propagate(False)
        
        # 缩小按钮
        btn_zoom_out = tk.Button(zoom_row, text="🔍− 缩小", font=("微软雅黑", 10),
                                 bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                 command=lambda: self._zoom(-self.SCALE_STEP), padx=8, pady=3)
        btn_zoom_out.pack(side=tk.LEFT, padx=8, pady=4)
        
        # 放大按钮
        btn_zoom_in = tk.Button(zoom_row, text="🔍+ 放大", font=("微软雅黑", 10),
                                bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                command=lambda: self._zoom(self.SCALE_STEP), padx=8, pady=3)
        btn_zoom_in.pack(side=tk.LEFT, padx=2, pady=4)
        
        # 适合窗口按钮
        btn_fit = tk.Button(zoom_row, text="📐 适合窗口", font=("微软雅黑", 10),
                            bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                            command=self._fit_to_window, padx=8, pady=3)
        btn_fit.pack(side=tk.LEFT, padx=8, pady=4)
        
        # 100%按钮
        btn_100 = tk.Button(zoom_row, text="1:1 原始", font=("微软雅黑", 10),
                            bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                            command=lambda: self._set_scale(1.0), padx=8, pady=3)
        btn_100.pack(side=tk.LEFT, padx=2, pady=4)
        
        # 播放控制（仅视频）
        if is_video:
            self.btn_play = tk.Button(video_row, text="⏯ 暂停", font=("微软雅黑", 10),
                                      bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                      command=self._toggle_video, padx=10, pady=3)
            self.btn_play.pack(side=tk.LEFT, padx=(8, 5), pady=5)

            self.video_time_label = tk.Label(
                video_row, text="00:00 / 00:00", font=("微软雅黑", 9),
                bg='#242424', fg='#CCCCCC', width=15
            )
            self.video_time_label.pack(side=tk.LEFT, padx=(0, 5), pady=5)

            speed_frame = tk.Frame(video_row, bg='#242424')
            speed_frame.pack(side=tk.RIGHT, padx=(5, 8), pady=4)
            tk.Label(speed_frame, text="播放速度", font=("微软雅黑", 9),
                     bg='#242424', fg='#CCCCCC').pack(side=tk.LEFT, padx=(0, 4))

            self.speed_var = tk.StringVar(value="1.0×")
            self.speed_combo = ttk.Combobox(
                speed_frame,
                textvariable=self.speed_var,
                values=self.PLAYBACK_RATE_LABELS,
                state='readonly', width=6, font=("微软雅黑", 9)
            )
            self.speed_combo.pack(side=tk.LEFT)
            self.speed_combo.bind('<<ComboboxSelected>>', self._on_speed_changed)

            self.video_progress_var = tk.DoubleVar(value=0.0)
            self.video_progress = ttk.Scale(
                video_row, from_=0.0, to=1.0,
                variable=self.video_progress_var,
                command=self._on_seek_preview
            )
            self.video_progress.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=6, pady=11)
            self.video_progress.bind('<ButtonPress-1>', self._on_seek_start)
            self.video_progress.bind('<ButtonRelease-1>', self._on_seek_end)
        
        # ---- 绑定事件 ----
        self.canvas.bind('<MouseWheel>', self._on_mousewheel)     # Windows滚轮
        self.canvas.bind('<Button-4>', self._on_mousewheel_up)    # Linux滚轮上
        self.canvas.bind('<Button-5>', self._on_mousewheel_down)  # Linux滚轮下
        self.canvas.bind('<ButtonPress-1>', self._on_drag_start)
        self.canvas.bind('<B1-Motion>', self._on_drag_move)
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        if is_video:
            self.window.bind('<space>', self._on_space_play_pause)
        
        # ---- 加载媒体 ----
        if is_video:
            self._load_video()
        else:
            self._load_image()
        # 等窗口布局完成后按窗口适配；“1:1 原始”按钮仍可随时查看原始像素。
        self.window.after(120, self._fit_to_window)
    
    # ==================== 图片加载 ====================
    
    def _load_image(self):
        """加载静态图片（原始分辨率）"""
        try:
            with Image.open(self.file_path) as image:
                image.load()
                self._orig_image = image.copy()
            self._update_display()
        except Exception as e:
            self.canvas.create_text(700, 400, text=f"无法加载图片: {e}",
                                    fill='#FF6B6B', font=("微软雅黑", 14))
    
    # ==================== 视频播放 ====================
    
    def _load_video(self):
        """加载视频，读取真实帧率/时长，并以1.0倍速开始播放。"""
        self._video_cap = cv2.VideoCapture(self.file_path)
        if not self._video_cap.isOpened():
            self.canvas.create_text(700, 400, text="无法打开视频",
                                    fill='#FF6B6B', font=("微软雅黑", 14))
            if hasattr(self, 'btn_play'):
                self.btn_play.config(state=tk.DISABLED)
            return
        
        fps = self._video_cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0 or fps > 120:
            fps = 25.0
        self._video_fps = float(fps)
        self._video_frame_count = max(0, int(self._video_cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        self._video_duration = (
            self._video_frame_count / self._video_fps
            if self._video_frame_count > 0 else 0.0
        )
        self._playback_rate = 1.0
        if hasattr(self, 'speed_var'):
            self.speed_var.set("1.0×")
        if hasattr(self, 'video_progress'):
            self.video_progress.config(to=max(self._video_duration, 0.001))
        
        # 先显示第一帧，再按媒体时钟调度后续帧。
        ret, frame = self._video_cap.read()
        if ret:
            self._display_video_frame(frame)
            self._set_video_progress(self._get_video_position())
        
        self._video_playing = True
        self._schedule_next_video_frame(reset_clock=True)

    def _frame_interval(self) -> float:
        """返回当前倍速下相邻视频帧的墙钟时间间隔（秒）。"""
        return 1.0 / max(self._video_fps * self._playback_rate, 0.001)

    def _schedule_next_video_frame(self, reset_clock: bool = False):
        """按照媒体时钟调度下一帧，避免把解码/缩放耗时叠加到帧间隔。"""
        if not self._video_playing or self._video_cap is None or self._seeking:
            return
        if self._video_after_id:
            try:
                self.window.after_cancel(self._video_after_id)
            except tk.TclError:
                pass
            self._video_after_id = None

        now = time.monotonic()
        interval = self._frame_interval()
        if reset_clock or self._next_frame_deadline is None:
            self._next_frame_deadline = now + interval
        delay_ms = max(1, int((self._next_frame_deadline - now) * 1000))
        self._video_after_id = self.window.after(delay_ms, self._update_video_frame)
    
    def _update_video_frame(self):
        """按真实FPS和当前倍速更新视频；落后时跳帧以保持正常播放速度。"""
        self._video_after_id = None
        if not self._video_playing or self._video_cap is None or self._seeking:
            return

        interval = self._frame_interval()
        now = time.monotonic()
        if self._next_frame_deadline is None:
            self._next_frame_deadline = now

        # 若UI渲染落后于媒体时钟，跳过已经错过的帧，而不是让整段视频慢放。
        frames_behind = max(0, int((now - self._next_frame_deadline) / interval))
        for _ in range(min(frames_behind, 30)):
            if not self._video_cap.grab():
                break

        ret, frame = self._video_cap.read()
        if not ret:
            self._video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._video_cap.read()
            if not ret:
                self._video_playing = False
                if hasattr(self, 'btn_play'):
                    self.btn_play.config(text="▶ 播放")
                return

        self._display_video_frame(frame)
        self._set_video_progress(self._get_video_position())

        # deadline只按媒体帧时钟推进，渲染耗时不会额外拖慢播放。
        self._next_frame_deadline += interval * (min(frames_behind, 30) + 1)
        if self._next_frame_deadline < time.monotonic() - interval:
            self._next_frame_deadline = time.monotonic() + interval
        self._schedule_next_video_frame()

    def _display_video_frame(self, frame):
        """把OpenCV帧转换成PIL图像并刷新Canvas。"""
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._orig_image = Image.fromarray(frame_rgb)
        self._update_display()

    def _get_video_position(self) -> float:
        """返回当前播放位置（秒），兼容不提供POS_MSEC的解码器。"""
        if self._video_cap is None:
            return 0.0
        position_ms = self._video_cap.get(cv2.CAP_PROP_POS_MSEC)
        if position_ms and position_ms > 0:
            return min(position_ms / 1000.0, self._video_duration or position_ms / 1000.0)
        frame_index = self._video_cap.get(cv2.CAP_PROP_POS_FRAMES)
        return max(0.0, frame_index / max(self._video_fps, 0.001))

    @staticmethod
    def _format_video_time(seconds: float) -> str:
        """把秒数格式化为 mm:ss；超过一小时后显示 h:mm:ss。"""
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _set_video_progress(self, seconds: float):
        """由播放器更新进度条和时间文本，不触发用户拖动逻辑。"""
        if not hasattr(self, 'video_progress_var'):
            return
        self._updating_progress = True
        try:
            position = max(0.0, min(float(seconds), self._video_duration or float(seconds)))
            self.video_progress_var.set(position)
            self.video_time_label.config(
                text=f"{self._format_video_time(position)} / "
                     f"{self._format_video_time(self._video_duration)}"
            )
        finally:
            self._updating_progress = False

    def _on_seek_preview(self, value):
        """拖动进度条时即时更新时间显示。"""
        if self._updating_progress or not hasattr(self, 'video_time_label'):
            return
        seconds = float(value)
        self.video_time_label.config(
            text=f"{self._format_video_time(seconds)} / "
                 f"{self._format_video_time(self._video_duration)}"
        )

    def _on_seek_start(self, event=None):
        """开始拖动进度条；暂时停止帧调度。"""
        self._seeking = True
        if self._video_after_id:
            try:
                self.window.after_cancel(self._video_after_id)
            except tk.TclError:
                pass
            self._video_after_id = None

    def _on_seek_end(self, event=None):
        """跳转到进度条位置并继续此前的播放状态。"""
        if self._video_cap is None:
            self._seeking = False
            return
        target_seconds = max(0.0, min(self.video_progress_var.get(), self._video_duration))
        self._video_cap.set(cv2.CAP_PROP_POS_MSEC, target_seconds * 1000.0)
        ret, frame = self._video_cap.read()
        if ret:
            self._display_video_frame(frame)
            self._set_video_progress(self._get_video_position())
        self._seeking = False
        self._next_frame_deadline = None
        if self._video_playing:
            self._schedule_next_video_frame(reset_clock=True)

    def _on_speed_changed(self, event=None):
        """应用用户选择的播放倍速。"""
        try:
            self._playback_rate = float(self.speed_var.get().rstrip('×'))
        except (TypeError, ValueError):
            self._playback_rate = 1.0
            self.speed_var.set("1.0×")
        if self._video_playing:
            self._schedule_next_video_frame(reset_clock=True)
    
    def _toggle_video(self):
        """播放/暂停视频"""
        if self._video_cap is None:
            return
        self._video_playing = not self._video_playing
        if self._video_playing:
            if hasattr(self, 'btn_play'):
                self.btn_play.config(text="⏯ 暂停")
            self._schedule_next_video_frame(reset_clock=True)
        else:
            if hasattr(self, 'btn_play'):
                self.btn_play.config(text="▶ 播放")
            if self._video_after_id:
                self.window.after_cancel(self._video_after_id)
                self._video_after_id = None

    def _on_space_play_pause(self, event=None):
        """空格键与播放/暂停按钮保持一致。"""
        self._toggle_video()
        return 'break'
    
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

    def _on_canvas_configure(self, event=None):
        """窗口布局变化时保持当前缩放比例，只重新居中显示。"""
        if self._canvas_resize_after_id:
            try:
                self.window.after_cancel(self._canvas_resize_after_id)
            except tk.TclError:
                pass
        self._canvas_resize_after_id = self.window.after(60, self._refresh_after_canvas_resize)

    def _refresh_after_canvas_resize(self):
        self._canvas_resize_after_id = None
        self._update_display()
    
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
            try:
                self.window.after_cancel(self._video_after_id)
            except tk.TclError:
                pass
            self._video_after_id = None
        if self._canvas_resize_after_id:
            try:
                self.window.after_cancel(self._canvas_resize_after_id)
            except tk.TclError:
                pass
            self._canvas_resize_after_id = None
        if self._video_cap:
            self._video_cap.release()
        if self._orig_image is not None:
            try:
                self._orig_image.close()
            except Exception:
                pass
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
        self.photo_count = 3             # 每组照片数
        self.video_count = 1             # 每组视频数
        self.media_order = ORDER_VIDEOS_FIRST
        self.group_pattern_mismatch_count = 0

        # ===== 大目录后台扫描状态 =====
        self._scan_thread = None
        self._scan_cancel_event = None
        self._scan_queue = queue.Queue()
        self._scan_poll_after_id = None
        self._scan_dialog = None
        self._scan_token = 0
        self._closing = False
        self._progress_save_lock = threading.Lock()
        self._progress_save_pending = None
        self._progress_save_thread = None
        self._jump_search_state = None
        
        # ===== 视频播放状态 =====
        self.video_cap = None             # cv2.VideoCapture 对象（解码线程内使用）
        self.video_playing = False        # 是否正在播放
        self.video_fps = 25               # 视频帧率
        self.video_frame_delay = 50       # 帧间延迟（毫秒，20fps显示）
        self.video_after_id = None        # after() 调度 ID
        self.video_photo = None           # 保持视频帧 PhotoImage 引用
        self._video_thread = None         # 视频解码线程
        self._video_queue = None          # 帧队列（解码线程→UI线程）
        self._video_stop = None           # 停止事件
        
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
        
        # 路径与模式按钮
        self.btn_open = tk.Button(
            toolbar, text="⚙ 路径与模式", font=("微软雅黑", 10),
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

        # 当前拍摄模式（右侧常驻显示，方便核对分组设置）
        self.label_capture_mode = tk.Label(
            toolbar, text="", font=("微软雅黑", 9),
            bg=COLOR_TOOLBAR, fg='#80CBC4'
        )
        self.label_capture_mode.pack(side=tk.RIGHT, padx=8, pady=3)
        self._update_capture_mode_label()
        
        # 统计信息（右侧）
        self.label_stats = tk.Label(
            toolbar, text="", font=("微软雅黑", 10),
            bg=COLOR_TOOLBAR, fg='#888888'
        )
        self.label_stats.pack(side=tk.RIGHT, padx=12, pady=3)

    def _update_capture_mode_label(self):
        """在工具栏显示当前拍摄模式。"""
        if not hasattr(self, 'label_capture_mode'):
            return
        order_text = ORDER_DISPLAY_NAMES.get(self.media_order, '未设置')
        self.label_capture_mode.config(
            text=f"模式：{self.photo_count}照片 + {self.video_count}视频｜{order_text}"
        )
    
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
            (0, 0, 0, "媒体 1"),
            (0, 1, 1, "媒体 2"),
            (1, 0, 2, "媒体 3"),
            (1, 1, 3, "媒体 4"),
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

        # 按照片/视频文件序号跳转（放在上一组与下一组之间）
        self.btn_jump_to_media = tk.Button(
            right_frame, text="跳转至", font=("微软雅黑", 10),
            bg='#6A1B9A', fg='white', activebackground='#8E24AA',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._prompt_jump_to_media
        )
        self.btn_jump_to_media.pack(side=tk.LEFT, padx=3)
        
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
    
    def _start_background_load(self, source_dir: str, target_dir: str,
                               photo_count=None, video_count=None, media_order=None):
        """在工作线程中扫描输入、进度和已有分类，保证Tk主线程不被大目录阻塞。"""
        self._stop_video()
        self._jump_search_state = None
        if hasattr(self, 'btn_jump_to_media'):
            self.btn_jump_to_media.config(state=tk.NORMAL, text="跳转至")
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()

        self._scan_token += 1
        token = self._scan_token
        cancel_event = threading.Event()
        self._scan_cancel_event = cancel_event
        self._scan_queue = queue.Queue()
        self._scan_dialog = ScanProgressDialog(self.root, self._cancel_background_scan)
        self.btn_open.config(state=tk.DISABLED)
        self.btn_target.config(state=tk.DISABLED)
        self.label_status.config(text="正在后台读取数据，可随时取消…", fg='#80CBC4')

        source_dir = os.path.abspath(source_dir)
        target_dir = os.path.abspath(target_dir)
        photo_count = self.photo_count if photo_count is None else photo_count
        video_count = self.video_count if video_count is None else video_count
        media_order = self.media_order if media_order is None else media_order

        def report(phase, visited, media_count):
            self._scan_queue.put((token, 'progress', phase, visited, media_count))

        def worker():
            try:
                parent_dir = os.path.dirname(source_dir)
                groups = scan_and_group_files(
                    source_dir, photo_count, video_count, media_order,
                    progress_callback=report, cancel_event=cancel_event
                )
                if cancel_event.is_set():
                    raise ScanCancelled()

                progress_file = os.path.join(parent_dir, '.wildcam_progress.json')
                processed_groups, class_history = load_progress_snapshot(progress_file)

                # 已有进度时只读取类别目录名，避免每次重启都遍历庞大的输出树。
                if processed_groups:
                    species_list = find_existing_species_folders(target_dir, source_dir)
                    existing_files = {}
                else:
                    species_list, existing_files = scan_classified_media(
                        target_dir, os.path.basename(source_dir), report, cancel_event
                    )

                processed_groups, class_history, newly_found = merge_presorted_progress(
                    groups, parent_dir, target_dir, existing_files,
                    processed_groups, class_history, report, cancel_event
                )

                mismatch_count = 0
                first_unprocessed = 0
                skipped_count = 0
                total_groups = len(groups)
                expected_types = expected_capture_types(
                    photo_count, video_count, media_order
                )
                for index in range(total_groups):
                    if index % 256 == 0 and cancel_event.is_set():
                        raise ScanCancelled()
                    start = index * groups.group_size
                    group_names = groups.file_names[start:start + groups.group_size]
                    actual_types = [
                        'video' if is_video_file(name) else 'image'
                        for name in group_names
                    ]
                    if actual_types != expected_types:
                        mismatch_count += 1
                    first_path = (
                        os.path.join(source_dir, group_names[0]) if group_names else ''
                    )
                    rel_path = os.path.relpath(first_path, parent_dir) if first_path else ''
                    if skipped_count == index and rel_path in processed_groups:
                        skipped_count += 1
                    elif skipped_count == index:
                        first_unprocessed = index
                    if report is not None and index and index % 5000 == 0:
                        report('建立分组索引', index, groups.total_files)

                if total_groups and skipped_count >= total_groups:
                    first_unprocessed = total_groups - 1

                result = {
                    'source_dir': source_dir,
                    'target_dir': target_dir,
                    'parent_dir': parent_dir,
                    'progress_file': progress_file,
                    'groups': groups,
                    'processed_groups': processed_groups,
                    'class_history': class_history,
                    'species_list': species_list,
                    'mismatch_count': mismatch_count,
                    'first_unprocessed': first_unprocessed,
                    'skipped_count': skipped_count,
                    'newly_found': newly_found,
                    'photo_count': photo_count,
                    'video_count': video_count,
                    'media_order': media_order,
                }
                self._scan_queue.put((token, 'done', result))
            except ScanCancelled:
                self._scan_queue.put((token, 'cancelled'))
            except Exception as exc:
                self._scan_queue.put((token, 'error', str(exc), traceback.format_exc()))

        self._scan_thread = threading.Thread(target=worker, daemon=True)
        self._scan_thread.start()
        self._poll_background_scan()

    def _cancel_background_scan(self):
        """请求扫描线程在安全检查点停止。"""
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        if self._scan_dialog is not None:
            self._scan_dialog.mark_cancelling()

    def _finish_background_scan_ui(self):
        if self._scan_poll_after_id:
            try:
                self.root.after_cancel(self._scan_poll_after_id)
            except tk.TclError:
                pass
            self._scan_poll_after_id = None
        if self._scan_dialog is not None:
            self._scan_dialog.close()
            self._scan_dialog = None
        self.btn_open.config(state=tk.NORMAL)
        self.btn_target.config(state=tk.NORMAL)

    def _poll_background_scan(self):
        """只在Tk主线程消费工作线程消息并更新界面。"""
        if self._closing:
            return
        terminal = None
        latest_progress = None
        try:
            while True:
                message = self._scan_queue.get_nowait()
                if message[0] != self._scan_token:
                    continue
                if message[1] == 'progress':
                    latest_progress = message
                else:
                    terminal = message
        except queue.Empty:
            pass

        if latest_progress and self._scan_dialog is not None:
            _, _, phase, visited, media_count = latest_progress
            self._scan_dialog.update_status(phase, visited, media_count)
            self.label_status.config(
                text=f"{phase}：已检查 {visited:,} 项，找到 {media_count:,} 个媒体文件",
                fg='#80CBC4'
            )

        if terminal is None:
            self._scan_poll_after_id = self.root.after(100, self._poll_background_scan)
            return

        self._finish_background_scan_ui()
        if terminal[1] == 'cancelled':
            self.label_status.config(text="已取消扫描，原数据未发生变化", fg='#FFB74D')
            return
        if terminal[1] == 'error':
            _, _, error_text, details = terminal
            self._log(f"读取大目录失败: {details}", 'error')
            self.label_status.config(text=f"读取失败：{error_text}", fg='#FF6B6B')
            messagebox.showerror("读取文件夹失败", f"无法完成目录扫描：\n\n{error_text}")
            return
        self._apply_background_load(terminal[2])

    def _apply_background_load(self, result: dict):
        """把线程计算好的不可变结果一次性切换到界面状态。"""
        old_target_dir = self.target_dir
        if old_target_dir and old_target_dir != result['target_dir'] and self._log_handler:
            try:
                self.logger.removeHandler(self._log_handler)
                self._log_handler.close()
            except Exception:
                pass
            self._log_handler = None
        self.source_dir = result['source_dir']
        self.target_dir = result['target_dir']
        self.parent_dir = result['parent_dir']
        self.photo_count = result['photo_count']
        self.video_count = result['video_count']
        self.media_order = result['media_order']
        self.progress_file = result['progress_file']
        self.groups = result['groups']
        self.processed_groups = result['processed_groups']
        self.class_history = result['class_history']
        self.species_list = result['species_list']
        self.group_pattern_mismatch_count = result['mismatch_count']
        self.current_group_index = -1
        self._panels_ready = False

        self.label_folder.config(text=f"📁 {self.source_dir}")
        self.label_target.config(text=f"📤 输出到: {self.target_dir}")
        self._update_capture_mode_label()
        self._rebuild_species_buttons()
        self._log(f"打开文件夹: {self.source_dir}")

        if not self.groups:
            self.label_stats.config(text="无媒体文件")
            self.label_status.config(text="未找到可识别的媒体文件", fg='#FFB74D')
            messagebox.showwarning(
                "未找到媒体文件",
                "在选定文件夹中未找到可识别的视频或图片文件。"
            )
            return

        self.label_stats.config(
            text=f"共 {len(self.groups):,} 组 / {self.groups.total_files:,} 个文件"
        )
        mismatch_count = self.group_pattern_mismatch_count
        if mismatch_count:
            self._log(f"有 {mismatch_count} 组与拍摄模式不完全一致", 'warning')
            messagebox.showwarning(
                "拍摄模式核对",
                f"有 {mismatch_count:,} 组与当前拍摄模式不完全一致（可能包含末尾不完整组）。\n\n"
                "所有文件仍会保留；如果分组不对，请点击“路径与模式”重新设置。"
            )

        newly_found = result['newly_found']
        if newly_found:
            self._save_progress()
            self._log(f"检测到 {newly_found} 组已手动分好，自动跳过")

        self.root.after(
            150,
            lambda: self._on_panels_ready(
                result['first_unprocessed'], result['skipped_count']
            )
        )
    
    def _show_path_dialog(self):
        """
        弹出路径选择对话框：一个窗口内同时选择输入和输出文件夹。
        确定后完成初始化，取消则保持空状态（可用工具栏按钮随时开始）。
        """
        dlg = PathSelectDialog(
            self.root,
            initial_input=self._pending_input or self.source_dir or "",
            initial_output=self.target_dir or "",
            initial_photo_count=self.photo_count,
            initial_video_count=self.video_count,
            initial_order=self.media_order
        )
        self.root.wait_window(dlg.window)  # 阻塞直到对话框关闭
        
        if dlg.result:
            in_path, out_path, photo_count, video_count, media_order = dlg.result
            self._start_background_load(
                in_path, out_path, photo_count, video_count, media_order
            )
        else:
            # 用户取消：保持空状态，提示可用工具栏按钮
            self.label_status.config(
                text="未选择路径，可点工具栏「⚙ 路径与模式」随时开始",
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
        """重新打开完整设置页，可同时切换输入/输出路径和拍摄模式。"""
        self._pending_input = self.source_dir or ""
        self._show_path_dialog()
    
    def _prompt_target_folder(self):
        """弹出输出文件夹选择对话框（分类结果输出位置）"""
        initial = self.target_dir if self.target_dir else os.path.expanduser("~")
        folder = filedialog.askdirectory(
            title="选择分类结果的输出文件夹",
            initialdir=initial
        )
        if folder:
            if self.source_dir:
                self._start_background_load(self.source_dir, folder)
            else:
                self.target_dir = os.path.abspath(folder)
                self.label_target.config(text=f"📤 输出到: {self.target_dir}")
    
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
    
    def _save_progress(self):
        """合并并在后台原子保存进度，避免大型历史记录阻塞界面。"""
        if not self.progress_file:
            return
        snapshot = (
            self.progress_file,
            list(self.processed_groups),
            dict(self.class_history),
        )
        with self._progress_save_lock:
            self._progress_save_pending = snapshot
            if self._progress_save_thread is not None and self._progress_save_thread.is_alive():
                return
            self._progress_save_thread = threading.Thread(
                target=self._progress_save_worker, daemon=True
            )
            self._progress_save_thread.start()

    def _progress_save_worker(self):
        """只写最新进度快照；连续分类时自动合并中间保存请求。"""
        while True:
            with self._progress_save_lock:
                snapshot = self._progress_save_pending
                self._progress_save_pending = None
            if snapshot is None:
                with self._progress_save_lock:
                    if self._progress_save_pending is None:
                        self._progress_save_thread = None
                        return
                continue

            progress_file, processed, history = snapshot
            temp_path = f"{progress_file}.tmp"
            try:
                with open(temp_path, 'w', encoding='utf-8') as handle:
                    json.dump(
                        {'processed': processed, 'history': history},
                        handle, ensure_ascii=False, separators=(',', ':')
                    )
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, progress_file)
            except OSError:
                try:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                except OSError:
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
        self._log(f"撤销分类: 第{group_index+1}组, 删除{deleted_count}个文件")
        
        return deleted_count
    
    # ==================== 组加载 ====================

    def _media_label_for_index(self, file_index: int) -> str:
        """按媒体真实类型生成“照片 N / 视频 N”标题。"""
        if file_index < 0 or file_index >= len(self.current_group_files):
            return f"媒体 {file_index + 1}"
        is_video = is_video_file(os.path.basename(self.current_group_files[file_index]))
        same_type_number = sum(
            1 for path in self.current_group_files[:file_index + 1]
            if is_video_file(os.path.basename(path)) == is_video
        )
        icon = "🎬" if is_video else "📷"
        media_name = "视频" if is_video else "照片"
        return f"{icon} {media_name} {same_type_number}"
    
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
        
        # 遍历4个主面板。视频可出现在任意位置；只自动播放第一个视频。
        video_started = False
        for panel_idx in range(4):
            panel = self._panels[panel_idx]
            
            if panel_idx < len(self.current_group_files):
                file_path = self.current_group_files[panel_idx]
                filename = os.path.basename(file_path)
                panel.label_text = self._media_label_for_index(panel_idx)

                if is_video_file(filename) and not video_started:
                    panel.file_path = file_path
                    panel.title_label.config(text=f"{panel.label_text} | {filename}")
                    self._load_video(file_path, panel)
                    video_started = True
                elif is_video_file(filename):
                    panel.display_video_thumbnail(file_path)
                else:
                    panel.display_image(file_path)
            else:
                panel.label_text = f"媒体 {panel_idx + 1}"
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
                op = MediaPanel(
                    self.overflow_frame, file_idx, self._media_label_for_index(file_idx)
                )
                op.frame.grid(row=0, column=i, sticky='nsew', padx=2, pady=2)
                op.set_toggle_callback(self._toggle_file_selection)
                op.set_fullscreen_callback(self._open_fullscreen)
                op.set_refresh_callback(self._on_panel_refresh)
                op.setup_mini_ops(self.species_list, self._on_panel_species_select, None)
                if is_video_file(os.path.basename(file_path)) and not video_started:
                    op.file_path = file_path
                    op.title_label.config(text=f"{op.label_text} | {os.path.basename(file_path)}")
                    self._load_video(file_path, op)
                    video_started = True
                elif is_video_file(os.path.basename(file_path)):
                    op.display_video_thumbnail(file_path)
                else:
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
        加载视频文件并开始播放（解码在子线程，UI永不卡死）。
        先尝试opencv（多种后端），失败则用PyAV后备。
        
        参数：
            video_path: 视频文件路径
            panel: 用于显示视频的 MediaPanel
        """
        # 停止旧视频（含旧线程）
        self._stop_video()
        
        self.video_panel = panel
        self.video_playing = True
        self._cached_video_dims = (0, 0)
        
        # 启动解码线程（daemon线程，解码卡住也不影响UI）
        self._video_stop = threading.Event()
        self._video_queue = queue.Queue(maxsize=2)
        self._video_thread = threading.Thread(
            target=self._video_decode_worker,
            args=(video_path,),
            daemon=True
        )
        self._video_thread.start()
        
        # 启动显示循环（UI线程只取帧显示，不解码）
        self.video_frame_delay = 50  # 20fps显示
        self._update_video_frame()
    
    def _video_decode_worker(self, video_path: str):
        """
        视频解码线程：持续读帧转RGB放入队列，循环播放。
        所有可能阻塞的解码操作都在此线程，UI线程只消费队列。
        """
        cap = None
        av_container = None
        av_iter = None
        fps = 25
        
        try:
            # ---- 方案1: OpenCV ----
            for backend in [cv2.CAP_FFMPEG, cv2.CAP_DSHOW, cv2.CAP_ANY]:
                try:
                    c = cv2.VideoCapture(video_path, backend)
                    if c.isOpened():
                        cap = c
                        break
                    c.release()
                except Exception:
                    continue
            if cap is None or not cap.isOpened():
                try:
                    import ctypes
                    buf = ctypes.create_unicode_buffer(512)
                    ctypes.windll.kernel32.GetShortPathNameW(video_path, buf, 512)
                    short_path = buf.value
                    if short_path and short_path != video_path:
                        cap = cv2.VideoCapture(short_path)
                except Exception:
                    pass
            
            # ---- 方案2: PyAV 后备 ----
            if cap is None or not cap.isOpened():
                try:
                    import av
                    av_container = av.open(video_path)
                    if not av_container.streams.video:
                        av_container.close()
                        av_container = None
                    else:
                        av_iter = av_container.decode(video=0)
                        # 预读一帧验证
                        if next(av_iter, None) is None:
                            av_container.close()
                            av_container = None
                except Exception:
                    av_container = None
            
            # 获取帧率（限制显示节奏用）
            if cap and cap.isOpened():
                fps = cap.get(cv2.CAP_PROP_FPS)
            if not (0 < fps <= 120):
                fps = 25
            
            source = cap if (cap and cap.isOpened()) else av_container
            if source is None:
                # 全部失败：通知UI显示错误
                self.root.after(0, lambda: self._video_load_failed(video_path))
                return
            
            # ---- 解码循环 ----
            fail_count = 0  # 连续读取失败计数，防止死循环
            while not self._video_stop.is_set():
                frame = None
                if cap is not None and cap.isOpened():
                    # 跳帧：连读最多3帧取最新，避免解码慢于显示时堆积
                    for _ in range(3):
                        ret, f = cap.read()
                        if ret:
                            frame = f
                        else:
                            break
                    if frame is None:
                        # 播放完，循环；但连续失败过多说明视频不可读，退出
                        fail_count += 1
                        if fail_count > 50:
                            break
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ret, frame = cap.read()
                        if not ret:
                            continue
                    else:
                        fail_count = 0
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                elif av_container is not None:
                    try:
                        av_frame = next(av_iter, None)
                        if av_frame is None:
                            # 循环：seek到开头
                            av_container.seek(0)
                            av_iter = av_container.decode(video=0)
                            av_frame = next(av_iter, None)
                        if av_frame is None:
                            fail_count += 1
                            if fail_count > 50:
                                break
                            continue
                        fail_count = 0
                        frame_rgb = np.array(av_frame.to_image())
                    except StopIteration:
                        av_container.seek(0)
                        av_iter = av_container.decode(video=0)
                        continue
                    except Exception:
                        break
                else:
                    break
                
                # 放入队列（满则丢弃最旧帧，保证队列不阻塞线程）
                try:
                    self._video_queue.put_nowait(frame_rgb)
                except queue.Full:
                    try:
                        self._video_queue.get_nowait()
                        self._video_queue.put_nowait(frame_rgb)
                    except Exception:
                        pass
        except Exception:
            pass  # 解码线程异常不影响UI
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            if av_container is not None:
                try:
                    av_container.close()
                except Exception:
                    pass
    
    def _video_load_failed(self, video_path: str):
        """视频完全无法打开时显示错误提示"""
        if not self.video_playing:
            return
        ext = os.path.splitext(video_path)[1].lower()
        self._log(f"无法播放视频: {video_path}", 'warning')
        panel = getattr(self, 'video_panel', None)
        if panel:
            panel.media_label.config(
                image='', text=f"⚠ 无法播放{ext}视频\n(可点击查看截图)",
                fg='#FFB74D'
            )
            panel.title_label.config(text=f"{panel.label_text} | ❌ {os.path.basename(video_path)}")
            try:
                panel.display_image(video_path)
            except Exception:
                pass
        self.video_playing = False
    
    def _update_video_frame(self):
        """
        定时从解码队列取帧并显示（UI线程不解码，绝不卡死）。
        视频播放完毕后由解码线程自动循环。
        """
        if not self.video_playing:
            return
        
        # 非阻塞取帧（无帧则保留上一帧，等下一轮）
        try:
            frame_rgb = self._video_queue.get_nowait()
        except (queue.Empty, AttributeError):
            frame_rgb = None
        
        panel = getattr(self, 'video_panel', None)
        if panel is None:
            return
        
        if frame_rgb is not None and panel is not None:
            # --- 获取/刷新缓存的面板显示尺寸（每30帧刷新一次）---
            if not hasattr(self, '_frame_count'):
                self._frame_count = 0
            self._frame_count += 1
            if self._frame_count % 30 == 0:
                self._cached_video_dims = panel._calc_display_size()
            new_w, new_h = self._cached_video_dims
            if new_w <= 0:
                new_w, new_h = panel._calc_display_size()
                self._cached_video_dims = (new_w, new_h)
            
            # 渲染帧（RGB numpy → 缩放 → PhotoImage）
            if new_w > 0 and new_h > 0:
                try:
                    pil_img = Image.fromarray(frame_rgb)
                    pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                    self.video_photo = ImageTk.PhotoImage(pil_img)
                    panel.media_label.config(image=self.video_photo, text='')
                except Exception:
                    pass
        
        # --- 调度下一帧显示 ---
        self.video_after_id = self.root.after(self.video_frame_delay, self._update_video_frame)
    
    def _toggle_play_pause(self):
        """切换视频播放/暂停状态"""
        if not hasattr(self, '_video_thread') or self._video_thread is None:
            return
        self.video_playing = not self.video_playing
        if self.video_playing:
            self._update_video_frame()
        else:
            if self.video_after_id:
                self.root.after_cancel(self.video_after_id)
                self.video_after_id = None
    
    def _stop_video(self):
        """停止视频播放，结束解码线程并释放资源"""
        self.video_playing = False
        if self.video_after_id:
            self.root.after_cancel(self.video_after_id)
            self.video_after_id = None
        # 通知解码线程退出并等待（超时2秒，避免阻塞UI）
        if self._video_stop is not None:
            self._video_stop.set()
        if hasattr(self, '_video_thread') and self._video_thread is not None:
            self._video_thread.join(timeout=2)
            self._video_thread = None
        # 清空队列
        if hasattr(self, '_video_queue'):
            try:
                while True:
                    self._video_queue.get_nowait()
            except Exception:
                pass
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
            panel_index: 文件在当前组中的索引
        """
        if panel_index < 0 or panel_index >= len(self.current_group_files):
            return
        
        file_path = self.current_group_files[panel_index]
        is_video = is_video_file(os.path.basename(file_path))
        
        # 暂停主窗口视频（避免两个窗口同时播放），并记住原来的播放状态。
        was_playing = self.video_playing
        if was_playing:
            self._toggle_play_pause()
        
        # 创建并打开全分辨率查看器（模态窗口，阻塞直到关闭）
        viewer = FullScreenViewer(self.root, file_path, is_video=is_video)
        # 等待查看器窗口关闭
        self.root.wait_window(viewer.window)
        
        # 只有原本正在播放时才恢复；查看图片也不会把主预览永久暂停。
        if was_playing and not self.video_playing:
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
        was_reclassification = bool(rel_path and rel_path in self.processed_groups)
        if was_reclassification:
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
        self._write_csv_record(target_species, replace_existing=was_reclassification)
        
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
    
    def _csv_species_for_file(self, file_index: int, target_species: str = None) -> str:
        """返回单个文件最终进入的类别；多类别以中文分号合并在同一行。"""
        labels = self.per_file_species.get(file_index)
        if labels:
            return '；'.join(sorted(labels, key=natural_sort_key))
        if target_species is None:
            return "空拍"
        is_selected = (
            file_index < len(self.selected_flags) and self.selected_flags[file_index]
        )
        return target_species if is_selected else "空拍"

    @staticmethod
    def _merge_media_metadata(own_data: dict, fallback_data: dict) -> dict:
        """优先使用文件自身元数据，缺失字段才回退到同组可用元数据。"""
        return {
            key: own_data.get(key) if own_data.get(key) is not None else fallback_data.get(key)
            for key in ('longitude', 'latitude', 'altitude', 'datetime')
        }

    @staticmethod
    def _csv_row(file_path: str, metadata: dict, species_name: str, point_name: str) -> dict:
        """构造一个媒体文件对应的CSV行。"""
        return {
            '文件名': os.path.basename(file_path),
            '经度': f"{metadata['longitude']:.6f}" if metadata['longitude'] is not None else "",
            '纬度': f"{metadata['latitude']:.6f}" if metadata['latitude'] is not None else "",
            '海拔高度(m)': f"{metadata['altitude']:.1f}" if metadata['altitude'] is not None else "",
            '物种名': species_name,
            '拍摄时间': metadata['datetime'].strftime('%Y-%m-%d %H:%M:%S') if metadata['datetime'] else "",
            '点位名称': point_name,
        }

    def _write_csv_record(self, target_species: str = None, replace_existing: bool = True):
        """
        将当前组逐文件写入CSV：一个图片或视频对应一行。

        重新分类同一组时按“点位名称 + 文件名”更新原行，避免重复记录。
        旧版无“文件名”列的CSV无法可靠映射到单个文件，因此会先自动备份，
        再创建新版CSV。
        """
        if not self.target_dir or not self.current_group_files:
            return

        csv_path = os.path.join(self.target_dir, 'wildcam_records.csv')
        point_name = os.path.basename(self.source_dir) if self.source_dir else ""

        # 为无完整元数据的文件准备同组回退值（仍优先使用文件自身值）。
        empty_metadata = {
            'longitude': None, 'latitude': None,
            'altitude': None, 'datetime': None
        }
        metadata_by_file = {}
        fallback_metadata = empty_metadata.copy()
        for file_path in self.current_group_files:
            metadata = extract_gps_from_file(file_path)
            metadata_by_file[file_path] = metadata
            for key in fallback_metadata:
                if fallback_metadata[key] is None and metadata.get(key) is not None:
                    fallback_metadata[key] = metadata[key]

        new_rows = []
        for index, file_path in enumerate(self.current_group_files):
            metadata = self._merge_media_metadata(
                metadata_by_file[file_path], fallback_metadata
            )
            new_rows.append(self._csv_row(
                file_path,
                metadata,
                self._csv_species_for_file(index, target_species),
                point_name,
            ))

        # 新分类直接追加，写入量与历史CSV大小无关；只有重新分类才流式重写。
        has_current_schema = False
        try:
            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                with open(csv_path, 'r', newline='', encoding='utf-8-sig') as source:
                    reader = csv.reader(source)
                    header = next(reader, [])
                    has_current_schema = '文件名' in header
                if not has_current_schema:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    stem, ext = os.path.splitext(csv_path)
                    backup_path = f"{stem}_旧格式备份_{timestamp}{ext}"
                    counter = 1
                    while os.path.exists(backup_path):
                        backup_path = f"{stem}_旧格式备份_{timestamp}_{counter}{ext}"
                        counter += 1
                    shutil.copy2(csv_path, backup_path)
                    self._log(f"旧版CSV已备份到: {backup_path}")
        except (OSError, csv.Error) as e:
            self._log(f"读取CSV失败，未写入新记录: {e}", 'warning')
            return

        if has_current_schema and not replace_existing:
            try:
                with open(csv_path, 'a', newline='', encoding='utf-8-sig') as target:
                    csv.DictWriter(target, fieldnames=CSV_HEADERS).writerows(new_rows)
                return
            except (OSError, csv.Error) as e:
                self._log(f"无法追加CSV记录: {e}", 'warning')
                return

        current_names = {os.path.basename(path) for path in self.current_group_files}
        temp_path = f"{csv_path}.tmp"
        try:
            with open(temp_path, 'w', newline='', encoding='utf-8-sig') as target:
                writer = csv.DictWriter(target, fieldnames=CSV_HEADERS)
                writer.writeheader()
                if has_current_schema:
                    with open(csv_path, 'r', newline='', encoding='utf-8-sig') as source:
                        reader = csv.DictReader(source)
                        for row in reader:
                            if (row.get('点位名称', '') == point_name
                                    and row.get('文件名', '') in current_names):
                                continue
                            writer.writerow({header: row.get(header, '') for header in CSV_HEADERS})
                writer.writerows(new_rows)
            os.replace(temp_path, csv_path)
        except (OSError, csv.Error) as e:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            self._log(f"无法写入CSV记录: {e}", 'warning')
    
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

    def _prompt_jump_to_media(self):
        """询问照片/视频序号，并启动不阻塞界面的分批查找。"""
        if not isinstance(self.groups, MediaGroupSequence) or not self.groups:
            messagebox.showinfo("跳转至", "请先打开包含媒体文件的文件夹。")
            return
        query = simpledialog.askstring(
            "跳转至照片/视频",
            "请输入照片或视频的序号：\n\n"
            "例如输入 200，可查找 200.jpg、IMG_0200.mp4 等文件所在的组。\n"
            "也可以直接输入完整文件名。",
            parent=self.root
        )
        if query is None:
            return
        query = query.strip()
        if not query:
            messagebox.showwarning("跳转至", "请输入有效的序号或文件名。")
            return

        self._jump_search_state = {'query': query, 'next_index': 0}
        self.btn_jump_to_media.config(state=tk.DISABLED, text="查找中…")
        self.label_status.config(text=f"正在查找序号 {query}…", fg='#CE93D8')
        self.root.after(1, self._continue_jump_to_media)

    def _continue_jump_to_media(self):
        """每次只检查一小批内存文件名，让百万级查找期间仍可操作界面。"""
        state = self._jump_search_state
        if state is None or not isinstance(self.groups, MediaGroupSequence):
            return
        group_index, next_index, finished = search_media_group_chunk(
            self.groups, state['query'], state['next_index']
        )
        state['next_index'] = next_index

        if group_index is not None:
            query = state['query']
            self._jump_search_state = None
            self.btn_jump_to_media.config(state=tk.NORMAL, text="跳转至")
            self._load_group(group_index)
            self.label_status.config(
                text=f"已跳到序号 {query} 所在的第 {group_index + 1:,} 组",
                fg='#4CAF50'
            )
            return
        if finished:
            query = state['query']
            self._jump_search_state = None
            self.btn_jump_to_media.config(state=tk.NORMAL, text="跳转至")
            self.label_status.config(text=f"没有找到序号或文件名：{query}", fg='#FFB74D')
            messagebox.showinfo("未找到", f"没有找到序号或文件名：{query}")
            return

        self.label_status.config(
            text=f"正在查找 {state['query']}：已检查 {next_index:,}/{self.groups.total_files:,} 个文件",
            fg='#CE93D8'
        )
        self.root.after(1, self._continue_jump_to_media)
    
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
        self._closing = True
        if self._scan_cancel_event is not None:
            self._scan_cancel_event.set()
        if self._scan_poll_after_id:
            try:
                self.root.after_cancel(self._scan_poll_after_id)
            except tk.TclError:
                pass
            self._scan_poll_after_id = None
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
        # 按真实文件类型重新缩放所有静态图片，不再假设第一个文件一定是视频。
        for panel_idx in range(0, min(4, len(self.current_group_files))):
            panel = self._panels[panel_idx]
            if panel.file_path and is_image_file(os.path.basename(panel.file_path)):
                panel.display_image(panel.file_path)
        for panel in self.overflow_panels:
            if panel.file_path and is_image_file(os.path.basename(panel.file_path)):
                panel.display_image(panel.file_path)
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
