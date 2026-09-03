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
  - stack -- stack record | `None`: register holding the stack now running
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

`state()["current-machine"]` and `state()["stack"]` are temporary registers.
They are set before one reconciliation quantum and cleared afterward. They
are not cross-thread communication channels.

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

DISK_WRITE_DAY frame
- data
  - day-record -- complete day record being persisted

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

## `memory` — mem-owned authoritative day records

```text
memory
- days -- dict
  - key -- `str`: ISO day text, for example `"2026-09-02"`
  - value -- complete day record
```

Only `mem` primitive operations mutate this collection. Tk receives a deep
copy of a day record as a returned snapshot; Tk does not directly read or
mutate `memory`.

## `disk_store` — simulated disk-owned records

```text
disk_store
- days -- dict
  - key -- `str`: ISO day text
  - value -- complete persisted day record
```

This is an in-process simulation, not a filesystem. `DISK_READ_DAY` returns a
deep copy of a stored record; `DISK_WRITE_DAY` replaces the stored record with
a deep copy. No disk path or M1 persistence format exists in this spike.

## Day record

```text
day record
- day -- `str`: ISO date text
- position-panel -- dict
  - key -- `str`: position id, currently `"position-1"` or `"position-2"`
  - value -- `str`: mounted panel id
- panels -- dict
  - key -- `str`: panel id
  - value -- panel record
```

```text
panel record
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
panels
- key -- `str`: panel id
- value -- panel metadata
  - type -- `"TODO" | "JOURNAL"`
```

```text
panel_widgets
- key -- `str`: panel id
- value -- widget record for its currently mounted contents
  - content -- `ttk.Frame`
  - status -- `ttk.Label` for TODO panels, when applicable
  - text-var -- `tk.StringVar` for JOURNAL panels, when applicable
```

These collections belong to Tk. The `panels` mapping is used by `handler_tk()`
to route a panel-targeted Tk frame to the handler for that panel's type.

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
