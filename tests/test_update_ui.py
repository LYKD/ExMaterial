from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from exmaterial import update_ui, updates


@unittest.skipUnless(sys.platform == "win32", "Windows Tk update interface")
@pytest.mark.usefixtures("tk_root")
class UpdateUiTests(unittest.TestCase):
    def setUp(self):
        self.notify = Mock()
        self.manager = update_ui.UpdateManager(self.root, "1.0.3", notify=self.notify)
        self.release = updates.Release(
            "1.2.0", updates.RELEASES_URL, "Release notes", "https://github.com/LYKD/ExMaterial/releases/download/v1.2.0/ExMaterial.exe", 10, "0" * 64
        )
        self.manual_release = updates.Release("1.2.0", updates.RELEASES_URL, "Release notes")

    def tearDown(self):
        for callback in self.root.tk.call("after", "info"):
            self.root.after_cancel(callback)
        for widget in self.root.winfo_children():
            widget.destroy()

    def checked(self, release, *, manual, frozen):
        with patch.object(updates.sys, "frozen", frozen, create=True):
            self.manager.events.put(("checked", release, manual))
            self.manager.poll()
            self.root.update_idletasks()

    def widgets(self, parent):
        for child in parent.winfo_children():
            yield child
            yield from self.widgets(child)

    def button_texts(self):
        return [widget.cget("text") for widget in self.widgets(self.manager.window) if isinstance(widget, tk.Button)]

    def assert_manual_controls(self):
        self.assertEqual(self.button_texts(), ["查看发布页", "稍后"])
        self.assertFalse(any(isinstance(widget, update_ui.ttk.Progressbar) for widget in self.widgets(self.manager.window)))

    def test_source_background_check_notifies_without_opening_window(self):
        self.checked(self.release, manual=False, frozen=False)
        self.assertIsNone(self.manager.window)
        self.notify.assert_called_once()
        self.assertIn("git pull", self.notify.call_args.args[0])

    def test_source_manual_check_shows_instructions_without_dead_controls(self):
        self.checked(self.manual_release, manual=True, frozen=False)
        self.assert_manual_controls()
        self.assertIn("git pull", self.manager.status.cget("text"))
        self.notify.assert_not_called()
        self.manager.close()
        self.assertIsNone(self.manager.window)

    def test_exe_background_check_keeps_install_controls(self):
        self.checked(self.release, manual=False, frozen=True)
        self.assertIn("下载并重启更新", self.button_texts())
        self.assertEqual(self.manager.install_button.cget("state"), "normal")
        self.assertTrue(self.manager.progress.winfo_exists())
        self.notify.assert_not_called()

    def test_unverifiable_exe_manual_check_shows_only_manual_controls(self):
        self.checked(self.manual_release, manual=True, frozen=True)
        self.assert_manual_controls()
        self.assertEqual(self.manager.status.cget("text"), updates.NO_PACKAGE_UPDATE_HINT)

    def test_unverifiable_exe_background_check_only_notifies(self):
        self.checked(self.manual_release, manual=False, frozen=True)
        self.assertIsNone(self.manager.window)
        self.notify.assert_called_once()

    def test_exe_download_progress_and_restart_dispatch_remain_functional(self):
        self.checked(self.release, manual=True, frozen=True)
        payload = Path("test-download.exe")
        self.manager.busy = True
        self.manager.events.put(("progress", 5, 10))
        self.manager.events.put(("downloaded", payload, None))
        with patch.object(self.manager, "restart") as restart:
            self.manager.poll()
        self.assertEqual(float(self.manager.progress["value"]), 50.0)
        self.assertEqual(self.manager.payload, payload)
        self.assertFalse(self.manager.busy)
        self.assertEqual(self.manager.install_button.cget("text"), "重启并更新")
        restart.assert_called_once()
        self.manager.payload = None
