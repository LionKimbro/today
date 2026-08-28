"""Standalone proof of concept for stacks, machines, and physical threads.

This is a deliberately small architectural spike, not a reusable framework.
Its central separation is:

    stack      = the continuation of one logical computation
    machine    = the semantic owner of an operation and its runnable stacks
    thread     = the physical execution context for one or more machines

Every stack transfer follows one visible path:

    source machine -> target thread inbound queue -> target machine run queue

The target machine is currently on a same-named thread (``mem`` on ``mem``),
but the thread registry permits a future thread to host several machines.
Each thread's ``current-machine`` register says which assigned machine it is
running at this instant; it is cleared between reconciliation quanta.

Run normally to watch the Tk trace window and the console trace:

    python src/parts/04_mobile-stacks.py

Use --headless when a display is unavailable.  That mode preserves the same
logical scheduler but manually invokes the Tk pump instead of entering Tk.
"""

from collections import deque
from queue import Empty, Queue
from threading import Lock, Thread, current_thread
import sys
import time
import tkinter as tk
from tkinter import ttk


SERIAL = "SERIAL"
YIELD = "YIELD"
STARTUP = "STARTUP"
STOP = "STOP"


# Central program facts, not a general storage bucket:
# {"root": <Tk root or None>, "headless": <bool>, "active-demo-count": <int>, ...}
g = {
    "root": None,
    "headless": False,
    "shutting-down": False,
    "active-demo-count": 0,
    "completed-demo-count": 0,
    "next-stack-number": 1,
    "tk-pump-scheduled": False,
}

# Physical execution contexts. A thread may host more than one machine:
# {"<thread-name>": {"in-queue": Queue(<delivery packets>),
#                     "machine-names": ["<machine-name>", ...],
#                     "current-machine": "<machine-name>" | None,
#                     "next-machine-index": <round-robin position>,
#                     "thread-type": "system" | "worker",
#                     "entry-fn": <thread procedure>,
#                     "thread-obj": <Thread for workers, None for tk>,
#                     "stop-requested": <bool>}}
# For a worker, "thread-obj" is its live threading.Thread; for the tk system
# thread it is None because the program's main thread already exists.
threads = {}

# Semantic execution machines. A machine owns runnable stacks, but its
# physical thread admits inbound delivery packets into that local run queue:
# {"<machine-name>": {"thread": "<owning-thread-name>",
#                       "run-queue": deque(<runnable stacks>),
#                       "handler": <primitive operation handler>}}
machines = {}

# Tk widgets by readable role. Only tk-machine procedures may mutate this:
# {"status": <ttk.Label>, "trace": <tk.Text>, ...}
widgets = {}

# Panel identity remains separate from panel type:
# {"<panel-id>": {"type": "<panel-type>"}}
panels = {
    "panel-demo": {"type": "trace-panel"},
}
# {"<panel-type>": <panel operation handler>}
panel_handlers = {}
trace_lock = Lock()


def trace(text):
    """Print a line; the Tk trace view is updated only by the Tk machine."""
    with trace_lock:
        print(text, flush=True)


def stack_summary(stack):
    frames = stack["frames"]
    if not frames:
        return "<empty>"
    frame = frames[-1]
    return f"{frame['machine']}:{frame['op']}"


def dump_stack(stack):
    parts = []
    for frame in stack["frames"]:
        name = frame.get("name", frame["op"])
        result = frame.get("child-result")
        suffix = "" if result is None else f" <- {result!r}"
        parts.append(f"{frame['machine']}:{name}{suffix}")
    return " [ " + " | ".join(parts) + " ]"


def log(machine_name, stack, action):
    line = (
        f"[{machine_name:4}] stack={stack['id']:7} {action:34} "
        f"top={stack_summary(stack)}{dump_stack(stack)}"
    )
    trace(line)
    if machine_name == "tk" and g["root"] is not None:
        widget = widgets.get("trace")
        if widget is not None:
            widget.insert("end", line + "\n")
            widget.see("end")


def make_frame(machine_name, operation, data=None):
    # {"machine": "<target machine>", "op": "<operation>", ...}
    frame = {"machine": machine_name, "op": operation}
    if data:
        frame.update(data)
    return frame


def make_serial(machine_name, name, steps):
    # {"machine": "<target>", "op": "SERIAL", "name": "<label>",
    #  "steps": [<child frames>], "ip": <next child index>,
    #  "child-result": <most recently returned child result>}
    return {
        "machine": machine_name,
        "op": SERIAL,
        "name": name,
        "steps": steps,
        "ip": 0,
        "child-result": None,
    }


def make_stack(stack_id, frame, kind):
    # {"id": "<readable id>", "frames": [<bottom frame>, ..., <top frame>],
    #  "kind": "startup" | "demo"}
    return {"id": stack_id, "frames": [frame], "kind": kind}


def push(stack, frame, machine_name):
    stack["frames"].append(frame)
    log(machine_name, stack, f"PUSH {frame['machine']}:{frame['op']}")


def pop(stack, machine_name, result):
    frame = stack["frames"].pop()
    log(machine_name, stack, f"POP {frame['machine']}:{frame['op']} result={result!r}")
    if stack["frames"]:
        stack["frames"][-1]["child-result"] = result
        log(machine_name, stack, f"RETURN result={result!r} to parent")
    return frame


def make_delivery(target_machine, stack):
    # {"machine": "<target machine>", "stack": <the complete continuation>}
    return {"machine": target_machine, "stack": stack}


def send_stack_to_machine(stack, target_machine, source_machine):
    """Relinquish a stack to the target machine's physical thread."""
    target_thread = machines[target_machine]["thread"]
    log(
        source_machine,
        stack,
        f"TRANSFER -> machine={target_machine} via thread={target_thread}",
    )
    threads[target_thread]["in-queue"].put(make_delivery(target_machine, stack))


def transfer(stack, current_machine, target_machine):
    send_stack_to_machine(stack, target_machine, current_machine)


def admit_delivery_to_machine(thread_name, delivery):
    """Place one received continuation onto its target machine's run queue."""
    machine_name = delivery["machine"]
    stack = delivery["stack"]
    if machines[machine_name]["thread"] != thread_name:
        raise RuntimeError(f"thread {thread_name} received work for foreign machine {machine_name}")
    machines[machine_name]["run-queue"].append(stack)
    log(machine_name, stack, f"THREAD {thread_name} RECEIVE -> machine run-queue")


def admit_thread_inbound(thread_name):
    """Drain a physical thread's queue into the run queues of its machines."""
    thread_state = threads[thread_name]
    admitted = 0
    while True:
        try:
            delivery = thread_state["in-queue"].get_nowait()
        except Empty:
            break
        if delivery == STOP:
            thread_state["stop-requested"] = True
            trace(f"[{thread_name:4}] thread received STOP")
            continue
        admit_delivery_to_machine(thread_name, delivery)
        admitted += 1
    return admitted


def expand_serial(stack, machine_name):
    frame = stack["frames"][-1]
    if frame["ip"] == len(frame["steps"]):
        result = frame.get("child-result", f"{frame['name']} complete")
        pop(stack, machine_name, result)
        return "continue"
    next_frame = frame["steps"][frame["ip"]]
    frame["ip"] += 1
    log(machine_name, stack, f"IP advance {frame['name']} -> {frame['ip']}/{len(frame['steps'])}")
    push(stack, dict(next_frame), machine_name)
    return "continue"


def yield_stack(stack, machine_name):
    pop(stack, machine_name, "yield consumed")
    machines[machine_name]["run-queue"].append(stack)
    log(machine_name, stack, "YIELD -> back of local run-queue")
    return "yield"


def complete_stack(stack, machine_name):
    log(machine_name, stack, "COMPLETE stack")
    if stack["kind"] == "demo":
        g["active-demo-count"] -= 1
        g["completed-demo-count"] += 1
        log(machine_name, stack, "DEMO result returned to Tk; machine is ready")
        refresh_demo_status()


def reconcile_stack(stack, machine_name):
    """Run one stack until it transfers, yields, or completes.

    This is shared by all machines.  A worker and Tk differ only in how they
    call it: workers block for inbound work; Tk calls it from ``after``.
    """
    while True:
        if not stack["frames"]:
            complete_stack(stack, machine_name)
            return
        frame = stack["frames"][-1]
        log(machine_name, stack, "INSPECT top frame")
        if frame["machine"] != machine_name:
            transfer(stack, machine_name, frame["machine"])
            return
        if frame["op"] == YIELD:
            yield_stack(stack, machine_name)
            return
        if frame["op"] == SERIAL:
            expand_serial(stack, machine_name)
            continue
        result = machines[machine_name]["handler"](stack)
        pop(stack, machine_name, result)


def run_one_local_stack(machine_name):
    if machines[machine_name]["thread"] != current_thread().name:
        raise RuntimeError(f"foreign thread attempted to run machine {machine_name}")
    machine = machines[machine_name]
    if not machine["run-queue"]:
        return False
    stack = machine["run-queue"].popleft()
    log(machine_name, stack, "RUN one reconciliation quantum")
    reconcile_stack(stack, machine_name)
    return True


def run_one_machine_on_current_thread(thread_name):
    """Choose one assigned machine fairly and mark it in the thread register."""
    thread_state = threads[thread_name]
    machine_names = thread_state["machine-names"]
    for offset in range(len(machine_names)):
        index = (thread_state["next-machine-index"] + offset) % len(machine_names)
        machine_name = machine_names[index]
        if not machines[machine_name]["run-queue"]:
            continue
        thread_state["next-machine-index"] = (index + 1) % len(machine_names)
        thread_state["current-machine"] = machine_name
        trace(f"[{thread_name:4}] register current-machine <- {machine_name}")
        try:
            return run_one_local_stack(machine_name)
        finally:
            thread_state["current-machine"] = None
            trace(f"[{thread_name:4}] register current-machine <- None")
    return False


def receive_blocking_delivery_for_current_thread(thread_name):
    """Block only when every machine on this worker thread is idle."""
    delivery = threads[thread_name]["in-queue"].get()
    if delivery == STOP:
        threads[thread_name]["stop-requested"] = True
        trace(f"[{thread_name:4}] thread received STOP while idle")
        return
    admit_delivery_to_machine(thread_name, delivery)


def run_worker_thread():
    """Blocking worker thread: admit packets, run one machine quantum, repeat."""
    thread_name = current_thread().name
    thread_state = threads[thread_name]
    trace(
        f"[{thread_name:4}] worker thread started for machines "
        f"{thread_state['machine-names']}; blocking inbound queue when idle"
    )
    while True:
        admit_thread_inbound(thread_name)
        if run_one_machine_on_current_thread(thread_name):
            continue
        if thread_state["stop-requested"]:
            break
        receive_blocking_delivery_for_current_thread(thread_name)
    trace(f"[{thread_name:4}] worker thread stopped")


def pump_tk_thread():
    """Tk callback version of the same thread scheduler: bounded and non-blocking."""
    thread_name = current_thread().name
    g["tk-pump-scheduled"] = False
    admit_thread_inbound(thread_name)
    for _ in range(3):
        if not run_one_machine_on_current_thread(thread_name):
            break
        admit_thread_inbound(thread_name)
    if not g["shutting-down"] and g["root"] is not None:
        g["tk-pump-scheduled"] = True
        g["root"].after(30, pump_tk_thread)


def schedule_tk_pump():
    if g["root"] is None:
        return
    if not g["tk-pump-scheduled"] and not g["shutting-down"]:
        g["tk-pump-scheduled"] = True
        g["root"].after_idle(pump_tk_thread)


def handler_tk(stack):
    """Machine routing has already occurred; panel routing is Tk's extra layer."""
    frame = stack["frames"][-1]
    if "panel" in frame:
        panel_id = frame["panel"]
        panel_type = panels[panel_id]["type"]
        log("tk", stack, f"PANEL route {panel_id} -> {panel_type}")
        return panel_handlers[panel_type](stack)
    return handle_tk_system_operation(stack)


def handle_tk_system_operation(stack):
    frame = stack["frames"][-1]
    if frame["op"] == STARTUP:
        if not g["headless"]:
            build_tk_interface_after_startup()
        return "tk ready"
    if frame["op"] == "TK_SHOW_RESULT":
        result = stack["frames"][-2].get("child-result")
        status = widgets.get("status")
        if status is not None:
            status.configure(text=f"{stack['id']} returned: {result}")
        return f"Tk displayed {result}"
    raise ValueError(f"unknown tk system operation: {frame['op']}")


def handle_trace_panel_operation(stack):
    frame = stack["frames"][-1]
    if frame["op"] == "TK_START":
        return f"panel acknowledged {stack['id']}"
    raise ValueError(f"unknown trace-panel operation: {frame['op']}")


def handler_mem(stack):
    frame = stack["frames"][-1]
    if frame["op"] == STARTUP:
        return "mem ready"
    if frame["op"] == "MEM_PREPARE":
        return f"prepared {stack['id']}"
    if frame["op"] == "MEM_FORMAT":
        disk_result = stack["frames"][-2].get("child-result")
        return f"mem formatted ({disk_result})"
    raise ValueError(f"unknown mem operation: {frame['op']}")


def handler_disk(stack):
    frame = stack["frames"][-1]
    if frame["op"] == STARTUP:
        return "disk ready"
    if frame["op"] == "DISK_READ":
        return f"disk bytes for {stack['id']}"
    raise ValueError(f"unknown disk operation: {frame['op']}")


def build_demo_stack(stack_id):
    mem_steps = [
        make_frame("mem", "MEM_PREPARE"),
        make_frame("mem", YIELD),
        make_frame("disk", "DISK_READ"),
        make_frame("mem", "MEM_FORMAT"),
    ]
    outer_steps = [
        make_frame("tk", "TK_START", {"panel": "panel-demo"}),
        make_serial("mem", "MEM_LOOKUP", mem_steps),
        make_frame("tk", "TK_SHOW_RESULT"),
    ]
    return make_stack(stack_id, make_serial("tk", "TK_TO_MEM_TO_DISK_TO_TK", outer_steps), "demo")


def post_demo_stack(label):
    """Turn a Tk request into stack data; the scheduler performs it later."""
    stack_id = f"{label}-{g['next-stack-number']}"
    g["next-stack-number"] += 1
    g["active-demo-count"] += 1
    send_stack_to_machine(build_demo_stack(stack_id), "tk", "user")
    trace(f"[user] stack={stack_id:7} posted independent workflow to tk")
    refresh_demo_status()
    schedule_tk_pump()


def refresh_demo_status():
    status = widgets.get("status")
    if status is not None:
        status.configure(
            text=(
                f"active stacks: {g['active-demo-count']}   "
                f"completed: {g['completed-demo-count']}"
            )
        )


def handle_when_alpha_button_is_clicked():
    post_demo_stack("alpha")


def handle_when_bravo_button_is_clicked():
    post_demo_stack("bravo")


def handle_when_fair_pair_button_is_clicked():
    post_demo_stack("alpha")
    post_demo_stack("bravo")


def handle_when_clear_trace_button_is_clicked():
    widgets["trace"].delete("1.0", "end")


def initialize_threads_and_machines():
    # The current spike intentionally maps one machine to each named thread.
    # The lists make the future multi-machine-per-thread case explicit now.
    threads["tk"] = {
        "in-queue": Queue(),
        "machine-names": ["tk"],
        "current-machine": None,
        "next-machine-index": 0,
        "thread-type": "system",
        "entry-fn": pump_tk_thread,
        "stop-requested": False,
        "thread-obj": None,
    }
    threads["mem"] = {
        "in-queue": Queue(),
        "machine-names": ["mem"],
        "current-machine": None,
        "next-machine-index": 0,
        "thread-type": "worker",
        "entry-fn": run_worker_thread,
        "stop-requested": False,
        "thread-obj": None,
    }
    threads["disk"] = {
        "in-queue": Queue(),
        "machine-names": ["disk"],
        "current-machine": None,
        "next-machine-index": 0,
        "thread-type": "worker",
        "entry-fn": run_worker_thread,
        "stop-requested": False,
        "thread-obj": None,
    }
    machines["tk"] = {
        "thread": "tk",
        "run-queue": deque(),
        "handler": handler_tk,
    }
    machines["mem"] = {
        "thread": "mem",
        "run-queue": deque(),
        "handler": handler_mem,
    }
    machines["disk"] = {
        "thread": "disk",
        "run-queue": deque(),
        "handler": handler_disk,
    }
    panel_handlers["trace-panel"] = handle_trace_panel_operation


def post_startup_stacks():
    for machine_name in machines:
        startup_stack = make_stack(
            f"boot-{machine_name}", make_frame(machine_name, STARTUP), "startup"
        )
        send_stack_to_machine(startup_stack, machine_name, "startup")
def create_tk_event_loop_shell():
    """Create only the hidden main-thread event-loop shell before tk:STARTUP."""
    g["root"] = tk.Tk()
    g["root"].withdraw()


def build_tk_interface_after_startup():
    """Construct and reveal the visible Tk interface for the tk:STARTUP frame."""
    root = g["root"]
    root.title("Today — mobile stacks proof of concept")
    root.geometry("1100x600")
    frame = ttk.Frame(root, padding=10)
    frame.pack(fill="both", expand=True)
    ttk.Label(
        frame,
        text="Mobile stacks: post independent continuations and watch tk → mem → disk → mem → tk",
    ).pack(anchor="w")
    controls = ttk.Frame(frame)
    controls.pack(anchor="w", pady=(8, 4))
    ttk.Button(controls, text="Launch alpha", command=handle_when_alpha_button_is_clicked).pack(side="left")
    ttk.Button(controls, text="Launch bravo", command=handle_when_bravo_button_is_clicked).pack(side="left", padx=4)
    ttk.Button(
        controls,
        text="Launch fair pair (yield)",
        command=handle_when_fair_pair_button_is_clicked,
    ).pack(side="left", padx=4)
    ttk.Button(controls, text="Clear trace", command=handle_when_clear_trace_button_is_clicked).pack(side="left", padx=4)
    panel = ttk.LabelFrame(frame, text="panel-demo / trace-panel", padding=6)
    panel.pack(fill="x", pady=(0, 8))
    ttk.Label(panel, text="This panel-type handler acknowledges TK_START before the stack transfers to mem.").pack(side="left")
    ttk.Button(panel, text="Launch from panel", command=handle_when_alpha_button_is_clicked).pack(side="right")
    widgets["status"] = ttk.Label(frame, text="Starting machines...")
    widgets["status"].pack(anchor="w", pady=(4, 8))
    trace_widget = tk.Text(frame, height=28, width=145, wrap="none")
    trace_widget.pack(fill="both", expand=True)
    widgets["trace"] = trace_widget
    root.protocol("WM_DELETE_WINDOW", request_shutdown)
    root.deiconify()
    trace("[tk  ] tk:STARTUP built and revealed the Tk interface")


def request_shutdown():
    if g["shutting-down"]:
        return
    g["shutting-down"] = True
    trace("[main] shutdown: sending STOP to worker thread inbound queues")
    threads["mem"]["in-queue"].put(STOP)
    threads["disk"]["in-queue"].put(STOP)
    if g["root"] is not None:
        g["root"].after(50, g["root"].destroy)


def start_workers():
    for thread_name in ("mem", "disk"):
        thread = Thread(target=threads[thread_name]["entry-fn"], name=thread_name)
        threads[thread_name]["thread-obj"] = thread
        thread.start()


def run_headless_tk_pump_until_completion():
    """Verification-only substitute for Tk callbacks when no display exists."""
    while not g["shutting-down"]:
        thread_name = current_thread().name
        admit_thread_inbound(thread_name)
        for _ in range(3):
            if not run_one_machine_on_current_thread(thread_name):
                break
        if g["completed-demo-count"] == 2:
            request_shutdown()
        time.sleep(0.01)


def main():
    g["headless"] = "--headless" in sys.argv
    current_thread().name = "tk"
    initialize_threads_and_machines()
    if not g["headless"]:
        create_tk_event_loop_shell()
    post_startup_stacks()
    start_workers()
    if g["headless"]:
        post_demo_stack("alpha")
        post_demo_stack("bravo")
        run_headless_tk_pump_until_completion()
    else:
        schedule_tk_pump()
        g["root"].mainloop()
    for thread_state in threads.values():
        if thread_state["thread-obj"] is not None:
            thread_state["thread-obj"].join()
    trace("[main] clean exit")


if __name__ == "__main__":
    main()
