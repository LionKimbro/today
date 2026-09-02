"""Narrative presentation for the mobile-stack spike.

Execution machines emit small semantic events here.  They do not print.  The
tk thread later drains this queue and presents one stable, computation-first
view of every event in the console and trace widget.
"""

from copy import deepcopy
from queue import Empty, Queue


# Thread-safe semantic trace records:
# [{"type": "STACK_CREATED" | "FRAME_RETURNED" | ...,
#   "stack": {"id": <str>, "frames": [<frame snapshots>]} | None,
#   "data": {<event-specific facts>}}]
events = Queue()


def result_summary(result):
    if isinstance(result, dict) and "day" in result and "panels" in result:
        return f"<day snapshot {result['day']}>"
    return repr(result)


def instruction_summary(frame):
    if frame["op"] == "SERIAL":
        return frame["name"]
    return frame["op"]


def snapshot_stack(stack):
    # {"id": "<readable stack id>", "kind": "startup" | "ui",
    #  "frames": [<immutable frame snapshots>]}
    return {
        "id": stack["id"],
        "kind": stack["kind"],
        "frames": deepcopy(stack["frames"]),
    }


def emit(event_type, stack=None, data=None):
    # {"type": "<semantic event>", "stack": <snapshot or None>,
    #  "data": {<event-specific facts>}}
    events.put(
        {
            "type": event_type,
            "stack": None if stack is None else snapshot_stack(stack),
            "data": {} if data is None else deepcopy(data),
        }
    )


def describe_stack(stack):
    lines = [f"  stack: {stack['id']}", "  frames:"]
    frames = stack["frames"]
    for index, frame in enumerate(frames):
        marker = "  <-- TOP" if index == len(frames) - 1 else ""
        line = f"    [{index}] machine={frame['machine']}  op={instruction_summary(frame)}"
        if frame["op"] == "SERIAL":
            line += f"  kind=SERIAL  ip={frame['ip']}/{len(frame['steps'])}"
        lines.append(line + marker)
        if frame.get("child-result") is not None:
            lines.append(f"        returned-result: {result_summary(frame['child-result'])}")
        if frame["op"] == "SERIAL":
            lines.append("        instructions:")
            for instruction_index, instruction in enumerate(frame["steps"]):
                marker = "[cur:]" if instruction_index == frame["ip"] else "      "
                lines.append(
                    f"          {marker} {instruction_index}: {instruction_summary(instruction)}"
                )
            if frame["ip"] == len(frame["steps"]):
                lines.append("          [done] all instructions have been pushed")
    return lines


def format_event(event):
    event_type = event["type"]
    stack = event["stack"]
    data = event["data"]
    if event_type == "EXTERNAL_EVENT":
        return ["EVENT", f"  {data['message']}"]
    if event_type == "SYSTEM":
        return ["SYSTEM", f"  {data['message']}"]
    if event_type == "STACK_CREATED":
        return [
            "STACK CREATED",
            f"  initial owner: {data['initial-owner']}",
            *describe_stack(stack),
        ]
    if event_type == "STACK_UPDATED":
        return ["STACK UPDATED", f"  reason: {data['reason']}", *describe_stack(stack)]
    if event_type == "STACK_SUBMITTED":
        return [
            "STACK SUBMITTED",
            f"  stack: {stack['id']}",
            f"  submitted by: {data['source']}",
            f"  destination: {data['to-machine']} (thread {data['to-thread']})",
            "  note: this is initial admission, not a continuation transfer",
            *describe_stack(stack)[2:],
        ]
    if event_type == "STACK_TRANSFERRED":
        return [
            "STACK TRANSFER",
            f"  stack: {stack['id']}",
            f"  from: {data['from-machine']}",
            f"  to: {data['to-machine']} (thread {data['to-thread']})",
            "  reason: top frame targets another machine",
            *describe_stack(stack)[2:],
        ]
    if event_type == "FRAME_RETURNED":
        lines = [
            "FRAME RETURNED",
            f"  stack: {stack['id']}",
            f"  completed: {data['frame']['machine']} / {instruction_summary(data['frame'])}",
            f"  result: {result_summary(data['result'])}",
        ]
        if data["parent"] is None:
            lines.append("  result delivered to: stack completion")
        else:
            lines.append(
                "  result delivered to: "
                f"{data['parent']['machine']} / {instruction_summary(data['parent'])}"
            )
        return lines + describe_stack(stack)[2:]
    if event_type == "FRAME_COMPLETED":
        return [
            "FRAME COMPLETED",
            f"  stack: {stack['id']}",
            f"  completed: {data['frame']['machine']} / {instruction_summary(data['frame'])}",
            f"  final result: {result_summary(data['result'])}",
            "  no parent frame: this was the bottom frame",
        ]
    if event_type == "STACK_YIELDED":
        return ["STACK YIELDED", f"  stack: {stack['id']}", "  reason: let another runnable stack proceed", *describe_stack(stack)[2:]]
    if event_type == "STACK_COMPLETED":
        return ["STACK COMPLETED", f"  stack: {stack['id']}"]
    raise ValueError(f"unknown trace event: {event_type}")


def present_pending(write_line):
    """Drain all queued semantic events through the caller's output adapter."""
    while True:
        try:
            event = events.get_nowait()
        except Empty:
            return
        for line in format_event(event):
            write_line(line)
        write_line("")
