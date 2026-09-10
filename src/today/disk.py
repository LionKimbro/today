"""The Disk machine: durable day-bundle files."""

import json
from datetime import date
from pathlib import Path

from . import machine, mobile_stacks


DATA_ROOT = Path(r"C:\lion\installed\lions-today-db")


def get_day_paths(day_id):
    day = date.fromisoformat(day_id)
    directory = DATA_ROOT / f"{day:%Y}" / f"{day:%Y-%m}" / day_id
    return directory, directory / f"{day_id}.json"


def handle_when_disk_receives_load_day():
    day_id = mobile_stacks.get_register("day-id")
    _, path = get_day_paths(day_id)
    bundle = None
    if path.exists():
        with path.open(encoding="utf-8") as source:
            bundle = json.load(source)
        print("Disk LOAD_DAY:", path)
    else:
        print("Disk LOAD_DAY: no record for", day_id)
    mobile_stacks.set_register(("day-bundle", bundle))


def handle_when_disk_receives_write_day():
    bundle = mobile_stacks.get_register("day-bundle")
    day_id = bundle["day"]["id"]
    directory, path = get_day_paths(day_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "assets").mkdir(exist_ok=True)
    (directory / "files").mkdir(exist_ok=True)
    temporary_path = path.with_suffix(".json.tmp")
    with temporary_path.open("w", encoding="utf-8") as destination:
        json.dump(bundle, destination, indent=2, sort_keys=True)
        destination.write("\n")
    temporary_path.replace(path)
    print("Disk WRITE_DAY:", path)


def run_disk_machine():
    machine.claim_machine("DISK")
    machine.run_machine()
