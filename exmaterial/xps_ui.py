"""Sample-bound XPS workbench; each window keeps its original sample identity."""
import csv
import json
from pathlib import Path
from tkinter import BOTH, END, LEFT, BooleanVar, Canvas, StringVar, Text, Toplevel, ttk
from tkinter import Button, Frame, Label, filedialog, messagebox

try:
    from . import xps_tools, xrd_tools
    from .plot_viewer import draw_scatter_plot, save_scatter_jpg, PlotViewer
    from .rendering import DeferredRedraw
except ImportError:
    import xps_tools
    import xrd_tools
    from plot_viewer import draw_scatter_plot, save_scatter_jpg, PlotViewer
    from rendering import DeferredRedraw


class XpsWindow:
    def __init__(self, parent, folder, title, embedded=False):
        self.folder = Path(folder)
        self.path = self.folder / "xps_workspace.json"
        self.embedded = embedded
        self.window = Frame(parent) if embedded else Toplevel(parent)
        if embedded:
            self.window.pack(fill=BOTH, expand=True)
        else:
            self.window.title(f"XPS · {title}")
            self.window.geometry("1120x800")
            self.window.minsize(860, 620)
        self.source = ""
        self.saved = None
        self.config = None
        header = Frame(self.window, padx=20, pady=14)
        header.pack(fill="x")
        Label(header, text="XPS 工作台", font=("Microsoft YaHei UI", 13, "bold")).pack(side=LEFT)
        Label(header, text=title, fg="#147d78").pack(side=LEFT, padx=20)
        Button(header, text="保存工作区", command=self.save).pack(side="right")
        body = Frame(self.window, padx=20)
        body.pack(fill=BOTH, expand=True)
        controls = Frame(body)
        controls.pack(fill="x")
        Button(controls, text="导入光谱…", command=self.import_file).pack(side=LEFT)
        Label(controls, text="结合能列").pack(side=LEFT, padx=(18, 4))
        self.energy = StringVar(value="1")
        ttk.Entry(controls, textvariable=self.energy, width=4).pack(side=LEFT)
        Label(controls, text="强度列").pack(side=LEFT, padx=(12, 4))
        self.intensity = StringVar(value="2")
        ttk.Entry(controls, textvariable=self.intensity, width=4).pack(side=LEFT)
        Label(body, text="原始数据 · 粘贴或导入单条扫描；多列文本按指定列读取，能量必须为结合能 (eV)。", anchor="w").pack(fill="x", pady=(12, 4))
        text_frame = Frame(body)
        text_frame.pack(fill="x")
        self.raw = Text(text_frame, height=7, wrap="none", undo=True)
        scroll = ttk.Scrollbar(text_frame, command=self.raw.yview)
        scroll.pack(side="right", fill="y")
        self.raw.pack(fill="x", expand=True)
        self.raw.configure(yscrollcommand=scroll.set)
        params = Frame(body, pady=10)
        params.pack(fill="x")
        self.params = {}
        for i, (key, label, default) in enumerate([
            ("shift", "能量平移 ΔE (eV)", "0"), ("lower", "能区下限 (eV)", ""),
            ("upper", "能区上限 (eV)", ""), ("window", "平滑窗口（奇数）", "1")]):
            var = StringVar(value=default)
            self.params[key] = var
            Label(params, text=label).grid(row=0, column=i, sticky="w")
            ttk.Entry(params, textvariable=var, width=18).grid(row=1, column=i, sticky="ew", padx=(0, 12))
            params.columnconfigure(i, weight=1)
        actions = Frame(body)
        actions.pack(fill="x")
        self.background = StringVar(value="无背景扣除")
        ttk.Combobox(actions, textvariable=self.background, values=["无背景扣除", "线性背景"], state="readonly", width=14).pack(side=LEFT)
        self.normalize = BooleanVar(value=False)
        ttk.Checkbutton(actions, text="按最大绝对强度归一化", variable=self.normalize).pack(side=LEFT, padx=12)
        Button(actions, text="处理 / 刷新预览", command=self.process).pack(side=LEFT)
        Button(actions, text="导出 CSV", command=self.export_csv).pack(side="right")
        Button(actions, text="导出 JPG", command=self.export_image).pack(side="right", padx=8)
        self.summary = StringVar(value="导入数据后点击处理。ΔE 加到原始结合能；范围使用校正后的能量。")
        Label(body, textvariable=self.summary, anchor="w").pack(fill="x", pady=10)
        self.canvas = Canvas(body, bg="white", height=300, highlightthickness=0)
        self.canvas.pack(fill=BOTH, expand=True)
        self.redraw = DeferredRedraw(self.canvas, self.draw)
        self.canvas._plot_scheduler = self.redraw
        self.canvas.bind("<Configure>", self.redraw.request)
        self.canvas.bind("<Double-Button-1>", lambda e: self.open_plot())
        Label(body, text="积分：背景扣除后、平滑和归一化前的有符号面积。峰位为采样最大值；不作化学态归属或原子百分比定量。", anchor="w").pack(fill="x", pady=10)
        if not embedded:
            self.window.protocol("WM_DELETE_WINDOW", self.close)
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if data.get("version") != 1 or not isinstance(data.get("raw_text"), str):
                    raise ValueError("不支持的工作区格式")
                self.raw.insert("1.0", data["raw_text"])
                self.source = data.get("source", "")
                self.energy.set(data.get("energy_column", "1"))
                self.intensity.set(data.get("intensity_column", "2"))
                for key, var in self.params.items():
                    var.set(data.get("parameters", {}).get(key, var.get()))
                self.background.set(data.get("background", "无背景扣除"))
                self.normalize.set(data.get("normalize", False))
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                messagebox.showerror("读取 XPS 失败", str(exc), parent=self.window)
                self.window.destroy()
                return
        self.saved = self.payload()
        if self.raw.get("1.0", "end-1c").strip():
            self.process()

    def payload(self):
        return dict(version=1, raw_text=self.raw.get("1.0", "end-1c"), source=self.source,
                    energy_column=self.energy.get(), intensity_column=self.intensity.get(),
                    parameters={k: v.get() for k, v in self.params.items()},
                    background=self.background.get(), normalize=self.normalize.get())

    def import_file(self):
        path = filedialog.askopenfilename(parent=self.window, filetypes=[("光谱文本", "*.txt *.csv *.tsv *.xy *.dat")])
        if not path:
            return
        try:
            text = xrd_tools.read_xrd_file(Path(path))
            xps_tools.parse_spectrum(text, int(self.energy.get()), int(self.intensity.get()))
            if self.payload() != self.saved and not messagebox.askyesno("替换光谱", "放弃当前未保存的 XPS 编辑并导入？", parent=self.window):
                return
            self.raw.delete("1.0", END)
            self.raw.insert("1.0", text)
            self.source = Path(path).name
            for key, value in {"shift": "0", "lower": "", "upper": "", "window": "1"}.items():
                self.params[key].set(value)
            self.background.set("无背景扣除")
            self.normalize.set(False)
            self.process()
        except (OSError, ValueError) as exc:
            messagebox.showerror("导入失败", str(exc), parent=self.window)

    def process(self):
        try:
            points, skipped = xps_tools.parse_spectrum(self.raw.get("1.0", END), int(self.energy.get()), int(self.intensity.get()))
            values = {k: (float(v.get()) if v.get().strip() else None) for k, v in self.params.items() if k != "window"}
            values["shift"] = values["shift"] or 0.0
            result = xps_tools.process_spectrum(points, **values, window=int(self.params["window"].get()),
                                                background="linear" if self.background.get() == "线性背景" else "none",
                                                normalize=self.normalize.get())
            self.config = xps_tools.plot_config(result, self.normalize.get())
            self.draw()
            self.summary.set(f"{len(result['rows'])} 点 · 跳过 {skipped} 行 · 最大值位置 {result['maximum_energy']:.5g} eV · 积分 {result['area']:.6g} (输入强度 × eV)")
            return result
        except (ValueError, OverflowError) as exc:
            self.config = None
            self.canvas.delete("all")
            self.summary.set("处理失败，请检查数据和参数。")
            messagebox.showerror("无法处理 XPS", str(exc), parent=self.window)
            return None

    def draw(self):
        if self.config:
            draw_scatter_plot(self.canvas, **self.config)

    def open_plot(self):
        if self.process() is not None:
            PlotViewer(self.window, self.config)

    def save(self):
        result = self.process()
        if result is None:
            return False
        try:
            payload = self.payload()
            xps_tools.save_workspace(self.path, {**payload, "processed": result})
            self.saved = payload
            self.summary.set(f"已保存原始数据、处理参数和结果 · {self.path.name}")
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror("保存失败", str(exc), parent=self.window)
            return False

    def export_csv(self):
        result = self.process()
        if result is None:
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".csv", initialfile="xps_processed.csv")
        if path:
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(["binding_energy_eV", "raw_intensity", "background", "processed_intensity"])
                    writer.writerows(result["rows"])
            except OSError as exc:
                messagebox.showerror("导出失败", str(exc), parent=self.window)

    def export_image(self):
        if self.process() is None:
            return
        path = filedialog.asksaveasfilename(parent=self.window, defaultextension=".jpg", initialfile="xps.jpg")
        if path:
            try:
                save_scatter_jpg(Path(path), **self.config)
            except (OSError, RuntimeError) as exc:
                messagebox.showerror("导出失败", str(exc), parent=self.window)

    def close(self):
        if self.payload() != self.saved:
            answer = messagebox.askyesnocancel("未保存的 XPS", "保存当前 XPS 工作区后关闭？", parent=self.window)
            if answer is None or (answer and not self.save()):
                return
        self.window.destroy()
