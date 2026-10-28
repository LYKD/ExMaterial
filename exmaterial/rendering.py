"""Coalesced resize redraws and peak-preserving preview reduction."""
import math
from functools import lru_cache

try:
    from .settings import settings_for
except ImportError:
    from settings import settings_for


class DeferredRedraw:
    def __init__(self, widget, callback, delay=None):
        self.widget, self.callback, self.delay = widget, callback, delay
        self.pending = None
        widget.bind("<Destroy>", self.cancel, add="+")
        self.root = widget._root()
        self.settings_binding = self.root.bind("<<PlotSettingsChanged>>", self.request, add="+")

    def request(self, event=None):
        # One pending frame, even if Windows sends many resize events.
        if self.pending is None:
            self.pending = self.widget.after(self.delay or settings_for(self.widget).redraw_delay_ms, self.run)

    def run(self):
        self.pending = None
        if self.widget.winfo_exists():
            self.callback()

    def cancel(self, event=None):
        if event is not None and event.widget != self.widget:
            return
        if self.pending is not None:
            self.widget.after_cancel(self.pending)
            self.pending = None
        if self.settings_binding:
            self.root.unbind("<<PlotSettingsChanged>>", self.settings_binding)
            self.settings_binding = None


@lru_cache(maxsize=1)
def require_gpu():
    try:
        import cupy as cp
        if cp.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("未检测到 CUDA GPU")
        # Exercise a kernel, not just the driver, before accepting the device.
        cp.arange(8).sum().item()
        return cp
    except Exception as exc:
        raise RuntimeError(f"需要可用的 NVIDIA CUDA GPU 和 CuPy：{exc}") from exc


def gpu_preview_points(points, limit):
    cp = require_gpu()
    size = max(1, math.ceil(len(points) / max(1, limit // 4)))
    count = len(points) // size
    values = cp.asarray(points[:count * size], dtype=cp.float64).reshape(count, size, 2)
    if not bool(cp.isfinite(values).all()):
        return preview_points(points, limit)  # Preserve gap sentinels exactly.
    starts = cp.arange(count) * size
    indices = cp.stack((starts, starts + size - 1,
                        starts + values[:, :, 1].argmin(axis=1),
                        starts + values[:, :, 1].argmax(axis=1)), axis=1)
    selected = cp.asnumpy(cp.unique(indices)).tolist()
    tail = points[count * size:]
    if tail and all(math.isfinite(x) and math.isfinite(y) for x, y in tail):
        indices = {0, len(tail) - 1, min(range(len(tail)), key=lambda i: tail[i][1]),
                   max(range(len(tail)), key=lambda i: tail[i][1])}
        tail = [tail[i] for i in sorted(indices)]
    return [points[i] for i in selected] + tail


def device_preview(widget, points, limit):
    if settings_for(widget).compute_device == "GPU" and len(points) > limit:
        try:
            return gpu_preview_points(points, limit)
        except Exception as exc:
            from tkinter import messagebox
            from dataclasses import replace
            root = widget._root()
            root.app_settings = replace(root.app_settings, compute_device="CPU")
            root.event_generate("<<ComputeDeviceFallback>>", when="tail")
            messagebox.showwarning("GPU 已回退 CPU", str(exc), parent=root)
    return preview_points(points, limit)


def preview_points(points, limit=1600):
    """Retain extrema in each bucket, including endpoints and gap sentinels."""
    if len(points) <= limit:
        return points
    size = max(1, math.ceil(len(points) / max(1, limit // 4)))
    result = []
    for start in range(0, len(points), size):
        bucket = points[start:start + size]
        finite = [i for i, (x, y) in enumerate(bucket) if math.isfinite(x) and math.isfinite(y)]
        if len(finite) != len(bucket):
            # Preserve gaps exactly rather than drawing a line across missing data.
            result.extend(bucket)
            continue
        indices = {0, len(bucket) - 1, min(finite, key=lambda i: bucket[i][1]), max(finite, key=lambda i: bucket[i][1])}
        result.extend(bucket[i] for i in sorted(indices))
    return result


def canvas_preview(canvas, points):
    settings = settings_for(canvas)
    limit = settings.preview_limit
    key = (limit, settings.compute_device)
    cache = getattr(canvas, "_preview_cache", None)
    if cache is not None and cache[0] is points and cache[1] == key:
        return cache[2]
    reduced = device_preview(canvas, points, limit)
    canvas._preview_cache = (points, key, reduced)
    return reduced
