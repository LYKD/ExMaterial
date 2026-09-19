from __future__ import annotations

from pathlib import Path
from tkinter import BOTH, LEFT, Button, Canvas, Frame, Label, StringVar, Tk, Toplevel

try:
    from PIL import Image, ImageDraw
except ModuleNotFoundError:
    Image = None
    ImageDraw = None


CANVAS_MARGIN = (92, 24, 34, 50)
IMAGE_MARGIN = (130, 45, 72, 105)


def x_ticks(x_limits: tuple[float, float], step: float) -> list[float]:
    start, end = x_limits
    if step <= 0:
        return [start, end]
    direction = 1 if end >= start else -1
    ticks = []
    value = start
    while (value <= end + 1e-9) if direction > 0 else (value >= end - 1e-9):
        ticks.append(value)
        value += direction * step
    if ticks[-1] != end:
        ticks.append(end)
    return ticks


def plot_bounds(
    points: list[tuple[float, float]],
    x_limits: tuple[float, float],
    y_limits: tuple[float, float] | None = None,
) -> tuple[float, float, float, float]:
    x_min, x_max = x_limits
    if y_limits is not None:
        y_min, y_max = y_limits
        return x_min, x_max, y_min, y_max
    visible_ys = [point[1] for point in points if min(x_min, x_max) <= point[0] <= max(x_min, x_max)]
    ys = visible_ys or [point[1] for point in points] or [0, 1]
    y_min, y_max = min(ys), max(ys)
    if y_min == y_max:
        y_min -= 1
        y_max += 1
    y_pad = (y_max - y_min) * 0.08
    return x_min, x_max, y_min - y_pad, y_max + y_pad


def clamp_value(value: float, limits: tuple[float, float]) -> float:
    lower, upper = min(limits), max(limits)
    return min(max(value, lower), upper)


def clamp_points_to_y_limits(points: list[tuple[float, float]], y_limits: tuple[float, float] | None) -> list[tuple[float, float]]:
    if y_limits is None:
        return points
    return [(x_value, clamp_value(y_value, y_limits)) for x_value, y_value in points]


def _screen_functions(
    width: int,
    height: int,
    margins: tuple[int, int, int, int],
    bounds: tuple[float, float, float, float],
):
    margin_left, margin_right, margin_top, margin_bottom = margins
    x_min, x_max, y_min, y_max = bounds

    def sx(x_value: float) -> float:
        return margin_left + (x_value - x_min) / (x_max - x_min) * (width - margin_left - margin_right)

    def sy(y_value: float) -> float:
        return height - margin_bottom - (y_value - y_min) / (y_max - y_min) * (height - margin_top - margin_bottom)

    return sx, sy


def smooth_screen_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return points


def draw_scatter_plot(
    canvas: Canvas,
    points: list[tuple[float, float]],
    title: str,
    xlabel: str,
    ylabel: str,
    x_limits: tuple[float, float],
    x_tick_step: float,
    y_limits: tuple[float, float] | None = None,
    crosshair: tuple[float, float] | None = None,
    connect_points: bool = False,
    smooth_line: bool = False,
    point_color: str = "#1f77b4",
    point_radius: float = 1.4,
) -> None:
    canvas.delete("all")
    points = clamp_points_to_y_limits(points, y_limits)
    width = max(canvas.winfo_width(), 430)
    height = max(canvas.winfo_height(), 260)
    margin_left, margin_right, margin_top, margin_bottom = CANVAS_MARGIN
    bounds = plot_bounds(points, x_limits, y_limits)
    x_min, x_max, y_min, y_max = bounds
    sx, sy = _screen_functions(width, height, CANVAS_MARGIN, bounds)

    canvas.create_text(width / 2, 15, text=title, font=("Arial", 10, "bold"))
    canvas.create_text(margin_left, margin_top - 12, text=ylabel, anchor="w", font=("Arial", 9))
    canvas.create_line(margin_left, margin_top, margin_left, height - margin_bottom, fill="#222222")
    canvas.create_line(margin_left, height - margin_bottom, width - margin_right, height - margin_bottom, fill="#222222")
    for x_value in x_ticks(x_limits, x_tick_step):
        x_pos = sx(x_value)
        canvas.create_line(x_pos, height - margin_bottom, x_pos, height - margin_bottom + 4, fill="#222222")
        canvas.create_text(x_pos, height - margin_bottom + 18, text=f"{x_value:.4g}", font=("Arial", 8))
    for index in range(6):
        y_value = y_min + (y_max - y_min) * index / 5
        y_pos = sy(y_value)
        canvas.create_line(margin_left - 4, y_pos, margin_left, y_pos, fill="#222222")
        canvas.create_text(margin_left - 10, y_pos, text=f"{y_value:.3g}", anchor="e", font=("Arial", 8))
    canvas.create_text(width / 2, height - 10, text=xlabel, font=("Arial", 9))
    visible_points = [(sx(x_value), sy(y_value)) for x_value, y_value in points if min(x_min, x_max) <= x_value <= max(x_min, x_max)]
    if connect_points and len(visible_points) >= 2:
        line_points = smooth_screen_points(visible_points) if smooth_line else visible_points
        coords = []
        for x_pos, y_pos in line_points:
            coords.extend([x_pos, y_pos])
        canvas.create_line(*coords, fill="#1f77b4", width=2)
    if point_radius > 0:
        for x_value, y_value in points:
            if min(x_min, x_max) <= x_value <= max(x_min, x_max):
                x_pos = sx(x_value)
                y_pos = sy(y_value)
                canvas.create_oval(x_pos - point_radius, y_pos - point_radius, x_pos + point_radius, y_pos + point_radius, fill=point_color, outline="")
    if crosshair:
        cross_x, cross_y = crosshair
        if min(x_min, x_max) <= cross_x <= max(x_min, x_max) and min(y_min, y_max) <= cross_y <= max(y_min, y_max):
            x_pos = sx(cross_x)
            y_pos = sy(cross_y)
            canvas.create_line(x_pos, margin_top, x_pos, height - margin_bottom, fill="#aa3333", dash=(4, 3))
            canvas.create_line(margin_left, y_pos, width - margin_right, y_pos, fill="#aa3333", dash=(4, 3))
            canvas.create_text(width - margin_right - 6, margin_top + 12, text=f"x={cross_x:.5g}, y={cross_y:.5g}", anchor="e", fill="#aa3333", font=("Arial", 9))


def render_scatter_image(
    points: list[tuple[float, float]],
    title: str,
    xlabel: str,
    ylabel: str,
    x_limits: tuple[float, float],
    x_tick_step: float,
    y_limits: tuple[float, float] | None = None,
    width: int = 1200,
    height: int = 760,
    connect_points: bool = False,
    smooth_line: bool = False,
    point_color: str = "#1f77b4",
    point_radius: float = 2,
):
    if Image is None or ImageDraw is None:
        raise RuntimeError("保存 JPG 需要安装 Pillow。请运行：python -m pip install pillow")
    points = clamp_points_to_y_limits(points, y_limits)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    margin_left, margin_right, margin_top, margin_bottom = IMAGE_MARGIN
    bounds = plot_bounds(points, x_limits, y_limits)
    x_min, x_max, y_min, y_max = bounds
    sx, sy = _screen_functions(width, height, IMAGE_MARGIN, bounds)
    draw.text((width / 2 - 70, 25), title, fill="#000000")
    draw.text((margin_left, margin_top - 28), ylabel, fill="#000000")
    draw.line((margin_left, margin_top, margin_left, height - margin_bottom), fill="#222222", width=2)
    draw.line((margin_left, height - margin_bottom, width - margin_right, height - margin_bottom), fill="#222222", width=2)
    for x_value in x_ticks(x_limits, x_tick_step):
        x_pos = sx(x_value)
        draw.line((x_pos, height - margin_bottom, x_pos, height - margin_bottom + 8), fill="#222222")
        draw.text((x_pos - 18, height - margin_bottom + 18), f"{x_value:.4g}", fill="#000000")
    for index in range(6):
        y_value = y_min + (y_max - y_min) * index / 5
        y_pos = sy(y_value)
        draw.line((margin_left - 8, y_pos, margin_left, y_pos), fill="#222222")
        draw.text((12, y_pos - 8), f"{y_value:.4g}", fill="#000000")
    draw.text((width / 2 - 36, height - 44), xlabel, fill="#000000")
    visible_points = [(sx(x_value), sy(y_value)) for x_value, y_value in points if min(x_min, x_max) <= x_value <= max(x_min, x_max)]
    if connect_points and len(visible_points) >= 2:
        draw.line(smooth_screen_points(visible_points) if smooth_line else visible_points, fill="#1f77b4", width=3)
    if point_radius > 0:
        for x_value, y_value in points:
            if min(x_min, x_max) <= x_value <= max(x_min, x_max):
                x_pos = sx(x_value)
                y_pos = sy(y_value)
                draw.ellipse((x_pos - point_radius, y_pos - point_radius, x_pos + point_radius, y_pos + point_radius), fill=point_color)
    return image


def save_scatter_jpg(
    path: Path,
    points: list[tuple[float, float]],
    title: str,
    xlabel: str,
    ylabel: str,
    x_limits: tuple[float, float],
    x_tick_step: float,
    y_limits: tuple[float, float] | None = None,
    connect_points: bool = False,
    smooth_line: bool = False,
    point_color: str = "#1f77b4",
    point_radius: float = 2,
) -> None:
    image = render_scatter_image(
        points,
        title,
        xlabel,
        ylabel,
        x_limits,
        x_tick_step,
        y_limits=y_limits,
        connect_points=connect_points,
        smooth_line=smooth_line,
        point_color=point_color,
        point_radius=point_radius,
    )
    image.save(path, "JPEG", quality=95)


class PlotViewer:
    def __init__(self, parent: Tk, config: dict) -> None:
        self.config = config
        self.points: list[tuple[float, float]] = config["points"]
        self.x_limits = tuple(config["x_limits"])
        _x_min, _x_max, y_min, y_max = plot_bounds(self.points, self.x_limits, config.get("y_limits"))
        self.y_limits = (y_min, y_max)
        self.crosshair: tuple[float, float] | None = None

        self.window = Toplevel(parent)
        self.window.title(config["title"])
        self.window.geometry("980x680")
        self.window.minsize(640, 420)
        toolbar = Frame(self.window, padx=8, pady=6)
        toolbar.pack(fill="x")
        Button(toolbar, text="重置视图", command=self.reset_view).pack(side=LEFT)
        Label(toolbar, text="滚轮缩放，单击图中位置读坐标").pack(side=LEFT, padx=(12, 0))
        self.coord_text = StringVar(value="x: --    y: --")
        Label(toolbar, textvariable=self.coord_text).pack(side="right")
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
        self.x_limits = tuple(self.config["x_limits"])
        _x_min, _x_max, y_min, y_max = plot_bounds(self.points, self.x_limits, self.config.get("y_limits"))
        self.y_limits = (y_min, y_max)
        self.crosshair = None
        self.coord_text.set("x: --    y: --")
        self.redraw()

    def redraw(self) -> None:
        draw_scatter_plot(
            self.canvas,
            self.points,
            self.config["title"],
            self.config["xlabel"],
            self.config["ylabel"],
            self.x_limits,
            self.config["x_tick_step"],
            self.y_limits,
            self.crosshair,
            self.config.get("connect_points", False),
            self.config.get("smooth_line", False),
            self.config.get("point_color", "#1f77b4"),
            self.config.get("point_radius", 1.4),
        )

    def data_from_event(self, event) -> tuple[float, float]:
        width = max(self.canvas.winfo_width(), 430)
        height = max(self.canvas.winfo_height(), 260)
        margin_left, margin_right, margin_top, margin_bottom = CANVAS_MARGIN
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
