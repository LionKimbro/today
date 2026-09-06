# Conceiving the Merge: Today `06_combined-model.py`

## Purpose

`06_combined-model.py` will join the rich, reconfigurable Today interface
from `03_combined-model.py` with the Mobile Stacks machine architecture from
`05_mobile-stacks.py`.

This document records the architectural understanding reached before the
merge.  It is a commitment about the shape of the system, not a claim that
every panel or persistence detail has already been designed.

The governing image remains:

```text
03 supplies the body.
05 supplies the nervous system.
```

The result should be a Today application with a small, explicit nervous
system, not a runtime framework containing a Today application.


## The First Priority: Preserve the Whole Layout System

The layout system in `03` is not disposable demonstration material.  It is a
central capability of Today and must be preserved with fidelity.

This includes:

* tabs, including creation, selection, renaming, and deletion;
* rows, including addition, deletion, and persisted heights;
* one-, two-, and three-pane rows;
* persisted sash proportions;
* stable logical tab and panel identities;
* panel-to-position relationships; and
* the Tk realization of this complete day-specific layout.

Individual panel contents are deliberately less settled.  The layout system
must provide a durable, flexible host in which panels can be introduced,
replaced, and rebuilt incrementally.


## The Mobile Stacks Commitment

The merge adopts the Mobile Stacks model from `05` for machine ownership,
cross-thread work, continuation, and wakeup.

```text
Tk thread   = Tk machine
Mem thread  = Mem machine
Disk thread = Disk machine
```

Only a Mobile Stack crosses a machine boundary.  A stack contains:

```text
frames      control: which machine and operation come next
registers   situation: the data that must travel with the work
```

Frames remain small control records.  Registers carry coherent records such
as a day bundle, a panel record, a panel locator, or a user-selected layout
change.  Ordinary Python handlers do the work and use `push()` and `drop()`
to record continuation.

Machine-owned structures never cross threads directly.  Data leaving an
owned structure is copied into stack registers; data arriving into an owned
structure is copied out again.


## Ownership

The program has three distinct worlds.

```text
Tk owns live presentation.
  widgets, current hosts, mounted panel widgets, temporary drag state,
  presentation lookup tables, and rendered snapshots.

Mem owns authoritative semantics.
  day layouts, panel records, day-to-panel relationships, and the current
  semantic world needed to answer and apply requests.

Disk owns persistence.
  files and the durable serialized forms of complete day bundles.
```

Tk must never mutate Mem records directly.  Mem must never manipulate Tk
widgets or Tk-owned presentation structures.  Disk must not directly operate
on either application's structures.

The Tk layout can change widgets during an active drag, but its durable result
-- for example a row height or sash proportions when the drag ends -- is sent
to Mem as a Mobile Stack operation.


## This Is Not a Global Reducer Core

Previous reducer cores were valued for the clean equation:

```text
reduce(state, event) -> next_state, effects
```

That architecture has a centralized event queue and a separate effects
queue.  It is deterministic, testable in isolation, and naturally friendly
to histories, undo, and redo.

The merged program does not presently adopt that entire architecture.  A
Mobile Stack is not an effects queue.  It is one item of work carrying the
continuation that belongs to that item.  Its journey through Mem, Disk, and
Tk is not the same thing as a reducer producing detached queued effects.

The merged application will instead use a serialized world-state Mem machine:

```text
Only Mem changes durable semantic state.
Mem runs one Mobile Stack operation at a time.
```

This gives the semantic mutation stage a clear ordering and no relevant
concurrent mutation, without forcing the whole growing application into one
global reducer algebra.

The good local parts of reducer design may still be used where they fit.
In particular, the layout transformation logic from `03` is well suited to
small, Tk-free, testable transformations of a day layout.  This is a useful
internal seam, not a claim that `06` is a reducer-core application.


## How One Durable Change Moves

A user action begins on Tk, but Tk does not mutate authoritative semantic
state.

For a representative durable change:

```text
Tk callback
    captures the user-selected result in stack registers
    and submits one stack

Tk operation
    routes the stack to Mem

Mem operation
    changes Mem-owned day and/or panel records
    copies a coherent day bundle into the stack
    leaves Disk write and Tk render as continuation frames

Disk operation
    writes the copied day bundle

Tk operation
    receives the copied snapshot
    updates its local presentation records
    reconciles the complete layout and remounts panels
```

Stacks are individually owned and separately queued.  The one Mem thread
serializes semantic changes.  After it applies one change and routes that
stack onward, it may process the next waiting change; it does not wait for the
first stack's Disk write and Tk render to finish.

When Tk has moved to another day before an older render returns, Tk may reject
the stale presentation result while Mem and Disk retain the valid update to
the original day.


## Day and Panel Data

Mem's authoritative state is a world model.  It is not Tk state and it is not
the complete state of the entire process.

A day record must preserve the complete layout semantics from `03`, including
tabs, rows, pane counts, sash proportions, selected tab, logical positions,
and special panel slots.  Panel identity remains separate from position.

Portable panel records should remain transport-clean:

```python
{
    "id": "<panel-id>",
    "type": "<panel-type>",
    "day": "<day-id>",
    "data": {...},
}
```

No panel record may contain Tk widget references, mounted state, position
references, or Tk caches.  Tk maintains presentation relationships externally,
including `position_to_panel` and `panel_to_position`.


## Panel Development

The merge should establish the panel meta-system, not prematurely settle every
panel's final form.

Initial panels may begin with Orientation and either a basic Whiteboard or a
Journal.  Later panels can increase in complexity:

```text
Orientation
  < Basic Whiteboard
  < Journal
  < Whiteboard with submission history and navigation
  < To-Do
```

Future creation and selection of multiple whiteboards remains an open product
design matter.  A temporary simple choice such as a small fixed set of named
whiteboards is acceptable if it lets the layout and Mobile Stacks integration
advance without committing to a premature general panel library.

Each panel type should add only:

* its portable `data` schema;
* Mem operations that change that semantic data; and
* Tk rendering and input code for that type.

It should not require changing the Mobile Stacks runtime or the layout engine.


## Module Boundaries After the Integrated Merge

The first `06` program should remain integrated enough to prove the actual
machine boundaries and data flow.  It should not be divided into files before
the merge merely to satisfy an abstract organization preference.

After the integrated program works, its real process and ownership seams can
be separated into modules such as:

```text
Tk machine core
Mem machine
Disk machine
per-panel code
general utility functions
Tkinter helper functions
```

That split is also the transition from experiments to the application proper:

```text
src/parts/
    records the assembled experimental lineage through `06`

src/today/
    receives the validated, modular Today application
```

The parts have then done their work.  Further application development belongs
in `src/today/`, where the module boundaries are grounded in a working whole.

This later split should preserve the same visible global world and procedural
machine shape.  It must not reintroduce Manager or Controller classes, pass
shared machine context through function arguments, or conceal cross-machine
ownership behind a generic adapter layer.  Module boundaries should expose
the machinery that the successful merge has revealed.


## Persistence and Future History

Disk persistence belongs exclusively to the Disk machine.  The intended
directory organization is day-oriented, approximately:

```text
yyyy/yyyy-mm/yyyy-mm-dd/
```

The precise file arrangement remains to be decided: it may be a single
complete day bundle or a layout file accompanied by separate panel data.
The first implementation should favor a self-consistent complete day bundle,
because it makes loading, saving, redraw, and later undo reliable.  Splitting
files should wait for a concrete reason.

Durable semantic changes should not necessarily cause an immediate disk write.
Mem remains authoritative as changes arrive, while Disk persistence is parked
briefly so a burst of edits can accumulate.  The intended write policy is:

```text
after a durable edit:
    mark the relevant day dirty
    postpone its Disk write for one quiet second

when another durable edit arrives before that second has elapsed:
    keep the day dirty and postpone again

when a day has remained dirty for fifteen seconds:
    force a write even if edits continue
```

Tk redraw remains responsive to Mem state; it does not wait for the deferred
Disk flush.  The exact timer and stack choreography are implementation work
for later, but the ownership remains firm: Mem decides that a day is dirty and
Disk performs the eventual write through Mobile Stacks.

The world-state model does not automatically provide reducer-style undo/redo.
When history is added, Mem should own it.  A robust initial strategy is to
capture complete day bundles before durable semantic changes, maintain undo
and redo histories per day, and restore a prior bundle through the ordinary
Mem -> Disk -> Tk stack route.  Snapshot history is not required for the
first merge, but the merge must keep this path possible.


## Deferred Decisions

The following are intentionally not decided by this conception note:

* the exact on-disk filenames and whether a day bundle is split across files;
* the first non-Orientation panel chosen for `06`;
* the final creation and selection experience for multiple whiteboards;
* undo/redo scope, persistence, and history representation; and
* any later choice to introduce a true reducer core for a bounded semantic
  subsystem.

The merge should not wait for these decisions unless one becomes necessary to
make the complete layout, Mobile Stacks routing, persistence, and redraw path
work correctly.
