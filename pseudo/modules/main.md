# `main.py`

OWNS: startup wiring, four queues, Core/Mem/Disk threads, Tk main thread,
shutdown joins.

WIRES:

- Tk → Core semantic-event queue
- Core → Tk command inbox and wakeup
- Core ↔ Mem Mobile Stack inboxes
- Core → Disk → Mem day-load stacks
- Mem → Disk one-way day-write stacks

DOES NOT OWN: application meaning, Tk operations, or machine behavior.
