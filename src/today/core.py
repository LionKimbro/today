"""The Reducer Core machine: Today state, reduction, and Tk commands."""

from datetime import date


g = {
    "running": False,
    "today-id": None,
    "incoming-events": None,
    "send-tk-command": None,
}

days = {}
tabs = {}
positions = {}
panels = {}


def initialize_today_world():
    today_id = date.today().isoformat()
    g["today-id"] = today_id

    days[today_id] = {"id": today_id, "tab-ids": ["tab-a"]}
    tabs["tab-a"] = {
        "id": "tab-a",
        "day-id": today_id,
        "label": "Tab A",
        "position-ids": ["position-1"],
    }
    positions["position-1"] = {
        "id": "position-1",
        "tab-id": "tab-a",
        "panel-id": "panel-1",
    }
    panels["panel-1"] = {"id": "panel-1", "label": "panel-1"}


def render_today():
    position = positions["position-1"]
    panel = panels[position["panel-id"]]
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


def set_panel_label(panel_id):
    g["send-tk-command"](
        {
            "type": "SET_PANEL_LABEL",
            "panel-id": panel_id,
            "panel-label": panels[panel_id]["label"],
        }
    )


def reduce_event(event):
    if event["type"] == "RENAME_PANEL":
        panels[event["panel-id"]]["label"] = "renamed panel"
        set_panel_label(event["panel-id"])
        return

    if event["type"] == "SHUTDOWN":
        g["running"] = False
        g["send-tk-command"]({"type": "SHUTDOWN_COMPLETE"})


def run_reducer_core():
    initialize_today_world()
    g["running"] = True
    render_today()

    while g["running"]:
        event = g["incoming-events"].get()
        print("Tk -> Core:", event)
        reduce_event(event)
