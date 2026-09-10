"""The Mem machine: the small canonical in-memory store."""

from copy import deepcopy
from datetime import date
from uuid import uuid4

from . import machine, mobile_stacks

days = {}
tabs = {}
rows = {}
positions = {}
panels = {}


def initialize_mem_store():
    today_id = date.today().isoformat()
    days[today_id] = {
        "id": today_id,
        "tab-ids": ["tab-a", "tab-b"],
        "selected-tab-id": "tab-a",
    }
    tabs["tab-a"] = {
        "id": "tab-a",
        "day-id": today_id,
        "label": "Tab A",
        "row-ids": ["row-a", "row-b"],
        "scroll-position": 0.0,
    }
    tabs["tab-b"] = {
        "id": "tab-b",
        "day-id": today_id,
        "label": "Tab B",
        "row-ids": ["row-c", "row-d"],
        "scroll-position": 0.0,
    }
    rows["row-a"] = {
        "id": "row-a",
        "tab-id": "tab-a",
        "column-count": 2,
        "height": 260,
        "sash-proportions": [0.5],
    }
    rows["row-b"] = {
        "id": "row-b",
        "tab-id": "tab-a",
        "column-count": 1,
        "height": 160,
        "sash-proportions": [],
    }
    rows["row-c"] = {
        "id": "row-c",
        "tab-id": "tab-b",
        "column-count": 2,
        "height": 260,
        "sash-proportions": [0.5],
    }
    rows["row-d"] = {
        "id": "row-d",
        "tab-id": "tab-b",
        "column-count": 1,
        "height": 160,
        "sash-proportions": [],
    }
    positions["row-a/column-1"] = {"panel-id": "whiteboard-a"}
    positions["row-a/column-2"] = {"panel-id": "whiteboard-b"}
    positions["row-b/column-1"] = {"panel-id": None}
    positions["row-c/column-1"] = {"panel-id": "whiteboard-a"}
    positions["row-c/column-2"] = {"panel-id": "whiteboard-c"}
    positions["row-d/column-1"] = {"panel-id": None}
    panels["whiteboard-a"] = {
        "id": "whiteboard-a",
        "day-id": today_id,
        "type": "WHITEBOARD",
        "label": "Whiteboard A",
        "text": "",
        "history": [],
        "revision": 1,
    }
    panels["whiteboard-b"] = {
        "id": "whiteboard-b",
        "day-id": today_id,
        "type": "WHITEBOARD",
        "label": "Whiteboard B",
        "text": "",
        "history": [],
        "revision": 1,
    }
    panels["whiteboard-c"] = {
        "id": "whiteboard-c",
        "day-id": today_id,
        "type": "WHITEBOARD",
        "label": "Whiteboard C",
        "text": "",
        "history": [],
        "revision": 1,
    }


def create_new_day(day_id):
    tab_id = f"tab-{uuid4().hex}"
    row_id = f"row-{uuid4().hex}"
    panel_id = f"whiteboard-{uuid4().hex}"
    days[day_id] = {"id": day_id, "tab-ids": [tab_id], "selected-tab-id": tab_id}
    tabs[tab_id] = {
        "id": tab_id,
        "day-id": day_id,
        "label": "Tab A",
        "row-ids": [row_id],
        "scroll-position": 0.0,
    }
    rows[row_id] = {
        "id": row_id,
        "tab-id": tab_id,
        "column-count": 1,
        "height": 260,
        "sash-proportions": [],
    }
    positions[get_position_id(row_id, 1)] = {"panel-id": panel_id}
    panels[panel_id] = {
        "id": panel_id,
        "day-id": day_id,
        "type": "WHITEBOARD",
        "label": "Whiteboard",
        "text": "",
        "history": [],
        "revision": 1,
    }
    print("Mem CREATE_DAY:", day_id)


def get_position_id(row_id, column):
    return f"{row_id}/column-{column}"


def get_tab_id_for_position(position_id):
    row_id = position_id.split("/", 1)[0]
    return rows[row_id]["tab-id"]


def get_day_id_for_position(position_id):
    return tabs[get_tab_id_for_position(position_id)]["day-id"]


def handle_when_mem_receives_get_day_layout():
    day_id = mobile_stacks.get_register("day-id")
    if day_id not in days:
        create_new_day(day_id)
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
                "panel-ids": sorted(panel_id for panel_id, panel in panels.items() if panel["day-id"] == day_id),
            },
        )
    )


def handle_when_mem_receives_get_panel():
    day_id = mobile_stacks.get_register("day-id")
    panel_id = mobile_stacks.get_register("panel-id")
    if panels[panel_id]["day-id"] != day_id:
        raise RuntimeError(f"panel {panel_id} does not belong to day {day_id}")
    print("Mem GET_PANEL:", panel_id)
    mobile_stacks.set_register(("panel", deepcopy(panels[panel_id])))


def handle_when_mem_receives_select_tab():
    day_id = mobile_stacks.get_register("day-id")
    tab_id = mobile_stacks.get_register("tab-id")
    if tab_id not in days[day_id]["tab-ids"]:
        raise RuntimeError(f"tab {tab_id} is not in day {day_id}")
    days[day_id]["selected-tab-id"] = tab_id
    print("Mem SELECT_TAB:", day_id, tab_id)
    mobile_stacks.set_register(("day-id", day_id))
    mobile_stacks.set_register(("tab-id", tab_id))


def handle_when_mem_receives_set_row_height():
    row_id = mobile_stacks.get_register("row-id")
    rows[row_id]["height"] = mobile_stacks.get_register("height")
    print("Mem SET_ROW_HEIGHT:", row_id, rows[row_id]["height"])
    mobile_stacks.set_register(("row", deepcopy(rows[row_id])))
    mobile_stacks.set_register(("layout-change", "ROW_HEIGHT"))


def handle_when_mem_receives_set_sash_proportions():
    row_id = mobile_stacks.get_register("row-id")
    rows[row_id]["sash-proportions"] = mobile_stacks.get_register("sash-proportions")
    print("Mem SET_SASH_PROPORTIONS:", row_id, rows[row_id]["sash-proportions"])
    mobile_stacks.set_register(("row", deepcopy(rows[row_id])))
    mobile_stacks.set_register(("layout-change", "SASH_PROPORTIONS"))


def handle_when_mem_receives_set_row_column_count():
    row_id = mobile_stacks.get_register("row-id")
    column_count = mobile_stacks.get_register("column-count")
    if column_count not in {1, 2, 3}:
        raise RuntimeError(f"invalid column count {column_count}")

    row = rows[row_id]
    old_column_count = row["column-count"]
    if column_count < old_column_count:
        for column in range(column_count + 1, old_column_count + 1):
            positions.pop(get_position_id(row_id, column))
    else:
        for column in range(old_column_count + 1, column_count + 1):
            positions[get_position_id(row_id, column)] = {"panel-id": None}

    row["column-count"] = column_count
    row["sash-proportions"] = [column / column_count for column in range(1, column_count)]
    print("Mem SET_ROW_COLUMN_COUNT:", row_id, column_count)
    mobile_stacks.set_register(("row", deepcopy(row)))
    mobile_stacks.set_register(("layout-change", "ROW_COLUMNS"))


def handle_when_mem_receives_move_row():
    tab_id = mobile_stacks.get_register("tab-id")
    row_id = mobile_stacks.get_register("row-id")
    direction = mobile_stacks.get_register("direction")
    row_ids = tabs[tab_id]["row-ids"]
    old_index = row_ids.index(row_id)
    new_index = max(0, min(len(row_ids) - 1, old_index + direction))
    row_ids.pop(old_index)
    row_ids.insert(new_index, row_id)
    print("Mem MOVE_ROW:", row_id, "to", new_index)
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))
    mobile_stacks.set_register(("layout-change", "TAB_ROWS"))


def handle_when_mem_receives_delete_row():
    tab_id = mobile_stacks.get_register("tab-id")
    row_id = mobile_stacks.get_register("row-id")
    row_ids = tabs[tab_id]["row-ids"]
    deleted = len(row_ids) > 1
    if deleted:
        row_ids.remove(row_id)
        row = rows.pop(row_id)
        for column in range(1, row["column-count"] + 1):
            positions.pop(get_position_id(row_id, column))
    print("Mem DELETE_ROW:", row_id, "deleted" if deleted else "kept final row")
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))
    mobile_stacks.set_register(("deleted-row-id", row_id if deleted else None))
    mobile_stacks.set_register(("layout-change", "TAB_ROWS"))


def handle_when_mem_receives_add_row():
    tab_id = mobile_stacks.get_register("tab-id")
    row_id = f"row-{uuid4().hex}"
    rows[row_id] = {
        "id": row_id,
        "tab-id": tab_id,
        "column-count": 1,
        "height": 160,
        "sash-proportions": [],
    }
    positions[get_position_id(row_id, 1)] = {"panel-id": None}
    tabs[tab_id]["row-ids"].append(row_id)
    print("Mem ADD_ROW:", tab_id, row_id)
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))
    mobile_stacks.set_register(("row", deepcopy(rows[row_id])))
    mobile_stacks.set_register(("layout-change", "TAB_ROWS"))


def handle_when_mem_receives_set_tab_scroll_position():
    tab_id = mobile_stacks.get_register("tab-id")
    scroll_position = mobile_stacks.get_register("scroll-position")
    tabs[tab_id]["scroll-position"] = max(0.0, min(1.0, scroll_position))
    print("Mem SET_TAB_SCROLL_POSITION:", tab_id, tabs[tab_id]["scroll-position"])
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))
    mobile_stacks.set_register(("layout-change", "TAB_SCROLL_POSITION"))


def handle_when_mem_receives_create_tab():
    day_id = mobile_stacks.get_register("day-id")
    tab_id = f"tab-{uuid4().hex}"
    row_id = f"row-{uuid4().hex}"
    tabs[tab_id] = {
        "id": tab_id,
        "day-id": day_id,
        "label": f"Tab {len(days[day_id]['tab-ids']) + 1}",
        "row-ids": [row_id],
        "scroll-position": 0.0,
    }
    rows[row_id] = {
        "id": row_id,
        "tab-id": tab_id,
        "column-count": 1,
        "height": 160,
        "sash-proportions": [],
    }
    positions[get_position_id(row_id, 1)] = {"panel-id": None}
    days[day_id]["tab-ids"].append(tab_id)
    days[day_id]["selected-tab-id"] = tab_id
    print("Mem CREATE_TAB:", day_id, tab_id)
    mobile_stacks.set_register(("day", deepcopy(days[day_id])))
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))
    mobile_stacks.set_register(("row", deepcopy(rows[row_id])))


def handle_when_mem_receives_rename_tab():
    tab_id = mobile_stacks.get_register("tab-id")
    label = mobile_stacks.get_register("label").strip()
    if not label:
        raise RuntimeError("tab label cannot be empty")
    tabs[tab_id]["label"] = label
    print("Mem RENAME_TAB:", tab_id, label)
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))


def handle_when_mem_receives_delete_tab():
    day_id = mobile_stacks.get_register("day-id")
    tab_id = mobile_stacks.get_register("tab-id")
    day = days[day_id]
    deleted = len(day["tab-ids"]) > 1
    if deleted:
        old_index = day["tab-ids"].index(tab_id)
        day["tab-ids"].remove(tab_id)
        for row_id in tabs[tab_id]["row-ids"]:
            row = rows.pop(row_id)
            for column in range(1, row["column-count"] + 1):
                positions.pop(get_position_id(row_id, column))
        tabs.pop(tab_id)
        day["selected-tab-id"] = day["tab-ids"][min(old_index, len(day["tab-ids"]) - 1)]
    print("Mem DELETE_TAB:", tab_id, "deleted" if deleted else "kept final tab")
    mobile_stacks.set_register(("day", deepcopy(day)))
    mobile_stacks.set_register(("tab-id", tab_id))
    mobile_stacks.set_register(("deleted", deleted))


def handle_when_mem_receives_update_panel():
    day_id = mobile_stacks.get_register("day-id")
    panel_id = mobile_stacks.get_register("panel-id")
    base_revision = mobile_stacks.get_register("base-revision")
    current_panel = panels[panel_id]
    if current_panel["day-id"] != day_id:
        raise RuntimeError(f"panel {panel_id} does not belong to day {day_id}")

    if current_panel["revision"] != base_revision:
        print("Mem UPDATE_PANEL conflict:", panel_id, "revision", current_panel["revision"])
        mobile_stacks.set_register(("update-result", "conflict"))
        mobile_stacks.set_register(("panel", deepcopy(current_panel)))
        return

    accepted_panel = deepcopy(mobile_stacks.get_register("proposed-panel"))
    accepted_panel["id"] = panel_id
    accepted_panel["day-id"] = day_id
    accepted_panel["revision"] = current_panel["revision"] + 1
    panels[panel_id] = accepted_panel
    print("Mem UPDATE_PANEL:", panel_id, "revision", base_revision, "->", accepted_panel["revision"])
    mobile_stacks.set_register(("update-result", "accepted"))
    mobile_stacks.set_register(("panel", deepcopy(accepted_panel)))


def handle_when_mem_receives_host_panel():
    day_id = mobile_stacks.get_register("day-id")
    position_id = mobile_stacks.get_register("position-id")
    panel_id = mobile_stacks.get_register("panel-id")
    tab_id = get_tab_id_for_position(position_id)
    if get_day_id_for_position(position_id) != day_id or panels[panel_id]["day-id"] != day_id:
        raise RuntimeError(f"panel {panel_id} cannot be hosted outside day {day_id}")
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
    day_id = mobile_stacks.get_register("day-id")
    position_id = mobile_stacks.get_register("position-id")
    if get_day_id_for_position(position_id) != day_id:
        raise RuntimeError(f"position {position_id} does not belong to day {day_id}")
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
