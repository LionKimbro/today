"""Machine addresses, Mobile Stack passage, and worker lifetimes."""

from queue import Queue
from threading import Event, RLock, Thread, current_thread, local, main_thread
from uuid import uuid4
import traceback

machines = {}  # Address -> runtime; membership changes use machines_lock.
machine_kinds = {}  # Kind -> handlers; installed before routing begins.
thread_state = local()
machines_lock = RLock()
a_thread_died_unexpectedly = Event()
shutdown_started = Event()


def initialize_machine_system():
    """Initialize before starting workers; never reset a live system."""
    with machines_lock:
        if any(r.get("thread") and r["thread"].is_alive() for r in machines.values()):
            raise RuntimeError("cannot initialize while a machine thread is alive")
        machines.clear()
        machine_kinds.clear()
        a_thread_died_unexpectedly.clear()
        shutdown_started.clear()


def install_machine(runtime):
    with machines_lock:
        runtime.setdefault("lifecycle", "starting")
        runtime.setdefault("thread", None)
        runtime.setdefault("dynamic", False)
        runtime.setdefault("continuation-frames", None)
        machines[runtime["name"]] = runtime


def install_machine_kind(kind, handlers):
    with machines_lock:
        machine_kinds[kind] = dict(handlers)


def get_machine_runtimes():
    with machines_lock:
        return list(machines.values())


def start_worker(machine_name, worker_loop):
    with machines_lock:
        runtime = machines[machine_name]
        if runtime["thread"] is not None:
            raise RuntimeError(f"worker already started: {machine_name}")
        thread = Thread(target=run_worker, args=(machine_name, worker_loop),
                        name=f"Today {machine_name}")
        runtime["thread"] = thread
        thread.start()
        return thread


def begin_shutdown():
    with machines_lock:
        shutdown_started.set()
        for runtime in machines.values():
            if runtime["dynamic"] and runtime["lifecycle"] in ("starting", "running"):
                runtime["lifecycle"] = "stopping"
                runtime["running"] = False
                runtime["inbox"].put(None)


def when_thread_dies_unexpectedly():
    """Latch fatal shutdown once and wake every worker, including new instances."""
    with machines_lock:
        if a_thread_died_unexpectedly.is_set():
            return
        a_thread_died_unexpectedly.set()
        shutdown_started.set()
        for runtime in machines.values():
            if runtime["lifecycle"] not in ("exited", "reaped"):
                runtime["lifecycle"] = "stopping"
            runtime["inbox"].put(None)


def run_worker(machine_name, worker_loop):
    """Normal retirement is expected; an uncaught BaseException is fatal."""
    claim_machine(machine_name)
    runtime = get_current_runtime()
    try:
        with machines_lock:
            if a_thread_died_unexpectedly.is_set() or runtime["lifecycle"] == "stopping":
                return
            runtime["lifecycle"] = "running"
            runtime["running"] = True
        worker_loop()
        if runtime["running"] and not a_thread_died_unexpectedly.is_set():
            raise RuntimeError(f"{machine_name} worker returned unexpectedly")
    except BaseException:
        traceback.print_exc()
        when_thread_dies_unexpectedly()
    finally:
        with machines_lock:
            runtime["running"] = False
            runtime["current-stack"] = None
            runtime["continuation-frames"] = None
            runtime["lifecycle"] = "exited"


def request_machine_retirement():
    """Finish this handler's handoff, then leave the worker loop."""
    with machines_lock:
        runtime = get_current_runtime()
        runtime["lifecycle"] = "stopping"
        runtime["running"] = False


def reap_exited_machines(flags=None):
    """Main joins completed workers before removing their addresses."""
    if current_thread() is not main_thread():
        raise RuntimeError("only the main thread may reap machines")
    for runtime in get_machine_runtimes():
        if flags and "dynamic" in flags and not runtime["dynamic"]:
            continue
        if runtime["lifecycle"] != "exited" or runtime["thread"] is None:
            continue
        runtime["thread"].join()
        with machines_lock:
            runtime["lifecycle"] = "reaped"
            if machines.get(runtime["name"]) is runtime:
                del machines[runtime["name"]]


def claim_machine(machine_name):
    with machines_lock:
        thread_state.runtime = machines[machine_name]


def get_current_runtime():
    return thread_state.runtime


def get_current_inbox():
    return get_current_runtime()["inbox"]


def continue_with_frames(frames):
    """Append bottom-first frames after removing the current handler's frame."""
    runtime = get_current_runtime()
    if runtime["continuation-frames"] is not None:
        raise RuntimeError("continuation already specified for this handler")
    runtime["continuation-frames"] = list(frames)


def handle_received_mobile_stack(stack):
    if a_thread_died_unexpectedly.is_set():
        return
    runtime = get_current_runtime()
    if shutdown_started.is_set() and runtime["dynamic"]:
        return
    if runtime["current-stack"] is not None:
        raise RuntimeError("cannot receive a stack while another stack is active")
    runtime["current-stack"] = stack
    handle_current_stack()


def route_current_stack():
    from . import mobile_stacks

    runtime = get_current_runtime()
    with machines_lock:
        if a_thread_died_unexpectedly.is_set() or (
                shutdown_started.is_set() and runtime["dynamic"]):
            clear_current_stack()
            return
        frame = mobile_stacks.top()
        destination = frame["machine"]
        if isinstance(destination, dict):
            if shutdown_started.is_set():
                clear_current_stack()
                return
            kind = destination["new"]
            name = f"{kind}-{uuid4().hex}"
            install_machine({
                "name": name, "inbox": Queue(), "current-stack": None,
                "handlers": machine_kinds[kind], "running": False, "dynamic": True,
            })
            frame["machine"] = name
            start_worker(name, run_machine)
            destination = name
        target = machines.get(destination)
        if target is None or target["lifecycle"] in ("stopping", "exited", "reaped"):
            if shutdown_started.is_set():
                clear_current_stack()
                return
            raise RuntimeError(f"cannot route to inactive machine: {destination}")
        stack = mobile_stacks.stack()
        print("Mobile Stack ->", destination, ":", frame["entry"])
        clear_current_stack()
        target["inbox"].put(stack)


def clear_current_stack():
    get_current_runtime()["current-stack"] = None


def handle_current_stack():
    from . import mobile_stacks

    frame = mobile_stacks.top()
    runtime = get_current_runtime()
    if frame["machine"] != runtime["name"]:
        raise RuntimeError(f"frame for {frame['machine']} received by {runtime['name']}")
    runtime["handlers"][frame["entry"]]()
    mobile_stacks.drop_frame()
    if runtime["continuation-frames"] is not None:
        mobile_stacks.stack()["frames"].extend(runtime["continuation-frames"])
        runtime["continuation-frames"] = None
    if mobile_stacks.has_frames():
        route_current_stack()
    else:
        clear_current_stack()


def run_machine():
    runtime = get_current_runtime()
    runtime["running"] = runtime["lifecycle"] != "stopping"
    while runtime["running"] and not a_thread_died_unexpectedly.is_set():
        item = runtime["inbox"].get()
        if a_thread_died_unexpectedly.is_set() or item is None or not runtime["running"]:
            request_machine_retirement()
            return
        handle_received_mobile_stack(item)
    runtime["running"] = False
