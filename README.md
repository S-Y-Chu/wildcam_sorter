# WildCam Sorter v1.12 — 红外相机照片与视频分类器 / Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 / Downloads](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12) · [本版源码 / Source](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12)

---

## 中文说明


### 简介

在先前版本的分段拍摄模式、双进度条与离线教程基础上，1.12 增加可编辑分类按钮、灵活预览布局和字体大小设置，改进视频预览及 Windows/Mac 查看器。

WildCam Sorter 是一款本地运行的红外/野外相机媒体分类工具。它按组预览照片和视频，把选中的文件复制到物种类别目录，并保存进度和 CSV。原始输入文件不会被移动或改写。

### 本版本主要功能

#### 1.12 新增与修复

- 长按类别按钮约 0.6 秒进入编辑模式；拖动按钮调整顺序，右上角的 × 可删除类别。删除时先选择另一个类别或“空拍”接收全部分类文件；迁移同步修改 CSV 与进度记录。若目标有同名且内容不同的文件，迁移会中止，不会覆盖。原始输入文件不会变动。
- 3、4、5、6 等数量的组按文件数自适应排版；3 和 5 个文件时把视频放在较大的预览位。每页最多显示 9 个媒体；组内更多文件可翻页。照片和视频保持原始比例，文件名与时间在同一行，没有超出范围时隐藏类别横向滚动条。
- 设置中的“界面字号”可以在 80%–150% 之间调整；性能设置允许图片线程最多 12 个、视频预览线程最多 6 个、缩略图缓存上限 4096 MB，预设分别提供 256 / 512 / 2048 MB，性能设置重启生效。高速浏览时复用预览面板和下一组首帧缓存。
- Windows 单独查看窗口缩小到屏幕内的保守尺寸；Mac 查看器使用主窗口内的“分类”页返回，不另开改变全屏尺寸的窗口。单独视频默认 0.5× 并可按空格暂停/继续；主页面视频自动播放，目标为 5×，限制每秒渲染帧数以避免无谓的持续解码。
- 主分类页按空格分类为“空拍”，按左右键切换上一组/下一组；在查看器内空格仍控制播放。需要实际流畅播放的速度取决于视频编码、磁盘和设备能力。

#### 1.11 新增与修复（沿用）

- 自动分析连续的照片 + 视频拍摄模式；若样本不足或仅有照片，则请手动指定拍摄模式。发现错误组时逐段列出准确的文件序号范围，点击“重选择模式”会预填检测出的候选模式（请核对）。
- 每个媒体窗格显示文件名与文件系统创建时间；没有创建时间的系统显示“修改时间”。扫描时跳过 macOS `._` 附属文件，不再把它们当作照片或视频。
- 主页面默认增加到 2 个视频预览线程；单独视频播放器把解码、跳转和追帧放在后台线程，拖动进度条不会阻塞主界面。视频解码取决于摄像机编码、硬盘和机器性能。
- 设置里增加“省内存 / 均衡 / 快速”预设与图片线程、视频线程、缩略图缓存 MB、下一组图片预读开关；保存后**重启生效**，分类复制及 CSV 保持单线程按顺序执行。
- 设置中的离线“教程（阅读模式）”提供中英切换、章节目录、字号调整和可点击的 HTTP(S) 链接，内容来自随便携包提供的本地 README。

#### 1.10.3 修复汇总（延续保留）

- **此前的 Mac 修复**：修复 macOS Aqua 按钮白底白字；主界面采用 4 个图片后台线程和独立的视频线程，修复慢预览及最后一格预览任务停止轮询，并预读下一组缩略图。
- **本次的跨平台修复**：分类按钮与上一组／跳转至／下一组等导航按钮分行排列；物种按钮可横向滚动，小窗口也能找到全部按钮；浅色主题的黄色提示文字自动变为深琥珀色，黑色主题保留亮黄色，后续新出现的提示同样跟随主题；修复增减物种按钮后分类栏偶现深色块。
- **本次的查看器修复**：只调整独立查看窗口，不再在打开它时重新配置主窗口；当 Windows 主窗口最大化或 Mac 主窗口放大／全屏时，查看器当时使用主窗口的完整可见尺寸；1.12 已进一步改为 Windows 小窗和 Mac 应用内页面。

上述布局与主题问题均影响 Windows 和 macOS，修复同时适用于两个平台。Mac 原生 Aqua 按钮与全屏行为另作兼容处理。

- 查看器以适合窗口为 100%，可围绕鼠标位置缩放至 1000%，并按鼠标实际距离任意方向拖动。
- 分类采用顺序后台队列：界面立即进入下一组，复制、EXIF、CSV 和日志按点击顺序完成。
- 不同文件序号范围可使用不同拍摄模式，也可限定本次只查看/分类的范围。
- 蓝色显示文件夹总进度，黄色显示选中范围进度；支持白色、黑色和跟随系统主题。
- 可识别输出文件夹里人工分类但未记入软件记录的文件，并补写 CSV。

### 安装与运行

#### Windows 10/11 64 位

1. 前往 [v1.12 Release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12) 下载 Windows Portable 压缩包。
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

打开即完整显示媒体；滚轮缩放为 100%–1000%，速度随滚轮动作变化并以指针为中心。图片可向任意方向 1:1 跟随鼠标拖动，Windows 查看器以较小尺寸居中，Mac 查看器占用主窗口内的媒体页。

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
- 源码分支：[1.12](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12)
- 作者：Siyuan ZHU

---

## English Guide


### Overview

Building on ranged capture patterns, dual progress bars and the offline guide, version 1.12 adds editable categories, a flexible preview grid and font scaling, plus improvements to video preview and the Windows/Mac viewers.

WildCam Sorter is a local desktop tool for classifying trail-camera photos and videos. It previews media in groups, copies selected files into species folders, and records progress and CSV data. Original input files are never moved or modified.

### Highlights in this release

#### 1.12 additions and fixes

- Press and hold a species button for about 0.6 seconds to enter edit mode. Drag to reorder, or use × to delete after choosing another category or Empty as the destination. The migration updates output files, CSV, and saved progress; conflicting filenames with different contents abort safely. Original input media is unchanged.
- The preview grid adapts to 3, 4, 5, 6 and other group sizes, giving video a larger cell for groups of 3 or 5. Up to nine files are shown per page, with paging for larger groups. Previews retain their aspect ratio; filenames and timestamps share a header row; the category scrollbar appears only if necessary.
- Scale the whole UI font from 80% to 150%. Configure up to 12 image workers, six video preview workers, and 4096 MB of thumbnail cache; memory presets now provide 256 / 512 / 2048 MB. Worker and cache changes take effect on restart. Reusing preview panes and prefetched video first frames improves rapid browsing.
- The Windows media viewer opens at a smaller on-screen size; the Mac viewer opens in an in-app tab with a Classification return button, retaining native full-screen window state. Standalone videos default to 0.5× and Space toggles playback. Videos in the main grid autoplay at a target 5× with capped rendering to reduce unnecessary CPU work.
- In the main classification page, Space means Empty and Left/Right arrows navigate groups. In the viewer, Space continues to pause or resume video. Actual smooth playback still depends on codec, storage and hardware.

#### 1.11 additions and fixes (carried forward)

- Detect likely repeated mixed photo/video capture patterns, report exact file ordinal ranges of mismatches, and prefill suggested modes when choosing “重选择模式” (verify the suggestions). Photo-only footage cannot reveal the number of photos per trigger.
- Show the file name and filesystem creation time in each pane (modification time where birth time is unavailable). Ignore macOS AppleDouble `._` sidecar files during scans.
- Two video preview workers by default; fullscreen video decoding, seeking and catching up with the media clock now run in a background worker. Actual playback depends on codecs, storage and hardware.
- Choose Low memory / Balanced / Fast settings, or configure image and video preview workers, thumbnail cache size and next-group media prefetch; **restart to apply**. Copying and CSV writes stay on one ordered worker.
- The offline bilingual README reader renders headings and lists, clickable HTTP(S) links, a table of contents, a language switch and adjustable text size.

#### 1.10.3 fixes carried forward

- **Earlier Mac fixes:** Readable macOS Aqua button text; four image preview workers and one separate video worker; fixed polling for the final pending preview and added prefetching for the next group.
- **New cross-platform fixes:** Classification and navigation occupy separate rows. A horizontal scrollbar keeps any number of species buttons accessible in a small window. Yellow warning text becomes dark amber in the light theme and stays bright yellow in the dark theme, including warnings displayed after switching themes. Rebuilding species buttons no longer leaves dark blocks in the light theme.
- **New viewer fixes:** Opening a photo or video styles only the viewer without reconfiguring the main window. When the parent is maximized on Windows or enlarged/fullscreen on macOS, the viewer previously filled its available area. Version 1.12 replaces this with a smaller Windows window and an embedded Mac page.

The layout and warning-text bugs apply to Windows and macOS. Aqua button rendering and native Mac fullscreen also have platform-specific handling.

- The viewer defines fit-to-window as 100%, zooms around the pointer up to 1000%, and pans freely by the exact mouse movement distance.
- Sorting uses an ordered background queue: the UI advances immediately while copy, EXIF, CSV, and log work completes in click order.
- Different file-number ranges can use different capture patterns, and the current session can be limited to a selected range.
- Blue shows whole-folder progress and yellow shows selected-range progress; light, dark, and system themes are available.
- Detects files sorted manually in the output tree but missing from app records and restores their CSV entries.

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

Media opens fully visible. Wheel zoom spans 100%–1000%, responds to wheel velocity, and stays centered on the pointer. Images pan freely at a 1:1 mouse-to-image distance, in a smaller Windows window or a page within the existing Mac window.

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
- Source branch: [1.12](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12)
- Author: Siyuan ZHU
