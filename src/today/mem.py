"""The Mem machine: the small canonical in-memory store."""

from copy import deepcopy
from queue import Empty
from time import monotonic
from uuid import uuid4

from . import machine, mobile_stacks

days = {}
tabs = {}
rows = {}
positions = {}
panels = {}
g = {"pending-day-writes": {}}


def initialize_mem_store():
    days.clear()
    tabs.clear()
    rows.clear()
    positions.clear()
    panels.clear()
    g["pending-day-writes"].clear()


def create_new_day(day_id):
    tab_id = f"tab-{uuid4().hex}"
    row_id = f"row-{uuid4().hex}"
    panel_id = f"whiteboard-{uuid4().hex}"
    orientation_panel_id = f"orientation-{uuid4().hex}"
    days[day_id] = {
        "id": day_id,
        "tab-ids": [tab_id],
        "selected-tab-id": tab_id,
        "orientation-position": {
            "id": f"{day_id}/orientation-position",
            "panel-id": orientation_panel_id,
        },
    }
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
    panels[orientation_panel_id] = {
        "id": orientation_panel_id,
        "day-id": day_id,
        "type": "ORIENTATION",
        "label": "Orientation",
        "text": "",
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


def make_day_bundle(day_id):
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
    panel_records = {
        panel_id: deepcopy(panel)
        for panel_id, panel in panels.items()
        if panel["day-id"] == day_id
    }
    return {
        "format": "today-day-v1",
        "day": deepcopy(day),
        "tabs": tab_records,
        "rows": row_records,
        "positions": position_records,
        "panels": panel_records,
    }


def install_day_bundle(bundle):
    day = bundle["day"]
    day_id = day["id"]
    if bundle.get("format") != "today-day-v1":
        raise RuntimeError(f"unsupported day bundle for {day_id}")
    if any(panel["day-id"] != day_id for panel in bundle["panels"].values()):
        raise RuntimeError(f"panel ownership mismatch in {day_id}")
    days[day_id] = deepcopy(day)
    tabs.update(deepcopy(bundle["tabs"]))
    rows.update(deepcopy(bundle["rows"]))
    positions.update(deepcopy(bundle["positions"]))
    panels.update(deepcopy(bundle["panels"]))


def make_day_layout(day_id):
    bundle = make_day_bundle(day_id)
    return {
        "day": bundle["day"],
        "tabs": bundle["tabs"],
        "rows": bundle["rows"],
        "positions": bundle["positions"],
        "panel-ids": sorted(bundle["panels"]),
    }


def mark_day_for_disk_save(day_id):
    g["pending-day-writes"][day_id] = monotonic() + 1.0


def handle_when_mem_receives_day_bundle():
    day_id = mobile_stacks.get_register("day-id")
    if day_id not in days:
        bundle = mobile_stacks.get_register("day-bundle")
        if bundle is None:
            create_new_day(day_id)
            mark_day_for_disk_save(day_id)
        else:
            install_day_bundle(bundle)
    print("Mem GET_DAY_LAYOUT:", day_id)
    mobile_stacks.set_register(("layout", make_day_layout(day_id)))


def handle_when_mem_receives_get_panel():
    day_id = mobile_stacks.get_register("day-id")
    panel_id = mobile_stacks.get_register("panel-id")
    if panels[panel_id]["day-id"] != day_id:
        raise RuntimeError(f"panel {panel_id} does not belong to day {day_id}")
    print("Mem GET_PANEL:", panel_id)
    mobile_stacks.set_register(("panel", deepcopy(panels[panel_id])))


def handle_when_mem_receives_create_panel():
    day_id = mobile_stacks.get_register("day-id")
    panel_type = mobile_stacks.get_register("panel-type")
    if panel_type not in {"WHITEBOARD", "TODO", "JOURNAL"}:
        raise RuntimeError(f"cannot create panel type {panel_type}")
    panel_id = f"{panel_type.lower()}-{uuid4().hex}"
    panel = {
        "id": panel_id,
        "day-id": day_id,
        "type": panel_type,
        "label": {"WHITEBOARD": "Whiteboard", "TODO": "To-Do", "JOURNAL": "Journal"}[panel_type],
        "text": "",
        "revision": 1,
    }
    if panel_type == "WHITEBOARD":
        panel["history"] = []
    panels[panel_id] = panel
    mark_day_for_disk_save(day_id)
    print("Mem CREATE_PANEL:", panel_id, "for", day_id)
    mobile_stacks.set_register(("panel", deepcopy(panel)))


def handle_when_mem_receives_select_tab():
    day_id = mobile_stacks.get_register("day-id")
    tab_id = mobile_stacks.get_register("tab-id")
    if tab_id not in days[day_id]["tab-ids"]:
        raise RuntimeError(f"tab {tab_id} is not in day {day_id}")
    days[day_id]["selected-tab-id"] = tab_id
    mark_day_for_disk_save(day_id)
    print("Mem SELECT_TAB:", day_id, tab_id)
    mobile_stacks.set_register(("day-id", day_id))
    mobile_stacks.set_register(("tab-id", tab_id))


def handle_when_mem_receives_set_row_height():
    row_id = mobile_stacks.get_register("row-id")
    rows[row_id]["height"] = mobile_stacks.get_register("height")
    mark_day_for_disk_save(get_day_id_for_position(get_position_id(row_id, 1)))
    print("Mem SET_ROW_HEIGHT:", row_id, rows[row_id]["height"])
    mobile_stacks.set_register(("row", deepcopy(rows[row_id])))
    mobile_stacks.set_register(("layout-change", "ROW_HEIGHT"))


def handle_when_mem_receives_set_sash_proportions():
    row_id = mobile_stacks.get_register("row-id")
    rows[row_id]["sash-proportions"] = mobile_stacks.get_register("sash-proportions")
    mark_day_for_disk_save(get_day_id_for_position(get_position_id(row_id, 1)))
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
    mark_day_for_disk_save(get_day_id_for_position(get_position_id(row_id, 1)))
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
    mark_day_for_disk_save(tabs[tab_id]["day-id"])
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
        mark_day_for_disk_save(tabs[tab_id]["day-id"])
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
    mark_day_for_disk_save(tabs[tab_id]["day-id"])
    print("Mem ADD_ROW:", tab_id, row_id)
    mobile_stacks.set_register(("tab", deepcopy(tabs[tab_id])))
    mobile_stacks.set_register(("row", deepcopy(rows[row_id])))
    mobile_stacks.set_register(("layout-change", "TAB_ROWS"))


def handle_when_mem_receives_set_tab_scroll_position():
    tab_id = mobile_stacks.get_register("tab-id")
    scroll_position = mobile_stacks.get_register("scroll-position")
    tabs[tab_id]["scroll-position"] = max(0.0, min(1.0, scroll_position))
    mark_day_for_disk_save(tabs[tab_id]["day-id"])
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
    mark_day_for_disk_save(day_id)
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
    mark_day_for_disk_save(tabs[tab_id]["day-id"])
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
        mark_day_for_disk_save(day_id)
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
    mark_day_for_disk_save(day_id)
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
    mark_day_for_disk_save(day_id)
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
    mark_day_for_disk_save(day_id)
    print("Mem UNHOST_PANEL:", position_id, "unhosts", panel_id)
    mobile_stacks.set_register(("position-id", position_id))
    mobile_stacks.set_register(("panel-id", None))
    mobile_stacks.set_register(("unhosted-position-id", None))


def handle_when_mem_receives_delete_panel():
    day_id = mobile_stacks.get_register("day-id")
    panel_id = mobile_stacks.get_register("panel-id")
    if panels[panel_id]["day-id"] != day_id:
        raise RuntimeError(f"panel {panel_id} does not belong to day {day_id}")
    if days[day_id]["orientation-position"]["panel-id"] == panel_id:
        raise RuntimeError("cannot delete the fixed Orientation panel")
    position_ids = []
    for tab_id in days[day_id]["tab-ids"]:
        for row_id in tabs[tab_id]["row-ids"]:
            for column in range(1, rows[row_id]["column-count"] + 1):
                position_id = get_position_id(row_id, column)
                if positions[position_id]["panel-id"] == panel_id:
                    position_ids.append(position_id)
    for position_id in position_ids:
        positions[position_id]["panel-id"] = None
    panels.pop(panel_id)
    mark_day_for_disk_save(day_id)
    print("Mem DELETE_PANEL:", panel_id, "from", len(position_ids), "positions")
    mobile_stacks.set_register(("panel-id", panel_id))
    mobile_stacks.set_register(("position-ids", position_ids))


def flush_day_writes_when_due(force=False):
    now = monotonic()
    day_ids = [
        day_id
        for day_id, deadline in g["pending-day-writes"].items()
        if force or deadline <= now
    ]
    for day_id in day_ids:
        g["pending-day-writes"].pop(day_id)
        mobile_stacks.create_stack()
        mobile_stacks.set_register(("day-bundle", make_day_bundle(day_id)))
        mobile_stacks.push_frame({"machine": "DISK", "entry": "WRITE_DAY"})
        machine.route_current_stack()


def get_seconds_until_next_day_write():
    if not g["pending-day-writes"]:
        return None
    return max(0.0, min(g["pending-day-writes"].values()) - monotonic())


def run_mem_machine():
    machine.claim_machine("MEM")
    initialize_mem_store()
    runtime = machine.get_current_runtime()
    runtime["running"] = True

    while runtime["running"]:
        try:
            item = runtime["inbox"].get(timeout=get_seconds_until_next_day_write())
        except Empty:
            flush_day_writes_when_due()
            continue

        if item is None:
            flush_day_writes_when_due(force=True)
            runtime["running"] = False
            return

        machine.handle_received_mobile_stack(item)
        flush_day_writes_when_due()
