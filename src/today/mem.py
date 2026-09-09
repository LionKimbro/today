"""The Mem machine: the small canonical in-memory store."""

from copy import deepcopy
from datetime import date

from . import machine, mobile_stacks

days = {}
panels = {}


def initialize_mem_store():
    today_id = date.today().isoformat()
    days[today_id] = {"id": today_id}
    panels["whiteboard-a"] = {
        "id": "whiteboard-a",
        "type": "WHITEBOARD",
        "label": "Whiteboard A",
        "text": "",
        "revision": 1,
    }
    panels["whiteboard-b"] = {
        "id": "whiteboard-b",
        "type": "WHITEBOARD",
        "label": "Whiteboard B",
        "text": "",
        "revision": 1,
    }


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


def run_mem_machine():
    machine.claim_machine("MEM")
    initialize_mem_store()
    machine.run_machine()
