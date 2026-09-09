# Mem protocol

Core and Mem communicate with Mobile Stacks.

| Operation | Core continuation | Registers in | Registers back |
| --- | --- | --- | --- |
| `GET_DAY_LAYOUT` | `DAY_LAYOUT_RETURNED` | `day-id` | `layout` |
| `SELECT_TAB` | `SELECTED_TAB_RETURNED` | `day-id`, `tab-id` | `day-id`, `tab-id` |
| `SET_ROW_HEIGHT` | `ROW_LAYOUT_RETURNED` | `row-id`, `height` | `row`, `layout-change` |
| `SET_SASH_PROPORTIONS` | `ROW_LAYOUT_RETURNED` | `row-id`, `sash-proportions` | `row`, `layout-change` |
| `SET_ROW_COLUMN_COUNT` | `ROW_LAYOUT_RETURNED` | `row-id`, `column-count` | `row`, `layout-change` |
| `MOVE_ROW` | `TAB_LAYOUT_RETURNED` | `tab-id`, `row-id`, `direction` | `tab` |
| `ADD_ROW` | `TAB_LAYOUT_RETURNED` | `tab-id` | `tab`, `row` |
| `DELETE_ROW` | `TAB_LAYOUT_RETURNED` | `tab-id`, `row-id` | `tab`, `deleted-row-id` |
| `SET_TAB_SCROLL_POSITION` | `TAB_LAYOUT_RETURNED` | `tab-id`, `scroll-position` | `tab` |
| `CREATE_TAB` | `TAB_CREATED_RETURNED` | `day-id` | `day`, `tab`, `row` |
| `RENAME_TAB` | `TAB_RENAMED_RETURNED` | `tab-id`, `label` | `tab` |
| `DELETE_TAB` | `TAB_DELETED_RETURNED` | `day-id`, `tab-id` | `day`, `tab-id`, `deleted` |
| `GET_PANEL` | `PANEL_RETURNED` | `panel-id` | `panel` |
| `UPDATE_PANEL` | `PANEL_UPDATED` | `panel-id`, `base-revision`, `proposed-panel` | `update-result`, `panel` |
| `HOST_PANEL` | `HOSTING_RETURNED` | `position-id`, `panel-id` | `position-id`, `panel-id`, `unhosted-position-id` |
| `UNHOST_PANEL` | `HOSTING_RETURNED` | `position-id` | `position-id`, `panel-id = null` |

`GET_DAY_LAYOUT` returns the selected day's tabs, rows, positions, and known
panel ids. Core keeps an active copy for reduction and rendering.

`SELECT_TAB` changes the selected tab in the canonical day record.

The geometry operations update one canonical row. Tk supplies measured sash
results; Core renders Mem's accepted row geometry back to Tk.

`MOVE_ROW` changes only a tab's ordered `row-ids`. Rows, derived positions,
and hosted panels retain their identities.

`ADD_ROW` appends a new one-column row with an empty derived position. Mem
mints the row identity. `SET_TAB_SCROLL_POSITION` accepts the tab's visible
vertical fraction without changing its layout.

`SET_ROW_COLUMN_COUNT` creates or removes derived positions. Removed positions
unhost their panels; panels remain canonical. A tab keeps at least one row and
a day keeps at least one tab.

`HOST_PANEL` changes Mem's canonical hosting record. If the panel already
appears elsewhere in the same tab, Mem unhosts that earlier position and
returns it. `UNHOST_PANEL` changes only the hosting relation; the panel stays.

`UPDATE_PANEL` accepts only when `base-revision` equals Mem's canonical
revision. An accepted panel receives the next revision. A conflict returns the
current canonical panel with `update-result = "conflict"`.
