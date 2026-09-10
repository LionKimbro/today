# Positions and panels

## Positions

Mem canonically owns days, tabs, rows, positions, and panels. Core retains the
active layout snapshot. The current tab owns ordered row identities. `rows` maps each row id to its
logical column count: `1`, `2`, or `3`.

Each row also carries `height` in pixels and `sash-proportions`: cumulative
fractions for its internal pane sashes. They are canonical layout meaning.

Rearranging rows changes the tab's row order, not the identity of a row or
position.

`positions` maps a derived, durable position id to one hosting record.

| Field | Meaning |
| --- | --- |
| `panel-id` | Panel currently hosted there |

```text
rows["row-a"] = {"column-count": 2}

positions["row-a/column-1"] = {"panel-id": "panel-1"}
positions["row-a/column-2"] = {"panel-id": null}
```

The position id is used unchanged by Tk, Core, Mem, and later Disk. It is
derived from the row id and logical column; no redundant position ordering is
kept.

## Panels

Mem canonically owns `panels`, mapping a panel id to its record.

Core may retain a visible panel snapshot; Mem remains canonical.

| Field | Meaning |
| --- | --- |
| `id` | Panel identity |
| `day-id` | Owning day identity |
| `type` | `WHITEBOARD`, `TODO`, `JOURNAL`, or top-slot-only `ORIENTATION` |
| `label` | Visible label |
| `text` | Panel text |
| `history` | Whiteboard snapshots only |
| `revision` | Canonical update revision |

## Hosting

`positions[position-id]["panel-id"]` names the panel hosted by that position.

Changing the field changes hosting. `null` means unhosted, not an empty panel.
The position and panel record remain.

A panel appears at most once in a tab. The same panel may appear in another
tab's position on its owning day.

The day-owned `orientation-position` is outside this tab geometry. It hosts
one fixed `ORIENTATION` panel for now; it has text and revisions, but no
history.

An empty ordinary position offers existing eligible panels plus creation of a
Whiteboard, To-Do, or Journal.

## To-Do panels

A To-Do panel's canonical `text` is one item per line:

```text
[ ] Open item
[>] Working item
[x] Done item
```

`List` and `Text` are Tk presentations of that one record. List controls send
semantic item events; Text editing uses the ordinary one-second debounce.
Either path becomes the normal revisioned `UPDATE_PANEL` request to Mem.

Journal remains a plain text panel for now.

Deleting a panel is distinct from unhosting: it removes the day-owned record
and every ordinary hosting reference to it.

Core's snapshot may additionally hold `dirty`, `awaiting`, `edit-generation`,
and `save-generation`. Those are working facts, never canonical Mem fields.
