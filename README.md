# WildCam Sorter — 红外相机照片与视频分类器 / Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 / Downloads](https://github.com/S-Y-Chu/wildcam_sorter/releases) · [问题反馈 / Issues](https://github.com/S-Y-Chu/wildcam_sorter/issues)

---

## 中文说明

WildCam Sorter 是一款本地运行的红外/野外相机照片与视频分类工具。它支持自定义相机拍摄模式、媒体预览、逐文件 CSV、多类别分类、大型目录后台扫描和断点续传。分类以复制文件为主，不移动或改写原始数据。

### 下载与安装

#### Windows 10/11 64 位

1. 前往 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases)，在最新版本中下载 Windows Portable ZIP。
2. 完整解压后运行 `WildCamSorter.exe`；无需安装 Python。

#### macOS

1. 在 ` → 关于本机`查看芯片类型。
2. M1/M2/M3/M4/M5 等 M 系列下载 `AppleSilicon` 包；Intel 处理器下载 `Intel` 包。
3. 完整解压后运行 `WildCamSorter.app`。第一次运行请在 Finder 中按住 Control 点击（或右键）程序，选择**打开**；若仍被阻止，到`系统设置 → 隐私与安全性`点击**仍要打开**。
4. 建议 macOS 13 Ventura 或更高版本。外接输出盘建议使用 APFS、Mac OS 扩展或 exFAT；macOS 通常不能直接写 NTFS。

> 便携版必须先完整解压，不要直接在 ZIP 预览窗口中运行。

### 最新版本 v1.10

- 图片以适合窗口为 100%，可围绕鼠标指针平滑缩放至 1000%，并按鼠标实际距离任意方向拖动。
- 不同文件序号范围可使用不同拍摄模式，也可仅处理指定范围。
- 分类后的复制、EXIF、CSV 和日志使用顺序后台队列，连续快速分类时界面立即切换且不漏记录。
- 蓝色显示整个文件夹进度，黄色显示本次选中范围进度。
- 支持白色、黑色、跟随系统主题，并提供教程、关于和联系作者入口。
- 可从输出类别目录识别人工分类的文件并补写缺失 CSV 记录。

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

1. Open [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) and download the Windows Portable ZIP from the latest release.
2. Extract it completely, then launch `WildCamSorter.exe`. Python is not required.

#### macOS

1. Check the processor under `Apple menu → About This Mac`.
2. Download `AppleSilicon` for M1/M2/M3/M4/M5-series Macs, or `Intel` for Intel Macs.
3. Extract the archive completely and launch `WildCamSorter.app`. On first launch, Control-click (or right-click) it in Finder and choose **Open**. If it is still blocked, choose **Open Anyway** under **System Settings → Privacy & Security**.
4. macOS 13 Ventura or newer is recommended. Use APFS, Mac OS Extended, or exFAT for external output drives; macOS normally cannot write NTFS.

> Always extract the portable archive completely. Do not launch the app from a ZIP preview window.

### Latest release: v1.10

- Fit-to-window is defined as 100%; zoom smoothly around the pointer up to 1000% and pan freely by the exact mouse movement distance.
- Different file-number ranges can use different capture patterns, and a session can be limited to a selected range.
- Copy, EXIF, CSV, and log work runs through an ordered background queue, so rapid sorting advances immediately without losing records.
- Blue shows whole-folder progress and yellow shows progress within the selected range.
- Light, dark, and system themes are available, together with Guide, About, and Contact Author pages.
- Files sorted manually into output category folders can be detected and restored to missing CSV records.

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

`main` contains only the project overview and version navigation. Full source, tests, dependencies, and packaging configuration live in each version branch. An older branch README documents that historical version and does not describe every current feature.

### Run from source

Switch to the desired version branch, then run:

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```

### Author

Siyuan ZHU · 2026
