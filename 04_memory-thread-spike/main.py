"""Executable Tkinter front end for the three-thread messaging spike."""

from __future__ import annotations

import queue
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from memory_thread import GET_NOTE, SAVE_ALL, SAVE_DATE, SAVE_NOTE, SET_NOTE, SHUTDOWN, run_memory_machine
from messages import create_transaction, summarize_transaction
from disk_thread import run_disk_machine


DISK_DELAY_SECONDS = 1.2
DATA_ROOT = Path(__file__).parent / "data"


def main():
    """Initialize the machines and run the Tk event loop."""
    memory_queue = queue.Queue()
    disk_queue = queue.Queue()
    gui_queue = queue.Queue()
    queues = {"memory": memory_queue, "disk": disk_queue, "tkinter": gui_queue}
    disk_thread = threading.Thread(target=run_disk_machine, args=(queues, DATA_ROOT, DISK_DELAY_SECONDS), daemon=True)
    memory_thread = threading.Thread(target=run_memory_machine, args=(queues, DATA_ROOT), daemon=True)
    disk_thread.start()
    memory_thread.start()

    root = tk.Tk()
    build_window(root, queues)
    root.protocol("WM_DELETE_WINDOW", lambda: handle_when_user_closes_spike(root, queues))
    poll_responses(root, gui_queue)
    root.mainloop()


def build_window(root, queues):
    """Build the small semantic request console."""
    root.title("Today — Threads and Memory Spike")
    root.geometry("850x620")
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Date").grid(row=0, column=0, sticky="w")
    date_entry = ttk.Entry(frame, width=20)
    date_entry.insert(0, "2026-08-26")
    date_entry.grid(row=0, column=1, sticky="ew", padx=6)
    ttk.Label(frame, text="Note ID").grid(row=1, column=0, sticky="w")
    note_entry = ttk.Entry(frame, width=20)
    note_entry.insert(0, "orientation")
    note_entry.grid(row=1, column=1, sticky="ew", padx=6)
    ttk.Label(frame, text="Note").grid(row=2, column=0, sticky="nw")
    note_text = tk.Text(frame, height=8, width=70)
    note_text.grid(row=2, column=1, columnspan=4, sticky="nsew", padx=6, pady=6)
    button_specs = [("Get Note", GET_NOTE), ("Set Note", SET_NOTE), ("Save Note", SAVE_NOTE), ("Save Date", SAVE_DATE), ("Save All", SAVE_ALL)]
    for column, (label, operation) in enumerate(button_specs):
        ttk.Button(frame, text=label, command=lambda op=operation: handle_when_user_clicks_semantic_button(op, date_entry, note_entry, note_text, queues)).grid(row=3, column=column, sticky="ew", padx=2)
    status = tk.StringVar(value="Ready. Disk delay: 1.2 seconds.")
    ttk.Label(frame, textvariable=status).grid(row=4, column=0, columnspan=5, sticky="w", pady=(10, 4))
    trace = tk.Text(frame, height=16, width=100, state="disabled")
    trace.grid(row=5, column=0, columnspan=5, sticky="nsew")
    frame.columnconfigure(1, weight=1)
    frame.rowconfigure(2, weight=1)
    frame.rowconfigure(5, weight=2)
    root.spike_widgets = {"date": date_entry, "note_id": note_entry, "note": note_text, "status": status, "trace": trace}


def handle_when_user_clicks_semantic_button(operation, date_entry, note_entry, note_text, queues):
    """Translate one GUI action into a semantic memory request."""
    payload = {"date": date_entry.get().strip(), "note_id": note_entry.get().strip()}
    if operation in {SET_NOTE}:
        payload["value"] = note_text.get("1.0", "end-1c")
    record = {"destination": "memory", "operation": operation, "payload": payload, "response_destination": "tkinter", "response_operation": f"{operation}_RESULT"}
    queues["memory"].put(create_transaction(record))
    root = date_entry.winfo_toplevel()
    root.spike_widgets["status"].set(f"Queued {operation}; Tk remains responsive while machines work.")


def poll_responses(root, gui_queue):
    """Receive completed transactions without blocking the Tk event loop."""
    try:
        while True:
            transaction = gui_queue.get_nowait()
            show_response(root, transaction)
    except queue.Empty:
        pass
    root.after(50, lambda: poll_responses(root, gui_queue))


def show_response(root, transaction):
    """Display semantic result and its complete travelling trace."""
    record = transaction[-1]
    payload = record.get("payload", {})
    widgets = root.spike_widgets
    if "value" in payload:
        widgets["note"].delete("1.0", "end")
        widgets["note"].insert("1.0", payload["value"])
    widgets["status"].set(f"{record['operation']}: {payload}")
    widgets["trace"].configure(state="normal")
    widgets["trace"].insert("end", summarize_transaction(transaction) + "\n\n")
    widgets["trace"].see("end")
    widgets["trace"].configure(state="disabled")


def handle_when_user_closes_spike(root, queues):
    """Ask the memory machine to stop before closing the demonstration window."""
    queues["memory"].put(create_transaction({"destination": "memory", "operation": SHUTDOWN}))
    root.destroy()


if __name__ == "__main__":
    main()
