"""Dependency-free XPS processing. Energies are binding energies in eV."""
from __future__ import annotations

import json
import math
import os
import tempfile
from pathlib import Path

try:
    from .xrd_tools import extract_numbers
    from .thermal_tools import nice_tick_step
except ImportError:
    from xrd_tools import extract_numbers
    from thermal_tools import nice_tick_step


def parse_spectrum(text: str, energy_column: int = 1, intensity_column: int = 2):
    if min(energy_column, intensity_column) < 1 or energy_column == intensity_column:
        raise ValueError("列号从 1 开始，能量列与强度列不能相同。")
    points, skipped = [], 0
    for line in text.splitlines():
        if not line.strip():
            continue
        values = extract_numbers(line)
        if len(values) < max(energy_column, intensity_column):
            skipped += 1
            continue
        points.append((values[energy_column - 1], values[intensity_column - 1]))
    if len(points) < 3:
        raise ValueError("至少需要三个有效数据点（结合能 eV、强度）。")
    points.sort()
    if any(a[0] == b[0] for a, b in zip(points, points[1:])):
        raise ValueError("结合能有重复值；请将不同扫描或能区分开导入。")
    return points, skipped


def process_spectrum(points, *, shift=0.0, lower=None, upper=None,
                     background="none", window=1, normalize=False):
    if not math.isfinite(shift) or any(v is not None and not math.isfinite(v) for v in (lower, upper)):
        raise ValueError("能量校正和范围必须是有限数值。")
    if lower is not None and upper is not None and lower >= upper:
        raise ValueError("能区下限必须小于上限。")
    if background not in {"none", "linear"}:
        raise ValueError("未知背景类型。")
    if not isinstance(window, int) or window < 1 or window % 2 == 0:
        raise ValueError("平滑窗口必须为正奇数；1 表示不平滑。")
    rows = sorted((x + shift, y) for x, y in points)
    rows = [(x, y) for x, y in rows if (lower is None or x >= lower) and (upper is None or x <= upper)]
    if len(rows) < 3 or window > len(rows):
        raise ValueError("所选能区至少需要三个点，且点数不能小于平滑窗口。")
    if any(not math.isfinite(x) or not math.isfinite(y) for x, y in rows):
        raise ValueError("数据包含非有限数值。")
    if any(a[0] >= b[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("结合能必须互不重复。")
    xs, ys = zip(*rows)
    base = [0.0] * len(rows)
    if background == "linear":
        base = [ys[0] + (ys[-1] - ys[0]) * (x - xs[0]) / (xs[-1] - xs[0]) for x in xs]
    corrected = [y - b for y, b in zip(ys, base)]
    # Signed trapezoidal area BEFORE smoothing/normalization; retain negative signal.
    area = sum((xs[i + 1] - xs[i]) * (corrected[i] + corrected[i + 1]) / 2 for i in range(len(xs) - 1))
    prefix = [0.0]
    for y in corrected:
        prefix.append(prefix[-1] + y)
    half = window // 2
    smooth = []
    for i in range(len(rows)):
        left, right = max(0, i - half), min(len(rows), i + half + 1)
        smooth.append((prefix[right] - prefix[left]) / (right - left))
    if normalize:
        scale = max(abs(y) for y in smooth)
        if scale == 0:
            raise ValueError("零信号无法归一化。")
        smooth = [y / scale for y in smooth]
    peak = max(range(len(rows)), key=lambda i: smooth[i])
    return {"rows": [(x, raw, b, y) for x, raw, b, y in zip(xs, ys, base, smooth)],
            "area": area, "maximum_energy": xs[peak]}


def plot_config(result, normalized=False):
    points = [(r[0], r[3]) for r in result["rows"]]
    low, high = points[0][0], points[-1][0]
    return dict(points=points, title="XPS", xlabel="Binding energy (eV)",
                ylabel="Normalized intensity" if normalized else "Intensity (input units)",
                x_limits=(high, low), x_tick_step=nice_tick_step(high - low),
                connect_points=True, point_color="#147d78", point_radius=0)


def save_workspace(path: Path, payload: dict):
    """Replace one complete workspace atomically; preserve the previous file on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         suffix=".tmp", delete=False) as stream:
            name = stream.name
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
