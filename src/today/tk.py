"""The Tk machine: widgets, bindings, events, and Core commands."""

import tkinter
from queue import Empty
from tkinter import ttk


g = {
    "root": None,
    "closing": False,
    "outgoing-events": None,
    "incoming-commands": None,
}

widgets = {}
panel_widgets = {}


def build_today_window():
    g["root"] = tkinter.Tk()
    g["root"].title("Today")
    g["root"].minsize(420, 300)
    g["root"].protocol("WM_DELETE_WINDOW", handle_when_user_requests_window_close)
    g["root"].bind("<<CoreMailAvailable>>", handle_when_core_mail_arrives)

    content = ttk.Frame(g["root"], padding=20)
    content.grid(sticky="nsew")
    g["root"].columnconfigure(0, weight=1)
    g["root"].rowconfigure(0, weight=1)
    content.columnconfigure(0, weight=1)
    content.rowconfigure(2, weight=1)

    widgets["title"] = ttk.Label(content, text="Today", font=("TkDefaultFont", 18, "bold"))
    widgets["title"].grid(row=0, column=0, sticky="w")
    widgets["date"] = ttk.Label(content)
    widgets["date"].grid(row=1, column=0, sticky="w", pady=(12, 12))

    widgets["tab"] = ttk.LabelFrame(content, padding=12)
    widgets["tab"].grid(row=2, column=0, sticky="nsew")
    widgets["tab"].columnconfigure(0, weight=1)
    widgets["tab"].rowconfigure(0, weight=1)

    widgets["panel"] = ttk.Frame(widgets["tab"], relief="solid", borderwidth=1, padding=24)
    widgets["panel"].grid(row=0, column=0, sticky="nsew")
    widgets["panel"].columnconfigure(0, weight=1)
    widgets["panel"].rowconfigure(1, weight=1)
    widgets["position"] = ttk.Label(widgets["panel"])
    widgets["position"].grid(row=0, column=0, sticky="w")
    widgets["panel-label"] = ttk.Label(widgets["panel"])
    widgets["panel-label"].grid(row=1, column=0)
    widgets["rename-button"] = ttk.Button(
        widgets["panel"], text="Rename panel", state="disabled"
    )
    widgets["rename-button"].grid(row=2, column=0, pady=(16, 0))


def handle_when_user_clicks_rename_panel_button(panel_id):
    g["outgoing-events"].put({"type": "RENAME_PANEL", "panel-id": panel_id})


def handle_when_user_requests_window_close():
    if g["closing"]:
        return

    g["closing"] = True
    widgets["rename-button"].state(["disabled"])
    g["outgoing-events"].put({"type": "SHUTDOWN"})


def enqueue_core_command_and_wake_tk(command):
    g["incoming-commands"].put(command)
    g["root"].event_generate("<<CoreMailAvailable>>", when="tail")


def realize_core_command(command):
    if command["type"] == "RENDER_TODAY":
        widgets["date"].configure(text=command["today-id"])
        widgets["tab"].configure(text=command["tab-label"])
        widgets["position"].configure(text=command["position-id"])
        widgets["panel-label"].configure(text=command["panel-label"])
        panel_widgets[command["panel-id"]] = {"label": widgets["panel-label"]}
        widgets["rename-button"].configure(
            command=lambda: handle_when_user_clicks_rename_panel_button(command["panel-id"])
        )
        if not g["closing"]:
            widgets["rename-button"].state(["!disabled"])
        return

    if command["type"] == "SET_PANEL_LABEL":
        panel_widgets[command["panel-id"]]["label"].configure(text=command["panel-label"])
        return

    if command["type"] == "SHUTDOWN_COMPLETE":
        g["root"].destroy()


def handle_when_core_mail_arrives(event):
    try:
        while True:
            command = g["incoming-commands"].get_nowait()
            print("Core -> Tk:", command)
            realize_core_command(command)
            if command["type"] == "SHUTDOWN_COMPLETE":
                return
    except Empty:
        pass


def run_tk_machine():
    g["root"].mainloop()
