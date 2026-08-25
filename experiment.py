"""Small procedural experiment for the Today GUI interaction model.

The application is intentionally organized as a staged machine:
Tk callbacks produce application events; idle processing mutates state;
GUI consequences are processed in a separate stage.
"""

from collections import deque
from datetime import date, timedelta
import tkinter as tk
from tkinter import ttk


TODO_PANEL = "TODO"
JOURNAL_PANEL = "JOURNAL"

SELECT_PREVIOUS_DAY = "SELECT_PREVIOUS_DAY"
SELECT_NEXT_DAY = "SELECT_NEXT_DAY"
SELECT_TODAY = "SELECT_TODAY"
SECOND_ELAPSED = "SECOND_ELAPSED"
TOGGLE_TODO = "TOGGLE_TODO"
EDIT_JOURNAL = "EDIT_JOURNAL"
EDIT_ORIENTATION = "EDIT_ORIENTATION"


g = {
    "root": None,
    "selected_day": date.today(),
    "processing_scheduled": False,
    "shut-up": False,
    "heartbeat_count": 0,
    "orientation_text": "orientation",
}

reg = {
    "event": None,
    "panel_id": None,
    "panel_widgets": None,
    "panel_state": None,
    "panel_type": None,
    "position_id": None,
    "position_widgets": None,
    "target_consequences": None,
}

global_event_queue = deque()
panel_event_queues = {
    "panel-todo-1": deque(),
    "panel-journal-1": deque(),
    "panel-journal-2": deque(),
}
gui_consequence_queue = deque()
panel_reconfiguration_queue = deque()

position_panel = {
    "position-1": "panel-todo-1",
    "position-2": "panel-journal-1",
}

position_widgets = {
    "position-1": {},
    "position-2": {},
}

panel_type = {
    "panel-todo-1": TODO_PANEL,
    "panel-journal-1": JOURNAL_PANEL,
    "panel-journal-2": JOURNAL_PANEL,
}

panel_state = {
    "panel-todo-1": {"items": [{"text": "Try the event route", "done": False}]},
    "panel-journal-1": {"text": "Write a thought, then press Enter."},
    "panel-journal-2": {"text": "This journal remembers its own text."},
}

panel_widgets = {
    "panel-todo-1": {},
    "panel-journal-1": {},
    "panel-journal-2": {},
}

top_widgets = {}


def request_idle_processing():
    """Ensure that one controlled processing pass is waiting."""
    if not g["processing_scheduled"]:
        g["processing_scheduled"] = True
        g["root"].after_idle(process_pending_work)


def queue_global_event(event_type, **data):
    global_event_queue.append({"type": event_type, **data})
    request_idle_processing()


def queue_panel_event(panel_id, event_type, **data):
    panel_event_queues[panel_id].append(
        {"type": event_type, "panel_id": panel_id, **data}
    )
    request_idle_processing()


def queue_panel_reconfiguration(position_id, new_panel_id):
    panel_reconfiguration_queue.append(
        {"position_id": position_id, "new_panel_id": new_panel_id}
    )
    request_idle_processing()


def target_consequences(target):
    """Load the consequence destination into the current queue register."""
    if target == "global":
        reg["target_consequences"] = "global"
    elif target == "active":
        reg["target_consequences"] = reg["panel_id"]
    else:
        raise ValueError(f"unknown consequence queue target: {target}")


def queue_consequence(consequence_type, data):
    """Append a consequence using the already-selected queue target."""
    if reg["target_consequences"] is None:
        raise RuntimeError(
            "target_consequences() must be called before queue_consequence()"
        )
    gui_consequence_queue.append(
        {
            "target": reg["target_consequences"],
            "type": consequence_type,
            "data": data,
        }
    )


def handle_when_previous_day_button_is_clicked():
    if not g["shut-up"]:
        queue_global_event(SELECT_PREVIOUS_DAY)


def handle_when_next_day_button_is_clicked():
    if not g["shut-up"]:
        queue_global_event(SELECT_NEXT_DAY)


def handle_when_today_button_is_clicked():
    if not g["shut-up"]:
        queue_global_event(SELECT_TODAY)


def handle_when_heartbeat_timer_fires():
    if not g["shut-up"]:
        queue_global_event(SECOND_ELAPSED)
    g["root"].after(1000, handle_when_heartbeat_timer_fires)


def handle_when_todo_toggle_button_is_clicked(panel_id):
    if not g["shut-up"]:
        queue_panel_event(panel_id, TOGGLE_TODO)


def handle_when_journal_entry_is_submitted(event, panel_id):
    if not g["shut-up"]:
        queue_panel_event(panel_id, EDIT_JOURNAL, text=event.widget.get())


def handle_when_orientation_text_is_submitted(event):
    if not g["shut-up"]:
        queue_global_event(EDIT_ORIENTATION, text=event.widget.get())


def handle_when_panel_switch_button_is_clicked(position_id):
    if g["shut-up"]:
        return
    current_panel_id = position_panel[position_id]
    if current_panel_id == "panel-todo-1":
        new_panel_id = "panel-journal-2"
    else:
        new_panel_id = "panel-todo-1"
    queue_panel_reconfiguration(position_id, new_panel_id)


def process_pending_work():
    g["processing_scheduled"] = False
    process_global_events()
    process_panel_events()
    process_gui_consequences()

    if not global_event_queue and not any(panel_event_queues.values()):
        process_panel_reconfigurations()

    if (
        global_event_queue
        or any(panel_event_queues.values())
        or gui_consequence_queue
        or panel_reconfiguration_queue
    ):
        request_idle_processing()


def process_global_events():
    while global_event_queue:
        reg["event"] = global_event_queue.popleft()
        process_current_global_event()
    reg["event"] = None


def process_current_global_event():
    event_type = reg["event"]["type"]
    target_consequences("global")
    if event_type == SELECT_PREVIOUS_DAY:
        g["selected_day"] -= timedelta(days=1)
        queue_consequence("refresh_top_area", {})
    elif event_type == SELECT_NEXT_DAY:
        g["selected_day"] += timedelta(days=1)
        queue_consequence("refresh_top_area", {})
    elif event_type == SELECT_TODAY:
        g["selected_day"] = date.today()
        queue_consequence("refresh_top_area", {})
    elif event_type == SECOND_ELAPSED:
        g["heartbeat_count"] += 1
        queue_consequence("refresh_heartbeat", {})
    elif event_type == EDIT_ORIENTATION:
        g["orientation_text"] = reg["event"]["text"]
        queue_consequence("refresh_orientation", {})


def process_panel_events():
    for panel_id in panel_event_queues:
        while panel_event_queues[panel_id]:
            event = panel_event_queues[panel_id].popleft()
            load_active_panel_registers(event)
            target_consequences("active")
            panel_handler[reg["panel_type"]]()
    clear_active_panel_registers()


def process_panel_reconfigurations():
    while panel_reconfiguration_queue:
        request = panel_reconfiguration_queue.popleft()
        process_panel_reconfiguration(request)


def process_panel_reconfiguration(request):
    position_id = request["position_id"]
    old_panel_id = position_panel[position_id]
    new_panel_id = request["new_panel_id"]
    if old_panel_id == new_panel_id:
        return

    tear_down_panel_gui(position_id, old_panel_id)
    position_panel[position_id] = new_panel_id
    install_panel_gui(position_id)

    panel_event_queues[old_panel_id].clear()
    panel_event_queues[new_panel_id].clear()


def load_active_panel_registers(event):
    reg["event"] = event
    reg["panel_id"] = event["panel_id"]
    reg["panel_widgets"] = panel_widgets[reg["panel_id"]]
    reg["panel_state"] = panel_state[reg["panel_id"]]
    reg["panel_type"] = panel_type[reg["panel_id"]]


def clear_active_panel_registers():
    reg["event"] = None
    reg["panel_id"] = None
    reg["panel_widgets"] = None
    reg["panel_state"] = None
    reg["panel_type"] = None
    reg["position_id"] = None
    reg["position_widgets"] = None


def handle_todo_panel_event():
    state = reg["panel_state"]
    if reg["event"]["type"] == TOGGLE_TODO:
        state["items"][0]["done"] = not state["items"][0]["done"]
        queue_consequence("refresh_panel", {})


def handle_journal_panel_event():
    if reg["event"]["type"] == EDIT_JOURNAL:
        reg["panel_state"]["text"] = reg["event"]["text"]
        queue_consequence("refresh_panel", {})


panel_handler = {
    TODO_PANEL: handle_todo_panel_event,
    JOURNAL_PANEL: handle_journal_panel_event,
}


def process_gui_consequences():
    while gui_consequence_queue:
        consequence = gui_consequence_queue.popleft()
        if consequence["target"] == "global":
            update_global_gui(consequence)
        else:
            position_id = find_panel_position(consequence["target"])
            if position_id is None:
                continue
            load_active_gui_registers(position_id)
            panel_gui_handler[reg["panel_type"]]()
    clear_active_panel_registers()


def find_panel_position(panel_id):
    for position_id, assigned_panel_id in position_panel.items():
        if assigned_panel_id == panel_id:
            return position_id
    return None


def load_active_gui_registers(position_id):
    panel_id = position_panel[position_id]
    reg["position_id"] = position_id
    reg["position_widgets"] = position_widgets[position_id]
    reg["panel_id"] = panel_id
    reg["panel_widgets"] = panel_widgets[panel_id]
    reg["panel_state"] = panel_state[panel_id]
    reg["panel_type"] = panel_type[panel_id]


def install_panel_gui(position_id):
    load_active_gui_registers(position_id)
    panel_builder[reg["panel_type"]]()
    refresh_panel_host_label()
    clear_active_panel_registers()


def tear_down_panel_gui(position_id, panel_id):
    widgets = panel_widgets[panel_id]
    g["shut-up"] = True
    try:
        if widgets.get("content_frame") is not None:
            widgets["content_frame"].destroy()
        widgets.clear()
    finally:
        g["shut-up"] = False

    if reg["position_id"] == position_id:
        clear_active_panel_registers()


def refresh_panel_host_label():
    g["shut-up"] = True
    try:
        position_id = reg["position_id"]
        panel_id = reg["panel_id"]
        position_widgets[position_id]["panel_label"].configure(
            text=f"{panel_id} / {reg['panel_type']}"
        )
    finally:
        g["shut-up"] = False


def update_global_gui(consequence):
    g["shut-up"] = True
    try:
        if consequence["type"] == "refresh_top_area":
            top_widgets["date_label"].configure(text=g["selected_day"].isoformat())
        elif consequence["type"] == "refresh_heartbeat":
            top_widgets["heartbeat_label"].configure(
                text=f"heartbeat {g['heartbeat_count']}"
            )
        elif consequence["type"] == "refresh_orientation":
            top_widgets["orientation_var"].set(g["orientation_text"])
    finally:
        g["shut-up"] = False


def update_todo_panel_gui():
    g["shut-up"] = True
    try:
        state = reg["panel_state"]
        widgets = reg["panel_widgets"]
        item = state["items"][0]
        widgets["status_label"].configure(
            text=("done" if item["done"] else "open") + ": " + item["text"]
        )
    finally:
        g["shut-up"] = False


def update_journal_panel_gui():
    g["shut-up"] = True
    try:
        reg["panel_widgets"]["text_var"].set(reg["panel_state"]["text"])
    finally:
        g["shut-up"] = False


panel_gui_handler = {
    TODO_PANEL: update_todo_panel_gui,
    JOURNAL_PANEL: update_journal_panel_gui,
}


def build_top_area(parent):
    area = ttk.Frame(parent, padding=8)
    area.pack(fill="x")
    ttk.Button(area, text="<", command=handle_when_previous_day_button_is_clicked).pack(side="left")
    top_widgets["date_label"] = ttk.Label(area, width=12, anchor="center")
    top_widgets["date_label"].pack(side="left", padx=6)
    top_widgets["date_label"].configure(text=g["selected_day"].isoformat())
    ttk.Button(area, text= "今", command=handle_when_today_button_is_clicked).pack(side="left")
    ttk.Button(area, text=">", command=handle_when_next_day_button_is_clicked).pack(side="left")
    top_widgets["orientation_var"] = tk.StringVar(value=g["orientation_text"])
    orientation = ttk.Entry(area, textvariable=top_widgets["orientation_var"], width=28)
    orientation.pack(side="left", padx=12)
    orientation.bind("<Return>", handle_when_orientation_text_is_submitted)
    top_widgets["heartbeat_label"] = ttk.Label(area, text="heartbeat 0")
    top_widgets["heartbeat_label"].pack(side="right")


def build_todo_panel_gui():
    panel_id = reg["panel_id"]
    host = reg["position_widgets"]["host"]
    content_frame = ttk.Frame(host, padding=8)
    content_frame.pack(fill="both", expand=True)
    panel_widgets[panel_id]["content_frame"] = content_frame
    panel_widgets[panel_id]["status_label"] = ttk.Label(content_frame)
    panel_widgets[panel_id]["status_label"].pack(anchor="w", pady=(0, 8))
    ttk.Button(
        content_frame,
        text="Toggle first item",
        command=lambda: handle_when_todo_toggle_button_is_clicked(panel_id),
    ).pack(anchor="w")
    update_todo_panel_gui()


def build_journal_panel_gui():
    panel_id = reg["panel_id"]
    host = reg["position_widgets"]["host"]
    content_frame = ttk.Frame(host, padding=8)
    content_frame.pack(fill="both", expand=True)
    panel_widgets[panel_id]["content_frame"] = content_frame
    text_var = tk.StringVar(value=panel_state[panel_id]["text"])
    panel_widgets[panel_id]["text_var"] = text_var
    entry = ttk.Entry(content_frame, textvariable=text_var, width=36)
    entry.pack(fill="x")
    entry.bind(
        "<Return>",
        lambda event: handle_when_journal_entry_is_submitted(event, panel_id),
    )
    ttk.Label(content_frame, text="Press Enter to queue an edit event.").pack(
        anchor="w", pady=(8, 0)
    )


panel_builder = {
    TODO_PANEL: build_todo_panel_gui,
    JOURNAL_PANEL: build_journal_panel_gui,
}


def build_panel_host(parent, position_id):
    host = ttk.LabelFrame(parent, text=position_id, padding=4)
    host.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    position_widgets[position_id]["host"] = host
    position_widgets[position_id]["panel_label"] = ttk.Label(host)
    position_widgets[position_id]["panel_label"].pack(anchor="w", padx=8, pady=(4, 0))
    if position_id == "position-1":
        ttk.Button(
            host,
            text="Replace panel",
            command=lambda: handle_when_panel_switch_button_is_clicked(position_id),
        ).pack(anchor="w", padx=8, pady=(4, 0))


def build_experiment_window():
    root = tk.Tk()
    g["root"] = root
    root.title("Today — interaction model experiment")
    build_top_area(root)
    panels = ttk.Frame(root)
    panels.pack(fill="both", expand=True)
    build_panel_host(panels, "position-1")
    build_panel_host(panels, "position-2")
    install_panel_gui("position-1")
    install_panel_gui("position-2")
    root.after(1000, handle_when_heartbeat_timer_fires)
    return root


def main():
    root = build_experiment_window()
    root.mainloop()


if __name__ == "__main__":
    main()
