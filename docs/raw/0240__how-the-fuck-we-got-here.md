# How the Fuck We Got Here

## Purpose

This is an orientation map, not a forensic history. It preserves the major
intellectual arcs behind the experimental files so that future context can
read old plans as evidence rather than as a pile of contradictions.

## The Three-Paragraph Dramatic Telling

Today began with a triumph. We set out to make a real daily cockpit and, almost gloriously, the physical system came together: tabs, rows, panes, positions, panels, draggable geometry, and a layout that could be inhabited rather than merely displayed. The `01` and `03` lineage proved that the core body of Today was not a vague aspiration but a beautiful, working thing. Alongside it came a controlled reducer-like interaction model, so callbacks would not dissolve into chaos. Fair Play and M1 were on the horizon—leases, shared files, a larger semantic ecology—but we made the early, clarifying decision to lock the scope down: Today would build and govern its own data world first, retaining identities and future export seams without trying to solve the whole distributed future before the cockpit itself had a life.

Then came the thread problem, and dread: every ordinary threaded request seemed to demand a conversation nobody wanted to remember. Send a message, wait for a response, identify what request it belongs to, reconstruct the interrupted process, and somehow continue correctly. The feeling was: *I hate threading; I do not want to live in this bureaucratic nightmare.* Mobile Stacks arrived as a revelation. One workload could travel, carrying its situation and the continuation of what remained. At first the revelation ran wild: `04` started growing toward a Forth-like stack machine, a threaded interpreter, practically a programming language, with serials and builders and phases and anarchy in the streets. That was the near-disaster. The rescue was the simplifying insight behind `05`: make the stack tiny—only the next machine and entry point—and make the registers wide enough to carry the situation. Frames remember control; registers remember the situation; ordinary Python does the work. It worked spectacularly, and changed how we think about cross-thread programs.

Then came the tragic discovery during the `06` merger: in our excitement to join `03`’s magnificent body with `05`’s magnificent nervous system, we had forgotten that `03` was already a reducer-core architecture. Suddenly the question was not merely “can these programs be joined?”—they could—but “which of these systems is supposed to govern what?” Panic, re-evaluation, first principles. Mobile Stacks should carry contextual work across machines; a Reducer Core should greedily and predictably govern a bounded present state; the enormous world of days and panels should not be swallowed by either. That is where we stand now: not in failure, but at the dramatic turning point where the earlier victories have made a more powerful design visible—Tk as a device machine, a bounded Reducer Core, a world model in Mem, persistence in Disk, and Mobile Stacks in their proper revelatory role.

Dates are reconstructed from document metadata and repository commits. One
older handoff has a conflicting `2025` metadata date; the `03` date follows
the surrounding August 2026 commits instead.

```text
2026-08-23 to 2026-08-25  layout, interaction, and the `03` union
2026-08-26 to 2026-08-27  explicit Tk / Mem / Disk thread thinking
2026-08-27 to 2026-08-28  initial Mobile Stacks invention
2026-08-29 to 2026-09-01  significant inactive pause: no notes or commits
2026-09-02 to 2026-09-04  Mobile Stacks return, complication, and rescue
2026-09-04                  `06` merge and architectural reconsideration
```

## Act I — The chassis (2026-08-23 to 2026-08-25)

Today began as a daily cockpit: a lived, reconfigurable workspace, not a Todo
app. `01_panels-model.py` and the earliest documents proved the hard part:
tabs, rows, one/two/three panes, draggable geometry, stable positions,
distinct panel identities, and switchable panel instruments could form a
beautiful layout system. This is the precious body of Today.

## Act II — Controlled interaction (2026-08-24 to 2026-08-25)

`02_interaction-model.py` addressed scattered widget-callback mutation. Tk
events became data; a controlled stage changed logical state; Tk reconciled
widgets afterward. This is where the reducer-like idea entered:

```text
state + event -> next state + effects
```

It offered isolation, predictable legal transitions, and an eventual path to
history and undo/redo.

## Act III — `03` made the body live (2026-08-25)

`03_combined-model.py` joined the layout chassis and interaction model into a
strong single-threaded application. Tabs, rows, pane geometry, panel
positions, Orientation, and basic panels worked together. Persistence and
workers were intentionally deferred: first prove the real cockpit.

## Act IV — Backing away from Fair Play and M1 (by 2026-08-25)

An earlier horizon involved M1-related storage and Fair Play leases for
multi-process access to files. It was a real future possibility, but too much
machinery for the immediate application. We chose to build Today’s own
understandable data world first and defer M1/Fair Play integration. Correct.

## Act V — The thread problem (2026-08-26 to 2026-08-27)

The next concern was responsiveness: Tk must remain responsive; complex memory
work should not freeze it; disk I/O needs its own jurisdiction. The Part II
work named Tk, Mem, and Disk threads. But ordinary threaded conversations are
cognitively miserable: what request is this reply for, and what remains?

## Act VI — Mobile Stacks (2026-08-27 to 2026-08-28; resumed 2026-09-02)

Mobile Stacks made traveling work explicit:

```text
the stack remembers control
the registers remember the situation
ordinary Python does the work
```

`04` began growing into a virtual machine: serial construction, phases,
replacement builders, instruction pointers, and too much machinery. `05`
simplified it successfully:

```text
one physical thread = one machine
frames = machine and operation
registers = traveling context
push() / drop() = continuation vocabulary
```

It worked in a live demonstration: a small nervous system, not a tank.

There was a significant pause from 2026-08-29 through 2026-09-01: no commits,
notes, or active development.  The September work was a return to the
experiment, including salvaging and simplifying what had been built earlier;
it was not one uninterrupted escalation of the design.

## Act VII — `06` united body and nervous system (2026-09-04)

The merger’s phrase was: `03` provides the body; `05` provides the nervous
system. `06_combined-model.py` proved that the rich layout could survive work
travelling through Tk, Mem, Disk, and back to Tk. This was a real success.

It also exposed a collision we had partly forgotten. `03` was not only layout;
it contained reducer-core discipline. Mobile Stacks move contextual work across
machines. Reducer Core governs bounded state transitions and produces effects.
Using Mobile Stacks for every layout event was workable, but raised the right
question: was the nervous system swallowing the reducer’s job?

## The distinction we were missing

```text
Reducer Core state
  the bounded present on-screen situation: active workspace snapshot,
  hosted positions, visible panel snapshots, selection, pending UI state

World model
  the large canonical universe: all days, all panels, journals,
  whiteboards/history, and future data
```

The world will be enormous; it should not be greedily absorbed into one
reducer-state object. The Core can instead work on the current lived slice.

## The emerging `07` picture (2026-09-04)

```text
Tk
  device machine: normalizes meaningful input and realizes declarative commands

Reducer Core
  bounded present state; reduce(state, event) -> next state, effects

Mem
  canonical world model and panel semantics

Disk
  persistence
```

Tk-to-Core semantic event queues and Core-to-Tk declarative command queues may
be clearer than forcing every one-way UI interaction into a Mobile Stack.
Mobile Stacks remain for Core/Mem/Disk work that needs context and continuation.
A stack return becomes a later Reducer Core event, rather than beginning a
nested stack while one is active.

## Open questions

* What exactly belongs in bounded Core state?
* Is active-day layout a Core snapshot, Mem data, or a careful split?
* What panel data is visible snapshot data versus Mem-only canonical data?
* Where does each panel type’s semantic logic live?
* Which crossings deserve stacks, and which deserve simple queues?
* What is the smallest declarative Tk command vocabulary that preserves the
  rich layout system?

## How to read the parts

```text
01: rich layout is possible and precious
02: controlled reducer-like interaction is valuable
03: layout and interaction body can live together
04: continuation travel is needed; do not overbuild a VM
05: small Mobile Stacks nervous system works
06: body and nervous system can meet; their final split needs thought
07: next exploration: bounded Core, world model, device Tk, proper stacks
```

We are not starting over. We have earned better questions.
