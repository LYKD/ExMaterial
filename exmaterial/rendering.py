"""Coalesced resize redraws and peak-preserving preview reduction."""
import math

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
    limit = settings_for(canvas).preview_limit
    cache = getattr(canvas, "_preview_cache", None)
    if cache is not None and cache[0] is points and cache[1] == limit:
        return cache[2]
    reduced = preview_points(points, limit)
    canvas._preview_cache = (points, limit, reduced)
    return reduced
