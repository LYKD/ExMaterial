from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    Y,
    Button,
    Canvas,
    Entry,
    Frame,
    Label,
    LabelFrame,
    Listbox,
    Menu,
    Scrollbar,
    StringVar,
    Text,
    Tk,
    Toplevel,
)
from tkinter import messagebox, simpledialog, ttk

try:
    from . import thermal_tools, xrd_tools
    from .plot_viewer import PlotViewer as GenericPlotViewer
    from .plot_viewer import draw_scatter_plot, save_scatter_jpg
except ImportError:  # Supports launching this file directly from its source folder.
    import thermal_tools
    import xrd_tools
    from plot_viewer import PlotViewer as GenericPlotViewer
    from plot_viewer import draw_scatter_plot, save_scatter_jpg


APP_NAME = "ExMaterial"
APP_VERSION = "1.0.0"
APP_TITLE = f"{APP_NAME} {APP_VERSION} · 样品记录"
DATA_FILE = "samples.json"
XRD_DATA_FILE = xrd_tools.XRD_DATA_FILE
PLOT_2THETA_FILE = xrd_tools.PLOT_2THETA_FILE
PLOT_D_FILE = xrd_tools.PLOT_D_FILE
PROCESSED_XRD_DATA_THETA_FILE = xrd_tools.PROCESSED_XRD_DATA_THETA_FILE
PROCESSED_XRD_DATA_D_FILE = xrd_tools.PROCESSED_XRD_DATA_D_FILE
PROCESSED_PLOT_2THETA_FILE = xrd_tools.PROCESSED_PLOT_2THETA_FILE
PROCESSED_PLOT_D_FILE = xrd_tools.PROCESSED_PLOT_D_FILE
MANUAL_XRD_PEAKS_FILE = xrd_tools.MANUAL_XRD_PEAKS_FILE
DEFAULT_WAVELENGTH = xrd_tools.DEFAULT_WAVELENGTH
THERMAL_PLOT_FILE = thermal_tools.THERMAL_PLOT_FILE
INVALID_FOLDER_CHARS = set('\\/:*?"<>|')
MAX_PLOT_POINTS = xrd_tools.MAX_PLOT_POINTS
MAX_PROCESSED_PLOT_POINTS = xrd_tools.MAX_PROCESSED_PLOT_POINTS
MAX_CANVAS_POINTS = xrd_tools.MAX_CANVAS_POINTS
MAX_PROCESSED_CANVAS_POINTS = xrd_tools.MAX_PROCESSED_CANVAS_POINTS
MAX_IMPORTANCE = 3
IMPORTANCE_STAR = "★"


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def information_dir() -> Path:
    return app_dir().parent / "information"


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def clamp_importance(value) -> int:
    try:
        importance = int(str(value).strip() or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, min(MAX_IMPORTANCE, importance))


def default_importance(number: int) -> int:
    return 0


def mousewheel_steps(event) -> int:
    if getattr(event, "num", None) == 4:
        return -1
    if getattr(event, "num", None) == 5:
        return 1
    delta = getattr(event, "delta", 0)
    if delta == 0:
        return 0
    return -1 if delta > 0 else 1


def bind_mousewheel(widget, y_target=None, x_target=None) -> None:
    y_target = y_target or widget
    x_target = x_target or widget

    def scroll_y(event):
        steps = mousewheel_steps(event)
        if steps:
            y_target.yview_scroll(steps, "units")
        return "break"

    def scroll_x(event):
        steps = mousewheel_steps(event)
        if steps:
            x_target.xview_scroll(steps, "units")
        return "break"

    for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        widget.bind(sequence, scroll_y)
    widget.bind("<Shift-MouseWheel>", scroll_x)


def bind_mousewheel_tree(widget, y_target) -> None:
    if not isinstance(widget, (Text, Listbox, Canvas, Scrollbar)):
        bind_mousewheel(widget, y_target)
    for child in widget.winfo_children():
        bind_mousewheel_tree(child, y_target)


def split_obtained_time(data: dict) -> tuple[str, str, str, str]:
    year = data.get("obtained_year", "")
    month = data.get("obtained_month", "")
    day = data.get("obtained_day", "")
    hour = data.get("obtained_hour", "")
    if year or month or day or hour:
        return year, month, day, hour
    text = data.get("obtained_at", "")
    numbers = re.findall(r"\d+", text)
    values = numbers + ["", "", "", ""]
    return values[0], values[1], values[2], values[3]


def thermal_conductivity_text(density_text: str, heat_capacity_text: str, diffusivity_text: str) -> str:
    return thermal_tools.calculate_thermal_conductivity(density_text, heat_capacity_text, diffusivity_text)


def normalize_thermal_rows(data: dict) -> list[dict[str, str]]:
    rows = data.get("thermal_rows", [])
    normalized: list[dict[str, str]] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            item = {
                "temperature_c": str(row.get("temperature_c", "")),
                "density": str(row.get("density", "")),
                "heat_capacity": str(row.get("heat_capacity", "")),
                "thermal_diffusivity": str(row.get("thermal_diffusivity", "")),
                "thermal_conductivity": str(row.get("thermal_conductivity", "")),
            }
            if not item["thermal_conductivity"]:
                item["thermal_conductivity"] = thermal_conductivity_text(
                    item["density"],
                    item["heat_capacity"],
                    item["thermal_diffusivity"],
                )
            if any(value.strip() for value in item.values()):
                normalized.append(item)
    if normalized:
        return normalized
    legacy = {
        "temperature_c": str(data.get("thermal_temperature_c", "")),
        "density": str(data.get("density", "")),
        "heat_capacity": str(data.get("heat_capacity", "")),
        "thermal_diffusivity": str(data.get("thermal_diffusivity", "")),
        "thermal_conductivity": str(data.get("thermal_conductivity", "")),
    }
    if not legacy["thermal_conductivity"]:
        legacy["thermal_conductivity"] = thermal_conductivity_text(
            legacy["density"],
            legacy["heat_capacity"],
            legacy["thermal_diffusivity"],
        )
    return [legacy] if any(value.strip() for value in legacy.values()) else []


@dataclass
class Sample:
    number: int
    importance: int = 0
    obtained_year: str = ""
    obtained_month: str = ""
    obtained_day: str = ""
    obtained_hour: str = ""
    temperature: str = ""
    pressure: str = ""
    annealing_time: str = ""
    density: str = ""
    heat_capacity: str = ""
    thermal_diffusivity: str = ""
    thermal_conductivity: str = ""
    thermal_rows: list[dict[str, str]] = field(default_factory=list)
    xrd_wavelength: str = DEFAULT_WAVELENGTH
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""

    @property
    def label(self) -> str:
        stars = IMPORTANCE_STAR * clamp_importance(self.importance)
        return f"#{self.number} {stars}".rstrip()

    @property
    def list_label(self) -> str:
        parts = [self.label]
        summary = self.compact_summary
        if summary:
            parts.append(summary)
        return "  ".join(parts)

    @property
    def compact_summary(self) -> str:
        parts = []
        if self.temperature:
            parts.append(f"{self.temperature}K")
        if self.pressure:
            parts.append(f"{self.pressure}GPa")
        if self.annealing_time:
            parts.append(f"{self.annealing_time}h")
        return "/".join(parts[:2])

    @staticmethod
    def from_dict(data: dict) -> "Sample":
        obtained_year, obtained_month, obtained_day, obtained_hour = split_obtained_time(data)
        return Sample(
            number=int(data.get("number", 0)),
            importance=clamp_importance(data.get("importance", 0)),
            obtained_year=obtained_year,
            obtained_month=obtained_month,
            obtained_day=obtained_day,
            obtained_hour=obtained_hour,
            temperature=data.get("temperature", ""),
            pressure=data.get("pressure", ""),
            annealing_time=data.get("annealing_time", ""),
            density=data.get("density", ""),
            heat_capacity=data.get("heat_capacity", ""),
            thermal_diffusivity=data.get("thermal_diffusivity", ""),
            thermal_conductivity=data.get("thermal_conductivity", ""),
            thermal_rows=normalize_thermal_rows(data),
            xrd_wavelength=data.get("xrd_wavelength", "") or DEFAULT_WAVELENGTH,
            notes=data.get("notes", ""),
            created_at=data.get("created_at", "") or now_text(),
            updated_at=data.get("updated_at", "") or now_text(),
        )


class MaterialStore:
    def __init__(self) -> None:
        self.root = information_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    def material_names(self) -> list[str]:
        return sorted([path.name for path in self.root.iterdir() if path.is_dir()], key=str.lower)

    def material_path(self, material: str) -> Path:
        return self.root / material

    def sample_dir(self, material: str, number: int) -> Path:
        return self.material_path(material) / f"#{number}"

    def create_material(self, material: str) -> None:
        material = material.strip()
        if not material:
            raise ValueError("材料文件夹名称不能为空。")
        if any(char in INVALID_FOLDER_CHARS for char in material):
            raise ValueError('名称不能包含这些字符：\\ / : * ? " < > |')
        folder = self.material_path(material)
        if folder.exists():
            raise ValueError("这个材料文件夹已经存在。")
        folder.mkdir()
        self.save_samples(material, [])

    def delete_material(self, material: str) -> None:
        folder = self.material_path(material)
        if folder.exists():
            shutil.rmtree(folder)

    def load_samples(self, material: str) -> list[Sample]:
        path = self.material_path(material) / DATA_FILE
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            messagebox.showerror("读取失败", f"无法读取 {path}")
            return []
        return sorted([Sample.from_dict(item) for item in data], key=lambda item: item.number)

    def save_samples(self, material: str, samples: list[Sample]) -> None:
        folder = self.material_path(material)
        folder.mkdir(parents=True, exist_ok=True)
        data = [asdict(sample) for sample in sorted(samples, key=lambda item: item.number)]
        (folder / DATA_FILE).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def add_sample(self, material: str) -> Sample:
        samples = self.load_samples(material)
        next_number = max([sample.number for sample in samples], default=0) + 1
        sample = Sample(
            number=next_number,
            importance=default_importance(next_number),
            created_at=now_text(),
            updated_at=now_text(),
        )
        samples.append(sample)
        self.save_samples(material, samples)
        self.sample_dir(material, sample.number).mkdir(parents=True, exist_ok=True)
        return sample

    def update_sample(self, material: str, updated: Sample) -> None:
        samples = self.load_samples(material)
        for index, sample in enumerate(samples):
            if sample.number == updated.number:
                updated.created_at = sample.created_at
                updated.updated_at = now_text()
                samples[index] = updated
                self.save_samples(material, samples)
                self.sample_dir(material, updated.number).mkdir(parents=True, exist_ok=True)
                return
        raise ValueError("没有找到要保存的样品。")

    def delete_sample(self, material: str, number: int) -> None:
        samples = [sample for sample in self.load_samples(material) if sample.number != number]
        self.save_samples(material, samples)
        folder = self.sample_dir(material, number)
        if folder.exists():
            shutil.rmtree(folder)

    def save_xrd_data(self, material: str, number: int, rows: list[tuple[float, float, float]]) -> Path:
        folder = self.sample_dir(material, number)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / XRD_DATA_FILE
        xrd_tools.save_xrd_csv(path, rows)
        return path

    def save_processed_xrd_data(
        self,
        material: str,
        number: int,
        theta_rows: list[tuple[float, float, float]],
        d_rows: list[tuple[float, float, float]],
    ) -> Path:
        folder = self.sample_dir(material, number)
        folder.mkdir(parents=True, exist_ok=True)
        if theta_rows:
            xrd_tools.save_xrd_csv(folder / PROCESSED_XRD_DATA_THETA_FILE, theta_rows)
        if d_rows:
            xrd_tools.save_xrd_csv(folder / PROCESSED_XRD_DATA_D_FILE, d_rows)
        return folder

    def load_manual_xrd_peaks(self, material: str, number: int) -> list[dict]:
        path = self.sample_dir(material, number) / MANUAL_XRD_PEAKS_FILE
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        peaks = data.get("peaks", []) if isinstance(data, dict) else []
        return peaks if isinstance(peaks, list) else []

    def save_manual_xrd_peaks(self, material: str, number: int, peaks: list[dict]) -> Path:
        folder = self.sample_dir(material, number)
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / MANUAL_XRD_PEAKS_FILE
        if not peaks:
            if path.exists():
                path.unlink()
            return path
        data = {"updated_at": now_text(), "peaks": peaks}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def delete_xrd_data(self, material: str, number: int) -> None:
        folder = self.sample_dir(material, number)
        for name in (
            XRD_DATA_FILE,
            PLOT_2THETA_FILE,
            PLOT_D_FILE,
            PROCESSED_XRD_DATA_THETA_FILE,
            PROCESSED_XRD_DATA_D_FILE,
            PROCESSED_PLOT_2THETA_FILE,
            PROCESSED_PLOT_D_FILE,
            MANUAL_XRD_PEAKS_FILE,
        ):
            path = folder / name
            if path.exists():
                path.unlink()

    def load_xrd_data(self, material: str, number: int) -> list[tuple[str, str]]:
        path = self.sample_dir(material, number) / XRD_DATA_FILE
        if not path.exists():
            return []
        rows: list[tuple[str, str]] = []
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                rows.append((row.get("2theta", ""), row.get("intensity", "")))
        return rows


class ExMaterialApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.store = MaterialStore()
        self.current_material = ""
        self.current_sample_number = 0
        self.fields = {
            "sample_label": StringVar(),
            "importance": StringVar(),
            "obtained_year": StringVar(),
            "obtained_month": StringVar(),
            "obtained_day": StringVar(),
            "obtained_hour": StringVar(),
            "temperature": StringVar(),
            "pressure": StringVar(),
            "annealing_time": StringVar(),
            "density": StringVar(),
            "heat_capacity": StringVar(),
            "thermal_diffusivity": StringVar(),
            "thermal_conductivity": StringVar(),
            "xrd_wavelength": StringVar(value=DEFAULT_WAVELENGTH),
        }
        self.theta_column = StringVar()
        self.intensity_column = StringVar()
        self.xrd_active_axis = "theta"
        self.processed_xrd_active_axis = "theta"
        self.thermal_rows: list[dict[str, StringVar]] = []
        self.thermal_rows_frame = Frame(root)
        self.xrd_theta_text = Text(root, wrap="none")
        self.xrd_d_text = Text(root, wrap="none")
        self.processed_xrd_theta_text = Text(root, wrap="none")
        self.processed_xrd_d_text = Text(root, wrap="none")
        self.processed_theta_rows: list[tuple[float, float, float]] = []
        self.processed_d_rows: list[tuple[float, float, float]] = []
        self.material_list = Listbox(root, exportselection=False)
        self.sample_list = Listbox(root, exportselection=False)
        self.notes = Text(root, height=5, wrap="word")
        self.thermal_plot_panel = LabelFrame(root)
        self.thermal_plot = Canvas(root)
        self.xrd_section = LabelFrame(root)
        self.plot_panel = LabelFrame(root)
        self.plot_2theta = Canvas(root)
        self.plot_d = Canvas(root)
        self.processed_plot_panel = LabelFrame(root)
        self.processed_plot_2theta = Canvas(root)
        self.processed_plot_d = Canvas(root)
        self.plot_configs: dict[str, dict] = {}
        self.last_sample_density = ""
        self.status = StringVar()
        self.build_ui()
        self.refresh_materials()

    def build_ui(self) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("1280x780")
        self.root.minsize(760, 520)
        self.build_menu()

        main = Frame(self.root, padx=12, pady=12)
        main.pack(fill=BOTH, expand=True)

        materials = Frame(main)
        materials.pack(side=LEFT, fill=Y, padx=(0, 12))
        Label(materials, text="材料文件夹").pack(anchor="w")
        self.material_list = self.listbox_with_scrollbar(materials, width=22)
        self.material_list.bind("<<ListboxSelect>>", self.on_material_select)
        Button(materials, text="新建材料文件夹", command=self.create_material).pack(fill="x", pady=(8, 0))
        Button(materials, text="删除材料文件夹", command=self.delete_material).pack(fill="x", pady=(8, 0))

        samples = Frame(main)
        samples.pack(side=LEFT, fill=Y, padx=(0, 12))
        Label(samples, text="样品").pack(anchor="w")
        self.sample_list = self.listbox_with_scrollbar(samples, width=24)
        self.sample_list.bind("<<ListboxSelect>>", self.on_sample_select)
        sample_buttons = Frame(samples)
        sample_buttons.pack(fill="x", pady=(8, 0))
        Button(sample_buttons, text="+", command=self.add_sample).pack(side=LEFT, fill="x", expand=True)
        Button(sample_buttons, text="- 删除", command=self.delete_sample).pack(side=LEFT, fill="x", expand=True, padx=(8, 0))

        editor_canvas = Canvas(main, highlightthickness=0)
        editor_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        editor_scroll = Scrollbar(main, command=editor_canvas.yview)
        editor_scroll.pack(side=RIGHT, fill=Y)
        editor_canvas.configure(yscrollcommand=editor_scroll.set)
        editor = Frame(editor_canvas)
        editor_window = editor_canvas.create_window((0, 0), window=editor, anchor="nw")
        editor.bind("<Configure>", lambda _event: editor_canvas.configure(scrollregion=editor_canvas.bbox("all")))
        editor_canvas.bind("<Configure>", lambda event: editor_canvas.itemconfigure(editor_window, width=event.width))
        bind_mousewheel(editor_canvas, editor_canvas)
        bind_mousewheel(editor, editor_canvas)

        info = LabelFrame(editor, text="样品信息", padx=10, pady=8)
        info.pack(fill="x")
        self.add_compact_field(info, "样品编号", "sample_label", 0, 0, readonly=True)
        self.add_compact_time_field(info, "获得样品时间", 0, 1)
        self.add_compact_field(info, "温度 (K)", "temperature", 0, 2)
        self.add_compact_field(info, "压强 (GPa)", "pressure", 0, 3)
        self.add_compact_field(info, "退火时间 (h)", "annealing_time", 1, 0)
        self.add_compact_field(info, "XRD 波长 λ (Å)", "xrd_wavelength", 1, 1)
        self.add_compact_field(info, "重要性 (0-3星)", "importance", 1, 2)
        density_entry = self.add_compact_field(info, "样品密度 (g/cm³)", "density", 1, 3)
        density_entry.bind("<KeyRelease>", lambda _event: self.update_sample_density_default())

        for col in range(4):
            info.columnconfigure(col, weight=1, uniform="info")

        Label(info, text="备注").grid(row=2, column=0, sticky="nw", pady=(8, 0), padx=(0, 8))
        notes_frame = Frame(info)
        notes_frame.grid(row=2, column=1, columnspan=3, sticky="ew", pady=(8, 0))
        self.notes = Text(notes_frame, height=4, wrap="word")
        self.notes.pack(side=LEFT, fill=BOTH, expand=True)
        notes_scroll = Scrollbar(notes_frame, command=self.notes.yview)
        notes_scroll.pack(side=RIGHT, fill=Y)
        self.notes.configure(yscrollcommand=notes_scroll.set)
        bind_mousewheel(self.notes)
        bind_mousewheel(notes_scroll, self.notes)
        Button(info, text="保存当前样品", command=self.save_sample).grid(row=3, column=3, sticky="e", pady=(8, 0))

        thermal = LabelFrame(editor, text="热导率数据", padx=10, pady=8)
        thermal.pack(fill="x", pady=(10, 0))
        Label(thermal, text="每行填写一个测试温度点；密度默认等于样品密度，也可以在单行里改成该温度点的密度。热导率 = 密度 × 热容 × 热扩散。").pack(anchor="w")
        self.thermal_rows_frame = Frame(thermal)
        self.thermal_rows_frame.pack(fill="x", pady=(6, 0))
        thermal_buttons = Frame(thermal)
        thermal_buttons.pack(fill="x", pady=(8, 0))
        Button(thermal_buttons, text="+ 添加温度点", command=lambda: self.add_thermal_row()).pack(side=LEFT)
        Button(thermal_buttons, text="清空热导率数据", command=self.clear_thermal_rows).pack(side=LEFT, padx=(8, 0))
        Button(thermal_buttons, text="保存热导率数据", command=self.save_thermal_current).pack(side=LEFT, padx=(8, 0))
        Button(thermal_buttons, text="画温度-热导率图", command=self.plot_thermal_conductivity).pack(side=RIGHT)
        self.set_thermal_rows([])

        self.thermal_plot_panel = LabelFrame(thermal, text="温度-热导率图", padx=10, pady=8)
        thermal_plot_buttons = Frame(self.thermal_plot_panel)
        thermal_plot_buttons.pack(fill="x")
        Button(thermal_plot_buttons, text="关闭图", command=self.hide_thermal_plot).pack(side=RIGHT)
        self.thermal_plot = Canvas(self.thermal_plot_panel, width=650, height=280, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.thermal_plot.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.thermal_plot.bind("<Double-Button-1>", lambda _event: self.open_plot_viewer("thermal"))

        self.xrd_section = LabelFrame(editor, text="XRD 数据", padx=10, pady=8)
        xrd = self.xrd_section
        xrd.pack(fill=BOTH, expand=True, pady=(10, 0))
        Label(xrd, text="原始数据在上，处理后数据在下；每个数据窗口右侧和底部都有滑动条。支持 txt、csv、制表符、空格、多列数据。").grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
        )

        xrd_body = Frame(xrd)
        xrd_body.grid(row=1, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        xrd_body.columnconfigure(0, weight=1)
        xrd_body.columnconfigure(2, weight=1)
        xrd_body.rowconfigure(1, weight=1)
        xrd_body.rowconfigure(5, weight=1)

        Label(xrd_body, text="原始 2theta + 强度").grid(row=0, column=0, sticky="w")
        Label(xrd_body, text="原始 d + 强度").grid(row=0, column=2, sticky="w")
        theta_outer = Frame(xrd_body)
        theta_outer.grid(row=1, column=0, sticky="nsew", pady=(3, 0))
        theta_outer.rowconfigure(0, weight=1)
        theta_outer.columnconfigure(0, weight=1)
        self.xrd_theta_text = self.scrolled_text_box(theta_outer, height=8, focus_axis="theta")

        convert_buttons = Frame(xrd_body, padx=8)
        convert_buttons.grid(row=1, column=1, sticky="ns", pady=(24, 0))
        Button(convert_buttons, text="2θ → d", width=8, command=self.convert_theta_to_d).pack(pady=(0, 8))
        Button(convert_buttons, text="d → 2θ", width=8, command=self.convert_d_to_theta).pack()

        d_outer = Frame(xrd_body)
        d_outer.grid(row=1, column=2, sticky="nsew", pady=(3, 0))
        d_outer.rowconfigure(0, weight=1)
        d_outer.columnconfigure(0, weight=1)
        self.xrd_d_text = self.scrolled_text_box(d_outer, height=8, focus_axis="d")

        xrd_buttons = Frame(xrd)
        xrd_buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        Label(xrd_buttons, text="横坐标列").pack(side=LEFT)
        Entry(xrd_buttons, textvariable=self.theta_column, width=5).pack(side=LEFT, padx=(4, 8))
        Label(xrd_buttons, text="强度列").pack(side=LEFT)
        Entry(xrd_buttons, textvariable=self.intensity_column, width=5).pack(side=LEFT, padx=(4, 12))
        Button(xrd_buttons, text="清空", command=self.clear_xrd_text).pack(side=LEFT)
        Button(xrd_buttons, text="保存XRD数据", command=self.save_xrd_current).pack(side=LEFT, padx=(6, 0))
        Button(xrd_buttons, text="画图", command=self.plot_xrd).pack(side=RIGHT)

        processed_hint = Label(xrd, text="处理后 XRD 数据只用于复制和画处理后图，不覆盖原始 XRD 数据。")
        processed_hint.grid(row=3, column=0, columnspan=3, sticky="w", pady=(10, 0))

        processed_body = Frame(xrd)
        processed_body.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(4, 0))
        processed_body.columnconfigure(0, weight=1)
        processed_body.columnconfigure(2, weight=1)
        processed_body.rowconfigure(1, weight=1)
        Label(processed_body, text="处理后 2theta + 强度").grid(row=0, column=0, sticky="w")
        Label(processed_body, text="处理后 d + 强度").grid(row=0, column=2, sticky="w")

        processed_theta_outer = Frame(processed_body)
        processed_theta_outer.grid(row=1, column=0, sticky="nsew", pady=(3, 0))
        processed_theta_outer.rowconfigure(0, weight=1)
        processed_theta_outer.columnconfigure(0, weight=1)
        self.processed_xrd_theta_text = self.scrolled_text_box(processed_theta_outer, height=8, processed_axis="theta")

        processed_buttons_middle = Frame(processed_body, padx=8)
        processed_buttons_middle.grid(row=1, column=1, sticky="ns", pady=(24, 0))
        Button(processed_buttons_middle, text="复制左侧", width=8, command=self.copy_processed_theta).pack(pady=(0, 8))
        Button(processed_buttons_middle, text="复制右侧", width=8, command=self.copy_processed_d).pack()

        processed_d_outer = Frame(processed_body)
        processed_d_outer.grid(row=1, column=2, sticky="nsew", pady=(3, 0))
        processed_d_outer.rowconfigure(0, weight=1)
        processed_d_outer.columnconfigure(0, weight=1)
        self.processed_xrd_d_text = self.scrolled_text_box(processed_d_outer, height=8, processed_axis="d")

        processed_buttons = Frame(xrd)
        processed_buttons.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        Label(processed_buttons, text="处理：分别平滑归一化；d 轴按峰面积校正").pack(side=LEFT)
        Button(processed_buttons, text="手动寻峰/修正", command=self.open_manual_peak_window).pack(side=LEFT, padx=(10, 0))
        Button(processed_buttons, text="生成处理后数据", command=self.generate_processed_xrd_data).pack(side=RIGHT)
        Button(processed_buttons, text="画处理后图", command=self.plot_processed_xrd_current).pack(side=RIGHT, padx=(0, 8))
        xrd.columnconfigure(0, weight=1)
        xrd.columnconfigure(1, weight=0)
        xrd.columnconfigure(2, weight=1)
        xrd.rowconfigure(1, weight=1)
        xrd.rowconfigure(4, weight=1)

        self.plot_panel = LabelFrame(editor, text="XRD 图", padx=10, pady=8)
        plot_buttons = Frame(self.plot_panel)
        plot_buttons.pack(fill="x")
        Button(plot_buttons, text="关闭图", command=self.hide_plots).pack(side=RIGHT)
        plot_body = Frame(self.plot_panel)
        plot_body.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.plot_2theta = Canvas(plot_body, width=430, height=260, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.plot_2theta.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        self.plot_2theta.bind("<Double-Button-1>", lambda _event: self.open_plot_viewer("2theta"))
        self.plot_d = Canvas(plot_body, width=430, height=260, bg="white", highlightthickness=1, highlightbackground="#cccccc")
        self.plot_d.pack(side=LEFT, fill=BOTH, expand=True)
        self.plot_d.bind("<Double-Button-1>", lambda _event: self.open_plot_viewer("d"))

        self.processed_plot_panel = LabelFrame(editor, text="处理后 XRD 图", padx=10, pady=8)
        processed_plot_buttons = Frame(self.processed_plot_panel)
        processed_plot_buttons.pack(fill="x")
        Button(processed_plot_buttons, text="关闭图", command=self.hide_processed_plots).pack(side=RIGHT)
        processed_plot_body = Frame(self.processed_plot_panel)
        processed_plot_body.pack(fill=BOTH, expand=True, pady=(8, 0))
        self.processed_plot_2theta = Canvas(
            processed_plot_body,
            width=430,
            height=260,
            bg="white",
            highlightthickness=1,
            highlightbackground="#cccccc",
        )
        self.processed_plot_2theta.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
        self.processed_plot_2theta.bind("<Double-Button-1>", lambda _event: self.open_plot_viewer("processed_2theta"))
        self.processed_plot_d = Canvas(
            processed_plot_body,
            width=430,
            height=260,
            bg="white",
            highlightthickness=1,
            highlightbackground="#cccccc",
        )
        self.processed_plot_d.pack(side=LEFT, fill=BOTH, expand=True)
        self.processed_plot_d.bind("<Double-Button-1>", lambda _event: self.open_plot_viewer("processed_d"))

        bind_mousewheel_tree(editor, editor_canvas)
        Label(self.root, textvariable=self.status, anchor="w", relief="sunken").pack(fill="x")

    def build_menu(self) -> None:
        menubar = Menu(self.root)
        function_menu = Menu(menubar, tearoff=0)
        function_menu.add_command(label="对比", command=self.open_compare_window)
        menubar.add_cascade(label="功能", menu=function_menu)
        self.root.config(menu=menubar)

    def open_compare_window(self) -> None:
        xrd_tools.XrdCompareWindow(self.root, self.store)

    def listbox_with_scrollbar(self, parent: Frame, width: int) -> Listbox:
        frame = Frame(parent)
        frame.pack(fill=BOTH, expand=True)
        box = Listbox(frame, width=width, exportselection=False)
        box.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar = Scrollbar(frame, command=box.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        box.config(yscrollcommand=scrollbar.set)
        bind_mousewheel(box)
        bind_mousewheel(scrollbar, box)
        return box

    def scrolled_text_box(self, parent: Frame, height: int, focus_axis: str | None = None, processed_axis: str | None = None) -> Text:
        frame = Frame(parent, relief="sunken", borderwidth=1, bg="#d0d0d0")
        frame.grid(sticky="nsew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = Text(frame, height=height, wrap="none", undo=True, borderwidth=0)
        text.grid(row=0, column=0, sticky="nsew")
        y_scroll = Scrollbar(frame, command=text.yview, width=22)
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll = Scrollbar(frame, command=text.xview, orient="horizontal", width=18)
        x_scroll.grid(row=1, column=0, sticky="ew")
        corner = Frame(frame, width=22, height=18, bg="#d0d0d0")
        corner.grid(row=1, column=1, sticky="nsew")
        text.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        bind_mousewheel(text)
        bind_mousewheel(y_scroll, text)
        if focus_axis:
            text.bind("<FocusIn>", lambda _event, axis=focus_axis: self.mark_xrd_axis(axis))
            text.bind("<KeyRelease>", lambda _event, axis=focus_axis: self.mark_xrd_axis(axis))
        if processed_axis:
            text.bind("<FocusIn>", lambda _event, axis=processed_axis: self.mark_processed_xrd_axis(axis))
            text.bind("<KeyRelease>", lambda _event, axis=processed_axis: self.mark_processed_xrd_axis(axis))
        return text

    def add_field(self, parent: Frame, label: str, key: str, row: int, column: int, readonly: bool = False) -> Entry:
        Label(parent, text=label).grid(row=row, column=column, sticky="w", pady=5, padx=(0 if column == 0 else 16, 8))
        state = "readonly" if readonly else "normal"
        entry = Entry(parent, textvariable=self.fields[key], state=state)
        entry.grid(row=row, column=column + 1, sticky="ew", pady=5)
        return entry

    def add_compact_field(self, parent: Frame, label: str, key: str, row: int, column: int, readonly: bool = False) -> Entry:
        box = Frame(parent, padx=4, pady=3)
        box.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=2)
        Label(box, text=label, anchor="w").pack(fill="x")
        state = "readonly" if readonly else "normal"
        entry = Entry(box, textvariable=self.fields[key], state=state)
        entry.pack(fill="x")
        return entry

    def add_compact_time_field(self, parent: Frame, label: str, row: int, column: int) -> None:
        box = Frame(parent, padx=4, pady=3)
        box.grid(row=row, column=column, sticky="ew", padx=(0 if column == 0 else 8, 0), pady=2)
        Label(box, text=label, anchor="w").pack(fill="x")
        inner = Frame(box)
        inner.pack(fill="x")
        parts = [
            ("obtained_year", "年", 5),
            ("obtained_month", "月", 3),
            ("obtained_day", "日", 3),
        ]
        for key, suffix, width in parts:
            Entry(inner, textvariable=self.fields[key], width=width).pack(side=LEFT)
            Label(inner, text=suffix).pack(side=LEFT, padx=(1, 3))

    def add_time_field(self, parent: Frame, label: str, row: int, column: int) -> None:
        Label(parent, text=label).grid(row=row, column=column, sticky="w", pady=5, padx=(16, 8))
        box = Frame(parent)
        box.grid(row=row, column=column + 1, sticky="ew", pady=5)
        parts = [
            ("obtained_year", "年", 5),
            ("obtained_month", "月", 3),
            ("obtained_day", "日", 3),
        ]
        for key, suffix, width in parts:
            Entry(box, textvariable=self.fields[key], width=width).pack(side=LEFT)
            Label(box, text=suffix).pack(side=LEFT, padx=(2, 6))

    def set_thermal_rows(self, rows: list[dict[str, str]]) -> None:
        self.thermal_rows = []
        for row in rows:
            self.thermal_rows.append(self.make_thermal_vars(row))
        if not self.thermal_rows:
            self.thermal_rows.append(self.make_thermal_vars({}))
        self.redraw_thermal_rows()
        self.update_all_thermal_rows()

    def make_thermal_vars(self, row: dict[str, str]) -> dict[str, StringVar]:
        values = {
            "temperature_c": row.get("temperature_c", ""),
            "density": row.get("density", "") or self.fields["density"].get().strip(),
            "heat_capacity": row.get("heat_capacity", ""),
            "thermal_diffusivity": row.get("thermal_diffusivity", ""),
            "thermal_conductivity": row.get("thermal_conductivity", ""),
        }
        if not values["thermal_conductivity"]:
            values["thermal_conductivity"] = thermal_conductivity_text(
                values["density"],
                values["heat_capacity"],
                values["thermal_diffusivity"],
            )
        return {key: StringVar(value=value) for key, value in values.items()}

    def redraw_thermal_rows(self) -> None:
        for child in self.thermal_rows_frame.winfo_children():
            child.destroy()
        headers = ["温度 (°C)", "密度 (g/cm³)", "热容 (J/(g·K))", "热扩散 (mm²/s)", "热导率 (W/(m·K))", ""]
        widths = [10, 12, 14, 14, 15, 8]
        for column, (header, width) in enumerate(zip(headers, widths)):
            Label(self.thermal_rows_frame, text=header, anchor="w").grid(row=0, column=column, sticky="ew", padx=(0, 8), pady=(0, 4))
            self.thermal_rows_frame.columnconfigure(column, weight=1 if column < 5 else 0)
        for index, row in enumerate(self.thermal_rows, start=1):
            Entry(self.thermal_rows_frame, textvariable=row["temperature_c"], width=widths[0]).grid(row=index, column=0, sticky="ew", padx=(0, 8), pady=2)
            density_entry = Entry(self.thermal_rows_frame, textvariable=row["density"], width=widths[1])
            density_entry.grid(row=index, column=1, sticky="ew", padx=(0, 8), pady=2)
            heat_entry = Entry(self.thermal_rows_frame, textvariable=row["heat_capacity"], width=widths[2])
            heat_entry.grid(row=index, column=2, sticky="ew", padx=(0, 8), pady=2)
            diff_entry = Entry(self.thermal_rows_frame, textvariable=row["thermal_diffusivity"], width=widths[3])
            diff_entry.grid(row=index, column=3, sticky="ew", padx=(0, 8), pady=2)
            Entry(self.thermal_rows_frame, textvariable=row["thermal_conductivity"], state="readonly", width=widths[4]).grid(
                row=index,
                column=4,
                sticky="ew",
                padx=(0, 8),
                pady=2,
            )
            for entry in (density_entry, heat_entry, diff_entry):
                entry.bind("<KeyRelease>", lambda _event, row_index=index - 1: self.update_thermal_row(row_index))
            Button(self.thermal_rows_frame, text="删除", command=lambda row_index=index - 1: self.delete_thermal_row(row_index)).grid(row=index, column=5, sticky="ew", pady=2)

    def add_thermal_row(self, row: dict[str, str] | None = None) -> None:
        row = row or {"density": self.fields["density"].get().strip()}
        if len(self.thermal_rows) == 1 and not any(value.get().strip() for value in self.thermal_rows[0].values()):
            self.thermal_rows[0] = self.make_thermal_vars(row)
        else:
            self.thermal_rows.append(self.make_thermal_vars(row))
        self.redraw_thermal_rows()

    def delete_thermal_row(self, index: int) -> None:
        if 0 <= index < len(self.thermal_rows):
            self.thermal_rows.pop(index)
        if not self.thermal_rows:
            self.thermal_rows.append(self.make_thermal_vars({}))
        self.redraw_thermal_rows()

    def clear_thermal_rows(self) -> None:
        self.set_thermal_rows([])

    def update_thermal_row(self, index: int) -> None:
        if not (0 <= index < len(self.thermal_rows)):
            return
        row = self.thermal_rows[index]
        row["thermal_conductivity"].set(
            thermal_conductivity_text(
                self.thermal_row_density(row),
                row["heat_capacity"].get(),
                row["thermal_diffusivity"].get(),
            )
        )

    def update_all_thermal_rows(self) -> None:
        for index in range(len(self.thermal_rows)):
            self.update_thermal_row(index)

    def update_sample_density_default(self) -> None:
        new_density = self.fields["density"].get().strip()
        old_density = self.last_sample_density
        for row in self.thermal_rows:
            current = row["density"].get().strip()
            if not current or current == old_density:
                row["density"].set(new_density)
        self.last_sample_density = new_density
        self.update_all_thermal_rows()

    def thermal_row_density(self, row: dict[str, StringVar]) -> str:
        override = row["density"].get().strip()
        if override:
            return override
        return self.fields["density"].get().strip()

    def collect_thermal_rows(self) -> list[dict[str, str]]:
        self.update_all_thermal_rows()
        rows: list[dict[str, str]] = []
        for row in self.thermal_rows:
            item = {key: value.get().strip() for key, value in row.items()}
            if any(value for value in item.values()):
                rows.append(item)
        return rows

    def first_thermal_row(self, rows: list[dict[str, str]]) -> dict[str, str]:
        return rows[0] if rows else {}

    def mark_xrd_axis(self, axis: str) -> None:
        self.xrd_active_axis = axis

    def mark_processed_xrd_axis(self, axis: str) -> None:
        self.processed_xrd_active_axis = axis

    def save_thermal_current(self) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        self.save_sample()
        self.set_status(f"已保存 {self.current_material} / #{self.current_sample_number} 的热导率数据")

    def plot_thermal_conductivity(self) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        self.save_sample()
        rows = self.collect_thermal_rows()
        points = thermal_tools.thermal_points(rows)
        if len(points) < 2:
            messagebox.showwarning("无法画图", "至少需要两个有效温度点才能画温度-热导率关系图。")
            return
        config = thermal_tools.thermal_plot_config(points)
        self.plot_configs["thermal"] = config
        self.show_thermal_plot()
        draw_scatter_plot(self.thermal_plot, **config)
        folder = self.store.sample_dir(self.current_material, self.current_sample_number)
        folder.mkdir(parents=True, exist_ok=True)
        try:
            thermal_tools.save_thermal_plot(folder / THERMAL_PLOT_FILE, points)
        except RuntimeError as exc:
            messagebox.showwarning("JPG 保存失败", str(exc))
            return
        self.set_status(f"已保存温度-热导率图：{folder / THERMAL_PLOT_FILE}")

    def show_thermal_plot(self) -> None:
        if not self.thermal_plot_panel.winfo_ismapped():
            self.thermal_plot_panel.pack(fill=BOTH, expand=True, pady=(6, 0))

    def hide_thermal_plot(self) -> None:
        self.thermal_plot_panel.pack_forget()
        self.thermal_plot.delete("all")
        self.plot_configs.pop("thermal", None)

    def set_xrd_rows(self, values: list[tuple[str, str]]) -> None:
        self.xrd_theta_text.delete("1.0", END)
        self.xrd_d_text.delete("1.0", END)
        self.clear_processed_xrd_text()
        if values:
            rows: list[tuple[float, float, float]] = []
            try:
                wavelength = xrd_tools.parse_wavelength(self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH)
            except ValueError:
                wavelength = xrd_tools.parse_wavelength(DEFAULT_WAVELENGTH)
            for theta_text, intensity_text in values:
                try:
                    theta = float(theta_text)
                    intensity = float(intensity_text)
                    rows.append((theta, intensity, xrd_tools.theta_to_d(theta, wavelength)))
                except ValueError:
                    continue
            if rows:
                self.xrd_theta_text.insert("1.0", xrd_tools.rows_to_theta_text(rows))
                self.xrd_d_text.insert("1.0", xrd_tools.rows_to_d_text(rows))
                self.mark_xrd_axis("theta")

    def xrd_theta_text_value(self) -> str:
        return self.xrd_theta_text.get("1.0", END).rstrip("\n")

    def xrd_d_text_value(self) -> str:
        return self.xrd_d_text.get("1.0", END).rstrip("\n")

    def processed_xrd_theta_text_value(self) -> str:
        return self.processed_xrd_theta_text.get("1.0", END).rstrip("\n")

    def processed_xrd_d_text_value(self) -> str:
        return self.processed_xrd_d_text.get("1.0", END).rstrip("\n")

    def set_xrd_theta_text_value(self, text: str) -> None:
        self.xrd_theta_text.delete("1.0", END)
        if text:
            self.xrd_theta_text.insert("1.0", text)
        self.mark_xrd_axis("theta")

    def set_xrd_d_text_value(self, text: str) -> None:
        self.xrd_d_text.delete("1.0", END)
        if text:
            self.xrd_d_text.insert("1.0", text)
        self.mark_xrd_axis("d")

    def clear_xrd_text(self) -> None:
        self.xrd_theta_text.delete("1.0", END)
        self.xrd_d_text.delete("1.0", END)
        self.clear_processed_xrd_text()

    def clear_processed_xrd_text(self) -> None:
        self.processed_xrd_theta_text.delete("1.0", END)
        self.processed_xrd_d_text.delete("1.0", END)
        self.processed_theta_rows = []
        self.processed_d_rows = []

    def copy_text_to_clipboard(self, text: str) -> None:
        if not text.strip():
            messagebox.showinfo("没有数据", "当前数据框为空。")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.set_status("数据已复制到剪贴板")

    def copy_processed_theta(self) -> None:
        self.copy_text_to_clipboard(self.processed_xrd_theta_text_value())

    def copy_processed_d(self) -> None:
        self.copy_text_to_clipboard(self.processed_xrd_d_text_value())

    def convert_theta_to_d(self) -> None:
        try:
            rows, skipped_rows = xrd_tools.parse_xrd_axis_text(
                self.xrd_theta_text_value(),
                self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH,
                "theta",
                self.theta_column.get(),
                self.intensity_column.get(),
            )
        except ValueError as exc:
            messagebox.showwarning("无法转换", str(exc))
            return
        self.set_xrd_d_text_value(xrd_tools.rows_to_d_text(rows))
        self.set_status(f"已将 2theta 转换为 d，共 {len(rows)} 行" + (f"，跳过 {skipped_rows} 行" if skipped_rows else ""))

    def convert_d_to_theta(self) -> None:
        try:
            rows, skipped_rows = xrd_tools.parse_xrd_axis_text(
                self.xrd_d_text_value(),
                self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH,
                "d",
                self.theta_column.get(),
                self.intensity_column.get(),
            )
        except ValueError as exc:
            messagebox.showwarning("无法转换", str(exc))
            return
        self.set_xrd_theta_text_value(xrd_tools.rows_to_theta_text(rows))
        self.set_status(f"已将 d 转换为 2theta，共 {len(rows)} 行" + (f"，跳过 {skipped_rows} 行" if skipped_rows else ""))

    def generate_processed_xrd_data(self) -> bool:
        theta_text = self.xrd_theta_text_value()
        d_text = self.xrd_d_text_value()
        if not theta_text.strip() and not d_text.strip():
            messagebox.showwarning("无法处理", "请先在原始 2theta 或 d 数据框中粘贴 XRD 数据。")
            return False
        skipped_rows = 0
        raw_theta_rows: list[tuple[float, float, float]] = []
        raw_d_rows: list[tuple[float, float, float]] = []
        try:
            if theta_text.strip():
                raw_theta_rows, skipped = xrd_tools.parse_xrd_axis_text(
                    theta_text,
                    self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH,
                    "theta",
                    self.theta_column.get(),
                    self.intensity_column.get(),
                )
                skipped_rows += skipped
            if d_text.strip():
                raw_d_rows, skipped = xrd_tools.parse_xrd_axis_text(
                    d_text,
                    self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH,
                    "d",
                    self.theta_column.get(),
                    self.intensity_column.get(),
                )
                skipped_rows += skipped
        except ValueError as exc:
            messagebox.showwarning("无法处理", str(exc))
            return False
        source_rows = raw_theta_rows or raw_d_rows
        theta_source = raw_theta_rows if raw_theta_rows else source_rows
        d_source = raw_d_rows if raw_d_rows else source_rows
        self.processed_theta_rows = xrd_tools.process_xrd_rows(theta_source, "theta")
        self.processed_d_rows = xrd_tools.process_xrd_rows(d_source, "d")
        if len(self.processed_theta_rows) < 2 and len(self.processed_d_rows) < 2:
            messagebox.showwarning("无法处理", "有效 XRD 数据不足，无法生成处理后数据。")
            return False
        if self.current_material and self.current_sample_number:
            self.store.save_manual_xrd_peaks(self.current_material, self.current_sample_number, [])
        self.processed_xrd_theta_text.delete("1.0", END)
        self.processed_xrd_d_text.delete("1.0", END)
        self.processed_xrd_theta_text.insert("1.0", xrd_tools.rows_to_theta_text(self.processed_theta_rows))
        self.processed_xrd_d_text.insert("1.0", xrd_tools.rows_to_d_text(self.processed_d_rows))
        self.mark_processed_xrd_axis("theta")
        skipped_text = f"，跳过 {skipped_rows} 行" if skipped_rows else ""
        self.set_status(
            f"已在主界面生成处理后 XRD 数据：2theta {len(self.processed_theta_rows)} 行，d {len(self.processed_d_rows)} 行{skipped_text}"
        )
        return True

    def current_processed_xrd_rows(self) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
        theta_rows: list[tuple[float, float, float]] = []
        d_rows: list[tuple[float, float, float]] = []
        wavelength = self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH
        if self.processed_xrd_theta_text_value().strip():
            theta_rows = xrd_tools.processed_rows_from_text(
                self.processed_xrd_theta_text_value(),
                wavelength,
                "theta",
            )
        if self.processed_xrd_d_text_value().strip():
            d_rows = xrd_tools.processed_rows_from_text(
                self.processed_xrd_d_text_value(),
                wavelength,
                "d",
            )
        if not theta_rows and d_rows:
            theta_rows = xrd_tools.finalize_processed_rows(d_rows, "theta")
        if not d_rows and theta_rows:
            d_rows = xrd_tools.finalize_processed_rows(theta_rows, "d")
        return theta_rows, d_rows

    def plot_processed_xrd_current(self) -> None:
        if not self.processed_xrd_theta_text_value().strip() and not self.processed_xrd_d_text_value().strip():
            if not self.generate_processed_xrd_data():
                return
        try:
            theta_rows, d_rows = self.current_processed_xrd_rows()
        except ValueError as exc:
            messagebox.showwarning("无法画处理后图", str(exc))
            return
        self.processed_theta_rows = theta_rows
        self.processed_d_rows = d_rows
        self.processed_xrd_theta_text.delete("1.0", END)
        self.processed_xrd_d_text.delete("1.0", END)
        self.processed_xrd_theta_text.insert("1.0", xrd_tools.rows_to_theta_text(theta_rows))
        self.processed_xrd_d_text.insert("1.0", xrd_tools.rows_to_d_text(d_rows))
        self.plot_processed_xrd_rows(theta_rows, d_rows)

    def open_manual_peak_window(self) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        if not self.processed_xrd_theta_text_value().strip() and not self.processed_xrd_d_text_value().strip():
            if not self.generate_processed_xrd_data():
                return
        try:
            theta_rows, d_rows = self.current_processed_xrd_rows()
        except ValueError as exc:
            messagebox.showwarning("无法打开手动寻峰", str(exc))
            return
        if len(theta_rows) < 2 and len(d_rows) < 2:
            messagebox.showwarning("无法打开手动寻峰", "处理后 XRD 数据至少需要两行有效数据。")
            return
        theta_rows = xrd_tools.finalize_processed_rows(theta_rows if len(theta_rows) >= 2 else d_rows, "theta")
        d_rows = xrd_tools.finalize_processed_rows(d_rows if len(d_rows) >= 2 else theta_rows, "d")
        peaks = self.store.load_manual_xrd_peaks(self.current_material, self.current_sample_number)
        xrd_tools.ManualPeakWindow(self.root, theta_rows, d_rows, peaks, self.apply_manual_peak_changes)

    def apply_manual_peak_changes(
        self,
        theta_rows: list[tuple[float, float, float]],
        d_rows: list[tuple[float, float, float]],
        peaks: list[dict],
    ) -> None:
        self.processed_theta_rows = theta_rows
        self.processed_d_rows = d_rows
        self.plot_processed_xrd_rows(theta_rows, d_rows)
        path = self.store.save_manual_xrd_peaks(self.current_material, self.current_sample_number, peaks)
        if peaks:
            self.set_status(f"已保存处理后 XRD、局部峰修正和 {len(peaks)} 个手动峰标记：{path}")
        else:
            self.set_status("已保存处理后 XRD；手动峰标记已清空。")

    def selected_xrd_axis_and_text(self) -> tuple[str, str]:
        theta_text = self.xrd_theta_text_value()
        d_text = self.xrd_d_text_value()
        if self.xrd_active_axis == "d" and d_text.strip():
            return "d", d_text
        if self.xrd_active_axis == "theta" and theta_text.strip():
            return "theta", theta_text
        if theta_text.strip():
            return "theta", theta_text
        if d_text.strip():
            return "d", d_text
        return self.xrd_active_axis, ""

    def parse_current_xrd_rows(self) -> tuple[list[tuple[float, float, float]], int, str]:
        axis, text = self.selected_xrd_axis_and_text()
        if not text.strip():
            raise ValueError("请先在 2theta 或 d 数据框中粘贴 XRD 数据。")
        rows, skipped_rows = xrd_tools.parse_xrd_axis_text(
            text,
            self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH,
            axis,
            self.theta_column.get(),
            self.intensity_column.get(),
        )
        return rows, skipped_rows, axis

    def save_xrd_current(self) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        self.save_sample()
        if not self.xrd_theta_text_value().strip() and not self.xrd_d_text_value().strip():
            self.store.delete_xrd_data(self.current_material, self.current_sample_number)
            self.hide_plots()
            self.hide_processed_plots()
            self.set_status(f"已删除 {self.current_material} / #{self.current_sample_number} 的 XRD 数据和图")
            return
        try:
            rows, skipped_rows, axis = self.parse_current_xrd_rows()
        except ValueError as exc:
            messagebox.showwarning("无法保存", str(exc))
            return
        data_path = self.store.save_xrd_data(self.current_material, self.current_sample_number, rows)
        axis_label = "d" if axis == "d" else "2theta"
        skipped_text = f"，跳过 {skipped_rows} 行" if skipped_rows else ""
        self.set_status(f"已从 {axis_label} 侧保存 {len(rows)} 行 XRD 数据{skipped_text}：{data_path}")

    def refresh_materials(self) -> None:
        self.material_list.delete(0, END)
        for name in self.store.material_names():
            self.material_list.insert(END, name)
        self.set_status()

    def refresh_samples(self, selected_number: int = 0) -> None:
        self.sample_list.delete(0, END)
        if not self.current_material:
            return
        for sample in self.store.load_samples(self.current_material):
            self.sample_list.insert(END, sample.list_label)
        if selected_number:
            self.select_sample(selected_number)
        self.set_status()

    def create_material(self) -> None:
        name = simpledialog.askstring("新建材料文件夹", "请输入材料或样品系列名称：", parent=self.root)
        if name is None:
            return
        try:
            self.store.create_material(name)
        except ValueError as exc:
            messagebox.showwarning("无法创建", str(exc))
            return
        self.refresh_materials()
        self.select_material(name.strip())

    def delete_material(self) -> None:
        selection = self.material_list.curselection()
        if not selection:
            messagebox.showinfo("请先选择", "请先选择要删除的材料文件夹。")
            return
        material = self.material_list.get(selection[0])
        message = f"确定删除材料文件夹“{material}”吗？\n\n其中所有样品记录、XRD 数据和图都会一起删除。"
        if not messagebox.askyesno("确认删除", message):
            return
        try:
            self.store.delete_material(material)
        except OSError as exc:
            messagebox.showerror("删除失败", f"无法删除材料文件夹：\n{exc}")
            return
        self.current_material = ""
        self.clear_editor()
        self.sample_list.delete(0, END)
        self.refresh_materials()
        self.set_status(f"已删除材料文件夹：{material}")

    def select_material(self, material: str) -> None:
        for index in range(self.material_list.size()):
            if self.material_list.get(index) == material:
                self.material_list.selection_clear(0, END)
                self.material_list.selection_set(index)
                self.material_list.see(index)
                self.on_material_select()
                return

    def on_material_select(self, _event=None) -> None:
        selection = self.material_list.curselection()
        if not selection:
            return
        self.current_material = self.material_list.get(selection[0])
        self.clear_editor()
        self.refresh_samples()

    def add_sample(self) -> None:
        if not self.current_material:
            messagebox.showinfo("请先选择", "请先创建或选择一个材料文件夹。")
            return
        sample = self.store.add_sample(self.current_material)
        self.refresh_samples(sample.number)
        self.load_sample(sample)

    def selected_sample_number(self) -> int:
        selection = self.sample_list.curselection()
        if not selection:
            return 0
        match = re.search(r"#(\d+)", self.sample_list.get(selection[0]))
        return int(match.group(1)) if match else 0

    def select_sample(self, number: int) -> None:
        for index in range(self.sample_list.size()):
            match = re.search(r"#(\d+)", self.sample_list.get(index))
            if match and int(match.group(1)) == number:
                self.sample_list.selection_clear(0, END)
                self.sample_list.selection_set(index)
                self.sample_list.see(index)
                return

    def on_sample_select(self, _event=None) -> None:
        number = self.selected_sample_number()
        if not number:
            return
        for sample in self.store.load_samples(self.current_material):
            if sample.number == number:
                self.load_sample(sample)
                return

    def thermal_rows_with_sample_density(self, sample: Sample) -> list[dict[str, str]]:
        rows = []
        sample_density = sample.density.strip()
        for row in sample.thermal_rows:
            item = dict(row)
            if sample_density and not item.get("density", "").strip():
                item["density"] = sample_density
            rows.append(item)
        return rows

    def load_sample(self, sample: Sample) -> None:
        self.current_sample_number = sample.number
        self.fields["sample_label"].set(sample.label)
        self.fields["importance"].set(str(clamp_importance(sample.importance)))
        self.fields["obtained_year"].set(sample.obtained_year)
        self.fields["obtained_month"].set(sample.obtained_month)
        self.fields["obtained_day"].set(sample.obtained_day)
        self.fields["obtained_hour"].set("")
        self.fields["temperature"].set(sample.temperature)
        self.fields["pressure"].set(sample.pressure)
        self.fields["annealing_time"].set(sample.annealing_time)
        self.fields["density"].set(sample.density)
        self.last_sample_density = sample.density.strip()
        self.set_thermal_rows(self.thermal_rows_with_sample_density(sample))
        self.fields["xrd_wavelength"].set(sample.xrd_wavelength or DEFAULT_WAVELENGTH)
        self.notes.delete("1.0", END)
        self.notes.insert("1.0", sample.notes)
        self.set_xrd_rows(self.store.load_xrd_data(self.current_material, sample.number))
        self.hide_thermal_plot()
        self.hide_plots()
        self.hide_processed_plots()
        self.set_status(f"正在编辑 {self.current_material} / {sample.label}")

    def save_sample(self) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        thermal_rows = self.collect_thermal_rows()
        first_thermal = self.first_thermal_row(thermal_rows)
        sample = Sample(
            number=self.current_sample_number,
            importance=clamp_importance(self.fields["importance"].get()),
            obtained_year=self.fields["obtained_year"].get().strip(),
            obtained_month=self.fields["obtained_month"].get().strip(),
            obtained_day=self.fields["obtained_day"].get().strip(),
            obtained_hour="",
            temperature=self.fields["temperature"].get().strip(),
            pressure=self.fields["pressure"].get().strip(),
            annealing_time=self.fields["annealing_time"].get().strip(),
            density=self.fields["density"].get().strip(),
            heat_capacity=first_thermal.get("heat_capacity", ""),
            thermal_diffusivity=first_thermal.get("thermal_diffusivity", ""),
            thermal_conductivity=first_thermal.get("thermal_conductivity", ""),
            thermal_rows=thermal_rows,
            xrd_wavelength=self.fields["xrd_wavelength"].get().strip() or DEFAULT_WAVELENGTH,
            notes=self.notes.get("1.0", END).strip(),
        )
        try:
            self.store.update_sample(self.current_material, sample)
        except ValueError as exc:
            messagebox.showwarning("保存失败", str(exc))
            return
        self.refresh_samples(sample.number)
        self.set_status(f"已保存 {self.current_material} / {sample.label}")

    def parse_float_field(self, key: str) -> float | None:
        text = self.fields[key].get().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def calculate_thermal_conductivity(self) -> str:
        density = self.parse_float_field("density")
        heat_capacity = self.parse_float_field("heat_capacity")
        diffusivity = self.parse_float_field("thermal_diffusivity")
        if density is None or heat_capacity is None or diffusivity is None:
            return ""
        return f"{density * heat_capacity * diffusivity:.6g}"

    def update_thermal_conductivity(self) -> None:
        self.fields["thermal_conductivity"].set(self.calculate_thermal_conductivity())

    def delete_sample(self) -> None:
        if not self.current_material:
            messagebox.showinfo("请先选择", "请先选择一个材料文件夹。")
            return
        number = self.selected_sample_number() or self.current_sample_number
        if not number:
            messagebox.showinfo("请先选择", "请先选择要删除的样品。")
            return
        if not messagebox.askyesno("确认删除", f"确定删除 {self.current_material} 中的 #{number} 吗？\n\n该样品的 XRD 数据和图也会删除。"):
            return
        self.store.delete_sample(self.current_material, number)
        self.clear_editor()
        self.refresh_samples()
        self.set_status(f"已删除 {self.current_material} / #{number}")

    def collect_xrd_rows(self) -> list[tuple[float, float, float]]:
        rows, skipped_rows, _axis = self.parse_current_xrd_rows()
        if skipped_rows:
            self.set_status(f"已跳过 {skipped_rows} 行非数据行或无效行")
        return rows

    def extract_numbers(self, line: str) -> list[float]:
        return xrd_tools.extract_numbers(line)

    def selected_or_inferred_xrd_columns(self, numeric_rows: list[tuple[int, list[float]]]) -> tuple[int, int]:
        return xrd_tools.selected_or_inferred_xrd_columns(numeric_rows, self.theta_column.get(), self.intensity_column.get())

    def infer_xrd_columns(self, numeric_rows: list[tuple[int, list[float]]]) -> tuple[int, int]:
        return xrd_tools.infer_xrd_columns(numeric_rows)

    def plot_xrd(self) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        self.save_sample()
        try:
            rows = self.collect_xrd_rows()
        except ValueError as exc:
            messagebox.showwarning("无法画图", str(exc))
            return
        data_path = self.store.save_xrd_data(self.current_material, self.current_sample_number, rows)
        folder = data_path.parent
        theta_points = [(row[0], row[1]) for row in rows]
        d_points = [(row[2], row[1]) for row in rows]
        d_x_limits = xrd_tools.d_plot_limits(rows)
        self.show_plots()
        theta_canvas_points = xrd_tools.downsample_points(theta_points, MAX_CANVAS_POINTS)
        d_canvas_points = xrd_tools.downsample_points(d_points, MAX_CANVAS_POINTS)
        theta_save_points = xrd_tools.downsample_points(theta_points, MAX_PLOT_POINTS)
        d_save_points = xrd_tools.downsample_points(d_points, MAX_PLOT_POINTS)
        self.plot_configs["2theta"] = {
            "points": theta_canvas_points,
            "title": "XRD: 2theta",
            "xlabel": "2theta (°)",
            "ylabel": "强度",
            "x_limits": (10, 100),
            "x_tick_step": 10,
            "y_limits": None,
            "connect_points": False,
            "smooth_line": False,
            "point_radius": 1.4,
        }
        self.plot_configs["d"] = {
            "points": d_canvas_points,
            "title": "XRD: d",
            "xlabel": "d (Å)",
            "ylabel": "强度",
            "x_limits": d_x_limits,
            "x_tick_step": 1,
            "y_limits": None,
            "connect_points": False,
            "smooth_line": False,
            "point_radius": 1.4,
        }
        draw_scatter_plot(self.plot_2theta, **self.plot_configs["2theta"])
        draw_scatter_plot(self.plot_d, **self.plot_configs["d"])
        try:
            save_scatter_jpg(
                folder / PLOT_2THETA_FILE,
                theta_save_points,
                "XRD: 2theta",
                "2theta (°)",
                "强度",
                (10, 100),
                10,
                y_limits=None,
                connect_points=False,
                smooth_line=False,
                point_radius=1.4,
            )
            save_scatter_jpg(
                folder / PLOT_D_FILE,
                d_save_points,
                "XRD: d",
                "d (Å)",
                "强度",
                d_x_limits,
                1,
                y_limits=None,
                connect_points=False,
                smooth_line=False,
                point_radius=1.4,
            )
        except RuntimeError as exc:
            messagebox.showwarning("JPG 保存失败", str(exc))
            return
        self.set_status(f"已保存 {len(rows)} 行原始 XRD 数据和图：{folder}")

    def plot_processed_xrd_rows(
        self,
        theta_rows: list[tuple[float, float, float]],
        d_rows: list[tuple[float, float, float]],
    ) -> None:
        if not self.current_material or not self.current_sample_number:
            messagebox.showinfo("没有样品", "请先选择或创建一个样品。")
            return
        if len(theta_rows) < 2 and len(d_rows) < 2:
            messagebox.showwarning("无法画图", "处理后 2theta 或 d 数据至少需要一侧包含两行有效数据。")
            return
        self.save_sample()
        theta_source_rows = xrd_tools.finalize_processed_rows(theta_rows if len(theta_rows) >= 2 else d_rows, "theta")
        d_source_rows = xrd_tools.finalize_processed_rows(d_rows if len(d_rows) >= 2 else theta_rows, "d")
        theta_plot_rows = xrd_tools.normalize_processed_rows_for_plot(theta_source_rows, "theta")
        d_plot_rows = xrd_tools.normalize_processed_rows_for_plot(d_source_rows, "d")
        folder = self.store.save_processed_xrd_data(self.current_material, self.current_sample_number, theta_source_rows, d_source_rows)
        self.processed_xrd_theta_text.delete("1.0", END)
        self.processed_xrd_d_text.delete("1.0", END)
        self.processed_xrd_theta_text.insert("1.0", xrd_tools.rows_to_theta_text(theta_source_rows))
        self.processed_xrd_d_text.insert("1.0", xrd_tools.rows_to_d_text(d_source_rows))
        theta_all_points = xrd_tools.processed_curve_points(theta_plot_rows, "theta", MAX_PROCESSED_CANVAS_POINTS)
        d_all_points = xrd_tools.processed_curve_points(d_plot_rows, "d", MAX_PROCESSED_CANVAS_POINTS)
        theta_save_points = xrd_tools.processed_curve_points(theta_plot_rows, "theta", MAX_PROCESSED_PLOT_POINTS)
        d_save_points = xrd_tools.processed_curve_points(d_plot_rows, "d", MAX_PROCESSED_PLOT_POINTS)
        d_x_limits = xrd_tools.d_plot_limits(d_source_rows)
        self.show_processed_plots()
        self.plot_configs["processed_2theta"] = xrd_tools.processed_plot_config(theta_all_points, "theta", MAX_PROCESSED_CANVAS_POINTS)
        self.plot_configs["processed_d"] = xrd_tools.processed_plot_config(d_all_points, "d", MAX_PROCESSED_CANVAS_POINTS, d_x_limits)
        draw_scatter_plot(self.processed_plot_2theta, **self.plot_configs["processed_2theta"])
        draw_scatter_plot(self.processed_plot_d, **self.plot_configs["processed_d"])
        try:
            save_scatter_jpg(
                folder / PROCESSED_PLOT_2THETA_FILE,
                theta_save_points,
                "XRD 处理后: 2theta",
                "2theta (°)",
                "强度",
                (10, 100),
                10,
                y_limits=(0, 100),
                connect_points=True,
                smooth_line=False,
                point_radius=0.0,
            )
            save_scatter_jpg(
                folder / PROCESSED_PLOT_D_FILE,
                d_save_points,
                "XRD 处理后: d",
                "d (Å)",
                "强度",
                d_x_limits,
                1,
                y_limits=(0, 100),
                connect_points=True,
                smooth_line=False,
                point_radius=0.0,
            )
        except RuntimeError as exc:
            messagebox.showwarning("JPG 保存失败", str(exc))
            return
        self.set_status(f"已保存处理后 XRD 数据和 0-100 平滑线图，不覆盖原始 XRD：{folder}")

    def show_plots(self) -> None:
        if not self.plot_panel.winfo_ismapped():
            self.plot_panel.pack(fill=BOTH, expand=True, pady=(10, 0))

    def hide_plots(self) -> None:
        self.plot_panel.pack_forget()
        self.plot_2theta.delete("all")
        self.plot_d.delete("all")
        self.plot_configs.pop("2theta", None)
        self.plot_configs.pop("d", None)

    def show_processed_plots(self) -> None:
        if not self.processed_plot_panel.winfo_ismapped():
            self.processed_plot_panel.pack(fill=BOTH, expand=True, pady=(10, 0))

    def hide_processed_plots(self) -> None:
        self.processed_plot_panel.pack_forget()
        self.processed_plot_2theta.delete("all")
        self.processed_plot_d.delete("all")
        self.plot_configs.pop("processed_2theta", None)
        self.plot_configs.pop("processed_d", None)

    def open_plot_viewer(self, key: str) -> None:
        config = self.plot_configs.get(key)
        if not config:
            label = "温度-热导率图" if key == "thermal" else "XRD 图"
            action = "请先点击“画温度-热导率图”。" if key == "thermal" else "请先根据 XRD 数据画图。"
            messagebox.showinfo("没有图", f"当前没有可放大的{label}。\n\n{action}")
            return
        GenericPlotViewer(self.root, config)

    def clear_editor(self) -> None:
        self.current_sample_number = 0
        self.last_sample_density = ""
        for key, value in self.fields.items():
            value.set(DEFAULT_WAVELENGTH if key == "xrd_wavelength" else "")
        self.notes.delete("1.0", END)
        self.set_thermal_rows([])
        self.set_xrd_rows([])
        self.hide_thermal_plot()
        self.hide_plots()
        self.hide_processed_plots()

    def set_status(self, text: str = "") -> None:
        base = f"数据目录：{self.store.root}"
        self.status.set(f"{text}    {base}" if text else base)


def main() -> None:
    root = Tk()
    try:
        ttk.Style().theme_use("vista")
    except Exception:
        pass
    ExMaterialApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
