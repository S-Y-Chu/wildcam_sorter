# WildCam Sorter v1.7 — 红外相机照片与视频分类器 / Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 / Downloads](https://github.com/S-Y-Chu/wildcam_sorter/releases) · [最新版源码 / Latest source](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10)

---

## 中文说明

> 这是历史版本 **v1.7** 的说明。一般用户请优先下载 [最新版本 v1.10](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.10)。

### 简介

修复媒体查看与视频播放，并把 CSV 改为包含文件名、每个媒体文件独立一行。

WildCam Sorter 是一款本地运行的红外/野外相机媒体分类工具。它按组预览照片和视频，把选中的文件复制到物种类别目录，并保存进度和 CSV。原始输入文件不会被移动或改写。

### 本版本主要功能

- 独立查看器以 100%（1:1 原始大小）打开。
- 视频默认 1.0 倍速，提供播放/暂停、可拖动进度条和九档倍速。
- CSV 增加文件名列，同组视频和照片分别写入。
- 重新分类会更新旧行，避免重复记录。

### 安装与运行

#### Windows 10/11 64 位

1. 前往 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) 下载与本版本对应的 Windows Portable 压缩包（如有）。
2. **完整解压** ZIP；不要直接在压缩包预览窗口中运行。
3. 双击 `WildCamSorter.exe`。便携版不需要安装 Python。

#### 从源码运行（开发者）

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```


### 数据与分组规则

按文件名自然排序并自动寻找视频；每个视频与下一个视频之前的照片组成一组。

支持的常见图片格式包括 JPG、JPEG、PNG、BMP；常见视频格式包括 AVI、MP4、MOV、MKV、WMV。实际视频兼容性取决于文件编码和系统解码能力。

### 基本使用

1. 启动程序，分别选择红外相机数据的输入文件夹和分类结果的输出文件夹。
2. 核对当前组中的照片和视频；不需要参与全局分类的文件可取消选中或单独指定类别。
3. 点击“空拍”、已有物种或“新物种”。多类别模式可为同一媒体选择多个类别。
4. 程序复制文件并保存进度，然后进入下一组。可返回上一组重新分类。

> 输入目录是原始数据；输出目录是分类结果。请勿把二者理解反，也不建议将输出目录设在输入目录内部。

### 媒体查看器

视频以原始 FPS、默认 1.0× 播放。倍速可选 0.5×、0.75×、0.8×、0.9×、1.0×、1.1×、1.2×、1.5×、2×，并可拖动进度条。

### CSV、进度与日志

列为：文件名、经度、纬度、海拔、物种、拍摄时间、点位名称。每个文件独立一行，多类别写在同一行。

- `wildcam_records.csv`：分类记录，UTF-8 编码。
- `.wildcam_progress.json`：断点续传数据；删除后会丢失软件保存的处理进度。
- `wildcam_sorter.log`：操作和错误日志；遇到问题时可连同复现步骤发给作者。

### 输出示例

```text
输出目录/
├── 空拍/
├── 牛/
├── 马/
├── wildcam_records.csv
├── .wildcam_progress.json
└── wildcam_sorter.log
```

分类操作以复制为主，原始照片和视频保留在输入目录。重新分类时，程序会调整先前由本软件生成的分类结果。

### 常见问题

**视频无法播放怎么办？** 先确认文件在系统播放器中能正常播放，再查看 `wildcam_sorter.log`。MOV/MP4 是容器格式，同一扩展名可能使用不同编码。

**关闭后能继续吗？** 可以。再次使用相同的输入与输出目录，程序会读取进度并跳过已处理内容。

**没有 Python 能用吗？** 可以。下载对应系统的 Portable 包，完整解压后运行即可。

**可以直接在 ZIP 里运行吗？** 不建议。必须先完整解压，否则依赖文件可能找不到，进度与日志也可能无法正常保存。

### 技术信息

- Python、tkinter、Pillow、OpenCV
- 打包：PyInstaller
- 源码分支：[v1.7](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.7)
- 作者：Siyuan ZHU

---

## English Guide

> This document describes historical release **v1.7**. Most users should download the [latest release, v1.10](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.10).

### Overview

Fixes media viewing and video playback, and changes CSV output to include filenames with one row per media file.

WildCam Sorter is a local desktop tool for classifying trail-camera photos and videos. It previews media in groups, copies selected files into species folders, and records progress and CSV data. Original input files are never moved or modified.

### Highlights in this release

- The standalone viewer opens at 100% (native 1:1 size).
- Video defaults to 1.0× and provides play/pause, a seek bar, and nine playback speeds.
- CSV adds a filename column and writes videos and photos in the same group separately.
- Reclassification updates existing rows instead of duplicating them.

### Installation and launch

#### Windows 10/11 64-bit

1. Open [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) and download the Windows Portable archive matching this version, when available.
2. **Extract the ZIP completely**; do not run the app from inside the archive preview.
3. Double-click `WildCamSorter.exe`. The portable build does not require Python.

#### Run from source (developers)

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```


### Data and grouping rules

Files are naturally sorted and videos are detected automatically; each video is grouped with the photos before the next video.

Common image formats include JPG, JPEG, PNG, and BMP. Common video formats include AVI, MP4, MOV, MKV, and WMV. Actual video compatibility depends on the codec and the system decoder.

### Quick start

1. Launch the app and choose the trail-camera input folder and classification output folder separately.
2. Review the photos and videos in the current group. Exclude files from the group action or assign an individual category when needed.
3. Choose Empty, an existing species, or New Species. Multi-category mode can assign the same media to several categories.
4. The app copies files, saves progress, and advances to the next group. Return to a previous group to correct a classification.

> The input folder contains original data; the output folder contains classified copies. Do not swap them, and avoid placing the output folder inside the input folder.

### Media viewer

Video plays at its source FPS and defaults to 1.0×. Available speeds are 0.5×, 0.75×, 0.8×, 0.9×, 1.0×, 1.1×, 1.2×, 1.5×, and 2×, with a draggable seek bar.

### CSV, progress, and logs

Columns are filename, longitude, latitude, altitude, species, capture time, and site name. Every file has its own row; multiple categories share that row.

- `wildcam_records.csv`: UTF-8 classification records.
- `.wildcam_progress.json`: resume data; deleting it removes the progress known to the app.
- `wildcam_sorter.log`: operations and error log; send it to the author together with reproduction steps when reporting a problem.

### Example output

```text
Output folder/
├── Empty/
├── Cattle/
├── Horse/
├── wildcam_records.csv
├── .wildcam_progress.json
└── wildcam_sorter.log
```

Sorting primarily copies files, so original photos and videos remain in the input folder. Reclassification adjusts results previously created by this app.

### FAQ

**A video does not play. What should I do?** First check that it plays in a system media player, then inspect `wildcam_sorter.log`. MOV and MP4 are containers, so files with the same extension may use different codecs.

**Can I resume after closing the app?** Yes. Reopen the same input and output folders; the app reads its progress and skips processed content.

**Can someone without Python use it?** Yes. Download the Portable build for the operating system, extract it completely, and launch the executable/app.

**Can I run it directly from the ZIP?** No. Extract the archive completely so bundled dependencies can be found and progress/log files can be written correctly.

### Technical information

- Python, tkinter, Pillow, and OpenCV
- Packaging: PyInstaller
- Source branch: [v1.7](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.7)
- Author: Siyuan ZHU
