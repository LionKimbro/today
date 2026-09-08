```
date: 2026-09-07
url: https://chatgpt.com/c/6a9cf89b-4860-83e8-8cd0-634dcd19a115
```

Here’s the **Stage 3 machine contract** I’d hand Codex next.

> # Stage 3 — Machine Runtime and Mobile Stack Contract
>
> We are adding the infrastructure needed for Mobile Stacks and a Mem machine.
>
> This stage should **not** add panel hosting semantics, Disk, full Whiteboard behavior, or the rich `03` layout.
>
> The goal is to establish a small, inspectable machine runtime that Core and Mem can both use.

## `machine.py`

`machine.py` should define the common runtime mechanics for a machine.

A machine conceptually owns:

```text
name
inbox queue
current_stack
operation dispatch table / handlers
lifecycle state
```

Each machine has one blocking inbox.

`None` sent to the inbox means:

```text
shut down this machine
```

The machine thread should block on:

```text
inbox.get()
```

when idle.

Do not busy-poll.

---

## Machine receive behavior

A machine may receive ordinary machine-specific messages or Mobile Stacks, depending on the machine.

For a Mobile Stack:

```text
receive stack

set:
    machine.current_stack = stack

inspect top frame

verify:
    top frame targets this machine

dispatch:
    top frame entry / operation
        -> corresponding machine handler
```

The machine works on only one current stack at a time.

When the handler has finished with that entry:

```text
drop_frame()
```

Then:

```text
if another frame remains:
    route stack to machine named by new top frame

else:
    stack is complete/dead
```

After the stack has been forwarded or completed:

```text
machine.current_stack = None
```

`current_stack` is temporary execution state owned by the machine runtime.

---

# Mobile Stack structure

A Mobile Stack has two conceptually distinct parts:

```text
frames
registers
```

Frames carry control.

Registers carry traveling context.

A frame contains at minimum:

```text
machine
entry
```

For example:

```text
CORE / PANEL_RETURNED
MEM  / GET_PANEL
```

Registers are a key/value store associated with the stack.

Example:

```text
panel-id = "panel-1"
panel = {...}
```

Temporary local computation should remain ordinary local variables.

Do not turn registers into a replacement for normal Python locals.

---

# Required stack primitives

Implement only the basic primitives currently needed:

```text
push_frame(machine-name, machine-entry)

drop_frame()

set_register(key, value)

get_register(key)
```

Keep these mechanisms small and explicit.

Do not build a virtual machine, bytecode layer, instruction pointer system, builder language, or generalized interpreter.

Mobile Stacks are continuation transport, not a programming language.

---

# Routing

A stack is routed according to the machine named by its current top frame.

Conceptually:

```text
route_stack(stack):

    top = inspect top frame

    destination = top.machine

    destination_machine.inbox.put(stack)
```

A stack may route back to the same machine.

That is legal.

Machine identity and continuation identity are separate concepts.

---

# Core machine special behavior

The Core machine already exists and receives plain semantic Tk events.

Stage 3 should use the **same Core inbox** for:

```text
plain Tk semantic events
returned Mobile Stacks
None for shutdown
```

Conceptually:

```text
item = core_inbox.get()

if item is None:
    shut down

if item is Tk semantic event:
    enqueue that ordinary Reducer event

if item is Mobile Stack:
    inspect top frame

    translate:
        top frame entry + relevant stack registers
            -> ordinary Reducer event

    enqueue that Reducer event

    drop_frame()

    if stack has another frame:
        route stack
    else:
        stack is complete
```

The Reducer Core itself should **not know about Mobile Stacks**.

The Core machine runtime knows about stacks.

The Reducer knows only:

```text
state
events
effects
```

Preserve:

```text
state + event -> next_state + effects
```

---

# Core processing rhythm

Avoid the ambiguous idea of waiting until “all events” have arrived.

Prefer this rhythm:

```text
block waiting for one Core inbox item

translate that item into zero or more Reducer events

process the Reducer event queue until empty

dispatch all emitted effects

return to blocking on the Core inbox
```

Conceptually:

```text
sleep
receive
translate
reduce until quiet
dispatch effects
sleep
```

Core is quiescent when:

```text
external Core inbox has no pending item being processed
and
internal Reducer event queue is empty
```

---

# Core effect processing

Reducer effects may currently do two kinds of outward work:

```text
send declarative semantic commands to Tk
create and route Mobile Stacks to another machine
```

For a Mobile Stack effect, Core’s effect-processing layer should:

```text
create stack
set required registers
push required continuation frames
route stack according to its top frame
```

Do not create Mobile Stacks inside the reducer itself.

The reducer emits an effect describing what should happen.

The Core machine effect layer realizes that effect.

---

# `mem.py`

Add a Mem machine running on its own thread.

Mem owns a small canonical in-memory store.

For Stage 3, keep it intentionally tiny:

```text
days
panels
```

It does not yet need to own the full future Today world.

At minimum, include:

```text
panel-1
```

with a small record such as:

```text
{
    "id": "panel-1",
    "label": "panel-1"
}
```

---

# `GET_PANEL`

Implement one real Mem operation:

```text
GET_PANEL
```

A representative journey should be:

```text
Core decides it needs panel-1

Core creates Mobile Stack

stack registers:
    panel-id = "panel-1"

stack frames:
    MEM / GET_PANEL
    CORE / PANEL_RETURNED
```

When Mem receives the stack:

```text
read panel-id register

look up panel in Mem store

set panel register to the panel record

drop MEM / GET_PANEL frame

route stack according to newly exposed top frame
```

The stack then returns to Core.

Core receives:

```text
CORE / PANEL_RETURNED
```

Core translates:

```text
entry + registers
    -> ordinary Reducer event
```

For example conceptually:

```text
PANEL_RECEIVED
    panel-id
    panel record
```

Then Core drops its frame and completes the stack if no frames remain.

---

# Important architectural boundary

Preserve these two independent communication systems:

```text
Tk <-> Core
    plain semantic messages
    queues
    immediate Tk wakeup
    NO Mobile Stacks
```

and:

```text
Core <-> Mem
    Mobile Stacks
    continuation + traveling context
```

Do not unify these into one transport abstraction.

They exist for different reasons.

---

# Module shape

Stage 3 should now have approximately:

```text
main.py
tk.py
core.py
machine.py
mobile_stacks.py
mem.py
```

`main.py` should remain thin and mostly wire together:

```text
queues
machine runtimes
threads
startup
shutdown
```

Do not move application semantics into `main.py`.

---

# Do not add yet

Do not add:

```text
Disk
panel types
panel chooser
CREATE_PANEL semantics
real panel hosting semantics
Whiteboard snapshot history
save scheduling
multiple positions
multiple tabs
03 layout migration
generalized machine framework
generalized transport framework
```

If future concerns become visible, preserve a clean seam and mention them rather than implementing them.

---

# Stage 3 success condition

Stage 3 is complete when this journey visibly works:

```text
Core
    needs panel-1

Core -> Mobile Stack -> Mem

Mem
    handles GET_PANEL
    puts panel record in registers

Mem -> same Mobile Stack -> Core

Core
    translates PANEL_RETURNED + registers
        -> ordinary Reducer event

Reducer
    processes the event

Core
    may issue a declarative Tk update
```

And the logs should make the journey easy to inspect.

The architectural proof is:

```text
Tk <====> Core
    semantic messaging

Core <==== Mobile Stacks ====> Mem
    continuation transport
```

Keep the implementation small enough that both arteries are obvious.
