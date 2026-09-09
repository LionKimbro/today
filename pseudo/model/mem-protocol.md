# Mem protocol

Core and Mem communicate with Mobile Stacks.

| Operation | Core continuation | Registers in | Registers back |
| --- | --- | --- | --- |
| `GET_DAY_LAYOUT` | `DAY_LAYOUT_RETURNED` | `day-id` | `layout` |
| `GET_PANEL` | `PANEL_RETURNED` | `panel-id` | `panel` |
| `UPDATE_PANEL` | `PANEL_UPDATED` | `panel-id`, `base-revision`, `proposed-panel` | `update-result`, `panel` |
| `HOST_PANEL` | `HOSTING_RETURNED` | `position-id`, `panel-id` | `position-id`, `panel-id`, `unhosted-position-id` |
| `UNHOST_PANEL` | `HOSTING_RETURNED` | `position-id` | `position-id`, `panel-id = null` |

`GET_DAY_LAYOUT` returns the selected day's tabs, rows, positions, and known
panel ids. Core keeps an active copy for reduction and rendering.

`HOST_PANEL` changes Mem's canonical hosting record. If the panel already
appears elsewhere in the same tab, Mem unhosts that earlier position and
returns it. `UNHOST_PANEL` changes only the hosting relation; the panel stays.

`UPDATE_PANEL` accepts only when `base-revision` equals Mem's canonical
revision. An accepted panel receives the next revision. A conflict returns the
current canonical panel with `update-result = "conflict"`.
