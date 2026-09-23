# WildCam Sorter — 红外相机照片与视频分类器 
# Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 v1.11 / Download](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.11) · [问题反馈 / Issues](https://github.com/S-Y-Chu/wildcam_sorter/issues)

---

## 中文说明

WildCam Sorter 是一款本地运行的红外/野外相机照片与视频分类工具。它支持自定义相机拍摄模式、媒体预览、逐文件 CSV、多类别分类、大型目录后台扫描和断点续传。分类以复制文件为主，不移动或改写原始数据。

### 下载与安装

#### Windows 10/11 64 位

1. 前往 [v1.11 Release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.11) 下载 `WildCamSorter_Windows_v1.11_Portable.zip`。
2. 完整解压后运行 `WildCamSorter.exe`；无需安装 Python。

#### macOS

1. 在 ` → 关于本机`查看芯片类型。
2. M 系列下载 `WildCamSorter_macOS_AppleSilicon_v1.11_Portable.zip`；Intel 处理器下载 `WildCamSorter_macOS_Intel_v1.11_Portable.zip`（均在 [v1.11 Release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.11)）。
3. 完整解压后运行 `WildCamSorter.app`。第一次运行请在 Finder 中按住 Control 点击（或右键）程序，选择**打开**；若仍被阻止，到`系统设置 → 隐私与安全性`点击**仍要打开**。
4. 建议 macOS 13 Ventura 或更高版本。外接输出盘建议使用 APFS、Mac OS 扩展或 exFAT；macOS 通常不能直接写 NTFS。

> 便携版必须先完整解压，不要直接在 ZIP 预览窗口中运行。

### 最新版本 v1.11

- 分析照片与视频顺序，给出可能的拍摄模式；不符合设置的组会列出具体文件序号区间，点击“重选择模式”时预填建议值。仅有照片时无法可靠推断每组照片数，仍需手动设置。
- 四个媒体窗格显示文件名和创建时间；不提供创建时间的系统显示修改时间。扫描时忽略 macOS 的 `._` 附属文件。
- 主页面默认使用 2 个视频预览线程；单独查看器在后台处理视频解码和进度跳转，以改善倍速播放与拖动进度条时的响应。
- 性能设置提供“省内存／均衡／快速”档位，并可自定义图片预览线程、视频预览线程、缩略图缓存上限和下一组图片预读。设置在**下次启动**生效；文件复制和 CSV 写入继续按顺序执行。
- 设置中的离线教程把本地 README 渲染为阅读页面，支持中英文切换、目录跳转、字号调整和可点击的链接。
- 沿用多范围拍摄模式、快速连续分类、双进度条、主题切换、人工分类识别与 CSV 补录等功能。

[查看 v1.11 完整更新与使用说明](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.11#readme)。

### 版本分支

| 版本 | 源码分支 | 主要内容 |
| --- | --- | --- |
| 1.0 | [1.0](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.0) | 首个公开版本：基础分组、分类、断点续传和 CSV。 |
| 1.5 | [1.5](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.5) | 多类别、每文件独立分类、自定义输出、动态布局和日志。 |
| 1.6 | [1.6](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.6) | 输入/输出路径分离、启动路径设置和界面改进。 |
| 1.6.4 | [1.6.4](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.6.4) | 视频解码与稳定性维护。 |
| 1.7 | [1.7](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.7) | 完整媒体播放器；CSV 文件名列和逐文件记录。 |
| 1.8 | [1.8](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.8) | 自定义固定拍摄模式、视频进度条和九档倍速。 |
| 1.9 | [1.9](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.9) | 超大目录后台处理、低内存优化、“跳转至”和 Mac 便携版。 |
| 1.10 | [1.10](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10) | 查看器缩放拖动、多范围模式、快速分类、双进度条和主题。 |
| 1.10.3 | [1.10.3](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10.3) | 修复 macOS 按钮文字、小窗口布局、浅色主题对比度和全屏查看器。 |
| 1.11 | [1.11](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.11) | 模式建议、错误文件范围、创建时间、视频响应、性能设置和离线双语教程。 |

`main` 只保存项目总说明和版本导航；每个版本的完整源码、测试、依赖和打包配置保存在对应版本分支。旧分支 README 描述该历史版本，不代表最新版功能。

### 从源码运行

切换到所需版本分支后：

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```

### 作者

Siyuan ZHU · 2026

---

## English Guide

WildCam Sorter is a local desktop tool for classifying trail-camera photos and videos. It supports configurable camera capture patterns, media previews, one-row-per-file CSV output, multi-category sorting, background scanning of large folders, and resumable work. Sorting primarily copies files and never moves or rewrites original media.

### Download and install

#### Windows 10/11 64-bit

1. Open the [v1.11 release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.11) and download `WildCamSorter_Windows_v1.11_Portable.zip`.
2. Extract it completely, then launch `WildCamSorter.exe`. Python is not required.

#### macOS

1. Check the processor under `Apple menu → About This Mac`.
2. Download `WildCamSorter_macOS_AppleSilicon_v1.11_Portable.zip` for Apple Silicon or `WildCamSorter_macOS_Intel_v1.11_Portable.zip` for Intel from the [v1.11 release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.11).
3. Extract the archive completely and launch `WildCamSorter.app`. On first launch, Control-click (or right-click) it in Finder and choose **Open**. If it is still blocked, choose **Open Anyway** under **System Settings → Privacy & Security**.
4. macOS 13 Ventura or newer is recommended. Use APFS, Mac OS Extended, or exFAT for external output drives; macOS normally cannot write NTFS.

> Always extract the portable archive completely. Do not launch the app from a ZIP preview window.

### Latest release: v1.11

- Suggest repeated mixed photo/video capture patterns. Report exact file-number ranges of mismatching groups and prefill suggested values when reselecting the mode. The photos-per-trigger count cannot be inferred reliably from photos alone.
- Show filenames and filesystem creation times in the four media panes (modification time when creation time is unavailable). Ignore macOS `._` sidecar files during scans.
- Use two video preview workers by default. Fullscreen video decoding and seeking run in a background thread for more responsive playback and scrubbing.
- Choose Low memory, Balanced, or Fast, or set image/video preview workers, thumbnail cache size, and next-group prefetch. **Restart to apply** performance settings. Copying and CSV writes remain ordered.
- Read the packaged README offline in a bilingual reading view with a table of contents, adjustable font size, and clickable links.
- Retain ranged capture patterns, rapid sorting, dual progress bars, themes, and recovery of manually classified media and CSV records.

[Read the full v1.11 notes and guide](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.11#readme).

### Version branches

| Version | Source branch | Highlights |
| --- | --- | --- |
| 1.0 | [1.0](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.0) | First public release: basic grouping, sorting, resume, and CSV. |
| 1.5 | [1.5](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.5) | Multi-category and per-file sorting, custom output, dynamic layout, and logs. |
| 1.6 | [1.6](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.6) | Separate input/output paths, startup path selection, and UI improvements. |
| 1.6.4 | [1.6.4](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.6.4) | Video decoding and stability maintenance. |
| 1.7 | [1.7](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.7) | Full media player; filename column and one CSV row per file. |
| 1.8 | [1.8](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.8) | Custom fixed capture pattern, video seek bar, and nine playback speeds. |
| 1.9 | [1.9](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.9) | Background processing for huge folders, low-memory design, Jump To, and Mac builds. |
| 1.10 | [1.10](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10) | Viewer zoom/pan, ranged patterns, rapid sorting, dual progress bars, and themes. |
| 1.10.3 | [1.10.3](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10.3) | macOS button readability, small-window layout, light-theme contrast, and fullscreen viewer fixes. |
| 1.11 | [1.11](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.11) | Capture suggestions, exact mismatch ranges, timestamps, video responsiveness, performance settings, and offline bilingual guide. |

`main` contains only the project overview and version navigation. Full source, tests, dependencies, and packaging configuration live in each version branch. An older branch README documents that historical version and does not describe every current feature.

### Run from source

Switch to the desired version branch, then run:

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```

### Author

Siyuan ZHU · 2026
