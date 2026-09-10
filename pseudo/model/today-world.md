# Today world

**Conceptual path:** day → tab → position → hosted panel identity

A day selects one of its tabs. A tab owns ordered rows; a row defines its
logical position slots.

Each day currently has an `orientation-position` outside its tabs. It hosts an
`ORIENTATION` panel. Orientation is the panel, not the slot.

| Thing | Current owner | Current role |
| --- | --- | --- |
| day | Mem | Canonical workspace; Core retains its active snapshot |
| tab | Mem | Canonical layout within its day, including its scroll position |
| row | Mem | Ordered tab row with a logical column count |
| position | Mem | Derived `row-id/column-N` location and hosted `panel-id` |
| orientation position | Mem day record | Top special position and hosted `panel-id` |
| panel | Mem | Canonical record owned by one day |
| visible panel | Core | Renderable snapshot of a Mem panel |

`row-a/column-1` hosts `panel-1`; it does not contain or become the panel.

Panels carry `day-id`. A position may host only a panel owned by the same day.
Core keeps `current-day-id`: the day whose active layout it is reducing and
rendering.

An unseen day requested by Core is created in Mem with **Tab A**, one row, one
position, one day-owned Whiteboard, and one Orientation panel. Disk has no
role yet.
