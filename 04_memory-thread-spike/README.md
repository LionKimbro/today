# Threads and Memory Spike

Run the standalone Tk demonstration from the repository root:

```text
python 04_memory-thread-spike/main.py
```

The GUI is the Tkinter machine. It places semantic requests on the memory
queue and polls its queue with `after()`, so it never waits for disk.
The memory machine owns `notes_by_date` and delegates concrete reads and
writes to the disk machine. Persistence is stored in the local `data/`
directory as `<date>/<note_id>.txt`.

Each travelling transaction is just its append-only history list. Records use
integer history indexes for both `response_to` and `continuation`; delivery
uses the string destinations `memory`, `disk`, and `tkinter` to select queues.

The disk machine waits 1.2 seconds per operation by default. This makes the
asynchronous behavior visible; change `DISK_DELAY_SECONDS` in `main.py` for a
different demonstration speed.
