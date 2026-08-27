"""Standalone proof of concept for a stack that moves among tk, mem, and disk.

Run normally to watch the Tk trace window and the console trace:

    python src/parts/04_mobile-stacks.py

Use --headless when a display is unavailable.  That mode preserves the same
logical scheduler but manually invokes the Tk pump instead of entering Tk.
"""

from collections import deque
from queue import Empty, Queue
from threading import Lock, Thread
import sys
import time
import tkinter as tk
from tkinter import ttk


SERIAL = "SERIAL"
YIELD = "YIELD"
STARTUP = "STARTUP"
STOP = "STOP"


g = {
    "root": None,
    "headless": False,
    "shutting-down": False,
    "demo-count": 0,
    "completed-demo-count": 0,
    "tk-pump-scheduled": False,
}

machines = {}
panels = {
    "panel-demo": {"type": "trace-panel"},
}
panel_handlers = {}
threads = {}
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
        widgets = machines["tk"].get("widgets", {})
        widget = widgets.get("trace")
        if widget is not None:
            widget.insert("end", line + "\n")
            widget.see("end")


def make_frame(machine_name, operation, data=None):
    frame = {"machine": machine_name, "op": operation}
    if data:
        frame.update(data)
    return frame


def make_serial(machine_name, name, steps):
    return {
        "machine": machine_name,
        "op": SERIAL,
        "name": name,
        "steps": steps,
        "ip": 0,
        "child-result": None,
    }


def make_stack(stack_id, frame, kind):
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


def transfer(stack, current_machine, target_machine):
    log(current_machine, stack, f"TRANSFER ownership -> {target_machine}")
    machines[target_machine]["in-queue"].put(stack)


def admit_inbound(machine_name):
    machine = machines[machine_name]
    admitted = 0
    while True:
        try:
            stack = machine["in-queue"].get_nowait()
        except Empty:
            break
        if stack == STOP:
            machine["stop-requested"] = True
            log(machine_name, make_stack("system", make_frame(machine_name, STOP), "system"), "STOP received")
            continue
        machine["run-queue"].append(stack)
        admitted += 1
        log(machine_name, stack, "ADMIT inbound -> local run-queue")
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
        g["completed-demo-count"] += 1
        if g["completed-demo-count"] == g["demo-count"]:
            log(machine_name, stack, "ALL demo stacks completed")
            if g["root"] is not None:
                g["root"].after(500, request_shutdown)


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
    machine = machines[machine_name]
    if not machine["run-queue"]:
        return False
    stack = machine["run-queue"].popleft()
    log(machine_name, stack, "RUN one reconciliation quantum")
    reconcile_stack(stack, machine_name)
    return True


def run_worker_machine(machine_name):
    """Blocking worker loop: admit, run one quantum, then recheck inbound."""
    trace(f"[{machine_name:4}] worker started; blocking inbound queue when idle")
    while True:
        admit_inbound(machine_name)
        if run_one_local_stack(machine_name):
            continue
        if machines[machine_name]["stop-requested"]:
            break
        stack = machines[machine_name]["in-queue"].get()
        if stack == STOP:
            machines[machine_name]["stop-requested"] = True
            continue
        machines[machine_name]["run-queue"].append(stack)
        log(machine_name, stack, "WAKE from blocking inbound queue")
    trace(f"[{machine_name:4}] worker stopped")


def pump_tk_machine():
    """Tk callback version of the same scheduler: bounded and non-blocking."""
    g["tk-pump-scheduled"] = False
    admit_inbound("tk")
    for _ in range(3):
        if not run_one_local_stack("tk"):
            break
        admit_inbound("tk")
    if not g["shutting-down"] and g["root"] is not None:
        g["tk-pump-scheduled"] = True
        g["root"].after(30, pump_tk_machine)


def schedule_tk_pump():
    if not g["tk-pump-scheduled"] and not g["shutting-down"]:
        g["tk-pump-scheduled"] = True
        g["root"].after_idle(pump_tk_machine)


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
        return "tk ready"
    if frame["op"] == "TK_SHOW_RESULT":
        result = stack["frames"][-2].get("child-result")
        status = machines["tk"]["widgets"].get("status")
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


def initialize_machines():
    machines["tk"] = {
        "in-queue": Queue(), "run-queue": deque(), "handler": handler_tk,
        "thread-type": "system", "entry-fn": pump_tk_machine,
        "stop-requested": False, "widgets": {},
    }
    machines["mem"] = {
        "in-queue": Queue(), "run-queue": deque(), "handler": handler_mem,
        "thread-type": "worker", "entry-fn": run_worker_machine,
        "stop-requested": False,
    }
    machines["disk"] = {
        "in-queue": Queue(), "run-queue": deque(), "handler": handler_disk,
        "thread-type": "worker", "entry-fn": run_worker_machine,
        "stop-requested": False,
    }
    panel_handlers["trace-panel"] = handle_trace_panel_operation


def post_startup_and_demo_stacks():
    for machine_name in machines:
        machines[machine_name]["in-queue"].put(
            make_stack(f"boot-{machine_name}", make_frame(machine_name, STARTUP), "startup")
        )
    for stack_id in ("alpha", "bravo"):
        g["demo-count"] += 1
        machines["tk"]["in-queue"].put(build_demo_stack(stack_id))


def build_window():
    root = tk.Tk()
    root.title("Today — mobile stacks proof of concept")
    root.geometry("1100x600")
    g["root"] = root
    frame = ttk.Frame(root, padding=10)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Two independent stacks: tk → mem → disk → mem → tk").pack(anchor="w")
    machines["tk"]["widgets"]["status"] = ttk.Label(frame, text="Starting machines...")
    machines["tk"]["widgets"]["status"].pack(anchor="w", pady=(4, 8))
    trace_widget = tk.Text(frame, height=28, width=145, wrap="none")
    trace_widget.pack(fill="both", expand=True)
    machines["tk"]["widgets"]["trace"] = trace_widget
    root.protocol("WM_DELETE_WINDOW", request_shutdown)
    return root


def request_shutdown():
    if g["shutting-down"]:
        return
    g["shutting-down"] = True
    trace("[main] shutdown: sending STOP to worker inbound queues")
    machines["mem"]["in-queue"].put(STOP)
    machines["disk"]["in-queue"].put(STOP)
    if g["root"] is not None:
        g["root"].after(50, g["root"].destroy)


def start_workers():
    for machine_name in ("mem", "disk"):
        thread = Thread(target=run_worker_machine, args=(machine_name,), name=f"{machine_name}-worker")
        threads[machine_name] = thread
        thread.start()


def run_headless_tk_pump_until_completion():
    """Verification-only substitute for Tk callbacks when no display exists."""
    while not g["shutting-down"]:
        admit_inbound("tk")
        for _ in range(3):
            if not run_one_local_stack("tk"):
                break
        if g["completed-demo-count"] == g["demo-count"]:
            request_shutdown()
        time.sleep(0.01)


def main():
    g["headless"] = "--headless" in sys.argv
    initialize_machines()
    if not g["headless"]:
        build_window()
    post_startup_and_demo_stacks()
    start_workers()
    if g["headless"]:
        run_headless_tk_pump_until_completion()
    else:
        schedule_tk_pump()
        g["root"].mainloop()
    for thread in threads.values():
        thread.join()
    trace("[main] clean exit")


if __name__ == "__main__":
    main()
