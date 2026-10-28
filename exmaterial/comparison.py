"""One sample comparison entry point, using saved sample-bound measurements."""
import csv
import json
import math
from pathlib import Path
from tkinter import BOTH, Button, Canvas, Label, Toplevel, filedialog, messagebox

try:
    from . import thermal_tools, xps_tools, xrd_tools
    from .rendering import DeferredRedraw, device_preview, settings_for
except ImportError:
    import thermal_tools
    import xps_tools
    import xrd_tools
    from rendering import DeferredRedraw, device_preview, settings_for


COLORS = ["#147d78", "#c34d35", "#6653a0", "#b07913", "#287abb", "#a44075"]


def load_xps_comparison(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    points, _ = xps_tools.parse_spectrum(data["raw_text"], int(data.get("energy_column", 1)),
                                       int(data.get("intensity_column", 2)))
    params = data.get("parameters", {})
    result = xps_tools.process_spectrum(
        points, shift=float(params.get("shift") or 0),
        lower=float(params["lower"]) if params.get("lower") else None,
        upper=float(params["upper"]) if params.get("upper") else None,
        window=int(params.get("window", 1)),
        background="linear" if data.get("background") == "线性背景" else "none",
        normalize=bool(data.get("normalize", False)),
    )
    return [(row[0], row[3]) for row in result["rows"]], bool(data.get("normalize", False))


def chart_geometry(series, kind):
    points = [p for item in series for p in item["points"]]
    low, high = min(x for x, _ in points), max(x for x, _ in points)
    if low == high:
        low, high = low - 1, high + 1
    bottom, top = min(y for _, y in points), max(y for _, y in points)
    pad = (top - bottom) * .08 or max(abs(top) * .08, 1)
    xlimits = (high, low) if kind == "XPS" else (low, high)
    return xlimits, (bottom - pad, top + pad)


def paint_chart(series, kind, width, height, line, text, dot):
    """Shared vector layout for Tk preview and full-resolution Pillow export."""
    (x0, x1), (y0, y1) = chart_geometry(series, kind)
    left, right, top, bottom = 80, width - 24, 65 + 19 * len(series), height - 55
    sx = lambda x: left + (x - x0) / (x1 - x0) * (right - left)
    sy = lambda y: bottom - (y - y0) / (y1 - y0) * (bottom - top)
    for i, item in enumerate(series):
        text(left, 18 + i * 19, item["label"], COLORS[i % len(COLORS)])
    xlabel = "Binding energy (eV)" if kind == "XPS" else "Temperature (°C)"
    ylabel = ("Normalized intensity" if series[0].get("normalized") else "Intensity (input units)") if kind == "XPS" else "Thermal conductivity (W/m/K)"
    text(left, top - 20, ylabel, "#222222")
    text(width / 2 - 70, height - 20, xlabel, "#222222")
    line([(left, top), (left, bottom), (right, bottom)], "#222222")
    for i in range(6):
        x, y = x0 + (x1 - x0) * i / 5, y0 + (y1 - y0) * i / 5
        text(sx(x) - 12, bottom + 12, f"{x:.4g}", "#222222")
        text(4, sy(y), f"{y:.4g}", "#222222")
    for i, item in enumerate(series):
        color = COLORS[i % len(COLORS)]
        coords = [(sx(x), sy(y)) for x, y in item["points"]]
        if len(coords) > 1:
            line(coords, color)
        if kind != "XPS" or len(coords) == 1:
            for x, y in coords:
                dot(x, y, color)


class SampleCompareWindow(xrd_tools.XrdCompareWindow):
    kinds = ["XRD", "XPS", "热导率"]

    def __init__(self, parent, store):
        super().__init__(parent, store)
        self.window.title("样品比对 · XRD / XPS / 热导率")
        self.window.geometry("1200x800")
        Label(self.window, text="使用已保存数据；编辑后请先保存。XPS 各样品应使用相同能区、强度单位和处理方式。").pack()
        Button(self.window, text="刷新样品列表", command=self.kind_changed).pack(side="left")
        Button(self.window, text="导出对比 CSV", command=self.export_csv).pack(side="left")

    def load_items(self):
        if self.kind.get() == "XRD":
            return super().load_items()
        self.sample_list.delete(0, "end")
        self.items = []
        for material in self.store.material_names():
            for sample in self.store.load_samples(material):
                folder = self.store.sample_dir(material, sample.number)
                path = folder / "xps_workspace.json" if self.kind.get() == "XPS" else folder
                available = path.is_file() if self.kind.get() == "XPS" else bool(thermal_tools.thermal_points(sample.thermal_rows))
                if available:
                    label = f"{material} / {sample.label}"
                    self.items.append((material, sample.number, path, label))
                    self.sample_list.insert("end", label)

    def generate(self):
        self.series = []
        self.canvas.delete("all")
        if self.kind.get() == "XRD":
            try:
                super().generate()
                if len(self.series) < 2:
                    self.series = []
                return
            except (OSError, ValueError) as exc:
                self.series = []
                messagebox.showerror("读取失败", str(exc), parent=self.window)
                return
        if len(self.selected_items) < 2:
            messagebox.showinfo("请选择样品", "请至少加入两个样品。", parent=self.window)
            return
        series = []
        try:
            for material, number, path, label in self.selected_items:
                normalized = False
                if self.kind.get() == "XPS":
                    points, normalized = load_xps_comparison(path)
                else:
                    sample = next(s for s in self.store.load_samples(material, strict=True) if s.number == number)
                    points = thermal_tools.thermal_points(sample.thermal_rows)
                if not points or any(not math.isfinite(v) for p in points for v in p):
                    raise ValueError(f"{label} 没有有效数据")
                series.append(dict(label=label, points=points, normalized=normalized))
            if len({s["normalized"] for s in series}) > 1:
                raise ValueError("XPS 归一化设置不一致，请在各样品工作区统一后保存。")
        except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
            messagebox.showerror("无法比对", str(exc), parent=self.window)
            return
        self.series = series
        self.redraw()

    def draw_on(self, canvas, series, kind):
        canvas.delete("all")
        reduced = [{**s, "points": device_preview(canvas, s["points"], settings_for(canvas).preview_limit)} for s in series]
        paint_chart(reduced, kind, max(430, canvas.winfo_width()), max(300 + 19 * len(series), canvas.winfo_height()),
                    lambda points, color: canvas.create_line(*[v for p in points for v in p], fill=color, width=2),
                    lambda x, y, value, color: canvas.create_text(x, y, text=value, fill=color, anchor="w"),
                    lambda x, y, color: canvas.create_oval(x-3, y-3, x+3, y+3, fill=color, outline=color))

    def redraw(self):
        if self.kind.get() == "XRD":
            return super().redraw()
        if self.series:
            self.draw_on(self.canvas, self.series, self.kind.get())

    def open_viewer(self):
        if self.kind.get() == "XRD":
            return super().open_viewer()
        if not self.series:
            return
        window = Toplevel(self.window)
        window.title(f"{self.kind.get()} 样品比对")
        window.geometry("1100x800")
        canvas = Canvas(window, bg="white")
        canvas.pack(fill=BOTH, expand=True)
        series, kind = self.series, self.kind.get()
        scheduler = DeferredRedraw(canvas, lambda: self.draw_on(canvas, series, kind))
        canvas.bind("<Configure>", scheduler.request)

    def save(self):
        if self.kind.get() == "XRD":
            return super().save()
        if not self.series:
            self.generate()
        if not self.series:
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".jpg", filetypes=[("JPEG", "*.jpg")])
        if not path:
            return
        try:
            from PIL import Image, ImageDraw, ImageFont
            image = Image.new("RGB", (1400, max(900, 400 + 19 * len(self.series))), "white")
            draw = ImageDraw.Draw(image)
            try:
                font = ImageFont.truetype("msyh.ttc", 14)
            except OSError:
                font = ImageFont.load_default()
            paint_chart(self.series, self.kind.get(), *image.size,
                        lambda points, color: draw.line(points, fill=color, width=2),
                        lambda x, y, value, color: draw.text((x, y), value, fill=color, font=font),
                        lambda x, y, color: draw.ellipse((x-3, y-3, x+3, y+3), fill=color))
            image.save(path, quality=95)
        except (OSError, ValueError) as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.window)

    def export_csv(self):
        if not self.series:
            self.generate()
        if not self.series:
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path:
            return
        kind = self.kind.get()
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(["sample", "d_A" if kind == "XRD" else "binding_energy_eV" if kind == "XPS" else "temperature_C",
                                 "thermal_conductivity_W_m_K" if kind == "热导率" else "intensity"])
                for item in self.series:
                    writer.writerows((item["label"], x, y) for x, y in item["points"])
        except OSError as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.window)
