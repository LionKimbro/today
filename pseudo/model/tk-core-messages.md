# Tk / Core messages

| Direction | Message | Meaning |
| --- | --- | --- |
| Tk → Core | `RENAME_PANEL`, `panel-id` | Rename this panel. |
| Tk → Core | `HOST_PANEL`, `position-id`, `panel-id` | Request that a position host an existing panel. |
| Tk → Core | `UNHOST_PANEL`, `position-id` | Request that this position become empty. |
| Tk → Core | `SELECT_TAB`, `tab-id` | Request that this day's selected tab change. |
| Tk → Core | `SET_ROW_HEIGHT`, `row-id`, `height` | Report a released row sash. |
| Tk → Core | `SET_SASH_PROPORTIONS`, `row-id`, proportions | Report released pane sashes. |
| Tk → Core | `TEXT_CHANGED`, `panel-id`, `text` | Replace Core's working text snapshot. |
| Tk → Core | `TEXT_DEBOUNCE`, `panel-id` | Text input rested; Core may flush it. |
| Tk → Core | `HISTORY_CURSOR_CHANGED`, `panel-id`, `history-cursor` | View HEAD or a snapshot. |
| Tk → Core | `SNAPSHOT`, `panel-id` | Preserve the current HEAD. |
| Tk → Core | `SHUTDOWN` | Stop Core cleanly. |
| Core → Tk | `RENDER_TODAY`, tab plus ordered rows/positions | Reconcile the initial/current structure. |
| Core → Tk | `SET_PANEL_LABEL`, `panel-id`, `panel-label` | Update one panel's visible label. |
| Core → Tk | `RENDER_POSITION`, `position-id`, position fields | Update one position as hosted or empty. |
| Core → Tk | `SET_SELECTED_TAB`, `tab-id` | Select the canonically accepted page tab. |
| Core → Tk | `SET_ROW_HEIGHT`, `row-id`, `height` | Apply accepted row height. |
| Core → Tk | `SET_SASH_PROPORTIONS`, `row-id`, proportions | Apply accepted pane sash positions. |
| Core → Tk | `RENDER_WHITEBOARD_VIEW`, panel view fields | Replace the editor with the selected version. |
| Core → Tk | `SET_WHITEBOARD_HISTORY_CURSOR`, history fields | Update slider and status only. |
| Core → Tk | `SHUTDOWN_COMPLETE` | Tk may close. |

`<<CoreMailAvailable>>` carries no application data: drain the Tk inbox.

Core ↔ Mem uses Mobile Stacks, not these messages.
