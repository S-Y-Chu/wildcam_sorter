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
from collections import OrderedDict
from collections.abc import Sequence

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from PIL import Image, ImageTk, ImageOps
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

APP_VERSION = '1.10'
IMAGE_PREVIEW_WORKERS = 4
VIDEO_PREVIEW_WORKERS = 1
PREVIEW_CACHE_LIMIT = 16
VIDEO_AUTOPLAY_FALLBACK_MS = 2500
THEME_DISPLAY_NAMES = {'system': '跟随系统主题', 'light': '白色主题', 'dark': '黑色主题'}
THEME_DARK_TO_LIGHT = {
    '#1E1E1E': '#F3F4F6', '#252525': '#FFFFFF', '#111111': '#E5E7EB',
    '#1A1A1A': '#EEF0F3', '#242424': '#F8F9FA', '#333333': '#D1D5DB',
    '#E0E0E0': '#202124', '#CCCCCC': '#303134', '#AAAAAA': '#5F6368',
    '#888888': '#6B7280', '#424242': '#4B5563', '#555555': '#6B7280',
}

# macOS 的 Aqua 原生 Button 会忽略自定义 background，却保留 foreground。
# 如果仍使用白色文字，就会出现白底白字。所有按钮统一通过 create_button
# 创建，在 macOS 上使用适合原生浅色按钮表面的深色文字。
MACOS_BUTTON_TEXT = '#202124'
MACOS_BUTTON_ACTIVE_TEXT = '#111827'
MACOS_BUTTON_DISABLED_TEXT = '#6B7280'

# CSV固定列。文件名放在第一列，图片和视频统一按“一个文件一行”记录。
CSV_HEADERS = ['文件名', '经度', '纬度', '海拔高度(m)', '物种名', '拍摄时间', '点位名称']


# ==================== 辅助函数 ====================

def settings_file_path() -> str:
    """返回跨平台用户设置路径。"""
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA') or str(Path.home())
    elif sys.platform == 'darwin':
        base = os.path.join(str(Path.home()), 'Library', 'Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.join(str(Path.home()), '.config')
    return os.path.join(base, 'WildCamSorter', 'settings.json')


def load_app_settings() -> dict:
    defaults = {'theme': 'system'}
    try:
        with open(settings_file_path(), 'r', encoding='utf-8') as handle:
            saved = json.load(handle)
        if saved.get('theme') in THEME_DISPLAY_NAMES:
            defaults.update(saved)
    except (OSError, ValueError, TypeError):
        pass
    return defaults


def save_app_settings(settings: dict):
    path = settings_file_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp = path + '.tmp'
    with open(temp, 'w', encoding='utf-8') as handle:
        json.dump(settings, handle, ensure_ascii=False, indent=2)
    os.replace(temp, path)


def system_uses_dark_theme() -> bool:
    """尽力读取操作系统主题；无法读取时按当地时段给出稳定后备。"""
    try:
        if sys.platform.startswith('win'):
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Themes\Personalize'
            )
            value, _ = winreg.QueryValueEx(key, 'AppsUseLightTheme')
            return int(value) == 0
        if sys.platform == 'darwin':
            import subprocess
            result = subprocess.run(
                ['defaults', 'read', '-g', 'AppleInterfaceStyle'],
                capture_output=True, text=True, timeout=1
            )
            return result.returncode == 0 and 'dark' in result.stdout.lower()
    except Exception:
        pass
    return False


def ensure_macos_button_readability(button, platform_name: str = None):
    """修正 macOS Aqua 忽略按钮背景后造成的白底白字问题。"""
    platform_name = platform_name or sys.platform
    if platform_name == 'darwin':
        button.configure(
            foreground=MACOS_BUTTON_TEXT,
            activeforeground=MACOS_BUTTON_ACTIVE_TEXT,
            disabledforeground=MACOS_BUTTON_DISABLED_TEXT,
        )
    return button


def create_button(parent, **kwargs):
    """创建跨平台按钮；Windows/Linux 保持原样，macOS 确保文字可读。"""
    return ensure_macos_button_readability(tk.Button(parent, **kwargs))

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


def preferred_video_backends(platform_name: str = None) -> list:
    """返回当前系统适合的视频解码后端，避免调用其他平台专用后端。"""
    platform_name = platform_name or sys.platform
    candidates = [getattr(cv2, 'CAP_FFMPEG', None)]
    if platform_name.startswith('win'):
        candidates.append(getattr(cv2, 'CAP_DSHOW', None))
    elif platform_name == 'darwin':
        candidates.append(getattr(cv2, 'CAP_AVFOUNDATION', None))
    else:
        candidates.append(getattr(cv2, 'CAP_GSTREAMER', None))
    candidates.append(getattr(cv2, 'CAP_ANY', 0))

    # 某些OpenCV构建中CAP_ANY等常量可能与其他后端重复。
    backends = []
    for backend in candidates:
        if backend is not None and backend not in backends:
            backends.append(backend)
    return backends


def _windows_short_path(file_path: str) -> str:
    """仅在Windows上取得短路径；macOS/Linux直接返回空字符串。"""
    if not sys.platform.startswith('win'):
        return ''
    try:
        import ctypes
        buffer = ctypes.create_unicode_buffer(32768)
        length = ctypes.windll.kernel32.GetShortPathNameW(
            file_path, buffer, len(buffer)
        )
        if 0 < length < len(buffer):
            return buffer.value
    except (AttributeError, OSError, ValueError):
        pass
    return ''


def open_video_capture(video_path: str):
    """以当前系统支持的OpenCV后端打开视频，失败时返回None。"""
    for backend in preferred_video_backends():
        capture = None
        try:
            capture = cv2.VideoCapture(video_path, backend)
            if capture.isOpened():
                return capture
        except Exception:
            pass
        if capture is not None:
            try:
                capture.release()
            except Exception:
                pass

    # 中文或超长路径的短路径后备只适用于Windows。
    short_path = _windows_short_path(video_path)
    if short_path and short_path != video_path:
        try:
            capture = cv2.VideoCapture(short_path)
            if capture.isOpened():
                return capture
            capture.release()
        except Exception:
            pass
    return None


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

    def group_index_for_file(self, file_index: int):
        if 0 <= file_index < len(self.file_names):
            return file_index // self.group_size
        return None

    def mode_for_group(self, index: int):
        return None


class RangedMediaGroupSequence(Sequence):
    """按多个1-based文件序号范围分组，访问时才生成路径，适合超大目录。"""

    def __init__(self, source_dir: str, file_names: list, segments: list,
                 selection_start: int = 1, selection_end: int = None):
        self.source_dir = os.path.abspath(source_dir)
        self.file_names = file_names
        self.segments = self._cover_segments(segments, len(file_names))
        total_files = len(file_names)
        self.selection_start = max(1, int(selection_start or 1))
        self.selection_end = min(total_files, int(selection_end or total_files))
        if self.selection_end < self.selection_start:
            raise ValueError('选中范围的结束序号不能小于开始序号')
        self._entries = []
        cumulative = 0
        self.all_group_count = 0
        for segment in self.segments:
            start0 = segment['start'] - 1
            end0 = min(segment['end'], total_files)
            size = segment['photo_count'] + segment['video_count']
            full_count = max(0, (end0 - start0 + size - 1) // size)
            self.all_group_count += full_count
            selected_start0 = max(start0, self.selection_start - 1)
            selected_end0 = min(end0, self.selection_end)
            if selected_start0 >= selected_end0:
                continue
            first_local = (selected_start0 - start0) // size
            last_local = (selected_end0 - 1 - start0) // size
            count = last_local - first_local + 1
            self._entries.append({
                'segment': segment, 'start0': start0, 'end0': end0,
                'size': size, 'first_local': first_local, 'count': count,
                'cumulative': cumulative,
            })
            cumulative += count

    @staticmethod
    def _cover_segments(segments: list, total_files: int) -> list:
        """补齐未配置区间；空档沿用前一个模式，首段前空档沿用首个模式。"""
        if not segments:
            segments = [{'start': 1, 'end': total_files, 'photo_count': 3,
                         'video_count': 1, 'order': ORDER_VIDEOS_FIRST}]
        clean = sorted((dict(item) for item in segments), key=lambda x: int(x['start']))
        result = []
        cursor = 1
        previous = clean[0]
        for raw in clean:
            start = max(cursor, int(raw['start']))
            end = min(total_files, int(raw.get('end') or total_files))
            photo, video, order = validate_capture_mode(
                raw['photo_count'], raw['video_count'], raw['order']
            )
            if cursor < start:
                filler = dict(previous)
                filler.update(start=cursor, end=start - 1)
                result.append(filler)
            if start <= end:
                item = dict(start=start, end=end, photo_count=photo,
                            video_count=video, order=order)
                result.append(item)
                previous = item
                cursor = end + 1
        if cursor <= total_files:
            filler = dict(previous)
            filler.update(start=cursor, end=total_files)
            result.append(filler)
        return result

    @property
    def total_files(self):
        return max(0, self.selection_end - self.selection_start + 1)

    def __len__(self):
        return sum(entry['count'] for entry in self._entries)

    def _locate(self, index: int):
        if index < 0:
            index += len(self)
        if index < 0 or index >= len(self):
            raise IndexError(index)
        for entry in self._entries:
            if index < entry['cumulative'] + entry['count']:
                local = entry['first_local'] + index - entry['cumulative']
                return entry, local
        raise IndexError(index)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        entry, local = self._locate(index)
        start0 = entry['start0'] + local * entry['size']
        end0 = min(start0 + entry['size'], entry['end0'])
        start0 = max(start0, self.selection_start - 1)
        end0 = min(end0, self.selection_end)
        return [os.path.join(self.source_dir, name)
                for name in self.file_names[start0:end0]]

    def mode_for_group(self, index: int):
        entry, _ = self._locate(index)
        return entry['segment']

    def group_index_for_file(self, file_index: int):
        if not (self.selection_start - 1 <= file_index < self.selection_end):
            return None
        for entry in self._entries:
            if entry['start0'] <= file_index < entry['end0']:
                local = (file_index - entry['start0']) // entry['size']
                if entry['first_local'] <= local < entry['first_local'] + entry['count']:
                    return entry['cumulative'] + local - entry['first_local']
        return None

    def all_view(self):
        return RangedMediaGroupSequence(
            self.source_dir, self.file_names, self.segments, 1, len(self.file_names)
        )


def media_sequence_number(filename: str):
    """提取扩展名前最后一段数字作为媒体序号；没有数字时返回 None。"""
    stem = os.path.splitext(os.path.basename(filename))[0]
    matches = re.findall(r'\d+', stem)
    return int(matches[-1]) if matches else None


def search_media_group_chunk(groups, query: str,
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
            return groups.group_index_for_file(file_index), file_index + 1, True
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
                            existing_files.setdefault(entry.name, []).append(
                                (category_name, entry.path)
                            )
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
        categories = []
        for name in names:
            for category, dest_path in existing_files[name]:
                dest_files.append(dest_path)
                if category not in categories:
                    categories.append(category)
        if categories:
            species_name = '、'.join(categories)
        processed_groups.add(rel_path)
        class_history[rel_path] = {
            'species': species_name or '未知',
            'dest_files': dest_files,
        }
        newly_found += 1
        if progress_callback is not None and group_idx % 2000 == 0:
            progress_callback('匹配已有分类', group_idx + 1, newly_found)

    return processed_groups, class_history, newly_found


def backfill_manual_csv(source_dir: str, target_dir: str, existing_files: dict,
                        progress_callback=None, cancel_event=None) -> int:
    """把输出目录中人工复制、但CSV尚未记录的原名媒体补写为一文件一行。"""
    if not existing_files:
        return 0
    csv_path = os.path.join(target_dir, 'wildcam_records.csv')
    point_name = os.path.basename(source_dir)
    recorded = set()
    has_schema = False
    try:
        if os.path.isfile(csv_path) and os.path.getsize(csv_path):
            with open(csv_path, 'r', newline='', encoding='utf-8-sig') as handle:
                reader = csv.DictReader(handle)
                has_schema = '文件名' in (reader.fieldnames or [])
                if has_schema:
                    recorded = {
                        row.get('文件名', '') for row in reader
                        if row.get('点位名称', '') == point_name
                    }
    except (OSError, csv.Error):
        return 0

    if os.path.isfile(csv_path) and not has_schema:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = os.path.splitext(csv_path)[0] + f'_旧格式备份_{timestamp}.csv'
        try:
            shutil.copy2(csv_path, backup)
        except OSError:
            return 0

    rows = []
    for index, (filename, locations) in enumerate(existing_files.items()):
        if cancel_event is not None and index % 128 == 0 and cancel_event.is_set():
            raise ScanCancelled()
        if filename in recorded:
            continue
        source_path = os.path.join(source_dir, filename)
        if not os.path.isfile(source_path):
            continue
        metadata = extract_gps_from_file(source_path)
        categories = sorted({item[0] for item in locations}, key=natural_sort_key)
        rows.append({
            '文件名': filename,
            '经度': f"{metadata['longitude']:.6f}" if metadata['longitude'] is not None else '',
            '纬度': f"{metadata['latitude']:.6f}" if metadata['latitude'] is not None else '',
            '海拔高度(m)': f"{metadata['altitude']:.1f}" if metadata['altitude'] is not None else '',
            '物种名': '；'.join(categories),
            '拍摄时间': metadata['datetime'].strftime('%Y-%m-%d %H:%M:%S')
            if metadata['datetime'] else '',
            '点位名称': point_name,
        })
        if progress_callback is not None and index and index % 500 == 0:
            progress_callback('补写人工分类CSV', index, len(rows))

    if not rows:
        return 0
    mode = 'a' if has_schema else 'w'
    with open(csv_path, mode, newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_HEADERS)
        if mode == 'w':
            writer.writeheader()
        writer.writerows(rows)
    return len(rows)


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
    
    img = None
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
    finally:
        if img is not None:
            try:
                img.close()
            except Exception:
                pass
    
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
        self.select_btn = create_button(
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

    def display_loading(self, file_path: str, label_text: str = None):
        """立即切换面板身份，缩略图随后由后台线程填入。"""
        self.file_path = file_path
        if label_text is not None:
            self.label_text = label_text
        self._photo = None
        self.title_label.config(
            text=f"{self.label_text} | {os.path.basename(file_path)}"
        )
        self.media_label.config(image='', text="加载中…")
    
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
            btn = create_button(
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
        self.mini_multi_btn = create_button(
            self.mini_func_row,
            text="📋 多类别", font=("微软雅黑", 8),
            bg='#6A1B9A', fg='white',
            relief=tk.FLAT, cursor='hand2',
            padx=4, pady=0,
            command=self._on_mini_multi
        )
        self.mini_multi_btn.pack(side=tk.LEFT, padx=1, pady=1)
        
        # 迷你刷新按钮
        self.mini_refresh_btn = create_button(
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
            btn = create_button(
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
        self.cancel_button = create_button(
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
                 initial_order: str = ORDER_VIDEOS_FIRST,
                 initial_segments: list = None,
                 initial_selection: tuple = (1, None)):
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
        create_button(input_row, text="📁", font=("微软雅黑", 10),
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
        create_button(output_row, text="📁", font=("微软雅黑", 10),
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
        first_segment = (initial_segments or [{}])[0]
        self.entry_photo_count.insert(0, str(first_segment.get('photo_count', initial_photo_count)))
        tk.Label(mode_row, text="张照片 +", font=("微软雅黑", 9),
                 bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)

        self.entry_video_count = tk.Entry(mode_row, font=("微软雅黑", 10), width=4,
                                          justify=tk.CENTER)
        self.entry_video_count.pack(side=tk.LEFT, padx=(6, 2), ipady=2)
        self.entry_video_count.insert(0, str(first_segment.get('video_count', initial_video_count)))
        tk.Label(mode_row, text="个视频", font=("微软雅黑", 9),
                 bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)

        self.order_var = tk.StringVar(
            value=ORDER_DISPLAY_NAMES.get(first_segment.get('order', initial_order),
                                           ORDER_DISPLAY_NAMES[ORDER_VIDEOS_FIRST])
        )
        self.order_combo = ttk.Combobox(
            mode_row, textvariable=self.order_var,
            values=[ORDER_DISPLAY_NAMES[ORDER_PHOTOS_FIRST],
                    ORDER_DISPLAY_NAMES[ORDER_VIDEOS_FIRST]],
            state='readonly', width=9, font=("微软雅黑", 9)
        )
        self.order_combo.pack(side=tk.RIGHT, padx=(8, 0))

        # ---- 模式生效范围 / 多段模式 ----
        scope_row = tk.Frame(mode_box, bg='#1E1E1E')
        scope_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(scope_row, text="上述模式适用于文件序号", font=("微软雅黑", 9),
                 bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)
        self.entry_mode_start = tk.Entry(scope_row, width=7, justify=tk.CENTER)
        self.entry_mode_start.pack(side=tk.LEFT, padx=4)
        self.entry_mode_start.insert(0, str(first_segment.get('start', 1)))
        tk.Label(scope_row, text="至", bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)
        self.entry_mode_end = tk.Entry(scope_row, width=9, justify=tk.CENTER)
        self.entry_mode_end.pack(side=tk.LEFT, padx=4)
        first_end = first_segment.get('end')
        if first_end:
            self.entry_mode_end.insert(0, str(first_end))
        tk.Label(scope_row, text="（留空=最后一个文件）", font=("微软雅黑", 8),
                 bg='#1E1E1E', fg='#888888').pack(side=tk.LEFT)

        self.extra_segment_rows = []
        self.extra_segments_frame = tk.Frame(mode_box, bg='#1E1E1E')
        self.extra_segments_frame.pack(fill=tk.X)
        for segment in (initial_segments or [])[1:]:
            self._add_segment_row(segment)
        create_button(
            mode_box, text="＋ 添加下一个模式范围", font=("微软雅黑", 9),
            bg='#455A64', fg='white', relief=tk.FLAT, cursor='hand2',
            command=self._add_segment_row
        ).pack(anchor='w', pady=(7, 0))

        selection_box = tk.LabelFrame(
            self.window, text=" 本次只查看/分类的范围 ", font=("微软雅黑", 9, "bold"),
            bg='#1E1E1E', fg='#E0E0E0', padx=10, pady=7
        )
        selection_box.pack(fill=tk.X, padx=20, pady=(6, 2))
        tk.Label(selection_box, text="文件序号", bg='#1E1E1E',
                 fg='#E0E0E0').pack(side=tk.LEFT)
        self.entry_selection_start = tk.Entry(selection_box, width=9, justify=tk.CENTER)
        self.entry_selection_start.pack(side=tk.LEFT, padx=5)
        self.entry_selection_start.insert(0, str((initial_selection or (1, None))[0] or 1))
        tk.Label(selection_box, text="至", bg='#1E1E1E',
                 fg='#E0E0E0').pack(side=tk.LEFT)
        self.entry_selection_end = tk.Entry(selection_box, width=11, justify=tk.CENTER)
        self.entry_selection_end.pack(side=tk.LEFT, padx=5)
        selected_end = (initial_selection or (1, None))[1]
        if selected_end:
            self.entry_selection_end.insert(0, str(selected_end))
        tk.Label(selection_box, text="（留空=全部）", font=("微软雅黑", 8),
                 bg='#1E1E1E', fg='#888888').pack(side=tk.LEFT)

        # ---- 提示文字 ----
        tk.Label(
            self.window,
            text="提示：只拍照片时把视频数填 0；输出文件夹不存在会自动创建",
            font=("微软雅黑", 8), bg='#1E1E1E', fg='#888888'
        ).pack(pady=(2, 8))
        
        # ---- 按钮行 ----
        btn_row = tk.Frame(self.window, bg='#1E1E1E')
        btn_row.pack(pady=(5, 15))
        create_button(btn_row, text="确定", font=("微软雅黑", 10),
                  bg='#2E7D32', fg='white', relief=tk.FLAT, cursor='hand2',
                  padx=20, pady=4, command=self._on_ok
                  ).pack(side=tk.LEFT, padx=10)
        create_button(btn_row, text="取消", font=("微软雅黑", 10),
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

    def _add_segment_row(self, values=None):
        values = values if isinstance(values, dict) else {}
        row = tk.Frame(self.extra_segments_frame, bg='#1E1E1E')
        row.pack(fill=tk.X, pady=(6, 0))
        entries = {}
        for label, key, width, default in (
                ('序号', 'start', 6, ''), ('至', 'end', 7, ''),
                ('照片', 'photo_count', 4, 3), ('视频', 'video_count', 4, 1)):
            tk.Label(row, text=label, bg='#1E1E1E', fg='#E0E0E0').pack(side=tk.LEFT)
            entry = tk.Entry(row, width=width, justify=tk.CENTER)
            entry.pack(side=tk.LEFT, padx=(2, 5))
            value = values.get(key, default)
            if value not in ('', None):
                entry.insert(0, str(value))
            entries[key] = entry
        order_var = tk.StringVar(value=ORDER_DISPLAY_NAMES.get(
            values.get('order', ORDER_VIDEOS_FIRST), ORDER_DISPLAY_NAMES[ORDER_VIDEOS_FIRST]
        ))
        ttk.Combobox(row, textvariable=order_var,
                     values=list(ORDER_DISPLAY_NAMES.values()), state='readonly',
                     width=9).pack(side=tk.LEFT, padx=4)
        item = {'frame': row, 'entries': entries, 'order_var': order_var}
        create_button(row, text="删除", bg='#8E2A2A', fg='white', relief=tk.FLAT,
                  command=lambda: self._remove_segment_row(item)).pack(side=tk.RIGHT)
        self.extra_segment_rows.append(item)

    def _remove_segment_row(self, item):
        if item in self.extra_segment_rows:
            self.extra_segment_rows.remove(item)
            item['frame'].destroy()
    
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
            first_start = int(self.entry_mode_start.get().strip() or '1')
            first_end_text = self.entry_mode_end.get().strip()
            segments = [{
                'start': first_start,
                'end': int(first_end_text) if first_end_text else None,
                'photo_count': photo_count,
                'video_count': video_count,
                'order': media_order,
            }]
            for row in self.extra_segment_rows:
                entries = row['entries']
                start_text = entries['start'].get().strip()
                end_text = entries['end'].get().strip()
                if not start_text:
                    raise ValueError('新增模式范围必须填写开始序号')
                p, v, order = validate_capture_mode(
                    entries['photo_count'].get().strip(),
                    entries['video_count'].get().strip(),
                    display_to_order.get(row['order_var'].get())
                )
                segments.append({
                    'start': int(start_text), 'end': int(end_text) if end_text else None,
                    'photo_count': p, 'video_count': v, 'order': order,
                })
            segments.sort(key=lambda item: item['start'])
            for index, segment in enumerate(segments):
                if segment['start'] < 1:
                    raise ValueError('范围序号必须从1开始')
                if segment['end'] is not None and segment['end'] < segment['start']:
                    raise ValueError('模式范围的结束序号不能小于开始序号')
                if index < len(segments) - 1:
                    if segment['end'] is None:
                        segment['end'] = segments[index + 1]['start'] - 1
                    if segment['end'] >= segments[index + 1]['start']:
                        raise ValueError('不同模式范围不能重叠')
            selection_start = int(self.entry_selection_start.get().strip() or '1')
            selection_end_text = self.entry_selection_end.get().strip()
            selection_end = int(selection_end_text) if selection_end_text else None
            if selection_start < 1 or (selection_end is not None
                                       and selection_end < selection_start):
                raise ValueError('本次查看范围填写不正确')
        except (ValueError, TypeError) as exc:
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
        
        self.result = (in_path, out_path, segments, selection_start, selection_end)
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
        - 鼠标滚轮围绕指针缩放（窗口适配大小的100%~1000%）
        - 鼠标拖动平移（放大后）
        - 空格键播放/暂停视频
        - ESC 或返回按钮关闭
    """
    
    MIN_ZOOM = 1.0    # 100% = 当前窗口中完整显示媒体的大小
    MAX_ZOOM = 10.0   # 1000%
    BUTTON_ZOOM_FACTOR = 1.2
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
        self.zoom_level = 1.0         # 相对适合窗口比例（1.0=界面显示100%）
        self.fit_scale = 1.0          # 适合窗口相对于原始像素的比例
        self.scale_factor = 1.0       # 实际渲染比例 = fit_scale * zoom_level
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
        self._image_left = 0.0
        self._image_top = 0.0
        self._rendered_size = (1, 1)
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._last_wheel_time = None
        
        # 创建顶层窗口
        self.window = tk.Toplevel(parent)
        self.window.title(f"🔍 {os.path.basename(file_path)}")
        # 按可用屏幕居中，并在四周留出余量，避免任务栏/程序坞遮住底部控件。
        self.window.update_idletasks()
        screen_w = max(800, self.window.winfo_screenwidth())
        screen_h = max(600, self.window.winfo_screenheight())
        window_w = min(1400, max(760, screen_w - 80))
        window_h = min(950, max(520, screen_h - 120))
        window_x = max(0, (screen_w - window_w) // 2)
        window_y = max(0, (screen_h - window_h) // 2 - 10)
        self.window.geometry(f"{window_w}x{window_h}+{window_x}+{window_y}")
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
        btn_close = create_button(toolbar, text="✕ 返回", font=("微软雅黑", 9),
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
        # 查看器采用视口切片渲染，无需生成可能占数百MB的整张1000%位图。
        self.h_scroll.pack_forget()
        self.v_scroll.pack_forget()
        
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
        btn_zoom_out = create_button(zoom_row, text="🔍− 缩小", font=("微软雅黑", 10),
                                 bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                 command=lambda: self._zoom_by_factor(
                                     1.0 / self.BUTTON_ZOOM_FACTOR), padx=8, pady=3)
        btn_zoom_out.pack(side=tk.LEFT, padx=8, pady=4)
        
        # 放大按钮
        btn_zoom_in = create_button(zoom_row, text="🔍+ 放大", font=("微软雅黑", 10),
                                bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                                command=lambda: self._zoom_by_factor(
                                    self.BUTTON_ZOOM_FACTOR), padx=8, pady=3)
        btn_zoom_in.pack(side=tk.LEFT, padx=2, pady=4)
        
        # 适合窗口按钮
        btn_fit = create_button(zoom_row, text="📐 适合窗口", font=("微软雅黑", 10),
                            bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                            command=self._fit_to_window, padx=8, pady=3)
        btn_fit.pack(side=tk.LEFT, padx=8, pady=4)
        
        # 100%按钮
        btn_100 = create_button(zoom_row, text="1:1 原始", font=("微软雅黑", 10),
                            bg='#424242', fg='white', relief=tk.FLAT, cursor='hand2',
                            command=self._show_original_pixels, padx=8, pady=3)
        btn_100.pack(side=tk.LEFT, padx=2, pady=4)
        
        # 播放控制（仅视频）
        if is_video:
            self.btn_play = create_button(video_row, text="⏯ 暂停", font=("微软雅黑", 10),
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
        # 等窗口布局完成后按窗口适配；此时界面缩放值固定显示100%。
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
        self._video_cap = open_video_capture(self.file_path)
        if self._video_cap is None or not self._video_cap.isOpened():
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
    
    def _calculate_fit_scale(self):
        """计算完整显示媒体所需的原始像素缩放比例。"""
        if self._orig_image is None:
            return 1.0
        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        orig_w, orig_h = self._orig_image.size
        return max(0.0001, min(canvas_w / orig_w, canvas_h / orig_h) * 0.98)

    def _update_display(self, anchor=None):
        """刷新显示；anchor=(x,y,image_x,image_y)时保持鼠标下像素不动。"""
        if self._orig_image is None:
            return

        old_w, old_h = self._rendered_size
        old_left, old_top = self._image_left, self._image_top
        self.fit_scale = self._calculate_fit_scale()
        self.scale_factor = self.fit_scale * self.zoom_level
        orig_w, orig_h = self._orig_image.size
        new_w = max(1, int(orig_w * self.scale_factor))
        new_h = max(1, int(orig_h * self.scale_factor))

        if self._canvas_img_id:
            self.canvas.delete(self._canvas_img_id)

        canvas_w = max(1, self.canvas.winfo_width())
        canvas_h = max(1, self.canvas.winfo_height())
        base_left = (canvas_w - new_w) / 2.0
        base_top = (canvas_h - new_h) / 2.0
        if anchor is not None:
            pointer_x, pointer_y, image_x, image_y = anchor
            left = pointer_x - image_x * new_w
            top = pointer_y - image_y * new_h
            self._pan_x = left - base_left
            self._pan_y = top - base_top
        else:
            left = base_left + self._pan_x
            top = base_top + self._pan_y

        if new_w <= canvas_w:
            left = base_left
            self._pan_x = 0.0
        else:
            left = min(0.0, max(canvas_w - new_w, left))
            self._pan_x = left - base_left
        if new_h <= canvas_h:
            top = base_top
            self._pan_y = 0.0
        else:
            top = min(0.0, max(canvas_h - new_h, top))
            self._pan_y = top - base_top

        self._image_left = left
        self._image_top = top
        self._rendered_size = (new_w, new_h)

        # 只重采样当前可见区域。即使1000%，内存也约等于窗口大小，而不是
        # 10倍宽×10倍高的整图，避免大图缩放时卡死。
        visible_left = max(0, int(-left))
        visible_top = max(0, int(-top))
        visible_right = min(new_w, int(canvas_w - left + 1))
        visible_bottom = min(new_h, int(canvas_h - top + 1))
        if visible_right > visible_left and visible_bottom > visible_top:
            crop_box = (
                visible_left / self.scale_factor,
                visible_top / self.scale_factor,
                visible_right / self.scale_factor,
                visible_bottom / self.scale_factor,
            )
            crop = self._orig_image.crop(crop_box)
            target_size = (visible_right - visible_left, visible_bottom - visible_top)
            if crop.size != target_size:
                crop = crop.resize(target_size, Image.Resampling.LANCZOS)
            self._display_photo = ImageTk.PhotoImage(crop)
            self._canvas_img_id = self.canvas.create_image(
                max(0, int(left)), max(0, int(top)), anchor=tk.NW,
                image=self._display_photo
            )
        self.canvas.config(scrollregion=(0, 0, canvas_w, canvas_h))

        pct = int(round(self.zoom_level * 100))
        self.label_zoom.config(text=f"{pct}%")
    
    # ==================== 缩放 ====================
    
    def _pointer_anchor(self, pointer_x: float, pointer_y: float):
        """返回鼠标下方在当前图像中的归一化坐标。"""
        rendered_w, rendered_h = self._rendered_size
        image_x = (pointer_x - self._image_left) / max(rendered_w, 1)
        image_y = (pointer_y - self._image_top) / max(rendered_h, 1)
        return (pointer_x, pointer_y,
                min(max(image_x, 0.0), 1.0),
                min(max(image_y, 0.0), 1.0))

    def _set_zoom(self, zoom: float, pointer=None):
        """设置相对窗口适配的缩放值，并可围绕鼠标位置缩放。"""
        zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(zoom)))
        if abs(zoom - self.zoom_level) < 1e-6:
            return
        anchor = self._pointer_anchor(*pointer) if pointer is not None else None
        self.zoom_level = zoom
        self._update_display(anchor=anchor)

    def _zoom_by_factor(self, factor: float, pointer=None):
        self._set_zoom(self.zoom_level * factor, pointer=pointer)
    
    def _fit_to_window(self):
        """缩放至适合窗口（图片完整可见）"""
        if self._orig_image is None:
            return
        canvas_w = self.canvas.winfo_width()
        canvas_h = self.canvas.winfo_height()
        if canvas_w <= 10 or canvas_h <= 10:
            return
        
        self.zoom_level = self.MIN_ZOOM
        self._pan_x = self._pan_y = 0.0
        self._update_display()

    def _show_original_pixels(self):
        """以一个屏幕像素对应一个图片像素显示（受100%~1000%限制）。"""
        fit_scale = self._calculate_fit_scale()
        self._set_zoom(1.0 / max(fit_scale, 0.0001))

    def _wheel_factor(self, event_delta: float) -> float:
        """根据滚轮速度返回倍率：慢转约两圈、快转约半圈达到10倍。"""
        now = time.monotonic()
        elapsed = None if self._last_wheel_time is None else now - self._last_wheel_time
        self._last_wheel_time = now
        if elapsed is None:
            steps_per_decade = 12.0
        elif elapsed <= 0.045:
            steps_per_decade = 6.0
        elif elapsed >= 0.16:
            steps_per_decade = 24.0
        else:
            ratio = (elapsed - 0.045) / (0.16 - 0.045)
            steps_per_decade = 6.0 + ratio * 18.0
        magnitude = abs(event_delta) / 120.0 if abs(event_delta) >= 120 else abs(event_delta)
        magnitude = min(max(magnitude, 1.0), 4.0)
        return 10.0 ** (magnitude / steps_per_decade)
    
    def _on_mousewheel(self, event):
        """Windows鼠标滚轮缩放"""
        factor = self._wheel_factor(event.delta)
        if event.delta < 0:
            factor = 1.0 / factor
        self._zoom_by_factor(factor, pointer=(event.x, event.y))
        return 'break'
    
    def _on_mousewheel_up(self, event):
        """Linux滚轮上（放大）"""
        self._zoom_by_factor(self._wheel_factor(1), pointer=(event.x, event.y))
        return 'break'
    
    def _on_mousewheel_down(self, event):
        """Linux滚轮下（缩小）"""
        self._zoom_by_factor(1.0 / self._wheel_factor(-1),
                             pointer=(event.x, event.y))
        return 'break'

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
        # 保持用户看到的100%~1000%级别；窗口尺寸变化时重新计算适配基准。
        self._update_display()
    
    # ==================== 拖动平移 ====================
    
    def _on_drag_start(self, event):
        """记录起点；移动多少像素，图片就移动多少像素。"""
        self._drag_start = (event.x, event.y)
        self.canvas.config(cursor='fleur')  # 移动光标
    
    def _on_drag_move(self, event):
        """拖动平移图片"""
        if self._drag_start is None:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._pan_x += dx
        self._pan_y += dy
        self._drag_start = (event.x, event.y)
        self._update_display()
    
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
        self.settings = load_app_settings()
        self._active_theme = None
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
        self.capture_segments = []
        self.selection_start = 1
        self.selection_end = None
        self.all_groups = []
        self._selected_processed_count = 0
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

        # ===== 无损快速分类队列 =====
        # UI只负责冻结“用户当时看到的那一组”的快照并立即前进；复制、EXIF、CSV
        # 全部由单一后台线程按点击顺序完成，避免重复点击造成跳组或记录丢失。
        self._classify_queue = queue.Queue()
        self._classify_result_queue = queue.Queue()
        self._pending_group_indices = set()
        self._classify_poll_after_id = None
        self._classify_worker_thread = threading.Thread(
            target=self._classification_worker, daemon=True
        )
        self._classify_worker_thread.start()
        
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
        self._video_generation = 0        # 防止已切组的旧线程向新面板写帧
        self._retired_video_threads = []  # 仍在退出的慢解码器（限制并发防资源耗尽）
        
        # ===== UI 状态 =====
        self._panels = []                 # MediaPanel 列表（4个）
        self._resize_after_id = None      # 窗口调整大小时的防抖 ID
        self._panels_ready = False        # 面板是否已完成首次渲染
        self._preview_generation = 0
        # 图片与视频首帧分离：慢视频不再占用图片线程。图片用优先队列，
        # 当前组优先于下一组的后台预读。
        self._image_preview_queue = queue.PriorityQueue()
        self._video_preview_queue = queue.Queue(maxsize=32)
        self._preview_result_queue = queue.Queue()
        self._preview_poll_after_id = None
        self._preview_task_sequence = 0
        self._preview_pending = set()
        self._preview_completed_panels = set()
        self._preview_pending_images = 0
        self._preview_cache = OrderedDict()
        self._preview_cache_lock = threading.Lock()
        self._pending_video_start = None
        self._autoplay_video_preview_ready = False
        self._video_start_after_id = None
        for _ in range(IMAGE_PREVIEW_WORKERS):
            threading.Thread(
                target=self._preview_worker,
                args=(self._image_preview_queue, 'image'),
                daemon=True,
            ).start()
        for _ in range(VIDEO_PREVIEW_WORKERS):
            threading.Thread(
                target=self._preview_worker,
                args=(self._video_preview_queue, 'video'),
                daemon=True,
            ).start()
        
        # ===== 日志系统 =====
        self.logger = None
        self._setup_logging()
        
        # ===== 创建主窗口 =====
        self.root = tk.Tk()
        self.root.title(f"WildCam Sorter v{APP_VERSION} - 野外相机数据分类工具")
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        main_w = min(1800, max(1000, screen_w - 40))
        main_h = min(1000, max(700, screen_h - 80))
        self.root.geometry(
            f"{main_w}x{main_h}+{max(0, (screen_w-main_w)//2)}+"
            f"{max(0, (screen_h-main_h)//2 - 10)}"
        )
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
        if hasattr(self, 'settings'):
            self._apply_theme(self.settings.get('theme', 'system'), persist=False)
        self.root.after(5000, self._poll_system_theme)
        
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
        self.btn_open = create_button(
            toolbar, text="⚙ 路径与模式", font=("微软雅黑", 10),
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

        # 系统设置独立放在右上角；路径与模式仍保留在左上角。
        self.btn_settings = create_button(
            toolbar, text="⚙", font=("微软雅黑", 12),
            bg='#455A64', fg='white', activebackground='#607D8B',
            relief=tk.FLAT, cursor='hand2', command=self._show_settings,
            padx=9, pady=2
        )
        self.btn_settings.pack(side=tk.RIGHT, padx=(3, 8), pady=3)

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
        if len(self.capture_segments) > 1:
            self.label_capture_mode.config(text=f"模式：分段模式（{len(self.capture_segments)} 段）")
        else:
            order_text = ORDER_DISPLAY_NAMES.get(self.media_order, '未设置')
            self.label_capture_mode.config(
                text=f"模式：{self.photo_count}照片 + {self.video_count}视频｜{order_text}"
            )

    def _resolved_theme(self, mode: str) -> str:
        if mode == 'system':
            return 'dark' if system_uses_dark_theme() else 'light'
        return mode if mode in ('light', 'dark') else 'dark'

    def _apply_theme(self, mode: str, persist: bool = True):
        """即时切换现有Tk控件颜色，并保存用户选择。"""
        resolved = self._resolved_theme(mode)
        reverse = {value.upper(): key for key, value in THEME_DARK_TO_LIGHT.items()}
        forward = {key.upper(): value for key, value in THEME_DARK_TO_LIGHT.items()}

        def convert(value):
            key = str(value).upper()
            dark = reverse.get(key, key)
            return forward.get(dark, value) if resolved == 'light' else dark

        def visit(widget):
            for option in ('background', 'foreground', 'activebackground',
                           'activeforeground', 'highlightbackground'):
                try:
                    current = widget.cget(option)
                    converted = convert(current)
                    if converted != current:
                        widget.configure(**{option: converted})
                except (tk.TclError, AttributeError):
                    pass
            # 主题转换可能再次写回白色 foreground；Aqua 的按钮表面仍是浅色，
            # 因此每次切换主题后都重新保证 macOS 按钮文字有足够对比度。
            if isinstance(widget, tk.Button):
                ensure_macos_button_readability(widget)
            for child in widget.winfo_children():
                visit(child)

        visit(self.root)
        self._active_theme = resolved
        self.settings['theme'] = mode
        if persist:
            try:
                save_app_settings(self.settings)
            except OSError as exc:
                self._log(f"无法保存设置: {exc}", 'warning')

    def _poll_system_theme(self):
        if self._closing:
            return
        if self.settings.get('theme') == 'system':
            resolved = self._resolved_theme('system')
            if resolved != self._active_theme:
                self._apply_theme('system', persist=False)
        self.root.after(5000, self._poll_system_theme)

    def _show_settings(self):
        window = tk.Toplevel(self.root)
        window.title("系统设置")
        window.geometry("520x330")
        window.transient(self.root)
        window.configure(bg=COLOR_BG)
        tk.Label(window, text="⚙ 系统设置", font=("微软雅黑", 15, "bold"),
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(pady=(18, 14))
        theme_row = tk.Frame(window, bg=COLOR_BG)
        theme_row.pack(fill=tk.X, padx=35, pady=8)
        tk.Label(theme_row, text="主题", width=10, anchor='w',
                 bg=COLOR_BG, fg=COLOR_TEXT).pack(side=tk.LEFT)
        display_to_key = {v: k for k, v in THEME_DISPLAY_NAMES.items()}
        theme_var = tk.StringVar(value=THEME_DISPLAY_NAMES.get(
            self.settings.get('theme', 'system'), THEME_DISPLAY_NAMES['system']))
        combo = ttk.Combobox(theme_row, textvariable=theme_var,
                             values=list(THEME_DISPLAY_NAMES.values()),
                             state='readonly', width=18)
        combo.pack(side=tk.LEFT)
        combo.bind('<<ComboboxSelected>>', lambda _event: self._apply_theme(
            display_to_key[theme_var.get()]
        ))

        info = tk.LabelFrame(window, text=" 帮助 ", bg=COLOR_BG, fg=COLOR_TEXT,
                             padx=12, pady=12)
        info.pack(fill=tk.X, padx=35, pady=15)
        create_button(info, text="教程（README）", command=self._show_tutorial,
                  bg='#1565C0', fg='white', relief=tk.FLAT, padx=12).pack(
                      side=tk.LEFT, padx=5)
        create_button(info, text="关于", command=lambda: messagebox.showinfo(
            "关于", f"WildCam Sorter v{APP_VERSION}\n野外相机照片/视频分类工具",
            parent=window), bg='#455A64', fg='white', relief=tk.FLAT,
            padx=12).pack(side=tk.LEFT, padx=5)
        create_button(info, text="联系作者", command=lambda: messagebox.showinfo(
            "联系作者", "作者：S-Y-Chu\n邮箱：siyuanzhu.cn@gmail.com",
            parent=window), bg='#455A64', fg='white', relief=tk.FLAT,
            padx=12).pack(side=tk.LEFT, padx=5)
        tk.Label(window,
                 text="性能设置已自动优化：后台缩略图、延迟视频解码、串行无损分类队列。",
                 bg=COLOR_BG, fg=COLOR_TEXT_DIM, wraplength=440).pack(pady=8)
        self._apply_theme(self.settings.get('theme', 'system'), persist=False)

    def _show_tutorial(self):
        window = tk.Toplevel(self.root)
        window.title("使用教程")
        window.geometry("900x700")
        text_widget = tk.Text(window, wrap=tk.WORD, padx=16, pady=14)
        scrollbar = tk.Scrollbar(window, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        text_widget.pack(fill=tk.BOTH, expand=True)
        candidates = [
            os.path.join(getattr(sys, '_MEIPASS', ''), 'README.md'),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'README.md'),
        ]
        content = "WildCam Sorter 使用教程\n\nREADME.md 未找到，请确认压缩包已完整解压。"
        for path in candidates:
            if path and os.path.isfile(path):
                try:
                    with open(path, 'r', encoding='utf-8') as handle:
                        content = handle.read()
                    break
                except OSError:
                    pass
        text_widget.insert('1.0', content)
        text_widget.configure(state=tk.DISABLED)
    
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
        self.btn_empty = create_button(
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
        self.btn_multi = create_button(
            left_frame, text="📋 多类别", font=("微软雅黑", 11, "bold"),
            bg='#6A1B9A', fg='white', activebackground='#9C27B0',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=8,
            command=self._toggle_multi_mode
        )
        self.btn_multi.pack(side=tk.LEFT, padx=4)
        
        # 新物种按钮
        self.btn_new = create_button(
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
        self.btn_prev = create_button(
            right_frame, text="◀ 上一组", font=("微软雅黑", 10),
            bg=COLOR_BUTTON_NAV, fg='white', activebackground='#616161',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._prev_group
        )
        self.btn_prev.pack(side=tk.LEFT, padx=3)

        # 按照片/视频文件序号跳转（放在上一组与下一组之间）
        self.btn_jump_to_media = create_button(
            right_frame, text="跳转至", font=("微软雅黑", 10),
            bg='#6A1B9A', fg='white', activebackground='#8E24AA',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._prompt_jump_to_media
        )
        self.btn_jump_to_media.pack(side=tk.LEFT, padx=3)
        
        # 下一组
        self.btn_next = create_button(
            right_frame, text="下一组 ▶", font=("微软雅黑", 10),
            bg=COLOR_BUTTON_NAV, fg='white', activebackground='#616161',
            relief=tk.FLAT, cursor='hand2', padx=10, pady=6,
            command=self._next_group
        )
        self.btn_next.pack(side=tk.LEFT, padx=3)
        
        # 跳至未处理按钮
        self.btn_jump = create_button(
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
        self.status_frame = tk.Frame(self.root, bg=COLOR_TOOLBAR, height=38)
        self.status_frame.grid(row=3, column=0, sticky='ew')
        self.status_frame.grid_propagate(False)
        
        # 进度条 Canvas
        self.progress_canvas = tk.Canvas(
            self.status_frame, bg=COLOR_TOOLBAR, height=5,
            highlightthickness=0
        )
        self.progress_canvas.pack(fill=tk.X)
        
        self.label_remaining = tk.Label(
            self.status_frame, text="", font=("微软雅黑", 8),
            bg=COLOR_TOOLBAR, fg='#AAAAAA', anchor=tk.W, justify=tk.LEFT
        )
        self.label_remaining.pack(side=tk.LEFT, padx=(10, 18))

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
                               photo_count=None, video_count=None, media_order=None,
                               segments=None, selection_start=1, selection_end=None):
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
        self.label_status.config(text="正在后台读取数据，可随时取消…", fg='#80CBC4')

        source_dir = os.path.abspath(source_dir)
        target_dir = os.path.abspath(target_dir)
        photo_count = self.photo_count if photo_count is None else photo_count
        video_count = self.video_count if video_count is None else video_count
        media_order = self.media_order if media_order is None else media_order
        segments = segments or [{
            'start': 1, 'end': None, 'photo_count': photo_count,
            'video_count': video_count, 'order': media_order,
        }]

        def report(phase, visited, media_count):
            self._scan_queue.put((token, 'progress', phase, visited, media_count))

        def worker():
            try:
                parent_dir = os.path.dirname(source_dir)
                scanned = scan_and_group_files(
                    source_dir, photo_count, video_count, media_order,
                    progress_callback=report, cancel_event=cancel_event
                )
                groups = RangedMediaGroupSequence(
                    source_dir, scanned.file_names, segments,
                    selection_start, selection_end
                )
                all_groups = groups.all_view()
                if cancel_event.is_set():
                    raise ScanCancelled()

                progress_file = os.path.join(parent_dir, '.wildcam_progress.json')
                processed_groups, class_history = load_progress_snapshot(progress_file)

                # 每次都核对输出目录，才能发现其他人手工复制的新分类。
                # 该扫描和CSV补写均在工作线程，不会冻住主窗口。
                species_list, existing_files = scan_classified_media(
                    target_dir, os.path.basename(source_dir), report, cancel_event
                )
                backfilled_count = backfill_manual_csv(
                    source_dir, target_dir, existing_files, report, cancel_event
                )

                processed_groups, class_history, newly_found = merge_presorted_progress(
                    all_groups, parent_dir, target_dir, existing_files,
                    processed_groups, class_history, report, cancel_event
                )

                mismatch_count = 0
                first_unprocessed = 0
                skipped_count = 0
                selected_processed_count = 0
                total_groups = len(groups)
                for index in range(total_groups):
                    if index % 256 == 0 and cancel_event.is_set():
                        raise ScanCancelled()
                    group_names = [os.path.basename(path) for path in groups[index]]
                    mode = groups.mode_for_group(index)
                    expected_types = expected_capture_types(
                        mode['photo_count'], mode['video_count'], mode['order']
                    )
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
                    if rel_path in processed_groups:
                        selected_processed_count += 1
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
                    'all_groups': all_groups,
                    'processed_groups': processed_groups,
                    'class_history': class_history,
                    'species_list': species_list,
                    'mismatch_count': mismatch_count,
                    'first_unprocessed': first_unprocessed,
                    'skipped_count': skipped_count,
                    'newly_found': newly_found,
                    'backfilled_count': backfilled_count,
                    'selected_processed_count': selected_processed_count,
                    'photo_count': photo_count,
                    'video_count': video_count,
                    'media_order': media_order,
                    'segments': groups.segments,
                    'selection_start': groups.selection_start,
                    'selection_end': groups.selection_end,
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
        self.all_groups = result['all_groups']
        self.capture_segments = result['segments']
        self.selection_start = result['selection_start']
        self.selection_end = result['selection_end']
        self.processed_groups = result['processed_groups']
        self.class_history = result['class_history']
        self.species_list = result['species_list']
        self.group_pattern_mismatch_count = result['mismatch_count']
        self._selected_processed_count = result['selected_processed_count']
        self.current_group_index = -1
        self._panels_ready = False

        self.label_folder.config(text=f"📁 {self.source_dir}")
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
            text=(f"文件夹共 {len(self.all_groups):,} 组 / {len(self.groups.file_names):,} 个文件"
                  f"｜已选 {len(self.groups):,} 组 / {self.groups.total_files:,} 个文件")
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
        if result.get('backfilled_count'):
            self._log(f"为人工分类补写了 {result['backfilled_count']} 行CSV记录")

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
        if self._pending_group_indices:
            messagebox.showinfo(
                "请稍候",
                f"后台仍在保存 {len(self._pending_group_indices)} 组分类。\n"
                "保存完成后再切换路径，可保证记录不会写错文件夹。",
                parent=self.root
            )
            return
        dlg = PathSelectDialog(
            self.root,
            initial_input=self._pending_input or self.source_dir or "",
            initial_output=self.target_dir or "",
            initial_photo_count=self.photo_count,
            initial_video_count=self.video_count,
            initial_order=self.media_order,
            initial_segments=self.capture_segments or None,
            initial_selection=(self.selection_start, self.selection_end)
        )
        self.root.wait_window(dlg.window)  # 阻塞直到对话框关闭
        
        if dlg.result:
            in_path, out_path, segments, selection_start, selection_end = dlg.result
            first = segments[0]
            self._start_background_load(
                in_path, out_path, first['photo_count'], first['video_count'],
                first['order'], segments, selection_start, selection_end
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
        """兼容旧调用：输出路径统一由“路径与模式”设置页管理。"""
        self._show_path_dialog()
    
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
        self._preview_generation += 1
        preview_generation = self._preview_generation
        if self._video_start_after_id is not None:
            try:
                self.root.after_cancel(self._video_start_after_id)
            except tk.TclError:
                pass
            self._video_start_after_id = None
        for preview_queue in (self._image_preview_queue, self._video_preview_queue):
            try:
                while True:
                    preview_queue.get_nowait()
            except queue.Empty:
                pass
        self._preview_pending.clear()
        self._preview_completed_panels.clear()
        self._preview_pending_images = sum(
            1 for path in self.groups[group_index]
            if not is_video_file(os.path.basename(path))
        )
        self._pending_video_start = None
        self._autoplay_video_preview_ready = False
        
        self.current_group_index = group_index
        self.current_group_files = self.groups[group_index]
        if hasattr(self.groups, 'mode_for_group'):
            mode = self.groups.mode_for_group(group_index)
            if mode:
                self.label_capture_mode.config(
                    text=(f"当前模式：{mode['photo_count']}照片 + {mode['video_count']}视频｜"
                          f"{ORDER_DISPLAY_NAMES.get(mode['order'], '')}")
                )
        
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
        
        # 先瞬间切换全部面板身份，再由后台线程解码缩略图。这样大图和慢视频
        # 不会阻塞分类按钮；只有用户在本组停留片刻时才启动实时视频。
        video_started = False
        for panel_idx in range(4):
            panel = self._panels[panel_idx]
            
            if panel_idx < len(self.current_group_files):
                file_path = self.current_group_files[panel_idx]
                filename = os.path.basename(file_path)
                panel.label_text = self._media_label_for_index(panel_idx)

                panel.display_loading(file_path, panel.label_text)
                self._queue_preview(panel, file_path, preview_generation)
                if is_video_file(filename) and not video_started:
                    video_started = True
                    self._pending_video_start = (preview_generation, file_path, panel)
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
                op.display_loading(file_path, op.label_text)
                self._queue_preview(op, file_path, preview_generation)
                if is_video_file(os.path.basename(file_path)) and not video_started:
                    video_started = True
                    self._pending_video_start = (preview_generation, file_path, op)
                op.set_selected(self.selected_flags[file_idx])
                self.overflow_panels.append(op)
        else:
            # 隐藏溢出行
            self.overflow_frame.grid_forget()
            self.display_frame.grid_rowconfigure(2, weight=0)

        # 视频首帧与图片均完成后再打开实时解码，避免同一视频被同时打开两次。
        # 极慢或损坏文件由兜底定时器放行，不能让自动播放永久等待。
        if self._pending_video_start is not None:
            self._video_start_after_id = self.root.after(
                VIDEO_AUTOPLAY_FALLBACK_MS,
                lambda g=preview_generation: self._maybe_start_pending_video(g, force=True)
            )

        # 图片线程空闲时预读下一组。缓存只保留少量缩略图，不随500G目录增长。
        self._queue_next_group_previews(group_index, preview_generation)
        
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

    def _next_preview_sequence(self) -> int:
        self._preview_task_sequence += 1
        return self._preview_task_sequence

    def _preview_cache_get(self, cache_key):
        with self._preview_cache_lock:
            image = self._preview_cache.pop(cache_key, None)
            if image is not None:
                self._preview_cache[cache_key] = image
                return image.copy()
        return None

    def _preview_cache_put(self, cache_key, image):
        with self._preview_cache_lock:
            self._preview_cache.pop(cache_key, None)
            self._preview_cache[cache_key] = image.copy()
            while len(self._preview_cache) > PREVIEW_CACHE_LIMIT:
                self._preview_cache.popitem(last=False)

    def _queue_preview(self, panel: MediaPanel, file_path: str, generation: int):
        """提交当前组缩略图；图片与视频使用互不阻塞的工作队列。"""
        width, height = panel._calc_display_size()
        width, height = max(width, 320), max(height, 200)
        media_kind = 'video' if is_video_file(os.path.basename(file_path)) else 'image'
        pending_key = (generation, panel.index, file_path)
        self._preview_pending.add(pending_key)

        if media_kind == 'image':
            cache_key = (file_path, width, height)
            cached = self._preview_cache_get(cache_key)
            if cached is not None:
                self._preview_result_queue.put(
                    (generation, panel.index, file_path, cached, None, media_kind)
                )
            else:
                job = (
                    0, self._next_preview_sequence(), generation, panel.index,
                    file_path, width, height, False,
                )
                self._image_preview_queue.put_nowait(job)
        else:
            job = (generation, panel.index, file_path, width, height, False)
            try:
                self._video_preview_queue.put_nowait(job)
            except queue.Full:
                self._preview_result_queue.put(
                    (generation, panel.index, file_path, None,
                     '视频预览队列已满', media_kind)
                )
        if self._preview_poll_after_id is None:
            self._preview_poll_after_id = self.root.after(20, self._poll_preview_results)

    def _queue_next_group_previews(self, group_index: int, generation: int):
        """低优先级预读下一组图片，切组后可直接使用内存中的小缩略图。"""
        next_index = group_index + 1
        if next_index >= len(self.groups):
            return
        default_width, default_height = self._panels[0]._calc_display_size()
        width, height = max(default_width, 320), max(default_height, 200)
        for file_path in self.groups[next_index]:
            if is_video_file(os.path.basename(file_path)):
                continue
            cache_key = (file_path, width, height)
            with self._preview_cache_lock:
                already_cached = cache_key in self._preview_cache
            if already_cached:
                continue
            job = (
                10, self._next_preview_sequence(), generation, -1,
                file_path, width, height, True,
            )
            self._image_preview_queue.put_nowait(job)

    @staticmethod
    def _decode_image_preview(file_path: str, width: int, height: int):
        """按目标尺寸尽早降采样JPEG，避免为小预览完整展开超大原图。"""
        with Image.open(file_path) as source:
            try:
                source.draft('RGB', (width, height))
            except (AttributeError, OSError, ValueError):
                pass
            source.load()
            image = ImageOps.exif_transpose(source).copy()
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        return image

    def _preview_worker(self, work_queue, media_kind: str):
        """后台读取缩略图；图片和视频各自使用独立队列。"""
        while True:
            job = work_queue.get()
            if media_kind == 'image':
                _, _, generation, panel_index, file_path, width, height, preload = job
            else:
                generation, panel_index, file_path, width, height, preload = job
            if not preload and generation != self._preview_generation:
                continue
            image = None
            error = None
            cap = None
            try:
                if media_kind == 'video':
                    cap = open_video_capture(file_path)
                    if cap is None:
                        raise OSError('无法读取视频首帧')
                    ok, frame = cap.read()
                    if not ok:
                        raise OSError('无法读取视频首帧')
                    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    image.thumbnail((width, height), Image.Resampling.LANCZOS)
                else:
                    image = self._decode_image_preview(file_path, width, height)
            except Exception as exc:
                error = str(exc)
                image = None
            finally:
                if cap is not None:
                    cap.release()
            if preload:
                if image is not None:
                    self._preview_cache_put((file_path, width, height), image)
                continue
            if generation != self._preview_generation:
                continue
            self._preview_result_queue.put(
                (generation, panel_index, file_path, image, error, media_kind)
            )

    def _panel_for_index(self, panel_index: int):
        if panel_index < 4:
            return self._panels[panel_index]
        extra = panel_index - 4
        return self.overflow_panels[extra] if extra < len(self.overflow_panels) else None

    def _poll_preview_results(self):
        """只显示当前组结果，过时任务直接释放，避免高速浏览时回闪。"""
        self._preview_poll_after_id = None
        try:
            while True:
                generation, panel_index, file_path, image, error, media_kind = (
                    self._preview_result_queue.get_nowait()
                )
                if generation != self._preview_generation:
                    continue
                pending_key = (generation, panel_index, file_path)
                self._preview_pending.discard(pending_key)
                panel = self._panel_for_index(panel_index)
                if panel is None or panel.file_path != file_path:
                    continue
                if image is None:
                    kind = '视频' if is_video_file(os.path.basename(file_path)) else '图片'
                    panel.media_label.config(image='', text=f"⚠ 无法预览{kind}")
                else:
                    photo = ImageTk.PhotoImage(image)
                    panel._photo = photo
                    panel.media_label.config(image=photo, text='')

                if panel_index not in self._preview_completed_panels:
                    self._preview_completed_panels.add(panel_index)
                    if media_kind == 'image':
                        self._preview_pending_images = max(
                            0, self._preview_pending_images - 1
                        )
                pending_video = self._pending_video_start
                if (media_kind == 'video' and pending_video is not None
                        and pending_video[0] == generation
                        and pending_video[1] == file_path):
                    self._autoplay_video_preview_ready = True
                self._maybe_start_pending_video(generation)
        except queue.Empty:
            pass
        # 不能只看队列是否为空：最后一个任务可能已被工作线程取走、仍在解码。
        # 只要当前组还有未返回的面板，就必须继续轮询结果。
        if (self._preview_pending or not self._preview_result_queue.empty()) \
                and not self._closing:
            self._preview_poll_after_id = self.root.after(20, self._poll_preview_results)

    def _maybe_start_pending_video(self, generation: int, force: bool = False):
        pending = self._pending_video_start
        if pending is None or pending[0] != generation:
            return
        if not force and (
                self._preview_pending_images > 0
                or not self._autoplay_video_preview_ready):
            return
        self._pending_video_start = None
        if self._video_start_after_id is not None:
            try:
                self.root.after_cancel(self._video_start_after_id)
            except tk.TclError:
                pass
            self._video_start_after_id = None
        self._start_video_if_current(*pending)

    def _start_video_if_current(self, generation: int, file_path: str,
                                panel: MediaPanel):
        """用户确实停留在该组时才开实时解码，快速掠过的组只加载首帧。"""
        self._retired_video_threads = [
            thread for thread in self._retired_video_threads if thread.is_alive()
        ]
        if (generation == self._preview_generation
                and panel.file_path == file_path and not self._closing
                and len(self._retired_video_threads) < 2):
            self._load_video(file_path, panel)
    
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
        self._video_generation += 1
        generation = self._video_generation
        self._video_stop = threading.Event()
        self._video_queue = queue.Queue(maxsize=2)
        stop_event = self._video_stop
        frame_queue = self._video_queue
        self._video_thread = threading.Thread(
            target=self._video_decode_worker,
            args=(video_path, stop_event, frame_queue, generation),
            daemon=True
        )
        self._video_thread.start()
        
        # 启动显示循环（UI线程只取帧显示，不解码）
        self.video_frame_delay = 50  # 20fps显示
        self._update_video_frame()
    
    def _video_decode_worker(self, video_path: str, stop_event: threading.Event,
                             frame_queue: queue.Queue, generation: int):
        """
        视频解码线程：持续读帧转RGB放入队列，循环播放。
        所有可能阻塞的解码操作都在此线程，UI线程只消费队列。
        """
        cap = None
        av_container = None
        av_iter = None
        fps = 25
        
        try:
            # ---- 方案1: OpenCV（按系统选择FFmpeg/DirectShow/AVFoundation） ----
            cap = open_video_capture(video_path)
            
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
                self.root.after(
                    0, lambda: self._video_load_failed(video_path, generation)
                )
                return
            
            # ---- 解码循环 ----
            fail_count = 0  # 连续读取失败计数，防止死循环
            while not stop_event.is_set():
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
                    frame_queue.put_nowait(frame_rgb)
                except queue.Full:
                    try:
                        frame_queue.get_nowait()
                        frame_queue.put_nowait(frame_rgb)
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
    
    def _video_load_failed(self, video_path: str, generation: int = None):
        """视频完全无法打开时显示错误提示"""
        if (not self.video_playing
                or (generation is not None and generation != self._video_generation)):
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
        """停止视频播放；只发退出信号，不在UI线程等待慢速解码器。"""
        self.video_playing = False
        self._video_generation += 1
        if self.video_after_id:
            self.root.after_cancel(self.video_after_id)
            self.video_after_id = None
        # 解码线程是daemon且持有自己的Event/Queue。某些损坏视频的read()会阻塞，
        # 因此这里绝不能join，否则每次切组都可能卡住整整2秒。
        if self._video_stop is not None:
            self._video_stop.set()
        if self._video_thread is not None and self._video_thread.is_alive():
            self._retired_video_threads.append(self._video_thread)
        self._video_thread = None
        self._video_stop = None
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
        if hasattr(self, 'settings'):
            self._apply_theme(self.settings.get('theme', 'system'), persist=False)
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
            # 一个事务同时写入多个类别，避免旧实现重复撤销同一组。
            self._classify_files(
                target_species=tuple(sorted(self.multi_selected, key=natural_sort_key))
            )
            # 退出多类模式
            self.multi_mode = False
            self.multi_selected.clear()
            self.btn_multi.config(text="📋 多类别", bg='#6A1B9A')
            self._update_multi_buttons()
            self.label_status.config(
                text=f"✅ 已分类到 {selected_count} 个类别", fg='#4CAF50'
            )
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
        if self._scan_thread is not None and self._scan_thread.is_alive():
            self.label_status.config(text="正在切换数据文件夹，请等待扫描完成", fg='#FFB74D')
            return
        if not self.current_group_files or not self.target_dir:
            self.label_status.config(
                text="⚠ 错误：未加载数据或未设置目标文件夹",
                fg='#FF6B6B'
            )
            return
        
        group_index = self.current_group_index
        if group_index in self._pending_group_indices:
            return
        rel_path = self._get_group_rel_path(group_index)
        categories = () if target_species is None else (
            tuple(target_species) if isinstance(target_species, (tuple, list, set))
            else (target_species,)
        )
        job = {
            'group_index': group_index,
            'rel_path': rel_path,
            'files': tuple(self.current_group_files),
            'selected': tuple(self.selected_flags),
            'per_file_species': {
                index: tuple(sorted(values, key=natural_sort_key))
                for index, values in self.per_file_species.items()
            },
            'categories': tuple(categories),
            'target_dir': self.target_dir,
            'point_name': os.path.basename(self.source_dir) if self.source_dir else '',
            'old_dest_files': tuple(
                self.class_history.get(rel_path, {}).get('dest_files', [])
            ),
            'replace_existing': rel_path in self.processed_groups,
        }
        self._pending_group_indices.add(group_index)
        self._classify_queue.put(job)
        self._log(
            f"已排队分类第{group_index + 1}组 → "
            f"{'、'.join(categories) if categories else '空拍'}"
        )
        self.label_status.config(
            text=f"⏳ 第 {group_index + 1} 组已进入分类队列（队列 {self._classify_queue.qsize()}）",
            fg='#80CBC4'
        )
        self._schedule_classification_poll(1)

        # 只允许一次点击推进一次；快点时下一次事件面对的必然是下一组。
        if auto_advance:
            self._auto_advance()

    @staticmethod
    def _job_species_for_file(job: dict, index: int) -> tuple:
        labels = job['per_file_species'].get(index)
        if labels:
            return tuple(labels)
        if not job['categories']:
            return ('空拍',)
        if index < len(job['selected']) and job['selected'][index]:
            return tuple(job['categories'])
        return ('空拍',)

    def _classification_worker(self):
        """严格按点击顺序执行复制和CSV事务，永不接触Tk控件。"""
        while True:
            job = self._classify_queue.get()
            if job is None:
                return
            errors = []
            dest_files = []
            staged_files = []
            copied_species = 0
            copied_empty = 0
            try:
                old_paths = {os.path.abspath(path) for path in job['old_dest_files']}
                for index, file_path in enumerate(job['files']):
                    filename = os.path.basename(file_path)
                    for category in self._job_species_for_file(job, index):
                        dest_dir = os.path.join(job['target_dir'], category)
                        try:
                            os.makedirs(dest_dir, exist_ok=True)
                            dest_path = os.path.join(dest_dir, filename)
                            if (os.path.exists(dest_path)
                                    and os.path.abspath(dest_path) not in old_paths):
                                base, ext = os.path.splitext(filename)
                                counter = 1
                                while os.path.exists(
                                        os.path.join(dest_dir, f"{base}_{counter}{ext}")):
                                    counter += 1
                                dest_path = os.path.join(dest_dir, f"{base}_{counter}{ext}")
                            temp_path = (
                                dest_path + f".wildcam-tmp-{threading.get_ident()}-{time.time_ns()}"
                            )
                            shutil.copy2(file_path, temp_path)
                            staged_files.append((temp_path, dest_path))
                            if category == '空拍':
                                copied_empty += 1
                            else:
                                copied_species += 1
                        except Exception as exc:
                            errors.append(f"{filename}: {exc}")

                if errors:
                    raise OSError('本组有文件复制失败，已回滚，未写入分类记录')

                # 所有源文件均已成功复制到临时文件后再提交，避免半组成功。
                for temp_path, dest_path in staged_files:
                    os.replace(temp_path, dest_path)
                    dest_files.append(dest_path)
                final_paths = {os.path.abspath(path) for path in dest_files}
                for old_path in old_paths - final_paths:
                    try:
                        if os.path.isfile(old_path):
                            os.remove(old_path)
                    except OSError as exc:
                        errors.append(f"删除旧分类 {os.path.basename(old_path)}: {exc}")
                self._write_csv_snapshot(job)
            except Exception as exc:
                if str(exc) not in errors:
                    errors.append(str(exc))
                for temp_path, _dest_path in staged_files:
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except OSError:
                        pass
                if not dest_files:
                    copied_species = copied_empty = 0
                self._log(f"后台分类失败: {exc}\n{traceback.format_exc()}", 'error')

            species_label = '、'.join(job['categories']) if job['categories'] else '空拍'
            self._classify_result_queue.put({
                'job': job, 'errors': errors, 'dest_files': dest_files,
                'copied_species': copied_species, 'copied_empty': copied_empty,
                'species_label': species_label,
            })

    def _poll_classification_results(self):
        """在主线程合并后台事务结果；一次轮询可消费多个高速点击。"""
        self._classify_poll_after_id = None
        if self._closing:
            return
        handled = False
        try:
            while True:
                result = self._classify_result_queue.get_nowait()
                handled = True
                job = result['job']
                index = job['group_index']
                self._pending_group_indices.discard(index)
                if result['dest_files'] and not result['errors']:
                    if job['rel_path'] not in self.processed_groups:
                        self._selected_processed_count += 1
                    self.processed_groups.add(job['rel_path'])
                    self.class_history[job['rel_path']] = {
                        'species': result['species_label'],
                        'dest_files': result['dest_files'],
                    }
                    self._save_progress()
                self._log(
                    f"分类完成 第{index + 1}组 → 「{result['species_label']}」: "
                    f"物种{result['copied_species']}个, 空拍{result['copied_empty']}个, "
                    f"错误{len(result['errors'])}个"
                )
                if result['errors']:
                    self._log('分类错误详情: ' + ' | '.join(result['errors']), 'warning')
                    self.label_status.config(
                        text=f"⚠ 第 {index + 1} 组完成，但有 {len(result['errors'])} 个错误",
                        fg='#FF9800'
                    )
                else:
                    pending = len(self._pending_group_indices) + self._classify_queue.qsize()
                    self.label_status.config(
                        text=f"✅ 第 {index + 1} 组已完整记录"
                             + (f"，后台队列尚有 {pending} 组" if pending else ''),
                        fg='#4CAF50'
                    )
        except queue.Empty:
            pass
        if handled:
            self._update_progress_bar()
        if self._pending_group_indices or not self._classify_result_queue.empty():
            self._schedule_classification_poll(40)

    def _schedule_classification_poll(self, delay_ms: int = 40):
        """确保任意时刻只有一个分类结果轮询，避免高速点击产生定时器风暴。"""
        if self._classify_poll_after_id is None and not self._closing:
            self._classify_poll_after_id = self.root.after(
                delay_ms, self._poll_classification_results
            )
    
    def _auto_advance(self):
        """分类完成后自动跳转到下一组"""
        if self.current_group_index + 1 < len(self.groups):
            next_index = self.current_group_index + 1
            current_mode = self.groups.mode_for_group(self.current_group_index)
            next_mode = self.groups.mode_for_group(next_index)
            if (current_mode and next_mode
                    and current_mode.get('start') != next_mode.get('start')):
                self.root.after(1, lambda: self._confirm_next_mode_range(next_index, next_mode))
            else:
                self._load_group(next_index)
        else:
            self.label_status.config(text="🎉 所有数据已处理完毕！", fg='#4CAF50')
            self.label_group_info.config(text="✨ 全部完成！")
            if (hasattr(self.groups, 'file_names')
                    and self.selection_end < len(self.groups.file_names)):
                self.root.after(100, self._offer_next_selected_range)

    def _confirm_next_mode_range(self, next_index: int, mode: dict):
        """跨过模式边界时主动让用户核对下一段，避免按错相机模式。"""
        if next_index != self.current_group_index + 1:
            return
        message = (
            f"上一拍摄模式范围已完成。\n\n下一范围从文件序号 {mode['start']} 开始，"
            f"模式为：{mode['photo_count']} 张照片 + {mode['video_count']} 个视频，"
            f"{ORDER_DISPLAY_NAMES.get(mode['order'], '')}。\n\n"
            "选择“是”按该模式继续；选择“否”返回“路径与模式”重新设置。"
        )
        if messagebox.askyesno("设置下一拍摄范围", message, parent=self.root):
            self._load_group(next_index)
        else:
            self._show_path_dialog()

    def _offer_next_selected_range(self):
        """本次选中范围结束后，询问是否接着选择后续范围。"""
        if self._pending_group_indices:
            self.root.after(100, self._offer_next_selected_range)
            return
        start = self.selection_end + 1
        if messagebox.askyesno(
                "已完成选中范围",
                f"文件序号 {self.selection_start}–{self.selection_end} 已处理完成。\n\n"
                f"是否从第 {start} 个文件开始设置下一个范围及拍摄模式？",
                parent=self.root):
            self.selection_start = start
            self.selection_end = None
            self._show_path_dialog()
    
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

    def _write_csv_snapshot(self, job: dict):
        """使用分类点击瞬间的不可变快照写CSV，供后台分类线程调用。"""
        files = job['files']
        if not files:
            return
        empty_metadata = {
            'longitude': None, 'latitude': None,
            'altitude': None, 'datetime': None
        }
        metadata_by_file = {}
        fallback_metadata = empty_metadata.copy()
        for file_path in files:
            metadata = extract_gps_from_file(file_path)
            metadata_by_file[file_path] = metadata
            for key in fallback_metadata:
                if fallback_metadata[key] is None and metadata.get(key) is not None:
                    fallback_metadata[key] = metadata[key]

        new_rows = []
        for index, file_path in enumerate(files):
            metadata = self._merge_media_metadata(
                metadata_by_file[file_path], fallback_metadata
            )
            species = '；'.join(self._job_species_for_file(job, index))
            new_rows.append(self._csv_row(
                file_path, metadata, species, job['point_name']
            ))
        self._replace_csv_rows(
            os.path.join(job['target_dir'], 'wildcam_records.csv'),
            job['point_name'], files, new_rows, job['replace_existing']
        )

    def _replace_csv_rows(self, csv_path: str, point_name: str, files,
                          new_rows: list, replace_existing: bool = True):
        """追加或原子替换一组CSV行；调用方必须位于串行工作线程。"""
        has_current_schema = False
        if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
            with open(csv_path, 'r', newline='', encoding='utf-8-sig') as source:
                header = next(csv.reader(source), [])
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

        if has_current_schema and not replace_existing:
            with open(csv_path, 'a', newline='', encoding='utf-8-sig') as target:
                csv.DictWriter(target, fieldnames=CSV_HEADERS).writerows(new_rows)
            return

        current_names = {os.path.basename(path) for path in files}
        temp_path = f"{csv_path}.tmp"
        try:
            with open(temp_path, 'w', newline='', encoding='utf-8-sig') as target:
                writer = csv.DictWriter(target, fieldnames=CSV_HEADERS)
                writer.writeheader()
                if has_current_schema:
                    with open(csv_path, 'r', newline='', encoding='utf-8-sig') as source:
                        for row in csv.DictReader(source):
                            if (row.get('点位名称', '') == point_name
                                    and row.get('文件名', '') in current_names):
                                continue
                            writer.writerow({h: row.get(h, '') for h in CSV_HEADERS})
                writer.writerows(new_rows)
            os.replace(temp_path, csv_path)
        except Exception:
            try:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            except OSError:
                pass
            raise

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
            
            btn = create_button(
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
        if not hasattr(self.groups, 'group_index_for_file') or not self.groups:
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
        if state is None or not hasattr(self.groups, 'group_index_for_file'):
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
        selected_processed = min(self._selected_processed_count, total)
        all_total = len(self.all_groups) if self.all_groups else total
        source_prefix = os.path.basename(self.source_dir or '') + os.sep
        folder_processed = min(sum(
            1 for rel in self.processed_groups if rel.startswith(source_prefix)
        ), all_total)
        
        # 背景
        self.progress_canvas.create_rectangle(0, 0, canvas_w, 5, fill='#333333', outline='')
        # 上2px为文件夹全部数据（蓝色），下3px为本次选中数据（黄色）。
        if all_total > 0:
            ratio = min(folder_processed / all_total, 1.0)
            self.progress_canvas.create_rectangle(
                0, 0, int(canvas_w * ratio), 2,
                fill=COLOR_PROGRESS, outline=''
            )
        if total > 0:
            ratio = min(selected_processed / total, 1.0)
            self.progress_canvas.create_rectangle(
                0, 2, int(canvas_w * ratio), 5,
                fill='#FBC02D', outline=''
            )
        self.label_count.config(
            text=f"文件夹 {folder_processed}/{all_total}｜已选 {selected_processed}/{total} 组"
        )
        self.label_remaining.config(
            text=(f"文件夹内数据剩余 {max(0, all_total-folder_processed)} 组待处理\n"
                  f"已选中数据剩余 {max(0, total-selected_processed)} 组待处理")
        )
    
    def _update_status(self):
        """更新状态栏"""
        if not self.groups:
            return
        remaining = len(self.groups) - self._selected_processed_count
        if remaining > 0:
            if not self.label_status.cget('text'):
                self.label_status.config(text="就绪", fg='#AAAAAA')
        else:
            self.label_status.config(text="🎉 全部完成！", fg='#4CAF50')
    
    # ==================== 窗口事件 ====================
    
    def _on_close(self):
        """关闭窗口清理"""
        if not self._closing and self._pending_group_indices:
            pending = len(self._pending_group_indices)
            wait_for_finish = messagebox.askyesno(
                "分类仍在保存",
                f"后台还有 {pending} 组正在复制并写入记录。\n\n"
                "是否等待全部保存完成后自动退出？\n"
                "选择“否”将返回程序，不会强制中断记录。",
                parent=self.root
            )
            if wait_for_finish:
                self.label_status.config(text=f"正在保存最后 {pending} 组，完成后自动退出…")
                self.root.after(100, self._close_when_classification_finishes)
            return
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

    def _close_when_classification_finishes(self):
        self._schedule_classification_poll(1)
        if self._pending_group_indices:
            self.root.after(100, self._close_when_classification_finishes)
        else:
            self._on_close()
    
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
