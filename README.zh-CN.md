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
- 提供处理后 XRD 的归一化、平滑、手动寻峰、局部高斯修正和独立图窗查看。
- 将样品数据和生成图自动保存在本机 `information/` 目录。

## 安装与运行

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

## 许可证

ExMaterial 使用 GNU General Public License v3.0 only（GPL-3.0-only）。你可以使用和修改本软件；公开分发修改版时，必须继续使用 GPLv3 并提供相应源代码。完整文本见 [LICENSE](LICENSE)。

## 贡献

欢迎提交问题、改进文档或聚焦明确的 Pull Request。提交前请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
