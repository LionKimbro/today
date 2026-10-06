# `main.py`

OWNS: startup wiring, four queues, Core/Mem/Disk threads, Tk main thread,
shutdown joins.

Startup initializes Disk's root from MachineRoot before opening the window or
starting workers. `main(data_root=...)` overrides the exact root for tests.

Required workers use machine's fatal exception boundary. Normal shutdown
joins Core and Mem before stopping Disk. Fatal shutdown wakes all workers
immediately; after Tk closes and workers join, main exits with status 1.

`worker_threads` holds the three process worker handles. Both the application
and worker tests call `finish_worker_shutdown`: join Core, join dynamic workers,
join Mem, send Disk its sentinel, join Disk. Test fallback cleanup runs only
after failure. Tests start workers through the same tracked startup function.

Startup resets the runtime system, installs kinds, and starts tracked workers.
Final shutdown begins by closing dynamic creation and waking dynamic machines,
joins Core and all dynamic workers, joins Mem, then stops/joins Disk. Main reaps
all exited workers after joining. Tk's main-thread polling also reaps completed
dynamic machines while the window remains open.

WIRES:

- Tk → Core semantic-event queue
- Core → Tk command inbox and wakeup
- Core ↔ Mem Mobile Stack inboxes
- Core → Disk → Mem day-load stacks
- Mem → Disk one-way day-write stacks

DOES NOT OWN: application meaning, Tk operations, or machine behavior.
