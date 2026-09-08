# Mem protocol

Core and Mem communicate with Mobile Stacks.

| Operation | Core continuation | Registers in | Registers back |
| --- | --- | --- |
| `GET_PANEL` | `PANEL_RETURNED` | `panel-id` | `panel` |
| `UPDATE_PANEL` | `PANEL_UPDATED` | `panel-id`, `base-revision`, `proposed-panel` | `update-result`, `panel` |

`UPDATE_PANEL` accepts only when `base-revision` equals Mem's canonical
revision. An accepted panel receives the next revision. A conflict returns the
current canonical panel with `update-result = "conflict"`.
