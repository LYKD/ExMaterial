from __future__ import annotations

import base64
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from pathlib import Path
from unittest.mock import patch

from exmaterial import updates


def release_data(version="1.2.0", payload=b"MZexample executable"):
    name = f"ExMaterial-{version}-windows-x64.exe"
    return {
        "tag_name": "v" + version, "draft": False, "prerelease": False, "body": "Changes",
        "assets": [{"name": name, "state": "uploaded", "size": len(payload),
                    "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
                    "browser_download_url": f"https://github.com/LYKD/ExMaterial/releases/download/v{version}/{name}"}],
    }


class UpdateTests(unittest.TestCase):
    def test_versions_are_numeric_and_never_downgrade(self):
        self.assertIsNotNone(updates.release_from_json(release_data("1.10.0"), "1.9.0"))
        self.assertIsNone(updates.release_from_json(release_data(), "1.2.0"))
        self.assertIsNone(updates.release_from_json(release_data(), "2.0.0"))
        data = release_data()
        data["prerelease"] = True
        self.assertIsNone(updates.release_from_json(data, "1.0.0"))

    def test_untrusted_or_unverifiable_assets_cannot_install(self):
        for field, bad_value in (("digest", None), ("size", 0), ("size", updates.MAX_DOWNLOAD_SIZE + 1),
                                 ("browser_download_url", "https://github.com.attacker.test/update.exe"),
                                 ("browser_download_url", "https://github.com/other/repo/update.exe")):
            data = release_data()
            data["assets"][0][field] = bad_value
            self.assertFalse(updates.release_from_json(data, "1.0.0").can_install)

    def test_verified_download_and_corrupt_download_cleanup(self):
        payload = b"MZexample executable"
        release = updates.release_from_json(release_data(payload=payload), "1.0.0")
        with patch.object(updates, "urlopen", return_value=io.BytesIO(payload)):
            downloaded = updates.download_release(release)
        try:
            self.assertEqual(downloaded.read_bytes(), payload)
        finally:
            shutil.rmtree(downloaded.parent)
        with tempfile.TemporaryDirectory(prefix="exmaterial-update-") as folder:
            stage = Path(folder) / "exmaterial-update-bad"
            stage.mkdir()
            with patch.object(updates.tempfile, "mkdtemp", return_value=str(stage)), \
                    patch.object(updates, "urlopen", return_value=io.BytesIO(b"MZwrong")):
                with self.assertRaises(updates.UpdateError):
                    updates.download_release(release)
            self.assertFalse(stage.exists())

    def test_download_refuses_hash_mismatch_at_correct_size(self):
        release = updates.release_from_json(release_data(), "1.0.0")
        with patch.object(updates, "urlopen", return_value=io.BytesIO(b"MZ" + b"x" * (release.size - 2))):
            with self.assertRaisesRegex(updates.UpdateError, "校验"):
                updates.download_release(release)

    def test_startup_acknowledgement_only_writes_private_temp_marker(self):
        with tempfile.TemporaryDirectory(prefix="exmaterial-update-") as folder:
            marker = Path(folder) / "ready"
            updates.confirm_update_startup(["--update-ready", str(marker)])
            self.assertEqual(marker.read_text(), "ready")
            other = Path(folder) / "other"
            updates.confirm_update_startup(["--update-ready", str(other)])
            self.assertFalse(other.exists())

    def test_source_edition_cannot_replace_python_executable(self):
        with patch.object(updates.sys, "frozen", False, create=True):
            with self.assertRaises(updates.UpdateError):
                updates.launch_installer(Path("unused.exe"), "0" * 64)

    def test_rate_limit_has_actionable_message(self):
        error = HTTPError(updates.API_URL, 403, "rate limit exceeded", {}, None)
        with patch.object(updates, "urlopen", side_effect=error):
            with self.assertRaisesRegex(updates.UpdateError, "检查频率"):
                updates.check_latest("1.0.0")

    def test_release_api_response_is_parsed(self):
        response = io.BytesIO(json.dumps(release_data()).encode("utf-8"))
        with patch.object(updates, "urlopen", return_value=response) as request:
            self.assertEqual(updates.check_latest("1.0.1").version, "1.2.0")
            self.assertEqual(request.call_args.args[0].full_url, updates.API_URL)

    def test_payload_changed_after_download_cannot_be_installed(self):
        with tempfile.TemporaryDirectory(prefix="exmaterial-update-") as folder:
            target = Path(folder) / "current.exe"
            target.write_bytes(b"MZcurrent")
            payload = Path(folder) / "ExMaterial-update.exe"
            payload.write_bytes(b"MZmodified")
            with self.assertRaisesRegex(updates.UpdateError, "校验"):
                updates.installer_script(target, payload, 1, "0" * 64)


@unittest.skipUnless(sys.platform == "win32" and shutil.which("powershell.exe"), "Windows replacement integration")
class WindowsReplacementTests(unittest.TestCase):
    def test_real_helper_replaces_restarts_and_rolls_back(self):
        # Test-created executables only; never touches the installed application.
        cache = Path(__file__).resolve().parents[1] / ".pytest_cache"
        cache.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="ExMaterial 用户 ' & ", dir=cache) as folder:
            parent = Path(folder)
            records = parent / "information"
            records.mkdir()
            sentinel = records / "samples.json"
            sentinel.write_text('user data', encoding="utf-8")
            target = parent / "ExMaterial 用户 ' & sample.exe"
            code = r'''using System; using System.IO; class Stub {
                public static void Main(string[] args) {
                    if(args.Length == 2 && args[0] == "--update-ready") File.WriteAllText(args[1], "ready");
                    else File.WriteAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "old-restarted"), "ok");
                }
            }'''
            compile_script = (
                "Add-Type -TypeDefinition " + updates._ps_literal(code)
                + " -Language CSharp -OutputType WindowsApplication -OutputAssembly " + updates._ps_literal(target)
            )
            self.run_ps(compile_script)
            original = target.read_bytes()
            with tempfile.TemporaryDirectory(prefix="exmaterial-update-") as stage_name:
                stage = Path(stage_name)
                payload = stage / "ExMaterial-update.exe"
                payload.write_bytes(original)
                script = updates.installer_script(target, payload, 2147483647, hashlib.sha256(original).hexdigest())
                self.run_ps(script)
                self.assertEqual(target.read_bytes(), original)
                self.assertFalse(stage.exists(), (stage / "error.log").read_text(encoding="utf-8-sig") if (stage / "error.log").exists() else "stage not removed")
            self.assertFalse(list(parent.glob("*.backup-*")))

            with tempfile.TemporaryDirectory(prefix="exmaterial-update-") as stage_name:
                stage = Path(stage_name)
                payload = stage / "ExMaterial-update.exe"
                payload.write_bytes(b"MZinvalid executable")
                script = updates.installer_script(target, payload, 2147483647, updates._file_hash(payload))
                # Exercise rollback, suppressing only the final interactive error dialog.
                script = script.split("    Add-Type -AssemblyName System.Windows.Forms")[0] + "\n}\n"
                self.run_ps(script)
                self.assertEqual(target.read_bytes(), original)
                deadline = time.monotonic() + 5
                while not (parent / "old-restarted").exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue((parent / "old-restarted").exists())
                self.assertTrue((stage / "error.log").exists())
                self.assertFalse(list(parent.glob("*.backup-*")))
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "user data")

    def run_ps(self, script):
        if "    Add-Type -AssemblyName System.Windows.Forms" in script:
            script = script.split("    Add-Type -AssemblyName System.Windows.Forms")[0] + "\n}\n"
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, timeout=40, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))


if __name__ == "__main__":
    unittest.main()
