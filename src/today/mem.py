"""The Mem machine: the small canonical in-memory store."""

from copy import deepcopy
from datetime import date

from . import machine, mobile_stacks

days = {}
panels = {}


def initialize_mem_store():
    today_id = date.today().isoformat()
    days[today_id] = {"id": today_id}
    panels["panel-1"] = {"id": "panel-1", "label": "panel-1"}


def handle_when_mem_receives_get_panel():
    panel_id = mobile_stacks.get_register("panel-id")
    print("Mem GET_PANEL:", panel_id)
    mobile_stacks.set_register(("panel", deepcopy(panels[panel_id])))


def run_mem_machine():
    machine.claim_machine("MEM")
    initialize_mem_store()
    machine.run_machine()
