# Exporting Tk-Core-Mem-Disk with Machine Stack for Python + Tkinter Applications

This is a reusable architecture for a Python/Tkinter application whose
UI, application meaning, canonical memory, and persistence are kept
separate.  It is programmed according to a "machine" model architecture,
rather than as an object hierarchy.

The reusable shape is:

```text
Tk main thread  -- semantic events -->  Reducer Core worker
Tk main thread  <-- declarative commands --/

Reducer Core  <---- Mobile Stacks ---->  Mem worker  <----> Disk worker
```

"Today" (an application) supplies one concrete application of this
shape.  Its days, tabs, panels, Whiteboards, layouts, history, and
date-folder JSON format are *not* part of this export.  Replace those
with the records and commands of the new application; retain the
ownership and machine boundaries.

## Ownership

| Machine | Owns | Does not own |
| --- | --- | --- |
| **Tk** | The root window, widgets, bindings, timers, local presentation state, translating gestures to semantic events, and realizing commands. | Application decisions, canonical records, persistence. |
| **Core** | Active application meaning: the reducer state needed to interpret events, active/derived view snapshots, pending work, and effects. | Widgets, canonical store records, file I/O. |
| **Mem** | Canonical mutable in-memory records and their invariants. It mints ids, accepts or rejects mutations, and returns copied results. | Tk widgets and application presentation policy. |
| **Disk** | Durable reads and writes of portable record bundles. | Live application meaning and canonical in-memory state. |
| **main** | Construction and wiring only: queues, machine runtimes, threads, startup order, and joining. | Feature behavior, reducer cases, widget operations, record rules. |

Core may retain a bounded working copy of the records currently meaningful to
the UI.  That copy is for reduction and rendering; Mem remains the canonical
authority.  Disk receives and returns serializable bundles, not live record
objects it owns.

## Threads, inboxes, and the runtime record

Tk starts on the process main thread and remains there for its entire life.
Every legal Tk call--including widget inspection, `after`, and event
generation--belongs on that thread.  Core, Mem, and Disk each have one worker
thread and one blocking inbox.  The normal worker rhythm is deliberately
boring:

```text
claim this machine's runtime on this thread
while running:
    item = inbox.get()             # block; do not poll a shared world
    sentinel -> stop
    Mobile Stack -> handle one frame, then route its continuation
```

Core additionally accepts plain Tk semantic-event records in its inbox.  It
turns an inbound item into reducer event(s), reduces until its local event and
effect queues are quiet, and then blocks again.  Mem may add a timed wakeup
for coalesced saving, but it is still a single owner thread for its store.

Each installed runtime is a small visible record:

```python
{
    "name": "MEM",
    "inbox": mem_inbox,
    "current-stack": None,
    "handlers": {"UPDATE_RECORD": handle_when_mem_receives_update_record},
    "running": False,
}
```

The process may have a stable machine registry, keyed by name, so routing can
find destination inboxes.  It must **not** have a mutable process-global
`current_runtime`.  Before its loop, each worker claims its own installed
runtime into thread-local state.  Machine and Mobile Stack primitives then
look up the runtime claimed by *this thread*.  This makes calls such as
`mobile_stacks.get_register("record-id")` concise without letting Core's
active stack leak into Mem or Disk.

There is exactly one `current-stack` slot per runtime.  Receiving a second
stack while that slot is occupied is an error.  A machine clears its local
slot before publishing the stack into another machine's queue.  This is both a
useful invariant and the reason handlers do not accept `runtime` or `stack`
as habitual arguments: those are current machine context, not caller choices.

Use ordinary globals in the same disciplined way as the style cards: a fixed
`g` bundle for named machine facts, separate open collections for records or
widgets, and registers only for genuine current procedural context.  Mutate
those containers in place.  Keep import time passive and start everything
from an explicit entrypoint.

## Mobile Stacks: an asynchronous call/return path

A Mobile Stack is an explicit work packet that crosses worker inboxes:

```python
{
    "kind": "MOBILE_STACK",
    "frames": [
        {"machine": "CORE", "entry": "RECORD_UPDATED_RETURNED"},
        {"machine": "MEM", "entry": "UPDATE_RECORD"},
    ],
    "registers": {
        "record-id": "r-17",
        "proposed-label": "Inbox",
    },
}
```

`frames` are continuation control, and `registers` are traveling named
context.  The last frame is the top.  Therefore create a return frame first
and the immediate destination frame last.  A receiving machine:

1. verifies that the top frame names itself;
2. places the stack in its one active-stack slot;
3. runs the handler named by `entry`, reading and adding registers as needed;
4. drops the handled top frame;
5. routes the remaining stack to the machine named by the newly exposed top
   frame, or clears the active-stack slot when no frames remain.

Handlers do not themselves drop frames or manually choose the next hop.  The
small generic machine runtime does that after every handler.  A handler may
copy a returned register record into a Core reducer event because the stack
may be routed or completed before Core reduces that event.

Registers carry operation-specific data--ids, requested values, a copied
bundle, an accepted record, or a result flag.  They are not a replacement for
Mem's record tables and are not a shared cross-thread register bank.  The
stack is the explicit cross-thread packet; its registers travel with it.

For a simple request, the stack is `Core -> Mem -> Core`.  A load can be
`Core -> Disk -> Mem -> Core`: Disk places a durable bundle in a register,
Mem installs or seeds canonical records and places an active layout/result in
another register, and Core receives the result.  A background Mem save can be
a one-way `Mem -> Disk` stack with only a `WRITE_BUNDLE` frame.

## Reducer meaning is separate from machine mechanics

The reducer answers application questions:

```text
given current Core state and a semantic event,
what is the next Core state and which effects should occur?
```

It knows application event names such as `RENAME_RECORD`, whether a mutation
is meaningful, and which declarative Tk update follows acceptance.  Its
output is data: effects such as `UPDATE_RECORD`, `LOAD_WORKSPACE`, or
`SET_RECORD_LABEL`.

The machine layer answers transport questions: claim a runtime, block on an
inbox, install the current stack, dispatch its top frame, drop it, and route
the continuation.  Stack construction is effect dispatch work outside the
reducer.  Stack arrival handlers translate returned registers into ordinary
reducer events.  This separation keeps reducer tests synchronous and small:
they need no queues, threads, Tk, or continuation frames.

## Tk/Core protocol

Tk sends plain semantic events.  They describe what the user requested or
what Tk measured; they do not carry a widget, callback, or UI implementation
decision.

```python
{"type": "RENAME_RECORD", "record-id": "r-17", "label": "Inbox"}
{"type": "SET_SPLIT_FRACTION", "fraction": 0.35}
{"type": "SHUTDOWN"}
```

Core sends declarative semantic commands.  They describe the presentation
result that Tk must realize; they do not ask Tk to make a domain decision.

```python
{"type": "SET_RECORD_LABEL", "record-id": "r-17", "label": "Inbox"}
{"type": "RENDER_WORKSPACE", "workspace": rendering}
{"type": "SHUTDOWN_COMPLETE"}
```

Core puts commands into a thread-safe Tk command queue.  Tk owns the drain
schedule--for example, a short `after` poll established by Tk during startup--
and its event handler realizes each command on the Tk thread.  A worker must
not call `event_generate`, `after`, or any other Tk API as a wakeup shortcut.
No worker reads, writes, or even consults a widget.  Conversely, Tk does not
optimistically alter the canonical model: it sends an event and renders the
command returned after Core has decided what is true.

## Complete small round trip

This generic rename flow is the whole pattern in miniature:

```text
Tk callback
  -> {RENAME_RECORD, record-id, label} into Core inbox
Core reducer
  -> next active state + {UPDATE_RECORD, record-id, label} effect
Core effect dispatcher
  -> stack registers: record-id, label
  -> frames: [CORE/RECORD_UPDATED_RETURNED, MEM/UPDATE_RECORD]
  -> route to Mem inbox
Mem UPDATE_RECORD handler
  -> validate and mutate canonical records[record-id]
  -> put a copied accepted record in stack registers
  -> runtime drops MEM frame and routes stack to Core
Core return handler
  -> copy accepted record into {RECORD_UPDATED, record} reducer event
  -> runtime drops CORE frame; stack completes
Core reducer
  -> update active snapshot + {SET_RECORD_LABEL, record-id, label} effect
Core effect dispatcher
  -> declarative command in Tk inbox; wake Tk
Tk command handler
  -> locate its widget locally and set its visible label
```

The reducer never pushes or drops frames.  Mem never calls Tk.  Tk never
changes Mem records.  If Mem rejects the mutation, return a result/status (or
the authoritative record) through the same continuation and let Core reduce a
semantic rejection event into the appropriate command.

## Startup and shutdown

Startup should be plain wiring, in this order:

1. Create the Core, Mem, Disk, and Core-to-Tk queues.
2. Create and install their runtime records and handler maps.
3. Wire the Tk-to-Core event queue and Core-to-Tk command queue; establish
   Tk's own command-drain schedule on the Tk thread.
4. Build the Tk window on the main thread.
5. Start Disk, Mem, and Core worker threads; each claims its own runtime.
6. Enter Tk's main loop.  Core's initial reducer event normally emits the
   first load effect.

For shutdown, Tk first flushes any Tk-local deferred semantic event and sends
one `SHUTDOWN` event to Core.  Core reduces it: stop accepting new Core work,
request Mem's clean stop/flush, and send `SHUTDOWN_COMPLETE` to Tk.  Tk then
destroys the root; the main wiring code joins Core and Mem, sends Disk its
sentinel once no new Mem writes can occur, and joins Disk.  Define this exact
order for the new app rather than relying on daemon threads or process exit.

## Non-rules and traps

- Never call Tk from outside the Tk machine or let a worker touch widget
  references.
- Keep `main.py` as wiring.  Do not place application behavior there.
- Do not introduce a global mutable current-runtime record; use a claimed
  thread-local runtime.
- Do not put Mobile Stack creation, frame handling, dropping, or routing in a
  reducer case.
- Do not habitually pass a runtime, stack, queue, widget registry, or full
  application context as function arguments.  Pass real call-time variation;
  use the claimed machine context for its current runtime and stack.
- Do not treat traveling registers as canonical storage, or trust ordinary
  registers across threads, callbacks, or delayed work.
- Do not create separate message, model, and queue modules merely because a
  conventional architecture diagram has them.  Add a module only when a real
  small machine or coherent domain needs one.
- Do not grow a broad framework, managers, controllers, or abstraction layers
  around these four machines.  Prefer visible dictionaries, small procedural
  modules, and handlers whose names say when and what they handle.

## Adoption sequence for a fresh app

1. **Smallest skeleton:** make `main.py`, `machine.py`, `mobile_stacks.py`,
   `tk.py`, `core.py`, and `mem.py`.  Give each worker an inbox/runtime,
   claim runtimes in their threads, run a Tk window, send one Tk semantic
   event to Core, and return one Core declarative command to Tk.  There is no
   Disk yet and no generic framework.
2. **First real Mem round trip:** choose one small canonical record mutation.
   Implement one reducer event/effect, one `Core -> Mem -> Core` Mobile Stack,
   one Mem invariant, and one targeted Tk command.  Establish copied return
   records and acceptance/rejection now; this proves ownership is real.
3. **Disk last:** define a compact serializable bundle for Mem's canonical
   records, add `LOAD_BUNDLE` and `WRITE_BUNDLE` frames, then add startup load,
   dirty/coalesced writes, forced flush, and the shutdown join order.  The
   durable format is an app choice, not part of this architecture.

## Today mapping (reference only)

The portable machinery is currently implemented in
[`src/today/machine.py`](../../src/today/machine.py),
[`src/today/mobile_stacks.py`](../../src/today/mobile_stacks.py), and the
wiring portions of [`src/today/main.py`](../../src/today/main.py).  Today uses
its Core, Mem, Disk, and Tk modules for the application-specific cases.  In a
new application, reuse the shape and rewrite those cases around the new
records and vocabulary rather than importing Today concepts.

One deliberate portability correction: Today's current
`enqueue_core_command_and_wake_tk()` calls `root.event_generate(...)` from the
Core worker.  Do not copy that bridge into a fresh app under the strict
Tk-only rule above; have Tk own command draining instead.  This guide changes
no Today behavior.
