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
from contextlib import contextmanager
from copy import deepcopy
from datetime import date, timedelta
from queue import Empty, Queue
from threading import Thread, current_thread
import sys
import time
import tkinter as tk
from tkinter import ttk

import loglogic


SERIAL = "SERIAL"
YIELD = "YIELD"
STARTUP = "STARTUP"
SUSPENDED = "SUSPENDED"
STOP = "STOP"
BUILDING = "building"
EXECUTING = "executing"

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
    "startup-load-day": None,
}

# Physical execution contexts.  The stack register names the one stack this
# thread is currently considering, whether building or executing.
# A thread's inbound queue and its machines' run queues can still hold many
# other stacks waiting for their own turn:
# {"<thread-name>": {"in-queue": Queue(<delivery records>),
#                     "machine-names": ["<machine-name>", ...],
#                     "current-machine": "<machine-name>" | None,
#                     "stack": <stack> | None,
#                     "stack-phase": None | "building" | "executing",
#                     "builder": {"serials": [<open serial records>]},
#                     "target": "<machine-name>" | None,
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

# Tk panel-type cache, populated from rendered day bundles; it is not
# authoritative memory: {"<panel-id>": "TODO" | "JOURNAL"}
panel_types = {}

# {"<panel-id>": {"content": <ttk.Frame>, "status": <ttk.Label>, ...}}
panel_widgets = {}

# {"<panel-type>": <Tk panel operation handler>}
panel_handlers = {}

# Authoritative memory, mutated only by mem primitive operations:
# {"days": {"YYYY-MM-DD": <day layout record>},
#  "panels": {"<panel-id>": {"day": "YYYY-MM-DD", "type": <type>,
#                             "state": <panel state>}}}
memory = {"days": {}, "panels": {}}

# Simulated disk records, mutated only by disk primitive operations:
# {"days": {"YYYY-MM-DD": <complete persisted day record>}}
disk_store = {"days": {}}

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


def set_register(key, value):
    """Write named state into this thread's one current stack."""
    stack = state()["stack"]
    if stack is None:
        raise RuntimeError("set_register requires a current stack")
    stack["registers"][key] = value


def present_traceline(line):
    """The tk presentation adapter; worker threads never call this."""
    print(line, flush=True)
    if not g["shutting-down"] and widgets.get("trace") is not None:
        widgets["trace"].insert("end", line + "\n")
        widgets["trace"].see("end")


def make_stack(stack_id, kind, root_instruction):
    """Make a new, inactive stack with its first frame already present."""
    # {"id": "<readable stack id>", "kind": "startup" | "ui",
    #  "registers": {<stack-local named state>},
    #  "frames": [<bottom frame>, ..., <top frame>]}
    stack = {
        "id": stack_id,
        "kind": kind,
        "registers": {},
        "frames": [deepcopy(root_instruction)],
    }
    return stack


def begin_stack(stack_id, kind):
    """Create this thread's one current stack in its building phase."""
    builder = state()["builder"]
    if state()["stack"] is not None or state()["stack-phase"] is not None:
        raise RuntimeError("this thread is already considering a stack")
    state()["stack"] = {"id": stack_id, "kind": kind, "registers": {}, "frames": []}
    state()["stack-phase"] = BUILDING
    builder["serials"] = []


def target(machine_name):
    """Set the target machine used by subsequently created instructions."""
    if machine_name not in machines:
        raise ValueError(f"unknown target machine: {machine_name}")
    state()["target"] = machine_name


def begin_serial(name):
    """Open a serial procedure at the builder's current target machine."""
    builder = state()["builder"]
    if state()["stack-phase"] != BUILDING:
        raise RuntimeError("begin_serial requires the building stack phase")
    if state()["target"] is None:
        raise RuntimeError("begin_serial requires a current construction target")
    builder["serials"].append({"name": name, "target": state()["target"], "steps": []})


def begin_replacement(name):
    """Temporarily use the serial builder to replace the active executing frame."""
    builder = state()["builder"]
    if state()["stack-phase"] != EXECUTING:
        raise RuntimeError("begin_replacement requires the executing stack phase")
    if builder["serials"]:
        raise RuntimeError("this thread already has replacement construction in progress")
    current_machine = top()["machine"]
    state()["stack-phase"] = BUILDING
    target(current_machine)
    begin_serial(name)


def instruction(operation, data=None):
    """Build an instruction or push its live frame at the current target."""
    builder = state()["builder"]
    if state()["target"] is None:
        raise RuntimeError("instruction requires a current target")
    # {"machine": "<target machine>", "op": "<operation>",
    #  "data": {<operation-specific fields>}}
    frame = {
        "machine": state()["target"],
        "op": operation,
        "data": {} if data is None else data,
    }
    if state()["stack-phase"] == EXECUTING:
        push_frame(frame)
        return
    if state()["stack-phase"] != BUILDING:
        raise RuntimeError("instruction requires the building or executing stack phase")
    if builder["serials"]:
        builder["serials"][-1]["steps"].append(frame)
        return
    if state()["stack"]["frames"]:
        raise RuntimeError("a stack under construction can have only one root instruction")
    state()["stack"]["frames"].append(frame)


def close_serial(name):
    """Close the named innermost serial and return its completed serial frame."""
    builder = state()["builder"]
    if state()["stack-phase"] != BUILDING:
        raise RuntimeError("close_serial requires the building stack phase")
    if not builder["serials"]:
        raise RuntimeError("close_serial requires an open serial")
    serial = builder["serials"][-1]
    if serial["name"] != name:
        raise RuntimeError(f"close_serial expected {serial['name']!r}, not {name!r}")
    builder["serials"].pop()
    return {
        "machine": serial["target"],
        "op": SERIAL,
        "data": {"name": serial["name"], "steps": serial["steps"], "ip": 0},
    }


def end_serial(name):
    """Close the named innermost serial and add it to its enclosing context."""
    builder = state()["builder"]
    frame = close_serial(name)
    if builder["serials"]:
        builder["serials"][-1]["steps"].append(frame)
        return
    if state()["stack"]["frames"]:
        raise RuntimeError("a stack under construction can have only one root instruction")
    state()["stack"]["frames"].append(frame)


def end_replacement(name):
    """Install the serial built by ``begin_replacement`` over its original frame."""
    builder = state()["builder"]
    if state()["stack-phase"] != BUILDING or len(builder["serials"]) != 1:
        raise RuntimeError("end_replacement requires active replacement construction")
    serial_frame = close_serial(name)
    previous = top()
    state()["stack"]["frames"][-1] = serial_frame
    state()["stack-phase"] = EXECUTING
    loglogic.emit(
        "STACK_UPDATED",
        state()["stack"],
        {"reason": f"rewrote {previous['machine']} / {previous['op']} as SERIAL / {serial_frame['data']['name']}"},
    )


@contextmanager
def serial(name):
    """Use a ``with`` block as shorthand for begin_serial/end_serial."""
    begin_serial(name)
    try:
        yield
    finally:
        end_serial(name)


def end_stack():
    """Validate construction and leave the completed stack in the stack register."""
    builder = state()["builder"]
    stack = state()["stack"]
    if state()["stack-phase"] != BUILDING or stack is None:
        raise RuntimeError("end_stack requires the building stack phase")
    if builder["serials"]:
        raise RuntimeError("end_stack requires every serial to be closed")
    if len(stack["frames"]) != 1:
        raise RuntimeError("end_stack requires exactly one root instruction")
    builder["serials"] = []
    state()["stack-phase"] = None


def push_frame(instruction):
    """Create a live frame by pushing this instruction onto the current stack."""
    stack = state()["stack"]
    frame = deepcopy(instruction)
    stack["frames"].append(frame)
    loglogic.emit(
        "STACK_UPDATED",
        stack,
        {"reason": f"expanded procedure with {frame['machine']} / {frame['op']}"},
    )


def pop_frame(result):
    """Pop the current frame and explicitly return its result to its parent."""
    stack = state()["stack"]
    machine_name = state()["current-machine"]
    frame = stack["frames"].pop()
    parent = stack["frames"][-1] if stack["frames"] else None
    if stack["frames"]:
        stack["frames"][-1]["child-result"] = result
        event_type = "FRAME_RETURNED"
    else:
        event_type = "FRAME_COMPLETED"
    loglogic.emit(
        event_type,
        stack,
        {"frame": frame, "result": result, "parent": parent, "machine": machine_name},
    )


def make_delivery(target_machine, stack):
    # {"machine": "<target machine>", "stack": <complete continuation stack>}
    return {"machine": target_machine, "stack": stack}


def send_stack_to_machine(target_machine):
    """Relinquish the registered current stack to another machine's thread."""
    stack = state()["stack"]
    source_name = state()["current-machine"]
    target_thread = machines[target_machine]["thread"]
    loglogic.emit(
        "STACK_TRANSFERRED",
        stack,
        {"from-machine": source_name, "to-machine": target_machine, "to-thread": target_thread},
    )
    threads[target_thread]["in-queue"].put(make_delivery(target_machine, stack))


def admit_delivery_to_machine(thread_name, delivery):
    """The receiving thread places a delivered stack in its target machine queue."""
    machine_name = delivery["machine"]
    stack = delivery["stack"]
    if machines[machine_name]["thread"] != thread_name:
        raise RuntimeError(f"thread {thread_name} received work for {machine_name}")
    machines[machine_name]["run-queue"].append(stack)


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
            loglogic.emit("SYSTEM", data={"message": f"thread {thread_name} received STOP"})
            continue
        admit_delivery_to_machine(thread_name, delivery)


def expand_serial():
    frame = top()
    data = frame["data"]
    if data["ip"] == len(data["steps"]):
        pop_frame(frame.get("child-result", f"{data['name']} complete"))
        return
    instruction = data["steps"][data["ip"]]
    data["ip"] += 1
    push_frame(instruction)


def yield_stack():
    stack = state()["stack"]
    machine_name = state()["current-machine"]
    pop_frame("yield consumed")
    machines[machine_name]["run-queue"].append(stack)
    loglogic.emit("STACK_YIELDED", stack)


def complete_stack():
    stack = state()["stack"]
    loglogic.emit("STACK_COMPLETED", stack)
    if stack["kind"] == "ui":
        g["completed-stack-count"] += 1


def reconcile():
    """Use the current thread registers to advance one stack to a boundary."""
    while True:
        stack = state()["stack"]
        if not stack["frames"]:
            complete_stack()
            return
        frame = top()
        machine_name = state()["current-machine"]
        if frame["machine"] != machine_name:
            send_stack_to_machine(frame["machine"])
            return
        if frame["op"] == YIELD:
            yield_stack()
            return
        if frame["op"] == SERIAL:
            expand_serial()
            continue
        result = machines[machine_name]["handler"]()
        if top() is not frame:
            continue
        if result == SUSPENDED:
            continue
        pop_frame(result)


def run_one_machine_on_current_thread():
    """Run one fair quantum and establish the current executing stack registers."""
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
        thread_state["stack-phase"] = EXECUTING
        try:
            reconcile()
        finally:
            thread_state["stack"] = None
            thread_state["stack-phase"] = None
            thread_state["current-machine"] = None
        return True
    return False


def receive_blocking_delivery_for_current_thread():
    """Workers block only after all of their assigned machine queues are empty."""
    thread_name = current_thread().name
    delivery = state()["in-queue"].get()
    if delivery == STOP:
        state()["stop-requested"] = True
        loglogic.emit("SYSTEM", data={"message": f"thread {thread_name} received STOP while idle"})
        return
    admit_delivery_to_machine(thread_name, delivery)


def run_worker_thread():
    """Worker procedure; its own name identifies its record in ``threads``."""
    thread_name = current_thread().name
    loglogic.emit("SYSTEM", data={"message": f"worker thread {thread_name} started"})
    while True:
        admit_thread_inbound()
        if run_one_machine_on_current_thread():
            continue
        if state()["stop-requested"]:
            break
        receive_blocking_delivery_for_current_thread()
    loglogic.emit("SYSTEM", data={"message": f"worker thread {thread_name} stopped"})


def pump_tk_thread():
    """Tk's non-blocking physical form of the same thread scheduler."""
    g["tk-pump-scheduled"] = False
    admit_thread_inbound()
    loglogic.present_pending(present_traceline)
    for _ in range(3):
        if not run_one_machine_on_current_thread():
            break
        post_pending_load_day()
        admit_thread_inbound()
        loglogic.present_pending(present_traceline)
    refresh_machine_status()
    if not g["shutting-down"]:
        g["tk-pump-scheduled"] = True
        g["root"].after(25, pump_tk_thread)


def schedule_tk_pump():
    if g["root"] is not None and not g["tk-pump-scheduled"]:
        g["tk-pump-scheduled"] = True
        g["root"].after_idle(pump_tk_thread)


def current_day_text():
    return g["selected-day"].isoformat()


def post_pending_load_day():
    """Post the startup day request after the boot stack releases the Tk thread."""
    day_text = g["startup-load-day"]
    if day_text is None or state()["stack"] is not None:
        return
    g["startup-load-day"] = None
    post_load_day_stack(day_text)


def make_blank_day(day_text):
    """Make one persisted day bundle; mem splits it into days and panels on load."""
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


def install_day_bundle(day_text, day_bundle):
    """Install one persisted day bundle into the separate mem day and panel records."""
    day_record = deepcopy(day_bundle)
    panel_records = day_record.pop("panels")
    if day_record["day"] != day_text:
        raise ValueError(f"day bundle key {day_text} does not match {day_record['day']}")
    for panel_id, panel_record in list(memory["panels"].items()):
        if panel_record["day"] == day_text:
            memory["panels"].pop(panel_id)
    memory["days"][day_text] = day_record
    for panel_id, panel_record in panel_records.items():
        panel = deepcopy(panel_record)
        panel["day"] = day_text
        memory["panels"][panel_id] = panel
    for panel_id in day_record["position-panel"].values():
        if memory["panels"][panel_id]["day"] != day_text:
            raise RuntimeError(f"panel {panel_id} is not owned by {day_text}")


def make_day_bundle(day_text):
    """Copy one day and all of its top-level panels into a persisted day bundle."""
    day_bundle = deepcopy(memory["days"][day_text])
    day_bundle["panels"] = {
        panel_id: deepcopy(panel_record)
        for panel_id, panel_record in memory["panels"].items()
        if panel_record["day"] == day_text
    }
    return day_bundle


def handler_tk():
    """Tk machine handler; panel-type routing happens after machine routing."""
    frame = top()
    if "panel" in frame["data"]:
        panel_id = frame["data"]["panel"]
        panel_type = panel_types[panel_id]
        loglogic.emit("STACK_UPDATED", state()["stack"], {"reason": f"panel route {panel_id} -> {panel_type}"})
        return panel_handlers[panel_type]()
    return handle_tk_system_operation()


def handle_tk_system_operation():
    frame = top()
    if frame["op"] == STARTUP:
        if not g["headless"]:
            build_tk_interface_after_startup()
        g["startup-load-day"] = current_day_text()
        return "tk ready"
    if frame["op"] == "TK_RENDER_DAY":
        day_snapshot = state()["stack"]["registers"]["day-record"]
        if day_snapshot["day"] != current_day_text():
            return f"Tk ignored stale day snapshot {day_snapshot['day']}"
        render_day_snapshot(day_snapshot)
        return f"Tk rendered {day_snapshot['day']}"
    if frame["op"] == "TK_SET_ORIENTATION":
        g["orientation"] = frame["data"]["text"]
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
    if frame["op"] == "SET_TODO_STATE":
        return handle_set_todo_state()
    if frame["op"] == "MEM_SET_PANEL_STATE":
        return handle_mem_set_panel_state()
    if frame["op"] == "MEM_SAVE_DAY":
        return handle_mem_save_day()
    if frame["op"] == "MEM_EDIT_AND_SAVE":
        return handle_mem_edit_and_save()
    raise ValueError(f"unknown mem operation: {frame['op']}")


def handle_mem_load_day():
    frame = top()
    data = frame["data"]
    day_text = state()["stack"]["registers"]["day"]
    if data.get("stage") is None:
        data["stage"] = "waiting-for-disk"
        target("disk")
        instruction("DISK_READ_DAY")
        return SUSPENDED
    install_day_bundle(day_text, frame["child-result"])
    set_register("day-record", make_day_bundle(day_text))
    return f"mem loaded {day_text}"


def apply_mem_edit(day_record, edit):
    if edit["kind"] == "edit-journal":
        memory["panels"][edit["panel"]]["state"]["text"] = edit["text"]
    elif edit["kind"] == "replace-panel":
        position = edit["position"]
        current_panel = day_record["position-panel"][position]
        current_type = memory["panels"][current_panel]["type"]
        candidates = memory["panels"]
        if current_type == TODO_PANEL:
            day_record["position-panel"][position] = next(
                panel_id
                for panel_id, panel in candidates.items()
                if panel["day"] == day_record["day"] and panel["type"] == JOURNAL_PANEL
            )
        else:
            day_record["position-panel"][position] = next(
                panel_id
                for panel_id, panel in candidates.items()
                if panel["day"] == day_record["day"] and panel["type"] == TODO_PANEL
            )
    else:
        raise ValueError(f"unknown mem edit: {edit['kind']}")


def resolve_path(data, path):
    """Follow a list of dictionary keys or list indexes and return the result."""
    for key in path:
        data = data[key]
    return data


def handle_set_todo_state():
    """Bind a semantic TODO request, then replace it with private mem serial work."""
    frame = top()
    data = frame["data"]
    begin_replacement("MEM_SET_AND_SAVE_TODO")
    target("mem")
    instruction(
        "MEM_SET_PANEL_STATE",
        {"path": ["items", data["item"], "done"], "value": data["done"]},
    )
    instruction("MEM_SAVE_DAY")
    end_replacement("MEM_SET_AND_SAVE_TODO")


def handle_mem_set_panel_state():
    frame = top()
    panel_id = state()["stack"]["registers"]["panel"]
    panel_state = memory["panels"][panel_id]["state"]
    path = frame["data"]["path"]
    target_state = resolve_path(panel_state, path[:-1])
    target_state[path[-1]] = frame["data"]["value"]
    return "panel state set"


def handle_mem_save_day():
    frame = top()
    data = frame["data"]
    panel_id = state()["stack"]["registers"]["panel"]
    day_text = memory["panels"][panel_id]["day"]
    set_register("day", day_text)
    if data.get("stage") is None:
        data["stage"] = "waiting-for-disk-save"
        target("disk")
        instruction("DISK_WRITE_DAY", {"day-record": make_day_bundle(day_text)})
        return SUSPENDED
    return f"mem saved {day_text}: {frame['child-result']}"


def handle_mem_edit_and_save():
    frame = top()
    data = frame["data"]
    day_text = state()["stack"]["registers"]["day"]
    if data.get("stage") is None:
        apply_mem_edit(memory["days"][day_text], data["edit"])
        day_bundle = make_day_bundle(day_text)
        set_register("day-record", deepcopy(day_bundle))
        data["stage"] = "waiting-for-disk-save"
        target("disk")
        instruction("DISK_WRITE_DAY", {"day-record": day_bundle})
        return SUSPENDED
    return f"mem edit saved: {frame['child-result']}"


def handler_disk():
    frame = top()
    if frame["op"] == STARTUP:
        return "disk ready"
    if frame["op"] == "DISK_READ_DAY":
        day_text = state()["stack"]["registers"]["day"]
        if day_text not in disk_store["days"]:
            disk_store["days"][day_text] = make_blank_day(day_text)
        return deepcopy(disk_store["days"][day_text])
    if frame["op"] == "DISK_WRITE_DAY":
        data = frame["data"]
        day_text = state()["stack"]["registers"]["day"]
        disk_store["days"][day_text] = deepcopy(data["day-record"])
        return f"disk wrote {day_text}"
    raise ValueError(f"unknown disk operation: {frame['op']}")


def make_load_day_stack(stack_id, day_text):
    begin_stack(stack_id, "ui")
    set_register("day", day_text)
    target("tk")
    with serial("TK_LOAD_AND_RENDER_DAY"):
        target("mem")
        with serial("MEM_LOAD_TRANSACTION"):
            instruction("MEM_LOAD_DAY")
            instruction(YIELD)
        target("tk")
        instruction("TK_RENDER_DAY")
    end_stack()


def make_panel_edit_stack(stack_id, edit):
    edit_data = dict(edit)
    day_text = edit_data.pop("day")
    panel_id = edit_data.get("panel")
    begin_stack(stack_id, "ui")
    set_register("day", day_text)
    target("tk")
    with serial("TK_EDIT_AND_RENDER"):
        if panel_id is not None:
            instruction("TK_PANEL_EVENT", {"panel": panel_id})
        target("mem")
        with serial("MEM_EDIT_TRANSACTION"):
            instruction("MEM_EDIT_AND_SAVE", {"edit": edit_data})
            instruction(YIELD)
        target("tk")
        instruction("TK_RENDER_DAY")
    end_stack()


def post_stack():
    """Submit the completed current stack to its root frame's target machine."""
    stack = state()["stack"]
    if state()["stack-phase"] is not None or stack is None:
        raise RuntimeError("post_stack requires a completed current stack")
    target_machine = stack["frames"][0]["machine"]
    target_thread = machines[target_machine]["thread"]
    source_name = "startup" if stack["kind"] == "startup" else state()["current-machine"] or "user"
    loglogic.emit("STACK_CREATED", stack, {"initial-owner": source_name})
    loglogic.emit(
        "STACK_SUBMITTED",
        stack,
        {"source": source_name, "to-machine": target_machine, "to-thread": target_thread},
    )
    threads[target_thread]["in-queue"].put(make_delivery(target_machine, stack))
    state()["stack"] = None
    state()["stack-phase"] = None
    schedule_tk_pump()


def next_stack_id(label):
    stack_id = f"{label}-{g['next-stack-number']}"
    g["next-stack-number"] += 1
    return stack_id


def post_load_day_stack(day_text):
    loglogic.emit("EXTERNAL_EVENT", data={"message": f"request load day {day_text}"})
    make_load_day_stack(next_stack_id("load-day"), day_text)
    post_stack()


def post_panel_edit_stack(edit):
    loglogic.emit("EXTERNAL_EVENT", data={"message": f"panel event: {edit['kind']}"})
    make_panel_edit_stack(next_stack_id(edit["kind"]), edit)
    post_stack()


def post_tk_instruction(operation, data):
    if operation != "TK_HEARTBEAT":
        loglogic.emit("EXTERNAL_EVENT", data={"message": f"request {operation}"})
    begin_stack(next_stack_id(operation.lower()), "ui")
    target("tk")
    instruction(operation, data)
    end_stack()
    post_stack()


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


def handle_when_todo_toggle_button_is_clicked(panel_id, desired_value):
    loglogic.emit("EXTERNAL_EVENT", data={"message": "panel event: toggle-todo"})
    begin_stack(next_stack_id("toggle-todo"), "ui")
    set_register("panel", panel_id)
    target("mem")
    instruction(
        "SET_TODO_STATE",
        {"item": 0, "done": desired_value},
    )
    end_stack()
    post_stack()


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
    """Render the day bundle carried by the stack; Tk never reads mem memory."""
    if g["headless"]:
        return
    widgets["date-label"].configure(text=day_record["day"])
    for position_id, panel_id in day_record["position-panel"].items():
        panel_record = day_record["panels"][panel_id]
        panel_types[panel_id] = panel_record["type"]
        clear_position_panel(position_id)
        position_widgets[position_id]["mounted-panel"] = panel_id
        build_panel_in_position(position_id, panel_id, panel_record)


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
        command=lambda: handle_when_todo_toggle_button_is_clicked(panel_id, not item["done"]),
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
    loglogic.emit("SYSTEM", data={"message": "tk:STARTUP built and revealed the two-panel interface"})


def initialize_threads_and_machines():
    # The registry values are data, shown in the dictionary-shape comments above.
    threads["tk"] = {
        "in-queue": Queue(), "machine-names": ["tk"], "current-machine": None,
        "stack": None, "stack-phase": None, "builder": {"serials": []}, "target": None,
        "next-machine-index": 0, "thread-type": "system",
        "entry-fn": pump_tk_thread, "thread-obj": None, "stop-requested": False,
    }
    threads["mem"] = {
        "in-queue": Queue(), "machine-names": ["mem"], "current-machine": None,
        "stack": None, "stack-phase": None, "builder": {"serials": []}, "target": None,
        "next-machine-index": 0, "thread-type": "worker",
        "entry-fn": run_worker_thread, "thread-obj": None, "stop-requested": False,
    }
    threads["disk"] = {
        "in-queue": Queue(), "machine-names": ["disk"], "current-machine": None,
        "stack": None, "stack-phase": None, "builder": {"serials": []}, "target": None,
        "next-machine-index": 0, "thread-type": "worker",
        "entry-fn": run_worker_thread, "thread-obj": None, "stop-requested": False,
    }
    machines["tk"] = {"thread": "tk", "run-queue": deque(), "handler": handler_tk}
    machines["mem"] = {"thread": "mem", "run-queue": deque(), "handler": handler_mem}
    machines["disk"] = {"thread": "disk", "run-queue": deque(), "handler": handler_disk}
    panel_handlers[TODO_PANEL] = handle_todo_panel_operation
    panel_handlers[JOURNAL_PANEL] = handle_journal_panel_operation


def post_startup_stacks():
    for machine_name in machines:
        begin_stack(f"boot-{machine_name}", "startup")
        target(machine_name)
        instruction(STARTUP)
        end_stack()
        post_stack()


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
    loglogic.emit("SYSTEM", data={"message": "shutdown: STOP each worker thread inbound queue"})
    for thread_state in threads.values():
        if thread_state["thread-type"] == "worker":
            thread_state["in-queue"].put(STOP)
    if g["root"] is not None:
        g["root"].after(50, g["root"].destroy)


def run_headless_tk_pump_until_complete():
    """Verification-only replacement for Tk callbacks; logical scheduler unchanged."""
    while not g["shutting-down"]:
        admit_thread_inbound()
        loglogic.present_pending(present_traceline)
        for _ in range(3):
            if not run_one_machine_on_current_thread():
                break
            post_pending_load_day()
            loglogic.present_pending(present_traceline)
        refresh_machine_status()
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
    loglogic.emit("SYSTEM", data={"message": "clean exit"})
    loglogic.present_pending(present_traceline)


if __name__ == "__main__":
    main()
