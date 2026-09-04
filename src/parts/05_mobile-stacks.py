"""Today mobile-stacks spike: a two-panel cockpit with live traveling work.

Frames say only where and what: ``{"machine": ..., "op": ...}``.
Registers travel with the stack and hold the surviving situation.  Ordinary
Python handlers do the work, discover later work, and edit the live stack by
calling ``push()`` and ``drop()``.
"""

from collections import deque
from copy import deepcopy
from datetime import date, timedelta
from queue import Empty, Queue
from threading import Thread, current_thread
import sys
import time
import tkinter as tk
from tkinter import ttk


TODO_PANEL = "TODO"
JOURNAL_PANEL = "JOURNAL"
HEARTBEAT_INTERVAL_MS = 15_000
TK_PUMP_INTERVAL_MS = 25


g = {
    "root": None,
    "headless": False,
    "selected-day": date.today(),
    "orientation": "orientation",
    "heartbeat": 0,
    "rendered-day": None,
    "tk-pump-scheduled": False,
    "shutting-down": False,
    "completed-stack-count": 0,
}

# Tk-owned live widgets and presentation records.
widgets = {}
position_widgets = {"position-1": {}, "position-2": {}}
panel_records = {}
panel_widgets = {}

# Mem-owned authoritative data: positions live with days; panels name owners.
memory = {"days": {}, "panels": {}}

# Disk-owned simulated persistence: each entry is a complete persisted bundle.
disk_store = {"days": {}}

# Cross-machine activity messages.  Tk alone presents them in its text widget.
activity = Queue()

# Each machine owns its local run queue.  The inbound queues transfer stack
# ownership across threads; no sender touches a stack after putting it there.
machines = {
    "tk": {"in-queue": Queue(), "run-queue": deque(), "handler": None, "worker": False},
    "mem": {"in-queue": Queue(), "run-queue": deque(), "handler": None, "worker": True},
    "disk": {"in-queue": Queue(), "run-queue": deque(), "handler": None, "worker": True},
}

# One active-stack register per physical machine thread.  It is only the
# runtime's current work slot, not a second place to store application data.
runtime = {
    "tk": {"stack": None},
    "mem": {"stack": None},
    "disk": {"stack": None},
}


def log(line):
    """Publish an observation for Tk to display at its next safe pump."""
    activity.put(line)


def present_activity():
    """Let the Tk thread present all activity accumulated by every machine."""
    while True:
        try:
            line = activity.get_nowait()
        except Empty:
            return
        print(line, flush=True)
        trace = widgets.get("trace")
        if trace is not None:
            trace.insert("end", line + "\n")
            trace.see("end")


def active_runtime():
    return runtime[current_thread().name]


def active_stack():
    stack = active_runtime()["stack"]
    if stack is None:
        raise RuntimeError("this operation requires an active work stack")
    return stack


def top():
    frames = active_stack()["frames"]
    if not frames:
        raise RuntimeError("this operation requires an active frame")
    return frames[-1]


def set_register(name, value):
    active_stack()["registers"][name] = value


def get_register(name):
    return active_stack()["registers"][name]


def push(machine_name, operation):
    """Put the next small unit of control on the active live work stack."""
    active_stack()["frames"].append({"machine": machine_name, "op": operation})


def drop():
    """Remove the active handler's own frame from the live work stack."""
    active_stack()["frames"].pop()


def begin_stack(machine_name, operation):
    """Start one small work stack on the calling machine's active-stack slot."""
    if active_runtime()["stack"] is not None:
        raise RuntimeError("cannot begin a stack while another stack is active")
    active_runtime()["stack"] = {"registers": {}, "frames": [{"machine": machine_name, "op": operation}]}


def submit_stack():
    """Queue the stack just constructed by the current Tk callback."""
    stack = active_stack()
    active_runtime()["stack"] = None
    queue_stack(stack)


def queue_stack(stack):
    """Give a stack to its top frame's machine, locally when already there."""
    if not stack["frames"]:
        g["completed-stack-count"] += 1
        log("stack completed")
        return
    machine_name = stack["frames"][-1]["machine"]
    if machine_name not in machines:
        raise ValueError(f"unknown machine {machine_name}")
    if current_thread().name == machine_name:
        machines[machine_name]["run-queue"].append(stack)
    else:
        machines[machine_name]["in-queue"].put(stack)


def admit_inbound_stacks(machine_name):
    machine = machines[machine_name]
    while True:
        try:
            stack = machine["in-queue"].get_nowait()
        except Empty:
            return
        if stack is None:
            machine["run-queue"].append(None)
        else:
            machine["run-queue"].append(stack)


def run_one_stack(machine_name):
    """Run one handler invocation, then let its edited top frame decide routing."""
    admit_inbound_stacks(machine_name)
    machine = machines[machine_name]
    if not machine["run-queue"]:
        return False
    stack = machine["run-queue"].popleft()
    if stack is None:
        return None

    active_runtime()["stack"] = stack
    frame = top()
    if frame["machine"] != machine_name:
        active_runtime()["stack"] = None
        queue_stack(stack)
        return True

    log(f"{machine_name}: {frame['op']}")
    machine["handler"]()
    stack = active_runtime()["stack"]
    active_runtime()["stack"] = None
    queue_stack(stack)
    return True


def run_worker_machine():
    machine_name = current_thread().name
    while True:
        result = run_one_stack(machine_name)
        if result is None:
            return
        if result is False:
            try:
                stack = machines[machine_name]["in-queue"].get(timeout=0.1)
            except Empty:
                continue
            machines[machine_name]["run-queue"].append(stack)


def schedule_tk_pump():
    if g["root"] is not None and not g["tk-pump-scheduled"]:
        g["tk-pump-scheduled"] = True
        g["root"].after(TK_PUMP_INTERVAL_MS, pump_tk_machine)


def pump_tk_machine():
    g["tk-pump-scheduled"] = False
    for _ in range(12):
        if not run_one_stack("tk"):
            break
    present_activity()
    if not g["shutting-down"]:
        schedule_tk_pump()


def make_blank_day(day_text):
    """Make sample disk content for a day not yet present in simulated storage."""
    todo_id = f"panel-{day_text}-todo-1"
    alternate_todo_id = f"panel-{day_text}-todo-2"
    journal_id = f"panel-{day_text}-journal-1"
    alternate_journal_id = f"panel-{day_text}-journal-2"
    return {
        "day": day_text,
        "position-panel": {"position-1": todo_id, "position-2": journal_id},
        "panels": {
            todo_id: {"type": TODO_PANEL, "state": {"items": [{"text": f"Try the panel controls on {day_text}", "done": False}]}},
            alternate_todo_id: {"type": TODO_PANEL, "state": {"items": [{"text": f"An alternate TODO for {day_text}", "done": False}]}},
            journal_id: {"type": JOURNAL_PANEL, "state": {"text": f"Write a thought for {day_text}."}},
            alternate_journal_id: {"type": JOURNAL_PANEL, "state": {"text": f"This alternate journal remembers {day_text}."}},
        },
    }


def install_day_bundle(day_text, day_bundle):
    """Mem-only: split a persisted bundle into the separate day and panel tables."""
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
    """Mem-only: join one day and its owned panels for a disk write or Tk render."""
    check_day_layout(day_text)
    day_bundle = deepcopy(memory["days"][day_text])
    day_bundle["panels"] = {
        panel_id: deepcopy(panel_record)
        for panel_id, panel_record in memory["panels"].items()
        if panel_record["day"] == day_text
    }
    return day_bundle


def check_day_layout(day_text):
    """Mem-only: each visible position must refer to a panel owned by its day."""
    for position_id, panel_id in memory["days"][day_text]["position-panel"].items():
        panel_record = memory["panels"].get(panel_id)
        if panel_record is None or panel_record["day"] != day_text:
            raise RuntimeError(f"{position_id} has invalid panel ownership: {panel_id}")


def handler_tk():
    operation = top()["op"]
    if operation == "REQUEST_LOAD_DAY":
        drop()
        push("mem", "LOAD_DAY")
        return
    if operation == "RENDER_DAY":
        render_day_from_register()
        drop()
        return
    if operation == "HANDLE_TODO_EVENT":
        drop()
        push("mem", "SET_TODO_STATE")
        return
    if operation == "HANDLE_JOURNAL_EVENT":
        drop()
        push("mem", "SET_JOURNAL_TEXT")
        return
    if operation == "HANDLE_REPLACE_PANEL":
        choose_replacement_panel()
        drop()
        push("mem", "SET_POSITION_PANEL")
        return
    if operation == "SET_ORIENTATION":
        g["orientation"] = get_register("orientation")
        drop()
        return
    if operation == "HEARTBEAT":
        g["heartbeat"] += 1
        widgets["heartbeat-label"].configure(text=f"heartbeat {g['heartbeat']}")
        drop()
        return
    raise ValueError(f"unknown tk operation {operation}")


def handler_mem():
    operation = top()["op"]
    if operation == "LOAD_DAY":
        handle_mem_load_day()
        return
    if operation == "AFTER_DISK_READ":
        day_text = get_register("day")
        install_day_bundle(day_text, get_register("day-record"))
        set_register("day-record", make_day_bundle(day_text))
        drop()
        push("tk", "RENDER_DAY")
        return
    if operation == "SET_TODO_STATE":
        panel_id = get_register("panel")
        memory["panels"][panel_id]["state"]["items"][0]["done"] = get_register("desired-state")
        prepare_save_and_render_for_panel(panel_id)
        return
    if operation == "SET_JOURNAL_TEXT":
        panel_id = get_register("panel")
        memory["panels"][panel_id]["state"]["text"] = get_register("journal-text")
        prepare_save_and_render_for_panel(panel_id)
        return
    if operation == "SET_POSITION_PANEL":
        day_text = get_register("day")
        panel_id = get_register("panel")
        if memory["panels"][panel_id]["day"] != day_text:
            raise RuntimeError(f"panel {panel_id} does not belong to {day_text}")
        memory["days"][day_text]["position-panel"][get_register("position")] = panel_id
        prepare_save_and_render(day_text)
        return
    raise ValueError(f"unknown mem operation {operation}")


def handle_mem_load_day():
    day_text = get_register("day")
    if day_text in memory["days"]:
        set_register("day-record", make_day_bundle(day_text))
        drop()
        push("tk", "RENDER_DAY")
        return
    drop()
    push("mem", "AFTER_DISK_READ")
    push("disk", "READ_DAY")


def prepare_save_and_render_for_panel(panel_id):
    prepare_save_and_render(memory["panels"][panel_id]["day"])


def prepare_save_and_render(day_text):
    set_register("day", day_text)
    set_register("day-record", make_day_bundle(day_text))
    drop()
    push("tk", "RENDER_DAY")
    push("disk", "WRITE_DAY")


def handler_disk():
    operation = top()["op"]
    day_text = get_register("day")
    if operation == "READ_DAY":
        if day_text not in disk_store["days"]:
            disk_store["days"][day_text] = make_blank_day(day_text)
            log(f"disk created sample day {day_text}")
        set_register("day-record", deepcopy(disk_store["days"][day_text]))
        drop()
        return
    if operation == "WRITE_DAY":
        disk_store["days"][day_text] = deepcopy(get_register("day-record"))
        log(f"disk saved {day_text}")
        drop()
        return
    raise ValueError(f"unknown disk operation {operation}")


def render_day_from_register():
    """Tk-only: project the supplied day snapshot into Tk presentation structures."""
    day_record = get_register("day-record")
    if day_record["day"] != current_day_text():
        log(f"tk ignored stale render for {day_record['day']}")
        return
    g["rendered-day"] = day_record["day"]
    panel_records.clear()
    for panel_id, panel_record in day_record["panels"].items():
        panel_records[panel_id] = deepcopy(panel_record)
    if not g["headless"]:
        widgets["date-label"].configure(text=day_record["day"])
        for position_id, panel_id in day_record["position-panel"].items():
            mount_panel(position_id, panel_id)


def choose_replacement_panel():
    """Tk-only: choose from the rendered presentation snapshot, then register it."""
    position_id = get_register("position")
    current_panel = position_widgets[position_id]["mounted-panel"]
    desired_type = JOURNAL_PANEL if panel_records[current_panel]["type"] == TODO_PANEL else TODO_PANEL
    mounted = {record.get("mounted-panel") for record in position_widgets.values()}
    for panel_id, panel_record in panel_records.items():
        if panel_record["type"] == desired_type and panel_id not in mounted:
            set_register("panel", panel_id)
            return
    raise RuntimeError(f"no unmounted {desired_type} panel is available for {position_id}")


def current_day_text():
    return g["selected-day"].isoformat()


def post_tk_work(operation):
    begin_stack("tk", operation)
    submit_stack()
    schedule_tk_pump()


def post_load_day():
    begin_stack("tk", "REQUEST_LOAD_DAY")
    set_register("day", current_day_text())
    submit_stack()
    schedule_tk_pump()


def clear_position_panel(position_id):
    old_panel = position_widgets[position_id].get("mounted-panel")
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
    item = panel_record["state"]["items"][0]
    content = panel_widgets[panel_id]["content"]
    ttk.Label(content, text=("done" if item["done"] else "open") + ": " + item["text"]).pack(anchor="w", pady=(0, 8))
    ttk.Button(content, text="Toggle first item", command=lambda: handle_when_todo_toggle_button_is_clicked(panel_id, not item["done"])).pack(anchor="w")


def build_journal_panel_gui(panel_id, panel_record):
    content = panel_widgets[panel_id]["content"]
    text_var = tk.StringVar(value=panel_record["state"]["text"])
    panel_widgets[panel_id]["text-var"] = text_var
    entry = ttk.Entry(content, textvariable=text_var, width=42)
    entry.pack(fill="x")
    entry.bind("<Return>", lambda event: handle_when_journal_entry_is_submitted(event, panel_id))
    ttk.Label(content, text="Press Enter to save this journal edit.").pack(anchor="w", pady=(8, 0))


def build_panel_host(parent, position_id):
    host = ttk.LabelFrame(parent, text=position_id, padding=4)
    host.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    position_widgets[position_id]["host"] = host
    position_widgets[position_id]["panel-label"] = ttk.Label(host)
    position_widgets[position_id]["panel-label"].pack(anchor="w", padx=8, pady=(4, 0))
    ttk.Button(host, text="Replace panel", command=lambda: handle_when_panel_replace_button_is_clicked(position_id)).pack(anchor="w", padx=8, pady=(4, 0))


def handle_when_previous_day_button_is_clicked():
    g["selected-day"] -= timedelta(days=1)
    post_load_day()


def handle_when_next_day_button_is_clicked():
    g["selected-day"] += timedelta(days=1)
    post_load_day()


def handle_when_today_button_is_clicked():
    g["selected-day"] = date.today()
    post_load_day()


def handle_when_orientation_text_is_submitted(event):
    begin_stack("tk", "SET_ORIENTATION")
    set_register("orientation", event.widget.get())
    submit_stack()
    schedule_tk_pump()


def handle_when_todo_toggle_button_is_clicked(panel_id, desired_value):
    begin_stack("tk", "HANDLE_TODO_EVENT")
    set_register("panel", panel_id)
    set_register("desired-state", desired_value)
    submit_stack()
    schedule_tk_pump()


def handle_when_journal_entry_is_submitted(event, panel_id):
    begin_stack("tk", "HANDLE_JOURNAL_EVENT")
    set_register("panel", panel_id)
    set_register("journal-text", event.widget.get())
    submit_stack()
    schedule_tk_pump()


def handle_when_panel_replace_button_is_clicked(position_id):
    begin_stack("tk", "HANDLE_REPLACE_PANEL")
    set_register("position", position_id)
    set_register("day", g["rendered-day"])
    submit_stack()
    schedule_tk_pump()


def handle_when_heartbeat_timer_fires():
    post_tk_work("HEARTBEAT")
    if not g["shutting-down"]:
        g["root"].after(HEARTBEAT_INTERVAL_MS, handle_when_heartbeat_timer_fires)


def handle_when_clear_activity_button_is_clicked():
    widgets["trace"].delete("1.0", "end")


def handle_when_main_window_is_closed():
    request_shutdown()
    g["root"].destroy()


def build_tk_interface():
    root = g["root"]
    root.title("Today — mobile stacks")
    root.geometry("1060x650")
    top_bar = ttk.Frame(root, padding=8)
    top_bar.pack(fill="x")
    ttk.Button(top_bar, text="<", command=handle_when_previous_day_button_is_clicked).pack(side="left")
    widgets["date-label"] = ttk.Label(top_bar, width=12, anchor="center")
    widgets["date-label"].pack(side="left", padx=6)
    ttk.Button(top_bar, text="今", command=handle_when_today_button_is_clicked).pack(side="left")
    ttk.Button(top_bar, text=">", command=handle_when_next_day_button_is_clicked).pack(side="left", padx=(4, 12))
    orientation = ttk.Entry(top_bar, width=28)
    orientation.insert(0, g["orientation"])
    orientation.pack(side="left")
    orientation.bind("<Return>", handle_when_orientation_text_is_submitted)
    widgets["heartbeat-label"] = ttk.Label(top_bar, text="heartbeat 0")
    widgets["heartbeat-label"].pack(side="right")

    panels_frame = ttk.Frame(root)
    panels_frame.pack(fill="both", expand=True)
    build_panel_host(panels_frame, "position-1")
    build_panel_host(panels_frame, "position-2")

    activity_frame = ttk.LabelFrame(root, text="mobile-stacks activity", padding=4)
    activity_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    ttk.Button(activity_frame, text="Clear activity", command=handle_when_clear_activity_button_is_clicked).pack(anchor="e")
    widgets["trace"] = tk.Text(activity_frame, height=13, wrap="none")
    widgets["trace"].pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", handle_when_main_window_is_closed)


def start_worker_threads():
    for machine_name in ("mem", "disk"):
        Thread(target=run_worker_machine, name=machine_name, daemon=True).start()


def request_shutdown():
    if g["shutting-down"]:
        return
    g["shutting-down"] = True
    machines["mem"]["in-queue"].put(None)
    machines["disk"]["in-queue"].put(None)


def run_headless_until_completed(target_count):
    deadline = time.monotonic() + 3
    while g["completed-stack-count"] < target_count and time.monotonic() < deadline:
        run_one_stack("tk")
        present_activity()
        time.sleep(0.005)
    if g["completed-stack-count"] < target_count:
        raise RuntimeError("headless mobile-stacks work did not complete")


def run_headless_demo():
    post_load_day()
    run_headless_until_completed(1)
    todo_id = next(panel_id for panel_id, panel in panel_records.items() if panel["type"] == TODO_PANEL)
    begin_stack("tk", "HANDLE_TODO_EVENT")
    set_register("panel", todo_id)
    set_register("desired-state", True)
    submit_stack()
    run_headless_until_completed(2)
    if not panel_records[todo_id]["state"]["items"][0]["done"]:
        raise RuntimeError("TODO event did not return an updated Tk presentation snapshot")
    journal_id = next(panel_id for panel_id, panel in panel_records.items() if panel["type"] == JOURNAL_PANEL)
    begin_stack("tk", "HANDLE_JOURNAL_EVENT")
    set_register("panel", journal_id)
    set_register("journal-text", "headless journal check")
    submit_stack()
    run_headless_until_completed(3)
    if panel_records[journal_id]["state"]["text"] != "headless journal check":
        raise RuntimeError("journal event did not return an updated Tk presentation snapshot")
    print("headless mobile-stacks check completed", flush=True)


def main():
    g["headless"] = "--headless" in sys.argv
    current_thread().name = "tk"
    machines["tk"]["handler"] = handler_tk
    machines["mem"]["handler"] = handler_mem
    machines["disk"]["handler"] = handler_disk
    start_worker_threads()
    if g["headless"]:
        run_headless_demo()
        request_shutdown()
        return
    g["root"] = tk.Tk()
    build_tk_interface()
    post_load_day()
    schedule_tk_pump()
    g["root"].after(HEARTBEAT_INTERVAL_MS, handle_when_heartbeat_timer_fires)
    g["root"].mainloop()


if __name__ == "__main__":
    main()
