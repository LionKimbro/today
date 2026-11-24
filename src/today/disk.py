"""The Disk machine: durable day-bundle files."""

import json
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

import machineroot

from . import machine, mobile_stacks


g = {"data-root": None}  # Installed at startup; unchanged while workers run.


def initialize_data_root(data_root=None):
    """Use the machine's Today directory, or an exact caller-selected test root."""
    if data_root is None:
        data_root = Path(machineroot.get("db-root-2026")) / "today"
    g["data-root"] = Path(data_root)


def get_day_paths(day_id):
    if g["data-root"] is None:
        raise RuntimeError("Today data root has not been initialized")
    day = date.fromisoformat(day_id)
    directory = g["data-root"] / f"{day:%Y}" / f"{day:%Y-%m}" / day_id
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


def get_image_asset_path(day_id, asset):
    """Only generated day-relative image names are valid stored references."""
    if not isinstance(asset, str) or not re.fullmatch(
            r"assets/image-[0-9a-f]{32}\.(jpg|png|gif)", asset):
        raise ValueError("Invalid image asset reference")
    directory, _ = get_day_paths(day_id)
    return directory / asset


def handle_when_disk_receives_write_image_asset():
    extension = mobile_stacks.get_register("image-extension")
    if extension not in (".jpg", ".png", ".gif"):
        raise ValueError("Image machine supplied an invalid storage extension")
    asset = f"assets/image-{uuid4().hex}{extension}"
    path = get_image_asset_path(mobile_stacks.get_register("day-id"), asset)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    mobile_stacks.set_register(("image-error", None))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_bytes(mobile_stacks.get_register("image-bytes"))
        if machine.a_thread_died_unexpectedly.is_set():
            temporary_path.unlink(missing_ok=True)
            return
        temporary_path.replace(path)
    except OSError as error:
        mobile_stacks.set_register(("image-error", str(error)))
        return
    mobile_stacks.set_register(("image-asset", asset))


def handle_when_disk_receives_read_image_asset():
    mobile_stacks.set_register(("image-error", None))
    try:
        path = get_image_asset_path(
            mobile_stacks.get_register("day-id"),
            mobile_stacks.get_register("image-asset"),
        )
        data = path.read_bytes()
    except (OSError, ValueError) as error:
        mobile_stacks.set_register(("image-error", str(error)))
        return
    if not machine.a_thread_died_unexpectedly.is_set():
        mobile_stacks.set_register(("image-bytes", data))


def run_disk_machine():
    machine.claim_machine("DISK")
    machine.run_machine()


def handle_when_disk_receives_list_attachments():
    directory, _ = get_day_paths(mobile_stacks.get_register("day-id"))
    folder = directory / "files"
    try:
        try:
            entries = list(folder.iterdir())
        except FileNotFoundError:
            entries = []
        records = []
        for entry in entries:
            metadata = entry.stat()
            is_directory = entry.is_dir()
            records.append({"name": entry.name, "type": "Folder" if is_directory else "File",
                            "size": None if is_directory else metadata.st_size})
        records.sort(key=lambda item: (item["name"].casefold(), item["name"]))
        result = {"entries": records, "error": None}
    except OSError as error:
        result = {"error": str(error)}
    mobile_stacks.set_register(("result", result))


def handle_when_disk_receives_open_attachments():
    directory, _ = get_day_paths(mobile_stacks.get_register("day-id"))
    folder = directory / "files"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        result = {"path": str(folder.resolve()), "error": None}
    except OSError as error:
        result = {"error": str(error)}
    mobile_stacks.set_register(("result", result))
