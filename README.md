# WildCam Sorter

面向红外相机照片与视频的本地分类工具。程序支持自定义相机拍摄模式、图片与视频预览、逐文件 CSV 记录、多类别分类，以及大型数据目录的后台扫描。

## 下载与使用

没有 Python 环境的 Windows 用户，请前往 [Releases](https://github.com/S-Y-Chu/wildcam_sorter/releases) 下载对应版本的 Portable 压缩包。完整解压后运行 `WildCamSorter.exe`。

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

## 仓库结构

`main` 仅作为项目说明与版本导航页。每个版本的完整源码、测试、依赖与打包配置保存在对应版本分支中。

## 作者

Siyuan ZHU，2026。
