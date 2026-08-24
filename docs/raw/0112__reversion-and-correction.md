```
date: 2026-08-23
```

# Today Cockpit GUI — Revert Vertical Paned Rows and Replace with Independent Drag-Resize Rows

We need to correct the most recent vertical-row architecture change.

The current implementation made the collection of rows into a **vertical `PanedWindow`**, but that turns out to be the wrong model for the cockpit.

## First: restore `experiment.py` from the previous good commit

Current history:

```text
c70642ff17202aad2db577c251902b715f772f2b
    major: made verticality paned, but, ... that was the wrong call...

3f6a85bcfe0796d8d9dafcc30a3bd60ef93f3dfe
    major: minimum heights
```

For **`experiment.py`**, restore the version from:

```text
3f6a85bcfe0796d8d9dafcc30a3bd60ef93f3dfe
```

Do **not** rewind or reset the entire repository unless necessary. Prefer restoring just that file from the earlier commit, e.g. conceptually:

```bash
git restore --source=3f6a85bcfe0796d8d9dafcc30a3bd60ef93f3dfe -- experiment.py
```

or the equivalent safe Git operation.

The goal is:

* keep the repository history intact;
* retain commit `c70642...` as historical evidence of the experiment;
* restore `experiment.py` to the known-good pre-vertical-PanedWindow state;
* then implement the corrected approach from there.

---

# Why the Vertical PanedWindow Approach Was Wrong

The vertical `PanedWindow` treats the rows as panes that must **divide the available viewport height among themselves**.

That is not what we want.

Observed behavior included:

* adding a third row caused existing rows to grow/rearrange unexpectedly;
* the new row could appear effectively hidden below a sash;
* dragging the sash exposed the new row;
* releasing it caused the visible viewport to redistribute itself among all rows;
* deleting a row caused remaining rows to absorb the freed space;
* sash positions caused rows to compete for one fixed vertical space.

This behavior is natural for a `PanedWindow`, but it is wrong for this application.

The important architectural distinction is:

> **Panels within a row are panes. Rows themselves are document blocks.**

Horizontally, panels should divide a row's available width.

Vertically, rows should **accumulate height in a scrollable document**.

---

# Correct Architecture

Keep the existing horizontal `PanedWindow` inside each row.

Do **not** use a vertical `PanedWindow` for the collection of rows.

Return to the scrollable document architecture:

```text
Middle Area
    Canvas
        RowsFrame
            Row 1
                horizontal PanedWindow
                    Panel
                    Panel

            resize handle

            Row 2
                horizontal PanedWindow
                    Panel

            resize handle

            Row 3
                horizontal PanedWindow
                    Panel
                    Panel
                    Panel

            resize handle

            [ Add a Row ]

    Vertical Scrollbar
```

Each row has its own independent explicit/requested height.

Adding rows increases the **total document height**.

Deleting rows decreases the total document height.

Existing rows should not automatically change height when another row is added or removed.

---

# Replace `[-]` / `[v]` with a Draggable Row Resize Handle

The earlier row controls were:

```text
[1]
[2]
[3]

[x]

[-]
[v]
```

The `[-]` and `[v]` buttons should remain removed.

Instead, place a thin horizontal draggable resize handle at the bottom edge of each row.

Conceptually:

```text
┌────┬────────────────────────────────────────────┐
│ 1  │                                            │
│[2] │                ROW 1                       │
│ 3  │                                            │
│ x  │                                            │
└────┴────────────────────────────────────────────┘
══════════════════════════════════════════════════   ← draggable

┌────┬────────────────────────────────────────────┐
│[1] │                                            │
│ 2  │                ROW 2                       │
│ 3  │                                            │
│ x  │                                            │
└────┴────────────────────────────────────────────┘
══════════════════════════════════════════════════   ← draggable
```

The handle may look visually similar to a PanedWindow sash, but it should **not actually be one**.

---

# Resize Behavior

When the user presses and drags a row's bottom resize handle:

* dragging downward makes that row taller;
* dragging upward makes that row shorter;
* only that row's height changes;
* rows below it move up/down naturally in the document;
* rows above it remain unchanged;
* the total `RowsFrame` height changes;
* the Canvas scroll region updates.

This is direct manipulation of the row's own height, not redistribution among neighboring rows.

For example:

```text
before:

Row 1: 220 px
Row 2: 220 px
Row 3: 220 px

drag Row 2 handle down by 96 px

after:

Row 1: 220 px
Row 2: 316 px
Row 3: 220 px
```

The document is now 96 pixels taller.

No other row should surrender space.

---

# Minimum Row Height

The existing default starting row height should also be the **minimum row height**.

A user must not be able to drag a row smaller than that starting/default height.

This preserves:

* visible panel headers;
* visible row controls;
* a usable panel body;
* access to all manipulation controls.

If the default row height is currently, for example, 180 or 200 pixels, use that same value as the minimum.

Do not allow dragging above that minimum.

There is no need for a maximum row height initially.

---

# Mouse Interaction

Implement the row resize handle with normal Tkinter mouse bindings.

Conceptually:

```text
<ButtonPress-1>
    remember starting mouse Y
    remember starting row height

<B1-Motion>
    delta = current mouse screen Y - starting mouse screen Y
    new_height = starting_height + delta
    clamp to minimum height
    apply row height
    update scroll region

<ButtonRelease-1>
    finalize height
```

Use screen/root coordinates if that makes dragging more stable while the Canvas is scrolling.

The cursor should preferably change over the resize handle to something indicating vertical resizing, such as the appropriate north/south resize cursor supported by Tkinter on the platform.

---

# Resize Handle Appearance

The resize affordance should be visible but subtle.

Possible implementation:

* a thin frame, perhaps 4–8 pixels tall;
* dark blue matching the workspace;
* slightly different shade on hover;
* vertical-resize cursor.

It should read as:

> "I can drag this boundary."

Do not make it visually heavy.

It should fit naturally with the existing dark-blue cockpit background.

---

# Preserve Horizontal PanedWindows

Do not change the horizontal panel resizing system.

Each Row still contains a horizontal `PanedWindow` with 1–3 panels:

```text
Row
    [1]
    [2]
    [3]

    [x]

    Horizontal PanedWindow
        Panel 1
        Panel 2
        Panel 3
```

Those sashes should continue behaving exactly as they do now.

This distinction is intentional:

```text
Panel widths:
    true PanedWindow sashes
    panes divide available row width

Row heights:
    custom draggable handles
    rows independently add to document height
```

---

# Preserve Row Controls

Keep the left-side row controls:

```text
[1]
[2]
[3]

[x]
```

The selected pane-count button should remain visibly selected.

Do not restore `[-]` or `[v]`.

---

# Add Row Behavior

Clicking `[Add a Row]` should:

1. Create a new row.
2. Give it the normal default/minimum row height.
3. Give it one panel.
4. Insert it immediately above `[Add a Row]`.
5. Increase the total scrollable document height accordingly.

Critically:

> Adding a row must not resize any existing row.

If three 220px rows exist and a fourth 220px row is added, the document should simply become about 220px taller.

The scrollbar then provides access to content outside the viewport.

---

# Delete Row Behavior

Clicking `[x]` should:

1. Remove that row.
2. Remove its resize handle.
3. Reduce the total document height by that row's height.
4. Leave the heights of all other rows unchanged.
5. Update the Canvas scroll region.

Critically:

> Deleting one row must not cause another row to grow.

---

# Scrolling

Preserve the current scrollable Middle Area.

The model should remain:

```text
Canvas viewport
    scrollable document taller than viewport
```

not:

```text
PanedWindow
    children competing to fill viewport
```

When row heights change, call whatever update is needed so the Canvas's `scrollregion` reflects the new requested height of `RowsFrame`.

---

# Future Layout Persistence

This architecture also makes persistence simpler.

Each row can eventually store an explicit normalized or pixel height.

For now, pixel height is fine internally.

Later, the Today layout aspect might contain something like:

```text
rows:
    - height: 220
      pane_count: 3
      horizontal_sashes: [...]

    - height: 364
      pane_count: 2
      horizontal_sashes: [...]

    - height: 220
      pane_count: 1
      horizontal_sashes: [...]
```

Unlike horizontal sash widths, row height may actually make sense as a pixel-ish user preference because the rows are document blocks rather than proportions of a shared viewport.

Do not over-design persistence yet.

---

# Key Design Principle

The corrected model is:

> **Rows stack. Panels divide.**

Or more explicitly:

> **Rows have independent heights and accumulate vertically in a scrollable document. Panels within each row divide the available width using draggable PanedWindow sashes.**

This is the behavior the GUI should implement.

Do not add new Today-domain functionality as part of this change.
