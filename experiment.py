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
    "processing_event": None,
    "active_panel_id": None,
    "active_panel_widgets": None,
    "active_panel_state": None,
    "active_panel_type": None,
    "heartbeat_count": 0,
    "orientation_text": "orientation",
}

global_event_queue = deque()
panel_event_queues = {
    "panel-1": deque(),
    "panel-2": deque(),
}
gui_consequence_queue = deque()

panel_type = {
    "panel-1": TODO_PANEL,
    "panel-2": JOURNAL_PANEL,
}

panel_state = {
    "panel-1": {"items": [{"text": "Try the event route", "done": False}]},
    "panel-2": {"text": "Write a thought, then press Enter."},
}

panel_widgets = {
    "panel-1": {},
    "panel-2": {},
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


def queue_gui_consequence(target, consequence_type, **data):
    gui_consequence_queue.append(
        {"target": target, "type": consequence_type, **data}
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


def process_pending_work():
    g["processing_scheduled"] = False
    process_global_events()
    process_panel_events()
    process_gui_consequences()

    if global_event_queue or any(panel_event_queues.values()) or gui_consequence_queue:
        request_idle_processing()


def process_global_events():
    while global_event_queue:
        g["processing_event"] = global_event_queue.popleft()
        process_current_global_event()
    g["processing_event"] = None


def process_current_global_event():
    event_type = g["processing_event"]["type"]
    if event_type == SELECT_PREVIOUS_DAY:
        g["selected_day"] -= timedelta(days=1)
        queue_gui_consequence("global", "refresh_top_area")
    elif event_type == SELECT_NEXT_DAY:
        g["selected_day"] += timedelta(days=1)
        queue_gui_consequence("global", "refresh_top_area")
    elif event_type == SELECT_TODAY:
        g["selected_day"] = date.today()
        queue_gui_consequence("global", "refresh_top_area")
    elif event_type == SECOND_ELAPSED:
        g["heartbeat_count"] += 1
        queue_gui_consequence("global", "refresh_heartbeat")
    elif event_type == EDIT_ORIENTATION:
        g["orientation_text"] = g["processing_event"]["text"]
        queue_gui_consequence("global", "refresh_orientation")


def process_panel_events():
    for panel_id in panel_event_queues:
        while panel_event_queues[panel_id]:
            event = panel_event_queues[panel_id].popleft()
            load_active_panel_registers(event)
            panel_handler[g["active_panel_type"]]()
    clear_active_panel_registers()


def load_active_panel_registers(event):
    g["processing_event"] = event
    g["active_panel_id"] = event["panel_id"]
    g["active_panel_widgets"] = panel_widgets[g["active_panel_id"]]
    g["active_panel_state"] = panel_state[g["active_panel_id"]]
    g["active_panel_type"] = panel_type[g["active_panel_id"]]


def clear_active_panel_registers():
    g["processing_event"] = None
    g["active_panel_id"] = None
    g["active_panel_widgets"] = None
    g["active_panel_state"] = None
    g["active_panel_type"] = None


def handle_todo_panel_event():
    state = g["active_panel_state"]
    if g["processing_event"]["type"] == TOGGLE_TODO:
        state["items"][0]["done"] = not state["items"][0]["done"]
        queue_gui_consequence(g["active_panel_id"], "refresh_panel")


def handle_journal_panel_event():
    if g["processing_event"]["type"] == EDIT_JOURNAL:
        g["active_panel_state"]["text"] = g["processing_event"]["text"]
        queue_gui_consequence(g["active_panel_id"], "refresh_panel")


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
            load_active_gui_registers(consequence["target"])
            panel_gui_handler[g["active_panel_type"]]()
    clear_active_panel_registers()


def load_active_gui_registers(panel_id):
    g["active_panel_id"] = panel_id
    g["active_panel_widgets"] = panel_widgets[panel_id]
    g["active_panel_state"] = panel_state[panel_id]
    g["active_panel_type"] = panel_type[panel_id]


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
        state = g["active_panel_state"]
        widgets = g["active_panel_widgets"]
        item = state["items"][0]
        widgets["status_label"].configure(
            text=("done" if item["done"] else "open") + ": " + item["text"]
        )
    finally:
        g["shut-up"] = False


def update_journal_panel_gui():
    g["shut-up"] = True
    try:
        g["active_panel_widgets"]["text_var"].set(g["active_panel_state"]["text"])
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
    ttk.Button(area, text= "今", command=handle_when_today_button_is_clicked).pack(side="left")
    ttk.Button(area, text=">", command=handle_when_next_day_button_is_clicked).pack(side="left")
    top_widgets["orientation_var"] = tk.StringVar(value=g["orientation_text"])
    orientation = ttk.Entry(area, textvariable=top_widgets["orientation_var"], width=28)
    orientation.pack(side="left", padx=12)
    orientation.bind("<Return>", handle_when_orientation_text_is_submitted)
    top_widgets["heartbeat_label"] = ttk.Label(area, text="heartbeat 0")
    top_widgets["heartbeat_label"].pack(side="right")
    queue_global_event(SELECT_TODAY)


def build_todo_panel(parent, panel_id):
    frame = ttk.LabelFrame(parent, text="Panel A — TODO", padding=8)
    frame.pack(side="left", fill="both", expand=True, padx=(8, 4), pady=8)
    panel_widgets[panel_id]["status_label"] = ttk.Label(frame)
    panel_widgets[panel_id]["status_label"].pack(anchor="w", pady=(0, 8))
    ttk.Button(
        frame,
        text="Toggle first item",
        command=lambda: handle_when_todo_toggle_button_is_clicked(panel_id),
    ).pack(anchor="w")
    queue_panel_event(panel_id, TOGGLE_TODO)


def build_journal_panel(parent, panel_id):
    frame = ttk.LabelFrame(parent, text="Panel B — JOURNAL", padding=8)
    frame.pack(side="left", fill="both", expand=True, padx=(4, 8), pady=8)
    text_var = tk.StringVar(value=panel_state[panel_id]["text"])
    panel_widgets[panel_id]["text_var"] = text_var
    entry = ttk.Entry(frame, textvariable=text_var, width=36)
    entry.pack(fill="x")
    entry.bind(
        "<Return>",
        lambda event: handle_when_journal_entry_is_submitted(event, panel_id),
    )
    ttk.Label(frame, text="Press Enter to queue an edit event.").pack(anchor="w", pady=(8, 0))


def build_experiment_window():
    root = tk.Tk()
    g["root"] = root
    root.title("Today — interaction model experiment")
    build_top_area(root)
    panels = ttk.Frame(root)
    panels.pack(fill="both", expand=True)
    build_todo_panel(panels, "panel-1")
    build_journal_panel(panels, "panel-2")
    root.after(1000, handle_when_heartbeat_timer_fires)
    return root


def main():
    root = build_experiment_window()
    root.mainloop()


if __name__ == "__main__":
    main()
