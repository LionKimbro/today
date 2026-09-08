# Architecture reconstruction — 2026-09-07

This is an inspection and execution report, not a new project rulebook.
Candidate lessons at the end await review.

## What Today appears to be becoming

Today / Temple of Focus is a daily operational cockpit whose stable panel
entities can inhabit changing positions in a day-oriented workspace. Rich
tabs, rows, resizing, panel switching, whiteboard history, and persistence
belong to its trajectory. Its execution model makes the ownership of work
and state visible through machines and traveling continuations.

The current application is `src/today/`, wired by `main.py` and launched by
`python -m today` or the installed `today` entry point. It implements Stage 3.
The `src/parts/` programs are experimental lineage, not imported application
subsystems. In particular, `05` and `06` give Tk Mobile Stacks and simulate
Disk storage in dictionaries. They do not establish the current Tk/Core seam
or provide durable persistence to the current package.

The main evidence is the Stage 3 contract in
`docs/raw/320__stage-3-codex-msg.md`, the seven-stage sequence in `0310`, the
`0230` outline as refined by `0232`, the bounded sketches in `pseudo/`, and
the running code. Older documents describe different intermediate designs.

## Explicit system model

| Machine / mechanism | Owned state and work | Execution and transport |
| --- | --- | --- |
| Tk | Widgets, bindings, local presentation mechanics, command realization | Main thread; semantic events to Core; command queue drained on virtual wake event |
| Core | Current day, bounded active layout, visible panel snapshots, reducer events and effects | Worker thread; one blocking inbox for semantic events, Mobile Stacks, and shutdown |
| Mem | Canonical days and panel containers | Worker thread; blocking inbox for Mobile Stacks and shutdown |
| Disk, future | Durable storage and I/O | No runtime in the current application; earlier spikes simulate this jurisdiction |
| `machine.py` | Runtime registry, thread-local runtime selection, active stack dispatch and transfer | Shared mechanics, not a separate machine or application decision-maker |
| `mobile_stacks.py` | Frames and traveling registers accessed through the current runtime | Continuation transport; no interpreter or request registry |
| `main.py` | Queue construction, startup wiring, worker creation, final joins | Composition only |

There are three actual queues: Core inbox, Mem inbox, and Tk command inbox.
Tk events and Mem returns share Core's inbox. Core's reducer-event and effect
lists are local processing state, not additional inter-thread queues.

The structural grammar is `day -> tab -> position -> hosted panel identity`.
Currently Core seeds one tab and one position; Mem seeds a minimal day record
and one panel. The complete linked day graph in the reference sketches is
ahead of this implementation. Position and panel identities are already
separate, while changing their hosting relationship remains future work.

Core's operating rhythm is: receive one item; translate a stack return or
semantic message into ordinary events; reduce the local event list; dispatch
effects; block again. The reducer mutates module-owned state and returns
effect dictionaries. It is not currently a pure function with an explicit
state argument, but its stack and GUI work is separated into effect handling.

Startup sends this stack, with the rightmost frame on top:

```text
[ CORE / PANEL_RETURNED, MEM / GET_PANEL ]
registers: panel-id

MEM adds an independent panel snapshot
runtime drops GET_PANEL and queues the same stack to CORE
CORE copies the result into a PANEL_RECEIVED event
runtime drops PANEL_RETURNED and clears the empty stack
reducer installs the visible copy and emits RENDER_TODAY
Tk realizes that command
```

The continuation supplies the return address; no pending callback registry is
needed. Remaining frames can address the same machine. They still go through
the queue rather than recursively dispatching.

## Invariants and implementation comparison

1. **One jurisdiction per state fact.** Mem owns canonical containers, Core
   owns inhabited snapshots, and Tk owns widgets. Before repair, GET_PANEL
   exported Mem's actual dictionary; Core's later shallow copy only isolated
   today's scalar fields. Copies now occur when leaving Mem and when retaining
   a result from a stack that may continue elsewhere.
2. **One active stack per machine thread.** Creating or receiving another
   stack must not silently overwrite it. Both entry points now reject that.
   Runtime claims are still a wiring convention, not an enforced exclusive
   thread lease; the registry and module dictionaries remain Python-accessible.
3. **Queue publication transfers stack ownership.** The sender now clears its
   active slot before publishing. Receivers dispatch only frames addressed to
   them; this check now survives Python's optimized mode.
4. **Stage 3 runtime owns frame completion.** Handlers leave their frame on top;
   the runtime pops it after return and routes by the newly exposed frame.
   Earlier spikes let handlers pop/push their own frames. Mixing those
   contracts would pop the wrong frame. Dynamic handler-discovered routes need
   a deliberate decision before being imported into Stage 3.
5. **Reducer work begins after stack delivery ends.** Retained result data
   belongs to the queued event before the stack is routed or completed.
   Effects may then create another stack without replacing the inbound one.
6. **The GUI seam transports meaning as data.** Widgets stay out of messages;
   effects declare render operations. The injected send function is startup
   wiring. Its Tk adapter queues first, then calls `event_generate` from Core
   to wake Tk. This explicit wake mechanism is the seam's special cross-thread
   Tk call; widget updates execute in the Tk callback. The actual Windows
   Python/Tk installation passed the GUI checks; other platforms were not run.
7. **A panel must arrive before it can be renamed.** Previously the live button
   could generate an event before GET_PANEL returned, causing `KeyError` in
   Core. Tk now disables it until render and uses the rendered identity; Core
   also ignores premature or unknown-panel rename events.
8. **Runtime owns machine lifecycle.** Core previously used `g['running']`
   while its runtime always reported false. It now uses the runtime flag,
   changed by an effect. Core's sentinel now enters the same shutdown path as
   the window-close event, stopping Mem and allowing Tk to close.

These are small repairs to established boundaries. The two transports,
module-shaped machines, hyphenated records, implicit current-stack primitives,
simple dispatch dictionaries, and thread-local runtime lookup remain intact.
The tiny local event lists do not yet justify a queue abstraction or scheduler.

## Execution evidence

Before repair, real Tk startup, rename, and ordinary close succeeded. Direct
execution reproduced canonical-record aliasing, premature-rename failure,
false Core lifecycle reporting, and the missing downstream sentinel shutdown.

After repair, nine standard-library tests passed. They cover nested snapshot
isolation, retention across a continuing stack, same-machine routing, final
completion, prevention of active-stack replacement, publication ownership,
wrong-machine dispatch, premature rename, and both shutdown paths using live
Core/Mem worker threads.

Four fresh-process real Tk checks passed: normal load/rename/close; held Mem
delivery with a disabled-button invocation and premature semantic event;
repeated close while a load is outstanding; and Core sentinel shutdown after
rename. Each checks worker termination; Tk callback exceptions are captured.
These exercise widget properties and callbacks, not manual visual inspection.

The untouched `05_mobile-stacks.py --headless` check also completed its seven
journeys, exercising simulated Disk reads/writes, panel changes, and day
navigation. That validates historical evidence, not current persistence.

## Remaining uncertainties and priorities

1. **Commit meaning:** rename still changes only Core's active copy. Mem
   remains unchanged, deliberately preserving the Stage 2/3 demonstration.
   Decide when a panel edit becomes a canonical commit before adding EXPORT
   behavior. Reload would currently restore the canonical label.
2. **Failure and shutdown:** unknown operations or missing panels can terminate
   a worker without notifying Tk; exception exits can leave runtime state
   marked active. There is no supervision or result/error protocol. Normal
   close stops Core immediately; a late read return can remain in its inbox.
   SHUTDOWN_COMPLETE means Tk may close, while `main.py` still joins Mem.
   Add error delivery and drain/cancel semantics before introducing writes or
   Disk; do not interpret the current acknowledgement as a persistence barrier.
3. **Dynamic continuations:** resolve the automatic-pop versus handler-edited
   frame contract when the first real Mem-to-Disk operation needs it. There is
   no reason to introduce a generalized VM in anticipation.
4. **State boundary:** decide how canonical day layout and Core's active layout
   relate as hosting becomes real. Core and Mem independently determine today's
   date at startup, which also leaves a midnight boundary unresolved.
5. **Reducer interface:** explicit state-in/state-out could improve replay and
   isolation as interactions grow. The present global mutation is visible and
   small; changing every call now would obscure the more concrete repairs.
   In-process restart/reset is also not a supported lifecycle yet.

The natural stopping point is a working Stage 3 with clearer ownership and
repeatable checks. The next larger moves require product or continuation
semantics rather than cleanup preferences.

## Mistakes, course corrections, and candidate lessons

The normal happy-path run did not expose the startup race. Holding Mem delivery
and exercising the early event was necessary; treating a successful launch as
proof of lifecycle correctness would have missed it. Likewise, a top-level
copy looked adequate for the current label but did not establish nested
ownership or retention across another continuation.

A Windows `rg` command using wildcard filenames failed; filtering known files
or using `rg` glob options avoids that shell mismatch. A documentation patch
used an incorrect context line and was rejected atomically; the actual text
was reread before reapplying. Neither required an architectural workaround.

Candidate lessons for review, not permanent rules:

- Establish which executable and stage a document describes before borrowing
  mechanisms from the richer prototypes.
- Test ownership by mutating nested traveling data and by forwarding a stack
  after delivery; check more than final UI text.
- Preserve the distinction between runtime-owned frame completion and the
  older handler-edited continuation model.
- Use a held machine response to exercise startup and shutdown ordering;
  deterministic queue ordering reveals more than arbitrary sleeps.
- Keep canonical edits, active edits, and persistence acknowledgements explicit
  when extending panel behavior.
- Run the real Tk seam alongside machine-only tests; both reveal different
  classes of failure.
