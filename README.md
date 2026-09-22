# WildCam Sorter v1.10 — 红外相机照片与视频分类器 / Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 / Downloads](https://github.com/S-Y-Chu/wildcam_sorter/releases) · [最新版源码 / Latest source](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10)

---

## 中文说明


### 简介

改善查看器、连续高速分类与稳定性，增加多范围拍摄模式、双进度条、主题设置和人工分类补录。

WildCam Sorter 是一款本地运行的红外/野外相机媒体分类工具。它按组预览照片和视频，把选中的文件复制到物种类别目录，并保存进度和 CSV。原始输入文件不会被移动或改写。

### 本版本主要功能

- 查看器以适合窗口为 100%，可围绕鼠标位置缩放至 1000%，并按鼠标实际距离任意方向拖动。
- 分类采用顺序后台队列：界面立即进入下一组，复制、EXIF、CSV 和日志按点击顺序完成。
- 不同文件序号范围可使用不同拍摄模式，也可限定本次只查看/分类的范围。
- 蓝色显示文件夹总进度，黄色显示选中范围进度；支持白色、黑色和跟随系统主题。
- 可识别输出文件夹里人工分类但未记入软件记录的文件，并补写 CSV。
- 修复 macOS Aqua 原生按钮忽略自定义背景后出现的白底白字问题，所有按钮在浅色、黑色和跟随系统主题下均保持清晰可读。
- macOS 预览改为 4 个图片线程和独立视频线程，修复最后一格任务已在解码却停止轮询的问题，并预读下一组缩略图。

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

可添加多个模式范围，例如 1–200 为“1 视频 + 3 照片，视频在前”，201–600 为“3 照片 + 1 视频，照片在前”。还可只处理如 1500–3000 的文件范围。

支持的常见图片格式包括 JPG、JPEG、PNG、BMP；常见视频格式包括 AVI、MP4、MOV、MKV、WMV。实际视频兼容性取决于文件编码和系统解码能力。

### 基本使用

1. 启动程序，选择输入与输出文件夹，设置一个或多个拍摄模式范围；如有需要，再限定本次查看/分类范围。
2. 核对当前组中的照片和视频；不需要参与全局分类的文件可取消选中或单独指定类别。
3. 点击“空拍”、已有物种或“新物种”。多类别模式可为同一媒体选择多个类别。
4. 程序复制文件并保存进度，然后进入下一组。可返回上一组重新分类。

> 输入目录是原始数据；输出目录是分类结果。请勿把二者理解反，也不建议将输出目录设在输入目录内部。

### 媒体查看器

打开即完整显示媒体；滚轮缩放为 100%–1000%，速度随滚轮动作变化并以指针为中心。图片可向任意方向 1:1 跟随鼠标拖动，窗口自动居中并避开任务栏或程序坞。

### CSV、进度与日志

包含文件名且每个媒体独立一行。后台队列保证快速连续点击时记录、日志和文件复制不丢失；人工放入输出类别目录的文件也可补录。

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
- 源码分支：[v1.10](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10)
- 作者：Siyuan ZHU

---

## English Guide


### Overview

Improves the viewer, rapid continuous sorting, and stability, while adding ranged capture patterns, dual progress bars, themes, and recovery of manually sorted files.

WildCam Sorter is a local desktop tool for classifying trail-camera photos and videos. It previews media in groups, copies selected files into species folders, and records progress and CSV data. Original input files are never moved or modified.

### Highlights in this release

- The viewer defines fit-to-window as 100%, zooms around the pointer up to 1000%, and pans freely by the exact mouse movement distance.
- Sorting uses an ordered background queue: the UI advances immediately while copy, EXIF, CSV, and log work completes in click order.
- Different file-number ranges can use different capture patterns, and the current session can be limited to a selected range.
- Blue shows whole-folder progress and yellow shows selected-range progress; light, dark, and system themes are available.
- Detects files sorted manually in the output tree but missing from app records and restores their CSV entries.
- Fixes white-on-white button labels caused by macOS Aqua ignoring custom button backgrounds, keeping every button readable in light, dark, and system themes.
- Uses four image workers plus an isolated video worker on macOS, keeps polling in-flight final-panel jobs, and preloads the next group's thumbnails.

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

Add multiple pattern ranges, for example 1–200 as “1 video + 3 photos, video first” and 201–600 as “3 photos + 1 video, photos first.” You can also process only a range such as files 1500–3000.

Common image formats include JPG, JPEG, PNG, and BMP. Common video formats include AVI, MP4, MOV, MKV, and WMV. Actual video compatibility depends on the codec and the system decoder.

### Quick start

1. Launch the app, choose input and output folders, configure one or more capture-pattern ranges, and optionally limit the range to review in this session.
2. Review the photos and videos in the current group. Exclude files from the group action or assign an individual category when needed.
3. Choose Empty, an existing species, or New Species. Multi-category mode can assign the same media to several categories.
4. The app copies files, saves progress, and advances to the next group. Return to a previous group to correct a classification.

> The input folder contains original data; the output folder contains classified copies. Do not swap them, and avoid placing the output folder inside the input folder.

### Media viewer

Media opens fully visible. Wheel zoom spans 100%–1000%, responds to wheel velocity, and stays centered on the pointer. Images pan freely at a 1:1 mouse-to-image distance, and the window is centered within the usable screen area.

### CSV, progress, and logs

Includes filenames with one row per media file. The background queue preserves records, logs, and copies during rapid repeated clicks; files placed manually in output category folders can also be recovered.

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
- Source branch: [v1.10](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10)
- Author: Siyuan ZHU
