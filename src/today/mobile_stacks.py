"""Mobile Stacks: continuation frames plus traveling registers."""

from . import machine


def create_stack():
    if stack() is not None:
        raise RuntimeError("cannot create a stack while another stack is active")
    machine.get_current_runtime()["current-stack"] = {
        "kind": "MOBILE_STACK",
        "frames": [],
        "registers": {},
    }


def stack():
    return machine.get_current_runtime()["current-stack"]


def push_frame(frame):
    stack()["frames"].append(frame)


def drop_frame():
    stack()["frames"].pop()


def set_register(key_value):
    key, value = key_value
    stack()["registers"][key] = value


def get_register(key):
    return stack()["registers"][key]


def has_register(key):
    return key in stack()["registers"]


def top():
    return stack()["frames"][-1]


def has_frames():
    return bool(stack()["frames"])


def is_mobile_stack(item):
    return isinstance(item, dict) and item.get("kind") == "MOBILE_STACK"
