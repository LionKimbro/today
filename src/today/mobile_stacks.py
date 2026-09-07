"""Mobile Stacks: continuation frames plus traveling registers."""

from threading import local


thread_state = local()


def create_stack():
    return {"kind": "MOBILE_STACK", "frames": [], "registers": {}}


def install_current_stack(stack):
    thread_state.current_stack = stack


def clear_current_stack():
    thread_state.current_stack = None


def get_current_stack():
    return thread_state.current_stack


def push_frame(frame):
    get_current_stack()["frames"].append(frame)


def drop_frame():
    return get_current_stack()["frames"].pop()


def set_register(key_value):
    key, value = key_value
    get_current_stack()["registers"][key] = value


def get_register(key):
    return get_current_stack()["registers"][key]


def get_top_frame():
    return get_current_stack()["frames"][-1]


def has_frames():
    return bool(get_current_stack()["frames"])


def is_mobile_stack(item):
    return isinstance(item, dict) and item.get("kind") == "MOBILE_STACK"
