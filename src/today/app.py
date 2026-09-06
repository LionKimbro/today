"""Today Stage 1: one current day, tab, position, and hosted panel."""

import tkinter as tk
from datetime import date
from tkinter import ttk


g = {
    "root": None,
    "today-id": None,
}

days = {}
tabs = {}
positions = {}
panels = {}
widgets = {}


def initialize_today_world():
    today_id = date.today().isoformat()
    g["today-id"] = today_id

    days[today_id] = {
        "id": today_id,
        "tab-ids": ["tab-a"],
    }
    tabs["tab-a"] = {
        "id": "tab-a",
        "day-id": today_id,
        "label": "Tab A",
        "position-ids": ["position-1"],
    }
    positions["position-1"] = {
        "id": "position-1",
        "tab-id": "tab-a",
        "panel-id": "panel-1",
    }
    panels["panel-1"] = {
        "id": "panel-1",
        "label": "panel-1",
    }


def build_today_window():
    g["root"] = tk.Tk()
    g["root"].title("Today")
    g["root"].minsize(420, 300)

    content = ttk.Frame(g["root"], padding=20)
    content.grid(sticky="nsew")
    g["root"].columnconfigure(0, weight=1)
    g["root"].rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(2, weight=1)

    ttk.Label(content, text="Today", font=("TkDefaultFont", 18, "bold")).grid(
        row=0, column=0, sticky="w"
    )
    ttk.Label(content, text=g["today-id"]).grid(row=1, column=0, sticky="w", pady=(12, 12))

    tab_frame = ttk.LabelFrame(content, text=tabs["tab-a"]["label"], padding=12)
    tab_frame.grid(row=2, column=0, sticky="nsew")
    tab_frame.columnconfigure(0, weight=1)
    tab_frame.rowconfigure(0, weight=1)
    widgets["tab-a"] = tab_frame

    position = positions["position-1"]
    panel = panels[position["panel-id"]]
    panel_frame = ttk.Frame(tab_frame, relief="solid", borderwidth=1, padding=24)
    panel_frame.grid(row=0, column=0, sticky="nsew")
    panel_frame.columnconfigure(0, weight=1)
    panel_frame.rowconfigure(0, weight=1)
    ttk.Label(panel_frame, text=panel["label"]).grid(row=0, column=0)
    widgets[position["id"]] = panel_frame


def main():
    initialize_today_world()
    build_today_window()
    g["root"].mainloop()


if __name__ == "__main__":
    main()
