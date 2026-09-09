# `mem.py`

OWNS: canonical in-memory `days`, `tabs`, `rows`, `positions`, and `panels`.

`GET_PANEL` deep-copies the requested panel into the current stack registers.
The canonical record stays owned by Mem, including nested mutable data.

`GET_DAY_LAYOUT` returns a copied active-day layout. `HOST_PANEL` and
`UNHOST_PANEL` canonically change only `positions[position-id]["panel-id"]`.
`SELECT_TAB` canonically changes `days[day-id]["selected-tab-id"]`.
`SET_ROW_HEIGHT` and `SET_SASH_PROPORTIONS` canonically change one row.

Stage 7C seeds `whiteboard-a`, `whiteboard-b`, and unhosted `whiteboard-c`.

Whiteboard records also canonically carry newest-first snapshot history.

`UPDATE_PANEL` accepts only a matching base revision, then returns the accepted
canonical panel with its incremented revision.
