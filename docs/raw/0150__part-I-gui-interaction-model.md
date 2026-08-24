```
date: 2026-08-24
chatgpt: https://chatgpt.com/c/6a8c06a2-bc00-83e8-a6ad-2ff7cf294921
```

# Today GUI Interaction Model — Experimental Implementation Brief

Build a **small experimental Tkinter program** that demonstrates the interaction architecture intended for the larger **Today** application.

Do **not** attempt to implement the existing full page/tab/row/pane chassis yet. That chassis already exists separately. This experiment exists only to prove the event-routing, state-mutation, and GUI-update model before it is integrated into the larger program.

Today is ultimately a daily operational cockpit whose GUI contains a global Top Area, whole-page tabs, rows, panes, and switchable Panels. Panels will have stable identities independent of their current row/pane placement, and each panel may display a different semantic type such as Todo, Journal, Whiteboard, etc.

The larger architecture deliberately separates:

```text
GUI structure
≠
semantic/application state
≠
background persistence mechanics
```

This experiment is concerned only with the first two.

## Programming Style

Follow these architectural rules.

Do not create classes. Tkinter itself is class-based, but application code should be procedural.

Global variables are acceptable and expected. Their usage should be explicit and disciplined.

Think of the program as a **staged machine whose state evolves under explicit control**, not as a collection of objects which own behavior.

Operations should occur at the stage where they are intended to occur.

Application events should normally be encoded and queued first, then processed later during an idle processing pass.

Do not build persistence logic, worker threads, or Fair Play logic into this experiment.

## Core Interaction Principle

An incoming Tkinter event should not directly perform application logic.

The path should be:

```text
Tkinter event occurs
    ↓
Tkinter callback receives raw event
    ↓
raw event is interpreted / encoded as application event
    ↓
application event is appended to the appropriate queue
    ↓
program requests an after_idle processing pass
```

The callback should therefore remain very small.

The application logic runs later:

```text
next Tk idle opportunity
    ↓
process queued application events
    ↓
mutate authoritative application state
    ↓
record GUI consequences
    ↓
process GUI consequence queue
    ↓
perform actual Tk widget updates
```

This is the central behavior the experiment must demonstrate.

## Event Producers

There are at least two kinds of event producers.

### 1. User GUI interaction

Examples:

```text
button click
text edit
panel-local control action
```

The Tk callback should encode the action and place it into an application queue.

### 2. One-second heartbeat

The program should also maintain a recurring one-second Tk timer.

The timer callback itself should not perform timing logic.

Instead:

```text
one-second Tk timer fires
    ↓
encode global SECOND_ELAPSED event
    ↓
append it to the global event queue
    ↓
request after_idle processing
    ↓
schedule the next one-second Tk timer
```

Therefore the heartbeat behaves like any other event producer.

Later application logic may use `SECOND_ELAPSED` for countdowns or timed behavior.

## Idle Processing Scheduling

Do not poll continuously.

Whenever an application event is added to a queue, ensure that an idle processing pass has been requested.

Conceptually:

```python
if not g[PROCESSING_SCHEDULED]:
    g[PROCESSING_SCHEDULED] = True
    root.after_idle(process_pending_work)
```

When `process_pending_work()` begins, it may clear the scheduled flag.

The important invariant is:

```text
no pending work
    → no repeated idle processing

new event arrives
    → one idle processing pass is requested
```

If more work is generated during processing and another pass is required, it may be scheduled again.

## Global Events and Panel Events

The system must distinguish between:

```text
global application events
```

and:

```text
events associated with a particular panel
```

There should therefore be a global event queue and a queue associated with each panel identity.

Conceptually:

```python
global_event_queue = ...

panel_event_queues[panel_id] = ...
```

A panel-local Tk callback should determine which panel generated the interaction, encode the application event with the panel ID, and append it to that panel's queue.

The callback should not immediately dispatch to panel logic.

## Stable Panel Identity

Panels must have stable IDs.

Do not identify a panel semantically as:

```text
row 2, column 1
```

because placement may change later.

Instead use identities such as:

```text
panel-1
panel-2
panel-3
```

Layout and panel identity are separate concepts.

The experiment does not need the real row/pane system, but its internal representation should assume that panel identity survives movement and layout changes.

## Active-Panel Registers

When a queued panel event is finally processed, establish a small set of global working registers describing the panel currently being operated on.

Conceptually:

```python
g[PROCESSING_EVENT] = event

g[ACTIVE_PANEL_ID] =
    g[PROCESSING_EVENT][PANEL_ID]

g[ACTIVE_PANEL_WIDGETS] =
    panel_widgets[g[ACTIVE_PANEL_ID]]

g[ACTIVE_PANEL_STATE] =
    panel_state[g[ACTIVE_PANEL_ID]]

g[ACTIVE_PANEL_TYPE] =
    panel_type[g[ACTIVE_PANEL_ID]]
```

These are processing registers.

Their meaning is:

```text
this is the event currently being executed
this is the panel currently being executed against
this is its semantic state
this is its live Tk GUI
this is its panel type
```

The experiment should make this idea visible and understandable in the code.

## Panel-Type Dispatch

After the active-panel registers are loaded, dispatch according to panel type.

Conceptually:

```python
panel_handler[g[ACTIVE_PANEL_TYPE]]()
```

For example:

```python
panel_handler = {
    TODO_PANEL: handle_todo_panel_event,
    JOURNAL_PANEL: handle_journal_panel_event,
}
```

The type-specific panel handler should interpret:

```text
current event
+
current panel state
```

and mutate the authoritative application state.

It should **not directly manipulate Tk widgets**.

## GUI Consequences

After application state changes, the panel handler should record what the GUI needs to do.

Use a GUI consequence queue for the experiment.

Conceptually:

```text
panel event
    ↓
panel-type application handler
    ↓
state mutation
    ↓
GUI consequence appended
```

Then, during the same idle processing cycle or a subsequent controlled GUI-update stage:

```text
GUI consequence queue is read
    ↓
appropriate panel/widget registers are loaded
    ↓
type-specific GUI updater is selected
    ↓
Tk widget operations are performed
```

There should therefore be a second dispatch boundary:

```python
panel_gui_handler[g[ACTIVE_PANEL_TYPE]]()
```

or equivalent.

The distinction is:

```text
panel application handler
    understands what the event means

panel GUI updater
    understands how current state/consequence
    should be represented in Tk
```

## Tk Event Muting

The program should include a global input-muting flag:

```python
g["SHUT-UP"]
```

or a constant-key equivalent.

Raw Tk event sensors should check this flag before promoting a Tk event into an application event.

Conceptually:

```text
Tk callback fires
    ↓
if SHUT-UP:
    ignore it
else:
    encode application event
    queue it
```

This exists because programmatic manipulation of Tk/ttk widgets can itself generate Tk events.

When GUI-update code performs operations that could generate false user-input events, it may temporarily do:

```python
g[SHUT_UP] = True

# perform widget manipulation

g[SHUT_UP] = False
```

Keep this simple. Do not add elaborate machinery around it for this experiment.

## Suggested Toy GUI

Keep the actual interface very small.

Include a simple global Top Area approximating:

```text
[<]  2026-08-24  [>] [今]   [ editable orientation text ]
```

Also include at least two simple panel areas so that panel-local routing can be demonstrated.

The panels do not need production-quality behavior.

For example:

```text
Panel A
    type: TODO
    one or two controls

Panel B
    type: JOURNAL
    one simple editable/display control
```

The exact visual design is unimportant.

The purpose is to prove:

```text
Tk event
→ encoded application event
→ correct queue
→ idle scheduling
→ active registers
→ type dispatch
→ state mutation
→ GUI consequence
→ GUI updater
→ Tk widget change
```

## In-Memory State Only

Use only in-memory state.

Possible conceptual state:

```python
selected_day_id
civic_today

day_state = {
    ...
}

panel_state = {
    "panel-1": ...,
    "panel-2": ...,
}

panel_type = {
    "panel-1": TODO_PANEL,
    "panel-2": JOURNAL_PANEL,
}

panel_widgets = {
    "panel-1": ...,
    "panel-2": ...,
}

panel_event_queues = {
    "panel-1": ...,
    "panel-2": ...,
}
```

Do not treat these exact names or structures as mandatory. They illustrate the intended machine organization.

## Global Event Handling

Global interactions should follow the same architecture.

For example:

```text
user clicks Next Day
    ↓
Tk callback
    ↓
encode SELECT_NEXT_DAY
    ↓
append to global event queue
    ↓
request after_idle
```

Then later:

```text
global event processing stage
    ↓
SELECT_NEXT_DAY is interpreted
    ↓
selected-day state changes
    ↓
GUI consequences are recorded
    ↓
Top Area GUI updater applies them
```

Likewise:

```text
SECOND_ELAPSED
```

should enter through the global event queue.

## Important Boundaries

Do not let Tk callbacks call sideways into unrelated widgets.

Do not let panel semantic handlers directly perform Tk operations.

Do not let GUI updater functions reinterpret the original meaning of user actions.

Do not implement worker-thread logic.

Do not implement filesystem persistence.

Do not implement Fair Play.

Do not retrofit this into the full existing panel chassis yet.

The purpose is to build the smallest possible runnable experiment that makes the interaction model obvious.

## What the Experiment Should Prove

When finished, it should be possible to inspect the code and clearly see these stages:

```text
EVENT PRODUCTION
    ↓
EVENT ENCODING
    ↓
QUEUEING
    ↓
AFTER-IDLE WAKEUP
    ↓
APPLICATION EVENT PROCESSING
    ↓
ACTIVE-CONTEXT REGISTER LOADING
    ↓
TYPE-SPECIFIC STATE TRANSITION
    ↓
GUI CONSEQUENCE RECORDING
    ↓
GUI CONSEQUENCE PROCESSING
    ↓
TYPE-SPECIFIC TK UPDATE
```

The resulting code should be intentionally small and readable.

We are not trying to create a framework.

We are trying to experimentally establish the **interaction law of the Today program** before integrating it into the already-existing page/tab/row/pane/panel chassis.
