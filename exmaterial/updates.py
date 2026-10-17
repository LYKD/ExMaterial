"""GitHub release discovery and verified Windows executable replacement."""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPOSITORY = "LYKD/ExMaterial"
RELEASES_URL = f"https://github.com/{REPOSITORY}/releases/latest"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
MAX_DOWNLOAD_SIZE = 512 * 1024 * 1024


class UpdateError(Exception):
    pass


@dataclass(frozen=True)
class Release:
    version: str
    page_url: str
    notes: str
    download_url: str = ""
    size: int = 0
    sha256: str = ""

    @property
    def can_install(self) -> bool:
        return bool(self.download_url and self.sha256 and self.size)


SOURCE_UPDATE_HINT = "当前从源码运行，自动替换仅适用于 Windows EXE 版。通过 Git 获取源码的用户可在源码目录执行 git pull 后重启；通过源码压缩包安装的用户请从发布页下载新版源码。升级时保留 information 数据目录。"
PLATFORM_UPDATE_HINT = "自动替换仅适用于 Windows EXE 版，请从发布页下载对应版本。"
NO_PACKAGE_UPDATE_HINT = "此版本没有可校验的 Windows 安装包，请从发布页下载。"


def manual_update_hint(release: Release) -> str:
    """Return why this running build cannot self-update, or an empty string when it can."""
    if sys.platform != "win32":
        return PLATFORM_UPDATE_HINT
    if not getattr(sys, "frozen", False):
        return SOURCE_UPDATE_HINT
    if not release.can_install:
        return NO_PACKAGE_UPDATE_HINT
    return ""


def version_tuple(version: str) -> tuple[int, int, int]:
    match = re.fullmatch(r"[vV]?(\d+)\.(\d+)\.(\d+)(?:\+[\w.-]+)?", version)
    if not match:
        raise UpdateError("发布版本号格式不受支持。")
    return tuple(int(part) for part in match.groups())


def release_from_json(data: dict, current_version: str) -> Release | None:
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name", ""))
    latest = version_tuple(tag)
    if latest <= version_tuple(current_version):
        return None
    version = ".".join(str(part) for part in latest)
    page = f"https://github.com/{REPOSITORY}/releases/tag/{quote(tag, safe='')}"
    release = Release(version, page, str(data.get("body") or "暂无更新说明。")[:20000])
    expected_names = (f"exmaterial-{version}-windows-x64.exe", "exmaterial.exe")
    assets = data.get("assets", [])
    if not isinstance(assets, list):
        return release
    for expected in expected_names:
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name", ""))
            url = str(asset.get("browser_download_url", ""))
            parsed = urlsplit(url)
            expected_path = f"/{REPOSITORY}/releases/download/{tag}/{name}"
            if (name.lower() != expected or asset.get("state") != "uploaded"
                    or parsed.scheme != "https" or parsed.netloc != "github.com"
                    or unquote(parsed.path) != expected_path or parsed.query or parsed.fragment):
                continue
            digest = str(asset.get("digest") or "")
            size = asset.get("size")
            if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
                continue
            if not isinstance(size, int) or isinstance(size, bool) or not 2 <= size <= MAX_DOWNLOAD_SIZE:
                continue
            return Release(version, page, release.notes, url, size, digest[7:].lower())
    return release


def check_latest(current_version: str) -> Release | None:
    request = Request(API_URL, headers={"Accept": "application/vnd.github+json", "User-Agent": "ExMaterial-updater"})
    try:
        with urlopen(request, timeout=15) as response:
            payload = response.read(1024 * 1024 + 1)
    except HTTPError as exc:
        if exc.code in (403, 429):
            raise UpdateError("GitHub 暂时限制了检查频率，请稍后重试，或从发布页查看新版。") from exc
        if exc.code == 404:
            raise UpdateError("当前没有可用的正式发布版本。") from exc
        raise
    if len(payload) > 1024 * 1024:
        raise UpdateError("更新服务器响应过大。")
    try:
        data = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise UpdateError("无法识别更新服务器响应。") from exc
    return release_from_json(data, current_version)


def download_release(release: Release, progress=None) -> Path:
    parsed = urlsplit(release.download_url)
    if (not release.can_install or parsed.scheme != "https" or parsed.netloc != "github.com"
            or not unquote(parsed.path).startswith(f"/{REPOSITORY}/releases/download/")
            or parsed.query or parsed.fragment or not parsed.path.lower().endswith(".exe")
            or not re.fullmatch(r"[a-fA-F0-9]{64}", release.sha256)
            or not 2 <= release.size <= MAX_DOWNLOAD_SIZE):
        raise UpdateError(NO_PACKAGE_UPDATE_HINT)
    stage = Path(tempfile.mkdtemp(prefix="exmaterial-update-"))
    payload = stage / "ExMaterial-update.exe"
    try:
        request = Request(release.download_url, headers={"User-Agent": "ExMaterial-updater"})
        digest = hashlib.sha256()
        total = 0
        with urlopen(request, timeout=30) as response, payload.open("wb") as handle:
            while True:
                chunk = response.read(128 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > release.size or total > MAX_DOWNLOAD_SIZE:
                    raise UpdateError("下载文件大小与发布信息不符。")
                handle.write(chunk)
                digest.update(chunk)
                if progress:
                    progress(total, release.size)
        if total != release.size or digest.hexdigest() != release.sha256:
            raise UpdateError("更新包校验失败，请重试下载。")
        with payload.open("rb") as handle:
            if handle.read(2) != b"MZ":
                raise UpdateError("下载文件不是 Windows 可执行程序。")
        return payload
    except Exception:
        # Only the fresh, private download directory is removed.
        shutil.rmtree(stage)
        raise


def _ps_literal(value) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def installer_script(target: Path, payload: Path, pid: int, expected_sha256: str) -> str:
    target = target.resolve(strict=True)
    payload = payload.resolve(strict=True)
    if target.suffix.lower() != ".exe" or not payload.parent.name.startswith("exmaterial-update-"):
        raise UpdateError("更新目标路径无效。")
    if not re.fullmatch(r"[a-fA-F0-9]{64}", expected_sha256) or _file_hash(payload) != expected_sha256.lower():
        raise UpdateError("更新包校验失败，请重新下载。")
    token = uuid.uuid4().hex
    header = "\n".join((
        "$ErrorActionPreference = 'Stop'",
        f"$target = {_ps_literal(target)}",
        f"$payload = {_ps_literal(payload)}",
        f"$stage = {_ps_literal(payload.parent)}",
        f"$ready = {_ps_literal(payload.parent / 'ready')}",
        f"$backup = {_ps_literal(target.with_name(target.name + '.backup-' + token))}",
        f"$candidate = {_ps_literal(target.with_name(target.name + '.update-' + token))}",
        f"$expectedHash = {_ps_literal(expected_sha256.lower())}",
        f"$oldPid = {int(pid)}",
    ))
    return header + r'''
$moved = $false
$installed = $false
try {
    $old = Get-Process -Id $oldPid -ErrorAction SilentlyContinue
    if ($old -and -not $old.WaitForExit(120000)) { throw 'The application did not close.' }
    Copy-Item -LiteralPath $payload -Destination $candidate
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($candidate)
    try {
        $actualHash = [System.BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha.Dispose()
    }
    if ($actualHash -ne $expectedHash) {
        throw 'The update package changed after download.'
    }
    # Retry briefly while Windows releases the old executable.
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Move-Item -LiteralPath $target -Destination $backup
            $moved = $true
            break
        } catch {
            if ($attempt -eq 29) { throw }
            Start-Sleep -Milliseconds 500
        }
    }
    Move-Item -LiteralPath $candidate -Destination $target
    $installed = $true
    $arguments = '--update-ready "' + $ready + '"'
    $newApp = Start-Process -FilePath $target -WorkingDirectory (Split-Path -LiteralPath $target) -ArgumentList $arguments -PassThru
    $deadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Path -LiteralPath $ready)) {
        if ($newApp.HasExited -or (Get-Date) -gt $deadline) { throw 'The updated application did not start.' }
        Start-Sleep -Milliseconds 250
    }
    # Cleanup errors must not roll back an already acknowledged application.
    Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $payload,$ready -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $stage -ErrorAction SilentlyContinue
} catch {
    $failure = $_.Exception.Message
    if ($installed -and $newApp -and -not $newApp.HasExited) {
        # A PyInstaller onefile application may also own a child process.
        & (Join-Path $env:SystemRoot 'System32/taskkill.exe') /PID $newApp.Id /T /F | Out-Null
        $null = $newApp.WaitForExit(10000)
    }
    if ($moved) {
        try {
            if ($installed) { Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue }
            Move-Item -LiteralPath $backup -Destination $target -Force
            Start-Process -FilePath $target -WorkingDirectory (Split-Path -LiteralPath $target)
        } catch {
            $failure += "`nRecovery failed. Backup: " + $backup + "`n" + $_.Exception.Message
        }
    }
    if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate -Force }
    $failure | Set-Content -LiteralPath (Join-Path $stage 'error.log') -Encoding UTF8 -ErrorAction SilentlyContinue
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.MessageBox]::Show("更新未完成，请查看下面的信息。`n" + $failure, 'ExMaterial 更新') | Out-Null
}
'''


def launch_installer(payload: Path, expected_sha256: str) -> None:
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise UpdateError(PLATFORM_UPDATE_HINT if sys.platform != "win32" else SOURCE_UPDATE_HINT)
    target = Path(sys.executable).resolve(strict=True)
    # Fail before closing the app when its install directory is not writable.
    try:
        with tempfile.TemporaryFile(dir=target.parent):
            pass
    except OSError as exc:
        raise UpdateError("程序所在目录不可写，请将软件移到可写目录，或从发布页手动更新。") from exc
    encoded = base64.b64encode(installer_script(target, payload, os.getpid(), expected_sha256).encode("utf-16-le")).decode("ascii")
    powershell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.Popen(
        [str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded],
        creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
    )


def confirm_update_startup(arguments: list[str]) -> None:
    if len(arguments) != 2 or arguments[0] != "--update-ready":
        return
    marker = Path(arguments[1]).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if (marker.name == "ready" and marker.parent.parent == temp_root
            and marker.parent.name.startswith("exmaterial-update-") and marker.parent.is_dir()):
        marker.write_text("ready", encoding="ascii")
