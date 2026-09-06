# Recommended Guidelines for the Merge of `03_combined_model.py` and `05_mobile-stacks.py`

## Purpose

The goal of this merge is to combine the mature Today application structure from `03_combined_model.py` with the simplified Mobile Stacks nervous system developed in `05_mobile-stacks.py`.

The merge should not be treated as an attempt to reconcile two equal architectures.

Instead:

```text
03_combined_model.py
    provides the body

05_mobile-stacks.py
    provides the nervous system
```

The combined model already contains useful Today behavior, presentation, panel logic, day navigation, and application structure.

The Mobile Stacks experiment has developed the preferred model for:

* thread ownership
* machine ownership
* cross-thread work
* continuation
* traveling context
* routing
* machine wakeup

The goal is therefore to preserve the useful application behavior of `03`, while replacing its cross-machine coordination model with the simpler and more explicit architecture proven in `05`.

Do not re-generalize the Mobile Stacks runtime during the merge.

Do not resurrect machinery that was deliberately removed during the transition from experiment 04 to experiment 05.

---

# 1. Preserve the Core Machine Boundary

Adopt this as a fundamental invariant:

> **One physical thread hosts one Mobile Stacks machine.**

Conceptually:

```text
Tk thread
    = Tk machine

Mem thread
    = Mem machine

Disk thread
    = Disk machine
```

The current thread name is the machine identity.

A function running on a thread should not normally need to be told which machine it belongs to.

Avoid unnecessary parameters such as:

```python
run_one_stack(machine_name)
```

when the machine is already determined by:

```python
current_thread().name
```

Machine identity is context, not caller variation.

---

# 2. Internal Sub-Machines Do Not Need Their Own Threads

The Tk machine may internally contain multiple regions of behavior.

For example:

```text
Tk machine
    general Tk behavior
    position behavior
    TODO-panel behavior
    journal-panel behavior
    other future panel behavior
```

These do not need to become separate Mobile Stacks machines.

The thread-level machine is the jurisdiction boundary.

Inside the machine, ordinary Python may use registers and local dispatch to identify the current subject.

For example:

```text
position-id
locate-panel-id
panel-record
```

may tell Tk which position or panel the current operation concerns.

The intended hierarchy is:

```text
thread identity
    determines machine ownership

top Mobile Stack frame
    determines operation

registers
    identify the current subject and traveling context

ordinary Python
    performs the machine's internal work
```

Do not promote every conceptual component into the Mobile Stacks routing layer.

---

# 3. Only the Mobile Stack Crosses Machine Boundaries

This is one of the most important invariants in the system.

> **Tk-owned, Mem-owned, and Disk-owned data structures must remain separate.**

A machine must never directly read or mutate another machine's owned dictionaries.

In particular:

```text
Tk must not directly access Mem-owned records.

Mem must not directly access Tk-owned records.

Disk must not directly manipulate either Tk or Mem application structures.
```

The Mobile Stack is the ownership airlock between machines.

The only object that changes thread ownership is the Mobile Stack itself:

```text
Mobile Stack
    frames
    registers
```

A stack belongs to exactly one machine/thread at any moment.

Cross-machine data movement should follow this form:

```text
machine-owned data
    ↓ deepcopy
Mobile Stack register

Mobile Stack changes machine ownership

Mobile Stack register
    ↓ deepcopy
receiving machine-owned data
```

Never cross the streams between machine-owned dictionaries.

---

# 4. Preserve Explicit Deepcopy Boundaries

When data leaves one machine's owned structures and enters a Mobile Stack, copy it.

When data leaves a Mobile Stack and becomes part of another machine's owned structures, copy it again.

Conceptually:

```text
MEM

memory["panels"][panel_id]
        |
        | deepcopy
        v

stack["registers"]["panel-record"]

        |
        | stack travels
        v

TK

        |
        | deepcopy
        v

panel_records[panel_id]
```

The Mem record, Mobile Stack record, and Tk record may share the same schema, but they must not be the same Python object.

The clarity of ownership is more important than avoiding small copies.

---

# 5. Keep Portable Panel Records Clean

Panel records should contain only semantic, transportable information.

Use a record shaped approximately like:

```python
panel_records = {
    "<panel-id>": {
        "id": "<panel-id>",
        "type": "<panel-type>",
        "day": "<day-id>",
        "data": {...},
    },
}
```

Everything in a panel record should be safe to transport directly through a Mobile Stack.

Do not put Tk-only information inside a panel record.

In particular, do not put:

```text
widget references
position references
mounted state
Tk caches
presentation annotations
```

inside the portable panel record.

A useful rule is:

> **If it is inside a panel record, it is dockable.**

If Tk needs additional information about a panel, store that information externally.

---

# 6. Keep Presentation Relationships External

Tk may need fast lookup between visible panels and positions.

Represent those relationships explicitly:

```python
panel_to_position = {}
position_to_panel = {}
```

Maintain them together.

Conceptually:

```python
position_to_panel["position-1"] = "panel-123"
panel_to_position["panel-123"] = "position-1"
```

Do not add presentation-only `"position"` fields to portable panel records.

If future Tk behavior needs additional annotation, prefer another external structure rather than contaminating the transport-clean record.

---

# 7. Use Position Records for Tk Presentation Structure

Positions are persistent Tk presentation locations.

Their records may contain both permanent host widgets and temporary widgets associated with the currently mounted panel.

Conceptually:

```python
position_records = {
    "position-1": {
        "id": "position-1",

        "host-widgets": {
            "labelframe": ...,
            "label": ...,
        },

        "panel-widgets": {
            ...
        },
    },
}
```

Distinguish the two lifetimes clearly.

```text
host-widgets
    exist for the lifetime of the position

panel-widgets
    exist only while a particular panel is mounted there
```

When a panel changes, destroy and rebuild the panel-specific widgets while preserving the host.

Avoid recreating a `panel_widgets` registry unless a concrete need for it remains after the merge.

Widgets belong to the currently active presentation position, not permanently to semantic panel records.

---

# 8. Establish a Standard Register Vocabulary

Use consistent Mobile Stack register names for common semantic operations.

For panel resolution:

```text
locate-panel-id
```

means:

> Find this panel.

For carrying the resolved panel:

```text
panel-record
```

means:

> This stack currently carries the portable panel record.

A typical lifecycle is:

```text
REQUEST

locate-panel-id = "panel-123"
panel-record = None
```

Mem resolves the panel.

```text
REPLY

locate-panel-id = None
panel-record = {
    "id": "panel-123",
    "type": ...,
    "day": ...,
    "data": {...},
}
```

Once the record has been resolved, clear `locate-panel-id`.

The locator has completed its purpose.

The record itself now contains its identity.

Do not unnecessarily explode coherent records into registers such as:

```text
panel-id
panel-type
panel-day
panel-data
```

Keep the record intact.

---

# 9. Frames Are Control; Registers Are Traveling Context

Preserve the central Mobile Stacks distinction:

> **Frames are control only. Registers are data/context.**

A frame should remain approximately:

```python
{
    "machine": "mem",
    "op": "LOAD_PANEL",
}
```

Frames should answer:

```text
Which machine owns the next work?

Which Python operation should execute?
```

Registers answer:

```text
What is this work about?

What information must survive while the work travels?
```

Do not return to parameterized instruction dictionaries or generalized instruction objects.

---

# 10. Preserve `push()` and `drop()` as the Continuation Vocabulary

The Mobile Stack control vocabulary should remain extremely small.

The important operations are:

```python
push(machine, op)
drop()
```

Handlers should directly edit the live stack.

Do not introduce handler return protocols such as:

```text
DONE
DROP
SUSPEND
REPLACE
YIELD
```

and do not recreate:

```text
SERIAL
instruction pointers
stage machines
replacement builders
child-result protocols
```

Ordinary Python should perform the work.

The stack should only remember what remains to be done.

---

# 11. Keep Continuation Dynamic

Do not convert the system into a fixed pipeline such as:

```text
Tk → Mem → Disk → Mem → Tk
```

Different operations may have different routes.

Examples:

```text
Tk → Mem → Tk

Tk → Mem → Disk → Tk

Tk → Disk → Tk

Tk → Mem
        ↓ cache miss
      Disk → Mem → Tk
```

A handler should be free to discover additional work while it executes.

The resulting top frame determines where the stack goes next.

The intended rule is:

> **A task is a traveling stack. Each machine does the part it understands, edits the remaining work, and the resulting top frame determines where the task goes next.**

---

# 12. Do Not Treat Mobile Stacks as Message Passing

The conceptual model should remain distinct from ordinary actor-style message passing.

Avoid thinking:

```text
Tk sends a message to Mem.

Mem sends a message to Disk.

Disk replies to Mem.

Mem replies to Tk.
```

Instead think:

```text
There is one piece of work.

It is currently owned by Tk.

Now it is owned by Mem.

Now it is owned by Disk.

Now it is owned by Tk again.
```

The registers preserve the situation.

The frames preserve continuation.

The Mobile Stack itself travels.

This is the defining architectural idea.

---

# 13. Collapse Runtime State Into Machine State

There should not be a separate parallel `runtime` registry whose only purpose is to hold the current stack.

The current stack is machine state.

Each machine record should contain its own:

```text
in-queue
run-queue
handler
worker state
stack
```

Conceptually:

```python
machines = {
    "tk": {
        "in-queue": Queue(),
        "run-queue": deque(),
        "handler": ...,
        "worker": False,
        "stack": None,
    },

    "mem": {
        ...
    },

    "disk": {
        ...
    },
}
```

Then:

```python
machines["mem"]["stack"]
```

means:

> Mem's currently executing Mobile Stack.

Keep this visible and inspectable.

Do not hide the current stack inside `threading.local()` unless a concrete later requirement demands it.

---

# 14. Make Stack Submission Sufficient

The runtime should own both routing and wakeup.

Callers should only need:

```python
submit_stack()
```

They should not need:

```python
submit_stack()
schedule_tk_pump()
```

or any other destination-specific wakeup ceremony.

The runtime contract should be:

> **Once a stack is submitted, its destination has received it and has been given whatever wakeup is necessary to process it.**

---

# 15. Preserve Demand-Driven Machine Wakeup

The runtime should sleep when there is no work.

Worker machines such as Mem and Disk naturally block on their inbound queues.

Adding work wakes them.

Tk should follow the same conceptual model.

Cross-thread work targeting Tk should:

```text
enqueue stack into Tk inbound queue
generate Tk virtual wake event
```

The virtual event means approximately:

> Wake up and read your mail.

Tk should not continuously poll every 25 ms for work.

Local Tk → Tk work may schedule a local Tk service pass through the event loop.

Cross-thread Tk delivery must use the dedicated queue-plus-wakeup path.

No arbitrary code should directly enqueue into Tk's inbound queue without also ensuring the corresponding wakeup.

---

# 16. Preserve Day Navigation as a Real Integration Case

The merged program should retain:

```text
previous day
today
next day
```

These controls are not incidental demo decoration.

They exercise an important real Today flow:

```text
Tk interaction
    ↓
request data
    ↓
Mem
    ↓
possibly Disk
    ↓
Mem
    ↓
Tk redraw
```

The merge should verify that day changes move naturally through Mobile Stacks and return with the data necessary for Tk to redraw.

---

# 17. Preserve Widget Redraw as a First-Class Proof

Rendering and redraw are important parts of the Mobile Stacks integration.

The merge should demonstrate:

```text
semantic state changes elsewhere

Mobile Stack returns to Tk

Tk receives a portable semantic snapshot

Tk updates its local records

Tk redraws or remounts the appropriate widgets
```

Do not bypass this by letting Mem manipulate Tk structures directly.

Tk owns presentation decisions.

Mem owns authoritative semantic state.

Disk owns persistence.

---

# 18. Keep Tk Live State and Mem Semantic State Distinct

After a day has been rendered, Tk owns the live presentation.

Tk may know things Mem does not need to know, such as:

```text
which widgets currently exist
which position currently hosts which visible panel
what is mounted
what has focus
what presentation decision the user just made
```

When Tk makes a user-facing decision, it should communicate the resulting semantic state to Mem through a Mobile Stack.

Avoid vague requests that force Mem to reconstruct a Tk presentation decision.

Prefer:

```text
SET_TODO_STATE
SET_POSITION_PANEL
```

over ambiguous verbs such as:

```text
TOGGLE_TODO
REPLACE_PANEL
```

when Tk already knows the desired result.

---

# 19. Prefer Exactness Over Generic Merge Abstractions

Do not build a large generic adapter layer merely to make `03` and `05` appear compatible.

Avoid abstractions such as:

```text
generic context objects
generic machine adapters
generic message envelopes
generic dispatch wrappers
compatibility managers
translation layers that exist only to preserve old machinery
```

Instead, identify the actual application flow and wire it directly into Mobile Stacks.

The merged system should feel like the exact machine Today needs.

---

# 20. Preserve Lion-Style Function Arguments

Function calls should express real caller decisions.

Do not pass stable machine context through function calls.

Prefer:

```python
run_one_stack()
admit_inbound_stacks()
active_stack()
render_current_panel()
```

when the current thread, machine, stack, or current record already establishes the context.

Use arguments when the caller genuinely chooses something.

Ordinary functions should normally have:

```text
0 arguments
1 argument
2 arguments
```

with optional flags only for real behavior variants.

Avoid passing:

```text
machine_name
machines
widgets
memory
runtime
current_stack
context
```

merely because a helper needs access to them.

---

# 21. Preserve the Existing Naming Philosophy

Use function names to expose program shape.

Use short primitive names for pervasive vocabulary such as:

```python
push()
drop()
log()
```

Use ordinary `verb_object` names for reusable actions.

Use long descriptive names for one-off procedural steps.

Callbacks should use long `handle_...` names.

Predicates should read as questions using forms such as:

```text
is_
has_
should_
may_
```

Do not let the merge introduce vague names such as:

```text
process()
handle()
do_work()
manage()
execute_step()
```

unless the meaning is genuinely obvious and reusable.

---

# 22. Keep Global State Visible and Thematic

Use global structures as visible control panels rather than hiding shared context behind manager objects.

Examples may include:

```python
g = {...}

machines = {...}

memory = {...}

disk_store = {...}

panel_records = {...}

position_records = {...}

panel_to_position = {...}

position_to_panel = {...}

widgets = {...}
```

Each structure should have a clear ownership and purpose.

Do not dump everything into `g`.

Do not create Manager/Controller classes merely to wrap these structures.

---

# 23. Preserve Quiet Module Import

Operational startup should remain explicit.

Use:

```python
def main():
    ...
```

and:

```python
if __name__ == "__main__":
    main()
```

Do not introduce loose operational calls at module scope.

---

# 24. Merge Behavior Before Polishing Architecture Further

The purpose of the grand unification is to determine whether the simplified Mobile Stacks architecture works as the actual nervous system of Today.

Therefore:

1. Preserve the important application behavior from `03`.
2. Replace its machine/thread coordination with the `05` model.
3. Make one complete integrated program work.
4. Run it.
5. Inspect the resulting architecture.
6. Only then simplify further where actual redundancy becomes visible.

Do not preemptively redesign Mobile Stacks for hypothetical future distributed systems.

Do not introduce speculative abstractions for future panel types or future machines unless the merged application already requires them.

---

# 25. Prefer `05` When the Two Models Conflict About Nervous-System Architecture

Where `03_combined_model.py` and `05_mobile-stacks.py` disagree about:

```text
thread routing
machine ownership
cross-thread communication
continuation
current-stack handling
machine wakeup
traveling work state
```

prefer the architectural model from `05`.

Where `03` contains richer or more mature:

```text
Today presentation
panel behavior
day behavior
widget layout
application semantics
user interaction
```

prefer and preserve the application behavior from `03`.

A useful merge heuristic is:

```text
application/body question
    → look first to 03

nervous-system/routing question
    → look first to 05
```

---

# 26. Do Not Resurrect Experiment 04

The following concepts were deliberately abandoned and should not reappear merely because they make the merge mechanically easier:

```text
SERIAL
serial instruction pointers
BUILDING / EXECUTING phases
nested serial construction
begin_serial / end_serial
replacement builders
begin_replacement / end_replacement
SUSPENDED
stage machines
child-result
generic instruction dictionaries
generalized instruction compilation
handler return protocols
generic VM-style call/return simulation
```

If the merge seems to require one of these, first ask whether ordinary Python plus:

```text
registers
frames
push()
drop()
```

can express the same application flow more directly.

---

# 27. Preserve Inspectability

After the merge, it should remain easy to inspect:

```text
What machine am I on?

What stack is it currently running?

What is the top frame?

What registers are traveling?

What work is waiting in each machine queue?

What panel records does Tk currently own?

What panel records does Mem currently own?

What panel is mounted in each position?
```

The architecture should remain visible enough that a developer can mentally animate it.

Avoid hidden control paths.

---

# 28. Desired Final Character

The merged program should feel like:

```text
Today application
    with a small explicit nervous system
```

not:

```text
a runtime framework
    containing a Today application
```

The Mobile Stacks machinery should remain subordinate to the application.

Its job is only to:

> **Get ordinary Python work onto the correct machine/thread, carry the situation with it, and remember enough continuation for the work to proceed afterward.**

The final architecture should preserve the central formulation:

> **The stack remembers control.**

> **The registers remember the situation.**

> **Python does the work.**

And the merged system should retain the overall quality target:

> **Motorcycle, not tank.**
