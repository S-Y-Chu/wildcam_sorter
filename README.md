# WildCam Sorter

面向红外相机照片与视频的本地分类工具。程序支持自定义相机拍摄模式、图片与视频预览、逐文件 CSV 记录、多类别分类，以及大型数据目录的后台扫描。

## 下载与使用

### Windows 10/11 64 位

前往 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) 下载对应版本的 Windows Portable 压缩包。完整解压后运行 `WildCamSorter.exe`，不需要安装 Python。

### macOS

在左上角 `` → **关于本机**中查看电脑芯片，然后在 Release **WildCam Sorter v1.9（Mac）**中选择对应的压缩包：

- Apple M1/M2/M3/M4/M5 等 M 系列芯片：下载 `AppleSilicon` 包
- Intel 处理器：下载 `Intel` 包

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

## 最新版本：1.9

- 扫描、排序、进度读取和已有分类核对均在后台执行，扫描过程可取消。
- 采用轻量文件分组，避免一次性加载全部媒体内容。
- 支持按照片或视频序号、完整文件名跳转到所在组。
- 启动设置页可指定照片数、视频数及二者先后顺序。
- 图片默认适应窗口显示；视频提供播放/暂停、可拖动进度条与 9 档倍速。
- CSV 按照片和视频逐文件记录，包含文件名列；重新分类时更新原记录。
- 提供 Apple Silicon 与 Intel 两个原生 macOS 便携包。

## 仓库结构

`main` 仅作为项目说明与版本导航页。每个版本的完整源码、测试、依赖与打包配置保存在对应版本分支中。

## 作者

Siyuan ZHU，2026
