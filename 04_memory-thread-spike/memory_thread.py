"""The memory machine: semantic access and sole owner of authoritative RAM."""

from __future__ import annotations

import re
from pathlib import Path

from messages import append_record


GET_NOTE = "GET_NOTE"
SET_NOTE = "SET_NOTE"
SAVE_NOTE = "SAVE_NOTE"
SAVE_DATE = "SAVE_DATE"
SAVE_ALL = "SAVE_ALL"
READ_FILE = "READ_FILE"
WRITE_FILE = "WRITE_FILE"
SHUTDOWN = "SHUTDOWN"


def run_memory_machine(queues, data_root):
    """Run semantic operations while owning all authoritative note data."""
    notes_by_date = {}
    dirty_notes = set()

    while True:
        transaction = queues["memory"].get()
        request = transaction[-1]
        operation = request["operation"]

        if operation == SHUTDOWN:
            append_record(
                transaction,
                {
                    "destination": "disk",
                    "operation": SHUTDOWN,
                    "response_destination": "memory",
                    "response_operation": "SHUTDOWN_RESULT",
                },
            )
            queues["disk"].put(transaction)
            return
        if operation == GET_NOTE:
            _handle_get_note(transaction, request, notes_by_date, queues, data_root)
        elif operation == SET_NOTE:
            _handle_set_note(transaction, request, notes_by_date, dirty_notes, queues)
        elif operation in {SAVE_NOTE, SAVE_DATE, SAVE_ALL}:
            _handle_save(transaction, request, notes_by_date, dirty_notes, queues, data_root)
        elif operation in {"READ_FILE_RESULT", "WRITE_FILE_RESULT"}:
            _handle_disk_result(transaction, request, notes_by_date, dirty_notes, queues, data_root)
        elif operation == "SHUTDOWN_RESULT":
            return
        else:
            _respond(transaction, request, {"error": f"unknown memory operation: {operation}"}, queues)


def _handle_get_note(transaction, request, notes_by_date, queues, data_root):
    payload = request["payload"]
    date = payload["date"]
    note_id = payload["note_id"]
    if _has_note(notes_by_date, date, note_id):
        _respond(transaction, request, {"date": date, "note_id": note_id, "value": _note_value(notes_by_date, date, note_id), "source": "RAM"}, queues)
        return

    path = _note_path(data_root, date, note_id)
    append_record(
        transaction,
        {
            "destination": "disk",
            "operation": READ_FILE,
            "payload": {"path": str(path)},
            "response_destination": "memory",
            "response_operation": "READ_FILE_RESULT",
            "continuation": len(transaction) - 1,
        },
    )
    queues["disk"].put(transaction)


def _handle_set_note(transaction, request, notes_by_date, dirty_notes, queues):
    payload = request["payload"]
    date = payload["date"]
    note_id = payload["note_id"]
    _store_note(notes_by_date, date, note_id, payload["value"])
    dirty_notes.add((date, note_id))
    _respond(transaction, request, {"date": date, "note_id": note_id, "value": payload["value"], "dirty": True}, queues)


def _handle_save(transaction, request, notes_by_date, dirty_notes, queues, data_root):
    payload = request["payload"]
    operation = request["operation"]
    if operation == SAVE_NOTE:
        keys = [(payload["date"], payload["note_id"])]
    elif operation == SAVE_DATE:
        keys = [(payload["date"], note_id) for note_id in notes_by_date.get(payload["date"], {})]
    else:
        keys = [(date, note_id) for date, notes in notes_by_date.items() for note_id in notes]

    writes = [{"date": date, "note_id": note_id, "value": _note_value(notes_by_date, date, note_id)} for date, note_id in keys if _has_note(notes_by_date, date, note_id)]
    if not writes:
        _respond(transaction, request, {"saved": [], "message": "No known notes required persistence."}, queues)
        return
    _delegate_next_write(transaction, request, len(transaction) - 1, writes, queues, data_root)


def _handle_disk_result(transaction, request, notes_by_date, dirty_notes, queues, data_root):
    if request["operation"] == "READ_FILE_RESULT":
        original = transaction[request["continuation"]]
        payload = original["payload"]
        result = request["payload"]
        value = result["data"] if result.get("found") else ""
        _store_note(notes_by_date, payload["date"], payload["note_id"], value)
        _respond(transaction, original, {"date": payload["date"], "note_id": payload["note_id"], "value": value, "source": "disk" if result.get("found") else "default"}, queues)
        return

    original = transaction[request["continuation"]]
    original_index = request["continuation"]
    writes = list(request["payload"].get("pending_writes", []))
    if request["payload"].get("written"):
        completed = writes.pop(0) if writes else None
        if completed:
            dirty_notes.discard((completed["date"], completed["note_id"]))
    if writes:
        _delegate_next_write(transaction, original, original_index, writes, queues, data_root)
    else:
        _respond(transaction, original, {"saved": True, "operation": original["operation"]}, queues)


def _delegate_next_write(transaction, original, original_index, writes, queues, data_root):
    current = writes[0]
    append_record(
        transaction,
        {
            "destination": "disk",
            "operation": WRITE_FILE,
            "payload": {
                "path": str(_note_path(data_root, current["date"], current["note_id"])),
                "data": current["value"],
                "pending_writes": writes,
            },
            "response_destination": "memory",
            "response_operation": "WRITE_FILE_RESULT",
            "continuation": original_index,
        },
    )
    queues["disk"].put(transaction)


def _respond(transaction, request, payload, queues):
    request_index = transaction.index(request)
    append_record(
        transaction,
        {"destination": request["response_destination"], "operation": request.get("response_operation", f"{request['operation']}_RESULT"), "response_to": request_index, "payload": payload},
    )
    queues[request["response_destination"]].put(transaction)


def _has_note(notes_by_date, date, note_id):
    return note_id in notes_by_date.get(date, {})


def _store_note(notes_by_date, date, note_id, value):
    notes_by_date.setdefault(date, {})[note_id] = {"value": value}


def _note_value(notes_by_date, date, note_id):
    return notes_by_date[date][note_id]["value"]


def _note_path(data_root, date, note_id):
    safe_date = _safe_component(date)
    safe_note_id = _safe_component(note_id)
    return Path(data_root) / safe_date / f"{safe_note_id}.txt"


def _safe_component(value):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)
