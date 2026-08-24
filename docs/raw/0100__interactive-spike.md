```
date: 2026-08-23
title: Interactive Spike
tags: today cockpit interactive chassis spike
```

# Today Cockpit GUI Layout — Minimal Implementation Spec

## Purpose

Build the **minimal GUI chassis** for the M1-based “Today” application.

This version is **only about layout and interaction**. It does not need to implement todos, journal entries, metrics, objectives, Arcs, date semantics, or other Today-system behavior yet.

The goal is to create a flexible cockpit layout that feels good to manipulate and can later host arbitrary Today panels.

---

## Window Structure

The application window has three major areas:

1. **Top Area**
2. **Middle Area**
3. **Status Bar**

The **Top Area** and **Middle Area** are contained in a vertically oriented Tkinter `PanedWindow` / `ttk.Panedwindow`.

The user must be able to drag the horizontal sash between them to resize how much vertical space each area occupies.

The **Status Bar** is outside the paned window and remains fixed at the bottom of the application window.

Conceptually:

```text
┌──────────────────────────────────────────────────────────────┐
│                         TOP AREA                             │
│                                                              │
├════════════════════ draggable sash ══════════════════════════┤
│                                                              │
│                        MIDDLE AREA                           │
│                                                              │
│                                                              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ STATUS BAR                                                   │
└──────────────────────────────────────────────────────────────┘
```

---

## Top Area

For this implementation, the Top Area may simply be an empty framed region containing a label such as:

```text
Top Area
```

Do not implement Today-specific controls yet.

The only important behavior is:

* it exists;
* it participates in the vertical `PanedWindow`;
* its height can be changed by dragging the sash;
* its sash position can eventually be saved/restored as part of the layout.

---

## Middle Area

The Middle Area is the main workspace.

It contains:

* a vertically scrollable content area;
* a vertical scrollbar on the right.

Because a normal Tkinter `Frame` is not directly scrollable, implement this using the conventional:

```text
MiddleArea
    Canvas
        RowsFrame
    Vertical Scrollbar
```

`RowsFrame` is embedded inside the Canvas using `create_window()`.

The scrollbar controls the Canvas's vertical scrolling.

The Canvas scroll region must update when the size of `RowsFrame` changes.

The embedded `RowsFrame` should track the available Canvas width so that rows expand horizontally with the window rather than retaining an arbitrary fixed width.

---

# Rows

`RowsFrame` contains zero or more **Rows**, followed by an **Add a Row** button.

The Add a Row button must always appear after the final row.

Example:

```text
┌──────────────────────────────────────────────────────────────┐
│ Row 1                                                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Row 2                                                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ Row 3                                                        │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                        [ Add a Row ]                         │
└──────────────────────────────────────────────────────────────┘
```

Clicking **Add a Row** creates a new row immediately above the button.

A new row should initially contain **one pane**.

---

# Row Layout

Each Row is implemented as a **horizontal PanedWindow**.

A Row can contain:

* 1 pane;
* 2 panes;
* 3 panes.

When more than one pane exists, the user can drag the vertical sash or sashes left/right to resize the panes.

Examples:

### One pane

```text
┌──────────────────────────────────────────────┐
│ PANEL                                        │
│                                              │
└──────────────────────────────────────────────┘
```

### Two panes

```text
┌────────────────────┬─────────────────────────┐
│ PANEL              │ PANEL                   │
│                    │                         │
└────────────────────┴─────────────────────────┘
```

### Three panes

```text
┌──────────────┬──────────────────┬─────────────┐
│ PANEL        │ PANEL            │ PANEL       │
│              │                  │             │
└──────────────┴──────────────────┴─────────────┘
```

Rows themselves are stacked vertically inside `RowsFrame`.

Rows should have a reasonable minimum height.

For the initial implementation, a row height around 150–250 pixels is acceptable.

Exact visual tuning can be adjusted later.

---

# Panels

Each pane contains exactly one **Panel**.

For now, a Panel is just a placeholder control.

It should visibly demonstrate:

* where the panel begins and ends;
* that it is hosted inside a pane;
* that the pane can be resized.

A Panel may initially contain something like:

```text
┌─────────────────────────────┐
│ Empty Panel              ⋮  │
│                             │
│                             │
│                             │
└─────────────────────────────┘
```

Do not implement actual panel types such as Todo, Journal, Orientation, Metrics, etc. yet.

However, structure the code so that a future Panel can contain an arbitrary child widget representing a selected panel type.

---

# Panel Manipulation Controls

Layout controls should consume as little visual space as practical.

Avoid large permanent toolbars around every panel.

For the initial version, each Panel may have a very small header containing:

```text
Empty Panel                     ⋮
```

or:

```text
Empty Panel                     ▾
```

Activating the small menu/control should expose temporary manipulation commands.

At minimum, provide enough controls to experiment with:

* changing the Row to 1 pane;
* changing the Row to 2 panes;
* changing the Row to 3 panes;
* removing a Row.

It is acceptable for the first implementation to place these commands in a small popup menu.

The main goal is to prove the layout concept, not perfect the manipulation UI.

---

# Row Pane Count

Changing the number of panes in a Row should work as follows:

### 1 → 2

Create another pane and Panel.

Try to divide the width approximately evenly.

### 2 → 3

Create another pane and Panel.

Try to divide the width approximately evenly.

### 3 → 2

Remove one pane.

For this prototype, removing the rightmost pane is acceptable.

### 2 → 1

Remove the rightmost pane.

### 3 → 1

Remove the two rightmost panes.

There is no important user data inside Panels yet, so destructive pane removal is acceptable in this prototype.

---

# Status Bar

A fixed Status Bar exists at the bottom of the window.

For this implementation it may simply display:

```text
Ready.
```

It should be structured as a place where future controls can report things such as:

* selected date;
* selected entity;
* snapshot timestamp;
* loaded file;
* save state;
* current panel;
* errors or informational messages.

---

# Scrolling

The Middle Area must scroll vertically when its Rows exceed the available viewport height.

The vertical scrollbar remains fixed on the right side.

Mouse wheel scrolling should work when the pointer is over the Middle Area.

Scrolling should move the Rows as a unit.

The Top Area and Status Bar must not scroll.

---

# Resizing

The GUI should behave sensibly when the main window is resized.

In particular:

* the outer vertical PanedWindow expands with the window;
* the Middle Area expands horizontally and vertically;
* the Canvas expands;
* Rows expand to the width of the Canvas;
* horizontal Row panes expand with their Row;
* the scrollbar remains against the right edge;
* the Status Bar remains against the bottom edge.

Use Tkinter `grid()` weight configuration or equivalent so resizing behaves naturally.

Prefer `grid()` for the main structural layout rather than mixing geometry managers inside the same parent.

---

# Initial Layout

On first launch, create a simple demonstration layout.

Recommended default:

```text
Top Area

Row 1
    2 panes

Row 2
    1 pane

[ Add a Row ]

Status: Ready.
```

The exact initial arrangement is not important.

The purpose is to immediately demonstrate:

* vertical Top/Middle resizing;
* horizontal pane resizing;
* multiple rows;
* scrolling;
* adding rows;
* changing pane counts.

---

# Layout Persistence

The eventual application will associate layout state with a particular Today-app/day entity.

Do **not** build the M1 persistence layer yet unless doing so is trivial.

However, structure layout state so that it can eventually be serialized into an M1 aspect.

The intended aspect identifier is approximately:

```text
tag:lionkimbro@gmail.com,2026:/today-app/layout/
```

A Today application entity will represent the application state associated with a particular person and date.

That entity may use either:

* a generated GUID; or
* a configured tag-URI pattern containing the date.

For example:

```text
tag:lionkimbro@gmail.com,2026:/today-app/date-entry/2026-08-23/
```

The Today application entity may link to:

```text
tag:m1lattice.net,2026:/date/2026-08-23/
```

and to a person entity such as:

```text
tag:lionkimbro@gmail.com,2026:/person/lionkimbro/
```

Important: the `2026` appearing immediately after the authority in a `tag:` URI is part of the TAG URI uniqueness mechanism. It indicates a period during which the authority controlled the domain/email identity. It does **not** mean the represented entity belongs to the year 2026.

---

# Layout State Model

Internally, represent the layout in a form that could later be serialized approximately like:

```text
layout
    outer_sash_position

    rows
        row
            pane_count
            sash_positions
            panels
                panel
                    panel_type

        row
            pane_count
            sash_positions
            panels
                ...
```

Possible future additions include:

```text
scroll_position
row_heights
panel_state
collapsed_state
selected_panel_type
top_area_state
```

Do not over-design this yet.

The important thing is that the GUI widgets should not themselves be treated as the persistent model.

Keep a small explicit Python representation of layout state, or make it straightforward to extract one from the widgets.

---

# Suggested Class Structure

A simple class organization would be useful.

For example:

```text
TodayApp
    TopArea
    MiddleArea
    StatusBar

ScrollableRows
    RowWidget
        PanelWidget
```

Possible responsibilities:

### `TodayApp`

Owns the root window and overall vertical layout.

### `TopArea`

Placeholder for future special Today controls.

### `MiddleArea`

Owns the scrollable Canvas, scrollbar, and RowsFrame.

Provides:

```text
add_row()
remove_row()
```

### `RowWidget`

Owns one horizontal PanedWindow.

Provides something like:

```text
set_pane_count(1 | 2 | 3)
get_sash_positions()
```

### `PanelWidget`

Placeholder container for a future Today panel.

Provides the minimal manipulation menu.

### `StatusBar`

Displays simple application state.

This exact decomposition is not mandatory if a cleaner implementation suggests itself.

---

# Important Architectural Principle

**Panels are hosts, not semantic types.**

A pane should not permanently be:

```text
TodoPane
```

Instead, conceptually:

```text
Pane
    PanelHost
        currently displaying TodoPanel
```

Later the same pane might display:

```text
OrientationPanel
JournalPanel
MetricsPanel
ObjectivesPanel
UpcomingPanel
ArcPanel
```

The physical cockpit layout and the semantic content displayed inside it should remain separate concepts.

---

# Non-Goals

Do **not** implement any of the following yet:

* todos;
* journal entries;
* objectives;
* metrics;
* orientation notes;
* upcoming-event logic;
* hodological dates;
* Arcs;
* M1 loading;
* M1 saving;
* Log Aspect support;
* task state;
* event scheduling;
* brightness/salience calculations;
* pseudo-logarithmic future visualization;
* drag-and-drop panel movement;
* sophisticated docking;
* polished themes;
* undo/redo;
* synchronization.

This prototype is strictly about answering:

> **Does this cockpit layout mechanism feel right?**

---

# Success Criteria

The prototype is successful if I can launch it and:

1. Drag the divider between Top Area and Middle Area vertically.
2. See a vertically scrollable collection of Rows.
3. Click **Add a Row** and get another Row.
4. Change any Row between 1, 2, and 3 panes.
5. Drag dividers between panes horizontally.
6. Resize the application window without the layout breaking.
7. Scroll through many Rows.
8. See a fixed Status Bar at the bottom.
9. Look at the resulting application and plausibly imagine filling the Panels with the real Today instruments later.

The primary goal is **feel and structural correctness**, not feature completeness.
