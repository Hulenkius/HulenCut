<p align="center">
  <img src="hulencutter.png" width="96" alt="HulenCut">
</p>

<h1 align="center">HulenCut</h1>

<p align="center">印刷品图像切片、表格识别、批量处理与导出的桌面工具</p>

<p align="center">
  <strong>v0.8.2</strong> · 繁體中文 / 简体中文 / English
</p>

## 简介

HulenCut 用于将整页书影扫描件或表格图片切分为多个独立图像，并完成命名、排序、筛选、批量处理和导出。

## 功能

- 导入图片、文件夹、`.cutter` 工程以及看典古籍 JSON
- 手动拖拽创建切片，或自动识别文字区域与表格
- 移动、缩放、筛选、合并、定幅、批量重命名切片
- 裁剪图像、校正倾斜
- 切片搜索、对齐、分布、预览与快速跳转
- 保存/自动载入同名 `.cutter` 工程
- 导出 PNG、JPG、BMP
- 录制并运行自动处理脚本，支持跨页循环
- 支持拖放打开文件、`Ctrl+K` 命令面板
- 深色/浅色/跟随系统主题
- 繁體中文、简体中文、English 即时切换

支持图片格式：`PNG`、`JPG`、`JPEG`、`BMP`、`TIF`、`TIFF`、`WEBP`

## 快速开始

### 运行 Windows 发布版

1. [下载发布包](https://github.com/Hulenkius/HulenCut/releases)
2. 双击 `HulenCut.exe`
3. 导入图片或文件夹开始处理

### 从源码运行

需要 Python 3.10+。

```powershell
python -m pip install -r requirements.txt
python cutter.py
```

或：

```powershell
python -m cutter_app
```

## 基本流程

1. 按 `Ctrl+O` 导入图片，或按 `Ctrl+Shift+O` 导入文件夹
2. 在画布上拖拽创建切片，或使用自动识别/表格识别
3. 在左侧列表中整理顺序、名称和尺寸
4. 按 `Ctrl+S` 保存 `.cutter` 工程
5. 按 `Ctrl+E` 导出切片

导出文件名默认格式：

```text
图片名_序号.png
图片名_序号_切片名称.png
```

## 快捷键

| 快捷键 | 功能 |
| --- | --- |
| `Ctrl+O` | 导入图片 |
| `Ctrl+Shift+O` | 导入文件夹 |
| `Ctrl+P` | 打开工程 |
| `Ctrl+S` | 保存工程 |
| `Ctrl+E` | 导出切片 |
| `Ctrl+K` | 命令面板 |
| `Ctrl+R` | 自动识别切片 |
| `Ctrl+T` | 自动识别表格 |
| `Ctrl+D` | 划分切片 |
| `Ctrl+M` | 移动切片 |
| `Ctrl+L` | 缩放切片 |
| `Ctrl+F` | 筛选切片 |
| `Ctrl+G` | 合并重叠切片 |
| `Ctrl+N` | 批量重命名 |
| `Ctrl+← / →` | 上一张 / 下一张图片 |
| `Ctrl+滚轮` | 缩放画布 |
| `Space + 拖拽` | 平移画布 |
| `方向键 / Shift+方向键` | 移动切片 1px / 10px |
| `Delete` | 删除选中切片 |

## 自动处理

- 在「自動處理」面板中录制操作并保存为 `.cscript` 脚本
- 支持导入、运行、重命名、删除脚本
- 可跨页循环执行整个图片文件夹
- 脚本导出前请先通过「導出 → 設定導出預設」设置默认目录和格式

## 打包

```powershell
python -m pip install pyinstaller
pyinstaller cutter.spec --noconfirm
```

输出目录：`dist/HulenCut/`

## 链接

- 项目主页：<https://vistudium.top/gouken/>
- 教程视频：<https://space.bilibili.com/66758675/lists/4816821>

## 致谢

Github Copilot、DeepSeek Harness、Basic、南池子、Kushim Jiang

本项目为 2025 年 1 月开始为[仲春仿宋](https://github.com/Hulenkius/sotyr)项目开发的配套软件，最初由 Github Copilot 编写，后由 DeepSeek Harness 规范化项目结构并构建现代化界面。于 2026 年 10 月 19 日开放源代码。