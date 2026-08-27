```
date: 2026-08-26
title: Spike for Part II: Threads and Memory
```

# Today Three-Thread Messaging Spike Specification

## Purpose

Build a small executable spike that proves the basic asynchronous architecture for Today.

The spike should demonstrate three threads:

```text
1. Main / Tkinter thread
2. Memory system thread
3. Disk thread
```

The goal is not to implement production M1 persistence yet. The goal is to prove:

* strict thread ownership;
* queue-based communication;
* semantic requests from the GUI to the memory system;
* lazy loading from disk;
* authoritative RAM owned by the memory thread;
* explicit save operations;
* append-only transaction histories that carry their own continuation information;
* clean, understandable routing across threads.

Do not integrate this into the existing Today GUI yet. This is a standalone architecture spike.

---

# 1. Thread Responsibilities

## Main / Tkinter Thread

The Tkinter thread owns:

```text
Tk widgets
GUI interaction
GUI-local presentation state
```

It must never:

```text
directly access authoritative memory
directly read or write disk
block waiting for another thread
```

The GUI communicates with the Memory System using transactions placed onto a queue.

Responses from the Memory System must arrive asynchronously and be processed by the Tk event loop.

---

## Memory System Thread

The Memory System thread owns:

```text
authoritative in-memory application data
semantic data-access behavior
decisions about whether disk access is needed
coordination of disk requests
```

For the spike, the semantic data is simply a collection of Notes identified by:

```text
date
note_id
```

For example:

```text
date: 2026-08-26
note_id: orientation
```

The Memory System is the only thread allowed to directly read or mutate authoritative RAM.

The Memory System may send transactions to the Disk thread when disk access is required.

It must not perform filesystem I/O itself.

---

## Disk Thread

The Disk thread owns filesystem I/O.

It performs concrete operations such as:

```text
READ_FILE
WRITE_FILE
```

It does not understand Notes as an application concept.

It does not know about panels, dates as semantic application objects, or Today GUI behavior.

It receives concrete disk instructions, performs them, appends a response record to the transaction, and transfers the transaction back to the requested destination.

For the spike, one disk thread is sufficient.

---

# 2. Module Structure

Implement each thread in a separate module.

Suggested structure:

```text
04_memory-thread-spike/
    main.py
    memory_thread.py
    disk_thread.py
```

A small shared module may be added if genuinely useful, for example:

```text
messages.py
```

but do not create a generalized framework.

Keep the spike procedural, explicit, and easy to inspect.

---

# 3. Public Semantic Memory Operations

The GUI should interact with the Memory System using these operations:

```text
GET_NOTE
SET_NOTE
SAVE_NOTE
SAVE_DATE
SAVE_ALL
```

There is deliberately no public `LOAD_NOTE` operation.

Loading is an implementation concern of the Memory System.

---

# 4. GET_NOTE Semantics

A request should conceptually look like:

```text
GET_NOTE
    date
    note_id
```

When the Memory System receives it:

```text
if note already exists in authoritative RAM:
    return it

otherwise:
    determine where the Note would be stored on disk
    request a disk read
```

If the disk read succeeds:

```text
store the loaded value in authoritative RAM
return the Note to the original requester
```

If no persisted Note exists:

```text
create the semantic default value
store that default in authoritative RAM
return the default
```

The caller should not need to know whether the returned Note came from:

```text
RAM
disk
or default creation
```

It simply asked for the Note.

---

# 5. SET_NOTE Semantics

Conceptually:

```text
SET_NOTE
    date
    note_id
    value
```

The Memory System immediately updates authoritative RAM.

This does not automatically imply a disk write.

RAM and disk are separate realms.

Nothing automatically moves between them merely because one side changed.

For the spike, maintain enough state to know that a Note has changed since its last successful persistence.

---

# 6. Explicit Save Operations

Support:

```text
SAVE_NOTE(date, note_id)
SAVE_DATE(date)
SAVE_ALL()
```

`SAVE_NOTE` requests persistence of one Note.

`SAVE_DATE` requests persistence of all applicable Notes currently known in authoritative RAM for that date.

`SAVE_ALL` requests persistence of all applicable Notes currently known in authoritative RAM.

These are semantic operations handled by the Memory System.

The Memory System determines which concrete filesystem writes are required and delegates those writes to the Disk thread.

The Disk thread should not implement `SAVE_NOTE`, `SAVE_DATE`, or `SAVE_ALL`.

It only sees concrete write requests.

---

# 7. Transaction Model

Communication between machines should use a travelling transaction object.

A logical transaction has:

```text
series_id
history
```

`series_id` uniquely identifies the entire transaction journey.

`history` is an append-only list of records.

Each appended record gets its own unique:

```text
message_id
```

Earlier records must never be modified.

At any moment, exactly one machine/thread owns the transaction object.

Ownership transfers only by placing the transaction onto another machine's queue.

After a machine transfers the transaction, it must not touch that transaction again unless ownership later returns to it.

---

# 8. Record Structure

A record should contain only fields needed for that step.

Useful fields include:

```text
message_id
destination
address
operation
payload

response_queue
response_address
response_operation

response_to
continuation
```

Not every field must exist on every record.

Do not include a separate request/response directional flag.

A record is a response when:

```text
response_to
```

is present.

If `response_to` is absent, the record is simply a new request or delegated operation.

---

# 9. response_to

`response_to` identifies the exact earlier record that this record answers.

Example:

```text
history[4]
    operation: READ_FILE

history[5]
    operation: READ_FILE_RESULT
    response_to: 4
```

This provides explicit causal pairing.

---

# 10. Continuation Model

Do not store a complete continuation stack in each record.

The append-only transaction history itself contains the continuation structure.

When an operation delegates subordinate work and must later resume, the delegated record stores only a pointer to the earlier record representing the suspended operation.

For example:

```text
continuation: 2
```

If record 2 itself has:

```text
continuation: 0
```

then the effective continuation chain is:

```text
0 → 2 → current work
```

The full stack can therefore be reconstructed by following continuation pointers backward through immutable history records.

No mutable transaction-wide stack should exist.

---

# 11. Example GET_NOTE Journey

A transaction might look conceptually like this:

```text
[0]
operation: GET_NOTE
destination: memory
payload:
    date: 2026-08-26
    note_id: orientation
response_queue: tkinter_queue
response_operation: GET_NOTE_RESULT
```

The Memory System discovers that the Note is not in RAM.

It appends:

```text
[1]
operation: READ_FILE
destination: disk
payload:
    path: ...
response_queue: memory_queue
response_operation: READ_FILE_RESULT
continuation: 0
```

and transfers ownership to the Disk thread.

The Disk thread performs the read and appends:

```text
[2]
operation: READ_FILE_RESULT
destination: memory
response_to: 1
payload:
    found: true
    data: ...
continuation: 0
```

The Memory System receives the transaction.

By examining the continuation pointer, it knows that record 0 contains the suspended `GET_NOTE`.

It incorporates the disk result into authoritative RAM and appends:

```text
[3]
operation: GET_NOTE_RESULT
destination: tkinter
response_to: 0
payload:
    date: 2026-08-26
    note_id: orientation
    value: ...
```

Then it transfers the transaction to the Tkinter queue.

The entire transaction now doubles as a complete diagnostic trace.

---

# 12. GUI for the Spike

Keep the GUI intentionally simple.

A useful interface would contain:

```text
Date field
Note ID field
Editable Note text

[Get Note]
[Set Note]
[Save Note]
[Save Date]
[Save All]

Status / trace area
```

The GUI should make it easy to demonstrate:

```text
GET from RAM
GET causing disk access
GET causing default creation
SET changing authoritative RAM
SAVE_NOTE
SAVE_DATE
SAVE_ALL
```

The GUI must remain responsive while disk operations occur.

---

# 13. Artificial Disk Delay

Add a small configurable artificial delay to disk operations.

For example:

```text
1–2 seconds
```

This is deliberate.

The spike should visibly prove that:

```text
Tk remains responsive
Memory remains independently active
Disk work happens asynchronously
```

Do not use the delay to simulate Fair Play.

Fair Play is no longer part of Today's ordinary storage architecture.

The delay is only for demonstrating asynchronous behavior.

---

# 14. Authoritative RAM

For the spike, authoritative memory may be represented very simply, for example:

```python
notes_by_date = {
    date: {
        note_id: {
            "value": ...,
            "dirty": ...,
        }
    }
}
```

The exact representation is not important.

The important invariant is:

> Only the Memory System thread directly accesses this structure.

Other threads communicate with it exclusively through messages.

---

# 15. Disk Representation

Keep persistence deliberately simple.

For example:

```text
data/
    2026-08-26/
        orientation.txt
        scratch.txt
```

or a similarly obvious representation.

This is not intended to define the eventual M1 file organization.

Do not attempt to model real M1 transport documents yet.

The spike is proving thread architecture and semantic access flow, not production persistence topology.

---

# 16. Debugging / Trace Visibility

Because each transaction contains an append-only history, make that history easy to inspect.

At minimum, print or display records in a readable format showing:

```text
series_id
history index
message_id
destination
operation
response_to
continuation
payload summary
```

The trace should make it possible to read one transaction from beginning to end and understand exactly how it travelled through the system.

This debugging property is one of the main purposes of the message architecture.

---

# 17. Important Invariants

Preserve these rules strictly:

```text
Tkinter thread:
    touches Tk only
    never blocks for Memory or Disk

Memory thread:
    sole direct authority over authoritative RAM
    performs no filesystem I/O

Disk thread:
    sole direct filesystem I/O executor
    never mutates authoritative RAM

Transactions:
    append-only
    single-owner
    never modified after handoff

Communication:
    queue based
    explicit
    asynchronous across thread boundaries
```

A machine may:

```text
read existing transaction history
append a new record
transfer ownership
```

It may never modify an earlier record.

---

# 18. What This Spike Is NOT

Do not implement:

```text
real M1 transport format
Fair Play
multiple disk workers
general worker pools
general job coordinator
OpenAI/network workers
production Today panels
full persistence schemas
cross-program shared storage
automatic disk synchronization
```

Those are future concerns.

---

# Success Criterion

The spike succeeds when it visibly demonstrates that:

> **Tk speaks semantically to Memory; Memory owns authoritative state and intelligently coordinates access; Disk performs concrete I/O; and one append-only travelling transaction records the entire causal journey across those machines.**

The resulting code should be small enough that a developer can read the three modules and understand the complete threading and data-flow architecture without needing a diagram or framework documentation.
