# ExMaterial

<p align="center">
  <img src="docs/assets/exmaterial-logo.png" alt="ExMaterial logo" width="180">
</p>

<p align="center">
  <strong>A desktop workspace for materials-sample records, XRD processing, and thermal-conductivity plots.</strong>
</p>

<p align="center">
  <a href="README.zh-CN.md">简体中文</a> · <a href="LICENSE">GPL-3.0-only</a> · <a href="CHANGELOG.md">Changelog</a>
</p>

## What it does

- Creates material families and numbered samples, each with acquisition conditions and notes.
- Stores multi-temperature thermal measurements and calculates thermal conductivity from density, heat capacity, and diffusivity.
- Imports, converts, processes, plots, and compares XRD data in `2θ` and `d` coordinates.
- Supports processed-XRD normalization, smoothing, manual peak capture, local Gaussian adjustments, and independent plot viewing.
- Writes every sample's data and generated figures to a local `information/` directory.

## Install and run

ExMaterial supports Python 3.10 or later on Windows. Create an environment, install the dependency, then start the desktop app:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python .\exmaterial\exmaterial_app.py
```

The first run creates `information/` beside the source folder. This directory holds your experimental records and is intentionally ignored by Git, so it cannot accidentally be published with the open-source code.

## Build a Windows executable

```powershell
python -m pip install ".[build]"
.\exmaterial\build_windows.bat
```

The executable is written to `exmaterial\ExMaterial.exe`. Keep the `information/` directory beside the `exmaterial/` directory when moving an existing workspace.

## Data model

```text
information/
└── <material name>/
    ├── samples.json
    └── #<sample number>/
        ├── xrd_data.csv
        ├── xrd_2theta.jpg
        ├── xrd_d.jpg
        ├── processed_xrd_*.csv / *.jpg
        ├── manual_xrd_peaks.json
        └── thermal_conductivity_temperature.jpg
```

See the [Chinese user manual](exmaterial/readme.txt) for detailed workflow instructions and units.

## License

ExMaterial is released under the GNU General Public License v3.0 only (GPL-3.0-only). You may use and modify it; redistributed modified versions must remain GPLv3 and provide their corresponding source code. See [LICENSE](LICENSE).

## Contributing

Bug reports, documentation improvements, and focused pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first.
