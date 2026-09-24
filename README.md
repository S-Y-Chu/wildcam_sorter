# WildCam Sorter — 红外相机照片与视频分类器 
# Trail-camera Photo & Video Sorter

[中文](#中文说明) · [English](#english-guide) · [下载 v1.12 / Download](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12) · [问题反馈 / Issues](https://github.com/S-Y-Chu/wildcam_sorter/issues)

---

## 中文说明

WildCam Sorter 是一款本地运行的红外/野外相机照片与视频分类工具。它支持自定义相机拍摄模式、媒体预览、逐文件 CSV、多类别分类、大型目录后台扫描和断点续传。分类以复制文件为主，不移动或改写原始数据。

### 下载与安装

#### Windows 10/11 64 位

1. 前往 [v1.12 Release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12) 下载 `WildCamSorter_Windows_v1.12_Portable.zip`。
2. 完整解压后运行 `WildCamSorter.exe`；无需安装 Python。

#### macOS

1. 在 ` → 关于本机`查看芯片类型。
2. M 系列下载 `WildCamSorter_macOS_AppleSilicon_v1.12_Portable.zip`；Intel 处理器下载 `WildCamSorter_macOS_Intel_v1.12_Portable.zip`（均在 [v1.12 Release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12)）。
3. 完整解压后运行 `WildCamSorter.app`。第一次运行请在 Finder 中按住 Control 点击（或右键）程序，选择**打开**；若仍被阻止，到`系统设置 → 隐私与安全性`点击**仍要打开**。
4. 建议 macOS 13 Ventura 或更高版本。外接输出盘建议使用 APFS、Mac OS 扩展或 exFAT；macOS 通常不能直接写 NTFS。

> 便携版必须先完整解压，不要直接在 ZIP 预览窗口中运行。

### 最新版本 v1.12

- 长按分类按钮进入编辑模式，按钮跟随鼠标移动、邻近按钮平滑让位；删除前指定接收类别或“空拍”，后台迁移分类文件、CSV 和进度记录，同名不同内容时中止，不覆盖原文件。
- 按本组实际文件数排版：1 个占满、2 个并排、3 个一大两小、4 个 2×2、5 个一大四小（全照片则上三下二）、6 个 3×2；9 个以上可翻页。优先给视频大格，也可在设置中选等大布局。预读小图会自动更新为适合窗格的清晰大图；文件名与时间并列显示。
- 在设置中把整体字号调到 80%–150%，图片预览线程最多 12 个、视频预览线程最多 6 个、缩略图缓存最多 4096 MB；下组视频首帧可以预读。性能设置重启生效。
- Windows 独立查看窗口留出屏幕边距；Mac 在原窗口内切换到带 × 关闭按钮的媒体选项卡，不改变全屏尺寸。单独播放视频默认 0.5 倍，空格暂停/继续；主页面视频自动以目标 5 倍速播放并限制无用解码。
- 在主分类页按空格分类为空拍，左右键切换分组；沿用 1.11 的拍摄模式建议、离线双语教程与 CSV 补录。

[查看 v1.12 完整更新与使用说明](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12#readme)。

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
| 1.12 | [1.12](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12) | 类别按钮编辑与迁移、自适应预览、字号、5 倍速主预览和跨平台查看器。 |

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

1. Open the [v1.12 release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12) and download `WildCamSorter_Windows_v1.12_Portable.zip`.
2. Extract it completely, then launch `WildCamSorter.exe`. Python is not required.

#### macOS

1. Check the processor under `Apple menu → About This Mac`.
2. Download `WildCamSorter_macOS_AppleSilicon_v1.12_Portable.zip` for Apple Silicon or `WildCamSorter_macOS_Intel_v1.12_Portable.zip` for Intel from the [v1.12 release](https://github.com/S-Y-Chu/wildcam_sorter/releases/tag/v1.12).
3. Extract the archive completely and launch `WildCamSorter.app`. On first launch, Control-click (or right-click) it in Finder and choose **Open**. If it is still blocked, choose **Open Anyway** under **System Settings → Privacy & Security**.
4. macOS 13 Ventura or newer is recommended. Use APFS, Mac OS Extended, or exFAT for external output drives; macOS normally cannot write NTFS.

> Always extract the portable archive completely. Do not launch the app from a ZIP preview window.

### Latest release: v1.12

- Hold a category button to edit and drag it with the pointer as neighboring buttons slide into place. Choose another category or Empty before deletion; migration updates output files, CSV and progress without overwriting differing files of the same name.
- Preview grids adapt to group size: one file fills the pane; two share a row; three use one large and two small cells; four use 2×2; five use one large and four small cells (or three above two for photos only); six use 3×2. Page through groups larger than nine files. Video receives the large cell where available, or choose equal-size cells in Settings. Small prefetched thumbnails upgrade to sharp pane-sized previews automatically.
- Scale all UI text to 80%–150%. Configure up to 12 image preview workers, six video workers and 4096 MB of thumbnail cache; next-group video first frames can be prefetched. Performance settings apply after restart.
- The Windows viewer opens in a smaller window, while the Mac viewer opens an in-window media tab with an × close control, even in full screen. Standalone video defaults to 0.5x and Space pauses/resumes it; main-grid video autoplays at a target 5x with capped rendering.
- Space sorts Empty and Left/Right navigates groups on the main page. Version 1.11 camera-pattern suggestions, the offline bilingual guide and CSV backfill remain available.

[Read the full v1.12 notes and guide](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12#readme).

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
| 1.12 | [1.12](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.12) | Editable categories and migration, adaptive previews, font scaling, 5x main preview and platform viewers. |

`main` contains only the project overview and version navigation. Full source, tests, dependencies, and packaging configuration live in each version branch. An older branch README documents that historical version and does not describe every current feature.

### Run from source

Switch to the desired version branch, then run:

```bash
python -m pip install -r requirements.txt
python wildcam_sorter.py
```

### Author

Siyuan ZHU · 2026
