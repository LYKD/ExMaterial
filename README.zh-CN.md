# ExMaterial

<p align="center">
  <img src="docs/assets/exmaterial-logo.png" alt="ExMaterial 标志" width="180">
</p>

<p align="center">
  <strong>用于材料样品记录、XRD 处理与热导率绘图的桌面软件。</strong>
</p>

<p align="center">
  <a href="README.md">English</a> · <a href="LICENSE">GPL-3.0-only</a> · <a href="CHANGELOG.md">更新日志</a>
</p>

## 功能

- 新建材料体系与连续编号的样品，并记录制备/获得条件和备注。
- 记录多温度点热导率数据，并由密度、热容和热扩散率自动计算热导率。
- 导入、转换、处理、绘制和对比 `2θ` 与 `d` 坐标下的 XRD 数据。
- 选中材料后，将 XRD 文本文件拖入主窗口，每个文件自动新建一个样品，备注记录原文件名；拖到原始 `d` 数据框时按 `d` 坐标导入。
- 提供处理后 XRD 的归一化、平滑、手动寻峰、局部高斯修正和独立图窗查看。
- 将样品数据和生成图自动保存在本机 `information/` 目录。
- 启动时后台检查正式版更新，也可通过“帮助 → 检查更新”手动检查；Windows EXE 版支持下载、校验并重启更新。

## 安装与运行

免安装 Windows x64 版：[下载 ExMaterial 1.0.2](https://github.com/LYKD/ExMaterial/releases/download/v1.0.2/ExMaterial-1.0.2-windows-x64.exe)。本次修改详见 [发布说明](https://github.com/LYKD/ExMaterial/releases/tag/v1.0.2) 和 [更新日志](CHANGELOG.md)。v1.0.1 及更早版本需手动升级这一次，随后即可使用软件内更新。将下载的 EXE 放回原程序目录，保留同级 information 数据目录。

支持 Windows 上的 Python 3.10 或更高版本：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\exmaterial\exmaterial_app.py
```

首次启动会在源码目录旁创建 `information/`。这里保存实验记录，已被 Git 忽略，因此不会因开源代码而误上传。

## 构建 Windows 程序

```powershell
python -m pip install ".[build]"
.\exmaterial\build_windows.bat
```

构建后可执行文件为 `exmaterial\ExMaterial.exe`。移动已有工作区时，请让 `information/` 继续与 `exmaterial/` 目录保持同级。

详细使用说明、单位和数据文件说明见 [中文用户手册](exmaterial/readme.txt)。

## 拖入 XRD 文件

支持 TXT、CSV、TSV、XY、DAT 文本文件，可一次拖入多个；默认按 `2θ + 强度` 读取，拖到原始 `d` 数据框时按 `d + 强度` 读取。导入采用界面当前的波长及列号设置，文件名（含扩展名）写入新样品备注，当前样品及未保存编辑保持不变。支持 UTF-8、带 BOM 的 UTF-16 和 GB18030 文本；RAW 等仪器二进制格式请先导出为文本。

仪器说明行（例如 `X-Ray 40kV/15mA`）会跳过，不再混入衍射点。此前已保存的错误点不会自动删除，请用原文件重新导入为新样品。

## 软件更新

发现新版本后，点击“下载并重启更新”。下载完成后确认编辑内容已保存，程序会退出、替换自身并启动新版。更新只替换当前 EXE，`information/` 数据目录继续保留；新版启动失败时会尝试恢复旧程序。网络不可用时仍可正常使用软件，并可通过更新窗口打开发布页手动下载。

此前没有更新功能的旧 EXE 需要先手动下载一次包含此功能的版本；此后可在软件内更新。源码运行方式仅提供检查和发布页入口。

发布维护要求：正式 Release 使用 `v主版本.次版本.补丁版本` 标签，附带 `ExMaterial-版本-windows-x64.exe`（或 `ExMaterial.exe`），并确保 GitHub 资产提供 SHA-256 `digest`。缺少可校验 EXE 时软件提供手动下载入口。源码版本和程序显示版本来自同一版本定义，发布时须同步更新 `exmaterial/__init__.py` 和 `pyproject.toml`。

## 许可证

ExMaterial 使用 GNU General Public License v3.0 only（GPL-3.0-only）。你可以使用和修改本软件；公开分发修改版时，必须继续使用 GPLv3 并提供相应源代码。完整文本见 [LICENSE](LICENSE)。

## 贡献

欢迎提交问题、改进文档或聚焦明确的 Pull Request。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
