import json
from unittest.mock import patch

import pytest

from exmaterial import exmaterial_app as app_module, rendering
from exmaterial.comparison import SampleCompareWindow, chart_geometry, load_xps_comparison
from exmaterial.settings import AppSettings, load_settings, save_settings


def test_legacy_location_and_manual_choice(tmp_path):
    base = tmp_path / "program"
    base.mkdir()
    (tmp_path / "information").mkdir()
    data = base / "information" / "carbon"
    data.mkdir(parents=True)
    (data / "samples.json").write_text("[]")
    with patch.object(app_module, "app_dir", return_value=base):
        assert app_module.information_dir() == data.parent
        (base / "data_location.json").write_text(json.dumps({"path": str(tmp_path / "information")}))
        assert app_module.information_dir() == tmp_path / "information"


def test_legacy_bom_wrapper_thermal_and_backup(tmp_path):
    with patch.object(app_module, "information_dir", return_value=tmp_path):
        store = app_module.MaterialStore()
    folder = tmp_path / "old"
    folder.mkdir()
    source = folder / "samples.json"
    source.write_text(json.dumps({"samples": [{"number": 1, "obtained_at": "2020-03-04 12:00",
                                             "density": "2", "heat_capacity": "3", "thermal_diffusivity": "4",
                                             "thermal_temperature_c": "25"}]}), encoding="utf-8-sig")
    before = source.read_bytes()
    sample, = store.load_samples("old", strict=True)
    assert sample.obtained_year == "2020"
    assert sample.thermal_rows[0]["thermal_conductivity"] == "24"
    store.save_samples("old", [sample])
    assert (folder / "samples.before-upgrade.json.bak").read_bytes() == before
    assert store.load_samples("old")[0].thermal_rows == sample.thermal_rows


def test_gpu_reduction_matches_cpu_with_extrema_and_tail():
    # Array backend emulation checks indexing and ordering without CUDA hardware.
    np = pytest.importorskip("numpy")
    points = [(float(i), float((i * 137) % 97)) for i in range(10003)]
    with patch.object(rendering, "require_gpu", return_value=np), patch.object(np, "asnumpy", side_effect=lambda v: v, create=True):
        assert rendering.gpu_preview_points(points, 1600) == rendering.preview_points(points, 1600)


def test_device_settings_persist(tmp_path):
    path = tmp_path / "settings.json"
    save_settings(path, AppSettings("精细", "GPU"))
    assert load_settings(path) == AppSettings("精细", "GPU")


def test_runtime_fallback_persists_cpu_choice(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    controller = SimpleNamespace(
        compute_device=Mock(), root=SimpleNamespace(app_settings=AppSettings("精细", "CPU")),
        settings_path=tmp_path / "settings.json", set_status=Mock())
    app_module.ExMaterialApp.on_compute_fallback(controller)
    controller.compute_device.set.assert_called_once_with("CPU")
    assert load_settings(controller.settings_path) == AppSettings("精细", "CPU")


def test_bad_database_cannot_be_overwritten_by_add(tmp_path):
    with patch.object(app_module, "information_dir", return_value=tmp_path):
        store = app_module.MaterialStore()
    folder = tmp_path / "damaged"
    folder.mkdir()
    source = folder / "samples.json"
    source.write_text('{broken', encoding="utf-8")
    with patch.object(app_module.messagebox, "showerror"), pytest.raises(ValueError):
        store.add_sample("damaged")
    assert source.read_text() == '{broken'


def test_gpu_runtime_failure_switches_to_cpu(native_tk_root):
    native_tk_root.app_settings = AppSettings("流畅", "GPU")
    points = [(float(i), float(i % 11)) for i in range(2000)]
    with patch.object(rendering, "gpu_preview_points", side_effect=RuntimeError("device lost")), \
            patch("tkinter.messagebox.showwarning") as warning:
        actual = rendering.device_preview(native_tk_root, points, 1600)
    assert actual == rendering.preview_points(points, 1600)
    assert native_tk_root.app_settings.compute_device == "CPU"
    warning.assert_called_once()


def test_three_comparison_modes(native_tk_root, tmp_path):
    native_tk_root.app_settings = AppSettings()
    with patch.object(app_module, "information_dir", return_value=tmp_path):
        store = app_module.MaterialStore()
    store.create_material("demo")
    for i in range(2):
        sample = store.add_sample("demo")
        sample.thermal_rows = [{"temperature_c": "25", "thermal_conductivity": str(i + 1)},
                               {"temperature_c": "100", "thermal_conductivity": str(i + 2)}]
        store.update_sample("demo", sample)
        store.save_xrd_data("demo", sample.number, [(20, 100, 4), (40, 50, 2)])
        path = store.sample_dir("demo", sample.number) / "xps_workspace.json"
        path.write_text(json.dumps({"raw_text": "284 10\n285 30\n286 10", "parameters": {"shift": "1"}}))
        assert load_xps_comparison(path)[0][0][0] == 285
    window = SampleCompareWindow(native_tk_root, store)
    try:
        for kind in window.kinds:
            window.kind.set(kind)
            window.kind_changed()
            assert len(window.items) == 2
            window.selected_items = list(window.items)
            window.generate()
            assert len(window.series) == 2
            if kind == "XPS":
                assert chart_geometry(window.series, kind)[0] == (287, 285)
            if kind == "热导率":
                assert window.series[1]["points"] == [(25., 2.), (100., 3.)]
            with patch("exmaterial.comparison.filedialog.asksaveasfilename", return_value=str(tmp_path / f"{kind}.csv")):
                window.export_csv()
            assert (tmp_path / f"{kind}.csv").is_file()
            if kind != "XRD":
                with patch("exmaterial.comparison.filedialog.asksaveasfilename", return_value=str(tmp_path / f"{kind}.jpg")):
                    window.save()
                assert (tmp_path / f"{kind}.jpg").stat().st_size > 1000
    finally:
        window.window.destroy()
