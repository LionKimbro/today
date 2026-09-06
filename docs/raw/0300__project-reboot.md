```
date: 2026-09-06
chatgpt: https://chatgpt.com/c/6a9cf89b-4860-83e8-8cd0-634dcd19a115
title: Major Reboot -- initial instruction
```

# Today — Stage 1

We are beginning a new implementation lineage of **Today**, a daily cockpit application.

This is intentionally a very small first stage. Do not anticipate later architecture unless explicitly instructed.

## Purpose of this stage

Prove the basic structural grammar of Today in a simple, working Tkinter application.

At startup:

* There is one day: **today**.
* The day has one tab: **Tab A**.
* Tab A has one position: **position-1**.
* `position-1` hosts one panel.
* The panel should have its own identity, separate from the position that hosts it.

The conceptual relationship is:

```text
day
    -> tab
        -> position
            -> hosted panel
```

A position does **not** contain or become the panel. A position hosts a panel.

For example:

```text
position-1 hosts panel-1
```

This distinction is important and should be preserved in the data model even though Stage 1 contains only one position and one panel.

## Threading

Stage 1 is deliberately **single-threaded**.

Everything runs on the normal Tk/main thread.

Do not introduce:

* worker threads
* queues
* Reducer Core
* Mem machine
* Disk machine
* Mobile Stacks

Those belong to later stages.

## UI scope

Build only enough interface to make the structure visible and usable:

```text
Today
--------------------------------

[today's date]

[ Tab A ]

+-----------------------------+
|                             |
|          panel-1            |
|                             |
+-----------------------------+
```

The exact visual styling is not important yet.

The structural concepts are important.

## Future compatibility

Later stages will introduce:

* separation between Tk and a Reducer Core
* Mem as an authoritative world model
* Mobile Stacks for cross-machine work
* multiple panels
* panel creation and retrieval
* multiple positions
* rich tab/row/pane layout derived from an earlier working Today prototype
* disk persistence

Do **not** implement these now.

However, Stage 1 should avoid choices that obviously make those later concepts impossible.

In particular:

* Keep panel identity distinct from position identity.
* Keep the logical day/tab/position/panel structure intelligible.
* Do not bury application meaning inside anonymous widget structures.
* Do not create abstractions merely because later stages might need them.

## Success condition

Stage 1 is complete when the program starts and visibly demonstrates:

> Today knows the current day; that day has Tab A; Tab A has `position-1`; and `position-1` hosts an identifiable panel.

Nothing more is required for this stage.
