# `main.py`

OWNS: startup wiring, four queues, Core/Mem/Disk threads, Tk main thread,
shutdown joins.

Required workers use machine's fatal exception boundary. Normal shutdown
joins Core and Mem before stopping Disk. Fatal shutdown wakes all workers
immediately; after Tk closes and workers join, main exits with status 1.

`worker_threads` holds the three process worker handles. Both the application
and worker tests call `finish_worker_shutdown`: join Core, join Mem, send Disk
its sentinel, join Disk. Test fallback cleanup runs only after failure.

WIRES:

- Tk → Core semantic-event queue
- Core → Tk command inbox and wakeup
- Core ↔ Mem Mobile Stack inboxes
- Core → Disk → Mem day-load stacks
- Mem → Disk one-way day-write stacks

DOES NOT OWN: application meaning, Tk operations, or machine behavior.
