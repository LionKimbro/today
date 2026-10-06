# Architecture review — 2026-10-06

This is an inspection and execution report, not a new project rulebook.
It updates the 2026-09-07 reconstruction to describe the current application.
Candidate lessons at the end await review.

## What Today is becoming

Today / Temple of Focus is a daily operational cockpit. Stable, day-owned
panel entities inhabit changing positions in a workspace of tabs and rows.
The current application supports day navigation, canonical hosting, tab and
row changes, resizing, scrolling, text panels, Whiteboard history, To-Do,
TkMarkup, Journal, Orientation, and image panels with durable storage.

The executable is `src/today/`, wired by `main.py` and launched by
`python -m today` or the installed `today` entry point. It has advanced beyond
the Stage 3 skeleton described in the original review. `src/parts/` remains
experimental lineage, not imported application subsystems. Historical stage
documents and exported architecture diagrams describe intermediate designs;
the current code and bounded sketches in `pseudo/` are the immediate evidence
for this review.

## Ownership and execution

| Machine / mechanism | Owned state and work | Execution and transport |
| --- | --- | --- |
| Tk | Widgets, bindings, presentation modes, native file dialog/drop reception, Tk image objects | Main thread; semantic events to Core; command inbox drained on a virtual wake event |
| Core | Active day/layout and panel snapshots, working edits, reducer events/effects, image request tokens | Permanent worker; inbox for semantic events, Mobile Stacks, and shutdown |
| Mem | Canonical days, tabs, rows, positions, panels, revisions, pending day writes | Permanent worker; Mobile Stack inbox with a timeout for due writes |
| Disk | Durable day bundles and image asset reads/writes | Permanent worker; Mobile Stack inbox |
| Image instances | Clipboard/source acquisition, validation, decoding, fitted preview preparation | Router-created workers; one inbox per instance; Disk round trips through Mobile Stacks |
| `machine.py` | Runtime/kind registries, thread-local runtime selection, routing, lifecycle, fatal latch, reaping | Shared mechanics, not another worker or application decision-maker |
| `mobile_stacks.py` | Traveling frames and registers accessed through the current runtime | Continuation transport, not a generalized interpreter |
| `main.py` | Root initialization, queues, startup wiring, tracked worker startup, final joins | Main-thread composition and shutdown orchestration |

There are four permanent queues: Core, Mem, Disk, and Core-to-Tk commands.
Each dynamic instance adds its own inbox. Tk events and stack returns share
Core's inbox. Core's reducer-event and effect lists are local processing state,
not additional inter-thread queues.

Mem owns the day graph. Tabs own ordered row identities; rows define one,
two, or three logical columns; derived position identities carry panel hosting
references. Panels remain independent of positions. Unhosting preserves a
panel; deleting removes its record and ordinary hosting references. A panel
may be hosted in different tabs of its day, but at most once in a given tab.
Orientation occupies a separate day-owned top position.

Core holds copied active layout and panel records, not aliases to Mem's
canonical containers. Working facts such as dirty state, edit/save generations,
image request tokens, and errors do not enter canonical records. Panel changes
use revisioned `UPDATE_PANEL`; Mem accepts a matching base revision or returns
a conflict. Core preserves newer edits across an older save's acceptance.
A Mem acceptance establishes an in-memory commit, not completion of a Disk write.

Core receives one inbox item, translates it into ordinary reducer events,
reduces its local event list, dispatches effects, and blocks again. The reducer
mutates module-owned state; it is not a pure state-in/state-out function.
Effects isolate stack creation and declarative Tk commands from reduction.

## Routing, continuations, and dynamic machines

A Mobile Stack carries registers and bottom-first frames. The top frame names
the next machine and handler. Queue publication transfers ownership: the
sender clears its active stack slot before making the stack available. A
receiver checks the destination and rejects replacement of an active stack.
Handlers leave their current frame in place; runtime removes it after return.

Day loading uses a continuation through Disk and Mem:

```text
Core -> Disk / LOAD_DAY -> Mem / DAY_BUNDLE_RETURNED
     -> Core / DAY_LAYOUT_RETURNED -> reducer events -> Tk commands
```

The continuation supplies return addresses; no callback registry is needed.
Retained results are copied into reducer events before the stack completes or
continues. A same-machine continuation still travels through its queue.

A creation destination is data in a frame:

```python
{"machine": {"new": "IMAGE"}, "entry": "IMPORT_IMAGE"}
```

The router resolves the registered kind, creates an instance with a unique
`IMAGE-<uuid>` address, installs its runtime and inbox, starts its thread, and
replaces the frame's destination with that actual address before publication.
Registry membership, creation, routing publication, and shutdown transitions
use `machines_lock`; new instances cannot slip past the shutdown gate.

Instances are not automatically disposable after one handler invocation.
They can accept later deliveries or send their stack elsewhere and wait for
its return. `continue_with_frames` declares frames that runtime appends after
removing the current frame; handlers do not manually compete with runtime's
automatic pop. A return frame uses the instance's actual runtime address.

The handler chooses retirement through `request_machine_retirement()`.
Retirement permits the current handler's final stack handoff, then ends its
worker loop. Routing to a stopping, exited, reaped, or missing address is an
error during ordinary operation. During application shutdown, late returns
to such destinations are discarded instead.

## Lifecycle, reaping, and shutdown

Permanent and dynamic workers share tracked startup and the `run_worker`
exception boundary. Runtime lifecycle records distinguish `starting`,
`running`, `stopping`, `exited`, and `reaped`; the compatible `running` flag
controls existing worker loops. The wrapper clears active stack/continuation
state and marks `exited` on every exit. Fatal or pre-start cancellation can
skip intermediate lifecycle states.

Workers do not remove their own registry entries. Only the main thread may
reap: it observes `exited`, joins the thread, marks `reaped`, and removes the
address. Tk's 50 ms poll reaps completed dynamic instances during operation.
Permanent addresses remain registered until the final shutdown sequence.

### Normal requested shutdown

Tk's close request, or Core's `None` sentinel, enters Core's semantic
`SHUTDOWN` path. Its effects close dynamic creation, request Core retirement,
wake/cancel dynamic workers, send Mem its sentinel, and tell Tk it may close.
Mem force-flushes pending canonical day bundles to Disk before returning.

After Tk leaves its main loop, the application and worker tests use the same
`main.finish_worker_shutdown()` function:

```text
close creation / wake dynamic workers
-> join Core -> join remaining dynamic workers -> join Mem
-> send Disk None -> join Disk -> reap all exited workers
```

Disk stops after its producers have stopped, so queued day writes precede its
sentinel. `SHUTDOWN_COMPLETE` permits closing the window; it is not itself a
persistence barrier. Final joins complete the ordinary exit sequence.
Unfinished image operations are cancelled, not guaranteed to become panel
commits. Normal shutdown does not drain every outstanding return stack.

### Fatal unexpected worker death

An uncaught `BaseException`, or an unexplained worker return while still
marked running, prints a full traceback and calls the idempotent
`when_thread_dies_unexpectedly()`. That function first sets
`a_thread_died_unexpectedly`, also closes creation, and sends `None` to every
registered worker inbox. Workers check the fatal event after waking; routing,
Core event/effect processing, and Tk command handling also stop ordinary work.

Tk's independent main-thread poll closes the window even if Core is the dead
worker. Main joins and reaps workers, then exits with status 1. Fatal shutdown
does not force Mem's normal save flush. Recent/in-flight state may be lost;
there is no recovery, retry, emergency save, or `os._exit()` path.

This enforces the policy that an unexpectedly dead worker must not leave the
rest of Today operating normally. It is cooperative shutdown, not interruption
of Python or native code already executing inside a handler. A hung worker
without an exception is outside the current policy: joins have no application
timeout or watchdog, by explicit design choice.

## Root resolution and durable storage

Before opening Tk or starting workers, Disk resolves MachineRoot's
`db-root-2026` resource and appends `today`. Missing configuration fails startup
instead of selecting a hardcoded fallback. `main(data_root=...)` supplies an
exact alternate directory for isolated tests and bypasses the registry lookup.

Each day lives under:

```text
<root>/YYYY/YYYY-MM/YYYY-MM-DD/
    YYYY-MM-DD.json
    assets/image-<uuid>.jpg|png|gif
    files/
```

Mem coalesces canonical changes into day-bundle writes, with a one-second
deadline from the latest change. Disk writes JSON to a temporary file and
replaces the destination. Image assets similarly publish via temporary-file
replacement. These are not a transaction spanning JSON and assets, nor a
power-loss durability guarantee. A fatal day-file I/O exception terminates
the application; expected image I/O failures return image error data.

## Image panel path and thread boundaries

An empty position offers `+ Image`. Empty image panels offer Paste from
Clipboard and Browse for Image, and accept one dropped file. Clearing returns
to these controls; it is distinct from unhosting or deleting the panel.
The root uses tkinterdnd2 for native drop reception and Pillow for image work.

Tk owns the dialog and drop callback. Both supply file paths; Tcl list parsing
preserves spaces in dropped paths. Paste sends a request only. An Image worker
uses Pillow's clipboard acquisition to obtain pixels or a single file path,
then validates JPEG, PNG, or GIF content. Source files are copied, not moved;
clipboard pixels become PNG.

```text
Tk request -> Core -> new Image instance
-> acquire / validate -> Disk writes asset -> same Image instance
-> Core validates result token -> revisioned Mem panel update

Tk preview bounds -> Core -> new Image instance
-> Disk reads asset -> same Image instance decodes / fits RGBA pixels
-> Core validates result token -> Tk constructs PhotoImage
```

An instance retires after its result/error handoff, not before its Disk return.
Decoding, EXIF orientation correction, and resizing happen off the Tk thread.
Tk creates and retains each host's `PhotoImage`; image objects do not cross
the GUI seam. Preview requests debounce geometry changes by 100 ms and fit
without upscaling. GIF presentation is static, using the first frame.

Mem stores only a day-relative `image-asset` reference or null. Original image
bytes and prepared preview pixels are not serialized into the day JSON.
Disk accepts only generated asset reference shapes, preventing arbitrary
relative paths from becoming stored asset reads.

Core's import/preview tokens reject obsolete results. Clear, deletion, and
day replacement invalidate requests; clear/import changes serialize through
the existing panel revision/edit-generation machinery. Tk additionally rejects
previews for obsolete assets or bounds and cancels pending widget callbacks
on teardown. Bad, missing, unsupported, or empty clipboard input produces an
ordinary panel error, not unexpected worker death.

Clearing or deleting retains the day-owned file. Cancellation or a stale
import can also leave an unreferenced asset. This intentionally avoids deleting
a file still referenced by an older saved bundle; garbage collection is not
implemented.

## Execution evidence

The current standard-library suite passes **43 tests**. Coverage includes
snapshot isolation and transfer ownership; revisioned updates and normal
worker shutdown; MachineRoot resolution/override; fatal failure and repeated
failure reporting; TkMarkup; dynamic creation/address replacement; repeated
deliveries; continuation survival through another machine; explicit retirement
and main-thread reaping; shutdown creation gates and discarded late returns;
image formats, asset storage, fitted previews, expected input errors, and
stale import/clear/delete handling.

Fresh-process real-Tk checks pass for normal shutdown and injected Core, Mem,
and Disk failures, with no remaining Today worker threads. Image UI checks
exercise input callbacks, busy/clear behavior, prepared display, stale results,
and teardown. A full-app image roundtrip imports into an isolated root, closes,
restarts and displays the saved image, then clears and persists the empty
reference while retaining the file.

These are scripted Windows Tk checks, not manual visual inspection or proof
of every desktop integration. Clipboard pixels are mocked in worker tests;
file-dialog selection and drop payloads are supplied to callbacks. Actual
clipboard interoperability and physical OS drag gestures remain useful manual
checks. `tests/gui_smoke.py` retains earlier-stage assumptions; the current
GUI evidence comes from `gui_failure_smoke.py`, `gui_image_smoke.py`, and
`gui_image_roundtrip.py`.

## Remaining boundaries and candidate lessons

The old review's missing Disk, canonical commit, unsupervised worker death,
and unresolved dynamic-continuation questions are no longer current gaps.
The remaining boundaries are concrete:

- Cooperative shutdown cannot finish a handler stuck forever. No timeout,
  forced thread termination, or hung-worker recovery is provided.
- Assets have no garbage collector; repeated import/clear can grow disk usage.
  GIF animation is not supported. Dynamic thread creation has no pool or
  concurrency cap; revisit that only if observed workloads require it.
- Mem acceptance and durable save remain different milestones. Normal exit
  completes queued writes but does not make unfinished imports successful;
  fatal exit intentionally permits loss. JSON and asset publication are not
  a multi-file transaction.
- Runtime selection is still a wiring convention, not an exclusive thread
  lease. Registries and module dictionaries remain Python-accessible. Runtime
  initialization refuses live workers; this does not establish full GUI or
  application in-process restart support.
- Reducer state remains module-owned. Explicit replay/state-in/state-out is a
  possible future change, not a prerequisite for the current boundaries.

Candidate lessons for review, not permanent rules:

- Establish which executable and date a document describes before borrowing
  mechanisms from historical prototypes.
- Test ownership with nested traveling data, and test lifecycle with held
  continuations, late returns, and actual thread termination.
- Keep runtime-owned frame completion separate from handler-declared
  continuations; keep retirement separate from reaping.
- Distinguish expected operation errors from broken worker invariants, and
  ordinary save completion from fatal cancellation.
- Run real Tk checks alongside machine-only tests; they reveal different
  classes of failure without moving image processing into the GUI thread.
