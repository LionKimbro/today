# Tk / Core messages

| Direction | Message | Meaning |
| --- | --- | --- |
| Tk → Core | `RENAME_PANEL`, `panel-id` | Rename this panel. |
| Tk → Core | `SHUTDOWN` | Stop Core cleanly. |
| Core → Tk | `RENDER_TODAY`, visible world fields | Reconcile the initial/current structure. |
| Core → Tk | `SET_PANEL_LABEL`, `panel-id`, `panel-label` | Update one panel's visible label. |
| Core → Tk | `SHUTDOWN_COMPLETE` | Tk may close. |

`<<CoreMailAvailable>>` carries no application data: drain the Tk inbox.

Core ↔ Mem uses Mobile Stacks, not these messages.
