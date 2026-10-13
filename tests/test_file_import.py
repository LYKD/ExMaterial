from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tkinterdnd2 import COPY, REFUSE_DROP, TkinterDnD

from exmaterial import exmaterial_app, xrd_tools


class XrdFileTests(unittest.TestCase):
    def test_text_encodings_and_quoted_csv_values(self):
        with tempfile.TemporaryDirectory() as folder:
            for encoding in ("utf-8-sig", "utf-16", "gb18030"):
                path = Path(folder) / "样品 数据.CSV"
                path.write_text('样品信息\nX-Ray 40kV/15mA\n"10","100"\n"20","50"', encoding=encoding)
                rows, skipped = xrd_tools.parse_xrd_text(xrd_tools.read_xrd_file(path), "1.5406")
                self.assertEqual(skipped, 2)
                self.assertEqual([(x, y) for x, y, _d in rows], [(10, 100), (20, 50)])

    def test_binary_instrument_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            for suffix in (".raw", ".txt"):
                path = Path(folder) / ("scan" + suffix)
                path.write_bytes(b"10 100\x00\n20 50")
                with self.assertRaises(ValueError):
                    xrd_tools.read_xrd_file(path)


class FileDropTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = TkinterDnD.Tk()
        cls.root.withdraw()
        cls.addClassCleanup(cls.root.destroy)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.directory_patch = patch.object(exmaterial_app, "information_dir", return_value=self.folder / "information")
        self.directory_patch.start()
        self.addCleanup(self.directory_patch.stop)
        self.addCleanup(self.clear_window)
        self.app = exmaterial_app.ExMaterialApp(self.root)
        self.app.store.create_material("carbon")
        self.app.current_material = "carbon"

    def clear_window(self):
        for callback in self.root.tk.call("after", "info"):
            self.root.after_cancel(callback)
        for widget in self.root.winfo_children():
            widget.destroy()

    def file(self, name, text="X-Ray 40kV/15mA\n10 100\n20 50"):
        path = self.folder / name
        path.write_text(text, encoding="utf-8-sig")
        return path

    def drop(self, paths, axis="theta"):
        # Tcl list handling is the same for native drops, including spaces/braces.
        data = self.root.tk.call("list", *(str(path) for path in paths))
        return self.app.on_xrd_file_drop(SimpleNamespace(data=data), axis)

    def test_multiple_files_create_samples_with_original_filenames_in_notes(self):
        paths = [self.file("中文 样品 {1}.TXT"), self.file("sample 2.csv")]
        originals = [path.read_bytes() for path in paths]
        self.assertEqual(self.drop(paths), COPY)
        samples = self.app.store.load_samples("carbon")
        self.assertEqual([sample.number for sample in samples], [1, 2])
        for sample, path in zip(samples, paths):
            self.assertEqual(sample.notes, f"XRD 来源文件：{path.name}")
            self.assertEqual(self.app.store.load_xrd_data("carbon", sample.number), [("10.0", "100.0"), ("20.0", "50.0")])
        self.assertEqual([path.read_bytes() for path in paths], originals)
        self.assertIn(paths[0].name, self.app.notes.get("1.0", "end"))

    def test_import_preserves_existing_sample_and_unsaved_editor(self):
        sample = self.app.store.add_sample("carbon")
        sample.notes = "Saved notes"
        self.app.store.update_sample("carbon", sample)
        self.app.store.save_xrd_data("carbon", sample.number, [(30, 150, 3), (40, 200, 2)])
        self.app.load_sample(sample)
        self.app.notes.insert("end", " unsaved edit")
        self.app.xrd_theta_text.insert("end", "\n50 250")
        notes = self.app.notes.get("1.0", "end")
        raw_text = self.app.xrd_theta_text_value()
        saved = (self.app.store.sample_dir("carbon", 1) / "xrd_data.csv").read_bytes()
        self.assertEqual(self.drop([self.file("new.txt")]), COPY)
        self.assertEqual(self.app.current_sample_number, 1)
        self.assertEqual(self.app.notes.get("1.0", "end"), notes)
        self.assertEqual(self.app.xrd_theta_text_value(), raw_text)
        self.assertEqual((self.app.store.sample_dir("carbon", 1) / "xrd_data.csv").read_bytes(), saved)
        self.assertEqual(self.app.store.load_samples("carbon")[0].notes, "Saved notes")

    def test_invalid_files_do_not_create_empty_samples_or_block_valid_files(self):
        bad = self.file("invalid.txt", "X-Ray 40kV/15mA")
        with patch.object(exmaterial_app.messagebox, "showwarning") as warning:
            self.assertEqual(self.drop([bad, self.file("valid.txt")]), COPY)
        self.assertEqual(len(self.app.store.load_samples("carbon")), 1)
        self.assertIn(bad.name, warning.call_args.args[1])

    def test_drop_into_d_input_uses_d_coordinate_and_current_columns(self):
        self.app.fields["xrd_wavelength"].set("1.0")
        self.app.theta_column.set("2")
        self.app.intensity_column.set("3")
        self.assertEqual(self.drop([self.file("d.txt", "1 4 100\n2 2 50")], "d"), COPY)
        path = self.app.store.sample_dir("carbon", 1) / "xrd_data.csv"
        rows = xrd_tools.load_xrd_csv(path)
        self.assertEqual([(d, y) for _x, y, d in rows], [(4, 100), (2, 50)])
        self.assertAlmostEqual(rows[0][0], xrd_tools.d_to_theta(4, 1.0))
        self.assertEqual(self.app.store.load_samples("carbon")[0].xrd_wavelength, "1.0")

    def test_missing_material_refuses_drop_without_creating_data(self):
        self.app.current_material = ""
        with patch.object(exmaterial_app.messagebox, "showinfo"):
            self.assertEqual(self.drop([self.file("scan.txt")]), REFUSE_DROP)
        self.assertEqual(self.app.store.load_samples("carbon"), [])

    def test_windows_drop_dispatch_reaches_main_window_and_d_input(self):
        if self.root.tk.call("tk", "windowingsystem") != "win32":
            self.skipTest("Windows TkDnD protocol")
        for target, path in (
            (self.app.notes, self.file("窗口 样品.txt")),
            (self.app.xrd_d_text, self.file("d 样品.txt", "4 100\n2 50")),
        ):
            data = self.root.tk.call("list", str(path))
            self.root.tk.call("tkdnd::olednd::HandleDragEnter", str(target),
                              ("CF_HDROP",), (COPY,), (), 0, 0, ("CF_HDROP",), data)
            action = self.root.tk.call("tkdnd::olednd::HandleDrop", str(target), (), 0, 0, "CF_HDROP", data)
            self.assertEqual(action, COPY)
        self.assertEqual(len(self.app.store.load_samples("carbon")), 2)
        rows = xrd_tools.load_xrd_csv(self.app.store.sample_dir("carbon", 2) / "xrd_data.csv")
        self.assertEqual([(d, y) for _x, y, d in rows], [(4, 100), (2, 50)])
