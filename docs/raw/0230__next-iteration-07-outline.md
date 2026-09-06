# Next Iteration `07`: Outline Toward a Reducer Core, World Model, and Device Tk

## Purpose

`06_combined-model.py` proved an important thing: the Mobile Stacks nervous
system can carry real Today layout work through Tk, Mem, Disk, and back to Tk.
It did not establish the final architecture.

The next iteration should explore an architecture in which:

```text
Tk is a GUI device machine.
The Reducer Core owns bounded present application meaning.
Mem owns the large canonical world model.
Disk owns persistence.
Mobile Stacks carry work that needs context and continuation.
```

This outline is a direction of investigation.  It is not yet a specification
to implement wholesale.


## The Revised Assumptions

The following prior assumptions should be discarded:

```text
The Reducer Core must contain the whole semantic world.

Mobile Stacks must govern every Tk event.

Tk ownership of widgets implies Tk ownership of the whole layout world.

Only Mobile Stacks may cross every machine boundary.
```

The resulting architecture uses more than one honest communication form.


## Machines and Jurisdictions

### Tk machine

Tk remains on the main thread and owns only what Tk must own:

```text
live widgets
widget bindings
focus
temporary drag mechanics
local hover/selection/animation mechanics
the legal execution of Tk commands
```

Tk is a device adapter, not the application’s decision-maker.

It has two primary duties:

```text
receive physical/UI events
    -> normalize semantically meaningful ones into plain data

receive declarative render commands or snapshots
    -> perform the necessary legal Tk realization
```

Raw Tk event objects, widget references, and arbitrary callbacks do not cross
out of the Tk thread.


### Reducer Core machine

The Reducer Core owns a bounded working state: the present on-screen
situation, rather than the entire Today database.

Illustrative state includes:

```text
selected day
current loaded day-layout snapshot
selected tab
currently hosted positions
loaded snapshots for visible panels
pending request / loading / error state
modal or interaction mode
```

It owns a real reducer relationship:

```text
reduce(state, event) -> next_state, effects
```

The reducer is the place where the application decides the next legal
on-screen state.  It is designed to be testable without Tk, threads, Mem, or
Disk.


### Mem machine

Mem owns the large canonical world model:

```text
all days
all panel records
whiteboard history
journal material
future Arc-related information
cached records and semantic indexes
```

Mem is not the Reducer Core’s bounded screen state.  It is the authoritative
world that the Reducer Core can request work from and commit changes to.

Panel semantic behavior belongs principally here: journal editing, TODO
changes, whiteboard meaning and history, panel creation, and panel selection.


### Disk machine

Disk owns the durable files and performs persistence work only when instructed
through its machine boundary.  The exact day-oriented file format remains a
later decision.


## Communication Forms

### Tk event queue

When a Tk interaction becomes semantically meaningful, Tk emits normalized
data to the Reducer Core.

```python
{
    "type": "SET_ROW_HEIGHT",
    "tab_id": "tab-...",
    "row_number": 2,
    "height": 240,
}
```

Tk-local rendering mechanics do not need to cross this boundary.  Examples
include raw mouse movement, hover coloring, native text selection, and other
high-frequency mechanics that do not yet represent a durable decision.


### Reducer effects

After committing a state transition, the Reducer Core processes declared
effects.  Effects may:

```text
enqueue a declarative Tk render command
start a Mobile Stack for Mem or Disk work
schedule a timer
record an observation
```

Effects must not be arbitrary hidden callback execution.  They should remain
inspectable data or explicit operations.


### Tk command queue

The Reducer Core sends Tk coarse declarative work, for example:

```text
RECONCILE_WORKSPACE with this screen snapshot
MOUNT_PANEL at this position with this panel snapshot
UPDATE_TOP_AREA with this date/orientation state
SHOW_DIALOG with this declarative request
```

Tk performs the widget mechanics locally.  The command vocabulary should
remain small and should not become remote procedure calls for every widget
mutation.


### Mobile Stacks

Mobile Stacks remain the architecture for work that needs traveling context
and continuation across semantic and persistence machines.

Typical routes include:

```text
Reducer -> Mem -> Reducer
Reducer -> Mem -> Disk -> Reducer
Reducer -> Disk -> Reducer
```

When a stack returns to the Reducer Core, its handler does not begin another
stack while the returned one is active.  It copies the result into Core-owned
delivery state or queues a plain result event, then completes the stack.  The
Reducer Core later reduces that result event and may emit new effects.


## Panels

Panel responsibilities divide by layer:

```text
Tk panel code
    rendering, widget construction, input normalization

Reducer Core
    current hosting, mounted position, visible snapshot, loading/error UI

Mem panel code
    canonical panel records and panel-specific semantic rules
```

The Reducer Core holds only snapshots for panels that are currently relevant
to the screen.  It does not absorb the full panel database.


## Initial Questions for `07`

Before implementation, answer these in small experiments:

1. Does the Reducer Core receive Tk events through a dedicated queue, a
   Mobile Stack, or a deliberately chosen mixture?
2. Is the active day layout a Core working snapshot whose canonical version is
   stored in Mem, or is some bounded portion of layout Core-authoritative?
3. What minimal declarative Tk command vocabulary is sufficient to reconcile
   the current rich layout system?
4. What exact panel snapshot is needed for each mounted position?
5. How should Mobile Stack results become Reducer events while preserving
   ordering, inspectability, and no nested active stacks?


## Immediate Development Posture

Do not immediately rebuild `06` into `07`.

First make a small, inspectable spike that proves:

```text
Tk semantic event
    -> Reducer event queue
    -> pure reduction
    -> declarative Tk command
```

Then add one Mobile Stack effect to Mem and return its result as a Reducer
event.  Only after those two seams are visible should the rich `03` layout
system be migrated.

`06` remains valuable as the proof that Mobile Stacks can carry real Today
work.  It is evidence and experimental lineage, not necessarily the final
application architecture.
