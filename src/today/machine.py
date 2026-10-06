"""Small shared runtime mechanics for machines with blocking inboxes."""

from threading import Event, Lock, local
import traceback

machines = {}
thread_state = local()
a_thread_died_unexpectedly = Event()
thread_failure_lock = Lock()


def when_thread_dies_unexpectedly():
    """Latch fatal shutdown once and wake every required worker."""
    with thread_failure_lock:
        if a_thread_died_unexpectedly.is_set():
            return
        a_thread_died_unexpectedly.set()
        for runtime in machines.values():
            runtime["inbox"].put(None)


def run_worker(machine_name, worker_loop):
    """Required worker boundary; even SystemExit is fatal here."""
    claim_machine(machine_name)
    runtime = get_current_runtime()
    try:
        if a_thread_died_unexpectedly.is_set():
            return
        worker_loop()
        if runtime["running"] and not a_thread_died_unexpectedly.is_set():
            raise RuntimeError(f"{machine_name} worker returned unexpectedly")
    except BaseException:
        traceback.print_exc()
        when_thread_dies_unexpectedly()
    finally:
        runtime["running"] = False
        runtime["current-stack"] = None


def install_machine(runtime):
    machines[runtime["name"]] = runtime


def claim_machine(machine_name):
    thread_state.runtime = machines[machine_name]


def get_current_runtime():
    return thread_state.runtime


def get_current_inbox():
    return get_current_runtime()["inbox"]


def handle_received_mobile_stack(stack):
    if a_thread_died_unexpectedly.is_set():
        return
    if get_current_runtime()["current-stack"] is not None:
        raise RuntimeError("cannot receive a stack while another stack is active")
    get_current_runtime()["current-stack"] = stack
    handle_current_stack()


def route_current_stack():
    from . import mobile_stacks

    if a_thread_died_unexpectedly.is_set():
        clear_current_stack()
        return
    frame = mobile_stacks.top()
    stack = mobile_stacks.stack()
    print("Mobile Stack ->", frame["machine"], ":", frame["entry"])
    inbox = machines[frame["machine"]]["inbox"]
    clear_current_stack()
    inbox.put(stack)


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

    if mobile_stacks.has_frames():
        route_current_stack()
        return

    clear_current_stack()


def run_machine():
    runtime = get_current_runtime()
    runtime["running"] = True

    while runtime["running"] and not a_thread_died_unexpectedly.is_set():
        item = runtime["inbox"].get()
        if a_thread_died_unexpectedly.is_set() or item is None:
            runtime["running"] = False
            return

        handle_received_mobile_stack(item)
    runtime["running"] = False
