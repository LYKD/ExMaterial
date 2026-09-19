from __future__ import annotations

import math
from pathlib import Path

try:
    from .plot_viewer import save_scatter_jpg
except ImportError:  # Supports launching exmaterial_app.py directly.
    from plot_viewer import save_scatter_jpg


THERMAL_PLOT_FILE = "thermal_conductivity_temperature.jpg"


def calculate_thermal_conductivity(density_text: str, heat_capacity_text: str, diffusivity_text: str) -> str:
    try:
        density = float(density_text.strip())
        heat_capacity = float(heat_capacity_text.strip())
        diffusivity = float(diffusivity_text.strip())
    except ValueError:
        return ""
    return f"{density * heat_capacity * diffusivity:.6g}"


def thermal_points(rows: list[dict[str, str]]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for row in rows:
        conductivity_text = row.get("thermal_conductivity", "")
        if not conductivity_text:
            conductivity_text = calculate_thermal_conductivity(
                row.get("density", ""),
                row.get("heat_capacity", ""),
                row.get("thermal_diffusivity", ""),
            )
        try:
            temperature = float(row.get("temperature_c", "").strip())
            conductivity = float(conductivity_text.strip())
        except ValueError:
            continue
        points.append((temperature, conductivity))
    return sorted(points, key=lambda point: point[0])


def nice_tick_step(span: float) -> float:
    if span <= 0:
        return 1.0
    raw = span / 6
    magnitude = 10 ** math.floor(math.log10(raw))
    for multiplier in (1, 2, 5, 10):
        step = multiplier * magnitude
        if raw <= step:
            return step
    return 10 * magnitude


def x_limits_and_step(points: list[tuple[float, float]]) -> tuple[tuple[float, float], float]:
    xs = [point[0] for point in points]
    x_min, x_max = min(xs), max(xs)
    if x_min == x_max:
        pad = 5 if x_min == 0 else abs(x_min) * 0.1
        return (x_min - pad, x_max + pad), nice_tick_step(pad * 2)
    span = x_max - x_min
    pad = span * 0.08
    limits = (x_min - pad, x_max + pad)
    return limits, nice_tick_step(limits[1] - limits[0])


def thermal_plot_config(points: list[tuple[float, float]]) -> dict:
    x_limits, x_tick_step = x_limits_and_step(points)
    return {
        "points": points,
        "title": "热导率-温度",
        "xlabel": "温度 (°C)",
        "ylabel": "热导率 (W/(m·K))",
        "x_limits": x_limits,
        "x_tick_step": x_tick_step,
        "connect_points": True,
        "point_color": "#d62728",
        "point_radius": 4.2,
    }


def save_thermal_plot(path: Path, points: list[tuple[float, float]]) -> None:
    config = thermal_plot_config(points)
    save_scatter_jpg(path, **config)
