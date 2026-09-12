# WildCam Sorter v1.9 — 红外相机照片与视频分类器 / Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 / Downloads](https://github.com/S-Y-Chu/wildcam_sorter/releases) · [最新版源码 / Latest source](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10)

---

## 中文说明

> 这是历史版本 **v1.9** 的说明。一般用户请优先下载 [最新版本 v1.10](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.10)。

### 简介

面向超大数据目录的后台扫描与低内存优化，增加“跳转至”，并提供 Windows 与两种 Mac 便携包。

WildCam Sorter 是一款本地运行的红外/野外相机媒体分类工具。它按组预览照片和视频，把选中的文件复制到物种类别目录，并保存进度和 CSV。原始输入文件不会被移动或改写。

### 本版本主要功能

- 扫描、自然排序、进度读取和已有分类核对在后台执行，可取消扫描。
- 只长期保存轻量文件名，当前组按需加载，适合数百 GB 数据目录。
- “上一组”和“下一组”之间增加“跳转至”，可输入序号或完整文件名。
- 提供 Windows x64、macOS Apple Silicon 和 macOS Intel 便携版。

### 安装与运行

#### Windows 10/11 64 位

1. 前往 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) 下载与本版本对应的 Windows Portable 压缩包（如有）。
2. **完整解压** ZIP；不要直接在压缩包预览窗口中运行。
3. 双击 `WildCamSorter.exe`。便携版不需要安装 Python。

#### macOS

1. 在 ` → 关于本机`查看芯片：M1/M2/M3/M4/M5 等下载 `AppleSilicon` 包，Intel 处理器下载 `Intel` 包。
2. 完整解压，把 `WildCamSorter.app` 放入“应用程序”或留在解压目录中。
3. 第一次运行时，在 Finder 中按住 Control 点击（或右键）程序，选择**打开**并确认；若仍被阻止，到`系统设置 → 隐私与安全性`点击**仍要打开**。
4. 外接硬盘必须可写。macOS 通常不能直接写 NTFS，建议 APFS、Mac OS 扩展或 exFAT。

> 建议 macOS 13 Ventura 或更高版本。程序未经 Apple 公证，不要为此关闭系统全部安全保护。

#### 从源码运行（开发者）

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```


### 数据与分组规则

启动时设置每组照片数、视频数和先后顺序。照片数可自由填写，视频数可为 0；此版本对整个目录使用一个固定模式。

支持的常见图片格式包括 JPG、JPEG、PNG、BMP；常见视频格式包括 AVI、MP4、MOV、MKV、WMV。实际视频兼容性取决于文件编码和系统解码能力。

### 基本使用

1. 启动程序，选择输入与输出文件夹，并填写整个目录采用的照片数、视频数和先后顺序。
2. 核对当前组中的照片和视频；不需要参与全局分类的文件可取消选中或单独指定类别。
3. 点击“空拍”、已有物种或“新物种”。多类别模式可为同一媒体选择多个类别。
4. 程序复制文件并保存进度，然后进入下一组。可返回上一组重新分类。

> 输入目录是原始数据；输出目录是分类结果。请勿把二者理解反，也不建议将输出目录设在输入目录内部。

### 媒体查看器

照片和视频默认适合窗口。视频播放器包含播放/暂停、可拖动进度条和九档倍速。

### CSV、进度与日志

包含文件名，每个媒体文件独立一行；新记录直接追加，重新分类时采用常量内存流式更新。

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
- 源码分支：[v1.9](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.9)
- 作者：Siyuan ZHU

---

## English Guide

> This document describes historical release **v1.9**. Most users should download the [latest release, v1.10](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.10).

### Overview

Adds background scanning and low-memory handling for very large datasets, Jump To navigation, and Windows plus two Mac portable builds.

WildCam Sorter is a local desktop tool for classifying trail-camera photos and videos. It previews media in groups, copies selected files into species folders, and records progress and CSV data. Original input files are never moved or modified.

### Highlights in this release

- Scanning, natural sorting, progress loading, and existing-sort checks run in the background and can be cancelled.
- Keeps lightweight filenames in memory and loads only the current group, suitable for datasets hundreds of gigabytes in size.
- Jump To between Previous and Next accepts a media sequence number or full filename.
- Portable builds are available for Windows x64, macOS Apple Silicon, and macOS Intel.

### Installation and launch

#### Windows 10/11 64-bit

1. Open [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) and download the Windows Portable archive matching this version, when available.
2. **Extract the ZIP completely**; do not run the app from inside the archive preview.
3. Double-click `WildCamSorter.exe`. The portable build does not require Python.

#### macOS

1. Check `Apple menu → About This Mac`: choose `AppleSilicon` for M1/M2/M3/M4/M5-series Macs, or `Intel` for Intel Macs.
2. Extract the archive completely and place `WildCamSorter.app` in Applications or keep it in the extracted folder.
3. On first launch, Control-click (or right-click) the app in Finder, choose **Open**, and confirm. If macOS still blocks it, use **System Settings → Privacy & Security → Open Anyway**.
4. An external output drive must be writable. macOS normally cannot write NTFS; APFS, Mac OS Extended, or exFAT is recommended.

> macOS 13 Ventura or newer is recommended. The app is not Apple-notarized; do not disable all macOS security protections.

#### Run from source (developers)

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```


### Data and grouping rules

At startup, set the photo count, video count, and order per group. Photo count is configurable and video count may be zero; this release applies one fixed pattern to the whole folder.

Common image formats include JPG, JPEG, PNG, and BMP. Common video formats include AVI, MP4, MOV, MKV, and WMV. Actual video compatibility depends on the codec and the system decoder.

### Quick start

1. Launch the app, choose input and output folders, and enter the photo count, video count, and media order used by the whole folder.
2. Review the photos and videos in the current group. Exclude files from the group action or assign an individual category when needed.
3. Choose Empty, an existing species, or New Species. Multi-category mode can assign the same media to several categories.
4. The app copies files, saves progress, and advances to the next group. Return to a previous group to correct a classification.

> The input folder contains original data; the output folder contains classified copies. Do not swap them, and avoid placing the output folder inside the input folder.

### Media viewer

Photos and videos fit the window initially. The video player includes play/pause, a draggable seek bar, and nine playback speeds.

### CSV, progress, and logs

Includes filenames with one row per media file. New records append directly, while reclassification uses constant-memory streaming updates.

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
- Source branch: [v1.9](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.9)
- Author: Siyuan ZHU
