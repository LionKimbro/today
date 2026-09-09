"""The Mem machine: the small canonical in-memory store."""

from copy import deepcopy
from datetime import date

from . import machine, mobile_stacks

days = {}
tabs = {}
rows = {}
positions = {}
panels = {}


def initialize_mem_store():
    today_id = date.today().isoformat()
    days[today_id] = {"id": today_id, "tab-ids": ["tab-a"], "selected-tab-id": "tab-a"}
    tabs["tab-a"] = {"id": "tab-a", "day-id": today_id, "label": "Tab A", "row-ids": ["row-a", "row-b"]}
    rows["row-a"] = {"id": "row-a", "tab-id": "tab-a", "column-count": 2}
    rows["row-b"] = {"id": "row-b", "tab-id": "tab-a", "column-count": 1}
    positions["row-a/column-1"] = {"panel-id": "whiteboard-a"}
    positions["row-a/column-2"] = {"panel-id": "whiteboard-b"}
    positions["row-b/column-1"] = {"panel-id": None}
    panels["whiteboard-a"] = {
        "id": "whiteboard-a",
        "type": "WHITEBOARD",
        "label": "Whiteboard A",
        "text": "",
        "history": [],
        "revision": 1,
    }
    panels["whiteboard-b"] = {
        "id": "whiteboard-b",
        "type": "WHITEBOARD",
        "label": "Whiteboard B",
        "text": "",
        "history": [],
        "revision": 1,
    }
    panels["whiteboard-c"] = {
        "id": "whiteboard-c",
        "type": "WHITEBOARD",
        "label": "Whiteboard C",
        "text": "",
        "history": [],
        "revision": 1,
    }


def get_position_id(row_id, column):
    return f"{row_id}/column-{column}"


def get_tab_id_for_position(position_id):
    row_id = position_id.split("/", 1)[0]
    return rows[row_id]["tab-id"]


def handle_when_mem_receives_get_day_layout():
    day_id = mobile_stacks.get_register("day-id")
    day = days[day_id]
    tab_records = {tab_id: deepcopy(tabs[tab_id]) for tab_id in day["tab-ids"]}
    row_records = {
        row_id: deepcopy(rows[row_id])
        for tab in tab_records.values()
        for row_id in tab["row-ids"]
    }
    position_records = {
        get_position_id(row_id, column): deepcopy(positions[get_position_id(row_id, column)])
        for row_id, row in row_records.items()
        for column in range(1, row["column-count"] + 1)
    }
    print("Mem GET_DAY_LAYOUT:", day_id)
    mobile_stacks.set_register(
        (
            "layout",
            {
                "day": deepcopy(day),
                "tabs": tab_records,
                "rows": row_records,
                "positions": position_records,
                "panel-ids": sorted(panels),
            },
        )
    )


def handle_when_mem_receives_get_panel():
    panel_id = mobile_stacks.get_register("panel-id")
    print("Mem GET_PANEL:", panel_id)
    mobile_stacks.set_register(("panel", deepcopy(panels[panel_id])))


def handle_when_mem_receives_update_panel():
    panel_id = mobile_stacks.get_register("panel-id")
    base_revision = mobile_stacks.get_register("base-revision")
    current_panel = panels[panel_id]

    if current_panel["revision"] != base_revision:
        print("Mem UPDATE_PANEL conflict:", panel_id, "revision", current_panel["revision"])
        mobile_stacks.set_register(("update-result", "conflict"))
        mobile_stacks.set_register(("panel", deepcopy(current_panel)))
        return

    accepted_panel = deepcopy(mobile_stacks.get_register("proposed-panel"))
    accepted_panel["id"] = panel_id
    accepted_panel["revision"] = current_panel["revision"] + 1
    panels[panel_id] = accepted_panel
    print("Mem UPDATE_PANEL:", panel_id, "revision", base_revision, "->", accepted_panel["revision"])
    mobile_stacks.set_register(("update-result", "accepted"))
    mobile_stacks.set_register(("panel", deepcopy(accepted_panel)))


def handle_when_mem_receives_host_panel():
    position_id = mobile_stacks.get_register("position-id")
    panel_id = mobile_stacks.get_register("panel-id")
    tab_id = get_tab_id_for_position(position_id)
    unhosted_position_id = None

    for row_id in tabs[tab_id]["row-ids"]:
        for column in range(1, rows[row_id]["column-count"] + 1):
            other_position_id = get_position_id(row_id, column)
            if other_position_id != position_id and positions[other_position_id]["panel-id"] == panel_id:
                positions[other_position_id]["panel-id"] = None
                unhosted_position_id = other_position_id

    positions[position_id]["panel-id"] = panel_id
    print("Mem HOST_PANEL:", position_id, "hosts", panel_id)
    mobile_stacks.set_register(("position-id", position_id))
    mobile_stacks.set_register(("panel-id", panel_id))
    mobile_stacks.set_register(("unhosted-position-id", unhosted_position_id))


def handle_when_mem_receives_unhost_panel():
    position_id = mobile_stacks.get_register("position-id")
    panel_id = positions[position_id]["panel-id"]
    positions[position_id]["panel-id"] = None
    print("Mem UNHOST_PANEL:", position_id, "unhosts", panel_id)
    mobile_stacks.set_register(("position-id", position_id))
    mobile_stacks.set_register(("panel-id", None))
    mobile_stacks.set_register(("unhosted-position-id", None))


def run_mem_machine():
    machine.claim_machine("MEM")
    initialize_mem_store()
    machine.run_machine()
