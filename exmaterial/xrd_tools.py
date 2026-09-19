from __future__ import annotations

import csv
import math
import re
from bisect import bisect_right
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, Y, Button, Canvas, Entry, Frame, Label, LabelFrame, Listbox, Scrollbar, StringVar, Toplevel, filedialog, messagebox, ttk

try:
    from .plot_viewer import CANVAS_MARGIN, PlotViewer, draw_scatter_plot, save_scatter_jpg, x_ticks
except ImportError:  # Supports launching exmaterial_app.py directly.
    from plot_viewer import CANVAS_MARGIN, PlotViewer, draw_scatter_plot, save_scatter_jpg, x_ticks


XRD_DATA_FILE = "xrd_data.csv"
PLOT_2THETA_FILE = "xrd_2theta.jpg"
PLOT_D_FILE = "xrd_d.jpg"
PROCESSED_XRD_DATA_THETA_FILE = "processed_xrd_2theta_data.csv"
PROCESSED_XRD_DATA_D_FILE = "processed_xrd_d_data.csv"
PROCESSED_PLOT_2THETA_FILE = "processed_xrd_2theta.jpg"
PROCESSED_PLOT_D_FILE = "processed_xrd_d.jpg"
MANUAL_XRD_PEAKS_FILE = "manual_xrd_peaks.json"
DEFAULT_WAVELENGTH = "1.5406"
MAX_PLOT_POINTS = 30000
MAX_PROCESSED_PLOT_POINTS = 16000
MAX_CANVAS_POINTS = 3000
MAX_PROCESSED_CANVAS_POINTS = 8000


def downsample_points(points: list[tuple[float, float]], max_points: int = MAX_PLOT_POINTS) -> list[tuple[float, float]]:
    if len(points) <= max_points:
        return points
    step = math.ceil(len(points) / max_points)
    return points[::step]


def extract_numbers(line: str) -> list[float]:
    normalized = line.replace(",", " ").replace(";", " ").replace("\t", " ")
    matches = re.findall(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", normalized)
    return [float(item) for item in matches]


def infer_xrd_columns(numeric_rows: list[tuple[int, list[float]]]) -> tuple[int, int]:
    max_cols = max(len(numbers) for _row_index, numbers in numeric_rows)
    if max_cols <= 2:
        return 0, 1
    best_col = 0
    best_score = -1.0
    for col in range(max_cols):
        values = [numbers[col] for _row_index, numbers in numeric_rows if len(numbers) > col]
        if len(values) < 2:
            continue
        valid_values = [value for value in values if 0 < value < 180]
        valid_ratio = len(valid_values) / len(values)
        if valid_ratio < 0.75:
            continue
        compared_steps = 0
        monotonic_steps = 0
        for left, right in zip(values, values[1:]):
            if 0 < left < 180 and 0 < right < 180:
                compared_steps += 1
                if right >= left:
                    monotonic_steps += 1
        monotonic_ratio = monotonic_steps / compared_steps if compared_steps else 0
        value_range = max(valid_values) - min(valid_values)
        range_score = min(value_range / 20, 1)
        next_values = [numbers[col + 1] for _row_index, numbers in numeric_rows if len(numbers) > col + 1]
        next_range = max(next_values) - min(next_values) if len(next_values) >= 2 else 0
        next_range_score = min(next_range / 100, 1)
        has_next_score = 1 if col + 1 < max_cols else 0
        score = valid_ratio * 0.3 + monotonic_ratio * 0.3 + range_score * 0.1 + next_range_score * 0.2 + has_next_score * 0.1
        if score > best_score:
            best_col = col
            best_score = score
    intensity_col = best_col + 1 if best_col + 1 < max_cols else (1 if best_col != 1 else 0)
    return best_col, intensity_col


def selected_or_inferred_xrd_columns(numeric_rows: list[tuple[int, list[float]]], theta_text: str, intensity_text: str) -> tuple[int, int]:
    theta_text = theta_text.strip()
    intensity_text = intensity_text.strip()
    if not theta_text and not intensity_text:
        return infer_xrd_columns(numeric_rows)
    if not theta_text or not intensity_text:
        raise ValueError("如果手动填写列号，请同时填写 2theta列 和 强度列。")
    try:
        theta_col = int(theta_text) - 1
        intensity_col = int(intensity_text) - 1
    except ValueError as exc:
        raise ValueError("列号必须是正整数，例如 1、2、3。") from exc
    if theta_col < 0 or intensity_col < 0:
        raise ValueError("列号必须从 1 开始。")
    if theta_col == intensity_col:
        raise ValueError("2theta列 和 强度列不能是同一列。")
    return theta_col, intensity_col


def parse_wavelength(wavelength_text: str) -> float:
    try:
        wavelength = float(wavelength_text.strip() or DEFAULT_WAVELENGTH)
    except ValueError as exc:
        raise ValueError("XRD 波长必须是数字。") from exc
    if wavelength <= 0:
        raise ValueError("XRD 波长必须大于 0。")
    return wavelength


def theta_to_d(two_theta: float, wavelength: float) -> float:
    if two_theta <= 0 or two_theta >= 180:
        raise ValueError("2theta 必须在 0 到 180 之间。")
    return wavelength / (2 * math.sin(math.radians(two_theta / 2)))


def d_to_theta(d_value: float, wavelength: float) -> float:
    if d_value <= 0:
        raise ValueError("d 必须大于 0。")
    ratio = wavelength / (2 * d_value)
    if ratio <= 0 or ratio > 1:
        raise ValueError("该 d 值无法用当前波长转换为 2theta。")
    return math.degrees(2 * math.asin(ratio))


def infer_d_columns(numeric_rows: list[tuple[int, list[float]]]) -> tuple[int, int]:
    max_cols = max(len(numbers) for _row_index, numbers in numeric_rows)
    if max_cols <= 2:
        return 0, 1
    best_col = 0
    best_score = -1.0
    for col in range(max_cols):
        values = [numbers[col] for _row_index, numbers in numeric_rows if len(numbers) > col]
        if len(values) < 2:
            continue
        valid_values = [value for value in values if 0 < value < 100]
        valid_ratio = len(valid_values) / len(values)
        if valid_ratio < 0.75:
            continue
        compared_steps = 0
        increasing_steps = 0
        decreasing_steps = 0
        for left, right in zip(values, values[1:]):
            if 0 < left < 100 and 0 < right < 100:
                compared_steps += 1
                if right >= left:
                    increasing_steps += 1
                if right <= left:
                    decreasing_steps += 1
        monotonic_ratio = max(increasing_steps, decreasing_steps) / compared_steps if compared_steps else 0
        value_range = max(valid_values) - min(valid_values)
        range_score = min(value_range / 3, 1)
        next_values = [numbers[col + 1] for _row_index, numbers in numeric_rows if len(numbers) > col + 1]
        next_range = max(next_values) - min(next_values) if len(next_values) >= 2 else 0
        next_range_score = min(next_range / 100, 1)
        has_next_score = 1 if col + 1 < max_cols else 0
        score = valid_ratio * 0.35 + monotonic_ratio * 0.25 + range_score * 0.1 + next_range_score * 0.2 + has_next_score * 0.1
        if score > best_score:
            best_col = col
            best_score = score
    intensity_col = best_col + 1 if best_col + 1 < max_cols else (1 if best_col != 1 else 0)
    return best_col, intensity_col


def selected_or_inferred_axis_columns(numeric_rows: list[tuple[int, list[float]]], axis_text: str, intensity_text: str, axis_kind: str) -> tuple[int, int]:
    axis_text = axis_text.strip()
    intensity_text = intensity_text.strip()
    if not axis_text and not intensity_text:
        return infer_d_columns(numeric_rows) if axis_kind == "d" else infer_xrd_columns(numeric_rows)
    if not axis_text or not intensity_text:
        raise ValueError("如果手动填写列号，请同时填写 横坐标列 和 强度列。")
    try:
        axis_col = int(axis_text) - 1
        intensity_col = int(intensity_text) - 1
    except ValueError as exc:
        raise ValueError("列号必须是正整数，例如 1、2、3。") from exc
    if axis_col < 0 or intensity_col < 0:
        raise ValueError("列号必须从 1 开始。")
    if axis_col == intensity_col:
        raise ValueError("横坐标列 和 强度列不能是同一列。")
    return axis_col, intensity_col


def parse_xrd_axis_text(raw_text: str, wavelength_text: str, axis_kind: str, axis_column: str = "", intensity_column: str = "") -> tuple[list[tuple[float, float, float]], int]:
    wavelength = parse_wavelength(wavelength_text)
    numeric_rows: list[tuple[int, list[float]]] = []
    for row_index, line in enumerate(raw_text.splitlines(), start=1):
        numbers = extract_numbers(line)
        if len(numbers) >= 2:
            numeric_rows.append((row_index, numbers))
    axis_label = "d" if axis_kind == "d" else "2theta"
    if len(numeric_rows) < 2:
        raise ValueError(f"至少需要两行有效 XRD 数据才能画图。请确认数据中包含 {axis_label} 和强度两列。")
    axis_col, intensity_col = selected_or_inferred_axis_columns(numeric_rows, axis_column, intensity_column, axis_kind)
    rows: list[tuple[float, float, float]] = []
    skipped_rows = len(raw_text.splitlines()) - len(numeric_rows)
    for _row_index, numbers in numeric_rows:
        if len(numbers) <= max(axis_col, intensity_col):
            skipped_rows += 1
            continue
        axis_value, intensity = numbers[axis_col], numbers[intensity_col]
        try:
            if axis_kind == "d":
                d_value = axis_value
                two_theta = d_to_theta(d_value, wavelength)
            else:
                two_theta = axis_value
                d_value = theta_to_d(two_theta, wavelength)
        except ValueError:
            skipped_rows += 1
            continue
        rows.append((two_theta, intensity, d_value))
    if len(rows) < 2:
        raise ValueError("至少需要两行有效 XRD 数据才能画图。请确认列号和数据内容。")
    return rows, skipped_rows


def format_xrd_value(value: float) -> str:
    return f"{value:.10g}"


def rows_to_theta_text(rows: list[tuple[float, float, float]]) -> str:
    return "\n".join(f"{format_xrd_value(theta)}\t{format_xrd_value(intensity)}" for theta, intensity, _d_value in rows)


def rows_to_d_text(rows: list[tuple[float, float, float]]) -> str:
    return "\n".join(f"{format_xrd_value(d_value)}\t{format_xrd_value(intensity)}" for _theta, intensity, d_value in rows)


def gaussian_smooth(values: list[float], sigma_samples: float) -> list[float]:
    """Positive-weight smoothing avoids the negative side lobes of SG filtering."""
    if len(values) < 5 or sigma_samples < 0.75:
        return values[:]
    radius = min(math.ceil(sigma_samples * 3), len(values) - 1)
    weights = [math.exp(-0.5 * (offset / sigma_samples) ** 2) for offset in range(-radius, radius + 1)]
    smoothed: list[float] = []
    for index in range(len(values)):
        total = 0.0
        weight_total = 0.0
        for offset, weight in zip(range(-radius, radius + 1), weights):
            source_index = index + offset
            if 0 <= source_index < len(values):
                total += values[source_index] * weight
                weight_total += weight
        smoothed.append(total / weight_total)
    return smoothed


def _unique_coordinate_values(rows: list[tuple[float, float, float]]) -> tuple[list[float], list[float]]:
    """Return increasing 2theta coordinates with duplicate positions averaged."""
    coordinates: list[float] = []
    values: list[float] = []
    counts: list[int] = []
    for theta, intensity, _d_value in sorted_finite_rows(rows, "theta"):
        if coordinates and math.isclose(theta, coordinates[-1], abs_tol=1e-12):
            counts[-1] += 1
            values[-1] += (intensity - values[-1]) / counts[-1]
        else:
            coordinates.append(theta)
            values.append(intensity)
            counts.append(1)
    return coordinates, values


def linear_interpolate(
    coordinates: list[float],
    values: list[float],
    targets: list[float],
) -> list[float]:
    if not coordinates:
        return []
    if len(coordinates) == 1:
        return [values[0] for _target in targets]
    output: list[float] = []
    for target in targets:
        if target <= coordinates[0]:
            output.append(values[0])
            continue
        if target >= coordinates[-1]:
            output.append(values[-1])
            continue
        right = bisect_right(coordinates, target)
        left = right - 1
        fraction = (target - coordinates[left]) / (coordinates[right] - coordinates[left])
        output.append(values[left] + fraction * (values[right] - values[left]))
    return output


def coordinate_aware_smooth(rows: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    """Smooth intensity on an evenly spaced 2theta grid, then restore input positions."""
    source_rows = sorted_finite_rows(rows, "theta")
    coordinates, values = _unique_coordinate_values(source_rows)
    if len(coordinates) < 5 or coordinates[0] == coordinates[-1]:
        return source_rows
    uniform_coordinates = [
        coordinates[0] + (coordinates[-1] - coordinates[0]) * index / (len(coordinates) - 1)
        for index in range(len(coordinates))
    ]
    uniform_values = linear_interpolate(coordinates, values, uniform_coordinates)
    step_size = (coordinates[-1] - coordinates[0]) / (len(coordinates) - 1)
    sigma_samples = 0.18 / max(step_size, 1e-12)
    smoothed_values = gaussian_smooth(uniform_values, sigma_samples)
    restored_values = linear_interpolate(uniform_coordinates, smoothed_values, [row[0] for row in source_rows])
    return [
        (theta, intensity, d_value)
        for (theta, _old_intensity, d_value), intensity in zip(source_rows, restored_values)
    ]


def normalize_intensities(rows: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    if not rows:
        return []
    min_intensity = min(intensity for _theta, intensity, _d_value in rows)
    shifted = [(theta, intensity - min_intensity, d_value) for theta, intensity, d_value in rows]
    max_intensity = max(intensity for _theta, intensity, _d_value in shifted)
    if max_intensity <= 0:
        return [(theta, 0.0, d_value) for theta, _intensity, d_value in shifted]
    return [(theta, intensity / max_intensity * 100, d_value) for theta, intensity, d_value in shifted]


def clamp_processed_intensities(rows: list[tuple[float, float, float]]) -> list[tuple[float, float, float]]:
    return [
        (theta, min(max(intensity, 0.0), 100.0), d_value)
        for theta, intensity, d_value in rows
    ]


def enforce_processed_scale(rows: list[tuple[float, float, float]], sort_axis: str = "theta") -> list[tuple[float, float, float]]:
    return clamp_processed_intensities(normalize_intensities(sorted_finite_rows(rows, sort_axis)))


def normalize_intensities_with_reference(
    rows: list[tuple[float, float, float]],
    reference_rows: list[tuple[float, float, float]],
) -> list[tuple[float, float, float]]:
    if not rows:
        return []
    reference = reference_rows or rows
    min_intensity = min(intensity for _theta, intensity, _d_value in reference)
    max_intensity = max(intensity for _theta, intensity, _d_value in reference)
    span = max_intensity - min_intensity
    if span <= 0:
        return [(theta, 0.0, d_value) for theta, _intensity, d_value in rows]
    return [
        (theta, min(max((intensity - min_intensity) / span * 100, 0.0), 100.0), d_value)
        for theta, intensity, d_value in rows
    ]


def normalize_processed_rows_for_plot(rows: list[tuple[float, float, float]], axis_kind: str) -> list[tuple[float, float, float]]:
    sort_axis = "d" if axis_kind == "d" else "theta"
    sorted_rows = sorted_finite_rows(rows, sort_axis)
    if axis_kind == "d":
        d_upper, d_lower = d_plot_limits(sorted_rows)
        visible_rows = [row for row in sorted_rows if d_lower <= row[2] <= d_upper]
    else:
        visible_rows = [row for row in sorted_rows if 10 <= row[0] <= 100]
    return clamp_processed_intensities(normalize_intensities_with_reference(sorted_rows, visible_rows))


def sorted_finite_rows(rows: list[tuple[float, float, float]], sort_axis: str = "theta") -> list[tuple[float, float, float]]:
    clean_rows = [
        (two_theta, intensity, d_value)
        for two_theta, intensity, d_value in rows
        if math.isfinite(two_theta) and math.isfinite(intensity) and math.isfinite(d_value)
    ]
    if sort_axis == "d":
        clean_rows.sort(key=lambda item: item[2], reverse=True)
    else:
        clean_rows.sort(key=lambda item: item[0])
    return clean_rows


def finalize_processed_rows(rows: list[tuple[float, float, float]], sort_axis: str = "theta") -> list[tuple[float, float, float]]:
    return enforce_processed_scale(rows, sort_axis)


def process_xrd_rows(rows: list[tuple[float, float, float]], sort_axis: str = "theta") -> list[tuple[float, float, float]]:
    """Smooth and normalize one input axis without changing its peak intensities."""
    clean_rows = sorted_finite_rows(rows, sort_axis)
    if not clean_rows:
        return []
    normalized = normalize_intensities(clean_rows)
    smoothed_rows = coordinate_aware_smooth(normalized)
    return enforce_processed_scale(smoothed_rows, sort_axis)


def processed_rows_from_text(raw_text: str, wavelength_text: str, axis_kind: str) -> list[tuple[float, float, float]]:
    rows, _skipped_rows = parse_xrd_axis_text(raw_text, wavelength_text, axis_kind, "1", "2")
    processed_rows = finalize_processed_rows(rows, "d" if axis_kind == "d" else "theta")
    if not processed_rows:
        return []
    return enforce_processed_scale(processed_rows, "d" if axis_kind == "d" else "theta")


def processed_plot_points(rows: list[tuple[float, float, float]], axis_kind: str) -> list[tuple[float, float]]:
    if axis_kind == "d":
        return [(d_value, min(max(intensity, 0.0), 100.0)) for _theta, intensity, d_value in rows]
    return [(theta, min(max(intensity, 0.0), 100.0)) for theta, intensity, _d_value in rows]


def d_plot_limits(rows: list[tuple[float, float, float]]) -> tuple[float, float]:
    """Keep the d view wide enough to contain the visible 2theta=10° boundary."""
    visible_d_values = [d_value for theta, _intensity, d_value in rows if 10 <= theta <= 100]
    if not visible_d_values:
        return (8, 1)
    upper_limit = max(8, math.ceil(max(visible_d_values) - 1e-9))
    return (float(upper_limit), 1.0)


def cubic_spline_interpolate(points: list[tuple[float, float]], target_count: int) -> list[tuple[float, float]]:
    """Return a natural cubic spline with continuous curvature between processed points."""
    ordered = sorted((x_value, y_value) for x_value, y_value in points if math.isfinite(x_value) and math.isfinite(y_value))
    if len(ordered) < 2:
        return ordered
    x_values: list[float] = []
    y_values: list[float] = []
    counts: list[int] = []
    for x_value, y_value in ordered:
        if x_values and math.isclose(x_value, x_values[-1], abs_tol=1e-12):
            counts[-1] += 1
            y_values[-1] += (y_value - y_values[-1]) / counts[-1]
        else:
            x_values.append(x_value)
            y_values.append(y_value)
            counts.append(1)
    if len(x_values) < 3 or x_values[0] == x_values[-1]:
        return list(zip(x_values, y_values))
    intervals = [right - left for left, right in zip(x_values, x_values[1:])]
    alpha = [0.0] * len(x_values)
    for index in range(1, len(x_values) - 1):
        alpha[index] = 3 * ((y_values[index + 1] - y_values[index]) / intervals[index] - (y_values[index] - y_values[index - 1]) / intervals[index - 1])
    lower = [1.0] + [0.0] * (len(x_values) - 1)
    upper = [0.0] * len(x_values)
    temporary = [0.0] * len(x_values)
    for index in range(1, len(x_values) - 1):
        lower[index] = 2 * (x_values[index + 1] - x_values[index - 1]) - intervals[index - 1] * upper[index - 1]
        if abs(lower[index]) < 1e-12:
            return list(zip(x_values, y_values))
        upper[index] = intervals[index] / lower[index]
        temporary[index] = (alpha[index] - intervals[index - 1] * temporary[index - 1]) / lower[index]
    coefficients_c = [0.0] * len(x_values)
    coefficients_b = [0.0] * (len(x_values) - 1)
    coefficients_d = [0.0] * (len(x_values) - 1)
    for index in range(len(x_values) - 2, -1, -1):
        coefficients_c[index] = temporary[index] - upper[index] * coefficients_c[index + 1]
        coefficients_b[index] = (y_values[index + 1] - y_values[index]) / intervals[index] - intervals[index] * (coefficients_c[index + 1] + 2 * coefficients_c[index]) / 3
        coefficients_d[index] = (coefficients_c[index + 1] - coefficients_c[index]) / (3 * intervals[index])
    target_count = max(2, target_count)
    queries = [
        x_values[0] + (x_values[-1] - x_values[0]) * index / (target_count - 1)
        for index in range(target_count)
    ]
    output: list[tuple[float, float]] = []
    interval_index = 0
    for query in queries:
        while interval_index < len(intervals) - 1 and query > x_values[interval_index + 1]:
            interval_index += 1
        offset = query - x_values[interval_index]
        output.append(
            (
                query,
                y_values[interval_index]
                + coefficients_b[interval_index] * offset
                + coefficients_c[interval_index] * offset * offset
                + coefficients_d[interval_index] * offset * offset * offset,
            )
        )
    return output


def processed_curve_points(
    rows: list[tuple[float, float, float]],
    axis_kind: str,
    max_points: int = MAX_PROCESSED_CANVAS_POINTS,
) -> list[tuple[float, float]]:
    points = processed_plot_points(rows, axis_kind)
    target_count = min(max_points, max(600, len(points) * 4))
    curve = cubic_spline_interpolate(points, target_count)
    if axis_kind == "d":
        curve.reverse()
    return [(x_value, min(max(y_value, 0.0), 100.0)) for x_value, y_value in curve]


def processed_plot_config(
    points: list[tuple[float, float]],
    axis_kind: str,
    max_points: int = MAX_CANVAS_POINTS,
    d_x_limits: tuple[float, float] | None = None,
) -> dict:
    display_points = downsample_points(points, max_points)
    if axis_kind == "d":
        return {
            "points": display_points,
            "title": "XRD 处理后: d",
            "xlabel": "d (Å)",
            "ylabel": "强度",
            "x_limits": d_x_limits or (8, 1),
            "x_tick_step": 1,
            "y_limits": (0, 100),
            "connect_points": True,
            "smooth_line": False,
            "point_radius": 0.0,
        }
    return {
        "points": display_points,
        "title": "XRD 处理后: 2theta",
        "xlabel": "2theta (°)",
        "ylabel": "强度",
        "x_limits": (10, 100),
        "x_tick_step": 10,
        "y_limits": (0, 100),
        "connect_points": True,
        "smooth_line": False,
        "point_radius": 0.0,
    }


def manual_peak_axis_value(row: tuple[float, float, float], axis_kind: str) -> float:
    return row[2] if axis_kind == "d" else row[0]


def find_manual_peak(
    rows: list[tuple[float, float, float]],
    axis_kind: str,
    position: float,
    half_width: float,
) -> tuple[float, float, float] | None:
    if half_width <= 0:
        raise ValueError("搜索半宽必须大于 0。")
    clean_rows = sorted_finite_rows(rows, "d" if axis_kind == "d" else "theta")
    if not clean_rows:
        return None
    nearby = [row for row in clean_rows if abs(manual_peak_axis_value(row, axis_kind) - position) <= half_width]
    candidates = nearby or clean_rows
    return max(candidates, key=lambda row: (row[1], -abs(manual_peak_axis_value(row, axis_kind) - position)))


def gaussian_peak_correction(
    rows: list[tuple[float, float, float]],
    axis_kind: str,
    position: float,
    target_intensity: float,
    half_width: float,
) -> tuple[list[tuple[float, float, float]], tuple[float, float, float] | None]:
    """Round one manually selected peak with a locally blended Gaussian profile."""
    if not 0 <= target_intensity <= 100:
        raise ValueError("峰高必须在 0 到 100 之间。")
    if half_width <= 0:
        raise ValueError("影响半宽必须大于 0。")
    sort_axis = "d" if axis_kind == "d" else "theta"
    clean_rows = sorted_finite_rows(rows, sort_axis)
    peak = find_manual_peak(clean_rows, axis_kind, position, half_width)
    if peak is None:
        return clean_rows, None
    center = manual_peak_axis_value(peak, axis_kind)
    left_candidates = [row for row in clean_rows if manual_peak_axis_value(row, axis_kind) <= center - half_width]
    right_candidates = [row for row in clean_rows if manual_peak_axis_value(row, axis_kind) >= center + half_width]
    left_row = max(left_candidates, key=lambda row: manual_peak_axis_value(row, axis_kind)) if left_candidates else min(clean_rows, key=lambda row: manual_peak_axis_value(row, axis_kind))
    right_row = min(right_candidates, key=lambda row: manual_peak_axis_value(row, axis_kind)) if right_candidates else max(clean_rows, key=lambda row: manual_peak_axis_value(row, axis_kind))
    left_x = manual_peak_axis_value(left_row, axis_kind)
    right_x = manual_peak_axis_value(right_row, axis_kind)

    def baseline(x_value: float) -> float:
        if math.isclose(left_x, right_x, abs_tol=1e-12):
            return (left_row[1] + right_row[1]) / 2
        fraction = (x_value - left_x) / (right_x - left_x)
        return left_row[1] + fraction * (right_row[1] - left_row[1])

    center_baseline = baseline(center)
    amplitude = target_intensity - center_baseline
    sigma = max(half_width / 2.5, 1e-12)
    corrected: list[tuple[float, float, float]] = []
    for row in clean_rows:
        x_value = manual_peak_axis_value(row, axis_kind)
        distance = abs(x_value - center)
        intensity = row[1]
        if distance <= half_width:
            gaussian = baseline(x_value) + amplitude * math.exp(-0.5 * ((x_value - center) / sigma) ** 2)
            blend = 0.5 * (1 + math.cos(math.pi * distance / half_width))
            intensity = intensity * (1 - blend) + gaussian * blend
        corrected.append((row[0], min(max(intensity, 0.0), 100.0), row[2]))
    snapped = find_manual_peak(corrected, axis_kind, center, half_width)
    return corrected, snapped


def parse_xrd_text(raw_text: str, wavelength_text: str, theta_column: str = "", intensity_column: str = "") -> tuple[list[tuple[float, float, float]], int]:
    return parse_xrd_axis_text(raw_text, wavelength_text, "theta", theta_column, intensity_column)


def save_xrd_csv(path: Path, rows: list[tuple[float, float, float]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(["2theta", "intensity", "d"])
        writer.writerows(rows)


def load_xrd_csv(path: Path) -> list[tuple[float, float, float]]:
    rows: list[tuple[float, float, float]] = []
    if not path.exists():
        return rows
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                rows.append((float(row["2theta"]), float(row["intensity"]), float(row["d"])))
            except (KeyError, TypeError, ValueError):
                continue
    return rows


COLORS = ["#222222", "#b45f06", "#ff8c00", "#c8d642", "#72b34a", "#299438", "#7a4fb5", "#1f77b4"]


def prepare_comparison_series(raw_series: list[dict]) -> tuple[list[dict], tuple[float, float]]:
    max_norm = 1.0
    offset = max_norm * 0.85
    prepared = []
    for index, item in enumerate(raw_series):
        points = item["points"]
        values = item["values"]
        display_points = [(d_value, offset * index + norm_value) for (d_value, _intensity), norm_value in zip(points, values)]
        prepared.append(
            {
                "label": item["label"],
                "points": points,
                "values": values,
                "display_points": display_points,
                "color": COLORS[index % len(COLORS)],
                "baseline": offset * index,
            }
        )
    y_min = -max_norm * 0.15
    y_max = max_norm + offset * max(len(prepared) - 1, 0) + max_norm * 0.15
    return prepared, (y_min, y_max)


def draw_xrd_comparison(canvas: Canvas, series: list[dict], x_limits: tuple[float, float] = (8, 1), y_limits: tuple[float, float] | None = None, crosshair: tuple[float, float] | None = None) -> None:
    canvas.delete("all")
    width = max(canvas.winfo_width(), 700)
    height = max(canvas.winfo_height(), 520)
    margin_left, margin_right, margin_top, margin_bottom = 86, 170, 34, 58
    x_min, x_max = x_limits
    prepared, default_y_limits = prepare_comparison_series(series)
    y_min, y_max = y_limits or default_y_limits

    def sx(x_value: float) -> float:
        return margin_left + (x_value - x_min) / (x_max - x_min) * (width - margin_left - margin_right)

    def sy(y_value: float) -> float:
        return height - margin_bottom - (y_value - y_min) / (y_max - y_min) * (height - margin_top - margin_bottom)

    canvas.create_line(margin_left, margin_top, margin_left, height - margin_bottom, fill="#222222")
    canvas.create_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, fill="#222222")
    canvas.create_text(20, height / 2, text="Intensity (a.u.)", angle=90, font=("Arial", 11))
    canvas.create_text((margin_left + width - margin_right) / 2, height - 18, text="d (Å)", font=("Arial", 11))
    for x_value in x_ticks(x_limits, 1):
        x_pos = sx(x_value)
        canvas.create_line(x_pos, height - margin_bottom, x_pos, height - margin_bottom + 5, fill="#222222")
        canvas.create_text(x_pos, height - margin_bottom + 19, text=f"{x_value:g}", font=("Arial", 9))
    legend_x = width - margin_right + 18
    legend_y = margin_top + 10
    canvas.create_text(legend_x, margin_top - 10, text="样品", anchor="w", font=("Arial", 10, "bold"))
    for index, item in enumerate(prepared):
        color = item["color"]
        coords = []
        for d_value, y_value in item["display_points"]:
            if min(x_min, x_max) <= d_value <= max(x_min, x_max):
                coords.extend([sx(d_value), sy(y_value)])
        if len(coords) >= 4:
            canvas.create_line(*coords, fill=color, width=2)
        y_text = legend_y + index * 22
        canvas.create_line(legend_x, y_text, legend_x + 22, y_text, fill=color, width=3)
        canvas.create_text(legend_x + 28, y_text, text=item["label"], anchor="w", fill=color, font=("Arial", 9))
    if crosshair:
        cross_x, cross_y = crosshair
        if min(x_min, x_max) <= cross_x <= max(x_min, x_max) and y_min <= cross_y <= y_max:
            x_pos = sx(cross_x)
            y_pos = sy(cross_y)
            canvas.create_line(x_pos, margin_top, x_pos, height - margin_bottom, fill="#aa3333", dash=(4, 3))
            canvas.create_line(margin_left, y_pos, width - margin_right, y_pos, fill="#aa3333", dash=(4, 3))
            canvas.create_text(width - margin_right - 8, margin_top + 12, text=f"x={cross_x:.5g}, y={cross_y:.5g}", anchor="e", fill="#aa3333", font=("Arial", 9))


def save_xrd_comparison_jpg(path: Path, series: list[dict]) -> None:
    if path.suffix.lower() not in {".jpg", ".jpeg"}:
        path = path.with_suffix(".jpg")
    if not series:
        return
    from PIL import Image, ImageDraw

    width, height = 1200, 850
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    margin_left, margin_right, margin_top, margin_bottom = 130, 230, 56, 95
    x_min, x_max = (8, 1)
    prepared, (y_min, y_max) = prepare_comparison_series(series)

    def sx(x_value: float) -> float:
        return margin_left + (x_value - x_min) / (x_max - x_min) * (width - margin_left - margin_right)

    def sy(y_value: float) -> float:
        return height - margin_bottom - (y_value - y_min) / (y_max - y_min) * (height - margin_top - margin_bottom)

    draw.line((margin_left, margin_top, margin_left, height - margin_bottom), fill="#222222", width=3)
    draw.line((margin_left, height - margin_bottom, width - margin_right, height - margin_bottom), fill="#222222", width=3)
    draw.text(((margin_left + width - margin_right) / 2 - 20, height - 48), "d (Å)", fill="#000000")
    draw.text((22, height / 2), "Intensity (a.u.)", fill="#000000")
    for x_value in x_ticks((8, 1), 1):
        x_pos = sx(x_value)
        draw.line((x_pos, height - margin_bottom, x_pos, height - margin_bottom + 10), fill="#222222", width=2)
        draw.text((x_pos - 8, height - margin_bottom + 20), f"{x_value:g}", fill="#000000")
    legend_x = width - margin_right + 25
    legend_y = margin_top + 20
    draw.text((legend_x, margin_top - 12), "样品", fill="#000000")
    for index, item in enumerate(prepared):
        color = item["color"]
        line_points = []
        for d_value, y_value in item["display_points"]:
            if 1 <= d_value <= 8:
                line_points.append((sx(d_value), sy(y_value)))
        if len(line_points) >= 2:
            draw.line(line_points, fill=color, width=3)
        y_text = legend_y + index * 28
        draw.line((legend_x, y_text, legend_x + 30, y_text), fill=color, width=4)
        draw.text((legend_x + 38, y_text - 8), item["label"], fill=color)
    image.save(path, "JPEG", quality=95)


class XrdCompareWindow:
    def __init__(self, parent, store) -> None:
        self.store = store
        self.series: list[dict] = []
        self.window = Toplevel(parent)
        self.window.title("对比 - XRD")
        self.window.geometry("980x700")
        self.window.minsize(760, 520)
        top = Frame(self.window, padx=10, pady=8)
        top.pack(fill="x")
        Label(top, text="对比性质").pack(side=LEFT)
        self.kind = StringVar(value="XRD")
        ttk.Combobox(top, textvariable=self.kind, values=["XRD"], width=10, state="readonly").pack(side=LEFT, padx=(6, 14))
        Button(top, text="生成对比图", command=self.generate).pack(side=LEFT)
        Button(top, text="保存对比图", command=self.save).pack(side=LEFT, padx=(8, 0))

        body = Frame(self.window, padx=10, pady=8)
        body.pack(fill=BOTH, expand=True)
        chooser = Frame(body)
        chooser.pack(side=LEFT, fill="y", padx=(0, 10))

        left = Frame(chooser)
        left.pack(side=LEFT, fill="y")
        Label(left, text="可用样品").pack(anchor="w")
        list_frame = Frame(left)
        list_frame.pack(fill=BOTH, expand=True)
        self.sample_list = Listbox(list_frame, width=28, exportselection=False)
        self.sample_list.pack(side=LEFT, fill=BOTH, expand=True)
        self.sample_list.bind("<Button-1>", self.start_range_select)
        self.sample_list.bind("<B1-Motion>", self.update_range_select)
        self.sample_list.bind("<ButtonRelease-1>", self.finish_range_select)
        scroll = Scrollbar(list_frame, command=self.sample_list.yview)
        scroll.pack(side=RIGHT, fill="y")
        self.sample_list.configure(yscrollcommand=scroll.set)

        middle = Frame(chooser, padx=8)
        middle.pack(side=LEFT, fill="y")
        Label(middle, text="").pack(pady=(22, 0))
        Button(middle, text="加入 →", command=self.add_selected).pack(fill="x", pady=(0, 8))
        Button(middle, text="← 移除", command=self.remove_selected).pack(fill="x", pady=(0, 8))
        Button(middle, text="清空", command=self.clear_selected).pack(fill="x")

        right = Frame(chooser)
        right.pack(side=LEFT, fill="y")
        Label(right, text="已选样品").pack(anchor="w")
        selected_frame = Frame(right)
        selected_frame.pack(fill=BOTH, expand=True)
        self.selected_list = Listbox(selected_frame, width=28, exportselection=False)
        self.selected_list.pack(side=LEFT, fill=BOTH, expand=True)
        selected_scroll = Scrollbar(selected_frame, command=self.selected_list.yview)
        selected_scroll.pack(side=RIGHT, fill="y")
        self.selected_list.configure(yscrollcommand=selected_scroll.set)

        self.items: list[tuple[str, int, Path, str]] = []
        self.selected_items: list[tuple[str, int, Path, str]] = []
        self.range_start_index: int | None = None
        self.load_items()

        self.canvas = Canvas(body, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.pack(side=LEFT, fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.canvas.bind("<Double-Button-1>", lambda _event: self.open_viewer())

    def load_items(self) -> None:
        self.sample_list.delete(0, END)
        self.items = []
        for material in self.store.material_names():
            for sample in self.store.load_samples(material):
                path = self.store.sample_dir(material, sample.number) / XRD_DATA_FILE
                if path.exists():
                    label = f"{material} / {sample.label}"
                    self.items.append((material, sample.number, path, label))
                    self.sample_list.insert(END, label)

    def add_selected(self) -> None:
        selection = self.sample_list.curselection()
        if not selection:
            messagebox.showinfo("请选择样品", "请先在左侧选择一个样品。")
            return
        for index in selection:
            item = self.items[index]
            if any(existing[2] == item[2] for existing in self.selected_items):
                continue
            self.selected_items.append(item)
            self.selected_list.insert(END, item[3])

    def start_range_select(self, event) -> None:
        self.range_start_index = self.sample_list.nearest(event.y)
        self.sample_list.selection_clear(0, END)
        self.sample_list.selection_set(self.range_start_index)

    def update_range_select(self, event) -> None:
        if self.range_start_index is None:
            return
        current = self.sample_list.nearest(event.y)
        start, end = sorted((self.range_start_index, current))
        self.sample_list.selection_clear(0, END)
        self.sample_list.selection_set(start, end)

    def finish_range_select(self, _event) -> None:
        self.range_start_index = None

    def remove_selected(self) -> None:
        selection = self.selected_list.curselection()
        if not selection:
            messagebox.showinfo("请选择样品", "请先在右侧选择要移除的样品。")
            return
        index = selection[0]
        del self.selected_items[index]
        self.selected_list.delete(index)

    def clear_selected(self) -> None:
        self.selected_items = []
        self.selected_list.delete(0, END)

    def selected_paths(self) -> list[tuple[Path, str]]:
        return [(path, label) for _material, _number, path, label in self.selected_items]

    def generate(self) -> None:
        selected = self.selected_paths()
        if len(selected) < 2:
            messagebox.showinfo("请选择样品", "请至少选择两个已经保存 XRD 数据的样品。")
            return
        self.series = []
        for path, label in selected:
            rows = load_xrd_csv(path)
            points = sorted([(row[2], row[1]) for row in rows if 1 <= row[2] <= 8], key=lambda item: item[0], reverse=True)
            points = downsample_points(points, MAX_PLOT_POINTS)
            if not points:
                continue
            intensities = [point[1] for point in points]
            min_i, max_i = min(intensities), max(intensities)
            span = max(max_i - min_i, 1e-12)
            values = [(value - min_i) / span for value in intensities]
            self.series.append({"label": label, "points": points, "values": values})
        if len(self.series) < 2:
            messagebox.showwarning("无法对比", "选中的样品中可用的 XRD 数据不足。")
            return
        self.redraw()

    def redraw(self) -> None:
        if self.series:
            draw_xrd_comparison(self.canvas, self.series)

    def open_viewer(self) -> None:
        if not self.series:
            messagebox.showinfo("没有图", "请先生成对比图。")
            return
        XrdComparisonViewer(self.window, self.series)

    def save(self) -> None:
        if not self.series:
            self.generate()
            if not self.series:
                return
        path = filedialog.asksaveasfilename(
            parent=self.window,
            title="保存 XRD 对比图",
            defaultextension=".jpg",
            filetypes=[("JPG 图片", "*.jpg"), ("JPEG 图片", "*.jpeg")],
        )
        if not path:
            return
        try:
            save_xrd_comparison_jpg(Path(path), self.series)
        except ModuleNotFoundError:
            messagebox.showwarning("保存失败", "保存 JPG 需要安装 Pillow。请运行：python -m pip install pillow")
            return
        messagebox.showinfo("保存完成", f"对比图已保存到：\n{path}")


class XrdComparisonViewer:
    def __init__(self, parent, series: list[dict]) -> None:
        self.series = series
        self.x_limits = (8, 1)
        _prepared, self.y_limits = prepare_comparison_series(series)
        self.crosshair: tuple[float, float] | None = None
        self.window = Toplevel(parent)
        self.window.title("XRD 对比图查看")
        self.window.geometry("980x680")
        self.window.minsize(640, 420)
        toolbar = Frame(self.window, padx=8, pady=6)
        toolbar.pack(fill="x")
        Button(toolbar, text="重置视图", command=self.reset_view).pack(side=LEFT)
        Label(toolbar, text="滚轮缩放，单击图中位置读坐标").pack(side=LEFT, padx=(12, 0))
        self.coord_text = StringVar(value="x: --    y: --")
        Label(toolbar, textvariable=self.coord_text).pack(side=RIGHT)
        self.canvas = Canvas(self.window, bg="white", highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.canvas.bind("<Motion>", self.on_motion_preview)
        self.canvas.bind("<Button-1>", self.on_click_read)
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        self.canvas.bind("<Button-4>", lambda event: self.zoom_at_event(event, 0.8))
        self.canvas.bind("<Button-5>", lambda event: self.zoom_at_event(event, 1.25))
        self.redraw()

    def reset_view(self) -> None:
        self.x_limits = (8, 1)
        _prepared, self.y_limits = prepare_comparison_series(self.series)
        self.crosshair = None
        self.coord_text.set("x: --    y: --")
        self.redraw()

    def redraw(self) -> None:
        draw_xrd_comparison(self.canvas, self.series, self.x_limits, self.y_limits, self.crosshair)

    def data_from_event(self, event) -> tuple[float, float]:
        width = max(self.canvas.winfo_width(), 700)
        height = max(self.canvas.winfo_height(), 520)
        margin_left, margin_right, margin_top, margin_bottom = 86, 170, 34, 58
        x_min, x_max = self.x_limits
        y_min, y_max = self.y_limits
        plot_width = max(width - margin_left - margin_right, 1)
        plot_height = max(height - margin_top - margin_bottom, 1)
        x_ratio = min(max((event.x - margin_left) / plot_width, 0), 1)
        y_ratio = min(max((height - margin_bottom - event.y) / plot_height, 0), 1)
        return x_min + x_ratio * (x_max - x_min), y_min + y_ratio * (y_max - y_min)

    def on_motion_preview(self, event) -> None:
        x_value, y_value = self.data_from_event(event)
        self.coord_text.set(f"当前 x: {x_value:.6g}    y: {y_value:.6g}    单击固定")

    def on_click_read(self, event) -> None:
        x_value, y_value = self.data_from_event(event)
        self.crosshair = (x_value, y_value)
        self.coord_text.set(f"已读 x: {x_value:.6g}    y: {y_value:.6g}")
        self.redraw()

    def on_mousewheel(self, event) -> None:
        self.zoom_at_event(event, 0.8 if event.delta > 0 else 1.25)

    def zoom_at_event(self, event, factor: float) -> None:
        center_x, center_y = self.data_from_event(event)
        self.x_limits = self.zoom_range(self.x_limits, center_x, factor)
        self.y_limits = self.zoom_range(self.y_limits, center_y, factor)
        self.crosshair = (center_x, center_y)
        self.coord_text.set(f"x: {center_x:.6g}    y: {center_y:.6g}")
        self.redraw()

    def zoom_range(self, limits: tuple[float, float], center: float, factor: float) -> tuple[float, float]:
        start, end = limits
        new_start = center + (start - center) * factor
        new_end = center + (end - center) * factor
        return limits if abs(new_end - new_start) < 1e-12 else (new_start, new_end)


class ManualPeakWindow:
    """Interactive peak selection and local Gaussian correction for processed XRD data."""

    def __init__(
        self,
        parent,
        theta_rows: list[tuple[float, float, float]],
        d_rows: list[tuple[float, float, float]],
        peak_records: list[dict],
        on_apply,
    ) -> None:
        self.theta_rows = sorted_finite_rows(theta_rows, "theta")
        self.d_rows = sorted_finite_rows(d_rows, "d")
        self.original_theta_rows = self.theta_rows[:]
        self.original_d_rows = self.d_rows[:]
        self.peak_records = self.clean_peak_records(peak_records)
        self.on_apply = on_apply
        self.selected_peak: tuple[float, float, float] | None = None

        self.window = Toplevel(parent)
        self.window.title("手动寻峰与局部修正")
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        window_width = min(1040, max(760, screen_width - 80))
        window_height = min(700, max(520, screen_height - 100))
        window_x = max((screen_width - window_width) // 2, 0)
        window_y = max((screen_height - window_height) // 2, 0)
        self.window.geometry(f"{window_width}x{window_height}+{window_x}+{window_y}")
        self.window.minsize(760, 520)

        self.axis_text = StringVar(value="2theta")
        self.search_width = StringVar(value="0.50")
        self.fit_width = StringVar(value="0.60")
        self.position_text = StringVar(value="--")
        self.intensity_text = StringVar(value="")
        self.selected_text = StringVar(value="在曲线上单击以选择峰位；程序会自动吸附到附近峰顶。")
        self.width_unit_text = StringVar(value="°")

        toolbar = Frame(self.window, padx=10, pady=8)
        toolbar.pack(fill="x")
        Label(toolbar, text="坐标").pack(side=LEFT)
        axis_box = ttk.Combobox(toolbar, textvariable=self.axis_text, values=["2theta", "d"], width=9, state="readonly")
        axis_box.pack(side=LEFT, padx=(5, 12))
        axis_box.bind("<<ComboboxSelected>>", self.change_axis)
        Label(toolbar, text="峰位吸附半宽").pack(side=LEFT)
        Entry(toolbar, textvariable=self.search_width, width=7).pack(side=LEFT, padx=(5, 2))
        Label(toolbar, textvariable=self.width_unit_text).pack(side=LEFT)
        Label(toolbar, text="单击曲线选择峰顶").pack(side=LEFT, padx=(14, 0))

        body = Frame(self.window, padx=10)
        body.pack(fill=BOTH, expand=True, pady=(0, 8))
        plot_frame = Frame(body)
        plot_frame.pack(side=LEFT, fill=BOTH, expand=True)
        self.canvas = Canvas(plot_frame, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.canvas.pack(fill=BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _event: self.redraw())
        self.canvas.bind("<Button-1>", self.select_peak_at_event)

        peak_frame = Frame(body, width=265)
        peak_frame.pack(side=RIGHT, fill=Y, padx=(10, 0))
        Label(peak_frame, text="已确认峰").pack(anchor="w")
        list_frame = Frame(peak_frame)
        list_frame.pack(fill=BOTH, expand=True, pady=(4, 0))
        self.peak_list = Listbox(list_frame, width=31, exportselection=False)
        self.peak_list.pack(side=LEFT, fill=BOTH, expand=True)
        peak_scroll = Scrollbar(list_frame, command=self.peak_list.yview)
        peak_scroll.pack(side=RIGHT, fill="y")
        self.peak_list.configure(yscrollcommand=peak_scroll.set)
        self.peak_list.bind("<<ListboxSelect>>", self.select_record)
        Button(peak_frame, text="记录当前峰", command=self.record_current_peak).pack(fill="x", pady=(8, 0))
        Button(peak_frame, text="删除所选标记", command=self.delete_selected_record).pack(fill="x", pady=(6, 0))
        Button(peak_frame, text="清空峰标记", command=self.clear_records).pack(fill="x", pady=(6, 0))

        correction = LabelFrame(self.window, text="局部高斯峰修正", padx=10, pady=8)
        correction.pack(fill="x", padx=10, pady=(0, 8))
        Label(correction, textvariable=self.selected_text, anchor="w").grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, 6))
        Label(correction, text="峰位").grid(row=1, column=0, sticky="w")
        Entry(correction, textvariable=self.position_text, state="readonly", width=12).grid(row=1, column=1, sticky="w", padx=(5, 14))
        Label(correction, text="目标峰高 (0-100)").grid(row=1, column=2, sticky="w")
        Entry(correction, textvariable=self.intensity_text, width=10).grid(row=1, column=3, sticky="w", padx=(5, 14))
        Label(correction, text="影响半宽").grid(row=1, column=4, sticky="w")
        Entry(correction, textvariable=self.fit_width, width=8).grid(row=1, column=5, sticky="w", padx=(5, 2))
        Label(correction, textvariable=self.width_unit_text).grid(row=1, column=6, sticky="w")
        Button(correction, text="高斯平滑修正", command=self.apply_gaussian_correction).grid(row=1, column=7, sticky="e", padx=(14, 0))
        correction.columnconfigure(0, weight=1)

        actions = Frame(self.window, padx=10)
        actions.pack(fill="x", pady=(0, 10))
        Button(actions, text="撤销本次数据修正", command=self.restore_original_rows).pack(side=LEFT)
        Button(actions, text="保存并写回处理后数据", command=self.apply_changes).pack(side=RIGHT)
        Button(actions, text="关闭", command=self.window.destroy).pack(side=RIGHT, padx=(0, 8))
        self.refresh_peak_list()
        self.redraw()
        self.window.after_idle(self.redraw)

    def clean_peak_records(self, records: list[dict]) -> list[dict]:
        clean: list[dict] = []
        for record in records:
            if not isinstance(record, dict) or record.get("axis") not in {"theta", "d"}:
                continue
            try:
                clean.append(
                    {
                        "axis": record["axis"],
                        "position": float(record["position"]),
                        "two_theta": float(record["two_theta"]),
                        "d": float(record["d"]),
                        "intensity": min(max(float(record["intensity"]), 0.0), 100.0),
                    }
                )
            except (KeyError, TypeError, ValueError):
                continue
        return clean

    def axis_kind(self) -> str:
        return "d" if self.axis_text.get() == "d" else "theta"

    def current_rows(self) -> list[tuple[float, float, float]]:
        return self.d_rows if self.axis_kind() == "d" else self.theta_rows

    def set_current_rows(self, rows: list[tuple[float, float, float]]) -> None:
        if self.axis_kind() == "d":
            self.d_rows = sorted_finite_rows(rows, "d")
        else:
            self.theta_rows = sorted_finite_rows(rows, "theta")

    def current_x_limits(self) -> tuple[float, float]:
        return d_plot_limits(self.current_rows()) if self.axis_kind() == "d" else (10, 100)

    def parse_positive(self, value: StringVar, label: str) -> float:
        try:
            number = float(value.get().strip())
        except ValueError as exc:
            raise ValueError(f"{label}必须是数字。") from exc
        if number <= 0:
            raise ValueError(f"{label}必须大于 0。")
        return number

    def change_axis(self, _event=None) -> None:
        self.width_unit_text.set("Å" if self.axis_kind() == "d" else "°")
        self.selected_peak = None
        self.position_text.set("--")
        self.intensity_text.set("")
        self.selected_text.set("在曲线上单击以选择峰位；程序会自动吸附到附近峰顶。")
        self.redraw()

    def data_x_from_event(self, event) -> float:
        width = max(self.canvas.winfo_width(), 430)
        margin_left, margin_right, _margin_top, _margin_bottom = CANVAS_MARGIN
        x_min, x_max = self.current_x_limits()
        ratio = min(max((event.x - margin_left) / max(width - margin_left - margin_right, 1), 0), 1)
        return x_min + ratio * (x_max - x_min)

    def select_peak_at_event(self, event) -> None:
        try:
            half_width = self.parse_positive(self.search_width, "峰位吸附半宽")
            peak = find_manual_peak(self.current_rows(), self.axis_kind(), self.data_x_from_event(event), half_width)
        except ValueError as exc:
            messagebox.showwarning("无法寻峰", str(exc), parent=self.window)
            return
        if peak is None:
            messagebox.showwarning("没有数据", "当前坐标没有可用于寻峰的处理后数据。", parent=self.window)
            return
        self.set_selected_peak(peak)

    def set_selected_peak(self, peak: tuple[float, float, float]) -> None:
        self.selected_peak = peak
        axis_value = manual_peak_axis_value(peak, self.axis_kind())
        self.position_text.set(f"{axis_value:.7g}")
        self.intensity_text.set(f"{peak[1]:.7g}")
        self.selected_text.set(f"已选峰：2theta = {peak[0]:.7g}°，d = {peak[2]:.7g} Å，强度 = {peak[1]:.7g}")
        self.redraw()

    def peak_record_from_current(self) -> dict | None:
        if self.selected_peak is None:
            return None
        peak = self.selected_peak
        return {
            "axis": self.axis_kind(),
            "position": manual_peak_axis_value(peak, self.axis_kind()),
            "two_theta": peak[0],
            "d": peak[2],
            "intensity": peak[1],
        }

    def upsert_record(self, record: dict) -> None:
        tolerance = max(1e-5, self.parse_positive(self.search_width, "峰位吸附半宽") * 0.05)
        for index, existing in enumerate(self.peak_records):
            if existing["axis"] == record["axis"] and abs(existing["position"] - record["position"]) <= tolerance:
                self.peak_records[index] = record
                return
        self.peak_records.append(record)

    def record_current_peak(self) -> None:
        record = self.peak_record_from_current()
        if record is None:
            messagebox.showinfo("请先选峰", "请先在曲线上单击一个峰。", parent=self.window)
            return
        try:
            self.upsert_record(record)
        except ValueError as exc:
            messagebox.showwarning("无法记录峰", str(exc), parent=self.window)
            return
        self.refresh_peak_list()
        self.redraw()

    def refresh_peak_list(self) -> None:
        self.peak_list.delete(0, END)
        for index, record in enumerate(self.peak_records, start=1):
            unit = "Å" if record["axis"] == "d" else "°"
            axis_name = "d" if record["axis"] == "d" else "2theta"
            self.peak_list.insert(END, f"{index}. {axis_name}={record['position']:.6g} {unit}, I={record['intensity']:.5g}")

    def select_record(self, _event=None) -> None:
        selection = self.peak_list.curselection()
        if not selection:
            return
        record = self.peak_records[selection[0]]
        self.axis_text.set("d" if record["axis"] == "d" else "2theta")
        self.change_axis()
        try:
            peak = find_manual_peak(self.current_rows(), self.axis_kind(), record["position"], self.parse_positive(self.search_width, "峰位吸附半宽"))
        except ValueError:
            peak = None
        if peak is not None:
            self.set_selected_peak(peak)

    def delete_selected_record(self) -> None:
        selection = self.peak_list.curselection()
        if not selection:
            messagebox.showinfo("请选择峰", "请在右侧选择一个要删除的峰标记。", parent=self.window)
            return
        del self.peak_records[selection[0]]
        self.refresh_peak_list()
        self.redraw()

    def clear_records(self) -> None:
        if not self.peak_records:
            return
        if not messagebox.askyesno("清空峰标记", "要清空当前样品记录的所有手动峰标记吗？\n这不会恢复已经修正的数据。", parent=self.window):
            return
        self.peak_records = []
        self.refresh_peak_list()
        self.redraw()

    def apply_gaussian_correction(self) -> None:
        if self.selected_peak is None:
            messagebox.showinfo("请先选峰", "请先在曲线上单击一个峰。", parent=self.window)
            return
        try:
            target_intensity = float(self.intensity_text.get().strip())
            half_width = self.parse_positive(self.fit_width, "影响半宽")
            position = manual_peak_axis_value(self.selected_peak, self.axis_kind())
            corrected, peak = gaussian_peak_correction(self.current_rows(), self.axis_kind(), position, target_intensity, half_width)
        except ValueError as exc:
            messagebox.showwarning("无法修正峰", str(exc), parent=self.window)
            return
        self.set_current_rows(corrected)
        if peak is not None:
            self.set_selected_peak(peak)
            record = self.peak_record_from_current()
            if record is not None:
                self.upsert_record(record)
        self.refresh_peak_list()
        self.redraw()

    def restore_original_rows(self) -> None:
        self.theta_rows = self.original_theta_rows[:]
        self.d_rows = self.original_d_rows[:]
        self.selected_peak = None
        self.position_text.set("--")
        self.intensity_text.set("")
        self.selected_text.set("已恢复本次打开工具前的处理后数据；峰标记仍会保留。")
        self.redraw()

    def redraw(self) -> None:
        rows = self.current_rows()
        if not rows:
            self.canvas.delete("all")
            return
        axis_kind = self.axis_kind()
        points = processed_curve_points(rows, axis_kind, MAX_PROCESSED_CANVAS_POINTS)
        config = processed_plot_config(points, axis_kind, MAX_PROCESSED_CANVAS_POINTS, self.current_x_limits())
        draw_scatter_plot(self.canvas, **config)
        width = max(self.canvas.winfo_width(), 430)
        height = max(self.canvas.winfo_height(), 260)
        margin_left, margin_right, margin_top, margin_bottom = CANVAS_MARGIN
        x_min, x_max = self.current_x_limits()

        def screen_x(value: float) -> float:
            return margin_left + (value - x_min) / (x_max - x_min) * (width - margin_left - margin_right)

        for index, record in enumerate(self.peak_records, start=1):
            if record["axis"] != axis_kind:
                continue
            value = record["position"]
            if min(x_min, x_max) <= value <= max(x_min, x_max):
                x_pos = screen_x(value)
                self.canvas.create_line(x_pos, margin_top, x_pos, height - margin_bottom, fill="#b13333", dash=(4, 3))
                self.canvas.create_text(x_pos, margin_top + 11, text=str(index), fill="#b13333", font=("Arial", 9, "bold"))
        if self.selected_peak is not None:
            x_pos = screen_x(manual_peak_axis_value(self.selected_peak, axis_kind))
            self.canvas.create_line(x_pos, margin_top, x_pos, height - margin_bottom, fill="#7a4fb5", width=2)

    def apply_changes(self) -> None:
        self.on_apply(self.theta_rows, self.d_rows, self.peak_records)
        self.window.destroy()
