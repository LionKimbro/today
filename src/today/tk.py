"""The Tk machine: widgets, bindings, events, and Core commands."""

import tkinter
from queue import Empty
from tkinter import ttk


g = {
    "root": None,
    "closing": False,
    "rendering-text": False,
    "rendering-history": False,
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

    widgets["workspace"] = ttk.Frame(widgets["tab"])
    widgets["workspace"].grid(row=0, column=0, sticky="nsew")
    widgets["workspace"].columnconfigure(0, weight=1)


def handle_when_text_widget_changes(event, panel_id):
    event.widget.edit_modified(False)
    if g["rendering-text"]:
        return
    g["outgoing-events"].put(
        {
            "type": "TEXT_CHANGED",
            "panel-id": panel_id,
            "text": event.widget.get("1.0", "end-1c"),
        }
    )
    schedule_text_debounce_for_panel(panel_id)


def handle_when_user_moves_history_cursor(value, panel_id):
    if g["rendering-history"]:
        return
    g["outgoing-events"].put(
        {
            "type": "HISTORY_CURSOR_CHANGED",
            "panel-id": panel_id,
            "history-cursor": int(float(value)),
        }
    )


def handle_when_user_clicks_snapshot_button(panel_id):
    g["outgoing-events"].put({"type": "SNAPSHOT", "panel-id": panel_id})


def schedule_text_debounce_for_panel(panel_id):
    if g["text-debounce-id"] is not None:
        g["root"].after_cancel(g["text-debounce-id"])
    g["text-debounce-panel-id"] = panel_id
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
        build_tab_workspace(command)
        return

    if command["type"] == "RENDER_HOSTED_PANEL":
        clear_position_host(command["position-id"])
        render_hosted_panel(command)
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


def build_tab_workspace(command):
    for child in widgets["workspace"].winfo_children():
        child.destroy()
    panel_widgets.clear()
    position_widgets.clear()

    for row_number, row in enumerate(command["rows"]):
        row_frame = ttk.Frame(widgets["workspace"])
        row_frame.grid(row=row_number, column=0, sticky="nsew", pady=(0, 12))
        row_frame.rowconfigure(0, weight=1)
        widgets["workspace"].rowconfigure(row_number, weight=1)

        for column_number, position in enumerate(row["positions"]):
            row_frame.columnconfigure(column_number, weight=1)
            host = ttk.Frame(row_frame, relief="solid", borderwidth=1, padding=12)
            host.grid(row=0, column=column_number, sticky="nsew", padx=(0, 12))
            position_widgets[position["position-id"]] = {"host": host, "panel-id": None}
            if position["panel-id"] is None:
                render_empty_position(position)
            else:
                render_hosted_panel(position)


def clear_position_host(position_id):
    position = position_widgets[position_id]
    if position["panel-id"] is not None:
        panel_widgets.pop(position["panel-id"], None)
    for child in position["host"].winfo_children():
        child.destroy()
    position["panel-id"] = None


def render_empty_position(command):
    host = position_widgets[command["position-id"]]["host"]
    ttk.Label(host, text=command["position-id"]).grid(row=0, column=0, sticky="w")
    ttk.Label(host, text="Empty position").grid(row=1, column=0, sticky="w", pady=(12, 0))


def render_hosted_panel(command):
    position = position_widgets[command["position-id"]]
    host = position["host"]
    position["panel-id"] = command["panel-id"]
    host.columnconfigure(0, weight=1)
    host.rowconfigure(2, weight=1)

    ttk.Label(host, text=f"{command['position-id']} hosts:").grid(row=0, column=0, sticky="w")
    label = ttk.Label(host, text=command["panel-label"])
    label.grid(row=1, column=0, sticky="w", pady=(12, 0))
    snapshot_button = ttk.Button(
        host,
        text="Snapshot",
        command=lambda panel_id=command["panel-id"]: handle_when_user_clicks_snapshot_button(panel_id),
    )
    snapshot_button.grid(row=1, column=1, sticky="e", pady=(12, 0))
    text = tkinter.Text(host, height=10, wrap="word")
    text.grid(row=2, column=0, sticky="nsew", pady=(16, 0))
    text.bind(
        "<<Modified>>",
        lambda event, panel_id=command["panel-id"]: handle_when_text_widget_changes(event, panel_id),
    )
    history_slider = tkinter.Scale(
        host,
        from_=0,
        to=0,
        orient="vertical",
        showvalue=False,
        command=lambda value, panel_id=command["panel-id"]: handle_when_user_moves_history_cursor(
            value, panel_id
        ),
    )
    history_slider.grid(row=2, column=1, sticky="ns", padx=(12, 0), pady=(16, 0))
    history_status = ttk.Label(host, text="Current working version")
    history_status.grid(row=3, column=0, sticky="w", pady=(8, 0))

    g["rendering-text"] = True
    text.insert("1.0", command["panel-text"])
    text.edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    panel_widgets[command["panel-id"]] = {
        "label": label,
        "text": text,
        "history-slider": history_slider,
        "history-status": history_status,
    }
    render_whiteboard_history_controls(command)


def handle_after_rendering_whiteboard_text():
    g["rendering-text"] = False


def render_whiteboard_view(command):
    panel = panel_widgets[command["panel-id"]]
    g["rendering-text"] = True
    panel["text"].delete("1.0", "end")
    panel["text"].insert("1.0", command["panel-text"])
    panel["text"].edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    render_whiteboard_history_controls(command)


def render_whiteboard_history_controls(command):
    panel = panel_widgets[command["panel-id"]]
    g["rendering-history"] = True
    panel["history-slider"].configure(to=command["history-size"])
    panel["history-slider"].set(command["history-cursor"])
    panel["history-status"].configure(text=command["history-status"])
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
