# `mem.py`

OWNS: canonical in-memory `days`, `tabs`, `rows`, `positions`, and `panels`.

`GET_PANEL` deep-copies the requested panel into the current stack registers.
The canonical record stays owned by Mem, including nested mutable data.

`GET_DAY_LAYOUT` returns a copied active-day layout. `HOST_PANEL` and
`UNHOST_PANEL` canonically change only `positions[position-id]["panel-id"]`.
An unseen requested day is seeded as Tab A → one row → one position → one
day-owned Whiteboard, plus a day-owned Orientation panel in its top slot.
`SELECT_TAB` canonically changes `days[day-id]["selected-tab-id"]`.
`SET_ROW_HEIGHT` and `SET_SASH_PROPORTIONS` canonically change one row.
`MOVE_ROW` canonically reorders a tab's row ids.
`ADD_ROW` appends a new empty row with a Mem-minted identity.
`DELETE_ROW` preserves its panels and removes a non-final row.
`SET_ROW_COLUMN_COUNT` changes one row's derived position slots.
`SET_TAB_SCROLL_POSITION` canonically changes one tab's visible vertical
fraction.
`CREATE_TAB`, `RENAME_TAB`, and `DELETE_TAB` canonically manage a day's tabs.

Stage 7C seeds `whiteboard-a`, `whiteboard-b`, and unhosted `whiteboard-c`.

Whiteboard records also canonically carry newest-first snapshot history.

`UPDATE_PANEL` accepts only a matching base revision, then returns the accepted
canonical panel with its incremented revision.
