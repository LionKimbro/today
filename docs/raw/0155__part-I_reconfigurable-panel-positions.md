# Today Interaction Experiment — Panel Host / Panel Identity Revision

Revise the current `experiment.py` interaction-model experiment.

The current event architecture is basically good and should be preserved:

```text
Tk callback
→ encode application event
→ append to global or per-panel queue
→ request after_idle processing
→ process event queues
→ load registers
→ dispatch to semantic handler
→ mutate state
→ queue GUI consequence
→ process GUI consequences
→ perform Tk operations
```

The current file already implements this basic staged-machine path with separate global and per-panel event queues, active registers, semantic panel dispatch, and GUI dispatch. Do not redesign that part unnecessarily.

The major conceptual change is about the relationship between:

```text
layout position
panel identity
panel type
live GUI widgets
```

These are not the same thing.

## Core Correction

A **panel position** is a persistent place in the GUI layout.

A **panel** is a semantic panel instance which may occupy that position.

A **panel type** describes what kind of panel that semantic panel is, such as:

```text
TODO
JOURNAL
```

Therefore:

```text
panel position ≠ panel identity ≠ panel type
```

Do not model switching from Todo to Journal as changing the type of the same panel ID.

Instead, a position which currently displays one panel may later display a different panel.

For example:

```text
position-1
    currently contains panel-todo-1
```

and later:

```text
position-1
    currently contains panel-journal-1
```

The GUI position survives.

The semantic panel instance changes.

## Panel Hosts

Create persistent **panel hosts**.

A panel host belongs to a panel position, not to a semantic panel.

Conceptually:

```python
position_widgets = {
    "position-1": {
        "host": ...,
    },

    "position-2": {
        "host": ...,
    },
}
```

Build these hosts first.

For example, instead of directly doing:

```python
build_todo_panel(parent, "panel-1")
build_journal_panel(parent, "panel-2")
```

the experiment should first do something conceptually like:

```python
build_panel_host(parent, "position-1")
build_panel_host(parent, "position-2")
```

The host should remain alive while different semantic panels are installed into it.

The host should therefore be the GUI object corresponding to the stable layout position.

## Panel Assignment

Maintain explicit state describing which semantic panel currently occupies each position.

Conceptually:

```python
position_panel = {
    "position-1": "panel-todo-1",
    "position-2": "panel-journal-1",
}
```

Then retain separate tables such as:

```python
panel_type = {
    "panel-todo-1": TODO_PANEL,
    "panel-journal-1": JOURNAL_PANEL,
}
```

and:

```python
panel_state = {
    "panel-todo-1": {
        ...
    },

    "panel-journal-1": {
        ...
    },
}
```

The exact names may vary, but preserve the conceptual separation.

The important rule is:

```text
position tells us WHERE
panel_id tells us WHICH semantic panel
panel_type tells us WHAT KIND of panel
```

## Initial GUI Installation

After creating the panel hosts, install the default semantic panels into them.

Conceptually:

```text
position-1 gets panel-todo-1
position-2 gets panel-journal-1
```

Do not hardwire the host itself as a Todo host or Journal host.

Instead:

```text
build panel host
↓
look up assigned panel_id
↓
look up panel type
↓
dispatch to type-specific GUI installer
```

Conceptually:

```python
install_panel_gui(position_id)
```

which internally determines:

```python
panel_id = position_panel[position_id]
panel_kind = panel_type[panel_id]
```

and dispatches:

```python
panel_builder[panel_kind]()
```

or equivalent.

## Type-Specific Panel GUI Builders

The Todo GUI and Journal GUI should remain type-specific.

For example:

```python
panel_builder = {
    TODO_PANEL: build_todo_panel_gui,
    JOURNAL_PANEL: build_journal_panel_gui,
}
```

These functions should build their controls **inside the already-existing host for the active position**.

They should not create the layout-position frame itself.

The host is persistent.

The type-specific contents are disposable.

Conceptually:

```text
position host
    ↓
currently contains TODO widgets

later:

position host
    ↓
TODO widgets destroyed
    ↓
JOURNAL widgets created
```

## Active GUI Registers

When installing or updating a panel GUI, load enough registers to describe both:

```text
the active position
the semantic panel occupying it
```

Conceptually, the register set may need to grow from the current:

```python
reg["panel_id"]
reg["panel_widgets"]
reg["panel_state"]
reg["panel_type"]
```

to include something like:

```python
reg["position_id"]
reg["position_widgets"]
```

The exact structure is flexible.

The important distinction must remain obvious in the code.

## Panel Widgets

The current program has:

```python
panel_widgets[panel_id]
```

This concept may still be useful, but be explicit about what it means.

Type-specific widget references belong to the **currently mounted semantic panel GUI**, while the persistent outer host belongs to the **position**.

A reasonable conceptual organization is:

```python
position_widgets[position_id]["host"]
```

for persistent layout machinery, and:

```python
panel_widgets[panel_id]
```

for live widgets belonging to a mounted semantic panel.

When a panel is removed from a position, its live widget references should be removed or cleared.

When another panel is installed, its live widget references should be registered.

## Demonstrate Panel Replacement

Add a simple experimental control which changes the semantic panel occupying a position.

For example, position-1 may initially contain:

```text
panel-todo-1
```

and a control may request that position-1 instead display:

```text
panel-journal-1
```

Later it should be possible to switch back.

The important behavior is:

```text
position-1
    panel-todo-1 / TODO

→ replacement →

position-1
    panel-journal-1 / JOURNAL

→ replacement →

position-1
    panel-todo-1 / TODO
```

The position remains the same.

The semantic panel IDs remain distinct.

The Todo panel retains its Todo state.

The Journal panel retains its Journal state.

Switching back should therefore restore the prior semantic state of that particular panel.

## Reconfiguration Requests

Do **not** put panel-replacement requests into the ordinary semantic event queue for the panel.

Panel replacement changes the machinery which will interpret future panel events.

Give reconfiguration requests their own queue or equivalent explicit mechanism.

Conceptually:

```python
panel_reconfiguration_queue = deque()
```

A request might say:

```python
{
    "position_id": "position-1",
    "new_panel_id": "panel-journal-1",
}
```

The exact record format is not important.

## Reconfiguration Happens at Quiescence

Panel reconfiguration should happen only after ordinary event processing has become quiescent.

The idle processing cycle should conceptually become:

```text
process global events

process ordinary panel events

process GUI consequences

if ordinary event queues are empty:
    process panel-reconfiguration requests
```

Do not change the semantic panel assignment while old semantic events are still waiting to be handled.

## Reconfiguration Procedure

When processing a reconfiguration request:

```text
1. confirm ordinary event queues are quiescent

2. identify the position being changed

3. identify the old panel currently occupying it

4. tear down the old type-specific GUI contents

5. clear/remove the old panel's live widget registrations

6. update the position → panel assignment

7. identify the new panel's type and state

8. build the new type-specific GUI inside the same persistent host

9. attach event sensors for the new panel

10. populate the GUI from the new panel's authoritative state

11. clear the event queue for the affected panel(s) as appropriate
```

After the replacement is complete, aggressively invalidate any residual ordinary events associated with the old GUI incarnation.

The intended policy is deliberately simple:

```text
wait for quiescence
perform replacement
clear residual events
```

If some bizarre Tk event is generated during teardown or reconstruction, it should not survive the reconfiguration boundary.

## Event Sensors After Reconfiguration

Type-specific GUI builders must attach the appropriate event sensors for the semantic panel being installed.

For example:

```text
Todo button callback
    → queues event using panel-todo-1

Journal Entry callback
    → queues event using panel-journal-1
```

When Todo GUI widgets are destroyed, their Tk bindings disappear with them.

When Journal GUI widgets are created, new bindings are attached using the Journal panel's panel ID.

This is an important part of the experiment.

Repeated switching must prove that input always routes to the currently installed semantic panel.

## Do Not Use Fake Semantic Events for GUI Initialization

The current experiment ends Todo construction by queueing a `TOGGLE_TODO` event merely to cause an initial display refresh.

Remove this behavior.

Building or installing a GUI must never mutate semantic state merely to initialize its appearance.

Instead:

```text
build widgets
↓
read authoritative current state
↓
populate widgets
```

The current code's initialization trick should therefore be eliminated.

## Preserve the Existing Event Architecture

Do not replace the current global/per-panel event system.

In particular, preserve the useful pattern already present:

```text
per-panel event queue
↓
load panel registers
↓
dispatch according to panel type
↓
semantic state mutation
↓
GUI consequence
```

Likewise preserve the heartbeat behavior:

```text
Tk timer fires
↓
SECOND_ELAPSED global event is queued
↓
after_idle processing is requested
```

The goal of this revision is **not** to invent a new event framework.

It is to prove that the existing event framework continues to work when the GUI routinely tears down one semantic panel and installs another into the same layout position.

## Desired Final Demonstration

The resulting experiment should visibly demonstrate all of the following:

```text
stable position host
        ↓
semantic panel installed
        ↓
panel-specific events routed by panel_id
        ↓
semantic handlers dispatched by panel type
        ↓
GUI consequences update correct live widgets
        ↓
quiescent boundary
        ↓
semantic panel removed
        ↓
different panel installed in same position
        ↓
new event sensors installed
        ↓
new panel events routed correctly
        ↓
switch back
        ↓
original panel's state is still present
```

Repeatedly switch one position between Todo and Journal.

If this remains correct through repeated installation, teardown, event rebinding, state restoration, and event routing, then the experiment has demonstrated the interaction behavior needed before integration into the larger Today page/row/pane chassis.
