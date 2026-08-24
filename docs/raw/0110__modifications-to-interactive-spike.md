```
date: 2026-08-23
```

# Today Cockpit GUI — Replace Row Height Buttons with Vertical Sashes

Update the current cockpit prototype so that **row height is controlled by draggable vertical-layout sashes rather than the `[-]` and `[v]` buttons**.

## Current State

Each row currently has a narrow control strip on the left:

```text
[1]
[2]
[3]

[x]

[-]
[v]
```

The `[1]`, `[2]`, and `[3]` controls change the number of horizontal panes in the row.

The `[x]` control deletes the row.

The `[-]` and `[v]` controls currently reduce/increase row height.

## Change

Remove the `[-]` and `[v]` controls entirely.

Keep:

```text
[1]
[2]
[3]

[x]
```

exactly as row-level controls.

Instead, make the collection of rows itself behave like a **vertically oriented paned layout**, so the user can resize adjacent rows by dragging the horizontal sash between them.

Conceptually:

```text
Middle Area
    Scrollable region
        Vertical PanedWindow
            Row 1
                Horizontal PanedWindow
                    Panel
                    Panel
                    Panel

            Row 2
                Horizontal PanedWindow
                    Panel
                    Panel

            Row 3
                Horizontal PanedWindow
                    Panel
```

Each row remains internally a **horizontal `PanedWindow`** controlling the widths of 1–3 panels.

The rows are now children of an outer **vertical `PanedWindow`** controlling their heights.

This gives direct manipulation in both dimensions:

* drag vertical sashes inside a row → resize panel widths
* drag horizontal sashes between rows → resize row heights

## Preserve Minimum Row Height

A row must not be collapsible to an unusably small size.

Use the current/default starting row height as the effective minimum row height, or preserve the existing minimum-height concept already implemented.

The user should always be able to see:

* the row-control strip;
* the panel headers;
* enough of the panel to understand what it is.

Do not allow sash dragging to reduce a row below that minimum.

## Scrolling

The existing Middle Area is vertically scrollable.

Preserve that behavior.

The vertically oriented row `PanedWindow` should live inside the existing scrollable Canvas architecture, or use another implementation that preserves the same result:

* the Top Area does not scroll;
* the Status Bar does not scroll;
* the rows scroll vertically as a group;
* dragging row sashes still works;
* `[Add a Row]` remains accessible after the final row.

If necessary, the vertical `PanedWindow` can be embedded inside the Canvas similarly to the current RowsFrame.

## Add a Row

`[Add a Row]` should continue creating a new row.

The new row should:

* begin with one panel;
* use the normal minimum/default row height;
* participate immediately in the vertical sash layout.

## Delete a Row

The existing `[x]` control should continue deleting its row.

After deletion, the remaining row panes/sashes should reflow cleanly.

## Important Persistence Detail

Tkinter sash positions are stored in **pixel coordinates**, but the eventual Today layout should preferably survive window resizing and different screen/window sizes.

Therefore, when layout persistence is implemented, do **not** treat raw sash pixel positions as the preferred persisted representation.

Instead, save sash positions as normalized proportions.

For a horizontal row sash:

```python
normalized_x = sash_x / available_row_width
```

For a vertical row-height sash:

```python
normalized_y = sash_y / available_rows_height
```

When restoring:

```python
sash_x = normalized_x * current_row_width
sash_y = normalized_y * current_rows_height
```

The exact persistence implementation is not required yet, but structure the code so this will be straightforward.

## Goal

The cockpit should now feel like a directly manipulated tiled workspace:

```text
                drag left/right
                       ↔
┌────┬──────────────────┬──────────────────┐
│123 │ Panel            │ Panel            │
│ x  │                  │                  │
├────┼──────────────────┴──────────────────┤  ↕ drag
│123 │ Panel                               │
│ x  │                                     │
├────┼───────────────┬─────────────────────┤  ↕ drag
│123 │ Panel         │ Panel               │
│ x  │               │                     │
└────┴───────────────┴─────────────────────┘
```

The intended interaction model is:

> **Buttons choose row structure; sashes choose geometry.**

Do not add any additional Today-domain functionality as part of this change.
