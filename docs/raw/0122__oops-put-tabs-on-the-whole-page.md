```
date: 2026-08-24
title: Oops -- the tabs go on the whole page, not the individual panes.
```

# Today Cockpit GUI — Tabs Apply to the Whole Page

The previous tab implementation put tabs **inside individual panes**.

That is not the intended design.

Tabs should instead apply to the **entire middle-page workspace**: the whole collection of rows, panes, panel assignments, row heights, sash positions, etc.

## First: restore `experiment.py`

Before implementing this change, restore `experiment.py` from commit:

```text
2dd09ff1b54d83cfa488ebde0b83190629452790
```

Prefer restoring only `experiment.py`, not resetting the entire repository.

For example:

```bash
git restore --source=2dd09ff1b54d83cfa488ebde0b83190629452790 -- experiment.py
```

The goal is to return to the last good version **before per-pane tabs were introduced**, while preserving Git history.

---

## Correct Structure

The intended hierarchy is:

```text
Today Window
    Top Area

    Page Tabs
        Page
            Scrollable Rows
                Row
                    Pane
                        Panel

    Status Bar
```

A tab therefore represents an entire **page/workspace layout**.

Conceptually:

```text
┌─────────────────────────────────────────────────────┐
│ Top Area                                            │
├─────────────────────────────────────────────────────┤
│ [ Tab A ] [ Tab B ] [ + ]                          │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Row 1                                             │
│   ┌───────────────┬─────────────────────────────┐   │
│   │ Panel         │ Panel                       │   │
│   └───────────────┴─────────────────────────────┘   │
│                                                     │
│   Row 2                                             │
│   ┌─────────────────────────────────────────────┐   │
│   │ Panel                                       │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│                         [ Add a Row ]               │
│                                                     │
├─────────────────────────────────────────────────────┤
│ Status Bar                                          │
└─────────────────────────────────────────────────────┘
```

Switching tabs swaps the entire middle workspace.

---

## Creating Tabs

The final tab is always:

```text
[ + ]
```

Clicking `+` creates a new page tab immediately before it.

Initial state:

```text
[ Tab A ] [ + ]
```

After clicking `+`:

```text
[ Tab A ] [ Tab B ] [ + ]
```

Then:

```text
[ Tab A ] [ Tab B ] [ Tab C ] [ + ]
```

The newly created tab should become selected immediately.

Each new page should begin with a sensible default page layout, such as one row with one pane.

---

## Tab Identity

Each real tab/page should have:

* an internal GUID;
* a user-visible name.

Example:

```text
id: 550e8400-e29b-41d4-a716-446655440000
name: "Tab A"
```

The visible name is not identity.

Renaming a tab must not change its GUID.

The `+` tab is only a UI sentinel and does not need a GUID.

---

## Rename / Delete

Double-clicking a normal tab should open a small dialog allowing:

* Rename
* Delete
* Cancel

Example:

```text
Page Name:
[ Planning                         ]

[ Rename ]   [ Delete ]   [ Cancel ]
```

Double-clicking `+` should do nothing.

A page should preferably not allow deletion of the final remaining real tab.

---

## Each Tab Owns Its Own Layout

Each page/tab has its own independent middle-area layout.

That includes:

* number of rows;
* row heights;
* number of panes in each row;
* horizontal pane sash positions;
* panel assignments;
* eventual panel-specific state;
* eventual scroll position.

Example:

```text
Tab A
    Row 1: 2 panes
    Row 2: 1 pane

Tab B
    Row 1: 3 panes
    Row 2: 2 panes
    Row 3: 1 pane
```

Changing Tab B must not alter Tab A.

---

## Preserve Existing Row/Panels Architecture

Inside each page, preserve the current cockpit behavior:

* vertically scrollable collection of rows;
* rows have independent heights;
* row heights are changed via draggable resize handles;
* rows do not divide the viewport height proportionally;
* each row contains 1–3 horizontal panes;
* horizontal pane sizing still uses `PanedWindow` sashes;
* `[1] [2] [3] [x]` controls remain on the left side of each row;
* `[Add a Row]` remains at the bottom of the current page.

The key model remains:

> **Rows stack. Panels divide. Pages switch.**

---

## No Tabs Inside Panes

Do not retain the previous architecture where individual panes contained their own tab notebooks.

For now:

```text
Pane
    Panel
```

not:

```text
Pane
    Tabs
        Panel
        Panel
```

Tabs belong one level much higher.

---

## Future Persistence Shape

No full M1 persistence is required yet, but structure the data so a future layout representation could look approximately like:

```text
layout:
    pages:
        - id: "<guid>"
          name: "Tab A"
          rows:
              ...

        - id: "<guid>"
          name: "Planning"
          rows:
              ...

    selected_page: "<guid>"
```

The `+` tab is not persisted as a page.

---

## Design Intent

The page tabs are intended to let the user maintain multiple **whole cockpit arrangements** for the same day.

For example:

```text
Daily
Planning
Writing
Review
```

Each can present the same underlying Today data differently.

The important abstraction is:

> **A tab is a page, and a page is a complete arrangement of rows and panels.**

Implement only this structural behavior for now. Do not add new Today-domain functionality as part of this change.
