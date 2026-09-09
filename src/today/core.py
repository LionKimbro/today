"""The Core machine: reducer state, effects, and returned Mobile Stacks."""

from copy import deepcopy
from datetime import date, datetime

from . import machine, mobile_stacks


g = {
    "today-id": None,
    "send-tk-command": None,
    "reducer-events": [],
    "effects": [],
}

tabs = {}
rows = {}
positions = {}
visible_panels = {}


def initialize_core_state():
    g["today-id"] = date.today().isoformat()
    tabs["tab-a"] = {"id": "tab-a", "label": "Tab A", "row-ids": ["row-a", "row-b"]}
    rows["row-a"] = {"id": "row-a", "tab-id": "tab-a", "column-count": 2}
    rows["row-b"] = {"id": "row-b", "tab-id": "tab-a", "column-count": 1}
    positions["row-a/column-1"] = {"panel-id": "whiteboard-a"}
    positions["row-a/column-2"] = {"panel-id": None}
    positions["row-b/column-1"] = {"panel-id": None}


def get_position_id(row_id, column):
    return f"{row_id}/column-{column}"


def get_position_rendering(position_id):
    panel_id = positions[position_id]["panel-id"]
    if panel_id is None:
        return {"position-id": position_id, "panel-id": None}

    panel = visible_panels[panel_id]
    return {
        "position-id": position_id,
        "panel-id": panel["id"],
        "panel-label": panel["label"],
        "panel-type": panel["type"],
        **get_whiteboard_view(panel),
    }


def get_tab_rendering(tab_id):
    tab = tabs[tab_id]
    return {
        "tab-label": tab["label"],
        "rows": [
            {
                "row-id": row_id,
                "column-count": rows[row_id]["column-count"],
                "positions": [
                    get_position_rendering(get_position_id(row_id, column))
                    for column in range(1, rows[row_id]["column-count"] + 1)
                ],
            }
            for row_id in tab["row-ids"]
        ],
    }


def install_panel_snapshot(panel):
    snapshot = dict(panel)
    snapshot["dirty"] = False
    snapshot["awaiting"] = None
    snapshot["edit-generation"] = 0
    snapshot["save-generation"] = None
    snapshot["history-cursor"] = 0
    visible_panels[panel["id"]] = snapshot


def get_canonical_panel_fields(panel):
    return {
        key: value
        for key, value in panel.items()
        if key not in {"dirty", "awaiting", "edit-generation", "save-generation", "history-cursor"}
    }


def prepare_whiteboard_update(panel_id):
    panel = visible_panels[panel_id]
    panel["awaiting"] = "MEM_UPDATE"
    panel["save-generation"] = panel["edit-generation"]
    return {
        "type": "UPDATE_PANEL",
        "panel-id": panel_id,
        "base-revision": panel["revision"],
        "proposed-panel": get_canonical_panel_fields(panel),
        "save-generation": panel["save-generation"],
    }


def get_whiteboard_view(panel):
    cursor = panel["history-cursor"]
    if cursor == 0:
        return {
            "panel-text": panel["text"],
            "history-cursor": 0,
            "history-size": len(panel["history"]),
            "history-status": "Current working version",
        }

    snapshot = panel["history"][cursor - 1]
    return {
        "panel-text": snapshot["text"],
        "history-cursor": cursor,
        "history-size": len(panel["history"]),
        "history-status": snapshot["timestamp"],
    }


def make_whiteboard_snapshot(panel):
    panel["history"].insert(
        0,
        {
            "text": panel["text"],
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def reduce_event(event):
    if event["type"] == "START":
        return [{"type": "GET_PANEL", "panel-id": "whiteboard-a"}]

    if event["type"] == "PANEL_RECEIVED":
        install_panel_snapshot(event["panel"])
        print("Core reducer: PANEL_RECEIVED", event["panel-id"])
        return [{"type": "RENDER_TODAY"}]

    if event["type"] == "HOST_PANEL":
        return [
            {
                "type": "GET_PANEL",
                "panel-id": event["panel-id"],
                "position-id": event["position-id"],
            }
        ]

    if event["type"] == "PANEL_FOR_HOSTING_RECEIVED":
        panel = visible_panels.get(event["panel-id"])
        if panel is None or not panel["dirty"]:
            history_cursor = None if panel is None else panel["history-cursor"]
            install_panel_snapshot(event["panel"])
            if history_cursor is not None:
                visible_panels[event["panel-id"]]["history-cursor"] = min(
                    history_cursor,
                    len(visible_panels[event["panel-id"]]["history"]),
                )
        positions[event["position-id"]]["panel-id"] = event["panel-id"]
        print("Core reducer:", event["position-id"], "hosts", event["panel-id"])
        return [{"type": "RENDER_HOSTED_PANEL", "position-id": event["position-id"]}]

    if event["type"] == "RENAME_PANEL":
        if event["panel-id"] not in visible_panels:
            return []
        proposed_panel = get_canonical_panel_fields(visible_panels[event["panel-id"]])
        proposed_panel["label"] = "renamed panel"
        return [
            {
                "type": "UPDATE_PANEL",
                "panel-id": event["panel-id"],
                "base-revision": visible_panels[event["panel-id"]]["revision"],
                "proposed-panel": proposed_panel,
            }
        ]

    if event["type"] == "TEXT_CHANGED":
        panel = visible_panels[event["panel-id"]]
        if panel["type"] != "WHITEBOARD":
            return []
        if panel["history-cursor"] != 0:
            make_whiteboard_snapshot(panel)
            panel["history-cursor"] = 0
            panel["text"] = event["text"]
            panel["dirty"] = True
            panel["awaiting"] = "TEXT_DEBOUNCE"
            panel["edit-generation"] += 1
            return [{"type": "SET_WHITEBOARD_HISTORY_CURSOR", "panel-id": event["panel-id"]}]
        panel["text"] = event["text"]
        panel["dirty"] = True
        panel["awaiting"] = "TEXT_DEBOUNCE"
        panel["edit-generation"] += 1
        return []

    if event["type"] == "TEXT_DEBOUNCE":
        panel = visible_panels[event["panel-id"]]
        if (
            not panel["dirty"]
            or panel["awaiting"] != "TEXT_DEBOUNCE"
            or panel["save-generation"] is not None
        ):
            return []
        return [prepare_whiteboard_update(event["panel-id"])]

    if event["type"] == "HISTORY_CURSOR_CHANGED":
        panel = visible_panels[event["panel-id"]]
        cursor = event["history-cursor"]
        if cursor < 0 or cursor > len(panel["history"]):
            return []
        panel["history-cursor"] = cursor
        return [{"type": "RENDER_WHITEBOARD_VIEW", "panel-id": event["panel-id"]}]

    if event["type"] == "SNAPSHOT":
        panel = visible_panels[event["panel-id"]]
        make_whiteboard_snapshot(panel)
        panel["dirty"] = True
        panel["awaiting"] = "MEM_UPDATE"
        panel["edit-generation"] += 1
        return [prepare_whiteboard_update(event["panel-id"])]

    if event["type"] == "PANEL_UPDATED":
        install_panel_snapshot(event["panel"])
        print("Core reducer: PANEL_UPDATED", event["panel-id"], "revision", event["panel"]["revision"])
        return [{"type": "SET_PANEL_LABEL", "panel-id": event["panel-id"]}]

    if event["type"] == "WHITEBOARD_UPDATED":
        panel = visible_panels[event["panel-id"]]
        accepted_panel = event["panel"]
        if panel["edit-generation"] > event["save-generation"]:
            panel["revision"] = accepted_panel["revision"]
            panel["save-generation"] = None
            panel["awaiting"] = "TEXT_DEBOUNCE"
            return [prepare_whiteboard_update(event["panel-id"])]
        install_panel_snapshot(accepted_panel)
        print("Core reducer: WHITEBOARD_UPDATED", event["panel-id"], "revision", accepted_panel["revision"])
        return [{"type": "SET_WHITEBOARD_HISTORY_CURSOR", "panel-id": event["panel-id"]}]

    if event["type"] == "PANEL_UPDATE_CONFLICT":
        print("Core reducer: PANEL_UPDATE_CONFLICT", event["panel-id"], "revision", event["panel"]["revision"])
        return []

    if event["type"] == "SHUTDOWN":
        return [{"type": "STOP_CORE"}, {"type": "STOP_MEM"}, {"type": "SHUTDOWN_TK"}]

    return []


def dispatch_effect(effect):
    if effect["type"] == "GET_PANEL":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("panel-id", effect["panel-id"]))
        if "position-id" in effect:
            mobile_stacks.set_register(("position-id", effect["position-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "PANEL_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "GET_PANEL"})
        machine.route_current_stack()
        return

    if effect["type"] == "UPDATE_PANEL":
        print("Reducer effect: UPDATE_PANEL", effect["panel-id"], "base-revision", effect["base-revision"])
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("panel-id", effect["panel-id"]))
        mobile_stacks.set_register(("base-revision", effect["base-revision"]))
        mobile_stacks.set_register(("proposed-panel", deepcopy(effect["proposed-panel"])))
        if "save-generation" in effect:
            mobile_stacks.set_register(("save-generation", effect["save-generation"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "PANEL_UPDATED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "UPDATE_PANEL"})
        machine.route_current_stack()
        return

    if effect["type"] == "RENDER_TODAY":
        g["send-tk-command"](
            {
                "type": "RENDER_TODAY",
                "today-id": g["today-id"],
                **get_tab_rendering("tab-a"),
            }
        )
        return

    if effect["type"] == "SET_PANEL_LABEL":
        panel = visible_panels[effect["panel-id"]]
        g["send-tk-command"](
            {"type": "SET_PANEL_LABEL", "panel-id": panel["id"], "panel-label": panel["label"]}
        )
        return

    if effect["type"] == "RENDER_HOSTED_PANEL":
        g["send-tk-command"](
            {
                "type": "RENDER_HOSTED_PANEL",
                **get_position_rendering(effect["position-id"]),
            }
        )
        return

    if effect["type"] == "RENDER_WHITEBOARD_VIEW":
        panel = visible_panels[effect["panel-id"]]
        g["send-tk-command"](
            {
                "type": "RENDER_WHITEBOARD_VIEW",
                "panel-id": panel["id"],
                **get_whiteboard_view(panel),
            }
        )
        return

    if effect["type"] == "SET_WHITEBOARD_HISTORY_CURSOR":
        panel = visible_panels[effect["panel-id"]]
        g["send-tk-command"](
            {
                "type": "SET_WHITEBOARD_HISTORY_CURSOR",
                "panel-id": panel["id"],
                **get_whiteboard_view(panel),
            }
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
    if mobile_stacks.has_register("position-id"):
        g["reducer-events"].append(
            {
                "type": "PANEL_FOR_HOSTING_RECEIVED",
                "position-id": mobile_stacks.get_register("position-id"),
                "panel-id": panel_id,
                "panel": deepcopy(mobile_stacks.get_register("panel")),
            }
        )
        return

    g["reducer-events"].append(
        # The stack may continue elsewhere before this event is reduced.
        {
            "type": "PANEL_RECEIVED",
            "panel-id": panel_id,
            "panel": deepcopy(mobile_stacks.get_register("panel")),
        }
    )


def handle_when_core_receives_panel_update():
    panel_id = mobile_stacks.get_register("panel-id")
    panel = deepcopy(mobile_stacks.get_register("panel"))
    if mobile_stacks.get_register("update-result") == "accepted":
        print("Core stack return: PANEL_UPDATED", panel_id, "revision", panel["revision"])
        if mobile_stacks.has_register("save-generation"):
            g["reducer-events"].append(
                {
                    "type": "WHITEBOARD_UPDATED",
                    "panel-id": panel_id,
                    "panel": panel,
                    "save-generation": mobile_stacks.get_register("save-generation"),
                }
            )
            return
        g["reducer-events"].append({"type": "PANEL_UPDATED", "panel-id": panel_id, "panel": panel})
        return

    print("Core stack return: PANEL_UPDATE_CONFLICT", panel_id, "revision", panel["revision"])
    g["reducer-events"].append(
        {"type": "PANEL_UPDATE_CONFLICT", "panel-id": panel_id, "panel": panel}
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
