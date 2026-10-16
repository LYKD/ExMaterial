# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### 改进

- 源码运行、非 Windows 平台或发布缺少可校验安装包时，更新窗口不再显示无法使用的“下载并重启更新”按钮，改为说明当前运行方式与对应的手动升级步骤。
- 无法自动更新时，启动后台检查只在状态栏提示新版本，不再弹出更新窗口；“帮助 → 检查更新”仍提供完整说明和发布页入口。

## [1.0.3] - 2026-10-13

### 新增

- 支持将一个或多个导出的 XRD 文本文件拖入主窗口，在当前材料下批量创建样品，并将来源文件名写入备注；拖入原始 d 输入框时按 d 坐标解析。
- 支持 UTF-8、UTF-16、GB18030 等文本编码及带引号的 CSV 数值；Windows EXE 包含原生 TkDnD 拖拽依赖。

### 修复

- 跳过 X-Ray 40kV/15mA 等仪器说明行，避免将其中的数字误识别为测量点。
- 导入时先保存 XRD 数据，再原子提交样品记录；XRD 写入、JSON 写入或替换失败时回滚本次新建目录，不留下空样品，批次中其他有效文件继续导入。
- 已有样品、未登记但已存在的样品目录及原始导入文件保持完整；已有记录损坏时拒绝导入，避免覆盖记录。

### 贡献与升级

- 感谢 lzy（GitHub: stellariums）在 [PR #1](https://github.com/LYKD/ExMaterial/pull/1) 中贡献批量拖拽导入、文本解析与 TkDnD 打包支持；本次审核补充了保存失败回滚及故障注入测试。
- v1.0.2 可通过“帮助 → 检查更新”安装此版；更早的无更新器版本请手动下载一次，保留原 information 数据目录。

## [1.0.2] - 2026-10-13

### 新增与改进

- 主编辑区支持在图表、参数输入框、动态新增热导率行和滚动条上使用鼠标滚轮；文本框保留独立滚动，放大图窗保留滚轮缩放。
- 材料与样品列表的新增、删除按钮统一移至各自列表上方。
- 绘制原始 XRD、处理后 XRD 或温度—热导率图后，自动滚动到对应图区，重复绘图也会重新定位。
- 新增启动后台检查更新和“帮助 → 检查更新”；Windows EXE 可下载、校验并重启升级，启动失败时尝试回退。
- 更新包须通过大小和 SHA-256 校验，版本比较防止降级；网络检查失败不影响正常使用。

### 修复

- 处理后 XRD 使用形状保持插值，避免自然三次样条过冲后被截断为假平顶。
- 识别异常采集间隔，在缺测处断线；主界面预览、独立放大图窗和 JPG 导出采用一致的分段显示。
- d 图继续从原始 d 输入生成，保持 0–100 归一化，不增加雅可比强度权重；缺测区真实峰形不作推断。

### 升级说明

- v1.0.1 及更早 EXE 未内置更新器，需手动下载 v1.0.2 一次；此后可在软件内检查并安装后续版本。
- 替换原有程序目录中的 EXE 即可升级，保留同级 information 数据目录。

## [1.0.1] - 2026-09-20

### Fixed

- Kept processed d-axis XRD intensities on the original input scale before smoothing and normalization, so their peak/valley relationship is not distorted by a coordinate-dependent intensity correction.

## [1.0.0] - 2026-09-19

### Added

- First public ExMaterial release.
- Materials and sample record workspace.
- XRD import, `2θ`/`d` conversion, processing, plotting, comparison, and manual peak tools.
- Multi-temperature thermal-conductivity records and plots.
- Project documentation, build metadata, tests, GPLv3 licensing, and official logo assets.
