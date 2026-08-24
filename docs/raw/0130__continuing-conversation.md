```
date: 2026-08-24
title: (Continuing Conversation)
purpose: We've made an experiment that demonstrates exactly how to construct panes, tabs, divide up the visual space; We're now going to work on populating it with usable panes.
```

# Today / M1 Cockpit — Conceptual Handoff

We have been designing **“Today”**, the M1-based daily cockpit for the **Temple of Focus**.

The purpose of Today is to be the main operational interface for a day: a place to orient, decide what matters, act, observe, journal, measure, and see what is coming.

Arcs will eventually connect to this system, but **Arcs are intentionally not part of the first implementation**.

A guiding principle throughout has been:

> **Don’t settle the ontology — discover it.**

We want to build something useful quickly, while preserving enough structure that future reshaping is easy.

---

## 1. Date vs. Day

A major distinction emerged between:

* a **civil calendar date**
* a **lived/operational day**
* application-specific state associated with that day

The current attractive idea for a globally reusable date identifier is something like:

```text
tag:m1lattice.net,2026:date/2026-08-23
```

The important property is that this URI can be used as a **coordinate** without requiring an actual M1 entity record to be instantiated anywhere.

Things can simply link to it.

Its meaning is largely established by the network of loaded/accessible data that references it.

The practical meaning of “August 23, 2026” therefore emerges from the data currently visible around that node.

The `2026` immediately following the TAG URI authority is **not a temporal claim about the represented thing**. It is part of the TAG URI uniqueness strategy: a year during which that authority unambiguously controlled the email/domain used to mint the URI.

---

## 2. Hodological Date

Lion routinely uses the concept of a **hodological date**.

A hodological day follows the continuity of lived waking time rather than midnight.

For example:

* wake at 8:00 AM on August 23
* remain awake until 4:00 AM on August 24

The 4:00 AM period still belongs to the same hodological day that began on August 23.

Therefore:

> **Civil Date is not necessarily identical to the operational Day used by Today.**

This strengthens the case for treating a canonical civil Date as a shared coordinate while allowing Today to have its own lived/operational concept of a Day.

---

## 3. Should Everything Belong to a “Lion’s Day” Entity?

This is intentionally unresolved.

Two possible models were considered.

### Container-like model

A “Lion’s Day” entity exists, and todos, journal material, objectives, etc. are aspects or child-like data attached to it.

### Relational model

Todos, appointments, journal entries, metrics, objectives, etc. exist as independent entities and link to:

* Lion
* the relevant Date/Day
* eventually other things such as Arcs, projects, places, people, etc.

Current thinking leans toward the second model because it preserves the independent meaning of each object.

A Todo is a Todo.

A Journal Entry is a Journal Entry.

“Belongs to Lion” and “associated with this Day” can simply be relationships.

A separate Lion-Day or Today-app/day entity can still exist when there is genuinely something to say about **the conjunction of Lion and that day**, especially application-specific state such as layout.

---

## 4. A Today-App Day Entity

There may be a Today application entity for a particular user/day.

It may use:

* a GUID, or
* a configurable TAG URI pattern containing the relevant date

For example:

```text
tag:lionkimbro@gmail.com,2026:/today-app/date-entry/2026-08-23/
```

That entity could link to:

```text
tag:m1lattice.net,2026:/date/2026-08-23/
```

and to a user/person entity such as:

```text
tag:lionkimbro@gmail.com,2026:/person/lionkimbro/
```

The Today application layout can live on an application-specific aspect on that entity.

---

# 5. Core Conceptual Functions of Today

Several broad functions emerged.

These are **conceptual regions**, not a fixed final GUI layout.

## Orientation

Answer:

> Where am I?

> What kind of day is this?

> What matters about the situation?

At minimum, Orientation includes:

* Date
* Day of Week
* a freeform context/orientation note

Example:

```text
Low-energy day.
Keep scope narrow.
Fair Play is the main development focus.
Important thing happening tomorrow.
```

The orientation note should be prominent enough to contextualize everything else.

A task has very different meaning on a high-energy engineering day than on a depleted recovery day.

---

## Direction

Answer:

> What am I trying to make happen today?

This led to the idea of **Objectives** being distinct from Todos.

Example:

```text
Objective:
Get Fair Play meaningfully closer to usable.
```

with several todos beneath or related to it.

Or:

```text
Objective:
Recover enough that tomorrow is viable.
```

Todos are actions.

Objectives preserve the purpose those actions serve.

---

## Operations

The ordinary actionable material:

* todos
* reminders
* appointments
* tasks
* perhaps other operational objects

The system should avoid prematurely becoming an enormous GTD ontology.

Start with clear, minimally committed facts.

---

## Witness

The day is not merely something to command.

It is something to observe.

This includes:

* journal entries
* observations
* activity notes
* realizations
* accomplishments
* status changes
* simple timestamped human notes

We deliberately did **not** settle whether the human journal should be the same thing as the M1 Log Aspect.

---

## Metrics

Possible examples:

```text
Sleep
Energy
Mood
Deep work
Exercise
Weight
Money earned
Sticker production
Programming time
Meditation
Miles driven
```

The interesting architectural idea is to make metrics generic rather than special-casing each type.

Something like:

```text
MetricDefinition
    name
    unit
    value_type

MetricObservation
    metric
    value
    timestamp
```

This would let Today gain new “senses” without adding new bespoke code for every measurement.

---

# 6. Forward-Looking Orientation

Orientation is not only about today.

It should also answer:

> What happens tomorrow?

> The day after tomorrow?

> What matters in the next seven days?

> What major things are coming later?

This led to a **pseudo-logarithmic future display** concept.

Today is shown in maximum detail.

Tomorrow appears in abbreviated form.

The day after tomorrow is somewhat compressed.

The next week becomes a compact horizon band.

Farther future time is mostly invisible except for highly significant events.

The metaphor used was the **Grand Galloping Gala** from MLP: a distant event can orient an enormous amount of present activity even when it is still far away.

---

# 7. Brightness / Salience

A related idea:

Future days or events could have a **brightness** or **salience** value.

Visibility would depend on some combination of:

* temporal distance
* importance / brightness

Ordinary distant days fade into darkness.

A highly significant event remains visible far in advance.

As an event approaches, even moderately important events naturally become more visible and detailed.

This feels closer to human temporal awareness than a flat calendar grid.

No brightness algorithm has been designed yet.

It is just an important future design insight.

---

# 8. M1 Log Aspect

M1 already has a core **Log Aspect**:

```text
tag:m1lattice.net,2026:aspect/log
```

The intent is to attach chronological histories to entities.

Important properties:

* append-only
* chronological
* multiple logs from different sources may coexist
* logs can be merged
* identical duplicate entries are eliminated
* individual entries are preserved
* interpretation belongs to consuming systems

Each entry has:

```text
timestamp
event
note?
agent?
via?
```

with an open event vocabulary including things such as:

```text
CREATED
UPDATED
ACCESSED
DEPRECATED
NOTE
```

General M1 tooling should eventually understand and support this aspect.

The user has not yet actually used it in practice.

---

# 9. Todo State and Logs

One useful pattern emerged for Todos.

A Todo entity may have a Todo-specific aspect containing current state:

```text
status: checked
```

while the generic Log Aspect records historical/provenance information:

```text
timestamp: ...
event: UPDATED
note: "Todo item was checked."
agent: Lion
via: Today application
```

This seems preferable to forcing every reader to replay the entire log just to answer:

> Is this checkbox currently checked?

So:

> **Current state lives in the domain aspect.**

> **History lives in the Log Aspect.**

There was also an idea for a future generic log extension:

```text
changes:
    - aspect: ...
      path: [...]
      value: ...
```

possibly including old/new values later.

But this was explicitly deferred to avoid getting overly bookkeeping-focused.

---

# 10. Whiteboard Interaction Model

A very important inspiration comes from the existing **pydeck26 Whiteboard** control.

It works like this:

* freeform editable text
* user may type anything
* clicking **Snapshot** stores a timestamped copy
* a vertical slider browses previous snapshots
* the status bar shows the timestamp of the selected historical state
* the text area displays what was stored at that time
* returning the slider to the top returns to the present editable state
* if the user browses to an old snapshot and begins editing it, that edited version becomes the new present

This is a particularly attractive interaction model for orientation/context notes.

It allows:

> a mutable present with recoverable historical states

without turning every revision into a journal entry.

The Whiteboard’s history mechanism is considered especially valuable.

---

# 11. Whiteboard Identity

A Whiteboard should probably be treated as:

* a **panel type**
* plus a particular **Whiteboard instance**

If two panes both display Whiteboards, they do not necessarily display the same underlying Whiteboard.

A specific Whiteboard can have:

* a GUID or other stable identity
* a user-visible title

Example:

```text
GUID: ...
Title: "Fair Play Architecture"
```

The title is not identity.

A possible panel menu interaction:

```text
Whiteboards >
    + New Whiteboard
    Fair Play Architecture
    Scratchpad
    ...
```

Current conservative instinct:

> **A Whiteboard may remain a context-local working surface rather than becoming a universal cross-context document system.**

If material becomes important enough to live elsewhere, promotion/copying into a document, journal entry, task, etc. can be an explicit act.

This is unresolved, but “NO — it’s just a Whiteboard” was considered a healthy initial constraint.

---

# 12. Day File Tree

Current likely filesystem organization:

```text
/yyyy/yyyy-mm/yyyy-mm-dd/
```

Example:

```text
/2026/2026-08/2026-08-23/
```

This creates a clear physical home for per-day M1 material.

---

# 13. GUI Chassis — Current Successful Architecture

A substantial amount of work was done building and testing a generic page/chassis system.

The chassis is now considered **successfully proven** and potentially reusable in other projects such as pydeck26.

The outer window is:

```text
Top Area

Middle Area

Status Bar
```

The Top Area and Middle Area are separated by a draggable sash.

The Status Bar stays fixed at the bottom.

---

## Middle Area

The Middle Area is a vertically scrollable document.

It contains a sequence of Rows.

Each Row contains:

* a narrow structural control strip on the left
* 1, 2, or 3 horizontally arranged panes

The row controls look approximately like:

```text
[1]
[2]
[3]

[x]
```

The selected pane-count button is visually active.

`x` deletes the row.

The row controls manipulate **row geometry**, not panel content.

---

## Rows Stack; Panels Divide

A crucial discovery:

> **Rows stack. Panels divide.**

Rows should **not** be implemented as children of one big vertical `PanedWindow`.

That caused rows to compete for portions of the viewport and produced bizarre resizing behavior.

Instead:

* rows are independent blocks in a vertically scrolling document
* each row has its own explicit height
* custom draggable horizontal resize handles change row height
* adding a row increases the total document height
* deleting a row decreases document height
* other rows do not automatically grow or shrink

Inside each row, however, a horizontal Tkinter `PanedWindow` is exactly appropriate.

The row’s 1–3 panels divide the row’s available width using draggable sashes.

So:

```text
Vertical:
    independent document blocks

Horizontal:
    true PanedWindow panes
```

---

# 14. Panels

Each pane hosts one panel/instrument.

The panel has a very small `...` menu.

The distinction is:

> **Row controls determine layout.**

> **Panel controls determine content.**

Possible future panel types include:

* Orientation
* Todo
* Whiteboard
* Journal
* Objectives
* Metrics
* Upcoming
* others discovered later

The panel itself is a host.

It is not permanently bound to a semantic type.

---

# 15. Whole-Page Tabs

Tabs were added, but an important correction was made:

Tabs do **not** belong inside individual panes.

Tabs apply to the **whole middle page**.

The hierarchy is:

```text
Today Window
    Top Area

    Page Tabs
        Page
            Rows
                Pane
                    Panel

    Status Bar
```

Each tab represents a complete workspace/page layout.

A tab therefore owns things such as:

* number of rows
* row heights
* pane counts
* horizontal sash positions
* panel assignments
* eventual panel-specific state
* eventual scroll position

Example conceptual tabs:

```text
Daily
Planning
Writing
Review
+
```

The final `+` tab creates a new page.

Real tabs have:

* GUID identity
* user-editable display name

Double-clicking a tab can rename/delete it.

This leads to the compact design principle:

> **Rows stack. Panels divide. Pages switch.**

---

# 16. Reusable Page Chassis

The resulting GUI system appears useful beyond Today.

It may be reusable directly in **pydeck26**, which is a project-focal cockpit containing things such as:

* Structure
* Dictionary
* Conversations
* Ideas
* Whiteboard

The page chassis is therefore worth preserving as a reusable component rather than treating it as Today-specific throwaway GUI code.

---

# 17. Where We Are Now

The GUI chassis exists and feels successful enough to build on.

Now, the immediate goal is to begin **populating the cockpit with real Today instruments** and to discover the system through use.

The most important first target is probably the **Top Area**, because it is unique: unlike the tabbed middle workspace, the Top Area is **global to the currently selected day and remains visible across every page tab**.

We already expect the Top Area to contain some combination of:

* the current date;
* day-of-week / temporal identity;
* controls for navigating backward and forward between days and returning to Today;
* some kind of orienting/context message for the day;
* perhaps, later, compact forward-looking context.

But these details are intentionally **not settled yet**.

The next conversation should begin by asking:

> **What should always be visible at the top of Today, no matter which cockpit page I am looking at?**

From there, begin implementing the first real controls and then populate useful panels in the middle workspace.

The design method remains:

> **Build the smallest useful thing, use it, notice what is missing, and let the interface reveal the ontology.**
