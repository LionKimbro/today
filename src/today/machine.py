"""Small shared runtime mechanics for machines with blocking inboxes."""

from threading import local

machines = {}
thread_state = local()


def install_machine(runtime):
    machines[runtime["name"]] = runtime


def claim_machine(machine_name):
    thread_state.runtime = machines[machine_name]


def get_current_runtime():
    return thread_state.runtime


def get_current_inbox():
    return get_current_runtime()["inbox"]


def handle_received_mobile_stack(stack):
    if get_current_runtime()["current-stack"] is not None:
        raise RuntimeError("cannot receive a stack while another stack is active")
    get_current_runtime()["current-stack"] = stack
    handle_current_stack()


def route_current_stack():
    from . import mobile_stacks

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

    while runtime["running"]:
        item = runtime["inbox"].get()
        if item is None:
            runtime["running"] = False
            return

        handle_received_mobile_stack(item)
