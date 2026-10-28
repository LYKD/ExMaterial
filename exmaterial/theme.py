"""A quiet, consistent desktop palette, shared by native Tk windows."""
from tkinter import ttk


def apply_theme(root):
    root.configure(background="#f1f5f7")
    for pattern, value in {
        "*Font": "{Microsoft YaHei UI} 10", "*Background": "#f1f5f7",
        "*Foreground": "#253b4b", "*Button.Background": "#e0efed",
        "*Button.activeBackground": "#c7e3df", "*Button.Relief": "flat",
        "*Button.BorderWidth": 0, "*Button.padX": 10, "*Button.padY": 5,
        "*Entry.Background": "#ffffff", "*Entry.Relief": "flat",
        "*Entry.highlightThickness": 1, "*Entry.highlightBackground": "#cedce2",
        "*Entry.highlightColor": "#147d78", "*Text.Background": "#ffffff",
        "*Text.Relief": "flat", "*Text.padX": 8, "*Text.padY": 6,
        "*Text.selectBackground": "#c7e3df", "*Listbox.Background": "#ffffff",
        "*Listbox.Relief": "flat", "*Listbox.BorderWidth": 0,
        "*Listbox.selectBackground": "#147d78", "*Listbox.selectForeground": "#ffffff",
        "*Listbox.highlightThickness": 0, "*LabelFrame.Relief": "groove",
        "*LabelFrame.BorderWidth": 1, "*LabelFrame.Foreground": "#147d78",
        "*Canvas.Background": "#ffffff",
    }.items():
        root.option_add(pattern, value)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TNotebook", background="#f1f5f7", borderwidth=0)
    style.configure("TNotebook.Tab", padding=(18, 9), font=("Microsoft YaHei UI", 10))
    style.map("TNotebook.Tab", background=[("selected", "#ffffff")], foreground=[("selected", "#147d78")])
    style.configure("TCombobox", padding=4)
