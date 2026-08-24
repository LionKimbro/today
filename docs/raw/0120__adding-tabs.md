```
date: 2026-08-24
title: Adding Tabs
```

# Today Cockpit GUI — Add Tabbed Panel Hosts

Add lightweight tab support to each pane in the cockpit.

The goal is to make tabs part of the pane structure **now**, before panel semantics and persistence become more complicated.

This should remain a small structural feature, not a large subsystem.

---

## Core Model

Each pane should contain a **tabbed host** rather than directly containing a single panel.

Conceptually:

```text
Row
    Pane
        TabbedHost
            Tab
                Panel
            Tab
                Panel
            "+"
```

The tabbed host may be implemented with `ttk.Notebook` or an equivalent Tkinter mechanism.

Each normal tab contains one panel.

The final tab is always a special **`+` tab** used to create new tabs.

---

# Initial State

When a pane is first created, it should contain:

```text
[ Tab A ] [ + ]
```

`Tab A` is a normal tab.

`+` is the special new-tab control.

A pane should never start empty.

---

# Creating a New Tab

The final tab always displays:

```text
+
```

When the user clicks the `+` tab:

1. Create a new normal tab immediately before the `+` tab.
2. Give the new tab a default display name.
3. Select the new tab.
4. Leave a fresh `+` tab at the end.

Example:

Before:

```text
[ Tab A ] [ + ]
```

Click `+`.

After:

```text
[ Tab A ] [ Tab B ] [ + ]
```

Click `+` again:

```text
[ Tab A ] [ Tab B ] [ Tab C ] [ + ]
```

Default names should proceed approximately:

```text
Tab A
Tab B
Tab C
...
```

The exact naming strategy is not important as long as new tabs get unique, readable default names.

---

# Tab Identity

Each normal tab should have a stable internal **GUID**.

The GUID is the identity of the tab.

The visible name such as:

```text
Tab A
```

is only a user-editable label.

Renaming a tab must not change its GUID.

Conceptually:

```text
Tab
    id: <GUID>
    name: "Tab A"
    panel: ...
```

Do not use the tab name as its identity.

---

# Renaming and Deleting Tabs

Double-clicking a normal tab should open a small modal dialog.

The dialog should allow the user to:

* rename the tab;
* delete the tab;
* cancel/close the dialog.

Conceptually:

```text
Tab Name:
[ Fair Play Notes              ]

[ Rename ]   [ Delete ]   [ Cancel ]
```

The exact button labels may vary slightly.

Double-clicking the `+` tab should do nothing.

---

# Rename Behavior

If the user edits the name and chooses Rename:

* update the visible tab text;
* retain the same GUID;
* close the dialog.

Renaming should have no effect on the panel contents.

---

# Delete Behavior

If the user chooses Delete:

* remove that normal tab;
* remove its associated panel instance;
* leave all other tabs unchanged;
* preserve the final `+` tab.

If deleting the selected tab, select a sensible neighboring normal tab afterward.

For this prototype, deleting tab contents can be destructive because real Today data has not yet been implemented.

---

# Minimum Number of Normal Tabs

A pane should always contain at least **one normal tab**.

If the pane contains only:

```text
[ Tab A ] [ + ]
```

then either:

* disable Delete for `Tab A`, or
* refuse deletion and leave the tab intact.

Do not allow the pane to become:

```text
[ + ]
```

with no real tab.

---

# The `+` Tab Is Not a Real Tab

The `+` tab is a UI sentinel only.

It should:

* have no GUID;
* contain no meaningful panel;
* never become part of persisted content state;
* always remain last;
* never be renameable;
* never be deleteable.

Its sole purpose is:

> Create another tab.

---

# Panel Relationship

Each normal tab contains exactly one Panel host.

For now, that Panel may remain the current placeholder panel.

Conceptually:

```text
Pane
    Tab A
        Panel
            Empty Panel

    Tab B
        Panel
            Empty Panel
```

Later, different tabs may display different panel types:

```text
Pane
    Today Notes
        WhiteboardPanel

    Tasks
        TodoPanel

    Metrics
        MetricsPanel
```

Do not implement those real panel types as part of this change.

---

# Panel Menus

The existing panel-level `...` menu should continue to belong to the panel inside the selected tab.

Tabs and panel types are separate concepts:

> **Tab = named slot inside a pane.**

> **Panel = instrument/content hosted by that tab.**

The tab name may eventually be independent of the panel type.

For example:

```text
Tab name:
    "Fair Play"

Panel type:
    Whiteboard
```

or:

```text
Tab name:
    "Morning"

Panel type:
    Todo
```

Do not conflate tab names with panel types.

---

# Visual Behavior

The tab system should feel lightweight.

The tab strip should sit naturally at the top of each pane.

Example:

```text
┌─────────────────────────────────────────────┐
│ [ Tab A ] [ Tab B ] [ + ]                  │
├─────────────────────────────────────────────┤
│ Empty Panel                             ... │
│                                             │
│                                             │
└─────────────────────────────────────────────┘
```

Do not add a separate permanent tab-management toolbar.

Tab creation is done through `+`.

Tab rename/delete is done through double-click.

That should be sufficient.

---

# Preserve Existing Cockpit Behavior

Do not regress:

* scrollable rows;
* independent row heights;
* draggable row resize handles;
* horizontal pane sashes;
* `[1] [2] [3] [x]` row controls;
* adding rows;
* deleting rows;
* Top Area resizing;
* Status Bar;
* window resizing;
* panel `...` menus;
* dark-blue cockpit styling.

---

# Future Persistence

Do not implement full M1 persistence yet unless convenient.

However, structure the tab state so that it can later serialize approximately like:

```text
pane:
    tabs:
        - id: "<guid>"
          name: "Tab A"
          panel: ...

        - id: "<guid>"
          name: "Fair Play"
          panel: ...

    selected_tab: "<guid>"
```

The `+` tab should not appear in persisted state.

---

# Architectural Principle

The cockpit hierarchy should now be understood as:

```text
Row
    Pane
        Tab
            Panel
```

These are four distinct concepts:

* **Row** controls vertical placement and height.
* **Pane** controls horizontal geometry.
* **Tab** provides multiple named workspaces within one pane.
* **Panel** provides the actual instrument/content.

The final `+` tab is simply the mechanism for creating another Tab.

---

# Success Criteria

The change is successful if:

1. Every pane starts with `Tab A` and `+`.
2. Clicking `+` creates and selects `Tab B`.
3. Repeated clicking creates `Tab C`, `Tab D`, etc.
4. `+` always remains last.
5. Double-clicking a normal tab opens a rename/delete dialog.
6. Renaming changes only the display name.
7. Each normal tab retains a GUID internally.
8. Deleting removes the selected tab cleanly.
9. A pane cannot lose its final normal tab.
10. All existing cockpit resizing and scrolling behavior continues to work.

The implementation should remain simple.

The purpose is to make the cockpit **tab-capable before richer panel/content semantics are added**.
