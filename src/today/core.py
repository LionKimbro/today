"""The Core machine: reducer state, effects, and returned Mobile Stacks."""

from copy import deepcopy
from datetime import date, datetime, timedelta

from . import machine, mobile_stacks


g = {
    "current-day-id": None,
    "send-tk-command": None,
    "reducer-events": [],
    "effects": [],
    "known-panel-ids": [],
    "pending-initial-panel-ids": [],
    "selected-tab-id": None,
    "pending-day-id": None,
    "orientation-position": None,
}

tabs = {}
rows = {}
positions = {}
visible_panels = {}


def initialize_core_state():
    g["current-day-id"] = date.today().isoformat()


def get_position_id(row_id, column):
    return f"{row_id}/column-{column}"


def get_tab_id_for_position(position_id):
    row_id = position_id.split("/", 1)[0]
    return rows[row_id]["tab-id"]


def get_position_ids_for_tab(tab_id):
    return [
        get_position_id(row_id, column)
        for row_id in tabs[tab_id]["row-ids"]
        for column in range(1, rows[row_id]["column-count"] + 1)
    ]


def get_position_rendering(position_id):
    panel_id = positions[position_id]["panel-id"]
    if panel_id is None:
        return {
            "position-id": position_id,
            "panel-id": None,
            "available-panel-ids": get_available_panel_ids(position_id),
        }

    panel = visible_panels[panel_id]
    return {
        "position-id": position_id,
        "panel-id": panel["id"],
        "panel-label": panel["label"],
        "panel-type": panel["type"],
        **get_whiteboard_view(panel),
    }


def get_available_panel_ids(position_id):
    tab_id = get_tab_id_for_position(position_id)
    hosted_panel_ids = {
        positions[position_id]["panel-id"]
        for position_id in get_position_ids_for_tab(tab_id)
    }
    hosted_panel_ids.discard(None)
    return [
        panel_id
        for panel_id in g["known-panel-ids"]
        if panel_id not in hosted_panel_ids and visible_panels[panel_id]["type"] == "WHITEBOARD"
    ]


def get_tab_rendering(tab_id):
    tab = tabs[tab_id]
    return {
        "tab-label": tab["label"],
        "scroll-position": tab["scroll-position"],
        "rows": [
            {
                "row-id": row_id,
                "column-count": rows[row_id]["column-count"],
                "height": rows[row_id]["height"],
                "sash-proportions": rows[row_id]["sash-proportions"],
                "positions": [
                    get_position_rendering(get_position_id(row_id, column))
                    for column in range(1, rows[row_id]["column-count"] + 1)
                ],
            }
            for row_id in tab["row-ids"]
        ],
    }


def get_day_rendering():
    orientation_panel = visible_panels[g["orientation-position"]["panel-id"]]
    return {
        "tabs": [
            {"tab-id": tab_id, **get_tab_rendering(tab_id)}
            for tab_id in tabs
        ],
        "selected-tab-id": g["selected-tab-id"],
        "orientation": {
            "position-id": g["orientation-position"]["id"],
            "panel-id": orientation_panel["id"],
            "panel-label": orientation_panel["label"],
            "panel-type": orientation_panel["type"],
            "panel-text": orientation_panel["text"],
        },
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


def get_day_navigation_effect_when_ready():
    if g["pending-day-id"] is None:
        return []
    if any(panel["dirty"] for panel in visible_panels.values()):
        return []
    day_id = g["pending-day-id"]
    g["pending-day-id"] = None
    return [{"type": "GET_DAY_LAYOUT", "day-id": day_id}]


def request_day_navigation(day_id):
    g["pending-day-id"] = day_id
    return get_day_navigation_effect_when_ready()


def prepare_text_panel_update(panel_id):
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
        return [{"type": "GET_DAY_LAYOUT", "day-id": g["current-day-id"]}]

    if event["type"] == "DAY_LAYOUT_RECEIVED":
        layout = event["layout"]
        g["current-day-id"] = layout["day"]["id"]
        g["selected-tab-id"] = layout["day"]["selected-tab-id"]
        g["orientation-position"] = layout["day"]["orientation-position"]
        g["known-panel-ids"] = layout["panel-ids"]
        tabs.clear()
        tabs.update(layout["tabs"])
        rows.clear()
        rows.update(layout["rows"])
        positions.clear()
        positions.update(layout["positions"])
        visible_panels.clear()
        g["pending-initial-panel-ids"] = sorted(g["known-panel-ids"])
        return [
            {"type": "GET_PANEL", "panel-id": panel_id}
            for panel_id in g["pending-initial-panel-ids"]
        ]

    if event["type"] == "SELECT_PREVIOUS_DAY":
        return request_day_navigation(
            (date.fromisoformat(g["current-day-id"]) - timedelta(days=1)).isoformat()
        )

    if event["type"] == "SELECT_NEXT_DAY":
        return request_day_navigation(
            (date.fromisoformat(g["current-day-id"]) + timedelta(days=1)).isoformat()
        )

    if event["type"] == "SELECT_TODAY":
        return request_day_navigation(date.today().isoformat())

    if event["type"] == "PANEL_RECEIVED":
        install_panel_snapshot(event["panel"])
        print("Core reducer: PANEL_RECEIVED", event["panel-id"])
        if event["panel-id"] in g["pending-initial-panel-ids"]:
            g["pending-initial-panel-ids"].remove(event["panel-id"])
        if not g["pending-initial-panel-ids"]:
            return [{"type": "RENDER_TODAY"}]
        return []

    if event["type"] == "HOST_PANEL":
        return [
            {
                "type": "GET_PANEL",
                "panel-id": event["panel-id"],
                "position-id": event["position-id"],
            }
        ]

    if event["type"] == "SELECT_TAB":
        return [{"type": "SELECT_TAB", "tab-id": event["tab-id"]}]

    if event["type"] == "TAB_SELECTED":
        g["selected-tab-id"] = event["tab-id"]
        return [{"type": "SET_SELECTED_TAB", "tab-id": event["tab-id"]}]

    if event["type"] == "SET_ROW_HEIGHT":
        return [{"type": "REQUEST_ROW_HEIGHT", "row-id": event["row-id"], "height": event["height"]}]

    if event["type"] == "SET_SASH_PROPORTIONS":
        return [
            {
                "type": "REQUEST_SASH_PROPORTIONS",
                "row-id": event["row-id"],
                "sash-proportions": event["sash-proportions"],
            }
        ]

    if event["type"] == "SET_ROW_COLUMN_COUNT":
        return [
            {
                "type": "REQUEST_ROW_COLUMN_COUNT",
                "row-id": event["row-id"],
                "column-count": event["column-count"],
            }
        ]

    if event["type"] == "ROW_LAYOUT_CHANGED":
        old_column_count = rows[event["row"]["id"]]["column-count"]
        rows[event["row"]["id"]] = event["row"]
        if event["layout-change"] == "ROW_HEIGHT":
            return [{"type": "SET_ROW_HEIGHT", "row-id": event["row"]["id"]}]
        if event["layout-change"] == "ROW_COLUMNS":
            for column in range(event["row"]["column-count"] + 1, old_column_count + 1):
                positions.pop(get_position_id(event["row"]["id"], column), None)
            for column in range(1, event["row"]["column-count"] + 1):
                positions.setdefault(get_position_id(event["row"]["id"], column), {"panel-id": None})
            return [{"type": "RENDER_TODAY"}]
        return [{"type": "SET_SASH_PROPORTIONS", "row-id": event["row"]["id"]}]

    if event["type"] == "MOVE_ROW":
        return [
            {
                "type": "MOVE_ROW",
                "tab-id": event["tab-id"],
                "row-id": event["row-id"],
                "direction": event["direction"],
            }
        ]

    if event["type"] == "ADD_ROW":
        return [{"type": "ADD_ROW", "tab-id": event["tab-id"]}]

    if event["type"] == "DELETE_ROW":
        return [
            {
                "type": "DELETE_ROW",
                "tab-id": event["tab-id"],
                "row-id": event["row-id"],
            }
        ]

    if event["type"] == "SET_TAB_SCROLL_POSITION":
        return [
            {
                "type": "REQUEST_TAB_SCROLL_POSITION",
                "tab-id": event["tab-id"],
                "scroll-position": event["scroll-position"],
            }
        ]

    if event["type"] == "TAB_LAYOUT_CHANGED":
        tabs[event["tab"]["id"]] = event["tab"]
        if "row" in event:
            row = event["row"]
            rows[row["id"]] = row
            positions[get_position_id(row["id"], 1)] = {"panel-id": None}
        if event["deleted-row-id"] is not None:
            deleted_row = rows.pop(event["deleted-row-id"])
            for column in range(1, deleted_row["column-count"] + 1):
                positions.pop(get_position_id(deleted_row["id"], column), None)
        if event["layout-change"] == "TAB_SCROLL_POSITION":
            return [{"type": "SET_TAB_SCROLL_POSITION", "tab-id": event["tab"]["id"]}]
        return [{"type": "RENDER_TODAY"}]

    if event["type"] == "CREATE_TAB":
        return [{"type": "CREATE_TAB", "day-id": g["current-day-id"]}]

    if event["type"] == "TAB_CREATED":
        g["selected-tab-id"] = event["day"]["selected-tab-id"]
        tabs[event["tab"]["id"]] = event["tab"]
        rows[event["row"]["id"]] = event["row"]
        positions[get_position_id(event["row"]["id"], 1)] = {"panel-id": None}
        return [{"type": "RENDER_TODAY"}]

    if event["type"] == "RENAME_TAB":
        return [{"type": "RENAME_TAB", "tab-id": event["tab-id"], "label": event["label"]}]

    if event["type"] == "TAB_RENAMED":
        tabs[event["tab"]["id"]] = event["tab"]
        return [{"type": "SET_TAB_LABEL", "tab-id": event["tab"]["id"]}]

    if event["type"] == "DELETE_TAB":
        return [{"type": "DELETE_TAB", "day-id": g["current-day-id"], "tab-id": event["tab-id"]}]

    if event["type"] == "TAB_DELETED":
        if not event["deleted"]:
            return []
        tab = tabs.pop(event["tab-id"])
        for row_id in tab["row-ids"]:
            row = rows.pop(row_id)
            for column in range(1, row["column-count"] + 1):
                positions.pop(get_position_id(row_id, column), None)
        g["selected-tab-id"] = event["day"]["selected-tab-id"]
        return [{"type": "RENDER_TODAY"}]

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
        return [
            {
                "type": "HOST_PANEL",
                "position-id": event["position-id"],
                "panel-id": event["panel-id"],
            }
        ]

    if event["type"] == "UNHOST_PANEL":
        return [{"type": "UNHOST_PANEL", "position-id": event["position-id"]}]

    if event["type"] == "HOSTING_CHANGED":
        positions[event["position-id"]]["panel-id"] = event["panel-id"]
        if event["unhosted-position-id"] is not None:
            positions[event["unhosted-position-id"]]["panel-id"] = None
        tab_id = get_tab_id_for_position(event["position-id"])
        position_ids_to_render = [event["position-id"]]
        for position_id in get_position_ids_for_tab(tab_id):
            if positions[position_id]["panel-id"] is None:
                position_ids_to_render.append(position_id)
        return [
            {"type": "RENDER_POSITION", "position-id": position_id}
            for position_id in dict.fromkeys(position_ids_to_render)
        ]

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
        if panel["type"] not in {"WHITEBOARD", "ORIENTATION"}:
            return []
        if panel["type"] == "WHITEBOARD" and panel["history-cursor"] != 0:
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
        return [prepare_text_panel_update(event["panel-id"])]

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
        return [prepare_text_panel_update(event["panel-id"])]

    if event["type"] == "PANEL_UPDATED":
        install_panel_snapshot(event["panel"])
        print("Core reducer: PANEL_UPDATED", event["panel-id"], "revision", event["panel"]["revision"])
        return [{"type": "SET_PANEL_LABEL", "panel-id": event["panel-id"]}]

    if event["type"] == "TEXT_PANEL_UPDATED":
        panel = visible_panels[event["panel-id"]]
        accepted_panel = event["panel"]
        if panel["edit-generation"] > event["save-generation"]:
            panel["revision"] = accepted_panel["revision"]
            panel["save-generation"] = None
            panel["awaiting"] = "TEXT_DEBOUNCE"
            return [prepare_text_panel_update(event["panel-id"])]
        install_panel_snapshot(accepted_panel)
        print("Core reducer: TEXT_PANEL_UPDATED", event["panel-id"], "revision", accepted_panel["revision"])
        if accepted_panel["type"] == "ORIENTATION":
            return [
                {"type": "SET_ORIENTATION_TEXT", "panel-id": event["panel-id"]},
                *get_day_navigation_effect_when_ready(),
            ]
        return [
            {"type": "RENDER_WHITEBOARD_VIEW", "panel-id": event["panel-id"]},
            *get_day_navigation_effect_when_ready(),
        ]

    if event["type"] == "PANEL_UPDATE_CONFLICT":
        print("Core reducer: PANEL_UPDATE_CONFLICT", event["panel-id"], "revision", event["panel"]["revision"])
        return []

    if event["type"] == "SHUTDOWN":
        return [{"type": "STOP_CORE"}, {"type": "STOP_MEM"}, {"type": "SHUTDOWN_TK"}]

    return []


def dispatch_effect(effect):
    if effect["type"] == "GET_DAY_LAYOUT":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", effect["day-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "DAY_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "DAY_BUNDLE_RETURNED"})
        mobile_stacks.push_frame({"machine": "DISK", "entry": "LOAD_DAY"})
        machine.route_current_stack()
        return

    if effect["type"] == "GET_PANEL":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", g["current-day-id"]))
        mobile_stacks.set_register(("panel-id", effect["panel-id"]))
        if "position-id" in effect:
            mobile_stacks.set_register(("position-id", effect["position-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "PANEL_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "GET_PANEL"})
        machine.route_current_stack()
        return

    if effect["type"] == "HOST_PANEL":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", g["current-day-id"]))
        mobile_stacks.set_register(("position-id", effect["position-id"]))
        mobile_stacks.set_register(("panel-id", effect["panel-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "HOSTING_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "HOST_PANEL"})
        machine.route_current_stack()
        return

    if effect["type"] == "SELECT_TAB":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", g["current-day-id"]))
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "SELECTED_TAB_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "SELECT_TAB"})
        machine.route_current_stack()
        return

    if effect["type"] == "REQUEST_ROW_HEIGHT":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("row-id", effect["row-id"]))
        mobile_stacks.set_register(("height", effect["height"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "ROW_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "SET_ROW_HEIGHT"})
        machine.route_current_stack()
        return

    if effect["type"] == "REQUEST_SASH_PROPORTIONS":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("row-id", effect["row-id"]))
        mobile_stacks.set_register(("sash-proportions", effect["sash-proportions"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "ROW_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "SET_SASH_PROPORTIONS"})
        machine.route_current_stack()
        return

    if effect["type"] == "REQUEST_ROW_COLUMN_COUNT":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("row-id", effect["row-id"]))
        mobile_stacks.set_register(("column-count", effect["column-count"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "ROW_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "SET_ROW_COLUMN_COUNT"})
        machine.route_current_stack()
        return

    if effect["type"] == "MOVE_ROW":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.set_register(("row-id", effect["row-id"]))
        mobile_stacks.set_register(("direction", effect["direction"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "MOVE_ROW"})
        machine.route_current_stack()
        return

    if effect["type"] == "ADD_ROW":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "ADD_ROW"})
        machine.route_current_stack()
        return

    if effect["type"] == "DELETE_ROW":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.set_register(("row-id", effect["row-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "DELETE_ROW"})
        machine.route_current_stack()
        return

    if effect["type"] == "REQUEST_TAB_SCROLL_POSITION":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.set_register(("scroll-position", effect["scroll-position"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_LAYOUT_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "SET_TAB_SCROLL_POSITION"})
        machine.route_current_stack()
        return

    if effect["type"] == "CREATE_TAB":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", effect["day-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_CREATED_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "CREATE_TAB"})
        machine.route_current_stack()
        return

    if effect["type"] == "RENAME_TAB":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.set_register(("label", effect["label"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_RENAMED_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "RENAME_TAB"})
        machine.route_current_stack()
        return

    if effect["type"] == "DELETE_TAB":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", effect["day-id"]))
        mobile_stacks.set_register(("tab-id", effect["tab-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "TAB_DELETED_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "DELETE_TAB"})
        machine.route_current_stack()
        return

    if effect["type"] == "UNHOST_PANEL":
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", g["current-day-id"]))
        mobile_stacks.set_register(("position-id", effect["position-id"]))
        mobile_stacks.push_frame({"machine": "CORE", "entry": "HOSTING_RETURNED"})
        mobile_stacks.push_frame({"machine": "MEM", "entry": "UNHOST_PANEL"})
        machine.route_current_stack()
        return

    if effect["type"] == "UPDATE_PANEL":
        print("Reducer effect: UPDATE_PANEL", effect["panel-id"], "base-revision", effect["base-revision"])
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-id", g["current-day-id"]))
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
                "today-id": g["current-day-id"],
                **get_day_rendering(),
            }
        )
        return

    if effect["type"] == "SET_PANEL_LABEL":
        panel = visible_panels[effect["panel-id"]]
        g["send-tk-command"](
            {"type": "SET_PANEL_LABEL", "panel-id": panel["id"], "panel-label": panel["label"]}
        )
        return

    if effect["type"] == "RENDER_POSITION":
        g["send-tk-command"](
            {
                "type": "RENDER_POSITION",
                **get_position_rendering(effect["position-id"]),
            }
        )
        return

    if effect["type"] == "SET_SELECTED_TAB":
        g["send-tk-command"]({"type": "SET_SELECTED_TAB", "tab-id": effect["tab-id"]})
        return

    if effect["type"] == "SET_ROW_HEIGHT":
        g["send-tk-command"](
            {"type": "SET_ROW_HEIGHT", "row-id": effect["row-id"], "height": rows[effect["row-id"]]["height"]}
        )
        return

    if effect["type"] == "SET_SASH_PROPORTIONS":
        g["send-tk-command"](
            {
                "type": "SET_SASH_PROPORTIONS",
                "row-id": effect["row-id"],
                "sash-proportions": rows[effect["row-id"]]["sash-proportions"],
            }
        )
        return

    if effect["type"] == "SET_TAB_SCROLL_POSITION":
        g["send-tk-command"](
            {
                "type": "SET_TAB_SCROLL_POSITION",
                "tab-id": effect["tab-id"],
                "scroll-position": tabs[effect["tab-id"]]["scroll-position"],
            }
        )
        return

    if effect["type"] == "SET_TAB_LABEL":
        g["send-tk-command"](
            {
                "type": "SET_TAB_LABEL",
                "tab-id": effect["tab-id"],
                "tab-label": tabs[effect["tab-id"]]["label"],
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

    if effect["type"] == "SET_ORIENTATION_TEXT":
        panel = visible_panels[effect["panel-id"]]
        g["send-tk-command"](
            {
                "type": "SET_ORIENTATION_TEXT",
                "panel-id": panel["id"],
                "panel-text": panel["text"],
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


def handle_when_core_receives_day_layout():
    g["reducer-events"].append(
        {"type": "DAY_LAYOUT_RECEIVED", "layout": deepcopy(mobile_stacks.get_register("layout"))}
    )


def handle_when_core_receives_hosting_update():
    g["reducer-events"].append(
        {
            "type": "HOSTING_CHANGED",
            "position-id": mobile_stacks.get_register("position-id"),
            "panel-id": mobile_stacks.get_register("panel-id"),
            "unhosted-position-id": mobile_stacks.get_register("unhosted-position-id"),
        }
    )


def handle_when_core_receives_selected_tab():
    g["reducer-events"].append(
        {"type": "TAB_SELECTED", "tab-id": mobile_stacks.get_register("tab-id")}
    )


def handle_when_core_receives_row_layout():
    g["reducer-events"].append(
        {
            "type": "ROW_LAYOUT_CHANGED",
            "row": deepcopy(mobile_stacks.get_register("row")),
            "layout-change": mobile_stacks.get_register("layout-change"),
        }
    )


def handle_when_core_receives_tab_layout():
    event = {
        "type": "TAB_LAYOUT_CHANGED",
        "tab": deepcopy(mobile_stacks.get_register("tab")),
        "layout-change": mobile_stacks.get_register("layout-change"),
        "deleted-row-id": mobile_stacks.get_register("deleted-row-id")
        if mobile_stacks.has_register("deleted-row-id")
        else None,
    }
    if mobile_stacks.has_register("row"):
        event["row"] = deepcopy(mobile_stacks.get_register("row"))
    g["reducer-events"].append(event)


def handle_when_core_receives_created_tab():
    g["reducer-events"].append(
        {
            "type": "TAB_CREATED",
            "day": deepcopy(mobile_stacks.get_register("day")),
            "tab": deepcopy(mobile_stacks.get_register("tab")),
            "row": deepcopy(mobile_stacks.get_register("row")),
        }
    )


def handle_when_core_receives_renamed_tab():
    g["reducer-events"].append(
        {"type": "TAB_RENAMED", "tab": deepcopy(mobile_stacks.get_register("tab"))}
    )


def handle_when_core_receives_deleted_tab():
    g["reducer-events"].append(
        {
            "type": "TAB_DELETED",
            "day": deepcopy(mobile_stacks.get_register("day")),
            "tab-id": mobile_stacks.get_register("tab-id"),
            "deleted": mobile_stacks.get_register("deleted"),
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
                    "type": "TEXT_PANEL_UPDATED",
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
