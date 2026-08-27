```
date: 2026-08-27
title: Context Handoff Machine Concept
chatgpt: https://chatgpt.com/c/6a9089b7-ea1c-83e8-9cb8-345519a9a424
```

# Today Stack Machine — Context Handoff

We are building **Today**, a Tkinter-based daily operational cockpit. The GUI chassis and interaction model already exist and have been successfully integrated. We are now designing a new **execution substrate** underneath them: a stack-machine system that can move computation explicitly between the program's machines/threads.

This is a substantial architectural change from an earlier queue-of-messages design.

The goal of this context is to design and build a **standalone spike** proving the stack-machine architecture before integrating it into Today.

Do **not** yet solve real M1 persistence, production panel behavior, or complex waits. Focus on the execution machine itself.

---

# 1. Current Program Shape

For now, Today has three machines:

```text
tk
mem
disk
```

These correspond roughly to three threads:

```text
1. Main / Tkinter thread
2. Memory-system thread
3. Disk thread
```

The intended ownership is:

```text
tk
    owns Tk widgets, GUI interaction, panel-local GUI state

mem
    owns authoritative application / M1 memory
    owns semantic memory-access behavior

disk
    owns filesystem I/O
```

The new architecture should allow a single logical operation to move among these machines without hidden callbacks or pending-request registries.

---

# 2. Core Idea: Computation Travels as a Stack

Processing is represented by **stacks of operation frames**.

Each stack frame says, among other things:

```text
which machine should execute this frame
what operation should be performed
operation-specific data
```

The top frame is the currently active operation.

The first thing any machine does with a stack is inspect the top frame.

If the frame belongs to another machine:

```text
look up that machine
put the entire stack onto that machine's in-queue
relinquish ownership completely
```

The machine does not call the other machine.

It ships the continuation of computation to it.

This is the central architectural rule.

---

# 3. Machine Registry

The spike should use a global machine registry approximately like:

```python
machines = {
    "tk": {...},
    "mem": {...},
    "disk": {...},
}
```

Each machine entry should contain approximately:

```python
{
    "in-queue": ...,
    "run-queue": ...,
    "handler": handler_tk / handler_mem / handler_disk,
    "thread-type": "system" or "worker",
    "entry-fn": start_tk / start_mem / start_disk,
}
```

Interpretation:

```text
in-queue
    thread-safe queue receiving stacks from other machines

run-queue
    local runnable stacks owned only by this machine
    probably a deque

handler
    machine-specific operation handler

thread-type
    descriptive metadata

entry-fn
    starts that machine's execution environment
```

The registry should make routing data-driven.

Avoid hardcoded functions such as:

```text
send_to_memory()
send_to_disk()
```

if generic machine lookup can perform the transfer.

---

# 4. Ownership Rule

A stack has exactly one owner at a time.

While a machine owns it, that machine may:

```text
inspect the stack
push frames
pop frames
modify the current active frame where the execution model allows it
append / update execution-local control state
place the stack onto its own local run queue
transfer it to another machine
```

Once the stack is placed on another machine's `in-queue`, the sender must not touch it again.

Queue transfer is an ownership transfer.

There should be no concurrent manipulation of one stack by multiple threads.

---

# 5. Startup

Current intended startup shape:

```text
1. Populate machines dict

2. Post one STARTUP stack to each machine.
   Each startup stack initially contains only a STARTUP frame
   addressed to that machine.

3. Start worker threads.

4. On the main thread, call start_tk() directly.

5. Tk runs until shutdown.

6. Join worker threads.

7. End process cleanly.
```

The spike may refine details, but preserve this overall idea unless implementation reveals a clear flaw.

---

# 6. Basic Worker Machine Loop

For non-Tk machines, the conceptual loop is approximately:

```text
loop(machine_name):

    receive stacks from in-queue

    attach them to local run-queue

    repeatedly reconcile runnable stacks

    transfer stacks elsewhere when top frame belongs elsewhere

    requeue locally when yielded or still runnable
```

Do not blindly implement this exact naive structure:

```python
stack = in_queue.get()

while run_queue:
    ...
```

because a perpetually yielding/requeued local stack could prevent the machine from checking newly arrived work.

The spike must develop a fair local scheduling policy.

A likely shape is:

```text
admit newly arrived inbound stacks
run one stack for one bounded reconciliation quantum
recheck inbound work
repeat
```

The exact scheduling algorithm should remain simple and explicit.

---

# 7. Tk Is Special Physically, Not Semantically

The Tk machine must obey the same logical execution model, but it cannot run a blocking worker loop because Tkinter needs control returned to `mainloop()`.

Therefore:

```text
mem/disk:
    blocking thread loop is fine

tk:
    Tk event loop periodically pumps its machine scheduler
```

Use something like:

```text
root.after(...)
root.after_idle(...)
```

to:

```text
admit incoming stacks
reconcile some bounded amount of Tk work
return control to Tk
```

The goal is:

> Same machine semantics, different physical pump.

Do not create a second incompatible execution model for Tk.

---

# 8. Reconciliation

Each machine should have a general reconciliation stage.

Conceptually:

```text
reconcile(stack, machine_name)
```

It examines the top frame and determines what happens next.

Important cases include:

## Empty Stack

```text
if stack is empty:
    discard it
```

## Frame Belongs to Another Machine

```text
if top.machine != current_machine:
    transfer entire stack to machines[top.machine]["in-queue"]
    relinquish ownership
```

This check should happen very early.

## Yield

If top frame represents `YIELD`:

```text
consume or otherwise resolve the yield frame
place the stack at the back of the local run queue
end this scheduling quantum
```

Yield should mean:

> Let another runnable stack have an opportunity.

It must not merely create a busy loop.

## Wait

A future `WAIT` mechanism is expected, but **do not solve waits in this spike unless necessary**.

Leave a clean conceptual opening for parked stacks.

## Multi-Step Operation

Some stack frames represent multi-step procedures.

Such a frame may contain something like:

```text
operations = [...]
ip = current instruction pointer
```

When that frame is active:

```text
take operation at current IP
advance IP
push that operation as a new top frame
resume execution from the new top
```

This is a major part of the design.

It allows explicit staged procedures without relying on hidden Python call-stack continuation.

## Primitive Machine Operation

If the top frame is a primitive operation for the current machine:

```text
dispatch to machine handler
perform operation
pop / replace / push frames as needed
continue reconciliation
```

---

# 9. The Stack Is the Continuation

This architecture replaces much of an earlier explicit request/response routing system.

The important idea is:

> When one machine needs another machine to do work, it pushes an operation for that machine onto the same stack.

Example:

```text
GET_NOTE    [mem]
```

Memory discovers it needs disk:

```text
GET_NOTE    [mem]
READ_FILE   [disk]   ← top
```

The stack transfers to disk.

Disk completes the read and removes/resolves its frame:

```text
GET_NOTE    [mem]    ← exposed again
```

The reconciler sees that the new top belongs to memory and transfers the stack back.

Memory resumes naturally.

The stack itself is therefore the continuation.

Avoid inventing callback registries or separate pending-request tables unless the experiment proves they are genuinely necessary.

---

# 10. Results

Determine a simple explicit way for lower frames to receive results from completed upper frames.

Possible mechanisms include:

```text
writing result into the suspended parent frame before popping child
pushing a result frame
using a designated result field
```

Do not overgeneralize.

The spike should experimentally discover the smallest mechanism that supports clean execution.

A typical flow should support:

```text
mem frame pushes disk read
disk frame produces data
disk frame completes
mem frame resumes with access to returned data
```

The result mechanism must remain understandable in a printed stack dump.

---

# 11. Machine-Specific Handlers

Each machine has a handler:

```text
handler_tk
handler_mem
handler_disk
```

These should deal only with operations belonging to their semantic/execution realm.

The generic reconciler should handle generic execution rules such as:

```text
machine routing
yield
multi-step expansion
empty stacks
future wait handling
```

Machine-specific handlers should not duplicate that infrastructure.

---

# 12. Tk Panel Dispatch

The existing Today interaction model already proved important panel concepts.

Preserve them.

In particular:

```text
panel identity
panel type
panel state
panel widgets
structural position
```

remain distinct.

When `handler_tk` receives a Tk operation, it may inspect the top frame for something like:

```text
panel: <panel-id>
```

If a panel is specified:

```text
look up panel_id
determine panel type / appropriate panel handler
dispatch the stack to that panel handler
```

Conceptually:

```python
def handler_tk(stack):
    frame = stack[-1]

    if "panel" in frame:
        panel_id = frame["panel"]
        panel_handler_for(panel_id)(stack)
        return

    handle_tk_system_operation(stack)
```

The exact code need not match this.

The important architectural idea is:

```text
machine routing:
    which thread executes this?

panel routing:
    which semantic GUI instrument handles it?
```

These are separate levels of dispatch.

---

# 13. Relationship to the Existing Interaction Model

The earlier `02_interaction-model.py` was built to solve these problems:

```text
Tk callbacks should not directly perform arbitrary application work

panel identity/type/state/widgets must remain separate

semantic panel events should be dispatched explicitly

GUI changes should be targeted rather than whole-window redraws

panel replacement should not rebuild unrelated GUI structure

execution stages should remain visible and understandable
```

Those principles remain valid.

What may become obsolete is the earlier transport machinery:

```text
global_event_queue
panel_event_queues
gui_consequence_queue
panel_reconfiguration_queue
```

The new stack machine may replace some or all of those queues as the execution substrate.

Do not discard the interaction principles merely because the scheduling mechanism changes.

Part of the spike's purpose is to reveal:

```text
what from 02 survives directly
what maps naturally onto stack operations
what old queue machinery is no longer necessary
```

Do not integrate with `03_combined-model.py` yet.

First prove the stack machine independently.

---

# 14. Suggested Spike Operations

Keep the initial operation vocabulary small.

Possible primitive operations:

```text
STARTUP
PRINT
YIELD
SHUTDOWN

TK_TEST
MEM_TEST
DISK_TEST
```

Add one or two multi-machine procedures such as:

```text
TEST_CROSS_MACHINE
    step on tk
    step on mem
    step on disk
    resume mem
    resume tk
```

Also test nested multi-step procedures.

The spike should visibly demonstrate a stack moving:

```text
tk → mem → disk → mem → tk
```

without hidden callback state.

---

# 15. Observability

Make the machine extremely easy to debug.

Provide readable tracing showing at least:

```text
stack identity
current machine
run-queue activity
top frame
frame machine
operation
push
pop
transfer
yield
completion
```

A developer should be able to watch a stack move among machines and understand exactly why.

Prefer clarity over compact output.

A stack dump should make execution understandable without needing a debugger.

---

# 16. Source Organization

Implement machine/thread responsibilities in separate modules.

A likely structure:

```text
stack_spike/
    main.py
    machine.py
    tk_machine.py
    mem_machine.py
    disk_machine.py
```

or a similarly clear procedural layout.

Do not create classes unless absolutely unavoidable because of a library requirement.

The project's coding style is procedural and machine-oriented.

Use dictionaries, functions, queues, explicit stages, and explicit state.

Avoid object-oriented framework construction.

---

# 17. Design Philosophy

This architecture follows a strong machine-programming philosophy:

> Execution should happen because an explicit machine stage says it happens.

Avoid hidden execution triggered by:

```text
callbacks calling arbitrary callbacks
constructors
observers
magical properties
implicit synchronization
background helpers whose timing is unclear
```

The stack should make control flow inspectable.

A stack moving to another machine should be the explicit representation of cross-thread control transfer.

---

# 18. Questions the Spike Should Answer

The experiment should give concrete answers to:

```text
What exactly is a stack?

What exactly is a frame?

How is a stack identified?

What does a primitive frame contain?

What does a multi-step frame contain?

How does IP advancement work?

How does a completed child operation return a result?

When is a frame popped?

When is a stack discarded?

How exactly does yield affect local scheduling?

How are inbound stacks admitted fairly?

How does Tk pump the same scheduler without blocking mainloop?

How does machine routing happen?

How does panel routing fit inside handler_tk?

How does shutdown propagate?

What invariants make stack ownership safe across threads?
```

Prefer answering these experimentally in code rather than designing a massive abstract framework first.

---

# 19. Explicitly Out of Scope

Do not yet implement:

```text
real M1 data
semantic GET_NOTE / SET_NOTE
disk persistence formats
Fair Play
general worker pools
OpenAI/network jobs
complex wait conditions
timeouts
priorities
cancellation framework
production Today integration
```

`WAIT` may be acknowledged structurally, but it does not need a finished design.

---

# 20. Success Criterion

The spike succeeds when a developer can run it and watch several independent stacks execute through:

```text
tk
mem
disk
```

with:

```text
explicit machine routing
exclusive stack ownership
local run queues
fair yielding
multi-step/IP expansion
cross-machine continuation
clean result return
Tk-safe scheduling
clean startup/shutdown
highly readable traces
```

and the resulting architecture feels simple enough that it can later replace the bespoke execution queues inside Today's existing interaction model.

The governing idea is:

> **The stack carries the computation.
> The top frame says what happens next.
> The frame's machine says where it happens.
> A machine either advances the computation locally or ships the whole continuation to the machine that owns the next operation.**
