```
date: 2026-08-23
```

# Today Cockpit GUI — Row Controls and Background Styling Change

Update the current GUI prototype with the following changes.

## 1. Move Row Layout Controls Out of Panel Menus

Each row should have a **small vertical control strip on its far left**.

The strip controls the geometry of the row itself, not the contents of any individual panel.

It should contain:

```text
[1]
[2]
[3]
[x]
```

Meaning:

* `1` → set the row to one pane
* `2` → set the row to two panes
* `3` → set the row to three panes
* `x` → delete the row

The button corresponding to the current pane count should appear visibly selected, pressed, highlighted, or otherwise distinct.

For example, a two-pane row might look conceptually like:

```text
┌────┬─────────────────────┬─────────────────────┐
│  1 │ Todo             ...│ Whiteboard       ...│
│ [2]│                     │                     │
│  3 │                     │                     │
│  x │                     │                     │
└────┴─────────────────────┴─────────────────────┘
```

Keep this strip **narrow and unobtrusive**. It should consume as little horizontal room as practical while remaining easy to click.

A width around 28–36 pixels is probably appropriate, but visual judgment is more important than an exact number.

---

## 2. Simplify the Panel `...` Menu

The `...` button inside each panel should no longer contain row-level commands such as:

```text
Set row to 1 pane
Set row to 2 panes
Set row to 3 panes
Remove row
```

Those belong exclusively in the new row control strip.

Instead, the panel menu should be reserved for operations concerning **that panel**.

For now, make its main purpose selecting the kind of panel.

Suggested menu:

```text
Panel Type
──────────────
Empty
Orientation
Todo
Whiteboard
Journal
Objectives
Metrics
Upcoming
```

These do not need to instantiate real panel implementations yet.

It is acceptable for selecting one merely to change the panel title, e.g.:

```text
Empty Panel
```

becomes:

```text
Whiteboard
```

or:

```text
Todo
```

The important architectural distinction is:

> **Row controls determine layout. Panel controls determine content.**

---

## 3. Fix Panel Popup Menu Position

Currently, clicking a panel's `...` button can cause the popup menu to appear far away from the button.

Fix this.

The popup menu should appear immediately adjacent to the `...` control, preferably directly beneath it or aligned to its lower-right corner.

Use the button's screen coordinates, such as:

```python
button.winfo_rootx()
button.winfo_rooty()
button.winfo_height()
```

and explicitly post the menu at the appropriate location.

The menu should visually feel attached to the button that opened it.

---

# 4. Add Stronger Visual Regions

The three major parts of the window should be visually distinguishable.

The intended visual hierarchy is:

```text
TOP AREA
    very deep navy blue

MIDDLE / ROW BACKGROUND
    slightly lighter dark blue

PANELS
    normal light panel surfaces

STATUS BAR
    visually distinct from the middle region
```

## Top Area

Give the Top Area a **very deep, dark navy blue background**.

Suggested starting point:

```text
#081525
```

or something visually similar.

This should feel very dark, calm, and substantial rather than bright or saturated.

Text appearing directly on this background should use a light foreground color so that it remains readable.

For example:

```text
#E8EEF5
```

Exact colors may be adjusted if necessary for readability.

---

## Middle Area Background

The area **behind and between the rows/panels** should use a slightly lighter dark blue.

Suggested starting point:

```text
#10243A
```

or:

```text
#122B43
```

The important relationship is:

```text
Top Area = darker navy
Middle background = slightly lighter dark blue
```

Both should still be clearly dark.

The panels themselves should remain light for now, creating a visual effect roughly like:

```text
deep navy header
dark blue cockpit workspace
light instrument panels floating inside it
```

---

## Status Bar

Give the Status Bar a distinct background so that it does not visually disappear into the workspace.

A neutral dark gray-blue or a shade related to the Top Area is fine.

For example:

```text
#0B1828
```

Add a subtle separator line or border above it if useful.

The Status Bar should clearly read as a fixed application region rather than the final few pixels of the scrolling workspace.

---

# 5. Make the Top/Middle Boundary Visible

The divider between the Top Area and Middle Area currently becomes difficult to see.

Preserve the draggable `PanedWindow` sash behavior, but make the boundary visually apparent.

A subtle line is sufficient.

For example:

```text
Top Area
────────────────────────────
Middle Area
```

The boundary should remain visible even when the Top Area has been resized very small.

Do not make it visually heavy; it should simply make the window structure obvious.

---

# 6. Make the Middle/Status Boundary Visible

Likewise, add a subtle separator between:

```text
Middle Area
Status Bar
```

This may be implemented as:

* a 1px border;
* a `ttk.Separator`;
* a contrasting top border on the Status Bar;
* another simple technique.

The purpose is simply to avoid regions visually dissolving into one another.

---

# 7. Preserve Existing Behavior

Do not regress any currently working layout behavior.

The following must continue to work:

* resizing the Top Area versus Middle Area;
* adding rows;
* deleting rows;
* changing rows between 1, 2, and 3 panes;
* dragging horizontal pane dividers;
* vertical scrolling;
* mouse-wheel scrolling;
* window resizing;
* keeping the Status Bar fixed;
* keeping `[Add a Row]` after the final row.

---

# 8. Architectural Intent

The GUI should now communicate three levels clearly:

```text
WINDOW
    temporal / special region
        Top Area

    flexible cockpit workspace
        Row
            Row Geometry Controls
            Panel
            Panel
            Panel

    application feedback
        Status Bar
```

The visual controls should reinforce this distinction:

* **left-side row strip** = "How is this row shaped?"
* **panel `...` menu** = "What instrument lives here?"
* **outer vertical sash** = "How much space does the special Top Area receive?"

This is still a GUI-layout prototype.

Do not begin implementing real Today-system functionality yet.

The goal of this change is to make the cockpit framework **visually clearer, structurally cleaner, and more pleasant to manipulate**.
