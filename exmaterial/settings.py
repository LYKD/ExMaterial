"""Shared application policy. New modules consume settings, not widget-local flags."""
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile


@dataclass(frozen=True)
class AppSettings:
    plot_quality: str = "流畅"
    compute_device: str = "CPU"

    @property
    def preview_limit(self):
        return 1600 if self.plot_quality == "流畅" else 6000

    @property
    def redraw_delay_ms(self):
        return 70 if self.plot_quality == "流畅" else 35


def load_settings(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        quality = data.get("plot_quality", "流畅")
        device = data.get("compute_device", "CPU")
        return AppSettings(quality if quality in {"流畅", "精细"} else "流畅",
                           device if device in {"CPU", "GPU"} else "CPU")
    except (OSError, ValueError, TypeError, AttributeError):
        return AppSettings()


def save_settings(path: Path, settings: AppSettings):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = stream.name
            json.dump({"version": 1, **asdict(settings)}, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def settings_for(widget):
    root = widget._root() if hasattr(widget, "_root") else widget
    return getattr(root, "app_settings", AppSettings())
