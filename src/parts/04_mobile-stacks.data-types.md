# Mobile Stacks Spike — Data Types

This is a reference for the dictionaries and queues used by
`04_mobile-stacks.py` and `loglogic.py`.

The spike uses ordinary Python dictionaries, lists, `deque` objects, and
`queue.Queue` objects. There are no application-defined classes.

## `g` — central Tk-system facts

```text
g
- root -- `tk.Tk | None`: the Tk event-loop shell
- headless -- `bool`: true when `--headless` is in use
- selected-day -- `datetime.date`: day currently requested by the user
- orientation -- `str`: top-area orientation text
- heartbeat -- `int`: rendered heartbeat counter
- shutting-down -- `bool`: prevents new Tk pump / heartbeat scheduling
- tk-pump-scheduled -- `bool`: whether a Tk scheduler callback is pending
- next-stack-number -- `int`: source for readable new stack ids
- completed-stack-count -- `int`: count of completed UI stacks
- startup-load-day -- `str | None`: initial day request deferred until tk boot ends
```

`g` contains central, fixed-shape program facts. It is not the storage for
day records, stacks, widgets, or machine queues.

## `threads` — physical execution contexts

```text
threads
- key -- `str`: thread name, currently `"tk"`, `"mem"`, or `"disk"`
- value -- thread-state record:
  - in-queue -- `queue.Queue`: cross-thread delivery packets for this thread
  - machine-names -- `list[str]`: ids of machines run by this thread
  - current-machine -- `str | None`: register naming the machine now running
  - stack -- stack record | `None`: the one stack this thread currently holds
  - stack-phase -- `None | "building" | "executing"`
    - building -- the current stack is being assembled
    - executing -- the scheduler owns this stack for one reconciliation quantum
  - builder -- construction-register record
    - serials -- `list[open serial]`: nested serial procedures being built
  - target -- `str | None`: target machine for the next created instruction
  - next-machine-index -- `int`: round-robin starting position for machines
  - thread-type -- `"system" | "worker"`: Tk main thread or worker thread
  - entry-fn -- function: procedure used to run a worker thread
  - thread-obj -- `threading.Thread | None`: live worker object; `None` for Tk
  - stop-requested -- `bool`: tells a worker loop to stop when it is idle
```

The current physical thread finds its own thread-state record with:

```python
state() == threads[threading.current_thread().name]
```

`state()["stack"]` holds at most one stack at a time, but that is only the
thread's current working register. Its inbound queue and each hosted machine's
run queue can hold any number of other stacks waiting to run. `stack-phase`
explicitly says whether the current stack is being built or is executing.
After `end_stack()`, the completed stack remains current with phase `None`
until `post_stack()` transfers ownership to a queue. Both registers are then
cleared; execution also clears them after its quantum ends.

`state()["builder"]` contains only construction cursor state. Each physical
thread has its own independent serial cursor. `state()["target"]` is a common
register used for both construction and live stack manipulation.

`set_register(key, value)` always writes into
`state()["stack"]["registers"]`. The explicit `stack-phase` explains whether
that current stack is being built or executed.

## `machines` — semantic execution machines

```text
machines
- key -- `str`: machine id, currently `"tk"`, `"mem"`, or `"disk"`
- value -- machine record:
  - thread -- `str`: id of the physical thread hosting this machine
  - run-queue -- `collections.deque[stack]`: stacks runnable on this machine
  - handler -- function: primitive-frame handler for this machine
```

A machine owns its `run-queue`. A machine does **not** own an inbound queue.
Thread inbound queues receive cross-thread delivery packets; the receiving
thread admits each packet to its designated machine's `run-queue`.

The current spike has one machine per thread, with matching names. The
`machine-names` list and `next-machine-index` register allow a future thread
to host multiple machines without changing the basic records.

## Delivery packet

```text
delivery
- machine -- `str`: target machine id
- stack -- stack record: complete continuation being handed off
```

A continuation moves through this path:

```text
source machine
→ threads[target-thread]["in-queue"]
→ machines[target-machine]["run-queue"]
```

Putting the stack into the target thread's inbound queue transfers ownership.
The sending machine must not alter that stack afterward.

## Stack

```text
stack
- id -- `str`: readable stack id, for example `"load-day-4"`
- kind -- `"startup" | "ui"`
  - startup -- a boot stack created during program startup
  - ui -- a stack created by a UI request or Tk system request
- registers -- `dict`: named state belonging to this one logical operation
  - day -- `str`, for day-flow stacks: the selected ISO day text
  - day-record -- complete day-record snapshot, after `MEM_LOAD_DAY` finishes
- frames -- `list[frame]`: frames ordered `[bottom, ..., top]`
```

The last item in `frames` is the active frame. The stack is the complete
continuation of a logical operation, including all suspended parent frames.
Its `registers` mapping travels with it unchanged through machine and thread
transfers. A register is stack-local state, not a thread working register and
not frame-local operation data.

## Stack frame

Every live frame includes:

```text
frame
- machine -- `str`: machine that must execute this frame
- op -- `str`: primitive operation name, `"SERIAL"`, or `"YIELD"`
- data -- `dict`: operation-specific fields, including serial procedure fields
- child-result -- any value | absent: generic slot for a completed child result
```

Operation-specific fields are always bundled under `frame["data"]`; they do
not appear alongside `machine` and `op`. Examples include:

```text
DISK_READ_DAY frame
- data
  - no fields: reads the day from `state()["stack"]["registers"]["day"]`

MEM_EDIT_AND_SAVE frame
- data
  - edit -- edit record
  - stage -- `str`: local resumption marker, for example `"waiting-for-disk-save"`

MEM_SET_PANEL_STATE frame
- data
  - path -- `list[str | int]`: path within the selected panel's state
  - value -- replacement value for the final path component
- stack register
  - panel -- `str`: selected panel id

SET_TODO_STATE frame
- data
  - item -- `int`: TODO item index
  - done -- `bool`: state explicitly selected by the user
- stack register
  - panel -- `str`: selected panel id, bound by Tk/control before posting

MEM_SAVE_DAY frame
- stack register
  - panel -- `str`: panel whose owning day is persisted

DISK_WRITE_DAY frame
- data
  - day-record -- complete persisted day bundle being written

`MEM_LOAD_DAY` splits the disk bundle into `memory["days"][day]` and the
top-level `memory["panels"]` records, then puts a copied day bundle into
`state()["stack"]["registers"]["day-record"]`. `MEM_EDIT_AND_SAVE` refreshes
that stack-register bundle after its in-memory edit and writes a reassembled
bundle to disk. `TK_RENDER_DAY` reads the stack-local bundle; there is no
`MEM_RETURN_DAY` frame in this version of the spike.

`SET_TODO_STATE` is the Tk/control-facing semantic instruction. Tk/control
binds the selected panel in the stack register and supplies the item plus
explicit desired `done` value; it never asks mem to toggle or infer the
opposite state. Mem drops the semantic frame, then pushes the private
`MEM_SET_AND_SAVE_TODO` serial. Its steps are `MEM_SET_PANEL_STATE` with
`path == ["items", item, "done"]`, then `MEM_SAVE_DAY`.
`MEM_SET_PANEL_STATE` uses `resolve_path(data, path)` to locate the containing
state record and assign the final path component.
`MEM_SAVE_DAY` derives the day from the selected panel's reverse `day` link,
updates the stack's `day` register, then writes that day bundle through disk.
The TODO stack is mem-only after its UI callback; it does not perform a Tk
render.

TK_PANEL_EVENT frame
- data
  - panel -- `str`: panel id used for Tk panel-type dispatch
```

### Result slot

```text
child-result -- any value | absent
```

When a child frame completes, `pop_frame(result)` removes it. If a parent
frame remains underneath, the result is written into:

```python
parent["child-result"] = result
```

The parent later resumes and can inspect that visible result slot. This spike
uses one last-child-result slot; a later child result replaces an earlier one.

## Serial frame and instruction templates

A serial frame is a multi-step procedure represented directly in frame data:

```text
serial frame
- machine -- `str`: machine that expands this procedure
- op -- `"SERIAL"`
- data
  - name -- `str`: readable procedure name
  - steps -- `list[instruction template]`: ordered child instructions
  - ip -- `int`: index of the next instruction template to push
- child-result -- result of the most recently completed child, if any
```

`steps` holds inert instruction templates. A template becomes a live frame
only when `push_frame()` copies it onto `state()["stack"]`.

```text
instruction template
- machine -- `str`: target machine for a future child frame
- op -- `str`: operation for that future frame
- data -- `dict`: optional operation-specific data
```

For example, the root day-load procedure is conceptually:

```text
TK_LOAD_AND_RENDER_DAY, serial on tk
- 0: MEM_LOAD_TRANSACTION, serial on mem
- 1: TK_RENDER_DAY, primitive on tk
```

If a serial frame has `ip == 0` and two steps, its next expansion pushes step
zero and changes `ip` to `1`. When `ip == len(steps)`, all children have been
pushed and the serial frame itself can complete using its `child-result`.

## Progressive construction context

Each thread uses one `state()["stack"]` register for both construction and
execution. `begin_stack()` creates an inactive stack there and sets
`state()["stack-phase"]` to `"building"`; construction fails if that thread
already holds a stack. `builder` contains only the nested serial cursor.

```python
begin_stack(stack_id, kind)
target("tk")

begin_serial("FOO")
instruction("...")
end_serial("FOO")

end_stack()
post_stack()
```

`target()` selects the target machine for subsequently created instructions,
whether a stack is being built or a live stack is being executed.
`begin_serial()` captures that target for the serial it opens. Nested serials
are represented by `state()["builder"]["serials"]`; closing one attaches it
to the enclosing serial, or makes it the new stack's sole root instruction.
`instruction()` appends to the innermost serial, or creates a root primitive
instruction when no serial is open. When `stack-phase` is `"executing"`,
`instruction()` instead pushes a live frame on `state()["stack"]`.
`end_stack()` requires every serial to be closed and exactly one root frame,
then clears the `"building"` phase. It does not return or clear the stack.

`post_stack()` requires a current stack with no active phase: the state left
by `end_stack()`. It reads the root frame's machine, delivers the stack to
that machine's hosting thread, and then clears the caller's current `stack`
and `stack-phase` registers. The destination is therefore contained in the
stack; the caller supplies no stack or machine argument.

The same surface language also expands a live stack:

```python
target("disk")
instruction("DISK_READ_DAY")
```

With `stack-phase == "executing"`, this creates the instruction template and
pushes its live frame onto `state()["stack"]`.

`serial(name)` is optional syntax sugar only:

```python
with serial("FOO"):
    instruction("...")
```

It calls `begin_serial("FOO")` on entry and `end_serial("FOO")` on exit. It
adds no construction state or execution behavior beyond those primitives.

The day-flow builders now use this progressive form. For example, the
load-and-render stack is constructed conceptually as:

```python
begin_stack(stack_id, "ui")
set_register("day", day_text)
target("tk")
with serial("TK_LOAD_AND_RENDER_DAY"):
    target("mem")
    with serial("MEM_LOAD_TRANSACTION"):
        instruction("MEM_LOAD_DAY")
        instruction(YIELD)
    target("tk")
    instruction("TK_RENDER_DAY")
end_stack()
post_stack()
```

`make_panel_edit_stack()` follows the same pattern, adding its optional Tk
panel event before its mem edit transaction.

## `memory` — mem-owned authoritative day and panel records

```text
memory
- days -- dict
  - key -- `str`: ISO day text, for example `"2026-09-02"`
  - value -- day layout record
    - day -- `str`: ISO date text
    - position-panel -- dict mapping positions to panel ids
- panels -- dict
  - key -- `str`: panel id
  - value -- panel record
    - day -- `str`: owning ISO day text
    - type -- `"TODO" | "JOURNAL"`
    - state -- type-specific mutable panel state
```

Only `mem` primitive operations mutate this collection. A day owns its layout
and panel ids; a panel owns its type, mutable state, and reverse `day` link.
The intended invariant is: if a day position references panel `P`, then
`memory["panels"][P]["day"]` is that day.

Tk does not consult this authoritative collection. Mem puts a copied day
bundle into the traveling stack's `day-record` register for Tk rendering.

## `disk_store` — simulated disk-owned records

```text
disk_store
- days -- dict
  - key -- `str`: ISO day text
  - value -- persisted day bundle
    - day -- day layout fields
    - panels -- panel records belonging to that day
```

This is an in-process simulation, not a filesystem. `DISK_READ_DAY` returns a
deep copy of a stored day bundle; `DISK_WRITE_DAY` replaces the stored bundle
with a deep copy. `install_day_bundle()` splits a bundle into the authoritative
top-level memory collections; `make_day_bundle()` reassembles one for writing.
No disk path or M1 persistence format exists in this spike.

## Day record

```text
day record
- day -- `str`: ISO date text
- position-panel -- dict
  - key -- `str`: position id, currently `"position-1"` or `"position-2"`
  - value -- `str`: mounted panel id
```

```text
panel record
- day -- `str`: owning ISO day text
- type -- `"TODO" | "JOURNAL"`
- state -- type-specific panel state
  - TODO state
    - items -- list of item records
      - text -- `str`
      - done -- `bool`
  - JOURNAL state
    - text -- `str`
```

## Tk panel and widget collections

```text
widgets
- key -- `str`: readable widget role, for example `"date-label"` or `"trace"`
- value -- live Tk widget or Tk variable
```

```text
position_widgets
- key -- `str`: position id
- value -- position widget record
  - host -- `ttk.LabelFrame`
  - panel-label -- `ttk.Label`
  - mounted-panel -- `str | None`
```

```text
panel_types
- key -- `str`: panel id
- value -- `"TODO" | "JOURNAL"`: Tk-cached panel type
```

```text
panel_widgets
- key -- `str`: panel id
- value -- widget record for its currently mounted contents
  - content -- `ttk.Frame`
  - status -- `ttk.Label` for TODO panels, when applicable
  - text-var -- `tk.StringVar` for JOURNAL panels, when applicable
```

These collections belong to Tk. The `panel_types` mapping is used by
`handler_tk()` for panel-type routing. `render_day_snapshot()` fills that cache
from the day bundle in the current stack register; Tk never consults
authoritative `memory`.

## `panel_handlers`

```text
panel_handlers
- key -- `"TODO" | "JOURNAL"`
- value -- function: handler for a Tk frame addressed to that panel type
```

Machine routing happens first: the top frame must be addressed to `tk`.
Panel routing happens inside `handler_tk()` only when that Tk frame has a
`panel` field.

## `loglogic.events` — narrative trace queue

```text
loglogic.events -- `queue.Queue[trace event]`

trace event
- type -- event name:
  - EXTERNAL_EVENT
  - SYSTEM
  - STACK_CREATED
  - STACK_SUBMITTED
  - STACK_UPDATED
  - STACK_TRANSFERRED
  - FRAME_RETURNED
  - FRAME_COMPLETED
  - STACK_YIELDED
  - STACK_COMPLETED
- stack -- stack snapshot | `None`
- data -- dict of event-specific presentation facts
```

`loglogic.emit()` deep-copies a stack when it records an event. Workers only
enqueue these semantic events. The Tk thread drains and presents them through
`loglogic.present_pending()`, which keeps output formatting out of the
execution machinery.
