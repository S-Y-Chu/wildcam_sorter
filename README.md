# WildCam Sorter v1.5 — 红外相机照片与视频分类器 / Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 / Downloads](https://github.com/S-Y-Chu/wildcam_sorter/releases) · [最新版源码 / Latest source](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10)

---

## 中文说明

> 这是历史版本 **v1.5** 的说明。一般用户请优先下载 [最新版本 v1.10](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.10)。

### 简介

增加多类别、每文件独立分类、自定义输出目录、动态布局、人工分类识别与日志。

WildCam Sorter 是一款本地运行的红外/野外相机媒体分类工具。它按组预览照片和视频，把选中的文件复制到物种类别目录，并保存进度和 CSV。原始输入文件不会被移动或改写。

### 本版本主要功能

- 同一文件可同时归入多个物种类别。
- 取消全局选中后，可在文件卡片中单独指定类别。
- 可单独指定输出目录，并识别已手动放入类别文件夹的媒体。
- 动态显示超过四个文件的组，日志自动轮转。

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

按文件名自然排序，自动找到视频，并把视频之间的照片归入前一个视频；支持 1 个视频 + 任意数量照片。

支持的常见图片格式包括 JPG、JPEG、PNG、BMP；常见视频格式包括 AVI、MP4、MOV、MKV、WMV。实际视频兼容性取决于文件编码和系统解码能力。

### 基本使用

1. 启动程序并选择红外相机数据文件夹；如需更换分类结果位置，再使用工具栏中的“输出到”。
2. 核对当前组中的照片和视频；不需要参与全局分类的文件可取消选中或单独指定类别。
3. 点击“空拍”、已有物种或“新物种”。多类别模式可为同一媒体选择多个类别。
4. 程序复制文件并保存进度，然后进入下一组。可返回上一组重新分类。

> 输入目录是原始数据；输出目录是分类结果。请勿把二者理解反，也不建议将输出目录设在输入目录内部。

### 媒体查看器

点击照片或视频打开独立查看器；支持滚轮缩放、拖动、适合窗口和 1:1 查看。

### CSV、进度与日志

CSV 使用旧版记录格式；v1.7 才开始保证媒体逐文件记录并增加文件名列。

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
- 源码分支：[v1.5](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.5)
- 作者：Siyuan ZHU

---

## English Guide

> This document describes historical release **v1.5**. Most users should download the [latest release, v1.10](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.10).

### Overview

Adds multi-category sorting, independent per-file labels, custom output folders, dynamic layout, manual-sort detection, and logging.

WildCam Sorter is a local desktop tool for classifying trail-camera photos and videos. It previews media in groups, copies selected files into species folders, and records progress and CSV data. Original input files are never moved or modified.

### Highlights in this release

- One file can be assigned to multiple species categories.
- After excluding a file from the group selection, assign its category directly on the file card.
- Choose a separate output folder and detect media already placed manually in category folders.
- Dynamically displays groups with more than four files and rotates log files automatically.

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

Files are naturally sorted. Videos are detected automatically, and photos between videos are assigned to the preceding video; one video plus any number of photos is supported.

Common image formats include JPG, JPEG, PNG, and BMP. Common video formats include AVI, MP4, MOV, MKV, and WMV. Actual video compatibility depends on the codec and the system decoder.

### Quick start

1. Launch the app and choose the trail-camera media folder. Use Output To on the toolbar when you want a different results location.
2. Review the photos and videos in the current group. Exclude files from the group action or assign an individual category when needed.
3. Choose Empty, an existing species, or New Species. Multi-category mode can assign the same media to several categories.
4. The app copies files, saves progress, and advances to the next group. Return to a previous group to correct a classification.

> The input folder contains original data; the output folder contains classified copies. Do not swap them, and avoid placing the output folder inside the input folder.

### Media viewer

Click a photo or video to open the standalone viewer, with wheel zoom, panning, fit-to-window, and 1:1 controls.

### CSV, progress, and logs

CSV uses the legacy format. Guaranteed one-row-per-media output and the filename column were introduced in v1.7.

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
- Source branch: [v1.5](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.5)
- Author: Siyuan ZHU
