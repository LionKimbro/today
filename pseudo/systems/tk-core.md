# Tk / Core seam

**Tk main thread** — wakes on `<<CoreMailAvailable>>`, then drains its inbox.

- → Core: relevant semantic event data
- ← Core: declarative semantic commands

**Core thread** — blocks on `Queue.get()` for events. It queues a command before
signaling Tk mail.

- ← Tk: relevant semantic event data
- → Tk: declarative semantic commands

Reconcile structure when structure changes; otherwise update the named entity.

No Tk objects cross the seam.

Tk checks the shared fatal worker event every 50 ms on its own thread and
destroys the window when set, even if Core has died. Fatal shutdown discards
ordinary Core commands and bypasses the normal debounce/save path.
