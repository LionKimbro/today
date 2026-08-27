"""The disk machine: the only owner of filesystem I/O."""

from __future__ import annotations

import time
from pathlib import Path

from messages import append_record


READ_FILE = "READ_FILE"
WRITE_FILE = "WRITE_FILE"
SHUTDOWN = "SHUTDOWN"


def run_disk_machine(queues, data_root, delay_seconds):
    """Run concrete disk operations until the memory machine shuts us down."""
    while True:
        transaction = queues["disk"].get()
        request = transaction[-1]
        operation = request["operation"]

        if operation == SHUTDOWN:
            append_record(
                transaction,
                {
                    "destination": request["response_destination"],
                    "operation": "SHUTDOWN_RESULT",
                    "response_operation": None,
                    "response_to": len(transaction) - 1,
                    "payload": {"stopped": True},
                },
            )
            queues[request["response_destination"]].put(transaction)
            return

        time.sleep(delay_seconds)
        if operation == READ_FILE:
            result = _read_file(request["payload"]["path"])
            result_operation = "READ_FILE_RESULT"
        elif operation == WRITE_FILE:
            result = _write_file(request["payload"])
            result_operation = "WRITE_FILE_RESULT"
        else:
            result = {"error": f"unknown disk operation: {operation}"}
            result_operation = "DISK_ERROR"

        response_payload = result.copy()
        pending_writes = request["payload"].get("pending_writes") if request.get("payload") else None
        if pending_writes is not None:
            response_payload["pending_writes"] = pending_writes

        append_record(
            transaction,
            {
                "destination": request["response_destination"],
                "operation": request["response_operation"],
                "response_operation": result_operation,
                "response_to": len(transaction) - 1,
                "payload": response_payload,
                "continuation": request.get("continuation"),
            },
        )
        queues[request["response_destination"]].put(transaction)


def _read_file(path):
    file_path = Path(path)
    try:
        return {"found": True, "data": file_path.read_text(encoding="utf-8")}
    except FileNotFoundError:
        return {"found": False, "data": None}
    except OSError as error:
        return {"found": False, "data": None, "error": str(error)}


def _write_file(payload):
    file_path = Path(payload["path"])
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(payload["data"], encoding="utf-8")
        return {"written": True, "path": str(file_path)}
    except OSError as error:
        return {"written": False, "path": str(file_path), "error": str(error)}
