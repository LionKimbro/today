# Panic-Diffusing Addendum: Panels, Core State, and Shipping Containers

## Purpose

The `07` outline correctly separates Tk, Reducer Core, Mem, Disk, and Mobile
Stacks, but that separation immediately raises a frightening question:

```text
Where does panel logic go?
```

Panels are not simple records.  Journals, whiteboards, and Todos can have rich
GUI interactions, active drafts, navigation, submission history, modes,
selection, loading states, and durable world meaning.  This note records the
insights that make the problem smaller and more navigable.


## Do Not Put All “Panel Logic” in One Place

“Panel logic” is not a single species of thing.  It divides by role.

```text
Tk-local panel mechanics
    caret and native text selection
    scroll position
    hover state
    raw drag motion
    widget construction and legal widget operations
    -> Tk machine

Active panel interaction state
    current draft
    active tool
    current history entry
    panel-specific UI mode
    pending/loading/error presentation state
    the currently visible panel snapshot
    -> Reducer Core state

Canonical panel world state
    saved journal entries
    persisted whiteboard history
    durable Todo items
    the panel record as part of the user’s world
    -> Mem machine
```

The correct question is therefore not “does panel logic belong in Core or
Mem?”  It is:

> For this specific panel fact, is it Tk-local mechanics, bounded active
> interaction state, or canonical durable world state?


## Panel Reducers Belong in the Core When They Govern the Present Interaction

The Reducer Core is not limited to one bland global reducer function.  It may
dispatch an event to panel-specific reducers that operate on the currently
active panel’s bounded Core state:

```python
reduce_journal_ui(core_state, event)
reduce_whiteboard_ui(core_state, event)
reduce_todo_ui(core_state, event)
```

These functions preserve the useful reducer relationship:

```text
current UI state + event -> next UI state + effects
```

They may update an active draft, choose a whiteboard-history entry, change an
active tool, mark the panel pending, or decide that an import/export effect is
needed.

They do **not** need to load every Journal, every Whiteboard, or every Todo in
existence into Core state.


## The Core Thread Is More Than the Reducer Function

The Reducer Core machine/thread can contain several visible stages:

```text
receive and queue Core events
reduce Core state
process declared effects
submit Mobile Stacks
receive returned-stack deliveries
queue later result events
emit declarative Tk commands
```

Only the state-transition stage is the Reducer Core proper.  Effect dispatch
and Mobile Stack delivery handling run on the same machine/thread but are not
the reducer equation itself.

This removes a false dilemma: code does not have to be either “inside the
reducer” or “somewhere unrelated.”  A machine can have an explicit operating
sequence around its reducer.


## The Shipping-Container Strategy

The working simplification is to treat a panel record as a coherent portable
shipping container.

```text
Mem canonical panel container
    -> deepcopy/import
Core active panel snapshot
    -> panel reducer and UI interaction
Core exports coherent panel container
    -> deepcopy/commit
Mem canonical panel container
```

An illustrative container is:

```python
{
    "id": "...",
    "type": "JOURNAL",
    "day": "...",
    "data": {...},
    "revision": 12,
}
```

This suggests a small first vocabulary:

```text
IMPORT_PANEL
EXPORT_PANEL
CREATE_PANEL
```

The immediate goal is not an enormous protocol of field-level messages.  It is
to load the whole relevant panel, work on the whole relevant active copy, and
save the whole relevant panel when a meaningful commit occurs.

Mem remains canonical.  Core holds the currently inhabited copy.  Tk owns the
live widgets around that copy.


## A Representative Journey

```text
Tk Journal widget
    -> normalized semantic UI event
Core event queue
    -> reduce_journal_ui(core_state, event)
    -> next Core state and EXPORT_PANEL effect
Mobile Stack
    -> Core to Mem with the coherent panel container
Mem
    -> accepts canonical copy and schedules persistence
returned Mobile Stack
    -> Core delivery handler queues PANEL_IMPORTED / PANEL_EXPORTED result
Core reducer
    -> updates bounded visible snapshot and emits RENDER_PANEL command
Tk command queue
    -> legal widget update
```

This is a working shape, not a commitment to every detail.  Future concerns
such as simultaneous edits, revisions, partial loading, and very large
whiteboards remain real, but they are later shipping-container concerns.  They
do not need to be solved before the first panel spike.


## The Calming Summary

```text
Panels do not force us to choose between Reducer Core and Mem.

Core governs the active interaction.
Mem governs the durable world.
Tk governs the live device mechanics.

Panels travel as coherent containers when they need to cross the boundary.
```

The next experiment should prove this with one intentionally simple panel,
such as Orientation or a Basic Whiteboard, before taking on Journal history or
Todo complexity.
