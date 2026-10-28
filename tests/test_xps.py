import json
from unittest.mock import patch

import pytest

from exmaterial import xps_tools
from exmaterial.rendering import DeferredRedraw, preview_points


def test_parse_descending_metadata_and_custom_columns():
    points, skipped = xps_tools.parse_spectrum('X-Ray 1486.6 eV\n1,286,10\n2,285,30\n3,284,20', 2, 3)
    assert points == [(284, 20), (285, 30), (286, 10)]
    assert skipped == 1
    with pytest.raises(ValueError):
        xps_tools.parse_spectrum('284 1\n284 2\n285 3')


def test_shift_background_signed_area_and_normalization():
    points = [(0, 2), (1, 5), (2, 4)]
    result = xps_tools.process_spectrum(points, shift=284, background='linear', normalize=True)
    assert result['rows'] == [(284, 2, 2, 0), (285, 5, 3, 1), (286, 4, 4, 0)]
    assert result['area'] == 2
    assert result['maximum_energy'] == 285
    assert xps_tools.plot_config(result)['x_limits'] == (286, 284)
    assert points == [(0, 2), (1, 5), (2, 4)]
    negative = xps_tools.process_spectrum([(0, 2), (1, 0), (3, 2)], background='linear')
    assert negative['area'] == -3


@pytest.mark.parametrize('kwargs', [{'shift': float('nan')}, {'window': 2}, {'window': 5},
                                    {'lower': 2, 'upper': 1}, {'background': 'invalid'}])
def test_invalid_processing(kwargs):
    with pytest.raises(ValueError):
        xps_tools.process_spectrum([(0, 1), (1, 2), (2, 1)], **kwargs)


def test_atomic_workspace_preserves_existing_on_failure(tmp_path):
    path = tmp_path / 'xps.json'
    xps_tools.save_workspace(path, {'raw_text': 'original'})
    with patch.object(xps_tools.os, 'replace', side_effect=OSError('disk failure')):
        with pytest.raises(OSError):
            xps_tools.save_workspace(path, {'raw_text': 'new'})
    assert json.loads(path.read_text())['raw_text'] == 'original'
    assert list(tmp_path.iterdir()) == [path]


def test_preview_retains_narrow_peak_and_extrema():
    points = [(x, 100 if x == 4123 else (-50 if x == 4124 else 0)) for x in range(100000)]
    reduced = preview_points(points)
    assert len(reduced) <= 1600
    assert points[4123] in reduced and points[4124] in reduced
    assert reduced[0] == points[0] and reduced[-1] == points[-1]


def test_resize_events_coalesce_and_cancel(native_tk_root):
    from tkinter import Canvas
    canvas = Canvas(native_tk_root)
    scheduler = DeferredRedraw(canvas, lambda: None)
    for _ in range(100):
        scheduler.request()
    pending = scheduler.pending
    assert pending in native_tk_root.tk.call('after', 'info')
    canvas.destroy()
    assert pending not in native_tk_root.tk.call('after', 'info')


def test_workbench_roundtrip_and_sample_identity(native_tk_root, tmp_path):
    from exmaterial.xps_ui import XpsWindow
    workspace = XpsWindow(native_tk_root, tmp_path / 'sample_1', 'sample 1')
    workspace.raw.insert('1.0', '284 10\n285 30\n286 10')
    workspace.params['shift'].set('0.5')
    assert workspace.save()
    workspace.window.destroy()
    reopened = XpsWindow(native_tk_root, tmp_path / 'sample_1', 'sample 1')
    assert reopened.params['shift'].get() == '0.5'
    assert reopened.process()['maximum_energy'] == 285.5
    assert reopened.config['x_limits'] == (286.5, 284.5)
    reopened.close()


def test_settings_roundtrip_and_bad_file_fallback(tmp_path):
    from exmaterial.settings import AppSettings, load_settings, save_settings
    path = tmp_path / 'settings.json'
    save_settings(path, AppSettings('精细'))
    assert load_settings(path).preview_limit == 6000
    path.write_text('{broken', encoding='utf-8')
    assert load_settings(path).preview_limit == 1600


def test_equal_tabs_preserve_unsaved_xps_on_sample_switch(native_tk_root, tmp_path):
    from exmaterial import exmaterial_app
    with patch.object(exmaterial_app, 'information_dir', return_value=tmp_path):
        app = exmaterial_app.ExMaterialApp(native_tk_root)
        app.store.create_material('demo')
        app.current_material = 'demo'
        first = app.store.add_sample('demo')
        second = app.store.add_sample('demo')
        app.load_sample(first)
        app.open_xps()
        workbench = app.xps_windows[('demo', first.number)]
        workbench.raw.insert('1.0', '284 10\n285 30\n286 10')
        app.load_sample(second)
        assert app.xps_windows[('demo', second.number)].raw.get('1.0', 'end-1c') == ''
        app.load_sample(first)
        assert workbench.raw.get('1.0', 'end-1c') == '284 10\n285 30\n286 10'
        assert len(app.analysis_tabs.tabs()) == 3
        app.plot_quality.set('精细')
        app.change_plot_quality()
        assert native_tk_root.app_settings.preview_limit == 6000
    for timer in native_tk_root.tk.call('after', 'info'):
        native_tk_root.after_cancel(timer)
    for child in native_tk_root.winfo_children():
        child.destroy()
