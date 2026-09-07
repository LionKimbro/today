"""Small shared runtime mechanics for machines with blocking inboxes."""

from threading import local

from . import mobile_stacks


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


def start_mobile_stack():
    stack = mobile_stacks.create_stack()
    get_current_runtime()["current-stack"] = stack
    mobile_stacks.install_current_stack(stack)


def handle_received_mobile_stack(stack):
    get_current_runtime()["current-stack"] = stack
    mobile_stacks.install_current_stack(stack)
    handle_current_stack()


def route_current_stack():
    frame = mobile_stacks.get_top_frame()
    stack = mobile_stacks.get_current_stack()
    print("Mobile Stack ->", frame["machine"], ":", frame["entry"])
    machines[frame["machine"]]["inbox"].put(stack)
    clear_current_stack()


def clear_current_stack():
    get_current_runtime()["current-stack"] = None
    mobile_stacks.clear_current_stack()


def handle_current_stack():
    frame = mobile_stacks.get_top_frame()
    runtime = get_current_runtime()
    assert frame["machine"] == runtime["name"]
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
