"""The Tk machine: widgets, bindings, events, and Core commands."""

import tkinter
from queue import Empty
from tkinter import ttk


COLORS = {
    "top": "#081525",
    "row-controls": "#0B1A2B",
    "row-controls-hover": "#17304A",
    "row-controls-text": "#B8C4D0",
    "middle": "#10243A",
    "panel": "#F3F6F8",
    "panel-text": "#162332",
    "separator": "#35516B",
    "status": "#0B1828",
    "status-text": "#D7E2EC",
}

g = {
    "root": None,
    "closing": False,
    "rendering-text": False,
    "rendering-history": False,
    "selecting-tab": False,
    "text-debounce-ids": {},
    "outgoing-events": None,
    "incoming-commands": None,
}

widgets = {}
tab_widgets = {}
row_widgets = {}
panel_widgets = {}
position_widgets = {}


def build_today_window():
    g["root"] = tkinter.Tk()
    g["root"].title("Today")
    g["root"].minsize(700, 500)
    g["root"].geometry("1100x760")
    g["root"].configure(background=COLORS["middle"])
    g["root"].protocol("WM_DELETE_WINDOW", handle_when_user_requests_window_close)
    g["root"].bind("<<CoreMailAvailable>>", handle_when_core_mail_arrives)

    style = ttk.Style(g["root"])
    style.configure("Page.TNotebook", background=COLORS["middle"], borderwidth=0)
    style.configure(
        "Page.TNotebook.Tab",
        background="#FFFFFF",
        foreground=COLORS["panel-text"],
        padding=(12, 5),
    )
    style.map(
        "Page.TNotebook.Tab",
        background=[("selected", "#FFFFFF"), ("active", "#F7FAFC")],
        foreground=[("selected", COLORS["panel-text"]), ("active", COLORS["panel-text"])],
    )
    style.configure("Panel.TFrame", background=COLORS["panel"])
    style.configure("Panel.TLabel", background=COLORS["panel"], foreground=COLORS["panel-text"])
    style.configure(
        "PanelTitle.TLabel",
        background=COLORS["panel"],
        foreground=COLORS["panel-text"],
        font=("TkDefaultFont", 10, "bold"),
    )

    g["root"].columnconfigure(0, weight=1)
    g["root"].rowconfigure(1, weight=1)

    top = tkinter.Frame(g["root"], background=COLORS["top"], padx=12, pady=10)
    top.grid(row=0, column=0, sticky="ew")
    widgets["title"] = tkinter.Label(
        top,
        text="Today",
        background=COLORS["top"],
        foreground=COLORS["status-text"],
        font=("TkDefaultFont", 18, "bold"),
    )
    widgets["title"].pack(side="left")
    widgets["date"] = tkinter.Label(
        top,
        background=COLORS["top"],
        foreground=COLORS["status-text"],
        padx=12,
    )
    widgets["date"].pack(side="left")

    widgets["tabs"] = ttk.Notebook(g["root"], style="Page.TNotebook")
    widgets["tabs"].grid(row=1, column=0, sticky="nsew")
    widgets["tabs"].bind("<<NotebookTabChanged>>", handle_when_user_selects_tab)

    widgets["status"] = tkinter.Label(
        g["root"],
        text="Ready.",
        anchor="w",
        background=COLORS["status"],
        foreground=COLORS["status-text"],
        padx=7,
        pady=3,
    )
    widgets["status"].grid(row=2, column=0, sticky="ew")


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


def handle_when_user_selects_panel_for_empty_position(position_id):
    panel_id = position_widgets[position_id]["choice"].get()
    if panel_id == "":
        return
    send_text_debounce_if_one_is_waiting()
    g["outgoing-events"].put(
        {"type": "HOST_PANEL", "position-id": position_id, "panel-id": panel_id}
    )


def handle_when_user_clicks_unhost_panel_button(position_id):
    send_text_debounce_if_one_is_waiting()
    g["outgoing-events"].put({"type": "UNHOST_PANEL", "position-id": position_id})


def handle_when_user_selects_tab(event):
    if g["selecting-tab"]:
        return
    page = event.widget.select()
    for tab_id, tab in tab_widgets.items():
        if str(tab["page"]) == page:
            g["outgoing-events"].put({"type": "SELECT_TAB", "tab-id": tab_id})
            return


def handle_when_user_clicks_move_row_button(tab_id, row_id, direction):
    g["outgoing-events"].put(
        {"type": "MOVE_ROW", "tab-id": tab_id, "row-id": row_id, "direction": direction}
    )


def handle_when_user_releases_pane_sash(event, row_id):
    pane = row_widgets[row_id]["pane"]
    width = pane.winfo_width()
    if width <= 1:
        return
    sash_proportions = [
        pane.sashpos(index) / width
        for index in range(len(row_widgets[row_id]["sash-proportions"]))
    ]
    g["outgoing-events"].put(
        {"type": "SET_SASH_PROPORTIONS", "row-id": row_id, "sash-proportions": sash_proportions}
    )


def handle_when_user_releases_row_sash(event, tab_id):
    for row_id in tab_widgets[tab_id]["row-ids"]:
        g["outgoing-events"].put(
            {
                "type": "SET_ROW_HEIGHT",
                "row-id": row_id,
                "height": row_widgets[row_id]["frame"].winfo_height(),
            }
        )


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
    if panel_id in g["text-debounce-ids"]:
        g["root"].after_cancel(g["text-debounce-ids"][panel_id])
    g["text-debounce-ids"][panel_id] = g["root"].after(
        1000,
        lambda: handle_when_text_debounce_expires(panel_id),
    )


def handle_when_text_debounce_expires(panel_id):
    g["text-debounce-ids"].pop(panel_id, None)
    g["outgoing-events"].put({"type": "TEXT_DEBOUNCE", "panel-id": panel_id})


def send_text_debounce_if_one_is_waiting():
    for panel_id, after_id in list(g["text-debounce-ids"].items()):
        g["root"].after_cancel(after_id)
        handle_when_text_debounce_expires(panel_id)


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
        build_today_tabs(command)
        return

    if command["type"] == "RENDER_POSITION":
        clear_position_host(command["position-id"])
        if command["panel-id"] is None:
            render_empty_position(command)
        else:
            render_hosted_panel(command)
        return

    if command["type"] == "RENDER_WHITEBOARD_VIEW":
        render_whiteboard_view(command)
        return

    if command["type"] == "SET_WHITEBOARD_HISTORY_CURSOR":
        render_whiteboard_history_controls(command)
        return

    if command["type"] == "SET_PANEL_LABEL":
        for panel in panel_widgets[command["panel-id"]]:
            panel["label"].configure(text=command["panel-label"])
        return

    if command["type"] == "SET_SELECTED_TAB":
        select_tab(command["tab-id"])
        return

    if command["type"] == "SET_ROW_HEIGHT":
        row_widgets[command["row-id"]]["height"] = command["height"]
        apply_tab_row_heights(row_widgets[command["row-id"]]["tab-id"])
        return

    if command["type"] == "SET_SASH_PROPORTIONS":
        row_widgets[command["row-id"]]["sash-proportions"] = command["sash-proportions"]
        apply_row_sash_proportions(command["row-id"])
        return

    if command["type"] == "SHUTDOWN_COMPLETE":
        g["root"].destroy()


def build_today_tabs(command):
    for child in widgets["tabs"].winfo_children():
        child.destroy()
    tab_widgets.clear()
    row_widgets.clear()
    panel_widgets.clear()
    position_widgets.clear()

    for tab in command["tabs"]:
        page = tkinter.Frame(widgets["tabs"], background=COLORS["middle"], padx=8, pady=8)
        widgets["tabs"].add(page, text=tab["tab-label"])
        tab_widgets[tab["tab-id"]] = {"page": page, "row-ids": []}
        build_tab_workspace(tab, page)

    select_tab(command["selected-tab-id"])


def select_tab(tab_id):
    g["selecting-tab"] = True
    widgets["tabs"].select(tab_widgets[tab_id]["page"])
    g["root"].after_idle(handle_after_selecting_tab)


def handle_after_selecting_tab():
    g["selecting-tab"] = False


def make_row_rail_button(button):
    tkinter.Button(
        button["parent"],
        text=button["text"],
        width=1,
        padx=0,
        pady=1,
        relief="flat",
        borderwidth=0,
        highlightthickness=0,
        background=COLORS["row-controls"],
        foreground=COLORS["row-controls-text"],
        activebackground=COLORS["row-controls-hover"],
        activeforeground="#E5EBF1",
        command=button.get("command"),
    ).grid(row=button["row"], column=0, pady=button.get("pady", 1))


def build_tab_workspace(command, workspace):
    workspace.columnconfigure(0, weight=1)
    workspace.rowconfigure(0, weight=1)
    rows_pane = ttk.Panedwindow(workspace, orient="vertical")
    rows_pane.grid(row=0, column=0, sticky="nsew")
    tab_widgets[command["tab-id"]]["rows-pane"] = rows_pane
    rows_pane.bind(
        "<ButtonRelease-1>",
        lambda event, tab_id=command["tab-id"]: handle_when_user_releases_row_sash(event, tab_id),
    )

    for row_number, row in enumerate(command["rows"]):
        row_frame = tkinter.Frame(rows_pane, background=COLORS["middle"])
        rows_pane.add(row_frame, weight=1)
        tab_widgets[command["tab-id"]]["row-ids"].append(row["row-id"])
        controls = tkinter.Frame(
            row_frame,
            width=24,
            background=COLORS["row-controls"],
        )
        controls.grid(row=0, column=0, sticky="ns", padx=(0, 4))
        controls.grid_propagate(False)
        make_row_rail_button(
            {
                "parent": controls,
                "text": "↑",
                "row": 0,
                "command": lambda tab_id=command["tab-id"], row_id=row["row-id"]: handle_when_user_clicks_move_row_button(
                    tab_id, row_id, -1
                ),
            }
        )
        make_row_rail_button({"parent": controls, "text": "1", "row": 1})
        make_row_rail_button({"parent": controls, "text": "2", "row": 2})
        make_row_rail_button({"parent": controls, "text": "3", "row": 3})
        make_row_rail_button({"parent": controls, "text": "x", "row": 4, "pady": (6, 1)})
        make_row_rail_button(
            {
                "parent": controls,
                "text": "↓",
                "row": 5,
                "pady": (6, 1),
                "command": lambda tab_id=command["tab-id"], row_id=row["row-id"]: handle_when_user_clicks_move_row_button(
                    tab_id, row_id, 1
                ),
            }
        )
        row_pane = ttk.Panedwindow(row_frame, orient="horizontal")
        row_pane.grid(row=0, column=1, sticky="nsew")
        row_frame.columnconfigure(1, weight=1)
        row_frame.rowconfigure(0, weight=1)
        row_pane.bind(
            "<ButtonRelease-1>",
            lambda event, row_id=row["row-id"]: handle_when_user_releases_pane_sash(event, row_id),
        )
        row_widgets[row["row-id"]] = {
            "tab-id": command["tab-id"],
            "frame": row_frame,
            "pane": row_pane,
            "height": row["height"],
            "sash-proportions": row["sash-proportions"],
        }

        for column_number, position in enumerate(row["positions"]):
            host = ttk.Frame(
                row_pane,
                style="Panel.TFrame",
                relief="solid",
                borderwidth=1,
                padding=12,
            )
            row_pane.add(host, weight=1)
            position_widgets[position["position-id"]] = {
                "host": host,
                "panel-id": None,
                "panel-widgets": None,
            }
            if position["panel-id"] is None:
                render_empty_position(position)
            else:
                render_hosted_panel(position)

    g["root"].after_idle(lambda tab_id=command["tab-id"]: apply_tab_geometry(tab_id))


def apply_tab_geometry(tab_id):
    apply_tab_row_heights(tab_id)
    for row_id in tab_widgets[tab_id]["row-ids"]:
        apply_row_sash_proportions(row_id)


def apply_tab_row_heights(tab_id):
    rows_pane = tab_widgets[tab_id]["rows-pane"]
    heights = [row_widgets[row_id]["height"] for row_id in tab_widgets[tab_id]["row-ids"]]
    if rows_pane.winfo_height() <= 1 or len(heights) < 2:
        return
    cumulative_height = 0
    for index, height in enumerate(heights[:-1]):
        cumulative_height += height
        rows_pane.sashpos(index, cumulative_height)


def apply_row_sash_proportions(row_id):
    pane = row_widgets[row_id]["pane"]
    if pane.winfo_width() <= 1:
        return
    for index, proportion in enumerate(row_widgets[row_id]["sash-proportions"]):
        pane.sashpos(index, int(pane.winfo_width() * proportion))


def clear_position_host(position_id):
    position = position_widgets[position_id]
    if position["panel-id"] is not None:
        panel_widgets[position["panel-id"]].remove(position["panel-widgets"])
        if not panel_widgets[position["panel-id"]]:
            panel_widgets.pop(position["panel-id"])
    for child in position["host"].winfo_children():
        child.destroy()
    position["panel-id"] = None
    position["panel-widgets"] = None


def render_empty_position(command):
    position = position_widgets[command["position-id"]]
    host = position["host"]
    ttk.Label(host, text=command["position-id"]).grid(row=0, column=0, sticky="w")
    choice = ttk.Combobox(host, values=command["available-panel-ids"], state="readonly")
    choice.grid(row=1, column=0, sticky="ew", pady=(12, 0))
    choice.set("Choose existing panel")
    choice.bind(
        "<<ComboboxSelected>>",
        lambda event, position_id=command["position-id"]: handle_when_user_selects_panel_for_empty_position(
            position_id
        ),
    )
    position["choice"] = choice


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
    unhost_button = ttk.Button(
        host,
        text="Unhost panel",
        command=lambda position_id=command["position-id"]: handle_when_user_clicks_unhost_panel_button(
            position_id
        ),
    )
    unhost_button.grid(row=0, column=1, sticky="e")
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
    panel = {
        "label": label,
        "text": text,
        "history-slider": history_slider,
        "history-status": history_status,
    }
    position["panel-widgets"] = panel
    panel_widgets.setdefault(command["panel-id"], []).append(panel)
    render_whiteboard_history_controls(command)


def handle_after_rendering_whiteboard_text():
    g["rendering-text"] = False


def render_whiteboard_view(command):
    g["rendering-text"] = True
    for panel in panel_widgets[command["panel-id"]]:
        panel["text"].delete("1.0", "end")
        panel["text"].insert("1.0", command["panel-text"])
        panel["text"].edit_modified(False)
    g["root"].after_idle(handle_after_rendering_whiteboard_text)
    render_whiteboard_history_controls(command)


def render_whiteboard_history_controls(command):
    g["rendering-history"] = True
    for panel in panel_widgets[command["panel-id"]]:
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
