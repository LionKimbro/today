"""Today mobile-stacks spike: a two-panel daily cockpit, before its next execution design.

This file salvages the useful visual and data-model parts of experiment 04.
It deliberately performs its current demo actions directly: load a day, edit
a panel, save its day bundle, and render the result.  It contains no Mobile
Stacks execution architecture.

Run normally:

    python src/parts/05_mobile-stacks.py

Use ``--headless`` to exercise the data model without making a Tk window.
"""

from copy import deepcopy
from datetime import date, timedelta
import sys
import tkinter as tk
from tkinter import ttk


TODO_PANEL = "TODO"
JOURNAL_PANEL = "JOURNAL"
HEARTBEAT_INTERVAL_MS = 15_000


# Central Tk-system facts.
g = {
    "root": None,
    "headless": False,
    "selected-day": date.today(),
    "orientation": "orientation",
    "heartbeat": 0,
    "rendered-day": None,
}

# Tk widgets by role.  Only Tk callbacks and rendering functions use this.
widgets = {}

# Tk-only panel placement records.
position_widgets = {
    "position-1": {},
    "position-2": {},
}

# Tk presentation data copied from the latest rendered day bundle.  This is
# not authoritative memory.
panel_types = {}
panel_records = {}
panel_widgets = {}

# Authoritative in-memory data.  A day owns position choices; a panel names
# its owning day and contains its own type and state.
memory = {"days": {}, "panels": {}}

# Simulated persisted data.  Each disk day is one self-contained day bundle.
disk_store = {"days": {}}


def log(line):
    """Present a small direct-action trace in the console and Tk display."""
    print(line, flush=True)
    trace = widgets.get("trace")
    if trace is not None:
        trace.insert("end", line + "\n")
        trace.see("end")


def current_day_text():
    return g["selected-day"].isoformat()


def make_blank_day(day_text):
    """Make sample persisted content for a day that has not yet been saved."""
    todo_id = f"panel-{day_text}-todo-1"
    alternate_todo_id = f"panel-{day_text}-todo-2"
    journal_id = f"panel-{day_text}-journal-1"
    alternate_journal_id = f"panel-{day_text}-journal-2"
    return {
        "day": day_text,
        "position-panel": {
            "position-1": todo_id,
            "position-2": journal_id,
        },
        "panels": {
            todo_id: {
                "type": TODO_PANEL,
                "state": {"items": [{"text": f"Try the panel controls on {day_text}", "done": False}]},
            },
            alternate_todo_id: {
                "type": TODO_PANEL,
                "state": {"items": [{"text": f"An alternate TODO for {day_text}", "done": False}]},
            },
            journal_id: {
                "type": JOURNAL_PANEL,
                "state": {"text": f"Write a thought for {day_text}."},
            },
            alternate_journal_id: {
                "type": JOURNAL_PANEL,
                "state": {"text": f"This alternate journal remembers {day_text}."},
            },
        },
    }


def install_day_bundle(day_text, day_bundle):
    """Split one persisted day bundle into authoritative day and panel tables."""
    day_record = deepcopy(day_bundle)
    panels = day_record.pop("panels")
    if day_record["day"] != day_text:
        raise ValueError(f"day bundle key {day_text} does not match {day_record['day']}")

    for panel_id, panel_record in list(memory["panels"].items()):
        if panel_record["day"] == day_text:
            memory["panels"].pop(panel_id)

    memory["days"][day_text] = day_record
    for panel_id, panel_record in panels.items():
        panel = deepcopy(panel_record)
        panel["day"] = day_text
        memory["panels"][panel_id] = panel
    check_day_layout(day_text)


def make_day_bundle(day_text):
    """Join one authoritative day record and its owned panels for persistence."""
    check_day_layout(day_text)
    day_bundle = deepcopy(memory["days"][day_text])
    day_bundle["panels"] = {
        panel_id: deepcopy(panel_record)
        for panel_id, panel_record in memory["panels"].items()
        if panel_record["day"] == day_text
    }
    return day_bundle


def check_day_layout(day_text):
    """Verify that every visible day position names a panel owned by that day."""
    day_record = memory["days"][day_text]
    for position_id, panel_id in day_record["position-panel"].items():
        panel_record = memory["panels"].get(panel_id)
        if panel_record is None:
            raise RuntimeError(f"{position_id} refers to missing panel {panel_id}")
        if panel_record["day"] != day_text:
            raise RuntimeError(f"panel {panel_id} is not owned by {day_text}")


def load_day(day_text):
    """Load one simulated disk day into the authoritative memory layout."""
    if day_text not in disk_store["days"]:
        disk_store["days"][day_text] = make_blank_day(day_text)
        log(f"disk created sample day {day_text}")
    install_day_bundle(day_text, disk_store["days"][day_text])
    log(f"loaded {day_text}: split disk bundle into days and panels")


def save_day(day_text):
    """Persist the current authoritative representation of one day."""
    disk_store["days"][day_text] = make_day_bundle(day_text)
    log(f"saved {day_text}: joined day and owned panels")


def render_day(day_text):
    """Copy current authoritative data into Tk's presentation snapshot and draw it."""
    day_record = make_day_bundle(day_text)
    g["rendered-day"] = day_text
    panel_records.clear()
    panel_types.clear()
    for panel_id, panel_record in day_record["panels"].items():
        panel_records[panel_id] = deepcopy(panel_record)
        panel_types[panel_id] = panel_record["type"]

    if not g["headless"]:
        widgets["date-label"].configure(text=day_text)
        for position_id, panel_id in day_record["position-panel"].items():
            mount_panel(position_id, panel_id)
    log(f"rendered {day_text}")


def load_and_render_selected_day():
    day_text = current_day_text()
    load_day(day_text)
    render_day(day_text)


def set_todo_done(panel_id, desired_value):
    panel_record = memory["panels"][panel_id]
    panel_record["state"]["items"][0]["done"] = desired_value
    day_text = panel_record["day"]
    save_day(day_text)
    render_day(day_text)


def set_journal_text(panel_id, text):
    panel_record = memory["panels"][panel_id]
    panel_record["state"]["text"] = text
    day_text = panel_record["day"]
    save_day(day_text)
    render_day(day_text)


def replace_panel_at_position(position_id):
    """Choose an unmounted alternate-type panel, make it visible, and save."""
    day_text = g["rendered-day"]
    current_panel = memory["days"][day_text]["position-panel"][position_id]
    current_type = memory["panels"][current_panel]["type"]
    desired_type = JOURNAL_PANEL if current_type == TODO_PANEL else TODO_PANEL
    mounted_panels = set(memory["days"][day_text]["position-panel"].values())
    for panel_id, panel_record in memory["panels"].items():
        if panel_record["day"] == day_text and panel_record["type"] == desired_type and panel_id not in mounted_panels:
            memory["days"][day_text]["position-panel"][position_id] = panel_id
            save_day(day_text)
            render_day(day_text)
            log(f"replaced {position_id} with {panel_id}")
            return
    raise RuntimeError(f"no unmounted {desired_type} panel is available for {position_id}")


def clear_position_panel(position_id):
    record = position_widgets[position_id]
    old_panel = record.get("mounted-panel")
    if old_panel is not None:
        panel_widgets[old_panel]["content"].destroy()
        panel_widgets.pop(old_panel, None)


def mount_panel(position_id, panel_id):
    clear_position_panel(position_id)
    position_widgets[position_id]["mounted-panel"] = panel_id
    build_panel_in_position(position_id, panel_id, panel_records[panel_id])


def build_panel_in_position(position_id, panel_id, panel_record):
    host = position_widgets[position_id]["host"]
    position_widgets[position_id]["panel-label"].configure(text=f"{panel_id} / {panel_record['type']}")
    content = ttk.Frame(host, padding=8)
    content.pack(fill="both", expand=True)
    panel_widgets[panel_id] = {"content": content}
    if panel_record["type"] == TODO_PANEL:
        build_todo_panel_gui(panel_id, panel_record)
    else:
        build_journal_panel_gui(panel_id, panel_record)


def build_todo_panel_gui(panel_id, panel_record):
    record = panel_widgets[panel_id]
    item = panel_record["state"]["items"][0]
    ttk.Label(
        record["content"],
        text=("done" if item["done"] else "open") + ": " + item["text"],
    ).pack(anchor="w", pady=(0, 8))
    ttk.Button(
        record["content"],
        text="Toggle first item",
        command=lambda: handle_when_todo_toggle_button_is_clicked(panel_id, not item["done"]),
    ).pack(anchor="w")


def build_journal_panel_gui(panel_id, panel_record):
    record = panel_widgets[panel_id]
    text_var = tk.StringVar(value=panel_record["state"]["text"])
    record["text-var"] = text_var
    entry = ttk.Entry(record["content"], textvariable=text_var, width=42)
    entry.pack(fill="x")
    entry.bind("<Return>", lambda event: handle_when_journal_entry_is_submitted(event, panel_id))
    ttk.Label(record["content"], text="Press Enter to save this journal edit.").pack(anchor="w", pady=(8, 0))


def build_panel_host(parent, position_id):
    host = ttk.LabelFrame(parent, text=position_id, padding=4)
    host.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    position_widgets[position_id]["host"] = host
    position_widgets[position_id]["panel-label"] = ttk.Label(host)
    position_widgets[position_id]["panel-label"].pack(anchor="w", padx=8, pady=(4, 0))
    ttk.Button(
        host,
        text="Replace panel",
        command=lambda: handle_when_panel_replace_button_is_clicked(position_id),
    ).pack(anchor="w", padx=8, pady=(4, 0))


def handle_when_previous_day_button_is_clicked():
    g["selected-day"] -= timedelta(days=1)
    load_and_render_selected_day()


def handle_when_next_day_button_is_clicked():
    g["selected-day"] += timedelta(days=1)
    load_and_render_selected_day()


def handle_when_today_button_is_clicked():
    g["selected-day"] = date.today()
    load_and_render_selected_day()


def handle_when_orientation_text_is_submitted(event):
    g["orientation"] = event.widget.get()
    log(f"orientation set to {g['orientation']!r}")


def handle_when_todo_toggle_button_is_clicked(panel_id, desired_value):
    set_todo_done(panel_id, desired_value)


def handle_when_journal_entry_is_submitted(event, panel_id):
    set_journal_text(panel_id, event.widget.get())


def handle_when_panel_replace_button_is_clicked(position_id):
    replace_panel_at_position(position_id)


def handle_when_heartbeat_timer_fires():
    g["heartbeat"] += 1
    widgets["heartbeat-label"].configure(text=f"heartbeat {g['heartbeat']}")
    g["root"].after(HEARTBEAT_INTERVAL_MS, handle_when_heartbeat_timer_fires)


def handle_when_clear_trace_button_is_clicked():
    widgets["trace"].delete("1.0", "end")


def handle_when_main_window_is_closed():
    g["root"].destroy()


def build_tk_interface():
    root = g["root"]
    root.title("Today — mobile stacks donor salvage")
    root.geometry("1060x650")

    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Button(top, text="<", command=handle_when_previous_day_button_is_clicked).pack(side="left")
    widgets["date-label"] = ttk.Label(top, width=12, anchor="center")
    widgets["date-label"].pack(side="left", padx=6)
    ttk.Button(top, text="今", command=handle_when_today_button_is_clicked).pack(side="left")
    ttk.Button(top, text=">", command=handle_when_next_day_button_is_clicked).pack(side="left", padx=(4, 12))
    orientation_var = tk.StringVar(value=g["orientation"])
    orientation = ttk.Entry(top, textvariable=orientation_var, width=28)
    orientation.pack(side="left")
    orientation.bind("<Return>", handle_when_orientation_text_is_submitted)
    widgets["heartbeat-label"] = ttk.Label(top, text="heartbeat 0")
    widgets["heartbeat-label"].pack(side="right")

    panels_frame = ttk.Frame(root)
    panels_frame.pack(fill="both", expand=True)
    build_panel_host(panels_frame, "position-1")
    build_panel_host(panels_frame, "position-2")

    activity = ttk.LabelFrame(root, text="activity", padding=4)
    activity.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    ttk.Button(activity, text="Clear activity", command=handle_when_clear_trace_button_is_clicked).pack(anchor="e")
    widgets["trace"] = tk.Text(activity, height=13, wrap="none")
    widgets["trace"].pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", handle_when_main_window_is_closed)


def run_headless_demo():
    """Exercise the donor data model without creating widgets."""
    load_and_render_selected_day()
    day_text = current_day_text()
    todo_id = memory["days"][day_text]["position-panel"]["position-1"]
    set_todo_done(todo_id, True)
    replace_panel_at_position("position-1")
    check_day_layout(day_text)
    print("headless data-model check completed", flush=True)


def main():
    g["headless"] = "--headless" in sys.argv
    if g["headless"]:
        run_headless_demo()
        return

    g["root"] = tk.Tk()
    build_tk_interface()
    load_and_render_selected_day()
    g["root"].after(HEARTBEAT_INTERVAL_MS, handle_when_heartbeat_timer_fires)
    g["root"].mainloop()


if __name__ == "__main__":
    main()
