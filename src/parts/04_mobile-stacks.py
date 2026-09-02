"""Today mobile-stacks spike: a small two-panel daily cockpit.

This is a readable experiment, not a framework.  It combines the visible
interaction shape of ``02_interaction-model.py`` with one explicit execution
rule:

    source machine -> target thread inbound queue -> target machine run queue

``disk`` owns simulated persisted day records.  ``mem`` owns the authoritative
in-memory day records.  ``tk`` owns widgets and renders a snapshot returned by
mem.  The stack is the continuation; its top frame says what happens next.

The current spike has one machine on each same-named thread.  The separate
thread registry is intentional: one future thread may list several machines,
each with its own run queue.

Run normally:

    python src/parts/04_mobile-stacks.py

Use ``--headless`` to verify the same logical scheduler without a display.
"""

from collections import deque
from copy import deepcopy
from datetime import date, timedelta
from queue import Empty, Queue
from threading import Lock, Thread, current_thread
import sys
import time
import tkinter as tk
from tkinter import ttk


SERIAL = "SERIAL"
YIELD = "YIELD"
STARTUP = "STARTUP"
SUSPENDED = "SUSPENDED"
STOP = "STOP"

TODO_PANEL = "TODO"
JOURNAL_PANEL = "JOURNAL"
HEARTBEAT_INTERVAL_MS = 15_000


# Central Tk-system facts:
# {"root": <Tk root>, "selected-day": <date>, "orientation": <str>,
#  "heartbeat": <int>, "tk-pump-scheduled": <bool>, "shutting-down": <bool>}
g = {
    "root": None,
    "headless": False,
    "selected-day": date.today(),
    "orientation": "orientation",
    "heartbeat": 0,
    "shutting-down": False,
    "tk-pump-scheduled": False,
    "next-stack-number": 1,
    "completed-stack-count": 0,
}

# Physical execution contexts.  ``current-machine`` and ``stack`` are
# thread-local registers stored in the record for the thread currently running:
# {"<thread-name>": {"in-queue": Queue(<delivery records>),
#                     "machine-names": ["<machine-name>", ...],
#                     "current-machine": "<machine-name>" | None,
#                     "stack": <stack> | None,
#                     "next-machine-index": <round-robin index>,
#                     "thread-type": "system" | "worker",
#                     "entry-fn": <thread procedure>,
#                     "thread-obj": <Thread for workers, None for tk>,
#                     "stop-requested": <bool>}}
threads = {}

# Semantic machines.  Each machine owns its own runnable stacks.  It does not
# have an inbound queue; its physical thread admits delivered stacks for it:
# {"<machine-name>": {"thread": "<thread-name>",
#                       "run-queue": deque(<runnable stacks>),
#                       "handler": <primitive-frame handler>}}
machines = {}

# Tk widget registry.  Only the tk machine touches this:
# {"date-label": <ttk.Label>, "orientation-var": <tk.StringVar>,
#  "heartbeat-label": <ttk.Label>, "trace": <tk.Text>, ...}
widgets = {}

# Tk-only panel placement and widget records:
# {"position-1": {"host": <ttk.LabelFrame>, "panel-label": <ttk.Label>,
#                  "mounted-panel": "<panel-id>" | None}, ...}
position_widgets = {
    "position-1": {},
    "position-2": {},
}

# {"<panel-id>": {"type": "TODO" | "JOURNAL"}}
panels = {}

# {"<panel-id>": {"content": <ttk.Frame>, "status": <ttk.Label>, ...}}
panel_widgets = {}

# {"<panel-type>": <Tk panel operation handler>}
panel_handlers = {}

# Authoritative memory, mutated only by mem primitive operations:
# {"days": {"YYYY-MM-DD": <complete day record>}}
memory = {"days": {}}

# Simulated disk records, mutated only by disk primitive operations:
# {"days": {"YYYY-MM-DD": <complete persisted day record>}}
disk_store = {"days": {}}

trace_lock = Lock()


def state():
    """Return the state record for this physical thread, by its own name."""
    return threads[current_thread().name]


def top():
    stack = state()["stack"]
    if stack is None:
        raise RuntimeError("this operation requires a current stack register")
    if not stack["frames"]:
        raise RuntimeError("current stack has no top frame")
    return stack["frames"][-1]


def trace(text):
    with trace_lock:
        print(text, flush=True)


def stack_summary(stack):
    if not stack["frames"]:
        return "<empty>"
    frame = stack["frames"][-1]
    return f"{frame['machine']}:{frame['op']}"


def result_summary(result):
    """Keep traces readable when a returned value is a complete day snapshot."""
    if isinstance(result, dict) and "day" in result and "panels" in result:
        return f"<day snapshot {result['day']}>"
    return repr(result)


def dump_stack(stack):
    parts = []
    for frame in stack["frames"]:
        name = frame.get("name", frame["op"])
        result = frame.get("child-result")
        suffix = "" if result is None else f" <- {result_summary(result)}"
        parts.append(f"{frame['machine']}:{name}{suffix}")
    return " [ " + " | ".join(parts) + " ]"


def log_stack(stack, machine_name, action):
    line = (
        f"[{machine_name:7}] stack={stack['id']:18} {action:40} "
        f"top={stack_summary(stack)}{dump_stack(stack)}"
    )
    trace(line)
    if machine_name == "tk" and widgets.get("trace") is not None:
        widgets["trace"].insert("end", line + "\n")
        widgets["trace"].see("end")


def make_instruction(machine_name, operation, data=None):
    """Make an inert instruction template; it becomes a frame only when pushed."""
    # {"machine": "<target machine>", "op": "<operation>", ...operation data...}
    instruction = {"machine": machine_name, "op": operation}
    if data is not None:
        instruction.update(data)
    return instruction


def make_serial_instruction(machine_name, name, steps):
    # {"machine": "<target>", "op": "SERIAL", "name": "<readable procedure>",
    #  "steps": [<instruction templates>], "ip": <next instruction index>,
    #  "child-result": <most recent child result>}
    return {
        "machine": machine_name,
        "op": SERIAL,
        "name": name,
        "steps": steps,
        "ip": 0,
        "child-result": None,
    }


def make_stack(stack_id, kind, root_instruction):
    """Make a new, inactive stack with its first frame already present."""
    # {"id": "<readable stack id>", "kind": "startup" | "ui",
    #  "frames": [<bottom frame>, ..., <top frame>]}
    return {
        "id": stack_id,
        "kind": kind,
        "frames": [deepcopy(root_instruction)],
    }


def push_frame(instruction):
    """Create a live frame by pushing this instruction onto the current stack."""
    stack = state()["stack"]
    frame = deepcopy(instruction)
    stack["frames"].append(frame)
    log_stack(stack, state()["current-machine"], f"PUSH {frame['machine']}:{frame['op']}")


def pop_frame(result):
    """Pop the current frame and explicitly return its result to its parent."""
    stack = state()["stack"]
    machine_name = state()["current-machine"]
    frame = stack["frames"].pop()
    log_stack(
        stack,
        machine_name,
        f"POP {frame['machine']}:{frame['op']} result={result_summary(result)}",
    )
    if stack["frames"]:
        stack["frames"][-1]["child-result"] = result
        log_stack(stack, machine_name, f"RETURN result={result_summary(result)} to parent")


def make_delivery(target_machine, stack):
    # {"machine": "<target machine>", "stack": <complete continuation stack>}
    return {"machine": target_machine, "stack": stack}


def send_stack_to_machine(stack, target_machine, source_name):
    """Relinquish a stack to the inbound queue of its target machine's thread."""
    target_thread = machines[target_machine]["thread"]
    log_stack(
        stack,
        source_name,
        f"TRANSFER -> machine={target_machine} via thread={target_thread}",
    )
    threads[target_thread]["in-queue"].put(make_delivery(target_machine, stack))


def transfer(target_machine):
    send_stack_to_machine(state()["stack"], target_machine, state()["current-machine"])


def admit_delivery_to_machine(thread_name, delivery):
    """The receiving thread places a delivered stack in its target machine queue."""
    machine_name = delivery["machine"]
    stack = delivery["stack"]
    if machines[machine_name]["thread"] != thread_name:
        raise RuntimeError(f"thread {thread_name} received work for {machine_name}")
    machines[machine_name]["run-queue"].append(stack)
    log_stack(stack, machine_name, f"THREAD {thread_name} RECEIVE -> machine run-queue")


def admit_thread_inbound():
    """Drain this thread's inbound queue into the run queues of its machines."""
    thread_name = current_thread().name
    thread_state = state()
    while True:
        try:
            delivery = thread_state["in-queue"].get_nowait()
        except Empty:
            return
        if delivery == STOP:
            thread_state["stop-requested"] = True
            trace(f"[{thread_name:7}] thread received STOP")
            continue
        admit_delivery_to_machine(thread_name, delivery)


def expand_serial():
    frame = top()
    if frame["ip"] == len(frame["steps"]):
        pop_frame(frame.get("child-result", f"{frame['name']} complete"))
        return
    instruction = frame["steps"][frame["ip"]]
    frame["ip"] += 1
    log_stack(
        state()["stack"],
        state()["current-machine"],
        f"IP advance {frame['name']} -> {frame['ip']}/{len(frame['steps'])}",
    )
    push_frame(instruction)


def yield_stack():
    stack = state()["stack"]
    machine_name = state()["current-machine"]
    pop_frame("yield consumed")
    machines[machine_name]["run-queue"].append(stack)
    log_stack(stack, machine_name, "YIELD -> back of this machine run-queue")


def complete_stack():
    stack = state()["stack"]
    log_stack(stack, state()["current-machine"], "COMPLETE stack")
    if stack["kind"] == "ui":
        g["completed-stack-count"] += 1
        refresh_machine_status()


def reconcile():
    """Use the current thread registers to advance one stack to a boundary."""
    while True:
        stack = state()["stack"]
        if not stack["frames"]:
            complete_stack()
            return
        frame = top()
        machine_name = state()["current-machine"]
        log_stack(stack, machine_name, "INSPECT top frame")
        if frame["machine"] != machine_name:
            transfer(frame["machine"])
            return
        if frame["op"] == YIELD:
            yield_stack()
            return
        if frame["op"] == SERIAL:
            expand_serial()
            continue
        result = machines[machine_name]["handler"]()
        if result == SUSPENDED:
            continue
        pop_frame(result)


def run_one_machine_on_current_thread():
    """Run one fair quantum and establish the two thread working registers."""
    thread_state = state()
    machine_names = thread_state["machine-names"]
    for offset in range(len(machine_names)):
        index = (thread_state["next-machine-index"] + offset) % len(machine_names)
        machine_name = machine_names[index]
        machine = machines[machine_name]
        if not machine["run-queue"]:
            continue
        thread_state["next-machine-index"] = (index + 1) % len(machine_names)
        thread_state["current-machine"] = machine_name
        thread_state["stack"] = machine["run-queue"].popleft()
        trace(f"[{current_thread().name:7}] register current-machine <- {machine_name}")
        trace(f"[{current_thread().name:7}] register stack <- {state()['stack']['id']}")
        try:
            log_stack(state()["stack"], machine_name, "RUN one reconciliation quantum")
            reconcile()
        finally:
            thread_state["stack"] = None
            thread_state["current-machine"] = None
            trace(f"[{current_thread().name:7}] registers stack/current-machine <- None")
        return True
    return False


def receive_blocking_delivery_for_current_thread():
    """Workers block only after all of their assigned machine queues are empty."""
    thread_name = current_thread().name
    delivery = state()["in-queue"].get()
    if delivery == STOP:
        state()["stop-requested"] = True
        trace(f"[{thread_name:7}] thread received STOP while idle")
        return
    admit_delivery_to_machine(thread_name, delivery)


def run_worker_thread():
    """Worker procedure; its own name identifies its record in ``threads``."""
    thread_name = current_thread().name
    trace(f"[{thread_name:7}] worker thread started for {state()['machine-names']}")
    while True:
        admit_thread_inbound()
        if run_one_machine_on_current_thread():
            continue
        if state()["stop-requested"]:
            break
        receive_blocking_delivery_for_current_thread()
    trace(f"[{thread_name:7}] worker thread stopped")


def pump_tk_thread():
    """Tk's non-blocking physical form of the same thread scheduler."""
    g["tk-pump-scheduled"] = False
    admit_thread_inbound()
    for _ in range(3):
        if not run_one_machine_on_current_thread():
            break
        admit_thread_inbound()
    if not g["shutting-down"]:
        g["tk-pump-scheduled"] = True
        g["root"].after(25, pump_tk_thread)


def schedule_tk_pump():
    if g["root"] is not None and not g["tk-pump-scheduled"]:
        g["tk-pump-scheduled"] = True
        g["root"].after_idle(pump_tk_thread)


def current_day_text():
    return g["selected-day"].isoformat()


def make_blank_day(day_text):
    """Make the one coherent record that disk persists and mem owns after loading."""
    todo_id = f"panel-{day_text}-todo-1"
    journal_id = f"panel-{day_text}-journal-1"
    alternate_journal_id = f"panel-{day_text}-journal-2"
    # {"day": "YYYY-MM-DD", "position-panel": {<position>: <panel-id>},
    #  "panels": {<panel-id>: {"type": <type>, "state": <panel state>}}}
    return {
        "day": day_text,
        "position-panel": {
            "position-1": todo_id,
            "position-2": journal_id,
        },
        "panels": {
            todo_id: {
                "type": TODO_PANEL,
                "state": {"items": [{"text": f"Try the stack route on {day_text}", "done": False}]},
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


def handler_tk():
    """Tk machine handler; panel-type routing happens after machine routing."""
    frame = top()
    if "panel" in frame:
        panel_id = frame["panel"]
        panel_type = panels[panel_id]["type"]
        log_stack(state()["stack"], "tk", f"PANEL route {panel_id} -> {panel_type}")
        return panel_handlers[panel_type]()
    return handle_tk_system_operation()


def handle_tk_system_operation():
    frame = top()
    if frame["op"] == STARTUP:
        if not g["headless"]:
            build_tk_interface_after_startup()
        post_load_day_stack(current_day_text())
        return "tk ready"
    if frame["op"] == "TK_RENDER_DAY":
        day_snapshot = state()["stack"]["frames"][-2]["child-result"]
        if day_snapshot["day"] != current_day_text():
            return f"Tk ignored stale day snapshot {day_snapshot['day']}"
        render_day_snapshot(day_snapshot)
        return f"Tk rendered {day_snapshot['day']}"
    if frame["op"] == "TK_SET_ORIENTATION":
        g["orientation"] = frame["text"]
        if widgets.get("orientation-var") is not None:
            widgets["orientation-var"].set(g["orientation"])
        return "orientation rendered"
    if frame["op"] == "TK_HEARTBEAT":
        g["heartbeat"] += 1
        if widgets.get("heartbeat-label") is not None:
            widgets["heartbeat-label"].configure(text=f"heartbeat {g['heartbeat']}")
        return "heartbeat rendered"
    raise ValueError(f"unknown tk operation: {frame['op']}")


def handle_todo_panel_operation():
    if top()["op"] == "TK_PANEL_EVENT":
        return "TODO panel accepted its event"
    raise ValueError(f"unknown TODO panel operation: {top()['op']}")


def handle_journal_panel_operation():
    if top()["op"] == "TK_PANEL_EVENT":
        return "JOURNAL panel accepted its event"
    raise ValueError(f"unknown JOURNAL panel operation: {top()['op']}")


def handler_mem():
    frame = top()
    if frame["op"] == STARTUP:
        return "mem ready"
    if frame["op"] == "MEM_LOAD_DAY":
        return handle_mem_load_day()
    if frame["op"] == "MEM_EDIT_AND_SAVE":
        return handle_mem_edit_and_save()
    if frame["op"] == "MEM_RETURN_DAY":
        return deepcopy(memory["days"][frame["day"]])
    raise ValueError(f"unknown mem operation: {frame['op']}")


def handle_mem_load_day():
    frame = top()
    if frame.get("stage") is None:
        frame["stage"] = "waiting-for-disk"
        push_frame(make_instruction("disk", "DISK_READ_DAY", {"day": frame["day"]}))
        return SUSPENDED
    memory["days"][frame["day"]] = deepcopy(frame["child-result"])
    return f"mem loaded {frame['day']}"


def apply_mem_edit(day_record, edit):
    if edit["kind"] == "toggle-todo":
        item = day_record["panels"][edit["panel"]]["state"]["items"][0]
        item["done"] = not item["done"]
    elif edit["kind"] == "edit-journal":
        day_record["panels"][edit["panel"]]["state"]["text"] = edit["text"]
    elif edit["kind"] == "replace-panel":
        position = edit["position"]
        current_panel = day_record["position-panel"][position]
        current_type = day_record["panels"][current_panel]["type"]
        candidates = day_record["panels"]
        if current_type == TODO_PANEL:
            day_record["position-panel"][position] = next(
                panel_id for panel_id, panel in candidates.items() if panel["type"] == JOURNAL_PANEL
            )
        else:
            day_record["position-panel"][position] = next(
                panel_id for panel_id, panel in candidates.items() if panel["type"] == TODO_PANEL
            )
    else:
        raise ValueError(f"unknown mem edit: {edit['kind']}")


def handle_mem_edit_and_save():
    frame = top()
    if frame.get("stage") is None:
        apply_mem_edit(memory["days"][frame["day"]], frame["edit"])
        frame["stage"] = "waiting-for-disk-save"
        push_frame(
            make_instruction(
                "disk",
                "DISK_WRITE_DAY",
                {"day": frame["day"], "day-record": deepcopy(memory["days"][frame["day"]])},
            )
        )
        return SUSPENDED
    return f"mem edit saved: {frame['child-result']}"


def handler_disk():
    frame = top()
    if frame["op"] == STARTUP:
        return "disk ready"
    if frame["op"] == "DISK_READ_DAY":
        if frame["day"] not in disk_store["days"]:
            disk_store["days"][frame["day"]] = make_blank_day(frame["day"])
        return deepcopy(disk_store["days"][frame["day"]])
    if frame["op"] == "DISK_WRITE_DAY":
        disk_store["days"][frame["day"]] = deepcopy(frame["day-record"])
        return f"disk wrote {frame['day']}"
    raise ValueError(f"unknown disk operation: {frame['op']}")


def make_load_day_stack(stack_id, day_text):
    mem_transaction = make_serial_instruction(
        "mem",
        "MEM_LOAD_TRANSACTION",
        [
            make_instruction("mem", "MEM_LOAD_DAY", {"day": day_text}),
            make_instruction("mem", YIELD),
            make_instruction("mem", "MEM_RETURN_DAY", {"day": day_text}),
        ],
    )
    root = make_serial_instruction(
        "tk",
        "TK_LOAD_AND_RENDER_DAY",
        [mem_transaction, make_instruction("tk", "TK_RENDER_DAY", {"day": day_text})],
    )
    return make_stack(stack_id, "ui", root)


def make_panel_edit_stack(stack_id, edit):
    panel_id = edit.get("panel")
    mem_transaction = make_serial_instruction(
        "mem",
        "MEM_EDIT_TRANSACTION",
        [
            make_instruction("mem", "MEM_EDIT_AND_SAVE", {"day": edit["day"], "edit": edit}),
            make_instruction("mem", YIELD),
            make_instruction("mem", "MEM_RETURN_DAY", {"day": edit["day"]}),
        ],
    )
    steps = []
    if panel_id is not None:
        steps.append(make_instruction("tk", "TK_PANEL_EVENT", {"panel": panel_id}))
    steps.extend([mem_transaction, make_instruction("tk", "TK_RENDER_DAY", {"day": edit["day"]})])
    return make_stack(stack_id, "ui", make_serial_instruction("tk", "TK_EDIT_AND_RENDER", steps))


def post_stack_to_tk(stack):
    send_stack_to_machine(stack, "tk", "user")
    schedule_tk_pump()


def next_stack_id(label):
    stack_id = f"{label}-{g['next-stack-number']}"
    g["next-stack-number"] += 1
    return stack_id


def post_load_day_stack(day_text):
    post_stack_to_tk(make_load_day_stack(next_stack_id("load-day"), day_text))


def post_panel_edit_stack(edit):
    post_stack_to_tk(make_panel_edit_stack(next_stack_id(edit["kind"]), edit))


def post_tk_instruction(operation, data):
    post_stack_to_tk(make_stack(next_stack_id(operation.lower()), "ui", make_instruction("tk", operation, data)))


def refresh_machine_status():
    label = widgets.get("machine-status")
    if label is not None:
        label.configure(text=f"completed stacks {g['completed-stack-count']}")


def handle_when_previous_day_button_is_clicked():
    g["selected-day"] -= timedelta(days=1)
    post_load_day_stack(current_day_text())


def handle_when_next_day_button_is_clicked():
    g["selected-day"] += timedelta(days=1)
    post_load_day_stack(current_day_text())


def handle_when_today_button_is_clicked():
    g["selected-day"] = date.today()
    post_load_day_stack(current_day_text())


def handle_when_orientation_text_is_submitted(event):
    post_tk_instruction("TK_SET_ORIENTATION", {"text": event.widget.get()})


def handle_when_todo_toggle_button_is_clicked(panel_id):
    post_panel_edit_stack({"kind": "toggle-todo", "day": current_day_text(), "panel": panel_id})


def handle_when_journal_entry_is_submitted(event, panel_id):
    post_panel_edit_stack(
        {"kind": "edit-journal", "day": current_day_text(), "panel": panel_id, "text": event.widget.get()}
    )


def handle_when_panel_replace_button_is_clicked(position_id):
    post_panel_edit_stack({"kind": "replace-panel", "day": current_day_text(), "position": position_id})


def handle_when_heartbeat_timer_fires():
    if not g["shutting-down"]:
        post_tk_instruction("TK_HEARTBEAT", {})
        g["root"].after(HEARTBEAT_INTERVAL_MS, handle_when_heartbeat_timer_fires)


def clear_position_panel(position_id):
    record = position_widgets[position_id]
    old_panel = record.get("mounted-panel")
    if old_panel is not None:
        panel_widgets[old_panel]["content"].destroy()
        panel_widgets.pop(old_panel, None)


def render_day_snapshot(day_record):
    """Tk receives a snapshot; it does not read or mutate ``memory`` directly."""
    if g["headless"]:
        return
    widgets["date-label"].configure(text=day_record["day"])
    for panel_id, panel_record in day_record["panels"].items():
        panels[panel_id] = {"type": panel_record["type"]}
    for position_id, panel_id in day_record["position-panel"].items():
        clear_position_panel(position_id)
        position_widgets[position_id]["mounted-panel"] = panel_id
        build_panel_in_position(position_id, panel_id, day_record["panels"][panel_id])


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
    record["status"] = ttk.Label(record["content"])
    record["status"].pack(anchor="w", pady=(0, 8))
    record["status"].configure(text=("done" if item["done"] else "open") + ": " + item["text"])
    ttk.Button(
        record["content"], text="Toggle first item",
        command=lambda: handle_when_todo_toggle_button_is_clicked(panel_id),
    ).pack(anchor="w")


def build_journal_panel_gui(panel_id, panel_record):
    record = panel_widgets[panel_id]
    text_var = tk.StringVar(value=panel_record["state"]["text"])
    record["text-var"] = text_var
    entry = ttk.Entry(record["content"], textvariable=text_var, width=42)
    entry.pack(fill="x")
    entry.bind("<Return>", lambda event: handle_when_journal_entry_is_submitted(event, panel_id))
    ttk.Label(record["content"], text="Press Enter to send this edit through tk → mem → disk → mem → tk.").pack(anchor="w", pady=(8, 0))


def build_panel_host(parent, position_id):
    host = ttk.LabelFrame(parent, text=position_id, padding=4)
    host.pack(side="left", fill="both", expand=True, padx=8, pady=8)
    position_widgets[position_id]["host"] = host
    position_widgets[position_id]["panel-label"] = ttk.Label(host)
    position_widgets[position_id]["panel-label"].pack(anchor="w", padx=8, pady=(4, 0))
    if position_id == "position-1":
        ttk.Button(host, text="Replace panel", command=lambda: handle_when_panel_replace_button_is_clicked(position_id)).pack(anchor="w", padx=8, pady=(4, 0))


def create_tk_event_loop_shell():
    """Create only the hidden event-loop shell; tk:STARTUP builds the interface."""
    g["root"] = tk.Tk()
    g["root"].withdraw()


def build_tk_interface_after_startup():
    root = g["root"]
    root.title("Today — mobile stacks proof of concept")
    root.geometry("1060x650")
    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Button(top, text="<", command=handle_when_previous_day_button_is_clicked).pack(side="left")
    widgets["date-label"] = ttk.Label(top, width=12, anchor="center")
    widgets["date-label"].pack(side="left", padx=6)
    ttk.Button(top, text="今", command=handle_when_today_button_is_clicked).pack(side="left")
    ttk.Button(top, text=">", command=handle_when_next_day_button_is_clicked).pack(side="left", padx=(4, 12))
    widgets["orientation-var"] = tk.StringVar(value=g["orientation"])
    orientation = ttk.Entry(top, textvariable=widgets["orientation-var"], width=28)
    orientation.pack(side="left")
    orientation.bind("<Return>", handle_when_orientation_text_is_submitted)
    widgets["heartbeat-label"] = ttk.Label(top, text="heartbeat 0")
    widgets["heartbeat-label"].pack(side="right")
    panels_frame = ttk.Frame(root)
    panels_frame.pack(fill="both", expand=True)
    build_panel_host(panels_frame, "position-1")
    build_panel_host(panels_frame, "position-2")
    status = ttk.Frame(root, padding=(8, 0, 8, 4))
    status.pack(fill="x")
    widgets["machine-status"] = ttk.Label(status, text="waiting for mem and disk")
    widgets["machine-status"].pack(side="left")
    ttk.Button(status, text="Clear trace", command=lambda: widgets["trace"].delete("1.0", "end")).pack(side="right")
    trace_frame = ttk.LabelFrame(root, text="stack trace", padding=4)
    trace_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
    widgets["trace"] = tk.Text(trace_frame, height=13, wrap="none")
    widgets["trace"].pack(fill="both", expand=True)
    root.protocol("WM_DELETE_WINDOW", request_shutdown)
    root.deiconify()
    root.after(HEARTBEAT_INTERVAL_MS, handle_when_heartbeat_timer_fires)
    trace("[tk     ] tk:STARTUP built and revealed the two-panel interface")


def initialize_threads_and_machines():
    # The registry values are data, shown in the dictionary-shape comments above.
    threads["tk"] = {
        "in-queue": Queue(), "machine-names": ["tk"], "current-machine": None,
        "stack": None, "next-machine-index": 0, "thread-type": "system",
        "entry-fn": pump_tk_thread, "thread-obj": None, "stop-requested": False,
    }
    threads["mem"] = {
        "in-queue": Queue(), "machine-names": ["mem"], "current-machine": None,
        "stack": None, "next-machine-index": 0, "thread-type": "worker",
        "entry-fn": run_worker_thread, "thread-obj": None, "stop-requested": False,
    }
    threads["disk"] = {
        "in-queue": Queue(), "machine-names": ["disk"], "current-machine": None,
        "stack": None, "next-machine-index": 0, "thread-type": "worker",
        "entry-fn": run_worker_thread, "thread-obj": None, "stop-requested": False,
    }
    machines["tk"] = {"thread": "tk", "run-queue": deque(), "handler": handler_tk}
    machines["mem"] = {"thread": "mem", "run-queue": deque(), "handler": handler_mem}
    machines["disk"] = {"thread": "disk", "run-queue": deque(), "handler": handler_disk}
    panel_handlers[TODO_PANEL] = handle_todo_panel_operation
    panel_handlers[JOURNAL_PANEL] = handle_journal_panel_operation


def post_startup_stacks():
    for machine_name in machines:
        startup = make_stack(
            f"boot-{machine_name}", "startup", make_instruction(machine_name, STARTUP)
        )
        send_stack_to_machine(startup, machine_name, "startup")


def start_worker_threads():
    for thread_name, thread_state in threads.items():
        if thread_state["thread-type"] != "worker":
            continue
        thread = Thread(target=thread_state["entry-fn"], name=thread_name)
        thread_state["thread-obj"] = thread
        thread.start()


def request_shutdown():
    if g["shutting-down"]:
        return
    g["shutting-down"] = True
    trace("[main   ] shutdown: STOP each worker thread inbound queue")
    for thread_state in threads.values():
        if thread_state["thread-type"] == "worker":
            thread_state["in-queue"].put(STOP)
    if g["root"] is not None:
        g["root"].after(50, g["root"].destroy)


def run_headless_tk_pump_until_complete():
    """Verification-only replacement for Tk callbacks; logical scheduler unchanged."""
    while not g["shutting-down"]:
        admit_thread_inbound()
        for _ in range(3):
            if not run_one_machine_on_current_thread():
                break
        if g["completed-stack-count"] >= 2:
            request_shutdown()
        time.sleep(0.01)


def main():
    g["headless"] = "--headless" in sys.argv
    current_thread().name = "tk"
    initialize_threads_and_machines()
    if not g["headless"]:
        create_tk_event_loop_shell()
    post_startup_stacks()
    start_worker_threads()
    if g["headless"]:
        post_load_day_stack((g["selected-day"] + timedelta(days=1)).isoformat())
        run_headless_tk_pump_until_complete()
    else:
        schedule_tk_pump()
        g["root"].mainloop()
    for thread_state in threads.values():
        if thread_state["thread-obj"] is not None:
            thread_state["thread-obj"].join()
    trace("[main   ] clean exit")


if __name__ == "__main__":
    main()
