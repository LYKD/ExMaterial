"""Nonblocking update checks; worker threads never call Tk."""
from __future__ import annotations

import queue
import shutil
import sys
import threading
import webbrowser
from tkinter import BOTH, END, LEFT, Button, Frame, Label, Text, Toplevel, messagebox, ttk

try:
    from . import updates
except ImportError:
    import updates


class UpdateManager:
    def __init__(self, root, current_version: str):
        self.root = root
        self.current_version = current_version
        self.events = queue.Queue()
        self.busy = False
        self.window = None
        self.release = None
        self.payload = None
        self.installing = False
        self.root.after(100, self.poll)

    def check(self, manual: bool = True) -> None:
        if self.window is not None and self.window.winfo_exists():
            self.window.lift()
            return
        if self.busy:
            if manual:
                messagebox.showinfo("检查更新", "正在检查更新，请稍候。", parent=self.root)
            return
        self.busy = True

        def worker():
            try:
                self.events.put(("checked", updates.check_latest(self.current_version), manual))
            except Exception as exc:
                self.events.put(("check_error", str(exc), manual))
        threading.Thread(target=worker, daemon=True).start()

    def poll(self) -> None:
        try:
            while True:
                kind, value, extra = self.events.get_nowait()
                if kind == "checked":
                    self.busy = False
                    if value is not None:
                        self.show_release(value)
                    elif extra:
                        messagebox.showinfo("检查更新", f"当前 {self.current_version} 已是最新正式版。", parent=self.root)
                elif kind == "check_error":
                    self.busy = False
                    if extra:
                        if messagebox.askyesno("无法检查更新", value + "\n\n是否打开发布页查看最新版？", parent=self.root):
                            webbrowser.open(updates.RELEASES_URL)
                elif kind == "progress":
                    self.progress["value"] = value / extra * 100
                    self.status.configure(text=f"正在下载：{value / 1048576:.1f} / {extra / 1048576:.1f} MB")
                elif kind == "downloaded":
                    self.busy = False
                    self.payload = value
                    self.status.configure(text="下载和校验完成，可以重启更新。")
                    self.install_button.configure(state="normal", text="重启并更新")
                    self.restart()
                elif kind == "download_error":
                    self.busy = False
                    self.status.configure(text="下载失败，可重试。")
                    self.install_button.configure(state="normal")
                    messagebox.showwarning("更新失败", value, parent=self.window)
        except queue.Empty:
            pass
        if not self.installing:
            self.root.after(100, self.poll)

    def show_release(self, release: updates.Release) -> None:
        self.release = release
        self.window = Toplevel(self.root)
        self.window.title("ExMaterial 软件更新")
        self.window.geometry("560x420")
        self.window.transient(self.root)
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        body = Frame(self.window, padx=16, pady=14)
        body.pack(fill=BOTH, expand=True)
        Label(body, text=f"发现新版本 {release.version}", font=("Arial", 13, "bold")).pack(anchor="w")
        Label(body, text=f"当前版本：{self.current_version}").pack(anchor="w", pady=(4, 8))
        notes = Text(body, wrap="word", height=10)
        notes.pack(fill=BOTH, expand=True)
        notes.insert(END, release.notes)
        notes.configure(state="disabled")
        can_install = release.can_install and sys.platform == "win32" and getattr(sys, "frozen", False)
        hint = "更新会关闭并重启软件，请先保存编辑内容。实验数据目录会保留。"
        if not can_install:
            hint = "请从发布页下载 Windows 版更新包，或更新本地源码。"
        self.status = Label(body, text=hint, wraplength=520, justify=LEFT)
        self.status.pack(anchor="w", pady=8)
        self.progress = ttk.Progressbar(body, maximum=100)
        self.progress.pack(fill="x", pady=(0, 8))
        buttons = Frame(body)
        buttons.pack(fill="x")
        Button(buttons, text="查看发布页", command=lambda: webbrowser.open(release.page_url)).pack(side=LEFT)
        Button(buttons, text="稍后", command=self.close).pack(side=LEFT, padx=8)
        self.install_button = Button(buttons, text="下载并重启更新", command=self.download, state="normal" if can_install else "disabled")
        self.install_button.pack(side="right")

    def download(self) -> None:
        if self.payload is not None:
            self.restart()
            return
        if self.busy:
            return
        self.busy = True
        self.install_button.configure(state="disabled")
        self.status.configure(text="正在下载更新包…")
        release = self.release

        def worker():
            try:
                payload = updates.download_release(release, lambda done, total: self.events.put(("progress", done, total)))
                self.events.put(("downloaded", payload, None))
            except Exception as exc:
                self.events.put(("download_error", str(exc), None))
        threading.Thread(target=worker, daemon=True).start()

    def restart(self) -> None:
        if not messagebox.askyesno("重启更新", "更新包已通过校验。请确认当前编辑内容已保存。\n\n现在关闭软件并更新到新版本？", parent=self.window):
            return
        try:
            updates.launch_installer(self.payload, self.release.sha256)
        except (OSError, updates.UpdateError) as exc:
            messagebox.showerror("无法安装更新", str(exc), parent=self.window)
            return
        self.installing = True
        self.root.destroy()

    def close(self) -> None:
        if self.busy:
            messagebox.showinfo("正在下载", "更新包正在下载，请等待下载完成。", parent=self.window)
            return
        if self.payload is not None:
            shutil.rmtree(self.payload.parent, ignore_errors=True)
            self.payload = None
        self.window.destroy()
        self.window = None
