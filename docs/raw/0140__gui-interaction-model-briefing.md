```
date: 2026-08-24
title: Part I -- the GUI Interaction Model
```

# Today GUI Interaction Model — Context Handoff

We are building **Today**, the daily operational cockpit for the larger **Temple of Focus** system. Today is meant to be the main interface through which a user works with a particular operational/hodological day: orienting, planning, acting, journaling, measuring, and reviewing. The larger design principle is:

> **Don’t settle the ontology — discover it.**

We are deliberately building useful interaction machinery first, then allowing the data model to become clearer through use.

The GUI chassis itself has already been experimentally developed and is considered successful. Its core layout principle is:

> **Rows stack. Panels divide. Pages switch.**

A Today window has:

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

The **Top Area** is global to the currently selected Today-day and remains visible regardless of which page tab is selected. The middle workspace is organized into whole-page tabs. Each tab owns an entire layout.

Within a page, rows stack vertically in a scrolling document. Rows are independently height-resizable. Each row contains **1, 2, or 3 panes** arranged horizontally, and those panes divide the row width using draggable sashes. There can be any number of rows.

Each pane hosts a **Panel**. A Panel is a host, not a permanently fixed semantic object. A panel may currently display a Whiteboard, Todo list, Journal, Objectives view, Metrics view, Upcoming view, or some other instrument discovered later. The user can change what role a panel is playing.

So, conceptually:

```text
Panel Host
    currently displays:
        Whiteboard
    later may become:
        Todo
    later may become:
        Journal
```

The panel's identity as a GUI location/host is distinct from the semantic thing currently displayed in it.

Likewise, a tab represents an entire page configuration: row count, row heights, pane counts, pane sash positions, panel assignments, and eventually panel-specific state and scroll position. Switching tabs can therefore radically change the visible arrangement.

## Immediate GUI Direction

The top of the Today window is likely to begin approximately as:

```text
[<]  2026-08-24  [>] [今]   [ editable orientation message................ ]
```

The selected Today-day represents a **hodological/operational day**, not necessarily the current civic date.

Navigation is never blocked merely because a day is in the future. The user may intentionally move to tomorrow early or remain on yesterday after midnight.

`[今]` normally means: navigate to the current **civic date**.

The user may later have some mechanism to designate a different operational day as “today,” but that mechanism does not need to be solved in this interaction-model experiment.

The editable orientation field is important because it exposes the central interaction problem we are trying to solve: user interaction changes application state, may eventually require persistence, and must update only the relevant live GUI objects.

## Your Assignment

Your task is to develop the **GUI interaction and application-object model**.

Do **not** solve the threading system or persistence/Fair Play system yet.

Those are separate architecture efforts that will eventually connect to this one.

The larger program will eventually have three major architectural areas:

```text
1. GUI interaction / application model
2. Worker-thread / job execution model
3. Persistence / Fair Play lease-and-write model
```

This context is responsible primarily for **#1**.

The purpose of this work is to answer questions such as:

* When the user interacts with a widget, what object receives that interaction?
* How is the interaction represented logically?
* Where does application state live?
* How does a state change cause only the necessary GUI objects to update?
* How does a panel changing roles affect bindings and event routing?
* What happens when a page tab switches and an entirely different set of panels becomes visible?
* How do GUI hosts such as Top Area, Page, Row, Pane, and Panel relate to the semantic models they currently display?
* How can we avoid event handlers calling sideways into arbitrary widgets and creating callback chaos?
* How can the interaction layer later request background work without knowing how worker threads or persistence operate?

A reducer-like architecture is under consideration, but it likely cannot be a simplistic “state changed, redraw the whole interface” model.

The GUI contains long-lived, stateful Tkinter objects:

```text
TodayWindow
TopArea
PageHost
Page
Row
Pane
Panel
```

These objects have real widget identity, geometry, scroll state, sash positions, editing state, etc. The application cannot cheaply or sensibly rebuild the entire interface after every keystroke.

We therefore suspect the design may need something like:

```text
User Interaction
    ↓
Command / Intent
    ↓
Application Logic
    ↓
Model Change
    ↓
Targeted GUI Update
```

rather than direct widget-to-widget communication.

For example:

```text
EditOrientation(day_id, new_text)
```

should affect the model representing that day and ultimately cause persistence to be requested, but the orientation widget should not need to know anything about file leases, worker queues, or filesystem writes.

Likewise:

```text
SelectDay(day_id)
```

may require several GUI regions to update:

```text
date display
navigation button state
orientation binding
visible panel data
possibly page/tab state
```

but that update should occur through an understandable application mechanism rather than scattered callback chains.

## Important Larger-System Constraint

Later, the GUI thread will follow a strong rule:

> **The GUI thread does GUI work and submits background work. It does not block on slow operations.**

Persistence will eventually use a separate **Fair Play** leasing system. Writing a file may require waiting roughly five seconds to acquire permission before the write can occur. Therefore GUI interactions must eventually be able to produce asynchronous jobs without blocking the UI.

You do not need to design that worker/job architecture here.

However, the GUI interaction model should leave a clean seam where application logic can later emit something like:

```text
SaveRequested(...)
```

or:

```text
SubmitJob(...)
```

without the GUI layer caring how that work is executed.

Likewise, background completion messages will eventually return to the GUI/application layer and may need to update state such as:

```text
saved
saving
waiting for access
save failed
```

So the interaction architecture should not assume that every logical action completes synchronously.

## Development Strategy

Do **not** begin by retrofitting all of this into the existing complex paned/tabbed chassis.

Instead, build a small experimental GUI that proves the interaction model first.

A good initial toy may contain only:

```text
[<]  date  [>] [今]  [ editable orientation field ]
```

with a tiny in-memory state model containing a few days.

For example:

```text
AppState
    selected_day
    civic_today
    days

DayState
    orientation_text
```

and a small command vocabulary such as:

```text
SelectPreviousDay
SelectNextDay
SelectCivicToday
EditOrientation(text)
```

The purpose of the experiment is not to finalize these exact names or classes.

The purpose is to discover a clean interaction architecture that can later scale to:

```text
multiple tabs
arbitrary rows
1–3 panes per row
switchable panel roles
live panel instances
panel-specific state
day navigation
global Top Area state
targeted incremental GUI updates
future asynchronous jobs/results
```

Once the interaction model is understandable in the toy, we will adapt it into the already-proven chassis.

The key thing to preserve is this separation:

```text
GUI structure
    ≠
semantic/application state
    ≠
background persistence mechanics
```

Yet these layers must communicate through explicit, understandable interfaces.

The goal of this context is therefore:

> **Design and experimentally prove the smallest interaction model that can grow into Today without turning into callback soup.**
