# Shared desktop services

XRD, XPS and thermal transport are peer analysis tabs. The material/sample record
is their common context. Keep algorithms independent of Tk; feature controllers
own their widgets and use the services below.

- `settings.py`: immutable application settings, validated loading, atomic saving,
  and `settings_for(widget)`. Settings live in `information/app_settings.json`.
  Add future user preferences here rather than to individual feature windows.
- `theme.py`: application-wide native widget defaults and ttk styles. Call once
  before constructing widgets; child windows inherit defaults automatically.
- `rendering.py`: `DeferredRedraw(widget, callback)` coalesces resize events,
  reads the shared performance policy, observes setting changes, and cancels
  timers/listeners when the widget is destroyed. Bind its `request` to Configure.
- `plot_viewer.py`: common on-screen plotting and independent full-data image
  export. Previews use `canvas_preview`, caching extrema-preserving reductions.
  Treat cached point lists as immutable; replace the list when data changes.
  Comparison-series lists follow the same replacement convention.
- `xps_tools.py`: parsing and calculations without UI state. Processing retains
  raw intensity and background alongside processed intensity. Workspace writes
  replace a temporary file atomically, preserving the previous file on failure.

New analysis modules should provide a pure processing function and the same plot
configuration dictionary (`points`, labels, limits, ticks). Use the shared viewer
and scheduler; never apply preview decimation to scientific computations or exports.
Display quality and compute device are separate shared settings. Optional CuPy CUDA
performs extrema reduction for large previews; Tk drawing and scientific processing
remain on CPU. Capability/runtime failures fall back to CPU. Standard builds do not
bundle CuPy; real CUDA hardware execution has not yet been validated.

XPS controllers capture sample identity when created. Switching samples hides the
previous controller without changing its save destination or losing unsaved edits.
Deletion and application exit consult those controllers before destroying them.

Validation: `python -m pytest -q`, `python -m compileall -q exmaterial`.
Scientific background: [Practical guides for XPS: quantitative XPS](https://pubs.aip.org/avs/jva/article/38/4/041201/246897/Practical-guides-for-x-ray-photoelectron).
The initial XPS implementation intentionally exposes linear background only; a
sampled maximum and a raw integrated area are not chemical-state identification
or sensitivity-corrected composition.
