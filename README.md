# WildCam Sorter

面向红外相机照片与视频的本地分类工具。程序支持自定义相机拍摄模式、图片与视频预览、逐文件 CSV 记录、多类别分类，以及大型数据目录的后台扫描。

## 下载与使用

### Windows 10/11 64 位

前往 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) 下载最新版本的 Windows Portable 压缩包。完整解压后运行 `WildCamSorter.exe`，不需要安装 Python。

### macOS

在左上角 `` → **关于本机**中查看电脑芯片，然后在 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) **WildCam Sorter v1.10** 中选择对应的压缩包：

- Apple M1/M2/M3/M4/M5 等 M 系列芯片：下载 `WildCamSorter_macOS_AppleSilicon_v1.10_Portable.zip`
- Intel 处理器：下载 `WildCamSorter_macOS_Intel_v1.10_Portable.zip`

完整解压后运行 `WildCamSorter.app`，不需要安装 Python。第一次打开时，请在 Finder 中按住 Control 点击（或右键点击）程序，选择 **打开** 并再次确认；如果仍被阻止，到 **系统设置 → 隐私与安全性**点击 **仍要打开**。建议使用 macOS 13 Ventura 或更高版本。

Mac 压缩包内附有完整的 `macOS使用说明.txt`。使用外接硬盘保存分类结果时请确保硬盘可写；macOS 通常不能直接写入 NTFS，建议使用 APFS、Mac OS 扩展或 exFAT。

需要阅读或修改源码时，请切换到对应版本分支。

## 版本分支

| 版本 | 源码分支 | 主要内容 |
| --- | --- | --- |
| 1.0 | [1.0](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.0) | 首个公开版本 |
| 1.5 | [1.5](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.5) | 多类别分类、独立选择、动态布局与视频双引擎 |
| 1.6 | [1.6](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.6) | 输入输出分离、启动路径设置与界面优化 |
| 1.6.4 | [1.6.4](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.6.4) | 视频解码与稳定性修复 |
| 1.7 | [1.7](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.7) | 媒体查看器、CSV 逐文件记录与 Windows 便携版 |
| 1.8 | [1.8](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.8) | 自定义拍摄模式、视频进度条和多档倍速 |
| 1.9 | [1.9](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.9) | 超大目录后台处理、低内存优化与“跳转至”功能 |
| 1.10 | [1.10](https://github.com/S-Y-Chu/wildcam_sorter/tree/1.10) | 查看器缩放拖动、多范围拍摄模式、快速连续分类、双进度条与主题设置 |

## 最新版本：1.10

- 图片查看器支持以鼠标指针为中心在 100%–1000% 间缩放，并可按住图片自由拖动。
- 支持多个序号范围使用不同拍摄模式，并可限定本次只查看/分类的文件范围。
- 分类后的复制、EXIF 读取和 CSV 写入改为后台按顺序处理，支持更流畅的连续分类。
- 增加文件夹总进度与本次选中范围进度两条进度条。
- 增加白色、黑色和跟随系统主题，以及教程、关于和联系作者入口。
- 可自动识别输出目录中人工分好的文件并补写 CSV 记录。
- Release 同时提供 Windows x64、macOS Apple Silicon 和 macOS Intel 三个 Portable 包。

## 仓库结构

`main` 仅作为项目说明与版本导航页。每个版本的完整源码、测试、依赖与打包配置保存在对应版本分支中。

## 作者

Siyuan ZHU，2026
