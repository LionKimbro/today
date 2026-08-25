```
date: 2025-08-25
title: Combining Models 01 (product of "part 0") and 02 (product of "part 1")
purpose: Combine models 01 and 02, products of part 0 and part 1, before we go on to part 2 (threads and work model)
```

# Today 03 Combined Model — Context Handoff

We are building **Today**, a daily operational cockpit for the larger Temple of Focus system.

Two separate GUI architecture experiments have already been completed successfully:

```text
01_panels-model.py
02_interaction-model.py
```

The purpose of this context is to build:

```text
03_combined-model.py
```

by combining the architectural ideas proven in `01` and `02`.

This is **not** yet the persistence implementation. Saving, loading, M1 storage, Fair Play leases, worker threads, and background job execution are deliberately being left out for now.

The immediate objective is narrower:

> **Prove that the real configurable panel/page chassis and the interaction/event model fit together cleanly as one single-threaded GUI/application machine.**

---

## Larger Program Context

Today is organized around an operational or **hodological day**.

A user may remain on a previous day after midnight, or navigate forward into tomorrow before the civil calendar changes. Day navigation is therefore explicit rather than mechanically forced by the clock.

The eventual Top Area is approximately:

```text
[<]  2026-08-25  [>] [今]   [ editable orientation text................ ]
```

`[今]` normally means the current civic date.

Below that is the main configurable workspace.

The GUI chassis follows the principle:

> **Rows stack. Panels divide. Pages switch.**

Conceptually:

```text
Today Window
    Top Area

    Page Tabs
        Page
            Row
                Pane / Position
                    Panel Host

    Status Bar
```

There may be any number of rows.

Each row contains 1, 2, or 3 horizontally divided panes.

Rows have independently adjustable heights.

Each whole-page tab owns a complete layout, so switching tabs can change:

```text
row count
row heights
pane counts
horizontal sash positions
panel assignments
eventual scroll position
```

A pane is fundamentally a **structural position**.

A semantic panel is mounted into that position.

---

# What 01 Proved

`01_panels-model.py` is the chassis/layout experiment.

It proved the configurable GUI structure:

```text
tabs
pages
rows
1–3 panes per row
resizable row heights
horizontal pane sashes
panel hosts
dynamic structural layout
```

The important conceptual distinction is:

> **The pane/position belongs to the GUI structure. The panel inhabiting it is content.**

Changing the panel content should therefore not require rebuilding the row, page, sash structure, etc.

Likewise, changing row geometry is not a semantic Todo/Journal/Whiteboard operation.

The combined model should preserve this separation.

---

# What 02 Proved

`02_interaction-model.py` is the interaction architecture experiment.

It is intentionally structured as a staged procedural machine.

Tk callbacks do not directly perform arbitrary application work.

Instead:

```text
Tk callback
    ↓
queue application event
    ↓
controlled processing stage
    ↓
mutate application state
    ↓
queue GUI consequence
    ↓
GUI consequence stage
    ↓
targeted widget update
```

It has separate concepts for:

```text
position_id
panel_id
panel_type
panel_state
panel_widgets
```

A position can be associated with one panel ID.

A panel ID has semantic identity and state.

A panel has a type such as:

```text
TODO
JOURNAL
```

and the interaction model dispatches panel events to the appropriate semantic handler.

It also already demonstrates replacing the panel mounted at a position.

Conceptually:

```text
position-1
    currently → panel-A → TODO

later:

position-1
    → panel-B → JOURNAL
```

The structural host remains.

The old panel GUI is torn down.

The new panel GUI is installed into the same structural position.

The panel's semantic state remains associated with its panel identity rather than with the host widget.

This distinction is central and should survive the combination.

---

# Why We Are Combining Them Now

The interaction experiment currently uses a deliberately tiny fake structure with a couple of hardcoded positions.

The chassis experiment provides the real structural environment:

```text
tabs
pages
rows
arbitrary dynamically created pane positions
```

The question this experiment needs to answer is:

> **Can the dynamically created positions from the real chassis become the positions into which the interaction machine mounts semantic panels?**

For example, the combined system may contain:

```text
Page A

Row 1
    position-17
    position-18

Row 2
    position-19
```

while the semantic configuration says:

```text
position-17 → panel-a812 → TODO
position-18 → panel-f194 → WHITEBOARD
position-19 → panel-99ac → JOURNAL
```

The interaction system should be able to route an event originating from `panel-a812` to the Todo logic and update only the relevant GUI.

The chassis should not need to understand Todo semantics.

The Todo logic should not need to understand Tkinter sash geometry.

---

# Major Objective: Position Identity

One particularly important design question is:

> **How does a dynamically created pane acquire a stable position identity and register itself with the interaction system?**

In `02`, positions were hardcoded for the experiment.

That will no longer be sufficient.

The combined model should discover a clean mechanism for dynamically creating and destroying structural positions.

A position probably needs something like:

```text
position_id
position_widgets
currently mounted panel_id
```

The exact representation is not predetermined.

Do not force a prematurely elaborate ontology.

But position identity must be explicit enough that:

```text
GUI event
→ panel identity
→ semantic state
→ targeted GUI consequence
```

remains understandable.

---

# Panel Identity and Panel Type

Do not collapse these concepts.

A panel has an identity independent of its type.

For example:

```text
panel_id = 1234...
panel_type = WHITEBOARD
```

Later that panel might perhaps be moved to another position.

Likewise, replacing the panel occupying a position does not mean the position itself became a different structural position.

Keep clear distinctions among:

```text
position identity
panel identity
panel type
panel state
panel widgets
```

The exact data structures may evolve, but the conceptual distinction matters.

---

# Panels Are Switchable Instruments

A Panel Host may display different kinds of instruments.

Possible eventual panel types include:

```text
Todo
Whiteboard
Journal
Objectives
Metrics
Upcoming
```

The experiment only needs enough fake panel types to prove the architecture.

Two types may be sufficient.

Do not implement the full Today application yet.

The point is to prove that:

```text
one position
    can mount one panel

that panel can be replaced

different panel types can have different:
    state
    event handlers
    widget builders
    GUI update logic
```

without creating callback chaos.

---

# Page Tabs Matter

A page tab represents an entire workspace layout.

Therefore the combined model should eventually be capable of handling this situation:

```text
Tab A
    Row 1
        position-A1
        position-A2

Tab B
    Row 1
        position-B1
    Row 2
        position-B2
        position-B3
```

Switching pages may therefore change the entire visible set of positions and panels.

The interaction model must not assume that every known panel is currently visible.

A semantic panel may exist in application state even when its tab is not currently displayed.

Likewise, GUI consequences aimed at an invisible/unmounted panel should be handled deliberately rather than accidentally updating unrelated widgets.

The combined experiment does not necessarily need to solve every future page-state issue, but it should avoid architectural assumptions that make this impossible later.

---

# Top Area

The combined experiment should also retain a small global Top Area.

It may remain as simple as:

```text
[<] date [>] [今] [orientation]
```

The Top Area is different from ordinary panels:

* it is global to the selected day;
* it remains visible while page tabs switch;
* it has editable/navigation behavior;
* it is not a semantic panel occupying a row position.

It should nevertheless participate in the same general interaction discipline:

```text
callback
→ queued event
→ state processing
→ GUI consequence
```

rather than becoming a separate pile of direct callbacks.

---

# Interaction Discipline to Preserve

A major goal is to avoid:

```text
widget
→ calls another widget
→ calls panel function
→ modifies state
→ callback fires
→ updates some other widget
→ ...
```

Instead preserve an explicit machine.

Approximately:

```text
USER INTERACTION STAGE
Tk callbacks only describe what happened.

        ↓

APPLICATION EVENT STAGE
Events are processed.
State is changed.
Consequences are requested.

        ↓

GUI CONSEQUENCE STAGE
Only the affected GUI is updated.

        ↓

STRUCTURAL RECONFIGURATION STAGE
When necessary, panels/positions/pages are mounted or unmounted.
```

The exact ordering can be refined if integration reveals a better structure.

The important part is that execution remains staged and visible.

---

# Keep the GUI Incremental

Do **not** adopt a model in which every state change rebuilds the entire Tk interface.

The chassis contains meaningful live GUI state:

```text
sashes
row heights
scroll positions
focus
editable controls
page geometry
```

The architecture therefore needs **targeted incremental updates**.

A Todo toggle should update the relevant Todo GUI.

An orientation edit should update orientation state.

A panel replacement should rebuild the contents of that panel host, not the whole page.

A row geometry change should remain a chassis operation.

---

# Explicitly Out of Scope

Do **not** add any of the following to `03_combined-model.py`:

```text
disk persistence
loading files
M1 documents
Fair Play
leases
five-second access waits
worker threads
thread synchronization
background save jobs
background load jobs
databases
real production schemas
```

All state should remain in memory.

We are intentionally trying to create a **single-threaded application core** first.

The eventual larger architecture is expected to have roughly three major parts:

```text
GUI / interaction machine
worker / threading / job machine
M1 persistence + Fair Play machine
```

The current experiment is still entirely inside the first part.

---

# Leave a Clean Future Seam

Although persistence and workers are out of scope, do not design the interaction model so that application code assumes everything must happen synchronously inside the GUI thread.

Eventually an application event may produce something conceptually like:

```text
REQUEST_BACKGROUND_WORK
```

and later a result may arrive like:

```text
BACKGROUND_WORK_COMPLETED
```

Those mechanisms will be designed separately.

For now, simply keep the interaction architecture explicit enough that another queue boundary can later be introduced without rewriting the whole GUI model.

Do not invent that queue yet unless a tiny placeholder materially clarifies the architecture.

---

# Development Philosophy

This is an architecture experiment.

Prefer:

```text
small
procedural
explicit
observable
easy to inspect
easy to throw away or revise
```

over building a generalized framework.

Do not prematurely create a reusable application library.

Do not solve every eventual Today feature.

We want to answer one question:

> **Can the successful chassis model and the successful interaction model become one coherent machine?**

If the combination exposes a conflict between the two experiments, treat that as valuable information.

Change the architecture rather than papering over the conflict.

The goal is not merely to make both files' features appear in one window.

The goal is to understand the clean conceptual relationship among:

```text
Page
Row
Position
Panel Host
Panel Identity
Panel Type
Panel State
Panel Widgets
Application Event
GUI Consequence
Structural Reconfiguration
```

When `03_combined-model.py` works and those relationships feel obvious rather than magical, the experiment has succeeded.

Only after that will we design the worker/thread/job system, and only after that will we introduce real M1 persistence and Fair Play lease-based writing.
