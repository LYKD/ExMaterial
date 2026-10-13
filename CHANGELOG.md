# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Added

- Drag one or more exported XRD text files into the main window to create new samples in the selected material, with source filenames in sample notes. Drop onto the raw d input to use d coordinates.
- Bundle native TkDnD support in Windows executable builds.

### Fixed

- Skip instrument metadata such as `X-Ray 40kV/15mA` when parsing XRD text instead of turning it into a false `(40, 15)` data point.

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
