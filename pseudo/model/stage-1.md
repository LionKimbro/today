# Stage 1 world

**Path:** day → tab → position → hosted panel identity

| Collection | Key | Record |
| --- | --- | --- |
| `days` | `<today-id>` — e.g. `2026-09-06` | `id`, `tab-ids` |
| `tabs` | `<tab-id>` — e.g. `tab-a` | `id`, `day-id`, `label`, `position-ids` |
| `positions` | `<position-id>` — e.g. `position-1` | `id`, `tab-id`, `panel-id` |
| `panels` | `<panel-id>` — e.g. `panel-1` | `id`, `label` |

`position-1` hosts `panel-1`; it does not contain or become the panel.
