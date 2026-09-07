# `main.py`

OWNS: startup wiring, three queues, Core and Mem threads, Tk main thread,
shutdown joins.

WIRES:

- Tk → Core semantic-event queue
- Core → Tk command inbox and wakeup
- Core ↔ Mem Mobile Stack inboxes

DOES NOT OWN: application meaning, Tk operations, or machine behavior.
