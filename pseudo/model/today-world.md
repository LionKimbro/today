# Today world

**Conceptual path:** day → tab → position → hosted panel identity

A day selects one of its tabs. A tab owns ordered rows; a row defines its
logical position slots.

A future day-owned special slot sits outside the tabs. It may host a compatible
special panel type; Orientation is one such panel, not the slot itself.

| Thing | Current owner | Current role |
| --- | --- | --- |
| day | Mem | Canonical workspace; Core retains its active snapshot |
| tab | Mem | Canonical layout within its day |
| row | Mem | Ordered tab row with a logical column count |
| position | Mem | Derived `row-id/column-N` location and hosted `panel-id` |
| panel | Mem | Canonical panel record |
| visible panel | Core | Renderable snapshot of a Mem panel |

`row-a/column-1` hosts `panel-1`; it does not contain or become the panel.
