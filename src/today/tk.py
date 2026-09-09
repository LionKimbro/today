"""The Tk machine: widgets, bindings, events, and Core commands."""

import tkinter
from queue import Empty
from tkinter import ttk


g = {
    "root": None,
    "closing": False,
    "rendering-text": False,
    "rendering-history": False,
    "active-panel-id": None,
    "text-debounce-id": None,
    "text-debounce-panel-id": None,
    "outgoing-events": None,
    "incoming-commands": None,
}

widgets = {}
panel_widgets = {}
position_widgets = {}


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
    widgets["panel"].rowconfigure(2, weight=1)
    widgets["position"] = ttk.Label(widgets["panel"])
    widgets["position"].grid(row=0, column=0, sticky="w")
    widgets["panel-choice"] = ttk.Combobox(
        widgets["panel"], values=("whiteboard-a", "whiteboard-b"), state="readonly"
    )
    widgets["panel-choice"].grid(row=0, column=0, sticky="e")
    widgets["panel-choice"].bind(
        "<<ComboboxSelected>>",
        lambda event: handle_when_user_selects_hosted_panel("position-1"),
    )
    widgets["panel-label"] = ttk.Label(widgets["panel"])
    widgets["panel-label"].grid(row=1, column=0, sticky="w")
    widgets["snapshot-button"] = ttk.Button(
        widgets["panel"], text="Snapshot", command=handle_when_user_clicks_snapshot_button
    )
    widgets["snapshot-button"].grid(row=1, column=1, sticky="e")
    widgets["whiteboard-text"] = tkinter.Text(widgets["panel"], height=10, wrap="word")
    widgets["whiteboard-text"].grid(row=2, column=0, sticky="nsew", pady=(16, 0))
    widgets["whiteboard-text"].bind("<<Modified>>", handle_when_text_widget_changes)
    widgets["whiteboard-text"].edit_modified(False)
    widgets["history-slider"] = tkinter.Scale(
        widgets["panel"], from_=0, to=0, orient="vertical", showvalue=False,
        command=handle_when_user_moves_history_cursor,
    )
    widgets["history-slider"].grid(row=2, column=1, sticky="ns", padx=(12, 0))
    widgets["history-status"] = ttk.Label(widgets["panel"], text="Current working version")
    widgets["history-status"].grid(row=3, column=0, sticky="w", pady=(8, 0))


def handle_when_user_selects_hosted_panel(position_id):
    send_text_debounce_if_one_is_waiting()
    panel_id = position_widgets[position_id]["choice"].get()
    g["outgoing-events"].put(
        {"type": "HOST_PANEL", "position-id": position_id, "panel-id": panel_id}
    )


def handle_when_text_widget_changes(event):
    widgets["whiteboard-text"].edit_modified(False)
    if g["rendering-text"] or g["active-panel-id"] is None:
        return
    g["outgoing-events"].put(
        {
            "type": "TEXT_CHANGED",
            "panel-id": g["active-panel-id"],
            "text": widgets["whiteboard-text"].get("1.0", "end-1c"),
        }
    )
    schedule_text_debounce_for_active_panel()


def handle_when_user_moves_history_cursor(value):
    if g["rendering-history"] or g["active-panel-id"] is None:
        return
    g["outgoing-events"].put(
        {
            "type": "HISTORY_CURSOR_CHANGED",
            "panel-id": g["active-panel-id"],
            "history-cursor": int(float(value)),
        }
    )


def handle_when_user_clicks_snapshot_button():
    g["outgoing-events"].put({"type": "SNAPSHOT", "panel-id": g["active-panel-id"]})


def schedule_text_debounce_for_active_panel():
    if g["text-debounce-id"] is not None:
        g["root"].after_cancel(g["text-debounce-id"])
    g["text-debounce-panel-id"] = g["active-panel-id"]
    g["text-debounce-id"] = g["root"].after(1000, handle_when_text_debounce_expires)


def handle_when_text_debounce_expires():
    panel_id = g["text-debounce-panel-id"]
    g["text-debounce-id"] = None
    g["text-debounce-panel-id"] = None
    g["outgoing-events"].put({"type": "TEXT_DEBOUNCE", "panel-id": panel_id})


def send_text_debounce_if_one_is_waiting():
    if g["text-debounce-id"] is None:
        return
    g["root"].after_cancel(g["text-debounce-id"])
    handle_when_text_debounce_expires()


def handle_when_user_requests_window_close():
    if g["closing"]:
        return

    g["closing"] = True
    send_text_debounce_if_one_is_waiting()
    g["outgoing-events"].put({"type": "SHUTDOWN"})


def enqueue_core_command_and_wake_tk(command):
    g["incoming-commands"].put(command)
    g["root"].event_generate("<<CoreMailAvailable>>", when="tail")


def realize_core_command(command):
    if command["type"] == "RENDER_TODAY":
        widgets["date"].configure(text=command["today-id"])
        widgets["tab"].configure(text=command["tab-label"])
        widgets["position"].configure(text=command["position-id"])
        render_hosted_panel(command)
        position_widgets[command["position-id"]] = {
            "label": widgets["panel-label"],
            "choice": widgets["panel-choice"],
        }
        widgets["position"].configure(text=f"{command['position-id']} hosts:")
        widgets["panel-choice"].set(command["panel-id"])
        return

    if command["type"] == "RENDER_HOSTED_PANEL":
        render_hosted_panel(command)
        position_widgets[command["position-id"]]["choice"].set(command["panel-id"])
        return

    if command["type"] == "RENDER_WHITEBOARD_VIEW":
        render_whiteboard_view(command)
        return

    if command["type"] == "SET_WHITEBOARD_HISTORY_CURSOR":
        render_whiteboard_history_controls(command)
        return

    if command["type"] == "SET_PANEL_LABEL":
        panel_widgets[command["panel-id"]]["label"].configure(text=command["panel-label"])
        return

    if command["type"] == "SHUTDOWN_COMPLETE":
        g["root"].destroy()


def render_hosted_panel(command):
    g["rendering-text"] = True
    g["active-panel-id"] = command["panel-id"]
    widgets["panel-label"].configure(text=command["panel-label"])
    widgets["whiteboard-text"].delete("1.0", "end")
    widgets["whiteboard-text"].insert("1.0", command["panel-text"])
    widgets["whiteboard-text"].edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    render_whiteboard_history_controls(command)
    panel_widgets[command["panel-id"]] = {"label": widgets["panel-label"]}


def handle_after_rendering_whiteboard_text():
    g["rendering-text"] = False


def render_whiteboard_view(command):
    g["rendering-text"] = True
    widgets["whiteboard-text"].delete("1.0", "end")
    widgets["whiteboard-text"].insert("1.0", command["panel-text"])
    widgets["whiteboard-text"].edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    render_whiteboard_history_controls(command)


def render_whiteboard_history_controls(command):
    g["rendering-history"] = True
    widgets["history-slider"].configure(to=command["history-size"])
    widgets["history-slider"].set(command["history-cursor"])
    widgets["history-status"].configure(text=command["history-status"])
    g["rendering-history"] = False


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
