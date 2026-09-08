"""The Core machine: reducer state, effects, and returned Mobile Stacks."""

from copy import deepcopy
from datetime import date

from . import machine, mobile_stacks


g = {
    "today-id": None,
    "send-tk-command": None,
    "reducer-events": [],
    "effects": [],
}

tabs = {}
positions = {}
visible_panels = {}


def initialize_core_state():
    g["today-id"] = date.today().isoformat()
    tabs["tab-a"] = {"id": "tab-a", "label": "Tab A", "position-ids": ["position-1"]}
    positions["position-1"] = {"id": "position-1", "tab-id": "tab-a", "panel-id": "panel-1"}


def reduce_event(event):
    if event["type"] == "START":
        return [{"type": "GET_PANEL", "panel-id": "panel-1"}]

    if event["type"] == "PANEL_RECEIVED":
        visible_panels[event["panel-id"]] = dict(event["panel"])
        print("Core reducer: PANEL_RECEIVED", event["panel-id"])
        return [{"type": "RENDER_TODAY"}]

    if event["type"] == "RENAME_PANEL":
        if event["panel-id"] not in visible_panels:
            return []
        visible_panels[event["panel-id"]]["label"] = "renamed panel"
        return [{"type": "SET_PANEL_LABEL", "panel-id": event["panel-id"]}]

    if event["type"] == "SHUTDOWN":
        return [{"type": "STOP_CORE"}, {"type": "STOP_MEM"}, {"type": "SHUTDOWN_TK"}]

    return []


def dispatch_effect(effect):
    if effect["type"] == "GET_PANEL":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("panel-id", effect["panel-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "PANEL_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "GET_PANEL"})
        machine.route_current_stack()
        return

    if effect["type"] == "RENDER_TODAY":
        position = positions["position-1"]
        panel = visible_panels[position["panel-id"]]
        g["send-tk-command"](
            {
                "type": "RENDER_TODAY",
                "today-id": g["today-id"],
                "tab-label": tabs["tab-a"]["label"],
                "position-id": position["id"],
                "panel-id": panel["id"],
                "panel-label": panel["label"],
            }
        )
        return

    if effect["type"] == "SET_PANEL_LABEL":
        panel = visible_panels[effect["panel-id"]]
        g["send-tk-command"](
            {"type": "SET_PANEL_LABEL", "panel-id": panel["id"], "panel-label": panel["label"]}
        )
        return

    if effect["type"] == "STOP_CORE":
        machine.get_current_runtime()["running"] = False
        return

    if effect["type"] == "STOP_MEM":
        machine.machines["MEM"]["inbox"].put(None)
        return

    if effect["type"] == "SHUTDOWN_TK":
        g["send-tk-command"]({"type": "SHUTDOWN_COMPLETE"})


def process_reducer_events_until_quiet():
    while g["reducer-events"]:
        event = g["reducer-events"].pop(0)
        g["effects"].extend(reduce_event(event))

    while g["effects"]:
        dispatch_effect(g["effects"].pop(0))


def handle_when_core_receives_panel_return():
    panel_id = mobile_stacks.get_register("panel-id")
    print("Core stack return: PANEL_RETURNED", panel_id)
    g["reducer-events"].append(
        # The stack may continue elsewhere before this event is reduced.
        {
            "type": "PANEL_RECEIVED",
            "panel-id": panel_id,
            "panel": deepcopy(mobile_stacks.get_register("panel")),
        }
    )


def run_reducer_core():
    machine.claim_machine("CORE")
    initialize_core_state()
    runtime = machine.get_current_runtime()
    runtime["running"] = True
    g["reducer-events"].append({"type": "START"})
    process_reducer_events_until_quiet()

    while runtime["running"]:
        item = machine.get_current_inbox().get()
        if item is None:
            item = {"type": "SHUTDOWN"}

        if mobile_stacks.is_mobile_stack(item):
            machine.handle_received_mobile_stack(item)
        else:
            print("Tk -> Core:", item)
            g["reducer-events"].append(item)

        process_reducer_events_until_quiet()
