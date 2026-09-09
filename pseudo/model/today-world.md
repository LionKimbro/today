# Today world

**Conceptual path:** day → tab → position → hosted panel identity

| Thing | Current owner | Current role |
| --- | --- | --- |
| day | Core | Current day workspace; moves to Mem with canonical layout in 7C |
| tab | Core | Current visible tab layout |
| row | Core | Ordered tab row with a logical column count |
| position | Core | Derived `row-id/column-N` location and hosted `panel-id` |
| panel | Mem | Canonical panel record |
| visible panel | Core | Renderable snapshot of a Mem panel |

`row-a/column-1` hosts `panel-1`; it does not contain or become the panel.
